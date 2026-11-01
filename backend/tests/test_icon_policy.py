from __future__ import annotations

import pytest

from app.services.icon_policy import (
    ICON_ALLOWED,
    IconPolicyError,
    detect_icon_format,
    validate_data_uri,
    validate_file_extension_format,
)


def test_gif_and_allowed_set() -> None:
    assert "gif" in ICON_ALLOWED
    assert detect_icon_format(b"GIF89a" + b"x" * 16) == "gif"


def test_svg_and_cur_rejected() -> None:
    assert detect_icon_format(b"<svg xmlns='http://www.w3.org/2000/svg'/>") is None
    assert detect_icon_format(b"\x00\x00\x02\x00" + b"x" * 16) is None
    with pytest.raises(IconPolicyError):
        validate_file_extension_format(".png", b"<svg xmlns='http://www.w3.org/2000/svg'/>")


def test_extension_magic_mismatch() -> None:
    with pytest.raises(IconPolicyError):
        validate_file_extension_format(".png", b"\xff\xd8\xff\xe0" + b"x" * 16)


def test_data_uri_alias_and_mismatch() -> None:
    assert validate_data_uri("data:image/gif;base64,R0lGODlh") == "gif"
    with pytest.raises(IconPolicyError):
        validate_data_uri("data:image/png;base64,/9j/4AAQ")
