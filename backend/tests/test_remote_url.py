from __future__ import annotations

import pytest

from app.config import settings
from app.services.remote_url import (
    REMOTE_HTTP_ERROR,
    RemoteUrlError,
    is_insecure_host_allowed,
    normalize_remote_url,
)


def test_public_http_rejected() -> None:
    with pytest.raises(RemoteUrlError, match="http://"):
        normalize_remote_url("http://example.com/icon.png")


def test_https_allowed_and_unchanged() -> None:
    assert normalize_remote_url("https://example.com/icon.png") == "https://example.com/icon.png"


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:8080/icon.png",
        "http://127.0.0.1/icon.png",
        "http://10.1.2.3/icon.png",
        "http://172.16.0.1/icon.png",
        "http://192.168.1.1/icon.png",
        "http://[::1]/icon.png",
        "http://[fd00::1]/icon.png",
    ],
)
def test_private_http_allowed(url: str) -> None:
    assert normalize_remote_url(url) == url


@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.1.1/icon.png",
        "http://[fe80::1]/icon.png",
        "http://0.0.0.0/icon.png",
        "http://[::]/icon.png",
        "http://[::ffff:10.0.0.1]/icon.png",
        "http://[::ffff:8.8.8.8]/icon.png",
        "http://localhost./icon.png",
        "http://[fe80::1%25eth0]/icon.png",
    ],
)
def test_unsafe_or_mapped_http_rejected(url: str) -> None:
    with pytest.raises(RemoteUrlError):
        normalize_remote_url(url)


def test_allowlist_hit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "remote_http_allow_hosts", "example.test")
    assert normalize_remote_url("http://example.test/icon.png") == "http://example.test/icon.png"


def test_allowlist_does_not_resolve_public_hostname(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "remote_http_allow_hosts", "")
    with pytest.raises(RemoteUrlError):
        normalize_remote_url("http://pretend-local.test/icon.png")


def test_userinfo_is_rejected_but_fragment_is_not_userinfo() -> None:
    with pytest.raises(RemoteUrlError, match="用户名或密码"):
        normalize_remote_url("http://evil.com@127.0.0.1/")
    assert normalize_remote_url("http://127.0.0.1#@evil.com/") == "http://127.0.0.1#@evil.com/"


def test_https_is_never_rewritten() -> None:
    source = "http://example.com/icon.png"
    with pytest.raises(RemoteUrlError) as exc:
        normalize_remote_url(source)
    assert str(exc.value) == REMOTE_HTTP_ERROR
    assert source == "http://example.com/icon.png"


def test_legacy_module_config_warns_but_does_not_block() -> None:
    from app.module_loader import ModuleConfig

    config = ModuleConfig(name="legacy", icon="http://example.com/icon.png")
    assert config.icon == "http://example.com/icon.png"
