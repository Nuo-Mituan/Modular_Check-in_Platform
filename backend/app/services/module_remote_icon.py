"""SSRF-conscious remote module icon proxy.

The module model is global (no owner/tenant column); this proxy relies on the
same authenticated access as GET /api/modules. If ownership is introduced,
an ownership check MUST be added here.

DNS is resolved before each request and every resolved address is checked
against the deny set. A TOCTOU window remains because httpx resolves again at
connect time; the stable public httpx API does not expose IP pinning with SNI.
This residual risk is accepted for TD-22.
"""
from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import logging
import socket
import time
from collections import OrderedDict
from typing import Final
from urllib.parse import urljoin, urlsplit

import httpx

from ..config import settings
from .icon_policy import detect_icon_format, is_svg, ICON_UNSUPPORTED_DETAIL, ICON_ALLOWED, FORMAT_TO_CONTENT_TYPE
from .remote_url import (
    REMOTE_HTTP_ERROR,
    RemoteUrlError,
    is_insecure_host_allowed,
    normalize_remote_url,
)

logger = logging.getLogger(__name__)

REMOTE_ICON_ERROR: Final = "远程图标不可用"
REMOTE_ICON_FORMAT_ERROR: Final = "远程图标格式不支持"
CONTENT_TYPE_ALIASES = {"image/jpg": "image/jpeg"}
ALLOWED_TYPES = frozenset(FORMAT_TO_CONTENT_TYPE[fmt] for fmt in ICON_ALLOWED) | {"image/vnd.microsoft.icon"}
CACHE_MAX = 64
NEGATIVE_MAX = 256


class RemoteIconError(Exception):
    def __init__(self, status_code: int = 502, detail: str = REMOTE_ICON_ERROR):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def _safe_url(url: str) -> str:
    try:
        p = urlsplit(url)
        return f"{p.scheme}://{p.hostname or ''}"
    except ValueError:
        return "<invalid-url>"


def _denied(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    # IPv4 RFC1918 is intentionally allowed for internal https targets.
    # IPv6 unique-local fc00::/7 and link-local are denied; IPv4 link-local
    # 169.254/16 is covered by is_link_local. This mirrors TD-21's literal policy.
    if address.is_unspecified or address.is_loopback or address.is_link_local:
        return True
    return isinstance(address, ipaddress.IPv6Address) and address.is_private


async def _resolve(host: str, port: int) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    infos = await asyncio.to_thread(socket.getaddrinfo, host, port, type=socket.SOCK_STREAM)
    result = []
    for info in infos:
        try:
            result.append(ipaddress.ip_address(info[4][0]))
        except ValueError:
            continue
    if not result:
        raise RemoteIconError()
    return result


async def _validate_target(url: str) -> None:
    try:
        normalize_remote_url(url, field_label="远程图标")
    except RemoteUrlError as exc:
        raise RemoteIconError(502, str(exc)) from exc
    parsed = urlsplit(url)
    host = parsed.hostname or ""
    if parsed.scheme.lower() == "http":
        # Proxy is stricter than TD-21: allow-list is intentionally ignored.
        if not is_insecure_host_allowed(host, allow_hosts=set()):
            raise RemoteIconError(502, REMOTE_HTTP_ERROR)
        return
    try:
        port = parsed.port or 443
    except ValueError as exc:
        raise RemoteIconError() from exc
    if any(_denied(ip) for ip in await _resolve(host, port)):
        raise RemoteIconError()


def _sniff(data: bytes) -> str:
    fmt = detect_icon_format(data)
    if fmt is None or is_svg(data):
        raise RemoteIconError(415, REMOTE_ICON_FORMAT_ERROR)
    return {"png": "image/png", "jpeg": "image/jpeg", "gif": "image/gif", "webp": "image/webp", "ico": "image/x-icon"}[fmt]


async def _fetch(url: str) -> tuple[bytes, str, str]:
    await _validate_target(url)
    timeout = httpx.Timeout(settings.remote_icon_timeout_seconds, connect=settings.remote_icon_connect_timeout_seconds)
    async with httpx.AsyncClient(follow_redirects=False, timeout=timeout, trust_env=False,
                                 headers={"Accept": "image/*", "User-Agent": "ModularCheckin/1.0"}) as client:
        current = url
        redirects = 0
        while True:
            try:
                async with client.stream("GET", current) as response:
                    if response.status_code in {301, 302, 303, 307, 308}:
                        location = response.headers.get("location")
                        if not location:
                            raise RemoteIconError()
                        next_url = urljoin(current, location)
                        nxt = urlsplit(next_url)
                        if nxt.username is not None or nxt.password is not None:
                            raise RemoteIconError()
                        if urlsplit(current).scheme == "https" and nxt.scheme != "https":
                            raise RemoteIconError()
                        redirects += 1
                        if redirects > 3:
                            raise RemoteIconError()
                        await _validate_target(next_url)
                        current = next_url
                        continue
                    if response.status_code != 200:
                        raise RemoteIconError()
                    source = (response.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
                    source = CONTENT_TYPE_ALIASES.get(source, source)
                    chunks = []
                    total = 0
                    async for chunk in response.aiter_bytes():
                        total += len(chunk)
                        if total > settings.remote_icon_max_bytes:
                            raise RemoteIconError()
                        chunks.append(chunk)
                    data = b"".join(chunks)
                    magic = _sniff(data[:16])
                    if source and source not in {"application/octet-stream", ""} and source != magic:
                        raise RemoteIconError(415, REMOTE_ICON_FORMAT_ERROR)
                    if not source or source == "application/octet-stream":
                        logger.warning("远程图标源站 Content-Type 缺失/泛化，按魔数处理 module_url=%s", _safe_url(current))
                    return data, magic, hashlib.sha256(data).hexdigest()
            except (httpx.HTTPError, OSError, asyncio.TimeoutError) as exc:
                logger.warning("远程图标拉取失败 module_url=%s error=%s", _safe_url(current), type(exc).__name__)
                raise RemoteIconError() from exc
    raise RemoteIconError()


_CACHE: OrderedDict[tuple[int, str], tuple[bytes, str, str, float]] = OrderedDict()
_NEGATIVE: dict[tuple[int, str], float] = {}
_INFLIGHT: dict[tuple[int, str], asyncio.Task[tuple[bytes, str, str]]] = {}


def _cache_key(module_id: int, url: str) -> tuple[int, str]:
    return (module_id, url)


def _purge_negative(now: float) -> None:
    for key, expiry in list(_NEGATIVE.items()):
        if expiry <= now:
            _NEGATIVE.pop(key, None)
    while len(_NEGATIVE) > NEGATIVE_MAX:
        _NEGATIVE.pop(next(iter(_NEGATIVE)))


async def get_remote_icon(module_id: int, url: str) -> tuple[bytes, str, str]:
    key = _cache_key(module_id, url)
    now = time.monotonic()
    _purge_negative(now)
    cached = _CACHE.get(key)
    if cached and cached[3] > now:
        _CACHE.move_to_end(key)
        return cached[0], cached[1], cached[2]
    if _NEGATIVE.get(key, 0) > now:
        raise RemoteIconError()
    task = _INFLIGHT.get(key)
    if task is None:
        task = asyncio.create_task(_fetch(url))
        _INFLIGHT[key] = task
    try:
        data, content_type, digest = await task
    except Exception:
        _NEGATIVE[key] = time.monotonic() + settings.remote_icon_negative_ttl_seconds
        raise
    finally:
        _INFLIGHT.pop(key, None)
    _CACHE[key] = (data, content_type, digest, time.monotonic() + settings.remote_icon_cache_ttl_seconds)
    _CACHE.move_to_end(key)
    while len(_CACHE) > CACHE_MAX:
        _CACHE.popitem(last=False)
    return data, content_type, digest
