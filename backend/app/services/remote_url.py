"""Synchronous policy for user-supplied remote URLs.

Only literal hosts are classified.  Hostnames are not resolved: this avoids
DNS/async coupling and prevents a public hostname from being treated as local.
"""
from __future__ import annotations

import ipaddress
import logging
from urllib.parse import urlsplit

from ..config import settings

logger = logging.getLogger(__name__)

REMOTE_HTTP_ERROR = (
    "远程地址使用 http:// 时仅允许本地或内网地址，公网请使用 https://"
)


class RemoteUrlError(ValueError):
    pass


def _allow_hosts() -> set[str]:
    return {
        item.strip().lower()
        for item in str(settings.remote_http_allow_hosts or "").split(",")
        if item.strip()
    }


def is_insecure_host_allowed(host: str, allow_hosts: set[str] | None = None) -> bool:
    """Return whether a literal http host is explicitly exempted."""
    if not host:
        return False
    normalized = host.strip().lower()
    if normalized == "localhost":
        return True
    if normalized in (allow_hosts if allow_hosts is not None else _allow_hosts()):
        return True
    try:
        address = ipaddress.ip_address(normalized)
    except ValueError:
        # Hostname: never resolve and never exempt implicitly.
        return False
    if address.is_unspecified or address.is_link_local:
        return False
    # Reject IPv4-mapped IPv6 rather than treating ::ffff:127.0.0.1 as loopback.
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        return False
    return bool(address.is_loopback or address.is_private)


def normalize_remote_url(value: str, *, field_label: str = "远程地址") -> str:
    """Validate a remote URL without rewriting it.

    https is always accepted; http is accepted only for literal local/private
    hosts or the configured allow-list.
    """
    text = str(value or "").strip()
    try:
        parsed = urlsplit(text)
    except ValueError as exc:
        raise RemoteUrlError(f"{field_label} URL 无效") from exc
    if parsed.scheme.lower() not in {"http", "https"}:
        raise RemoteUrlError(f"{field_label} 必须是 http:// 或 https:// 地址")
    host = parsed.hostname
    if not host:
        raise RemoteUrlError(f"{field_label} URL 缺少主机名")
    if parsed.scheme.lower() == "http" and not is_insecure_host_allowed(host):
        raise RemoteUrlError(REMOTE_HTTP_ERROR)
    return text


def validate_remote_url(value: str, *, field_label: str = "远程地址") -> str:
    return normalize_remote_url(value, field_label=field_label)
