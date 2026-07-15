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


def test_inventory_job_assets_lists_all_gaps(tmp_path: Path) -> None:
    from core.job_assets import format_inventory_summary, inventory_job_assets

    root = tmp_path / "assets" / "jobs"
    empty = inventory_job_assets("9", topic="topic", root=root)
    assert empty["script_ok"] is False
    assert empty["complete"] is False
    assert set(empty["missing_images"]) == {
        "intro.png",
        "scene_1.png",
        "scene_2.png",
        "scene_3.png",
        "ending.png",
    }
    assert "script MISSING" in format_inventory_summary(empty)

    assets = _write_complete_assets(root, "9", topic="topic one")
    (assets / "images" / "scene_1.png").unlink()
    (assets / "images" / "ending.png").unlink()
    inv = inventory_job_assets("9", topic="topic one", root=root)
    assert inv["script_ok"] is True
    assert inv["complete"] is False
    assert inv["missing_images"] == ["scene_1.png", "ending.png"]
    assert set(inv["present_images"]) == {"intro.png", "scene_2.png", "scene_3.png"}
    summary = format_inventory_summary(inv)
    assert "script OK" in summary
    assert "scene_1.png" in summary


def test_try_load_reusable_job_assets(tmp_path: Path) -> None:
    from core.job_assets import try_load_job_scenes_draft, try_load_reusable_job_assets

    root = tmp_path / "assets" / "jobs"
    assert try_load_reusable_job_assets("1", topic="topic", root=root) is None

    assets = _write_complete_assets(root, "1", topic="topic one")
    # Partial: remove one image → incomplete for full reuse, but draft still loads
    (assets / "images" / "ending.png").unlink()
    assert try_load_reusable_job_assets("1", topic="topic one", root=root) is None
    assert try_load_job_scenes_draft("1", topic="topic one", root=root) is not None

    (assets / "images" / "ending.png").write_bytes(b"png")
    loaded = try_load_reusable_job_assets("1", topic="topic one", root=root)
    assert loaded is not None
    assert loaded[1]["title"] == "Test title"
    assert try_load_reusable_job_assets("1", topic="other", root=root) is None


@patch("core.slideshow_pipeline.synthesize_scene_speech")
@patch("core.slideshow_pipeline.generate_scene_images")
@patch("core.slideshow_pipeline.run_tts_writer")
@patch("core.slideshow_pipeline.run_scene_script_writer")
@patch("core.slideshow_pipeline.attach_random_ambient_overlay", return_value=None)
@patch("core.slideshow_pipeline.attach_random_music", return_value=None)
def test_pipeline_fills_only_missing_images(
    _mock_music,
    _mock_overlay,
    mock_script,
    mock_tts_writer,
    mock_images,
    mock_speech,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from core.slideshow_pipeline import run_slideshow_pipeline

    root = tmp_path / "assets" / "jobs"
    monkeypatch.setattr("core.job_assets.DEFAULT_JOBS_ASSETS_ROOT", root)
    topic = "topic one"
    assets = _write_complete_assets(root, "3", topic=topic)
    (assets / "images" / "ending.png").unlink()
    (assets / "images" / "scene_2.png").unlink()

    def _fake_images(project: dict, **kwargs) -> list[Path]:
        assert kwargs.get("force") is False
        images_dir = kwargs["images_dir"]
        images_dir.mkdir(parents=True, exist_ok=True)
        generated: list[Path] = []
        for slide in project["slides"]:
            from core.project_schema import slide_image_filename

            path = images_dir / slide_image_filename(slide)
            if path.is_file():
                slide["image"] = {"path": str(path.resolve()), "source": "job_assets"}
                continue
            path.write_bytes(b"new")
            slide["image"] = {"path": str(path.resolve()), "source": "mock"}
            generated.append(path)
        assert {p.name for p in generated} == {"scene_2.png", "ending.png"}
        return generated

    mock_images.side_effect = _fake_images
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

    run_slideshow_pipeline(
        topic,
        output_dir=tmp_path / "out",
        caption_mode="none",
        job_assets_id="3",
        image_provider="mock",
    )

    mock_script.assert_not_called()
    mock_tts_writer.assert_not_called()
    mock_images.assert_called_once()
    assert mock_images.call_args.kwargs["force"] is False
    assert has_complete_job_assets("3", root=root)
    assert (assets / "images" / "intro.png").read_bytes() == b"png"
    assert (assets / "images" / "ending.png").read_bytes() == b"new"


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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from core.slideshow_pipeline import run_slideshow_pipeline

    root = tmp_path / "assets" / "jobs"
    monkeypatch.setattr("core.job_assets.DEFAULT_JOBS_ASSETS_ROOT", root)
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

    payload = run_slideshow_pipeline(
        topic,
        output_dir=tmp_path / "out",
        caption_mode="none",
        job_assets_id="42",
    )

    mock_script.assert_not_called()
    mock_tts.assert_not_called()
    mock_images.assert_not_called()
    assert payload["image_provider"] == "job_assets"
    assert (tmp_path / "out" / "images" / "intro.png").is_file()
    assert payload["publish"]["title"] == "Test title"


def test_execute_job_requires_assets_when_flag_set(tmp_path: Path) -> None:
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


@patch("core.slideshow_pipeline.synthesize_scene_speech")
@patch("core.slideshow_pipeline.generate_scene_images")
@patch("core.slideshow_pipeline.run_tts_writer")
@patch("core.slideshow_pipeline.run_scene_script_writer")
@patch("core.slideshow_pipeline.attach_random_ambient_overlay", return_value=None)
@patch("core.slideshow_pipeline.attach_random_music", return_value=None)
@patch("core.slideshow_pipeline._get_client", return_value=object())
def test_pipeline_persists_job_assets_when_missing(
    _client,
    _mock_music,
    _mock_overlay,
    mock_script,
    mock_tts_writer,
    mock_images,
    mock_speech,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from core.slideshow_pipeline import run_slideshow_pipeline

    root = tmp_path / "assets" / "jobs"
    monkeypatch.setattr("core.job_assets.DEFAULT_JOBS_ASSETS_ROOT", root)

    slides = _sample_slides()
    publish = _sample_publish()
    mock_script.return_value = (slides, publish)
    mock_tts_writer.return_value = [
        {"tts": "Narration for slide 1."},
        {"tts": "Narration for slide 2."},
        {"tts": "Narration for slide 3."},
    ]

    def _fake_images(project: dict, **kwargs) -> list[Path]:
        images_dir = kwargs["images_dir"]
        images_dir.mkdir(parents=True, exist_ok=True)
        paths: list[Path] = []
        for slide in project["slides"]:
            from core.project_schema import slide_image_filename

            path = images_dir / slide_image_filename(slide)
            path.write_bytes(b"png")
            slide["image"] = {"path": str(path.resolve()), "source": "mock"}
            paths.append(path)
        return paths

    mock_images.side_effect = _fake_images
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

    run_slideshow_pipeline(
        "topic one",
        output_dir=tmp_path / "out",
        caption_mode="none",
        job_assets_id="7",
        image_provider="mock",
    )

    mock_script.assert_called_once()
    mock_images.assert_called_once()
    assert has_complete_job_assets("7", root=root)


OLD_IMAGE_BYTES = b"OLD-IMAGE-FROM-PREVIOUS-TOPIC"


@patch("core.slideshow_pipeline.synthesize_scene_speech")
@patch("core.slideshow_pipeline.run_tts_writer")
@patch("core.slideshow_pipeline.run_scene_script_writer")
@patch("core.slideshow_pipeline.attach_random_ambient_overlay", return_value=None)
@patch("core.slideshow_pipeline.attach_random_music", return_value=None)
@patch("core.slideshow_pipeline._get_client", return_value=object())
def test_changed_topic_discards_images_from_the_previous_script(
    _client,
    _music,
    _overlay,
    mock_script,
    mock_tts,
    mock_speech,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Editing a job's topic must not ship the old topic's slide images."""
    from core.job_assets import job_images_dir
    from core.slideshow_pipeline import run_slideshow_pipeline

    root = tmp_path / "assets" / "jobs"
    monkeypatch.setattr("core.job_assets.DEFAULT_JOBS_ASSETS_ROOT", root)
    job_id = "7"

    save_job_scenes_draft(
        job_id, topic="old topic", slides=_sample_slides(), publish=_sample_publish(), root=root
    )
    images = job_images_dir(job_id, root=root)
    images.mkdir(parents=True, exist_ok=True)
    for name in ("intro.png", "scene_1.png", "scene_2.png", "scene_3.png", "ending.png"):
        (images / name).write_bytes(OLD_IMAGE_BYTES)

    mock_script.return_value = (_sample_slides(), _sample_publish())
    mock_tts.return_value = ["Narration 1.", "Narration 2.", "Narration 3."]
    mock_speech.return_value = (
        [
            {"scene_id": 2, "start_ms": 0, "end_ms": 1000},
            {"scene_id": 3, "start_ms": 1000, "end_ms": 2000},
            {"scene_id": 4, "start_ms": 2000, "end_ms": 3000},
        ],
        [{"word": "hi", "start_ms": 0, "end_ms": 3000}],
        {2: [], 3: [], 4: []},
    )

    payload = run_slideshow_pipeline(
        "new topic",
        output_dir=tmp_path / "out",
        caption_mode="none",
        image_provider="mock",
        job_assets_id=job_id,
    )

    shipped = [Path(image["path"]).read_bytes() for image in payload["video"]["images"]]
    assert shipped and OLD_IMAGE_BYTES not in shipped
    assert (job_images_dir(job_id, root=root) / "intro.png").read_bytes() != OLD_IMAGE_BYTES
