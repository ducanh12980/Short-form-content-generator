"""Tests for per-job asset library under assets/jobs/<id>/."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from core.job_assets import (
    JobAssetsError,
    copy_job_images_into,
    has_complete_job_assets,
    job_assets_dir,
    load_job_scenes_draft,
    missing_job_asset_paths,
    require_complete_job_assets,
    save_job_scenes_draft,
)
from core.project_schema import TOTAL_SLIDE_COUNT


def _sample_slides() -> list[dict]:
    slides = [
        {
            "id": 1,
            "role": "intro",
            "title": "Intro",
            "visual_concept": "face close-up",
            "description": "",
        },
    ]
    for i in range(1, 4):
        slides.append(
            {
                "id": i + 1,
                "role": "content",
                "content_index": i,
                "title": f"Title {i}",
                "description": f"Desc {i}",
                "visual_concept": f"visual {i}",
                "tts": f"Narration for slide {i}.",
            }
        )
    slides.append(
        {
            "id": 5,
            "role": "ending",
            "title": "Ending",
            "visual_concept": "outro",
            "description": "",
        }
    )
    assert len(slides) == TOTAL_SLIDE_COUNT
    return slides


def _sample_publish() -> dict:
    return {
        "title": "Test title",
        "description": "Test description",
        "hashtags": ["#a", "#b", "#c"],
    }


def _write_complete_assets(root: Path, job_id: str, topic: str = "topic one") -> Path:
    save_job_scenes_draft(
        job_id,
        topic=topic,
        slides=_sample_slides(),
        publish=_sample_publish(),
        root=root,
    )
    images = job_assets_dir(job_id, root=root) / "images"
    images.mkdir(parents=True, exist_ok=True)
    for name in ("intro.png", "scene_1.png", "scene_2.png", "scene_3.png", "ending.png"):
        (images / name).write_bytes(b"png")
    return job_assets_dir(job_id, root=root)


def test_has_complete_job_assets(tmp_path: Path) -> None:
    root = tmp_path / "assets" / "jobs"
    assert not has_complete_job_assets("1", root=root)
    _write_complete_assets(root, "1")
    assert has_complete_job_assets("1", root=root)
    assert missing_job_asset_paths("1", root=root) == []


def test_require_complete_job_assets_raises(tmp_path: Path) -> None:
    root = tmp_path / "assets" / "jobs"
    with pytest.raises(JobAssetsError, match="Missing job assets"):
        require_complete_job_assets("9", root=root)


def test_load_job_scenes_draft_topic_mismatch(tmp_path: Path) -> None:
    root = tmp_path / "assets" / "jobs"
    _write_complete_assets(root, "1", topic="expected topic")
    with pytest.raises(JobAssetsError, match="topic mismatch"):
        load_job_scenes_draft("1", topic="other topic", root=root)


def test_load_job_scenes_draft_ok(tmp_path: Path) -> None:
    root = tmp_path / "assets" / "jobs"
    _write_complete_assets(root, "1", topic="topic one")
    slides, publish = load_job_scenes_draft("1", topic="topic one", root=root)
    assert len(slides) == TOTAL_SLIDE_COUNT
    assert publish["title"] == "Test title"


def test_copy_job_images_into(tmp_path: Path) -> None:
    root = tmp_path / "assets" / "jobs"
    _write_complete_assets(root, "1")
    run_dir = tmp_path / "run"
    slides = _sample_slides()
    copied = copy_job_images_into(run_dir, "1", root=root, slides=slides)
    assert len(copied) == 5
    assert (run_dir / "images" / "intro.png").is_file()
    assert slides[0]["image"]["path"].endswith("intro.png")
    assert slides[0]["image"]["source"] == "job_assets"


@patch("core.slideshow_pipeline.synthesize_scene_speech")
@patch("core.slideshow_pipeline.generate_scene_images")
@patch("core.slideshow_pipeline.run_tts_writer")
@patch("core.slideshow_pipeline.run_scene_script_writer")
@patch("core.slideshow_pipeline.attach_random_ambient_overlay", return_value=None)
@patch("core.slideshow_pipeline.attach_random_music", return_value=None)
def test_pipeline_reuses_job_assets(
    _mock_music,
    _mock_overlay,
    mock_script,
    mock_tts,
    mock_images,
    mock_speech,
    tmp_path: Path,
) -> None:
    from core.slideshow_pipeline import run_slideshow_pipeline

    root = tmp_path / "assets" / "jobs"
    topic = "topic one"
    _write_complete_assets(root, "42", topic=topic)

    mock_speech.return_value = (
        [
            {"scene_id": 2, "start_ms": 0, "end_ms": 1000},
            {"scene_id": 3, "start_ms": 1000, "end_ms": 2000},
            {"scene_id": 4, "start_ms": 2000, "end_ms": 3000},
        ],
        [{"word": "hi", "start_ms": 0, "end_ms": 500}],
        {
            2: [{"word": "hi", "start_ms": 0, "end_ms": 500}],
            3: [{"word": "hi", "start_ms": 1000, "end_ms": 1500}],
            4: [{"word": "hi", "start_ms": 2000, "end_ms": 2500}],
        },
    )

    with (
        patch("core.job_assets.has_complete_job_assets", return_value=True),
        patch("core.job_assets.require_complete_job_assets", return_value=root / "42"),
        patch(
            "core.job_assets.load_job_scenes_draft",
            return_value=load_job_scenes_draft("42", topic=topic, root=root),
        ),
        patch(
            "core.job_assets.copy_job_images_into",
            side_effect=lambda out, job_id, slides=None, **kw: copy_job_images_into(
                out, job_id, root=root, slides=slides
            ),
        ),
    ):
        payload = run_slideshow_pipeline(
            topic,
            output_dir=tmp_path / "out",
            caption_mode="none",
            job_assets_id="42",
            require_job_assets=True,
        )

    mock_script.assert_not_called()
    mock_tts.assert_not_called()
    mock_images.assert_not_called()
    assert payload["image_provider"] == "job_assets"
    assert (tmp_path / "out" / "images" / "intro.png").is_file()
    assert payload["publish"]["title"] == "Test title"


def test_execute_job_requires_assets(tmp_path: Path) -> None:
    from core.batch_runner import execute_job

    row = {
        "id": "missing",
        "topic": "topic",
        "status": "pending",
        "mode": "slideshow",
        "image_provider": "mock",
    }
    with pytest.raises(JobAssetsError, match="Missing job assets"):
        execute_job(row, output_dir=tmp_path / "final", require_job_assets=True)
