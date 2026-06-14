"""Google Photos Library API REST client (post-April-2025 method/scope set).

Pure helpers (`parse_batch_create_result`, `should_retry`, `backoff_seconds`) are unit
tested; the thin HTTP methods are exercised by the end-to-end run (and were proven by the
validation spike).
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass

import requests

from .membership import chunked

API = "https://photoslibrary.googleapis.com/v1"

# Scopes the full tool needs.
SCOPES = [
    "https://www.googleapis.com/auth/photoslibrary.appendonly",          # upload, create, add
    "https://www.googleapis.com/auth/photoslibrary.edit.appcreateddata",  # remove from album
    "https://www.googleapis.com/auth/photoslibrary.readonly.appcreateddata",  # read album state
]

_RETRY_CODES = {429, 500, 502, 503, 504}


@dataclass
class CreatedItem:
    filename: str
    media_item_id: str | None
    ok: bool
    message: str


def parse_batch_create_result(resp: dict) -> list[CreatedItem]:
    """Parse a mediaItems:batchCreate response (200 or 207) into per-item results."""
    out: list[CreatedItem] = []
    for r in resp.get("newMediaItemResults", []):
        status = r.get("status") or {}
        code = status.get("code", 0) or 0
        mi = r.get("mediaItem") or {}
        out.append(
            CreatedItem(
                filename=mi.get("filename", ""),
                media_item_id=mi.get("id"),
                ok=code == 0 and bool(mi.get("id")),
                message=status.get("message", ""),
            )
        )
    return out


def should_retry(status_code: int) -> bool:
    return status_code in _RETRY_CODES


def backoff_seconds(attempt: int, rng: random.Random, *, base: float = 1.0, cap: float = 32.0) -> float:
    """Exponential backoff with full jitter, capped."""
    return min(cap, base * (2**attempt)) + rng.random()


class GooglePhotosClient:
    def __init__(self, session, *, max_retries: int = 5):
        self.session = session
        self.max_retries = max_retries
        self._rng = random.Random()

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        kwargs.setdefault("timeout", 120)
        last_exc = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = self.session.request(method, url, **kwargs)
            except requests.RequestException as e:
                last_exc = e
                if attempt == self.max_retries:
                    raise
                time.sleep(backoff_seconds(attempt, self._rng))
                continue
            if resp.status_code < 400 or not should_retry(resp.status_code) or attempt == self.max_retries:
                return resp
            time.sleep(backoff_seconds(attempt, self._rng))
        if last_exc:  # pragma: no cover
            raise last_exc
        return resp

    # --- albums ----------------------------------------------------------
    def create_album(self, title: str) -> str:
        r = self._request("POST", f"{API}/albums", json={"album": {"title": title}})
        r.raise_for_status()
        return r.json()["id"]

    def album_add(self, album_id: str, media_item_ids) -> None:
        for chunk in chunked(list(media_item_ids)):
            r = self._request(
                "POST",
                f"{API}/albums/{album_id}:batchAddMediaItems",
                json={"mediaItemIds": chunk},
            )
            r.raise_for_status()

    def album_remove(self, album_id: str, media_item_ids) -> None:
        for chunk in chunked(list(media_item_ids)):
            r = self._request(
                "POST",
                f"{API}/albums/{album_id}:batchRemoveMediaItems",
                json={"mediaItemIds": chunk},
            )
            r.raise_for_status()

    def search_album_media_ids(self, album_id: str) -> list[str]:
        ids: list[str] = []
        page = None
        while True:
            body = {"albumId": album_id, "pageSize": 100}
            if page:
                body["pageToken"] = page
            r = self._request("POST", f"{API}/mediaItems:search", json=body)
            r.raise_for_status()
            j = r.json()
            ids.extend(m["id"] for m in j.get("mediaItems", []))
            page = j.get("nextPageToken")
            if not page:
                return ids

    # --- uploads / media items ------------------------------------------
    def upload_bytes(self, data: bytes, mime: str, filename: str = "") -> str:
        r = self._request(
            "POST",
            f"{API}/uploads",
            data=data,
            headers={
                "Content-Type": "application/octet-stream",
                "X-Goog-Upload-Content-Type": mime,
                "X-Goog-Upload-Protocol": "raw",
            },
        )
        r.raise_for_status()
        return r.text

    def batch_create(self, items: list[tuple[str, str]], album_id: str | None = None) -> list[CreatedItem]:
        """items = (upload_token, filename) pairs. Chunks at 50; tolerates HTTP 207."""
        results: list[CreatedItem] = []
        for chunk in chunked(items):
            body = {
                "newMediaItems": [
                    {"simpleMediaItem": {"uploadToken": tok, "fileName": name}}
                    for tok, name in chunk
                ]
            }
            if album_id:
                body["albumId"] = album_id
            try:
                r = self._request("POST", f"{API}/mediaItems:batchCreate", json=body)
                if r.status_code not in (200, 207):
                    r.raise_for_status()
                parsed = parse_batch_create_result(r.json())
                if len(parsed) != len(chunk):
                    raise ValueError(f"got {len(parsed)} results for {len(chunk)} items")
            except Exception as e:  # noqa: BLE001 - isolate a bad chunk, keep going
                parsed = [
                    CreatedItem(filename=name, media_item_id=None, ok=False, message=str(e))
                    for _, name in chunk
                ]
            results.extend(parsed)
        return results
