"""Background music selection — pick a random track from a music library folder."""

from __future__ import annotations

import os
import random
import shutil
from pathlib import Path

MUSIC_EXTENSIONS = frozenset({".mp3", ".wav", ".m4a", ".ogg", ".aac"})
DEFAULT_MUSIC_DIR = Path("assets/music")
FALLBACK_MUSIC_DIR = Path(__file__).resolve().parent.parent / "music"
from core.audio_volume import DEFAULT_MUSIC_VOLUME, resolve_music_volume
def _legacy_music_file() -> Path | None:
    """Single-track override via BACKGROUND_MUSIC_PATH (file path)."""
    legacy = os.environ.get("BACKGROUND_MUSIC_PATH", "").strip()
    if not legacy:
        return None
    path = Path(legacy)
    if path.is_file() and path.suffix.lower() in MUSIC_EXTENSIONS:
        return path
    return None


def resolve_music_dir(explicit: str | Path | None = None) -> Path:
    """Return the music library directory from explicit arg, env, or defaults."""
    if explicit is not None:
        return Path(explicit)

    music_dir = os.environ.get("MUSIC_DIR", "").strip()
    if music_dir:
        return Path(music_dir)

    legacy = os.environ.get("BACKGROUND_MUSIC_PATH", "").strip()
    if legacy:
        path = Path(legacy)
        if path.is_dir():
            return path

    # Prefer the first library folder that actually contains tracks.
    for candidate in (DEFAULT_MUSIC_DIR, FALLBACK_MUSIC_DIR):
        if list_music_files(candidate):
            return candidate

    return DEFAULT_MUSIC_DIR


def list_music_files(music_dir: str | Path) -> list[Path]:
    """List audio files in music_dir (non-recursive)."""
    root = Path(music_dir)
    if not root.is_dir():
        return []

    files = [
        path
        for path in sorted(root.iterdir())
        if path.is_file() and path.suffix.lower() in MUSIC_EXTENSIONS
    ]
    return files


def pick_random_music(
    music_dir: str | Path | None = None,
    *,
    rng: random.Random | None = None,
) -> Path | None:
    """Pick a random music file from the library. Returns None if the folder is empty."""
    fixed = _legacy_music_file()
    if fixed is not None and music_dir is None:
        return fixed

    root = resolve_music_dir(music_dir)
    candidates = list_music_files(root)
    if not candidates:
        return None
    chooser = rng or random
    return chooser.choice(candidates)


def stage_music_for_output(
    music_path: str | Path,
    output_dir: str | Path,
) -> Path:
    """Copy a music file beside other render artifacts when it lives outside output_dir."""
    src = Path(music_path).resolve()
    if not src.is_file():
        raise FileNotFoundError(f"Music file not found: {src}")

    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    dest = out / src.name
    if src != dest:
        shutil.copy2(src, dest)
    return dest


def attach_random_music(
    output_dir: str | Path,
    *,
    music_dir: str | Path | None = None,
    volume: float | None = None,
    rng: random.Random | None = None,
) -> dict[str, str | float] | None:
    """Pick random background music and stage it in output_dir.

    Returns an audio.music dict for the project payload, or None if no tracks found.
    """
    picked = pick_random_music(music_dir, rng=rng)
    if picked is None:
        return None

    staged = stage_music_for_output(picked, output_dir)
    return {
        "path": str(staged.resolve()),
        "volume": resolve_music_volume(volume),
        "source": "random",
        "original_name": picked.name,
    }
