"""Image prep for upload: EXIF-orient, downscale, HEIC->JPEG, and content hashing."""
from __future__ import annotations

import hashlib
import io
from pathlib import Path

from PIL import Image, ImageOps

# Register the HEIF/HEIC opener so Image.open() handles iPhone .heic files.
try:
    import pillow_heif

    pillow_heif.register_heif_opener()
except Exception:  # pragma: no cover - HEIC just won't decode without it
    pass

_HASH_CHUNK = 1 << 20


def jpeg_filename(name: str) -> str:
    """Normalize an upload filename to .jpg (we always upload JPEG bytes)."""
    return Path(name).with_suffix(".jpg").name


def sha256_file(path: str | Path) -> str:
    """SHA-256 of the original file bytes (the upload-dedup key)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(_HASH_CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def prepare_for_upload(path: str | Path, max_long_edge: int, jpeg_quality: int) -> bytes:
    """Return JPEG bytes: EXIF-oriented, flattened to RGB, downscaled (never upscaled)."""
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im)  # bake in rotation so TV shows it upright
        if im.mode != "RGB":
            im = im.convert("RGB")
        long_edge = max(im.size)
        if long_edge > max_long_edge:
            scale = max_long_edge / long_edge
            im = im.resize(
                (round(im.width * scale), round(im.height * scale)),
                Image.LANCZOS,
            )
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=jpeg_quality)
        return buf.getvalue()
