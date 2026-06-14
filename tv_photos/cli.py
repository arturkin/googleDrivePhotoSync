"""Command-line interface: init / run / status."""
from __future__ import annotations

import argparse
import os
import random
import shutil
import sys
import time
from pathlib import Path

from .auth import make_client
from .config import load_config, render_config_template
from .pipeline import run_rotation
from .progress import format_progress
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
    dry = cfg.dry_run or args.dry_run
    client = None if dry else make_client(client_secret, token)

    print("Scanning libraries (can take several minutes on external drives)...")
    candidates = enumerate_photos(
        cfg.libraries, cfg.min_width, cfg.exclude_screenshots, log=lambda m: print("  " + m)
    )
    if not candidates:
        sys.exit("No eligible photos found — check [source].libraries and that the drive is mounted.")

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
            print(f"rotation count: {cfg.count}")
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
    pr.set_defaults(func=cmd_run)

    ps = sub.add_parser("status", help="show pool/album/credential state")
    ps.set_defaults(func=cmd_status)

    args = p.parse_args(argv)
    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())
