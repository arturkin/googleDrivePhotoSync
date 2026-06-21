"""TOML configuration: load, defaults, validation."""
from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "tv-photos" / "config.toml"


@dataclass
class Config:
    libraries: list[str]
    exclude_screenshots: bool = True
    min_width: int = 1000
    upload_max_long_edge: int = 3840
    jpeg_quality: int = 85
    album_title: str = "TV Rotation"
    count: int = 1000
    reshuffle_count: int = 75
    overlay_location: bool = True
    dry_run: bool = False


def load_config(path: str | Path) -> Config:
    with open(Path(path), "rb") as f:
        data = tomllib.load(f)
    source = data.get("source", {})
    quality = data.get("quality", {})
    rotation = data.get("rotation", {})
    overlay = data.get("overlay", {})
    behavior = data.get("behavior", {})

    cfg = Config(
        libraries=source.get("libraries") or [],
        exclude_screenshots=source.get("exclude_screenshots", True),
        min_width=quality.get("min_width", 1000),
        upload_max_long_edge=quality.get("upload_max_long_edge", 3840),
        jpeg_quality=quality.get("jpeg_quality", 85),
        album_title=rotation.get("album_title", "TV Rotation"),
        count=rotation.get("count", 1000),
        reshuffle_count=rotation.get("reshuffle_count", 75),
        overlay_location=overlay.get("location", True),
        dry_run=behavior.get("dry_run", False),
    )
    _validate(cfg)
    return cfg


def _validate(cfg: Config) -> None:
    if not isinstance(cfg.libraries, list) or not cfg.libraries:
        raise ValueError(
            "config [source].libraries must be a non-empty list of .photoslibrary paths"
        )
    if cfg.count < 1:
        raise ValueError("config [rotation].count must be >= 1")
    if cfg.reshuffle_count < 1:
        raise ValueError("config [rotation].reshuffle_count must be >= 1")
    if cfg.min_width < 0:
        raise ValueError("config [quality].min_width must be >= 0")
    if not 1 <= cfg.jpeg_quality <= 100:
        raise ValueError("config [quality].jpeg_quality must be between 1 and 100")
    if cfg.upload_max_long_edge < 1:
        raise ValueError("config [quality].upload_max_long_edge must be >= 1")


def render_config_template(libraries: list[str]) -> str:
    # json.dumps emits a valid TOML basic string (same \" and \\ escaping).
    libs = ", ".join(json.dumps(lib) for lib in libraries)
    return f"""# tv-photos configuration
[source]
# Apple Photos libraries to pool photos from (random selection across all of them).
libraries = [{libs}]
exclude_screenshots = true

[quality]
min_width = 1000              # skip images narrower than this (px)
upload_max_long_edge = 3840   # downscale cap on upload (px) — keeps permanent storage small
jpeg_quality = 85

[rotation]
album_title = "TV Rotation"
count = 1000                  # photos uploaded per full `run` (favorites first, then random fill)
reshuffle_count = 75          # album size for `reshuffle` — keep small so the TV cycles them all

[overlay]
location = true               # burn "City, Country" into the bottom-left of each photo (skipped if unknown)

[behavior]
dry_run = false
"""
