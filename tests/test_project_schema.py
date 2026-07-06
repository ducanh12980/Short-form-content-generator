"""Tests for core/project_schema.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.project_schema import (
    get_broll_dir,
    get_caption_tokens,
    get_caption_settings,
    get_narration_duration_ms,
    get_raw_script,
    get_topic,
    load_project,
    normalize_project,
    save_project,
)


def test_normalize_project_upgrades_legacy_payload() -> None:
    legacy = {
        "topic": "test",
        "raw_script": "Hello world",
        "tokens": [{"word": "Hello", "highlight_color": "none", "animation_pop": "none"}],
        "audio": {
            "path": "output/narration.mp3",
            "word_timestamps": [{"text": "Hello", "start_ms": 0, "end_ms": 100}],
        },
    }
    project = normalize_project(legacy)
    assert project["project_version"] == 1
    assert project["captions"]["tokens"][0]["text"] == "Hello"
    assert project["captions"]["tokens"][0]["start_ms"] == 0


def test_load_project_reads_file(tmp_path: Path) -> None:
    payload = {
        "topic": "x",
        "tokens": [{"text": "a", "style": "primary", "animation": "none"}],
        "audio": {
            "path": str(tmp_path / "narration.mp3"),
            "word_timestamps": [{"text": "a", "start_ms": 0, "end_ms": 50}],
        },
    }
    path = tmp_path / "pipeline_payload.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    project = load_project(path)
    assert project["captions"]["theme"] == "minimalist"


def test_get_caption_tokens_shared_schema() -> None:
    project = normalize_project(
        {
            "tokens": [{"text": "Go", "style": "highlight", "animation": "pop"}],
            "audio": {"word_timestamps": [{"text": "Go", "start_ms": 0, "end_ms": 80}]},
        }
    )
    tokens = get_caption_tokens(project)
    assert tokens[0]["text"] == "Go"
    assert tokens[0]["style"] == "highlight"


def test_get_caption_settings_font_override() -> None:
    project = {
        "captions": {
            "theme": "cyberpunk",
            "font": "Arial-Bold",
            "tokens": [],
        }
    }
    settings = get_caption_settings(project)
    assert settings["theme_name"] == "cyberpunk"
    assert settings["font_override"] == "Arial-Bold"


def test_normalize_project_requires_tokens_and_audio() -> None:
    with pytest.raises(ValueError, match="captions or legacy"):
        normalize_project({"topic": "only topic"})


def test_get_broll_dir_from_render_output() -> None:
    project = normalize_project(
        {
            "tokens": [{"text": "Hi", "style": "primary", "animation": "none"}],
            "audio": {
                "path": "output/narration.mp3",
                "word_timestamps": [{"text": "Hi", "start_ms": 0, "end_ms": 100}],
            },
        }
    )
    assert get_broll_dir(project) == Path("output/images")


def test_get_narration_duration_ms_from_timestamps() -> None:
    project = normalize_project(
        {
            "tokens": [{"text": "a", "style": "primary", "animation": "none"}],
            "audio": {
                "word_timestamps": [
                    {"text": "a", "start_ms": 0, "end_ms": 400},
                    {"text": "b", "start_ms": 400, "end_ms": 900},
                ],
            },
        }
    )
    assert get_narration_duration_ms(project) == 900


def test_save_and_reload_project(tmp_path: Path) -> None:
    project = {"topic": "t", "captions": {"theme": "minimalist", "font": None, "tokens": []}}
    path = tmp_path / "project.json"
    save_project(project, path)
    loaded = load_project(path)
    assert loaded["topic"] == "t"


def test_get_raw_script_and_topic() -> None:
    project = {"topic": " brief ", "raw_script": " script "}
    assert get_topic(project) == "brief"
    assert get_raw_script(project) == "script"


def test_normalize_project_rebuilds_karaoke_from_words_by_scene() -> None:
    project = normalize_project(
        {
            "topic": "t",
            "caption_mode": "sentence",
            "scenes": [
                {
                    "id": 1,
                    "tts": "Câu một. Câu hai.",
                    "start_ms": 0,
                    "end_ms": 2000,
                }
            ],
            "captions": {"theme": "minimalist", "tokens": []},
            "audio": {
                "path": "output/narration.mp3",
                "word_timestamps": [
                    {"text": "Câu", "start_ms": 0, "end_ms": 100},
                    {"text": "một", "start_ms": 100, "end_ms": 300},
                    {"text": "Câu", "start_ms": 500, "end_ms": 600},
                    {"text": "hai", "start_ms": 600, "end_ms": 800},
                ],
                "words_by_scene": {
                    "1": [
                        {"text": "Câu", "start_ms": 0, "end_ms": 100},
                        {"text": "một", "start_ms": 100, "end_ms": 300},
                        {"text": "Câu", "start_ms": 500, "end_ms": 600},
                        {"text": "hai", "start_ms": 600, "end_ms": 800},
                    ]
                },
            },
        }
    )
    tokens = get_caption_tokens(project)
    assert len(tokens) == 2
    assert len(tokens[0]["words"]) == 2
    assert tokens[0]["words"][0]["text"] == "Câu"


def test_load_project_preserves_karaoke_words(tmp_path: Path) -> None:
    payload = {
        "topic": "t",
        "caption_mode": "sentence",
        "scenes": [{"id": 1, "tts": "Hi.", "start_ms": 0, "end_ms": 500}],
        "captions": {
            "theme": "minimalist",
            "tokens": [
                {
                    "text": "Hi.",
                    "style": "primary",
                    "animation": "none",
                    "start_ms": 0,
                    "end_ms": 400,
                    "words": [{"text": "Hi.", "start_ms": 0, "end_ms": 400}],
                }
            ],
        },
        "audio": {
            "path": str(tmp_path / "narration.mp3"),
            "word_timestamps": [{"text": "Hi", "start_ms": 0, "end_ms": 400}],
        },
    }
    path = tmp_path / "pipeline_payload.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    loaded = load_project(path)
    tokens = get_caption_tokens(loaded)
    assert len(tokens[0]["words"]) == 1


def test_normalize_project_rebuilds_sentence_captions() -> None:
    project = normalize_project(
        {
            "topic": "t",
            "caption_mode": "sentence",
            "scenes": [
                {
                    "id": 1,
                    "tts": "Câu một. Câu hai.",
                    "start_ms": 0,
                    "end_ms": 2000,
                }
            ],
            "captions": {"theme": "minimalist", "tokens": []},
            "audio": {
                "path": "output/narration.mp3",
                "word_timestamps": [
                    {"text": "Câu", "start_ms": 0, "end_ms": 100},
                    {"text": "một", "start_ms": 100, "end_ms": 300},
                    {"text": "Câu", "start_ms": 500, "end_ms": 600},
                    {"text": "hai", "start_ms": 600, "end_ms": 800},
                ],
            },
        }
    )
    tokens = get_caption_tokens(project)
    assert len(tokens) == 2
    assert tokens[0]["text"] == "Câu một."
    assert tokens[0]["start_ms"] == 0
    assert tokens[1]["end_ms"] == 800
