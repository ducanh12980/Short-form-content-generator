"""Tests for the fixed brand end card appended after narration."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.endcard import (
    DEFAULT_ENDCARD_DURATION_MS,
    attach_endcard,
    resolve_endcard_duration_ms,
    resolve_endcard_path,
    stage_endcard_for_output,
)
from core.project_schema import load_project
from core.remotion_render_stage import project_to_remotion_props


@pytest.fixture(autouse=True)
def _clear_endcard_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ENDCARD_PATH", raising=False)
    monkeypatch.delenv("ENDCARD_DURATION_MS", raising=False)


def _endcard_file(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "endcard.jpg"
    path.write_bytes(b"jpg")
    return path


def test_repo_ships_an_endcard() -> None:
    """The daily batch relies on the committed card — CI has no Downloads folder."""
    assert resolve_endcard_path() is not None


def test_resolve_endcard_path_env_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    custom = tmp_path / "brand.png"
    custom.write_bytes(b"png")
    monkeypatch.setenv("ENDCARD_PATH", str(custom))
    assert resolve_endcard_path() == custom


def test_resolve_endcard_path_can_be_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENDCARD_PATH", "off")
    assert resolve_endcard_path() is None


def test_resolve_endcard_path_missing_file_is_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ENDCARD_PATH", str(tmp_path / "nope.jpg"))
    assert resolve_endcard_path() is None


def test_resolve_endcard_duration_ms_defaults_and_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert resolve_endcard_duration_ms() == DEFAULT_ENDCARD_DURATION_MS
    monkeypatch.setenv("ENDCARD_DURATION_MS", "4000")
    assert resolve_endcard_duration_ms() == 4000
    monkeypatch.setenv("ENDCARD_DURATION_MS", "garbage")
    assert resolve_endcard_duration_ms() == DEFAULT_ENDCARD_DURATION_MS
    assert resolve_endcard_duration_ms(1500) == 1500


def test_stage_endcard_copies_into_output_dir(tmp_path: Path) -> None:
    src = _endcard_file(tmp_path / "assets")
    out = tmp_path / "run"
    staged = stage_endcard_for_output(src, out)
    assert staged == (out / "endcard.jpg").resolve()
    assert staged.read_bytes() == b"jpg"


def test_attach_endcard_appends_after_last_slide(tmp_path: Path) -> None:
    src = _endcard_file(tmp_path / "assets")
    timeline = [
        {"path": "a.png", "start_ms": 0, "end_ms": 3000},
        {"path": "b.png", "start_ms": 3000, "end_ms": 9000},
    ]
    entry = attach_endcard(timeline, tmp_path / "run", endcard_path=src)

    assert entry is not None
    assert len(timeline) == 3 and timeline[-1] is entry
    assert entry["start_ms"] == 9000
    assert entry["end_ms"] == 9000 + DEFAULT_ENDCARD_DURATION_MS
    assert entry["role"] == "endcard"
    # Slide timing must be untouched — the card extends the video, not compresses it.
    assert timeline[1]["end_ms"] == 9000


def test_attach_endcard_returns_none_when_disabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ENDCARD_PATH", "off")
    timeline: list[dict] = [{"path": "a.png", "start_ms": 0, "end_ms": 3000}]
    assert attach_endcard(timeline, tmp_path) is None
    assert len(timeline) == 1


def test_render_duration_covers_endcard_past_narration(tmp_path: Path) -> None:
    """durationMs must follow the timeline, else the card renders off the end."""
    narration = tmp_path / "narration.mp3"
    narration.write_bytes(b"fake")
    scene = tmp_path / "scene.png"
    scene.write_bytes(b"png")
    card = tmp_path / "endcard.jpg"
    card.write_bytes(b"jpg")

    payload = {
        "topic": "test",
        "captions": {"theme": "minimalist", "font": None, "tokens": []},
        "video": {
            "images": [
                {"path": str(scene), "start_ms": 0, "end_ms": 9000},
                {"path": str(card), "start_ms": 9000, "end_ms": 11500},
            ]
        },
        "audio": {
            "path": str(narration),
            "word_timestamps": [{"text": "Hi", "start_ms": 0, "end_ms": 9000}],
        },
    }
    path = tmp_path / "pipeline_payload.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    props, _public_dir = project_to_remotion_props(load_project(path))

    assert props["durationMs"] == 11500
    assert props["images"][-1]["src"] == "endcard.jpg"
