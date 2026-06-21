"""Image prep for upload: EXIF-orient, downscale, HEIC->JPEG, and content hashing."""
from __future__ import annotations

import hashlib
import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

# Register the HEIF/HEIC opener so Image.open() handles iPhone .heic files.
try:
    import pillow_heif

    pillow_heif.register_heif_opener()
except Exception:  # pragma: no cover - HEIC just won't decode without it
    pass

_HASH_CHUNK = 1 << 20

# First system font that loads wins; falls back to PIL's bundled bitmap font.
_FONT_CANDIDATES = (
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/HelveticaNeue.ttc",
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
)


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()  # pragma: no cover - only if no system font exists


def draw_location_label(
    im: Image.Image,
    text: str,
    *,
    height_ratio: float = 0.016,
    margin_ratio: float = 0.04,
) -> Image.Image:
    """Return a copy of ``im`` with ``text`` burned into the bottom-left corner.

    White text on a soft drop shadow so it stays legible over any photo — placed
    near where Google TV Ambient mode renders the album name. Size and margins
    scale with the image (via ``height_ratio`` / ``margin_ratio``) so it looks
    consistent across 4K landscape and phone portrait shots. Never mutates the input.
    """
    base = im.convert("RGBA")
    w, h = base.size
    font = _load_font(max(14, round(h * height_ratio)))
    margin = round(min(w, h) * margin_ratio)

    draw = ImageDraw.Draw(base)
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    x = margin - left
    y = h - margin - (bottom - top) - top

    # Soft drop shadow on its own layer, blurred, then composited under the text.
    shadow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).text((x, y), text, font=font, fill=(0, 0, 0, 200))
    base = Image.alpha_composite(base, shadow.filter(ImageFilter.GaussianBlur(max(2, round(h * 0.004)))))

    ImageDraw.Draw(base).text((x, y), text, font=font, fill=(255, 255, 255, 240))
    return base.convert("RGB")


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


def prepare_for_upload(
    path: str | Path,
    max_long_edge: int,
    jpeg_quality: int,
    label: str | None = None,
) -> bytes:
    """Return JPEG bytes: EXIF-oriented, flattened to RGB, downscaled (never upscaled).

    If ``label`` is given (a non-empty place name), it is burned into the bottom-left
    corner after downscaling, so the text size is relative to the uploaded image.
    """
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
        if label:
            im = draw_location_label(im, label)
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=jpeg_quality)
        return buf.getvalue()
