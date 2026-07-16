"""Brand end card — a fixed image appended after narration on every video."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

ENDCARD_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp"})
DEFAULT_ENDCARD_PATH = Path("assets/endcard/endcard.jpg")
FALLBACK_ENDCARD_PATH = (
    Path(__file__).resolve().parent.parent / "assets" / "endcard" / "endcard.jpg"
)
DEFAULT_ENDCARD_DURATION_MS = 2500


def resolve_endcard_path(explicit: str | Path | None = None) -> Path | None:
    """Return the end card image from explicit arg, ENDCARD_PATH env, or default.

    Returns None when disabled (ENDCARD_PATH="off") or no image is on disk.
    """
    if explicit is not None:
        path = Path(explicit)
        return path if path.is_file() else None

    override = os.environ.get("ENDCARD_PATH", "").strip()
    if override:
        if override.lower() in ("off", "none", "0"):
            return None
        path = Path(override)
        return path if path.is_file() else None

    for candidate in (DEFAULT_ENDCARD_PATH, FALLBACK_ENDCARD_PATH):
        if candidate.is_file() and candidate.suffix.lower() in ENDCARD_EXTENSIONS:
            return candidate
    return None


def resolve_endcard_duration_ms(explicit: int | None = None) -> int:
    """Return end card screen time in ms from explicit arg, env, or default."""
    if explicit is not None:
        return max(1, int(explicit))

    raw = os.environ.get("ENDCARD_DURATION_MS", "").strip()
    if not raw:
        return DEFAULT_ENDCARD_DURATION_MS
    try:
        value = int(float(raw))
    except ValueError:
        return DEFAULT_ENDCARD_DURATION_MS
    return value if value > 0 else DEFAULT_ENDCARD_DURATION_MS


def stage_endcard_for_output(endcard_path: str | Path, output_dir: str | Path) -> Path:
    """Copy the end card beside other render artifacts so Remotion can serve it."""
    src = Path(endcard_path).resolve()
    if not src.is_file():
        raise FileNotFoundError(f"End card image not found: {src}")

    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    dest = out / f"endcard{src.suffix.lower()}"
    if src != dest:
        shutil.copy2(src, dest)
    return dest


def attach_endcard(
    image_timeline: list[dict[str, Any]],
    output_dir: str | Path,
    *,
    endcard_path: str | Path | None = None,
    duration_ms: int | None = None,
) -> dict[str, Any] | None:
    """Append the brand end card to a video.images timeline, extending the video.

    The card starts where the last slide ends, so narration and slide timing are
    untouched — the video simply runs longer. Returns the appended entry, or None
    when no end card is configured.
    """
    picked = resolve_endcard_path(endcard_path)
    if picked is None:
        return None

    staged = stage_endcard_for_output(picked, output_dir)
    start_ms = max((int(image.get("end_ms", 0)) for image in image_timeline), default=0)
    hold_ms = resolve_endcard_duration_ms(duration_ms)

    entry: dict[str, Any] = {
        "path": str(staged.resolve()),
        "start_ms": start_ms,
        "end_ms": start_ms + hold_ms,
        "scene_id": None,
        "role": "endcard",
        "source": "static",
        "media_type": "image",
        "original_name": picked.name,
    }
    image_timeline.append(entry)
    return entry
