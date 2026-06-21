"""Command-line interface: init / run / status."""
from __future__ import annotations

import argparse
import os
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path

from .auth import make_client
from .config import load_config, render_config_template
from .images import jpeg_filename, prepare_for_upload
from .pipeline import reshuffle_existing, run_rotation
from .progress import format_progress
from .selection import select_preview
from .source import enumerate_photos
from .state import State


def _make_progress_printer():
    """Return a progress(done, total) callback that draws an in-place bar with ETA."""
    state = {"start": None}

    def progress(done, total):
        if state["start"] is None:
            state["start"] = time.monotonic()
        elapsed = time.monotonic() - state["start"]
        line = format_progress(done, total, elapsed)
        end = "\n" if done >= total else ""
        print("\r  uploading " + line, end=end, flush=True)

    return progress


def home_dir() -> Path:
    return Path(
        os.environ.get("TV_PHOTOS_HOME", str(Path.home() / ".config" / "tv-photos"))
    ).expanduser()


def _paths(args):
    home = home_dir()
    home.mkdir(parents=True, exist_ok=True)
    config = Path(args.config).expanduser() if getattr(args, "config", None) else home / "config.toml"
    return home, config, home / "client_secret.json", home / "token.json", home / "state.db"


def cmd_init(args) -> int:
    home, config, client_secret, token, state_db = _paths(args)

    if args.client_secret:
        shutil.copy(Path(args.client_secret).expanduser(), client_secret)
        os.chmod(client_secret, 0o600)  # contains an OAuth client secret
        print(f"Installed client secret -> {client_secret}")

    if not config.exists():
        config.write_text(render_config_template(args.libraries or []))
        print(f"Wrote config template -> {config}")
        if not args.libraries:
            print("  edit [source].libraries to point at your .photoslibrary paths, then re-run init")

    title = load_config(config).album_title if config.exists() else "TV Rotation"

    client = make_client(client_secret, token)
    st = State(state_db)
    album_id = st.get_album_id()
    if album_id:
        print(f"Album already initialized (id={album_id})")
    else:
        album_id = client.create_album(title)
        st.set_album_id(album_id)
        print(f"Created album {title!r} (id={album_id})")

    print("\nNext: on the TV, Ambient mode -> Google Photos -> select this album once.")
    return 0


def cmd_run(args) -> int:
    home, config, client_secret, token, state_db = _paths(args)
    if not config.exists():
        sys.exit(f"No config at {config}. Run `tv-photos init` and set [source].libraries.")
    cfg = load_config(config)

    st = State(state_db)
    album_id = st.get_album_id()
    if not album_id:
        sys.exit("No album yet — run `tv-photos init` first.")

    count = args.count if args.count else cfg.count

    if args.reuse:
        # Fast/free: reshuffle the album from already-uploaded photos (no scan, no upload).
        client = make_client(client_secret, token)
        report = reshuffle_existing(
            client=client, state=st, count=count, album_id=album_id,
            rng=random.Random(), log=print,
        )
        print(f"\nDone (reuse). selected={report.selected} "
              f"album=+{report.added}/-{report.removed} -> {report.album_size}")
        return 0

    dry = cfg.dry_run or args.dry_run
    client = None if dry else make_client(client_secret, token)

    print("Scanning libraries (can take several minutes on external drives)...")
    candidates = enumerate_photos(
        cfg.libraries, cfg.min_width, cfg.exclude_screenshots, log=lambda m: print("  " + m)
    )
    if not candidates:
        sys.exit("No eligible photos found — check [source].libraries and that the drive is mounted.")

    overlay = cfg.overlay_location and not args.no_location
    report = run_rotation(
        client=client,
        state=st,
        candidates=candidates,
        count=count,
        album_id=album_id,
        max_long_edge=cfg.upload_max_long_edge,
        jpeg_quality=cfg.jpeg_quality,
        rng=random.Random(),
        dry_run=dry,
        overlay_location=overlay,
        log=print,
        progress=None if dry else _make_progress_printer(),
    )
    tag = " [DRY RUN]" if report.dry_run else ""
    print(
        f"\nDone{tag}. pool={report.pool} selected={report.selected} reused={report.reused} "
        f"uploaded={report.uploaded} failed={report.upload_failed} "
        f"album=+{report.added}/-{report.removed} -> {report.album_size}"
    )
    return 1 if report.upload_failed else 0


def cmd_reshuffle(args) -> int:
    """Fast/free: set the album to a fresh small random set from already-uploaded photos.

    Keeps the album small (``reshuffle_count``, ~75) so Google TV Ambient mode actually
    cycles through all of them instead of replaying the same handful out of a 1000-photo album.
    No library scan, no uploads — finishes in seconds.
    """
    home, config, client_secret, token, state_db = _paths(args)
    cfg = load_config(config) if config.exists() else None
    st = State(state_db)
    album_id = st.get_album_id()
    if not album_id:
        sys.exit("No album yet — run `tv-photos init` first.")

    count = args.count or (cfg.reshuffle_count if cfg else 75)
    pool = st.count_uploaded()
    if pool == 0:
        sys.exit("Nothing uploaded yet — run a full `tv-photos run` first to build the pool.")

    client = make_client(client_secret, token)
    report = reshuffle_existing(
        client=client, state=st, count=count, album_id=album_id,
        rng=random.Random(), log=print,
    )
    print(f"\nDone (reshuffle). album now holds {report.album_size} photos "
          f"(+{report.added}/-{report.removed}) drawn from {pool} uploaded.")
    return 0


def cmd_preview(args) -> int:
    """Render a few photos with the location overlay to a folder, so you can eyeball
    the result before a full run touches the album. No uploads, no album changes."""
    home, config, client_secret, token, state_db = _paths(args)
    if not config.exists():
        sys.exit(f"No config at {config}. Run `tv-photos init` and set [source].libraries.")
    cfg = load_config(config)

    out = Path(args.out).expanduser() if args.out else home / "preview"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    print("Scanning libraries to find photos with location (can take several minutes)...")
    candidates = enumerate_photos(
        cfg.libraries, cfg.min_width, cfg.exclude_screenshots, log=lambda m: print("  " + m)
    )
    chosen = select_preview(candidates, args.count, random.Random())
    if not chosen:
        sys.exit("No photos with location info found — nothing to preview. "
                 "(Photos need GPS/place data from Apple Photos.)")

    for i, photo in enumerate(chosen, 1):
        data = prepare_for_upload(photo.path, cfg.upload_max_long_edge, cfg.jpeg_quality, photo.place)
        name = f"{i:02d}_{jpeg_filename(photo.filename)}"
        (out / name).write_bytes(data)
        print(f"  {name}  ->  {photo.place}")

    print(f"\nWrote {len(chosen)} preview image(s) to {out}")
    if sys.platform == "darwin":
        subprocess.run(["open", str(out)], check=False)  # pop the folder in Finder
    return 0


def cmd_status(args) -> int:
    home, config, client_secret, token, state_db = _paths(args)
    st = State(state_db)
    print(f"home:           {home}")
    print(f"config:         {config} {'(exists)' if config.exists() else '(MISSING)'}")
    print(f"credentials:    token={'yes' if token.exists() else 'no'} "
          f"client_secret={'yes' if client_secret.exists() else 'no'}")
    print(f"album_id:       {st.get_album_id()}")
    print(f"uploaded total: {st.count_uploaded()}")
    print(f"album members:  {len(st.get_album_members())}")
    if config.exists():
        try:
            cfg = load_config(config)
            print(f"rotation count: {cfg.count}  (reshuffle: {cfg.reshuffle_count})")
            print(f"location label: {'on' if cfg.overlay_location else 'off'}")
            print(f"libraries:      {len(cfg.libraries)}")
            for lib in cfg.libraries:
                print(f"  - {lib}")
        except ValueError as e:
            print(f"config error:   {e}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="tv-photos",
        description="Rotate random Apple Photos onto a Google TV ambient-mode album.",
    )
    p.add_argument("--config", help="path to config.toml (default ~/.config/tv-photos/config.toml)")
    sub = p.add_subparsers(dest="command", required=True)

    pi = sub.add_parser("init", help="OAuth, create album, write a config template")
    pi.add_argument("--client-secret", help="OAuth Desktop client_secret.json to install")
    pi.add_argument("--libraries", nargs="*", help="library paths to write into the new config")
    pi.set_defaults(func=cmd_init)

    pr = sub.add_parser("run", help="select + upload + reshuffle the album (the core loop)")
    pr.add_argument("--dry-run", action="store_true", help="no write calls; just print the plan")
    pr.add_argument("--count", type=int, help="override rotation count for this run (e.g. a small first test)")
    pr.add_argument("--reuse", action="store_true",
                    help="reshuffle the album from already-uploaded photos only (no library scan, no new uploads)")
    pr.add_argument("--no-location", action="store_true",
                    help="don't burn the location label onto photos this run (overrides config)")
    pr.set_defaults(func=cmd_run)

    prs = sub.add_parser(
        "reshuffle",
        help="fast/free: set the album to a fresh small random set from already-uploaded photos",
    )
    prs.add_argument("--count", type=int,
                     help="album size (default [rotation].reshuffle_count, ~75) — keep small so the TV cycles all")
    prs.set_defaults(func=cmd_reshuffle)

    pp = sub.add_parser(
        "preview",
        help="render a few located photos with the overlay to a folder (no uploads) to eyeball the style",
    )
    pp.add_argument("--count", type=int, default=8, help="how many sample images to render (default 8)")
    pp.add_argument("--out", help="output folder (default ~/.config/tv-photos/preview)")
    pp.set_defaults(func=cmd_preview)

    ps = sub.add_parser("status", help="show pool/album/credential state")
    ps.set_defaults(func=cmd_status)

    args = p.parse_args(argv)
    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())
