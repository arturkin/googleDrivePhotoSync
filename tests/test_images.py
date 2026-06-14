import hashlib
import io

from PIL import Image

from tv_photos.images import jpeg_filename, prepare_for_upload, sha256_file


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
