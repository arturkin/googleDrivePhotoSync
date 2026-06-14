"""Local SQLite state: uploaded media items (by content hash) + album membership."""
from __future__ import annotations

import sqlite3
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS uploaded (
    sha256          TEXT PRIMARY KEY,
    media_item_id   TEXT NOT NULL,
    filename        TEXT,
    uploaded_at     TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS album_members (
    media_item_id   TEXT PRIMARY KEY
);
CREATE TABLE IF NOT EXISTS meta (
    key     TEXT PRIMARY KEY,
    value   TEXT
);
"""


class State:
    """Thin wrapper over a SQLite file holding the upload pool and album membership."""

    def __init__(self, path: str | Path):
        self.conn = sqlite3.connect(str(path), timeout=30)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA busy_timeout = 30000")  # wait, don't fail, on a locked db
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    # --- uploads ---------------------------------------------------------
    def record_upload(self, sha256: str, media_item_id: str, filename: str = "") -> None:
        self.conn.execute(
            "INSERT INTO uploaded (sha256, media_item_id, filename) VALUES (?, ?, ?) "
            "ON CONFLICT(sha256) DO UPDATE SET media_item_id=excluded.media_item_id, "
            "filename=excluded.filename, uploaded_at=CURRENT_TIMESTAMP",
            (sha256, media_item_id, filename),
        )
        self.conn.commit()

    def get_media_item_id(self, sha256: str) -> str | None:
        row = self.conn.execute(
            "SELECT media_item_id FROM uploaded WHERE sha256 = ?", (sha256,)
        ).fetchone()
        return row["media_item_id"] if row else None

    def count_uploaded(self) -> int:
        return self.conn.execute("SELECT COUNT(*) AS n FROM uploaded").fetchone()["n"]

    # --- album metadata --------------------------------------------------
    def set_album_id(self, album_id: str) -> None:
        self._set_meta("album_id", album_id)

    def get_album_id(self) -> str | None:
        return self._get_meta("album_id")

    def _set_meta(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO meta (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        self.conn.commit()

    def _get_meta(self, key: str) -> str | None:
        row = self.conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    # --- album membership ------------------------------------------------
    def set_album_members(self, media_item_ids) -> None:
        self.conn.execute("DELETE FROM album_members")
        self.conn.executemany(
            "INSERT OR IGNORE INTO album_members (media_item_id) VALUES (?)",
            [(mid,) for mid in media_item_ids],
        )
        self.conn.commit()

    def get_album_members(self) -> set[str]:
        return {
            r["media_item_id"]
            for r in self.conn.execute("SELECT media_item_id FROM album_members")
        }

    def close(self) -> None:
        self.conn.close()
