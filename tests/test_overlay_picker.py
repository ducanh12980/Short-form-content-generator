"""Tests for ambient overlay picker."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.overlay_picker import (
    attach_random_ambient_overlay,
    list_fire_overlays,
    list_overlays,
    load_manifest,
    pick_fire_overlay,
    pick_random_overlay,
    resolve_overlays_dir,
    stage_overlay_for_output,
)
from core.project_schema import load_project
from core.remotion_render_stage import project_to_remotion_props


def test_load_manifest_reads_fire_entry() -> None:
    manifest = load_manifest()
    assert "fire/smoke_fire_sparks.webm" in manifest
    assert manifest["fire/smoke_fire_sparks.webm"]["effect"] == "fire"
    assert "snow/snow_storm.webm" in manifest
    assert manifest["snow/snow_storm.webm"]["effect"] == "snow"
    assert manifest["snow/snow_storm.webm"]["playback_rate"] == 0.5
    assert "lights/gold_particles.webm" in manifest
    assert manifest["lights/gold_particles.webm"]["effect"] == "lights"


def test_list_overlays_includes_repo_asset() -> None:
    overlays = list_overlays()
    names = [p.name for p in overlays]
    assert "smoke_fire_sparks.webm" in names
    assert "snow_storm.webm" in names
    assert "gold_particles.webm" in names


def test_pick_random_overlay_returns_metadata() -> None:
    picked = pick_random_overlay()
    if not list_overlays():
        pytest.skip("no overlays in library")
    path, entry = picked
    assert path.is_file()
    assert entry.get("blend_mode") == "screen"


def test_attach_random_ambient_overlay_stages_in_output(tmp_path: Path) -> None:
    overlays_dir = tmp_path / "overlays"
    fire_dir = overlays_dir / "fire"
    fire_dir.mkdir(parents=True)
    (fire_dir / "test_sparks.webm").write_bytes(b"webm")
    manifest = {
        "fire/test_sparks.webm": {
            "effect": "fire",
            "variant": "sparks",
            "opacity_default": 0.35,
            "blend_mode": "screen",
            "duration_ms": 5000,
        }
    }
    (overlays_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    out = tmp_path / "output"

    result = attach_random_ambient_overlay(out, overlays_dir=overlays_dir)
    assert result is not None
    staged = Path(str(result["path"]))
    assert staged.is_file()
    assert staged.parent == out.resolve()
    assert result["effect"] == "fire"
    assert result["opacity"] == 0.35
    assert result["duration_ms"] == 5000
    assert result["source"] == "random"


def test_project_to_remotion_props_includes_ambient_overlay(tmp_path: Path) -> None:
    narration = tmp_path / "narration.mp3"
    overlay = tmp_path / "smoke_fire_sparks.webm"
    narration.write_bytes(b"voice")
    overlay.write_bytes(b"webm")
    payload = {
        "topic": "test",
        "tokens": [],
        "audio": {
            "path": str(narration),
            "word_timestamps": [{"text": "Hi", "start_ms": 0, "end_ms": 400}],
        },
        "video": {
            "ambient": {
                "effect": "fire",
                "variant": "sparks",
                "path": str(overlay),
                "opacity": 0.42,
                "blend_mode": "screen",
                "duration_ms": 9830,
                "loop": True,
                "source": "auto",
            }
        },
    }
    path = tmp_path / "pipeline_payload.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    project = load_project(path)
    props, _ = project_to_remotion_props(project)
    assert props["ambientOverlaySrc"] == "smoke_fire_sparks.webm"
    assert props["ambientOpacity"] == 0.42
    assert props["ambientBlendMode"] == "screen"
    assert props["ambientLoopDurationMs"] == 9830


def test_project_to_remotion_props_includes_playback_rate(tmp_path: Path) -> None:
    narration = tmp_path / "narration.mp3"
    overlay = tmp_path / "snow_storm.webm"
    narration.write_bytes(b"voice")
    overlay.write_bytes(b"webm")
    payload = {
        "topic": "test",
        "tokens": [],
        "audio": {
            "path": str(narration),
            "word_timestamps": [{"text": "Hi", "start_ms": 0, "end_ms": 400}],
        },
        "video": {
            "ambient": {
                "effect": "snow",
                "path": str(overlay),
                "opacity": 0.45,
                "blend_mode": "screen",
                "duration_ms": 15015,
                "playback_rate": 0.5,
                "loop": True,
                "source": "random",
            }
        },
    }
    path = tmp_path / "pipeline_payload.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    project = load_project(path)
    props, _ = project_to_remotion_props(project)
    assert props["ambientPlaybackRate"] == 0.5


def test_stage_overlay_for_output_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        stage_overlay_for_output(tmp_path / "missing.webm", tmp_path / "out")


def test_resolve_overlays_dir_defaults_to_assets() -> None:
    root = resolve_overlays_dir()
    assert (root / "manifest.json").is_file()
