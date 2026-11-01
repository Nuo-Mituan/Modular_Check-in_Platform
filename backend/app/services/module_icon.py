"""Synchronous icon loading/decoding, executed in a worker thread."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image, UnidentifiedImageError
from .icon_policy import detect_icon_format, is_svg, SUFFIX_TO_FORMAT

MAX_ICON_BYTES = 64 * 1024
MAX_ICON_PIXELS = 1024 * 1024
# Path-based icons: declared suffix must match the detected file signature.
ICON_FORMAT_BY_SUFFIX = {
    f".{suffix}": fmt.upper() for suffix, fmt in SUFFIX_TO_FORMAT.items()
}


class ModuleIconError(Exception):
    def __init__(
        self, status_code: int, detail: str, code: str | None = None
    ) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
        self.code = code


class ModuleIconNotFound(ModuleIconError):
    def __init__(self) -> None:
        super().__init__(404, "图标不存在")


class ModuleIconTooLarge(ModuleIconError):
    def __init__(self) -> None:
        super().__init__(
            413, "图标文件过大", code="icon_size_default"
        )


class ModuleIconInvalid(ModuleIconError):
    def __init__(
        self,
        detail: str = "图标格式不合法",
        code: str | None = "icon_format_default",
    ) -> None:
        super().__init__(415, detail, code)


def _decode_pillow(data: bytes, fmt: str) -> bytes:
    try:
        with Image.open(BytesIO(data)) as image:
            if image.format != fmt:
                raise UnidentifiedImageError("format mismatch")
            if image.width <= 0 or image.height <= 0:
                raise ValueError("invalid dimensions")
            if image.width * image.height > MAX_ICON_PIXELS:
                raise ModuleIconTooLarge()
            rgba = image.convert("RGBA")
            if rgba.width * rgba.height > MAX_ICON_PIXELS:
                raise ModuleIconTooLarge()
            output = BytesIO()
            rgba.save(output, format="PNG", optimize=True)
            return output.getvalue()
    except ModuleIconError:
        raise
    except Image.DecompressionBombError as exc:
        raise ModuleIconTooLarge() from exc
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ModuleIconInvalid() from exc


def _detect_icon_format(data: bytes) -> str | None:
    """Identify the real format from magic bytes; never trust the suffix."""
    fmt = detect_icon_format(data)
    if fmt is None or is_svg(data):
        return None
    return {"ico": "ICO", "png": "PNG", "jpeg": "JPEG", "gif": "GIF", "webp": "WEBP"}[fmt]


def load_icon(candidate: Path) -> tuple[bytes, str, int]:
    """Return (bytes, media_type, mtime_ns); all filesystem work happens here."""
    declared = ICON_FORMAT_BY_SUFFIX.get(candidate.suffix.lower())
    if declared is None:
        if candidate.suffix.lower() == ".svg":
            raise ModuleIconInvalid(
                "SVG 图标已停止支持，请改用 PNG 格式", code=None
            )
        raise ModuleIconInvalid()
    try:
        stat = candidate.stat()
        with candidate.open("rb") as handle:
            data = handle.read(MAX_ICON_BYTES + 1)
    except ModuleIconError:
        raise
    except (OSError, ValueError) as exc:
        raise ModuleIconNotFound() from exc
    if len(data) > MAX_ICON_BYTES:
        raise ModuleIconTooLarge()

    actual = _detect_icon_format(data)
    if actual is None or actual != declared:
        raise ModuleIconInvalid()

    if actual == "ICO":
        if len(data) < 22:
            raise ModuleIconInvalid()
        count = int.from_bytes(data[4:6], "little")
        if count <= 0:
            raise ModuleIconInvalid()
        width = data[6] or 256
        height = data[7] or 256
        if not (0 < width <= 256 and 0 < height <= 256):
            raise ModuleIconInvalid()
    if actual in {"ICO", "PNG", "JPEG", "GIF", "WEBP"}:
        # Raster icons are normalized to PNG so the response MIME always
        # matches the actual bytes, including JPEG/WebP inputs.
        return _decode_pillow(data, actual), "image/png", stat.st_mtime_ns
    raise ModuleIconInvalid()
