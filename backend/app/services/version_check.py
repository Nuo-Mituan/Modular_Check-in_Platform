"""Cached GitHub release check for the public version endpoint."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import threading
import time
import urllib.request
from dataclasses import dataclass

logger = logging.getLogger(__name__)

RELEASE_URL = "https://api.github.com/repos/Nuo-Mituan/Modular_Check-in_Platform/releases/latest"
SUCCESS_TTL = 3600.0
FAILURE_TTL = 300.0


@dataclass(frozen=True)
class LatestRelease:
    tag_name: str
    html_url: str | None = None


_lock = threading.Lock()
_cached_release: LatestRelease | None = None
_cached_at = 0.0


def _fetch_release() -> LatestRelease | None:
    try:
        request = urllib.request.Request(
            RELEASE_URL,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "modular-checkin-platform",
            },
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            if response.status != 200:
                return None
            data = json.loads(response.read(2 * 1024 * 1024))
        tag = str(data.get("tag_name") or "").strip()
        if not tag:
            return None
        html_url = data.get("html_url")
        return LatestRelease(tag_name=tag, html_url=str(html_url) if html_url else None)
    except Exception as exc:
        status = getattr(exc, "code", None)
        logger.warning(
            "检查 GitHub 版本失败 url=%s status=%s error=%s: %s",
            RELEASE_URL, status, type(exc).__name__, exc,
        )
        return None


def _cached_release_sync() -> LatestRelease | None:
    global _cached_release, _cached_at
    with _lock:
        ttl = SUCCESS_TTL if _cached_release is not None else FAILURE_TTL
        if _cached_at and time.monotonic() - _cached_at < ttl:
            return _cached_release
        _cached_release = _fetch_release()
        _cached_at = time.monotonic()
        return _cached_release


async def get_latest_release() -> LatestRelease | None:
    return await asyncio.to_thread(_cached_release_sync)


def newer_version(latest: str, current: str) -> bool:
    def parse(value: str) -> tuple[int, int, int] | None:
        match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", str(value).strip())
        return tuple(int(part) for part in match.groups()) if match else None

    left, right = parse(latest), parse(current)
    return left is not None and right is not None and left > right
