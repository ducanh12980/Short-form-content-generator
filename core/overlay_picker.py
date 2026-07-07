"""Ambient overlay selection — pick and stage overlay loops from assets/overlays/."""

from __future__ import annotations

import json
import os
import random
import shutil
from pathlib import Path
from typing import Any

OVERLAY_EXTENSIONS = frozenset({".webm", ".mp4", ".mov"})
DEFAULT_OVERLAYS_DIR = Path("assets/overlays")
FALLBACK_OVERLAYS_DIR = Path(__file__).resolve().parent.parent / "assets" / "overlays"
MANIFEST_NAME = "manifest.json"
DEFAULT_FIRE_EFFECT = "fire"


def resolve_overlays_dir(explicit: str | Path | None = None) -> Path:
    """Return the overlays library directory from explicit arg, env, or default."""
    if explicit is not None:
        return Path(explicit)

    overlays_dir = os.environ.get("OVERLAYS_DIR", "").strip()
    if overlays_dir:
        return Path(overlays_dir)

    if (DEFAULT_OVERLAYS_DIR / MANIFEST_NAME).is_file():
        return DEFAULT_OVERLAYS_DIR
    return FALLBACK_OVERLAYS_DIR


def load_manifest(overlays_dir: str | Path | None = None) -> dict[str, Any]:
    """Load manifest.json from the overlays directory."""
    root = resolve_overlays_dir(overlays_dir)
    manifest_path = root / MANIFEST_NAME
    if not manifest_path.is_file():
        return {}
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _manifest_entry_for_path(manifest: dict[str, Any], rel_key: str) -> dict[str, Any]:
    entry = manifest.get(rel_key)
    return dict(entry) if isinstance(entry, dict) else {}


def list_overlays(overlays_dir: str | Path | None = None) -> list[Path]:
    """List overlay files registered in manifest, or scan effect subfolders."""
    root = resolve_overlays_dir(overlays_dir)
    manifest = load_manifest(root)
    candidates: list[Path] = []

    for rel_key in manifest:
        path = root / Path(rel_key.replace("/", os.sep))
        if path.is_file():
            candidates.append(path)

    if candidates:
        return sorted(candidates)

    if not root.is_dir():
        return []
    for subdir in sorted(root.iterdir()):
        if not subdir.is_dir():
            continue
        for path in sorted(subdir.iterdir()):
            if path.is_file() and path.suffix.lower() in OVERLAY_EXTENSIONS:
                candidates.append(path)
    return candidates


def list_fire_overlays(overlays_dir: str | Path | None = None) -> list[Path]:
    """List fire overlay files registered in manifest or present under fire/."""
    root = resolve_overlays_dir(overlays_dir)
    manifest = load_manifest(root)
    candidates: list[Path] = []

    for rel_key in manifest:
        entry = _manifest_entry_for_path(manifest, rel_key)
        if entry.get("effect") != DEFAULT_FIRE_EFFECT:
            continue
        path = root / Path(rel_key.replace("/", os.sep))
        if path.is_file():
            candidates.append(path)

    if candidates:
        return sorted(candidates)

    fire_dir = root / "fire"
    if not fire_dir.is_dir():
        return []
    return sorted(
        path
        for path in fire_dir.iterdir()
        if path.is_file() and path.suffix.lower() in OVERLAY_EXTENSIONS
    )


def pick_random_overlay(
    overlays_dir: str | Path | None = None,
    *,
    rng: random.Random | None = None,
) -> tuple[Path, dict[str, Any]] | None:
    """Pick a random overlay file and its manifest metadata."""
    root = resolve_overlays_dir(overlays_dir)
    manifest = load_manifest(root)
    candidates = list_overlays(root)
    if not candidates:
        return None

    chooser = rng or random
    picked = chooser.choice(candidates).resolve()
    root_resolved = root.resolve()

    rel_key = picked.relative_to(root_resolved).as_posix()
    entry = _manifest_entry_for_path(manifest, rel_key)
    if not entry:
        effect = picked.parent.name if picked.parent.name != root_resolved.name else "overlay"
        entry = {
            "effect": effect,
            "variant": picked.stem,
            "opacity_default": 0.4,
            "blend_mode": "screen",
            "duration_ms": 10_000,
        }
    return picked, entry


def pick_fire_overlay(
    overlays_dir: str | Path | None = None,
    *,
    rng: random.Random | None = None,
) -> tuple[Path, dict[str, Any]] | None:
    """Pick a random fire overlay file and its manifest metadata."""
    root = resolve_overlays_dir(overlays_dir)
    manifest = load_manifest(root)
    candidates = list_fire_overlays(root)
    if not candidates:
        return None

    chooser = rng or random
    picked = chooser.choice(candidates).resolve()
    root_resolved = root.resolve()

    rel_key = picked.relative_to(root_resolved).as_posix()
    entry = _manifest_entry_for_path(manifest, rel_key)
    if not entry:
        entry = {
            "effect": DEFAULT_FIRE_EFFECT,
            "variant": "sparks",
            "opacity_default": 0.4,
            "blend_mode": "screen",
            "duration_ms": 10_000,
        }
    return picked, entry


def stage_overlay_for_output(
    overlay_path: str | Path,
    output_dir: str | Path,
) -> Path:
    """Copy an overlay file beside other render artifacts when it lives outside output_dir."""
    src = Path(overlay_path).resolve()
    if not src.is_file():
        raise FileNotFoundError(f"Overlay file not found: {src}")

    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    dest = out / src.name
    if src != dest:
        shutil.copy2(src, dest)
    return dest


def attach_random_ambient_overlay(
    output_dir: str | Path,
    *,
    overlays_dir: str | Path | None = None,
    rng: random.Random | None = None,
) -> dict[str, Any] | None:
    """Pick a random ambient overlay and stage it in output_dir.

    Returns a video.ambient dict for the project payload, or None if no overlays found.
    """
    picked = pick_random_overlay(overlays_dir, rng=rng)
    if picked is None:
        return None

    overlay_path, entry = picked
    staged = stage_overlay_for_output(overlay_path, output_dir)
    effect = str(entry.get("effect", DEFAULT_FIRE_EFFECT))
    return {
        "effect": effect,
        "variant": str(entry.get("variant", overlay_path.stem)),
        "path": str(staged.resolve()),
        "opacity": float(entry.get("opacity_default", 0.4)),
        "blend_mode": str(entry.get("blend_mode", "screen")),
        "loop": True,
        "duration_ms": int(entry.get("duration_ms", 10_000)),
        "playback_rate": float(entry.get("playback_rate", 1.0)),
        "source": "random",
        "original_name": overlay_path.name,
    }
