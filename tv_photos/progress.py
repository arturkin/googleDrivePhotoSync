"""Tiny dependency-free progress bar rendering for the CLI."""
from __future__ import annotations


def fmt_duration(seconds: float) -> str:
    """Format seconds as M:SS, or H:MM:SS past an hour."""
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{sec:02d}"
    return f"{m}:{sec:02d}"


def format_progress(done: int, total: int, elapsed: float, width: int = 24) -> str:
    """Render a single progress line with percent, count, elapsed, and ETA."""
    frac = (done / total) if total > 0 else 1.0
    frac = min(max(frac, 0.0), 1.0)
    filled = int(frac * width)
    bar = "█" * filled + "░" * (width - filled)
    eta = (elapsed / done * (total - done)) if (done > 0 and total > 0) else 0.0
    return (
        f"[{bar}] {int(frac * 100):3d}% {done}/{total} | "
        f"elapsed {fmt_duration(elapsed)} | ETA {fmt_duration(eta)}"
    )
