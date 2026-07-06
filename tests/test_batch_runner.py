"""Tests for CSV batch runner (mocked pipeline — no live API)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from core.batch_runner import (
    BatchLockError,
    batch_lock,
    collect_slideshow_image_paths,
    init_jobs_csv,
    load_jobs,
    process_pending_jobs,
    reset_stale_running,
    save_jobs,
)


def test_init_and_roundtrip_csv(tmp_path: Path) -> None:
    csv_path = tmp_path / "jobs.csv"
    init_jobs_csv(csv_path)
    rows = load_jobs(csv_path)
    assert len(rows) == 2
    assert rows[0]["status"] == "pending"
    assert rows[0]["mode"] == "slideshow"


def test_save_jobs_atomic(tmp_path: Path) -> None:
    csv_path = tmp_path / "jobs.csv"
    rows = [
        {
            "id": "9",
            "topic": "test topic",
            "status": "pending",
            "mode": "slideshow",
            "image_provider": "mock",
            "output_path": "",
            "error": "",
            "created_at": "",
            "completed_at": "",
        }
    ]
    save_jobs(csv_path, rows)
    loaded = load_jobs(csv_path)
    assert loaded[0]["topic"] == "test topic"


def test_reset_stale_running() -> None:
    rows = [{"status": "running"}, {"status": "done"}, {"status": "pending"}]
    assert reset_stale_running(rows) == 1
    assert rows[0]["status"] == "pending"
    assert rows[1]["status"] == "done"


def test_collect_slideshow_image_paths_from_scenes() -> None:
    payload = {
        "scenes": [
            {"id": 2, "image": {"path": "/b.png"}},
            {"id": 1, "image": {"path": "/a.png"}},
        ]
    }
    paths = collect_slideshow_image_paths(payload)
    assert [p.name for p in paths] == ["a.png", "b.png"]


def test_collect_slideshow_image_paths_missing_raises() -> None:
    with pytest.raises(ValueError, match="No slide images"):
        collect_slideshow_image_paths({"scenes": []})


def test_batch_lock_exclusive(tmp_path: Path) -> None:
    lock_path = tmp_path / "jobs.csv.lock"
    with batch_lock(lock_path):
        with pytest.raises(BatchLockError):
            with batch_lock(lock_path):
                pass


@patch("core.batch_runner.execute_job")
def test_process_pending_jobs_updates_csv(mock_execute, tmp_path: Path) -> None:
    mock_execute.return_value = tmp_path / "output" / "final.mp4"
    (tmp_path / "output").mkdir()
    (tmp_path / "output" / "final.mp4").write_bytes(b"mp4")

    csv_path = tmp_path / "jobs.csv"
    init_jobs_csv(csv_path, examples=False)
    save_jobs(
        csv_path,
        [
            {
                "id": "1",
                "topic": "topic one",
                "status": "pending",
                "mode": "slideshow",
                "image_provider": "mock",
                "output_path": "",
                "error": "",
                "created_at": "",
                "completed_at": "",
            },
            {
                "id": "2",
                "topic": "topic two",
                "status": "pending",
                "mode": "slideshow",
                "image_provider": "mock",
                "output_path": "",
                "error": "",
                "created_at": "",
                "completed_at": "",
            },
        ],
    )

    results = process_pending_jobs(csv_path, max_jobs=1, output_base=tmp_path / "batch")
    assert len(results) == 1
    assert results[0]["status"] == "done"

    rows = load_jobs(csv_path)
    by_id = {row["id"]: row for row in rows}
    assert by_id["1"]["status"] == "done"
    assert by_id["1"]["output_path"]
    assert by_id["2"]["status"] == "pending"


@patch("core.batch_runner.execute_job", side_effect=RuntimeError("boom"))
def test_process_pending_jobs_marks_failed(mock_execute, tmp_path: Path) -> None:
    csv_path = tmp_path / "jobs.csv"
    save_jobs(
        csv_path,
        [
            {
                "id": "1",
                "topic": "fail topic",
                "status": "pending",
                "mode": "slideshow",
                "image_provider": "mock",
                "output_path": "",
                "error": "",
                "created_at": "",
                "completed_at": "",
            },
        ],
    )

    results = process_pending_jobs(csv_path, output_base=tmp_path / "batch")
    assert results[0]["status"] == "failed"
    rows = load_jobs(csv_path)
    assert rows[0]["status"] == "failed"
    assert "boom" in rows[0]["error"]


def test_process_pending_skips_done(tmp_path: Path) -> None:
    csv_path = tmp_path / "jobs.csv"
    save_jobs(
        csv_path,
        [
            {
                "id": "1",
                "topic": "done topic",
                "status": "done",
                "mode": "slideshow",
                "image_provider": "mock",
                "output_path": "/x/final.mp4",
                "error": "",
                "created_at": "",
                "completed_at": "2026-01-01T00:00:00+00:00",
            },
        ],
    )
    results = process_pending_jobs(csv_path)
    assert results == []
