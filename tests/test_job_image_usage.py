"""Tests for per-image token usage reporting (assets/jobs/<id>/usage.json)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.job_assets import (
    format_usage_summary,
    job_usage_path,
    load_job_image_usage,
    save_job_image_usage,
    summarize_image_usage,
)
from core.slide_image_stage import generate_scene_images
from scripts.pregenerate_job_assets import format_run_usage_report


def _record(image: str, *, in_tokens: int, out_tokens: int, **extra) -> dict:
    return {
        "image": image,
        "provider": "chatgpt",
        "input_tokens": in_tokens,
        "output_tokens": out_tokens,
        "total_tokens": in_tokens + out_tokens,
        **extra,
    }


def test_summarize_image_usage_sums_token_fields() -> None:
    totals = summarize_image_usage(
        [_record("intro.png", in_tokens=100, out_tokens=4000),
         _record("ending.png", in_tokens=120, out_tokens=4160)]
    )
    assert totals == {
        "images": 2,
        "input_tokens": 220,
        "output_tokens": 8160,
        "total_tokens": 8380,
    }


def test_summarize_omits_fields_the_api_did_not_report() -> None:
    """Pollinations and mock cost no tokens — the report must not invent zeros."""
    totals = summarize_image_usage([{"image": "intro.png", "provider": "pollinations"}])
    assert totals == {"images": 1}
    assert format_usage_summary(totals) == "1 image(s) — tokens unavailable"


def test_format_usage_summary_shows_cached() -> None:
    summary = format_usage_summary(
        {"images": 5, "input_tokens": 500, "cached_tokens": 120, "output_tokens": 20800}
    )
    assert summary == "5 image(s) — in=500 (cached=120), out=20800"


def test_save_job_image_usage_writes_totals_in_slide_order(tmp_path: Path) -> None:
    save_job_image_usage(
        "7",
        topic="chủ đề",
        records=[
            _record("ending.png", in_tokens=120, out_tokens=4160),
            _record("intro.png", in_tokens=100, out_tokens=4000),
        ],
        root=tmp_path,
    )

    data = json.loads(job_usage_path("7", root=tmp_path).read_text(encoding="utf-8"))
    assert data["topic"] == "chủ đề"
    assert [r["image"] for r in data["images"]] == ["intro.png", "ending.png"]
    assert data["totals"]["total_tokens"] == 8380
    assert data["totals"]["images"] == 2


def test_gap_fill_replaces_only_the_regenerated_image(tmp_path: Path) -> None:
    """A run that regenerates one PNG must keep what the other images cost."""
    save_job_image_usage(
        "7",
        topic="t",
        records=[
            _record("intro.png", in_tokens=100, out_tokens=4000),
            _record("scene_1.png", in_tokens=110, out_tokens=4100),
        ],
        root=tmp_path,
    )
    save_job_image_usage(
        "7",
        topic="t",
        records=[_record("scene_1.png", in_tokens=999, out_tokens=5000)],
        root=tmp_path,
    )

    data = load_job_image_usage("7", root=tmp_path)
    by_name = {r["image"]: r for r in data["images"]}
    assert by_name["intro.png"]["input_tokens"] == 100
    assert by_name["scene_1.png"]["input_tokens"] == 999
    assert data["totals"]["input_tokens"] == 1099


def test_load_job_image_usage_missing_or_corrupt_is_empty(tmp_path: Path) -> None:
    assert load_job_image_usage("99", root=tmp_path) == {}

    path = job_usage_path("99", root=tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text("{not json", encoding="utf-8")
    assert load_job_image_usage("99", root=tmp_path) == {}


def _openai_image_response(*, input_tokens: int, output_tokens: int, cached: int) -> MagicMock:
    return MagicMock(
        status_code=200,
        json=lambda: {
            "data": [{"b64_json": "aGVsbG8="}],
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
                "input_tokens_details": {"cached_tokens": cached},
            },
            "quality": "low",
        },
    )


@patch("core.slide_image_stage.requests.post")
@patch.dict(
    os.environ,
    {
        "OPENAI_IMAGE_API_KEY": "test-key",
        "OPENAI_IMAGE_MODEL": "gpt-image-2",
        "OPENAI_IMAGE_QUALITY": "low",
        "OPENAI_IMAGE_SIZE": "896x1600",
        "OPENAI_IMAGE_PROMPT_MODE": "compact",
    },
    clear=False,
)
def test_api_token_usage_reaches_usage_json(mock_post: MagicMock, tmp_path: Path) -> None:
    """End to end: what gpt-image-2 reports must land in the stored report."""
    mock_post.return_value = _openai_image_response(
        input_tokens=512, output_tokens=1280, cached=400
    )
    project = {
        "topic": "tướng số",
        "slides": [
            {"id": 1, "role": "intro", "title": "Hook", "visual_concept": "a face"},
            {
                "id": 2,
                "role": "content",
                "content_index": 1,
                "title": "Nét tướng",
                "description": "mô tả",
            },
        ],
    }

    usage: list[dict] = []
    generate_scene_images(
        project,
        images_dir=tmp_path / "images",
        provider="chatgpt",
        force=True,
        usage_out=usage,
    )
    save_job_image_usage("7", topic="tướng số", records=usage, root=tmp_path)

    data = json.loads(job_usage_path("7", root=tmp_path).read_text(encoding="utf-8"))
    intro = next(r for r in data["images"] if r["image"] == "intro.png")
    assert intro["input_tokens"] == 512
    assert intro["output_tokens"] == 1280
    assert intro["cached_tokens"] == 400
    assert intro["model"] == "gpt-image-2"
    assert intro["quality"] == "low"
    assert intro["role"] == "intro"
    assert data["totals"] == {
        "images": 2,
        "input_tokens": 1024,
        "cached_tokens": 800,
        "output_tokens": 2560,
        "total_tokens": 3584,
    }


def test_cached_images_are_not_recorded_as_free(tmp_path: Path) -> None:
    """A cached PNG makes no API call, so it must not overwrite its stored tokens."""
    images_dir = tmp_path / "images"
    images_dir.mkdir()
    (images_dir / "intro.png").write_bytes(b"already here")

    project = {
        "topic": "t",
        "slides": [{"id": 1, "role": "intro", "title": "Hook", "visual_concept": "x"}],
    }
    usage: list[dict] = []
    generate_scene_images(
        project, images_dir=images_dir, provider="chatgpt", force=False, usage_out=usage
    )
    assert usage == []


def test_run_report_groups_by_job_and_totals() -> None:
    report = format_run_usage_report(
        [
            _record("intro.png", in_tokens=100, out_tokens=4000, job_id="1"),
            _record("ending.png", in_tokens=120, out_tokens=4160, job_id="1"),
            _record("intro.png", in_tokens=130, out_tokens=4200, job_id="2"),
        ]
    )
    assert "Job 1: 2 image(s) — in=220, out=8160, total=8380" in report
    assert "Job 2: 1 image(s) — in=130, out=4200, total=4330" in report
    assert "• intro.png: in=100, out=4000, total=4100" in report
    assert "Tổng: 3 image(s) — in=350, out=12360, total=12710" in report
