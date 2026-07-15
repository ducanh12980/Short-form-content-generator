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

    result = execute_job(row, output_dir=tmp_path / "final")

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


@patch("orchestrator_mvp.run_slideshow_with_render")
def test_execute_job_resets_run_dir_between_jobs(mock_run, tmp_path: Path) -> None:
    """Leftover scenes_draft/images from a prior CSV row must not leak into the next job."""
    from core.batch_runner import execute_job

    run_dir = tmp_path / "final"
    run_dir.mkdir()
    stale = run_dir / "scenes_draft.json"
    stale.write_text('{"topic":"old"}', encoding="utf-8")
    (run_dir / "images").mkdir()
    (run_dir / "images" / "intro.png").write_bytes(b"old")

    final = run_dir / "final.mp4"
    mock_run.return_value = ({}, final)
    row = {
        "id": "2",
        "topic": "new topic",
        "status": "pending",
        "mode": "slideshow",
        "image_provider": "mock",
    }

    execute_job(row, output_dir=run_dir)

    assert not stale.exists()
    assert not (run_dir / "images" / "intro.png").exists()
    assert mock_run.call_args.kwargs["job_assets_id"] == "2"


def test_is_quota_exhausted_error() -> None:
    from core.batch_runner import is_quota_exhausted_error

    assert is_quota_exhausted_error(
        RuntimeError("Gemini daily quota exceeded for this API key/model")
    )
    assert is_quota_exhausted_error(RuntimeError("Error 429 RESOURCE_EXHAUSTED"))
    assert not is_quota_exhausted_error(RuntimeError("network timeout"))


@patch("core.batch_runner.execute_job")
def test_process_pending_jobs_stops_on_quota(mock_execute, tmp_path: Path) -> None:
    mock_execute.side_effect = RuntimeError(
        "Scene script writer failed: Gemini daily quota exceeded for this API key/model."
    )

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
        csv_path, max_jobs=0, output_dir=tmp_path / "final", require_job_assets=False
    )

    assert len(results) == 1
    assert results[0]["status"] == "failed"
    assert mock_execute.call_count == 1
    rows = load_jobs(csv_path)
    assert rows[0]["status"] == "failed"
    assert rows[1]["status"] == "pending"


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


def test_select_pending_from_today() -> None:
    from datetime import date

    from core.batch_runner import select_pending_from_today

    rows = [
        {
            "id": "past",
            "topic": "past",
            "status": "pending",
            "created_at": "2026-07-09T00:00:00+07:00",
        },
        {
            "id": "today",
            "topic": "today",
            "status": "pending",
            "created_at": "2026-07-10T03:30:00+07:00",
        },
        {
            "id": "future",
            "topic": "future",
            "status": "pending",
            "created_at": "2026-07-15T00:00:00+07:00",
        },
        {
            "id": "done",
            "topic": "done",
            "status": "done",
            "created_at": "2026-07-20T00:00:00+07:00",
        },
    ]
    matched = select_pending_from_today(rows, today=date(2026, 7, 10))
    assert [r["id"] for r in matched] == ["today", "future"]


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


@patch("core.publish_runner.publish_video_report", return_value={"telegram": True})
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
    assert all(row["publish_status"] == "ok" for row in load_jobs(csv_path))


def _done_row(job_id: str, publish_status: str) -> dict[str, str]:
    return {
        "id": job_id,
        "topic": f"topic {job_id}",
        "status": "done",
        "mode": "slideshow",
        "image_provider": "mock",
        "output_path": "",
        "error": "",
        "created_at": "2026-07-10T00:00:00+07:00",
        "completed_at": "2026-07-10T01:00:00+07:00",
        "publish_status": publish_status,
    }


def test_format_and_parse_publish_status_round_trip() -> None:
    from core.batch_runner import format_publish_status, parse_failed_publish_platforms

    assert format_publish_status([]) == "ok"
    assert format_publish_status(["telegram", "drive"]) == "failed:drive,telegram"
    assert parse_failed_publish_platforms("failed:drive,telegram") == ["drive", "telegram"]
    assert parse_failed_publish_platforms("ok") == []
    assert parse_failed_publish_platforms("") == []


def test_select_publish_failed_picks_only_done_rows_with_failed_platforms() -> None:
    from core.batch_runner import select_jobs

    rows = [
        _done_row("1", "ok"),
        _done_row("2", "failed:telegram"),
        _done_row("3", ""),
        {**_done_row("4", "failed:drive"), "status": "failed"},
    ]
    assert [row["id"] for row in select_jobs(rows, select="publish-failed")] == ["2"]


@patch("core.publish_runner.publish_video_report")
@patch("core.batch_runner.execute_job")
def test_publish_failure_is_recorded_per_platform(
    mock_execute, mock_publish, tmp_path: Path
) -> None:
    out = tmp_path / "output" / "final.mp4"
    (tmp_path / "output").mkdir()
    out.write_bytes(b"mp4")
    mock_execute.return_value = out
    mock_publish.return_value = {"drive": True, "telegram": False}

    csv_path = tmp_path / "jobs.csv"
    save_jobs(csv_path, [{**_done_row("1", ""), "status": "pending", "completed_at": ""}])

    results = process_pending_jobs(
        csv_path,
        max_jobs=0,
        select="pending",
        publish=True,
        output_dir=tmp_path / "final",
    )

    assert results[0]["publish"] == "failed"
    row = load_jobs(csv_path)[0]
    # Render succeeded, so the row stays done — the publish gap lives in its own column.
    assert row["status"] == "done"
    assert row["publish_status"] == "failed:telegram"


@patch("core.publish_runner.publish_video_report", return_value={"telegram": True})
@patch("core.batch_runner.execute_job")
def test_publish_failed_retry_skips_platforms_that_already_succeeded(
    mock_execute, mock_publish, tmp_path: Path
) -> None:
    out = tmp_path / "output" / "final.mp4"
    (tmp_path / "output").mkdir()
    out.write_bytes(b"mp4")
    mock_execute.return_value = out

    csv_path = tmp_path / "jobs.csv"
    save_jobs(csv_path, [_done_row("1", "failed:telegram")])

    results = process_pending_jobs(
        csv_path,
        max_jobs=0,
        select="publish-failed",
        publish=True,
        output_dir=tmp_path / "final",
    )

    # Drive already has the video; only telegram is retried.
    assert mock_publish.call_args.kwargs["platforms"] == ["telegram"]
    assert results[0]["publish"] == "ok"
    assert load_jobs(csv_path)[0]["publish_status"] == "ok"
