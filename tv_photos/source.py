"""Enumerate eligible photos across multiple Apple Photos libraries via osxphotos."""
from __future__ import annotations

from pathlib import Path

from .models import Photo


def is_eligible(photo, min_width: int, exclude_screenshots: bool) -> bool:
    """Quality/usability filter for a single osxphotos PhotoInfo (duck-typed)."""
    if not getattr(photo, "isphoto", False):
        return False  # skip videos
    if not photo.path or getattr(photo, "ismissing", False):
        return False  # original not on disk (e.g. iCloud-optimized) — can't upload
    if (photo.width or 0) < min_width:
        return False
    if exclude_screenshots and getattr(photo, "screenshot", False):
        return False
    return True


def enumerate_photos(
    libraries: list[str],
    min_width: int = 1000,
    exclude_screenshots: bool = True,
    *,
    log=lambda msg: None,
) -> list[Photo]:
    """Pool eligible photos across all `libraries` into one candidate list."""
    import osxphotos  # heavy import; keep it lazy so unit tests stay fast

    pool: list[Photo] = []
    for lib in libraries:
        label = Path(lib).name
        log(f"scanning {label} ...")
        db = osxphotos.PhotosDB(lib)
        kept = 0
        for p in db.photos():
            if is_eligible(p, min_width, exclude_screenshots):
                pool.append(
                    Photo(
                        uuid=p.uuid,
                        path=p.path,
                        filename=p.original_filename or p.filename or f"{p.uuid}.jpg",
                        width=p.width or 0,
                        height=p.height or 0,
                        favorite=bool(p.favorite),
                        library=label,
                    )
                )
                kept += 1
        log(f"  {label}: {kept} eligible")
    return pool
