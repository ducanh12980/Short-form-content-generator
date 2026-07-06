"""Tests for background music picker."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.music_picker import (
    FALLBACK_MUSIC_DIR,
    attach_random_music,
    list_music_files,
    pick_random_music,
    resolve_music_dir,
    stage_music_for_output,
)
from core.project_schema import load_project
from core.remotion_render_stage import project_to_remotion_props


def test_list_music_files_filters_extensions(tmp_path: Path) -> None:
    (tmp_path / "a.mp3").write_bytes(b"x")
    (tmp_path / "b.txt").write_text("nope")
    (tmp_path / "c.wav").write_bytes(b"y")
    assert [p.name for p in list_music_files(tmp_path)] == ["a.mp3", "c.wav"]


def test_pick_random_music_returns_none_when_empty(tmp_path: Path) -> None:
    assert pick_random_music(tmp_path) is None


def test_resolve_music_dir_falls_back_to_repo_music_folder() -> None:
    """music/ at repo root is used when assets/music is empty."""
    if (FALLBACK_MUSIC_DIR / "music-1.mp3").is_file():
        assert resolve_music_dir() == FALLBACK_MUSIC_DIR


def test_pick_random_music_without_explicit_uses_library() -> None:
    picked = pick_random_music()
    if (FALLBACK_MUSIC_DIR / "music-1.mp3").is_file():
        assert picked is not None
        assert picked.suffix.lower() == ".mp3"


def test_pick_random_music_chooses_from_folder(tmp_path: Path) -> None:
    (tmp_path / "one.mp3").write_bytes(b"1")
    (tmp_path / "two.mp3").write_bytes(b"2")
    rng = __import__("random").Random(0)
    picked = pick_random_music(tmp_path, rng=rng)
    assert picked is not None
    assert picked.name in {"one.mp3", "two.mp3"}


def test_attach_random_music_stages_in_output(tmp_path: Path) -> None:
    music_dir = tmp_path / "library"
    music_dir.mkdir()
    (music_dir / "bed.mp3").write_bytes(b"music")
    out = tmp_path / "output"

    result = attach_random_music(out, music_dir=music_dir, rng=__import__("random").Random(0))
    assert result is not None
    staged = Path(str(result["path"]))
    assert staged.is_file()
    assert staged.parent == out.resolve()
    assert result["original_name"] == "bed.mp3"


def test_project_to_remotion_props_includes_music(tmp_path: Path) -> None:
    narration = tmp_path / "narration.mp3"
    music = tmp_path / "bed.mp3"
    narration.write_bytes(b"voice")
    music.write_bytes(b"music")
    payload = {
        "topic": "test",
        "tokens": [],
        "audio": {
            "path": str(narration),
            "word_timestamps": [{"text": "Hi", "start_ms": 0, "end_ms": 400}],
            "music": {"path": str(music), "volume": 0.2},
        },
    }
    path = tmp_path / "pipeline_payload.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    project = load_project(path)
    props, _ = project_to_remotion_props(project)
    assert props["musicSrc"] == "bed.mp3"
    assert props["musicVolume"] == 0.2


def test_stage_music_for_output_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        stage_music_for_output(tmp_path / "missing.mp3", tmp_path / "out")
