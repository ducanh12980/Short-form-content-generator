"""Tests for b-roll retrieval stage (mocked Pexels — no live API)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.broll_retrieval_stage import _build_image_timeline, retrieve_broll


def _sample_payload(tmp_path: Path) -> Path:
    payload = {
        "topic": "drinking water health tips",
        "raw_script": "Stay hydrated every day.",
        "tokens": [{"text": "Stay", "style": "primary", "animation": "none"}],
        "audio": {
            "path": str(tmp_path / "narration.mp3"),
            "word_timestamps": [
                {"text": "Stay", "start_ms": 0, "end_ms": 500},
                {"text": "hydrated", "start_ms": 500, "end_ms": 1200},
            ],
        },
    }
    path = tmp_path / "pipeline_payload.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_build_image_timeline_spans_narration() -> None:
    images = [Path("a.jpg"), Path("b.jpg")]
    timeline = _build_image_timeline(images, duration_ms=3000)

    assert len(timeline) == 2
    assert timeline[0]["start_ms"] == 0
    assert timeline[0]["end_ms"] == 1500
    assert timeline[1]["start_ms"] == 1500
    assert timeline[1]["end_ms"] == 3000
    assert timeline[0]["source"] == "pexels"
    assert timeline[0]["media_type"] == "image"


@patch("core.broll_retrieval_stage.download_images_for_keywords")
@patch.dict("os.environ", {"PEXELS_API_KEY": "test-key"})
def test_retrieve_broll_updates_project_images(
    mock_download: MagicMock,
    tmp_path: Path,
) -> None:
    project_path = _sample_payload(tmp_path)
    image_a = tmp_path / "images" / "water_1.jpg"
    image_b = tmp_path / "images" / "health_2.jpg"
    image_a.parent.mkdir(parents=True)
    image_a.write_bytes(b"a")
    image_b.write_bytes(b"b")
    mock_download.return_value = [image_a, image_b]

    result = retrieve_broll(project_path, max_images=2)

    assert result == [image_a, image_b]
    updated = json.loads(project_path.read_text(encoding="utf-8"))
    images = updated["video"]["images"]
    assert len(images) == 2
    assert images[0]["path"] == str(image_a.resolve())
    assert images[1]["end_ms"] == 1200
    assert updated["video"]["clips"] == []


@patch("core.broll_retrieval_stage.download_images_for_keywords")
@patch.dict("os.environ", {"PEXELS_API_KEY": "test-key"})
def test_retrieve_broll_skips_when_images_exist(
    mock_download: MagicMock,
    tmp_path: Path,
) -> None:
    project_path = _sample_payload(tmp_path)
    existing_image = tmp_path / "existing.jpg"
    existing_image.write_bytes(b"x")
    payload = json.loads(project_path.read_text(encoding="utf-8"))
    payload["video"] = {
        "canvas": {"width": 1080, "height": 1920},
        "images": [
            {
                "path": str(existing_image),
                "start_ms": 0,
                "end_ms": 1000,
                "source": "pexels",
                "media_type": "image",
            }
        ],
        "clips": [],
    }
    project_path.write_text(json.dumps(payload), encoding="utf-8")

    result = retrieve_broll(project_path)

    assert result == [existing_image]
    mock_download.assert_not_called()


@patch.dict("os.environ", {}, clear=True)
def test_retrieve_broll_requires_pexels_key(tmp_path: Path) -> None:
    project_path = _sample_payload(tmp_path)
    with pytest.raises(RuntimeError, match="PEXELS_API_KEY"):
        retrieve_broll(project_path)
