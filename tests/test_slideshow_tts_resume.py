"""Tests for slideshow pipeline TTS resume draft."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from core.slideshow_pipeline import (
    SCENES_DRAFT_FILENAME,
    _load_scenes_draft,
    _save_scenes_draft,
)


def _sample_slides_with_tts() -> list[dict]:
    return [
        {"id": 1, "role": "intro", "title": "Intro", "visual_concept": "dawn scene"},
        {"id": 2, "role": "content", "content_index": 1, "title": "A", "description": "d", "tts": "ta"},
        {"id": 3, "role": "content", "content_index": 2, "title": "B", "description": "d", "tts": "tb"},
        {"id": 4, "role": "content", "content_index": 3, "title": "C", "description": "d", "tts": "tc"},
        {"id": 5, "role": "ending", "title": "End", "visual_concept": "sunset path"},
    ]


def test_save_and_load_scenes_draft(tmp_path: Path) -> None:
    slides = _sample_slides_with_tts()
    _save_scenes_draft(tmp_path, topic="topic", slides=slides)
    loaded = _load_scenes_draft(tmp_path, topic="topic")
    assert loaded is not None
    assert loaded[1]["tts"] == "ta"


def test_load_scenes_draft_rejects_topic_mismatch(tmp_path: Path) -> None:
    slides = _sample_slides_with_tts()
    _save_scenes_draft(tmp_path, topic="topic-a", slides=slides)
    assert _load_scenes_draft(tmp_path, topic="topic-b") is None


@patch("core.slideshow_pipeline.run_scene_script_writer")
@patch("core.slideshow_pipeline.run_tts_writer")
@patch("core.slideshow_pipeline.synthesize_scene_speech")
@patch("core.slideshow_pipeline.generate_scene_images")
@patch("core.slideshow_pipeline._get_client")
def test_run_slideshow_pipeline_resumes_scenes_draft(
    mock_get_client: MagicMock,
    mock_images: MagicMock,
    mock_tts: MagicMock,
    mock_tts_writer: MagicMock,
    mock_scene_writer: MagicMock,
    tmp_path: Path,
) -> None:
    from core.slideshow_pipeline import run_slideshow_pipeline

    slides = _sample_slides_with_tts()
    _save_scenes_draft(tmp_path, topic="resume topic", slides=slides)
    mock_tts.return_value = (
        [
            {"scene_id": 2, "start_ms": 0, "end_ms": 1000},
            {"scene_id": 3, "start_ms": 1000, "end_ms": 2000},
            {"scene_id": 4, "start_ms": 2000, "end_ms": 3000},
        ],
        [{"text": "ta", "start_ms": 0, "end_ms": 500}],
        {2: [{"text": "ta", "start_ms": 0, "end_ms": 500}]},
    )
    mock_images.return_value = []

    run_slideshow_pipeline("resume topic", output_dir=tmp_path, caption_mode="none")

    mock_scene_writer.assert_not_called()
    mock_tts_writer.assert_not_called()
    mock_tts.assert_called_once()
    assert (tmp_path / SCENES_DRAFT_FILENAME).is_file()
