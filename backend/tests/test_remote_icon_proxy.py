from __future__ import annotations

import asyncio
import ipaddress
import time

import pytest

from app.services import module_remote_icon as icon
from app.services.module_remote_icon import (
    RemoteIconError,
    _denied,
    _purge_negative,
    _sniff,
    get_remote_icon,
)


@pytest.mark.parametrize(
    "address,denied",
    [
        ("169.254.169.254", True),
        ("127.0.0.1", True),
        ("::1", True),
        ("fe80::1", True),
        ("0.0.0.0", True),
        ("::", True),
        ("10.0.0.1", False),
        ("192.168.1.1", False),
        ("8.8.8.8", False),
    ],
)
def test_denied_matrix(address: str, denied: bool) -> None:
    assert _denied(ipaddress.ip_address(address)) is denied


def test_sniff_and_alias() -> None:
    assert _sniff(b"\x89PNG\r\n\x1a\n" + b"x" * 8) == "image/png"
    assert _sniff(b"\xff\xd8\xff" + b"x" * 8) == "image/jpeg"
    assert _sniff(b"GIF89a" + b"x" * 8) == "image/gif"
    assert _sniff(b"RIFF0000WEBP" + b"x") == "image/webp"
    assert icon.CONTENT_TYPE_ALIASES["image/jpg"] == "image/jpeg"
    with pytest.raises(RemoteIconError):
        _sniff(b"<svg>")


@pytest.mark.asyncio
async def test_cache_key_includes_url(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    async def fake(url: str) -> tuple[bytes, str, str]:
        calls.append(url)
        return b"png", "image/png", url
    monkeypatch.setattr(icon, "_fetch", fake)
    icon._CACHE.clear()
    icon._NEGATIVE.clear()
    assert (await get_remote_icon(1, "https://a/icon.png"))[2] == "https://a/icon.png"
    assert (await get_remote_icon(1, "https://a/other.png"))[2] == "https://a/other.png"
    assert calls == ["https://a/icon.png", "https://a/other.png"]


@pytest.mark.asyncio
async def test_negative_cache_expiry_and_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0
    async def fail(_: str) -> tuple[bytes, str, str]:
        nonlocal calls
        calls += 1
        raise RemoteIconError()
    monkeypatch.setattr(icon, "_fetch", fail)
    icon._CACHE.clear(); icon._NEGATIVE.clear(); icon._INFLIGHT.clear()
    with pytest.raises(RemoteIconError):
        await get_remote_icon(2, "https://dead/icon.png")
    with pytest.raises(RemoteIconError):
        await get_remote_icon(2, "https://dead/icon.png")
    assert calls == 1
    key = (2, "https://dead/icon.png")
    icon._NEGATIVE[key] = time.monotonic() - 1
    with pytest.raises(RemoteIconError):
        await get_remote_icon(2, "https://dead/icon.png")
    assert calls == 2
    now = time.monotonic()
    icon._NEGATIVE.update({(i, f"u{i}"): now - 1 for i in range(300)})
    _purge_negative(now)
    assert len(icon._NEGATIVE) <= icon.NEGATIVE_MAX


@pytest.mark.asyncio
async def test_inflight_dedupe(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0
    gate = asyncio.Event()
    async def slow(url: str) -> tuple[bytes, str, str]:
        nonlocal calls
        calls += 1
        await gate.wait()
        return b"png", "image/png", url
    monkeypatch.setattr(icon, "_fetch", slow)
    icon._CACHE.clear(); icon._NEGATIVE.clear(); icon._INFLIGHT.clear()
    first = asyncio.create_task(get_remote_icon(3, "https://same/icon.png"))
    await asyncio.sleep(0)
    second = asyncio.create_task(get_remote_icon(3, "https://same/icon.png"))
    gate.set()
    await asyncio.gather(first, second)
    assert calls == 1


@pytest.mark.asyncio
async def test_https_resolved_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    async def resolved(host: str, port: int):
        return [ipaddress.ip_address("169.254.169.254")]
    monkeypatch.setattr(icon, "_resolve", resolved)
    with pytest.raises(RemoteIconError):
        await icon._validate_target("https://evil.example/icon.png")


@pytest.mark.asyncio
async def test_https_resolved_rfc1918_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    async def resolved(host: str, port: int):
        return [ipaddress.ip_address("10.0.0.1")]
    monkeypatch.setattr(icon, "_resolve", resolved)
    await icon._validate_target("https://internal.example/icon.png")
