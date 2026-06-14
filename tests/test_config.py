import pytest

from tv_photos.config import Config, load_config, render_config_template


def write(tmp_path, text):
    p = tmp_path / "config.toml"
    p.write_text(text)
    return p


def test_load_minimal_applies_defaults(tmp_path):
    p = write(tmp_path, '[source]\nlibraries = ["/a.photoslibrary"]\n')
    cfg = load_config(p)
    assert cfg.libraries == ["/a.photoslibrary"]
    assert cfg.count == 1000
    assert cfg.min_width == 1000
    assert cfg.upload_max_long_edge == 3840
    assert cfg.jpeg_quality == 85
    assert cfg.album_title == "TV Rotation"
    assert cfg.exclude_screenshots is True
    assert cfg.dry_run is False


def test_load_overrides(tmp_path):
    p = write(
        tmp_path,
        """
[source]
libraries = ["/a.photoslibrary", "/b.photoslibrary"]
exclude_screenshots = false

[quality]
min_width = 1600
upload_max_long_edge = 2560
jpeg_quality = 90

[rotation]
album_title = "Living Room"
count = 250

[behavior]
dry_run = true
""",
    )
    cfg = load_config(p)
    assert cfg.libraries == ["/a.photoslibrary", "/b.photoslibrary"]
    assert cfg.exclude_screenshots is False
    assert cfg.min_width == 1600
    assert cfg.upload_max_long_edge == 2560
    assert cfg.jpeg_quality == 90
    assert cfg.album_title == "Living Room"
    assert cfg.count == 250
    assert cfg.dry_run is True


def test_missing_libraries_raises(tmp_path):
    p = write(tmp_path, "[rotation]\ncount = 10\n")
    with pytest.raises(ValueError, match="librar"):
        load_config(p)


def test_empty_libraries_raises(tmp_path):
    p = write(tmp_path, "[source]\nlibraries = []\n")
    with pytest.raises(ValueError, match="librar"):
        load_config(p)


def test_count_must_be_positive(tmp_path):
    p = write(tmp_path, '[source]\nlibraries = ["/a"]\n[rotation]\ncount = 0\n')
    with pytest.raises(ValueError, match="count"):
        load_config(p)


def test_jpeg_quality_out_of_range(tmp_path):
    p = write(tmp_path, '[source]\nlibraries = ["/a"]\n[quality]\njpeg_quality = 0\n')
    with pytest.raises(ValueError, match="jpeg_quality"):
        load_config(p)


def test_template_roundtrips(tmp_path):
    text = render_config_template(["/x.photoslibrary", "/y.photoslibrary"])
    p = write(tmp_path, text)
    cfg = load_config(p)
    assert isinstance(cfg, Config)
    assert cfg.libraries == ["/x.photoslibrary", "/y.photoslibrary"]
    assert cfg.count == 1000


def test_template_escapes_special_chars(tmp_path):
    weird = ['/Volumes/My "Photos".photoslibrary', "/Volumes/back\\slash.photoslibrary"]
    text = render_config_template(weird)
    p = write(tmp_path, text)
    cfg = load_config(p)
    assert cfg.libraries == weird
