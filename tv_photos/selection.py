"""Pick the rotation set: favorites first, then random fill from the rest."""
from __future__ import annotations

import random

from .models import Photo


def select_rotation(candidates: list[Photo], n: int, rng: random.Random) -> list[Photo]:
    """Choose up to ``n`` photos for the album.

    Favorites are preferred: include all of them, and if that already exceeds ``n``
    randomly sample ``n`` favorites. Otherwise fill the remaining slots with a random
    sample of the non-favorites. Returns the whole pool when it is smaller than ``n``.
    """
    if n <= 0 or not candidates:
        return []
    favorites = [c for c in candidates if c.favorite]
    others = [c for c in candidates if not c.favorite]
    if len(favorites) >= n:
        return rng.sample(favorites, n)
    fill = rng.sample(others, min(n - len(favorites), len(others)))
    return favorites + fill


def select_preview(candidates: list[Photo], n: int, rng: random.Random) -> list[Photo]:
    """Pick up to ``n`` photos that actually have a location label, for a preview.

    Previewing is about seeing the burned-in place text, so photos with no
    location are useless here and excluded.
    """
    located = [c for c in candidates if c.place]
    return rng.sample(located, min(n, len(located)))
