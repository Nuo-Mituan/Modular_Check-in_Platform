"""Single backend policy for module icon formats.

Frontend mirror: frontend/src/constants/moduleIcon.js.
SVG is deliberately unsupported in every path.
"""
from __future__ import annotations

import base64
import binascii

ICON_ALLOWED = frozenset({"ico", "png", "jpeg", "gif", "webp"})
SUFFIX_TO_FORMAT = {
    "ico": "ico", "png": "png", "jpg": "jpeg", "jpeg": "jpeg",
    "gif": "gif", "webp": "webp",
}
FORMAT_TO_CONTENT_TYPE = {
    "ico": "image/x-icon", "png": "image/png", "jpeg": "image/jpeg",
    "gif": "image/gif", "webp": "image/webp",
}
CONTENT_TYPE_TO_FORMAT = {
    "image/x-icon": "ico", "image/vnd.microsoft.icon": "ico",
    "image/png": "png", "image/jpeg": "jpeg", "image/jpg": "jpeg",
    "image/gif": "gif", "image/webp": "webp",
}
ALLOWED_CONTENT_TYPES = frozenset(CONTENT_TYPE_TO_FORMAT)
ICON_UNSUPPORTED_DETAIL = "图标仅支持 PNG/JPEG/GIF/WebP/ICO，不支持 SVG"


class IconPolicyError(ValueError):
    pass


def detect_icon_format(data: bytes) -> str | None:
    """Return ico/png/jpeg/gif/webp from magic bytes, or None."""
    if len(data) >= 6 and data[:2] == b"\x00\x00":
        icon_type = int.from_bytes(data[2:4], "little")
        return "ico" if icon_type == 1 else None  # .cur (type=2) rejected
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def is_svg(data: bytes) -> bool:
    # The substring check covers BOM/XML prolog variants (e.g. \xef\xbb\xbf<svg>);
    # do not remove it as a redundant optimization.
    head = data.lstrip()[:512].lower()
    return b"<svg" in head and (head.startswith(b"<?xml") or head.startswith(b"<svg"))


def validate_data_uri(value: str, *, max_bytes: int = 256 * 1024) -> str:
    try:
        header, encoded = value.split(",", 1)
        mime = header[5:].split(";", 1)[0].lower()
        if not header.startswith("data:") or ";base64" not in header:
            raise IconPolicyError(ICON_UNSUPPORTED_DETAIL)
        if mime == "image/svg+xml":
            raise IconPolicyError(ICON_UNSUPPORTED_DETAIL)
        expected = CONTENT_TYPE_TO_FORMAT.get(mime)
        if expected is None:
            raise IconPolicyError(ICON_UNSUPPORTED_DETAIL)
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error, KeyError) as exc:
        raise IconPolicyError("图标不是合法的 Base64 图片 Data URI") from exc
    if len(raw) > max_bytes:
        raise IconPolicyError("Base64 图标不能超过 256KB")
    actual = detect_icon_format(raw)
    if actual is None or actual != expected or is_svg(raw):
        raise IconPolicyError(ICON_UNSUPPORTED_DETAIL)
    return actual


def validate_file_extension_format(suffix: str, data: bytes) -> str:
    declared = SUFFIX_TO_FORMAT.get(suffix.lstrip(".").lower())
    if declared is None:
        raise IconPolicyError(ICON_UNSUPPORTED_DETAIL)
    actual = detect_icon_format(data)
    if actual is None or actual != declared or is_svg(data):
        raise IconPolicyError(ICON_UNSUPPORTED_DETAIL)
    return actual
