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
    job_created_date_vn,
    load_jobs,
    process_pending_jobs,
    reset_stale_running,
    save_jobs,
    select_jobs,
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


@patch("orchestrator_mvp.run_slideshow_with_render")
def test_execute_job_slideshow_disables_inline_publish(mock_run, tmp_path: Path) -> None:
    from core.batch_runner import execute_job

    final = tmp_path / "final" / "final.mp4"
    mock_run.return_value = ({}, final)
    row = {
        "id": "1",
        "topic": "topic one",
        "status": "pending",
        "mode": "slideshow",
        "image_provider": "mock",
    }

    result = execute_job(row, output_dir=tmp_path / "final", require_job_assets=False)

    assert result == final
    mock_run.assert_called_once()
    assert mock_run.call_args.kwargs["publish"] is False
    assert mock_run.call_args.kwargs["job_assets_id"] == "1"
    assert mock_run.call_args.kwargs["require_job_assets"] is False


@patch("orchestrator_mvp.run_mvp_with_render")
def test_execute_job_mvp_disables_inline_publish(mock_run, tmp_path: Path) -> None:
    from core.batch_runner import execute_job

    final = tmp_path / "final" / "final.mp4"
    mock_run.return_value = ({}, final)
    row = {
        "id": "1",
        "topic": "topic one",
        "status": "pending",
        "mode": "mvp",
        "image_provider": "",
    }

    result = execute_job(row, output_dir=tmp_path / "final")

    assert result == final
    mock_run.assert_called_once()
    assert mock_run.call_args.kwargs["publish"] is False


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

    results = process_pending_jobs(
        csv_path, max_jobs=1, output_dir=tmp_path / "final", require_job_assets=False
    )
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

    results = process_pending_jobs(
        csv_path, output_dir=tmp_path / "final", require_job_assets=False
    )
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


def test_job_created_date_vn_parses_offset() -> None:
    from datetime import date

    assert job_created_date_vn("2026-07-10T03:30:00+07:00") == date(2026, 7, 10)
    assert job_created_date_vn("2026-07-09T20:00:00+00:00") == date(2026, 7, 10)  # UTC → VN next day
    assert job_created_date_vn("") is None
    assert job_created_date_vn("not-a-date") is None


def test_select_jobs_due_today() -> None:
    from datetime import date

    rows = [
        {
            "id": "1",
            "topic": "today",
            "status": "pending",
            "created_at": "2026-07-10T00:00:00+07:00",
        },
        {
            "id": "2",
            "topic": "tomorrow",
            "status": "pending",
            "created_at": "2026-07-11T00:00:00+07:00",
        },
        {
            "id": "3",
            "topic": "today done",
            "status": "done",
            "created_at": "2026-07-10T12:00:00+07:00",
        },
        {
            "id": "4",
            "topic": "no date",
            "status": "pending",
            "created_at": "",
        },
    ]
    matched = select_jobs(rows, select="due-today", today=date(2026, 7, 10))
    assert [r["id"] for r in matched] == ["1"]


def test_select_jobs_failed() -> None:
    rows = [
        {"id": "1", "status": "failed", "created_at": "2026-07-01T00:00:00+07:00"},
        {"id": "2", "status": "pending", "created_at": "2026-07-10T00:00:00+07:00"},
        {"id": "3", "status": "failed", "created_at": "2026-07-09T00:00:00+07:00"},
    ]
    matched = select_jobs(rows, select="failed")
    assert [r["id"] for r in matched] == ["1", "3"]


@patch("core.batch_runner.execute_job")
def test_process_due_today_all_matched(mock_execute, tmp_path: Path) -> None:
    from datetime import date

    out = tmp_path / "output" / "final.mp4"
    (tmp_path / "output").mkdir()
    out.write_bytes(b"mp4")
    mock_execute.return_value = out

    csv_path = tmp_path / "jobs.csv"
    save_jobs(
        csv_path,
        [
            {
                "id": "1",
                "topic": "a",
                "status": "pending",
                "mode": "slideshow",
                "image_provider": "mock",
                "output_path": "",
                "error": "",
                "created_at": "2026-07-10T01:00:00+07:00",
                "completed_at": "",
            },
            {
                "id": "2",
                "topic": "b",
                "status": "pending",
                "mode": "slideshow",
                "image_provider": "mock",
                "output_path": "",
                "error": "",
                "created_at": "2026-07-10T02:00:00+07:00",
                "completed_at": "",
            },
            {
                "id": "3",
                "topic": "c",
                "status": "pending",
                "mode": "slideshow",
                "image_provider": "mock",
                "output_path": "",
                "error": "",
                "created_at": "2026-07-11T00:00:00+07:00",
                "completed_at": "",
            },
        ],
    )

    results = process_pending_jobs(
        csv_path,
        max_jobs=0,
        select="due-today",
        today=date(2026, 7, 10),
        output_dir=tmp_path / "final",
        require_job_assets=False,
    )
    assert len(results) == 2
    assert all(r["status"] == "done" for r in results)
    rows = load_jobs(csv_path)
    by_id = {r["id"]: r for r in rows}
    assert by_id["1"]["status"] == "done"
    assert by_id["2"]["status"] == "done"
    assert by_id["3"]["status"] == "pending"


@patch("core.batch_runner.execute_job")
def test_process_failed_retries_all(mock_execute, tmp_path: Path) -> None:
    out = tmp_path / "output" / "final.mp4"
    (tmp_path / "output").mkdir()
    out.write_bytes(b"mp4")
    mock_execute.return_value = out

    csv_path = tmp_path / "jobs.csv"
    save_jobs(
        csv_path,
        [
            {
                "id": "1",
                "topic": "fail a",
                "status": "failed",
                "mode": "slideshow",
                "image_provider": "mock",
                "output_path": "",
                "error": "boom",
                "created_at": "2026-07-08T00:00:00+07:00",
                "completed_at": "2026-07-08T01:00:00+07:00",
            },
            {
                "id": "2",
                "topic": "ok",
                "status": "pending",
                "mode": "slideshow",
                "image_provider": "mock",
                "output_path": "",
                "error": "",
                "created_at": "2026-07-10T00:00:00+07:00",
                "completed_at": "",
            },
            {
                "id": "3",
                "topic": "fail b",
                "status": "failed",
                "mode": "slideshow",
                "image_provider": "mock",
                "output_path": "",
                "error": "boom2",
                "created_at": "2026-07-09T00:00:00+07:00",
                "completed_at": "2026-07-09T01:00:00+07:00",
            },
        ],
    )

    results = process_pending_jobs(
        csv_path,
        max_jobs=0,
        select="failed",
        output_dir=tmp_path / "final",
        require_job_assets=False,
    )
    assert len(results) == 2
    assert {r["id"] for r in results} == {"1", "3"}
    rows = load_jobs(csv_path)
    by_id = {r["id"]: r for r in rows}
    assert by_id["1"]["status"] == "done"
    assert by_id["1"]["error"] == ""
    assert by_id["2"]["status"] == "pending"
    assert by_id["3"]["status"] == "done"


@patch("core.publish_runner.publish_video", return_value=True)
@patch("core.batch_runner.execute_job")
def test_process_publish_per_job(mock_execute, mock_publish, tmp_path: Path) -> None:
    out = tmp_path / "output" / "final.mp4"
    (tmp_path / "output").mkdir()
    out.write_bytes(b"mp4")
    mock_execute.return_value = out

    csv_path = tmp_path / "jobs.csv"
    save_jobs(
        csv_path,
        [
            {
                "id": "1",
                "topic": "a",
                "status": "pending",
                "mode": "slideshow",
                "image_provider": "mock",
                "output_path": "",
                "error": "",
                "created_at": "2026-07-10T00:00:00+07:00",
                "completed_at": "",
            },
            {
                "id": "2",
                "topic": "b",
                "status": "pending",
                "mode": "slideshow",
                "image_provider": "mock",
                "output_path": "",
                "error": "",
                "created_at": "2026-07-10T00:00:00+07:00",
                "completed_at": "",
            },
        ],
    )

    results = process_pending_jobs(
        csv_path,
        max_jobs=0,
        select="pending",
        publish=True,
        output_dir=tmp_path / "final",
        require_job_assets=False,
    )
    assert len(results) == 2
    assert all(r.get("publish") == "ok" for r in results)
    assert mock_publish.call_count == 2
