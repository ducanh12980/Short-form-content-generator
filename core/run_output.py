"""Timestamped run folders for pipeline artifacts (same pattern as stitch.py)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

GENERATIONS_BASE = Path("output") / "generations"
STITCH_BASE = Path("output") / "stitch"
RUN_ID_FORMAT = "%Y%m%d_%H%M%S"


def new_run_dir(base: Path) -> Path:
    """Return ``<base>/<YYYYMMDD_HHMMSS>/`` (directory is not created yet)."""
    run_id = datetime.now().strftime(RUN_ID_FORMAT)
    return base / run_id


def new_generation_run_dir() -> Path:
    """Return a unique generation run folder under ``output/generations/``."""
    return new_run_dir(GENERATIONS_BASE)


def ensure_run_dir(path: str | Path) -> Path:
    """Create the run folder and return its resolved path."""
    resolved = Path(path).resolve()
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def resolve_generation_output_dir(explicit: str | Path | None = None) -> Path:
    """Pick output dir: explicit CLI arg, or a new timestamped run folder.

    ``OUTPUT_DIR`` sets the parent folder for timestamped runs (default:
    ``output/generations``). It does not write directly into a fixed folder —
    use ``--output-dir`` for that.
    """
    import os

    if explicit is not None and str(explicit).strip():
        return Path(explicit)
    env = os.environ.get("OUTPUT_DIR", "").strip()
    generations_base = Path(env) if env else GENERATIONS_BASE
    return new_run_dir(generations_base)
