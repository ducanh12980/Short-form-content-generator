"""Run folders for pipeline artifacts (fixed final dir for orchestrator; timestamped for stitch)."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

DEFAULT_OUTPUT_BASE = Path("output")
FINAL_RUN_DIR_NAME = "final"
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


def reset_run_dir(path: str | Path) -> Path:
    """Remove an existing run folder and recreate it (overwrite previous artifacts)."""
    resolved = Path(path).resolve()
    if resolved.exists():
        shutil.rmtree(resolved)
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def resolve_final_output_dir() -> Path:
    """Default orchestrator output: ``<OUTPUT_DIR or output>/final``."""
    import os

    env = os.environ.get("OUTPUT_DIR", "").strip()
    base = Path(env) if env else DEFAULT_OUTPUT_BASE
    return base / FINAL_RUN_DIR_NAME


def prepare_default_run_dir() -> Path:
    """Clear and return the default run folder (``output/final``)."""
    return reset_run_dir(resolve_final_output_dir())


def resolve_generation_output_dir(explicit: str | Path | None = None) -> Path:
    """Pick output dir: explicit CLI arg, or the fixed ``final`` run folder.

    ``OUTPUT_DIR`` sets the parent folder for the default final dir (default:
    ``output/final``). Use ``--output-dir`` to write elsewhere without clearing.
    """
    if explicit is not None and str(explicit).strip():
        return Path(explicit)
    return resolve_final_output_dir()
