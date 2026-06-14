"""Shared data types for the pipeline."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Photo:
    """A candidate photo enumerated from an Apple Photos library.

    `path` points at the on-disk original; selection only needs `favorite` and an
    identity. The content hash used for upload dedup is computed later, only for the
    photos actually selected (so we never hash the whole pool).
    """

    uuid: str
    path: str
    filename: str
    width: int
    height: int
    favorite: bool
    library: str = ""
