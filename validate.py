#!/usr/bin/env python3
"""
Phase 0 validation spike for the Mac -> Google TV ambient-mode photo rotator.

PURPOSE
  Prove (or disprove) the project's #1 risk: does an album CREATED BY THIS APP
  via the Google Photos Library API show up in the TV's
  Ambient mode -> Google Photos album picker?

  Research says ~70% chance it does NOT. This spike is the cheapest way to find
  out on your actual TV before building the full tool. It is THROWAWAY code.

WHAT IT DOES
  1. Desktop OAuth (scope: photoslibrary.appendonly), caches token.json.
  2. Creates an album "TV Rotation (API test)".
  3. Uploads the photos you pass on the command line (HEIC auto-converted via `sips`).
  4. batchCreate's them directly into the album (handles HTTP 207 partial success).
  5. Prints the album id and exactly what to check on the TV.

USAGE
  # put a few photos in ./test_photos/  (or pass paths explicitly)
  ./.venv/bin/python validate.py
  ./.venv/bin/python validate.py ~/Desktop/a.jpg ~/Desktop/b.heic

REQUIRES
  client_secret.json (OAuth Desktop client) in this directory. See SETUP.md.
"""
from __future__ import annotations

import mimetypes
import subprocess
import sys
import tempfile
from pathlib import Path

import requests
from google.auth.transport.requests import AuthorizedSession, Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

HERE = Path(__file__).resolve().parent
CLIENT_SECRET_FILE = HERE / "client_secret.json"
TOKEN_FILE = HERE / "token.json"
TEST_PHOTOS_DIR = HERE / "test_photos"

# Only the upload/create scope is needed for this spike. The full tool will also
# request photoslibrary.edit.appcreateddata (remove) + readonly.appcreateddata (read).
SCOPES = ["https://www.googleapis.com/auth/photoslibrary.appendonly"]

API = "https://photoslibrary.googleapis.com/v1"
ALBUM_TITLE = "TV Rotation (API test)"

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".heif"}
HEIC_EXTS = {".heic", ".heif"}


def die(msg: str, code: int = 1) -> None:
    print(f"\n[ERROR] {msg}", file=sys.stderr)
    sys.exit(code)


def get_credentials() -> Credentials:
    """Desktop OAuth flow with on-disk token caching + refresh."""
    creds: Credentials | None = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing access token...")
            creds.refresh(Request())
        else:
            if not CLIENT_SECRET_FILE.exists():
                die(
                    f"Missing {CLIENT_SECRET_FILE.name}. Create an OAuth 'Desktop app' "
                    "client in Google Cloud and download it here. See SETUP.md."
                )
            print("Opening browser for Google sign-in / consent...")
            flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json())
        print(f"Saved credentials to {TOKEN_FILE.name}")
    return creds


def collect_photos(args: list[str]) -> list[Path]:
    if args:
        paths = [Path(a).expanduser() for a in args]
    elif TEST_PHOTOS_DIR.is_dir():
        paths = sorted(
            p for p in TEST_PHOTOS_DIR.iterdir() if p.suffix.lower() in IMAGE_EXTS
        )
    else:
        paths = []
    valid = [p for p in paths if p.is_file() and p.suffix.lower() in IMAGE_EXTS]
    if not valid:
        die(
            "No images found. Pass image paths as arguments, or drop a few "
            f"(.jpg/.png/.heic) into {TEST_PHOTOS_DIR}/ and re-run."
        )
    return valid


def to_uploadable(path: Path) -> tuple[bytes, str, str]:
    """Return (bytes, mime, filename) for upload; convert HEIC->JPEG via sips."""
    if path.suffix.lower() in HEIC_EXTS:
        tmp = Path(tempfile.mkdtemp()) / (path.stem + ".jpg")
        subprocess.run(
            ["sips", "-s", "format", "jpeg", str(path), "--out", str(tmp)],
            check=True,
            capture_output=True,
        )
        return tmp.read_bytes(), "image/jpeg", tmp.name
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    return path.read_bytes(), mime, path.name


def create_album(session: AuthorizedSession) -> str:
    r = session.post(f"{API}/albums", json={"album": {"title": ALBUM_TITLE}})
    if not r.ok:
        die(f"Create album failed: {r.status_code} {r.text}")
    album = r.json()
    print(f"Created album: {album.get('title')!r}  id={album['id']}")
    return album["id"]


def upload_bytes(session: AuthorizedSession, data: bytes, mime: str, name: str) -> str:
    r = session.post(
        f"{API}/uploads",
        data=data,
        headers={
            "Content-Type": "application/octet-stream",
            "X-Goog-Upload-Content-Type": mime,
            "X-Goog-Upload-Protocol": "raw",
        },
    )
    if not r.ok:
        die(f"Upload failed for {name}: {r.status_code} {r.text}")
    return r.text  # plain-text upload token


def batch_create(session: AuthorizedSession, album_id: str, items: list[tuple[str, str]]) -> None:
    """items = list of (upload_token, filename). <=50 per call."""
    body = {
        "albumId": album_id,
        "newMediaItems": [
            {"simpleMediaItem": {"uploadToken": tok, "fileName": name}}
            for tok, name in items
        ],
    }
    r = session.post(f"{API}/mediaItems:batchCreate", json=body)
    # 200 = all ok, 207 = partial success. Both carry per-item results.
    if r.status_code not in (200, 207):
        die(f"batchCreate failed: {r.status_code} {r.text}")
    results = r.json().get("newMediaItemResults", [])
    ok = 0
    for res in results:
        status = res.get("status", {})
        # status.code absent/0 == OK
        if status.get("code", 0) in (0, None):
            ok += 1
            mi = res.get("mediaItem", {})
            print(f"  + {mi.get('filename', '?')}  id={mi.get('id', '?')}")
        else:
            print(f"  ! FAILED: {status.get('message')} (token={res.get('uploadToken','?')[:12]}...)")
    print(f"\nbatchCreate HTTP {r.status_code}: {ok}/{len(results)} media items created.")


def main(argv: list[str]) -> int:
    photos = collect_photos(argv)
    print(f"Using {len(photos)} photo(s):")
    for p in photos:
        print(f"  - {p}")

    creds = get_credentials()
    session = AuthorizedSession(creds)

    album_id = create_album(session)

    tokens: list[tuple[str, str]] = []
    for p in photos:
        data, mime, name = to_uploadable(p)
        print(f"Uploading {name} ({mime}, {len(data)//1024} KB)...")
        tokens.append((upload_bytes(session, data, mime, name), name))

    # spike has <=50 photos; no chunking needed
    batch_create(session, album_id, tokens)

    print("\n" + "=" * 70)
    print("NEXT — the actual test (this is the go/no-go):")
    print(f"  On the TV: Settings -> System -> Ambient mode -> Google Photos.")
    print(f"  Look for the album titled:  {ALBUM_TITLE!r}")
    print("  (Give it a few minutes; a TV restart can force a sync.)")
    print("  Appears  -> Google Photos path works; we build the full tool.")
    print("  Missing  -> pivot to the USB/local fallback (see the plan).")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except requests.RequestException as e:
        die(f"Network error: {e}")
