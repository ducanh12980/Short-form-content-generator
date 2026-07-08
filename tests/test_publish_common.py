"""Tests for shared publish helpers."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.batch_runner import init_jobs_csv, save_jobs
from core.publish.common import (
    PublishError,
    assert_video_exists,
    find_latest_done_job,
    format_job_caption,
    load_publish_from_payload,
    resolve_publish_metadata,
)


def test_format_job_caption_truncates_long_topic() -> None:
    topic = "x" * 2000
    caption = format_job_caption(job_id="42", topic=topic, max_len=100)
    assert len(caption) <= 100
    assert caption.endswith("…")


def test_load_publish_from_payload(tmp_path: Path) -> None:
    payload_path = tmp_path / "pipeline_payload.json"
    payload_path.write_text(
        json.dumps(
            {
                "publish": {
                    "title": "T",
                    "description": "D",
                    "hashtags": ["#x"],
                }
            }
        ),
        encoding="utf-8",
    )
    publish = load_publish_from_payload(payload_path)
    assert publish is not None
    assert publish["title"] == "T"


def test_resolve_publish_metadata_uses_video_parent(tmp_path: Path) -> None:
    video = tmp_path / "final.mp4"
    video.write_bytes(b"mp4")
    payload_path = tmp_path / "pipeline_payload.json"
    payload_path.write_text(
        json.dumps(
            {
                "publish": {
                    "title": "From payload",
                    "description": "Desc",
                    "hashtags": ["#one"],
                }
            }
        ),
        encoding="utf-8",
    )

    publish = resolve_publish_metadata(video)
    assert publish is not None
    assert publish["title"] == "From payload"


def test_assert_video_exists_rejects_missing(tmp_path: Path) -> None:
    with pytest.raises(PublishError, match="not found"):
        assert_video_exists(tmp_path / "missing.mp4")


def test_assert_video_exists_rejects_empty(tmp_path: Path) -> None:
    video = tmp_path / "empty.mp4"
    video.write_bytes(b"")
    with pytest.raises(PublishError, match="empty"):
        assert_video_exists(video)


def test_find_latest_done_job(tmp_path: Path) -> None:
    csv_path = tmp_path / "jobs.csv"
    init_jobs_csv(csv_path, examples=False)
    rows = [
        {
            "id": "1",
            "topic": "older",
            "status": "done",
            "mode": "slideshow",
            "image_provider": "mock",
            "output_path": "a.mp4",
            "error": "",
            "created_at": "2026-01-01T00:00:00+00:00",
            "completed_at": "2026-01-01T01:00:00+00:00",
        },
        {
            "id": "2",
            "topic": "newer",
            "status": "done",
            "mode": "slideshow",
            "image_provider": "mock",
            "output_path": "b.mp4",
            "error": "",
            "created_at": "2026-01-02T00:00:00+00:00",
            "completed_at": "2026-01-02T01:00:00+00:00",
        },
    ]
    save_jobs(csv_path, rows)
    latest = find_latest_done_job(csv_path)
    assert latest is not None
    assert latest["id"] == "2"


@patch("core.publish.common.subprocess.run")
@patch("core.publish.common.shutil.which")
def test_probe_video_metadata_parses_ffprobe(
    mock_which: MagicMock,
    mock_run: MagicMock,
    tmp_path: Path,
) -> None:
    from core.publish.common import probe_video_metadata

    mock_which.return_value = "ffprobe"
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps(
            {
                "streams": [{"width": 1080, "height": 1920}],
                "format": {"duration": "45.6"},
            }
        ),
    )
    video = tmp_path / "final.mp4"
    video.write_bytes(b"mp4")

    metadata = probe_video_metadata(video)
    assert metadata is not None
    assert metadata.width == 1080
    assert metadata.height == 1920
    assert metadata.duration_sec == 46
