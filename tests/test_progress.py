from tv_photos.progress import fmt_duration, format_progress


def test_fmt_duration():
    assert fmt_duration(0) == "0:00"
    assert fmt_duration(9) == "0:09"
    assert fmt_duration(70) == "1:10"
    assert fmt_duration(3661) == "1:01:01"


def test_progress_midway():
    s = format_progress(50, 100, 10.0)
    assert "50%" in s
    assert "50/100" in s
    assert "ETA 0:10" in s  # 10s for first 50 -> 10s for remaining 50


def test_progress_start():
    s = format_progress(0, 100, 0.0)
    assert "0%" in s
    assert "0/100" in s


def test_progress_complete():
    s = format_progress(100, 100, 20.0)
    assert "100%" in s
    assert "100/100" in s


def test_progress_zero_total_does_not_crash():
    s = format_progress(0, 0, 0.0)
    assert "0/0" in s


def test_bar_has_fixed_width():
    s = format_progress(25, 100, 5.0, width=20)
    bar = s[s.index("[") + 1 : s.index("]")]
    assert len(bar) == 20
    assert bar.count("█") == 5  # 25% of 20
