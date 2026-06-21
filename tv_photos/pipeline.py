"""Core rotation pipeline: select -> dedup-plan -> upload -> reshuffle album membership."""
from __future__ import annotations

import random
from dataclasses import dataclass

from .images import jpeg_filename, prepare_for_upload, sha256_file
from .membership import compute_diff
from .models import Photo
from .selection import select_rotation


@dataclass
class UploadPlan:
    known: dict[str, str]                # sha256 -> media_item_id (already uploaded)
    to_upload: list[tuple[str, Photo]]   # (sha256, representative photo) for unique new content


@dataclass
class RunReport:
    pool: int
    selected: int
    reused: int
    uploaded: int
    upload_failed: int
    added: int
    removed: int
    album_size: int
    dry_run: bool


def build_upload_plan(selected: list[Photo], state, hasher) -> UploadPlan:
    """Split the selection into already-uploaded (by content hash) vs. needs-upload.

    Identical content (same hash) collapses to a single upload.
    """
    known: dict[str, str] = {}
    to_upload: list[tuple[str, Photo]] = []
    seen: set[str] = set()
    for photo in selected:
        sha = hasher(photo.path)
        if sha in seen:
            continue
        seen.add(sha)
        mid = state.get_media_item_id(sha)
        if mid:
            known[sha] = mid
        else:
            to_upload.append((sha, photo))
    return UploadPlan(known=known, to_upload=to_upload)


def reshuffle_existing(
    *,
    client,
    state,
    count: int,
    album_id: str,
    rng: random.Random,
    log=lambda msg: None,
) -> RunReport:
    """Reshuffle the album from ALREADY-uploaded photos — no library scan, no uploads.

    Fast/free rotation (and the recovery path when uploads succeeded but the album
    membership update didn't).
    """
    pool = state.all_media_item_ids()
    target = rng.sample(pool, min(count, len(pool)))
    current = state.get_album_members()
    to_add, to_remove = compute_diff(current, target)
    if to_add:
        client.album_add(album_id, to_add)
    if to_remove:
        client.album_remove(album_id, to_remove)
    state.set_album_members(target)
    log(f"reshuffle: album +{len(to_add)} -{len(to_remove)} -> {len(target)} "
        f"(from {len(pool)} already uploaded; no new uploads)")
    return RunReport(
        pool=len(pool), selected=len(target), reused=len(target), uploaded=0,
        upload_failed=0, added=len(to_add), removed=len(to_remove),
        album_size=len(target), dry_run=False,
    )


def run_rotation(
    *,
    client,
    state,
    candidates: list[Photo],
    count: int,
    album_id: str,
    max_long_edge: int,
    jpeg_quality: int,
    rng: random.Random,
    dry_run: bool = False,
    overlay_location: bool = False,
    log=lambda msg: None,
    hasher=sha256_file,
    prepare=prepare_for_upload,
    progress=None,
) -> RunReport:
    """Select the rotation, upload only new content, and set album membership to it."""
    selected = select_rotation(candidates, count, rng)
    log(f"pool={len(candidates)} selected={len(selected)} (favorites first, then random fill)")

    plan = build_upload_plan(selected, state, hasher)
    log(f"already uploaded: {len(plan.known)} | new to upload: {len(plan.to_upload)}")

    if dry_run:
        current = state.get_album_members()
        target_n = len(plan.known) + len(plan.to_upload)
        log(f"[dry-run] would upload {len(plan.to_upload)} new photos")
        log(f"[dry-run] album has {len(current)} now; target ~{target_n} photos")
        return RunReport(
            pool=len(candidates), selected=len(selected), reused=len(plan.known),
            uploaded=0, upload_failed=0, added=0, removed=0,
            album_size=len(current), dry_run=True,
        )

    # 1. upload bytes for new unique content
    failed = 0
    items: list[tuple[str, str, str]] = []  # (sha, upload_token, filename)
    for i, (sha, photo) in enumerate(plan.to_upload, 1):
        try:
            label = photo.place if overlay_location else None
            data = prepare(photo.path, max_long_edge, jpeg_quality, label)
            name = jpeg_filename(photo.filename)  # always JPEG bytes -> .jpg name
            token = client.upload_bytes(data, "image/jpeg", name)
            items.append((sha, token, name))
        except Exception as e:  # noqa: BLE001 - keep going; report at end
            failed += 1
            log(f"  upload failed: {photo.filename}: {e}")
        if progress:
            progress(i, len(plan.to_upload))
        elif i % 50 == 0:
            log(f"  uploaded {i}/{len(plan.to_upload)} ...")

    # 2. create media items (chunked, tolerates 207); persist only successes
    new_map: dict[str, str] = {}
    created = client.batch_create([(tok, name) for _, tok, name in items])
    if len(created) != len(items):
        # The API must return one result per requested item, in order. If it doesn't,
        # zip-by-position would mis-map sha -> media_item_id and corrupt dedup state.
        # Refuse to persist this run rather than poison future runs.
        log(f"  WARNING: batchCreate returned {len(created)} results for {len(items)} "
            f"uploads; skipping persistence to avoid mis-mapping")
        failed += len(items)
    else:
        for (sha, _, _), result in zip(items, created):
            if result.ok and result.media_item_id:
                state.record_upload(sha, result.media_item_id, result.filename)
                new_map[sha] = result.media_item_id
            else:
                failed += 1
                log(f"  create failed: {result.filename}: {result.message}")

    # 3. set album membership to exactly the target set
    target_ids = list(plan.known.values()) + list(new_map.values())
    current = state.get_album_members()
    to_add, to_remove = compute_diff(current, target_ids)
    if to_add:
        client.album_add(album_id, to_add)
    if to_remove:
        client.album_remove(album_id, to_remove)
    state.set_album_members(target_ids)
    log(f"album: +{len(to_add)} -{len(to_remove)} = {len(target_ids)} photos")

    return RunReport(
        pool=len(candidates), selected=len(selected), reused=len(plan.known),
        uploaded=len(new_map), upload_failed=failed, added=len(to_add),
        removed=len(to_remove), album_size=len(target_ids), dry_run=False,
    )
