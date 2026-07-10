"""Audio mix levels — narration and background music volume from env or defaults."""

from __future__ import annotations

import os

DEFAULT_MUSIC_VOLUME = 0.25
DEFAULT_NARRATION_VOLUME = 1.2


def resolve_music_volume(explicit: float | None = None) -> float:
    """Return music volume from explicit arg, MUSIC_VOLUME env, or default."""
    if explicit is not None:
        return explicit
    raw = os.environ.get("MUSIC_VOLUME", "").strip()
    if raw:
        try:
            return float(raw)
        except ValueError:
            pass
    return DEFAULT_MUSIC_VOLUME


def resolve_narration_volume(explicit: float | None = None) -> float:
    """Return narration volume from explicit arg, NARRATION_VOLUME env, or default."""
    if explicit is not None:
        return explicit
    raw = os.environ.get("NARRATION_VOLUME", "").strip()
    if raw:
        try:
            return float(raw)
        except ValueError:
            pass
    return DEFAULT_NARRATION_VOLUME
