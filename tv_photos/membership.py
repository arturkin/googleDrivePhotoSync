"""Album membership diff + batch chunking for the Google Photos API (<=50/call)."""
from __future__ import annotations

from typing import Sequence, TypeVar

T = TypeVar("T")

API_BATCH_LIMIT = 50


def compute_diff(current: Sequence[str], target: Sequence[str]) -> tuple[list[str], list[str]]:
    """Return (to_add, to_remove) to turn the album's `current` members into `target`.

    Order-independent and duplicate-safe; results are sorted for deterministic batching.
    """
    cur, tgt = set(current), set(target)
    return sorted(tgt - cur), sorted(cur - tgt)


def chunked(seq: Sequence[T], size: int = API_BATCH_LIMIT) -> list[list[T]]:
    """Split `seq` into lists of at most `size` items."""
    if size <= 0:
        raise ValueError("size must be positive")
    items = list(seq)
    return [items[i : i + size] for i in range(0, len(items), size)]
