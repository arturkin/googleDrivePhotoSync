from types import SimpleNamespace

from tv_photos.source import is_eligible


def photo(**kw):
    base = dict(isphoto=True, width=4000, height=3000, path="/x.jpg", ismissing=False, screenshot=False)
    base.update(kw)
    return SimpleNamespace(**base)


def test_normal_wide_photo_is_eligible():
    assert is_eligible(photo(), min_width=1000, exclude_screenshots=True) is True


def test_video_excluded():
    assert is_eligible(photo(isphoto=False), 1000, True) is False


def test_too_narrow_excluded():
    assert is_eligible(photo(width=800), 1000, True) is False


def test_missing_path_excluded():
    assert is_eligible(photo(path=None), 1000, True) is False


def test_missing_local_copy_excluded():
    assert is_eligible(photo(ismissing=True), 1000, True) is False


def test_screenshot_excluded_when_flag_set():
    assert is_eligible(photo(screenshot=True), 1000, True) is False


def test_screenshot_kept_when_flag_off():
    assert is_eligible(photo(screenshot=True), 1000, False) is True


def test_none_width_excluded():
    assert is_eligible(photo(width=None), 1000, True) is False
