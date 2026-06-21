import hashlib
import io

from PIL import Image

from tv_photos.images import (
    draw_location_label,
    jpeg_filename,
    prepare_for_upload,
    sha256_file,
)


def _mean_luma(im, box):
    """Average brightness of a crop, for asserting where ink landed."""
    crop = im.convert("L").crop(box)
    hist = crop.histogram()
    total = sum(i * count for i, count in enumerate(hist))
    return total / (crop.width * crop.height)


def test_jpeg_filename_normalizes_extension():
    assert jpeg_filename("IMG_1234.HEIC") == "IMG_1234.jpg"
    assert jpeg_filename("a.jpeg") == "a.jpg"
    assert jpeg_filename("photo") == "photo.jpg"
    assert jpeg_filename("My.Vacation.PNG") == "My.Vacation.jpg"


def test_sha256_matches_hashlib(tmp_path):
    p = tmp_path / "f.bin"
    p.write_bytes(b"hello world")
    assert sha256_file(p) == hashlib.sha256(b"hello world").hexdigest()


def test_downscales_to_max_long_edge(tmp_path):
    src = tmp_path / "big.png"
    Image.new("RGB", (5000, 2500), (120, 30, 200)).save(src)
    data = prepare_for_upload(src, max_long_edge=3840, jpeg_quality=85)
    out = Image.open(io.BytesIO(data))
    assert out.format == "JPEG"
    assert max(out.size) == 3840
    assert out.size == (3840, 1920)


def test_does_not_upscale_small_image(tmp_path):
    src = tmp_path / "small.png"
    Image.new("RGB", (800, 600), (10, 10, 10)).save(src)
    data = prepare_for_upload(src, max_long_edge=3840, jpeg_quality=85)
    out = Image.open(io.BytesIO(data))
    assert out.size == (800, 600)
    assert out.format == "JPEG"


def test_flattens_rgba_to_rgb(tmp_path):
    src = tmp_path / "a.png"
    Image.new("RGBA", (400, 400), (10, 20, 30, 128)).save(src)
    data = prepare_for_upload(src, max_long_edge=3840, jpeg_quality=85)
    out = Image.open(io.BytesIO(data))
    assert out.mode == "RGB"


def test_draw_location_label_writes_bottom_center():
    base = Image.new("RGB", (1600, 900), (0, 0, 0))
    out = draw_location_label(base, "Reykjavík, Iceland")
    assert out.size == base.size
    assert out.mode == "RGB"
    # ink sits in the bottom-center band; the top is untouched
    assert _mean_luma(out, (500, 740, 1100, 880)) > 1
    assert _mean_luma(out, (0, 0, 1600, 200)) < 0.01
    # bottom padding keeps text clear of the very edge (so the TV can't clip it)
    assert _mean_luma(out, (0, 895, 1600, 900)) < 0.01


def test_draw_location_label_is_horizontally_centered():
    base = Image.new("RGB", (1600, 900), (0, 0, 0))
    out = draw_location_label(base, "Reykjavík, Iceland")
    center = _mean_luma(out, (600, 740, 1000, 900))
    left = _mean_luma(out, (0, 740, 300, 900))
    right = _mean_luma(out, (1300, 740, 1600, 900))
    assert center > left and center > right


def test_draw_location_label_does_not_mutate_input():
    base = Image.new("RGB", (800, 600), (0, 0, 0))
    draw_location_label(base, "Somewhere")
    assert _mean_luma(base, (0, 400, 400, 600)) < 1  # original unchanged


def test_height_ratio_scales_text_size():
    base = Image.new("RGB", (1600, 900), (0, 0, 0))
    small = draw_location_label(base, "Reykjavík, Iceland", height_ratio=0.018)
    big = draw_location_label(base, "Reykjavík, Iceland", height_ratio=0.040)
    # bigger ratio => more ink in the bottom band
    assert _mean_luma(big, (0, 600, 1600, 900)) > _mean_luma(small, (0, 600, 1600, 900))


def test_prepare_with_label_differs_from_without(tmp_path):
    src = tmp_path / "p.png"
    Image.new("RGB", (2000, 1200), (40, 60, 90)).save(src)
    plain = prepare_for_upload(src, max_long_edge=3840, jpeg_quality=85)
    labeled = prepare_for_upload(src, max_long_edge=3840, jpeg_quality=85, label="Vík, Iceland")
    assert labeled != plain
    out = Image.open(io.BytesIO(labeled))
    assert out.format == "JPEG"
    assert out.size == (2000, 1200)


def test_prepare_label_none_is_unchanged(tmp_path):
    src = tmp_path / "p.png"
    Image.new("RGB", (1000, 800), (5, 5, 5)).save(src)
    assert prepare_for_upload(src, 3840, 85, label=None) == prepare_for_upload(src, 3840, 85)
