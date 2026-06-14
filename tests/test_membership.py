import pytest

from tv_photos.membership import chunked, compute_diff


def test_diff_adds_and_removes():
    add, remove = compute_diff(current=["a", "b", "c"], target=["b", "c", "d"])
    assert add == ["d"]
    assert remove == ["a"]


def test_diff_no_change():
    add, remove = compute_diff(current=["a", "b"], target=["b", "a"])
    assert add == []
    assert remove == []


def test_diff_first_run_adds_all():
    add, remove = compute_diff(current=[], target=["a", "b"])
    assert add == ["a", "b"]
    assert remove == []


def test_diff_empty_target_removes_all():
    add, remove = compute_diff(current=["a", "b"], target=[])
    assert add == []
    assert remove == ["a", "b"]


def test_diff_ignores_duplicates():
    add, remove = compute_diff(current=["a", "a"], target=["a", "b", "b"])
    assert add == ["b"]
    assert remove == []


def test_chunked_splits_with_remainder():
    assert chunked(list(range(7)), 3) == [[0, 1, 2], [3, 4, 5], [6]]


def test_chunked_exact_multiple():
    assert chunked(list(range(6)), 3) == [[0, 1, 2], [3, 4, 5]]


def test_chunked_default_size_is_50():
    chunks = chunked(list(range(120)))
    assert [len(c) for c in chunks] == [50, 50, 20]


def test_chunked_empty():
    assert chunked([], 50) == []


def test_chunked_size_larger_than_seq():
    assert chunked([1, 2], 50) == [[1, 2]]


def test_chunked_rejects_nonpositive_size():
    with pytest.raises(ValueError):
        chunked([1, 2, 3], 0)
