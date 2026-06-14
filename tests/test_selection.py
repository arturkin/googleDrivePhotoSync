import random

from tv_photos.models import Photo
from tv_photos.selection import select_rotation


def make_photos(n, *, favorite=False, start=0):
    return [
        Photo(
            uuid=f"u{i}",
            path=f"/lib/{i}.jpg",
            filename=f"{i}.jpg",
            width=4000,
            height=3000,
            favorite=favorite,
        )
        for i in range(start, start + n)
    ]


def rng():
    return random.Random(42)


def test_returns_all_when_pool_smaller_than_n():
    pool = make_photos(3)
    result = select_rotation(pool, 10, rng())
    assert set(result) == set(pool)


def test_returns_exactly_n_when_pool_larger():
    pool = make_photos(50)
    result = select_rotation(pool, 10, rng())
    assert len(result) == 10


def test_n_zero_returns_empty():
    assert select_rotation(make_photos(5), 0, rng()) == []


def test_empty_pool_returns_empty():
    assert select_rotation([], 10, rng()) == []


def test_prefers_favorites_then_fills_with_others():
    favs = make_photos(3, favorite=True, start=0)
    others = make_photos(10, favorite=False, start=100)
    result = select_rotation(favs + others, 5, rng())
    assert len(result) == 5
    # all favorites are included
    assert set(favs).issubset(set(result))
    # remainder drawn from others
    assert len([p for p in result if not p.favorite]) == 2


def test_samples_favorites_when_favorites_exceed_n():
    favs = make_photos(8, favorite=True, start=0)
    others = make_photos(5, favorite=False, start=100)
    result = select_rotation(favs + others, 5, rng())
    assert len(result) == 5
    # when there are more favorites than slots, only favorites are used
    assert all(p.favorite for p in result)


def test_includes_all_favorites_and_all_others_when_total_below_n():
    favs = make_photos(2, favorite=True, start=0)
    others = make_photos(3, favorite=False, start=100)
    result = select_rotation(favs + others, 10, rng())
    assert set(result) == set(favs + others)


def test_no_duplicates():
    pool = make_photos(5, favorite=True) + make_photos(20, favorite=False, start=100)
    result = select_rotation(pool, 15, rng())
    assert len(result) == len(set(result))


def test_deterministic_with_seeded_rng():
    pool = make_photos(5, favorite=True) + make_photos(50, favorite=False, start=100)
    a = select_rotation(pool, 20, random.Random(7))
    b = select_rotation(pool, 20, random.Random(7))
    assert a == b
