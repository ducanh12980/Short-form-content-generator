"""Tests for per-slot repair of the current day: failed-today + attempt cap."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.batch_runner import (
    DEFAULT_MAX_ATTEMPTS,
    job_attempts,
    load_jobs,
    process_pending_jobs,
    save_jobs,
    select_jobs,
)

TODAY = date(2026, 7, 17)
_TODAY_ISO = "2026-07-17T04:33:00+07:00"
_YESTERDAY_ISO = "2026-07-16T04:33:00+07:00"


def _row(job_id: str, **over) -> dict[str, str]:
    row = {
        "id": job_id,
        "topic": f"topic {job_id}",
        "status": "pending",
        "mode": "slideshow",
        "image_provider": "mock",
        "output_path": "",
        "error": "",
        "created_at": _TODAY_ISO,
        "completed_at": "",
        "publish_status": "",
        "attempts": "",
    }
    row.update(over)
    return row


def test_job_attempts_treats_blank_and_garbage_as_zero() -> None:
    assert job_attempts({"attempts": ""}) == 0
    assert job_attempts({}) == 0
    assert job_attempts({"attempts": "oops"}) == 0
    assert job_attempts({"attempts": "-4"}) == 0
    assert job_attempts({"attempts": "2"}) == 2


def test_failed_today_ignores_other_days() -> None:
    """A slot repairs today only — old failures must not burn today's quota."""
    rows = [
        _row("1", status="failed"),
        _row("2", status="failed", created_at=_YESTERDAY_ISO),
        _row("3"),
    ]
    picked = select_jobs(rows, select="failed-today", today=TODAY)
    assert [r["id"] for r in picked] == ["1"]

    # The nightly sweep still reaches every failure regardless of date.
    assert [r["id"] for r in select_jobs(rows, select="failed", today=TODAY)] == ["1", "2"]


def test_failed_today_stops_at_the_attempt_cap() -> None:
    rows = [
        _row("1", status="failed", attempts="2"),
        _row("2", status="failed", attempts=str(DEFAULT_MAX_ATTEMPTS)),
        _row("3", status="failed", attempts="99"),
    ]
    picked = select_jobs(rows, select="failed-today", today=TODAY)
    assert [r["id"] for r in picked] == ["1"]


def test_attempt_cap_applies_to_the_nightly_failed_sweep_too() -> None:
    rows = [_row("1", status="failed", attempts=str(DEFAULT_MAX_ATTEMPTS))]
    assert select_jobs(rows, select="failed", today=TODAY) == []


def test_attempt_cap_can_be_disabled() -> None:
    rows = [_row("1", status="failed", attempts="99")]
    picked = select_jobs(rows, select="failed-today", today=TODAY, max_attempts=0)
    assert [r["id"] for r in picked] == ["1"]


def test_publish_failed_today_scopes_to_today() -> None:
    rows = [
        _row("1", status="done", publish_status="failed:telegram"),
        _row("2", status="done", publish_status="failed:drive", created_at=_YESTERDAY_ISO),
        _row("3", status="done", publish_status="ok"),
        _row("4", status="failed"),
    ]
    picked = select_jobs(rows, select="publish-failed-today", today=TODAY)
    assert [r["id"] for r in picked] == ["1"]


def test_attempt_cap_never_blocks_a_fresh_pending_job() -> None:
    """due-today is not a retry mode; a row that used its budget still runs when re-queued."""
    rows = [_row("1", attempts="99")]
    assert [r["id"] for r in select_jobs(rows, select="due-today", today=TODAY)] == ["1"]


def _write_csv(tmp_path: Path, rows: list[dict[str, str]]) -> Path:
    path = tmp_path / "jobs.csv"
    save_jobs(path, rows)
    return path


@patch("core.batch_runner.execute_job")
def test_attempts_increments_on_every_run(mock_execute: MagicMock, tmp_path: Path) -> None:
    mp4 = tmp_path / "final.mp4"
    mp4.write_bytes(b"video")
    mock_execute.return_value = mp4

    path = _write_csv(tmp_path, [_row("1")])
    process_pending_jobs(path, select="due-today", today=TODAY, max_jobs=1)
    assert load_jobs(path)[0]["attempts"] == "1"


@patch("core.batch_runner.execute_job")
def test_failed_job_retried_by_a_later_slot_until_the_cap(
    mock_execute: MagicMock, tmp_path: Path
) -> None:
    """Three slots retry a broken job, then leave it alone for a human."""
    mock_execute.side_effect = RuntimeError("render blew up")
    path = _write_csv(tmp_path, [_row("1")])

    # Slot 1 renders it fresh and fails.
    process_pending_jobs(path, select="due-today", today=TODAY, max_jobs=1)
    assert load_jobs(path)[0]["status"] == "failed"
    assert load_jobs(path)[0]["attempts"] == "1"

    # Slots 2 and 3 repair the day first — same row, two more attempts.
    for expected in ("2", "3"):
        process_pending_jobs(path, select="failed-today", today=TODAY, max_jobs=0)
        assert load_jobs(path)[0]["attempts"] == expected

    # Budget spent: further slots (and the nightly sweep) skip it entirely.
    assert process_pending_jobs(path, select="failed-today", today=TODAY, max_jobs=0) == []
    assert process_pending_jobs(path, select="failed", today=TODAY, max_jobs=0) == []
    assert mock_execute.call_count == DEFAULT_MAX_ATTEMPTS


@patch("core.batch_runner.execute_job")
def test_repairing_the_day_then_rendering_the_next_job(
    mock_execute: MagicMock, tmp_path: Path
) -> None:
    """The 08:33 slot fixes job 1 and still renders job 2, so the day catches up."""
    mp4 = tmp_path / "final.mp4"
    mp4.write_bytes(b"video")
    mock_execute.return_value = mp4

    path = _write_csv(tmp_path, [_row("1", status="failed", attempts="1"), _row("2")])

    repaired = process_pending_jobs(path, select="failed-today", today=TODAY, max_jobs=0)
    rendered = process_pending_jobs(path, select="due-today", today=TODAY, max_jobs=1)

    assert [item["id"] for item in repaired] == ["1"]
    assert [item["id"] for item in rendered] == ["2"]
    assert [row["status"] for row in load_jobs(path)] == ["done", "done"]


@patch("core.batch_runner.execute_job")
def test_crash_still_burns_an_attempt(mock_execute: MagicMock, tmp_path: Path) -> None:
    """attempts is written before the render, so a hard crash cannot loop forever."""
    mock_execute.side_effect = KeyboardInterrupt()
    path = _write_csv(tmp_path, [_row("1")])

    try:
        process_pending_jobs(path, select="due-today", today=TODAY, max_jobs=1)
    except KeyboardInterrupt:
        pass

    assert load_jobs(path)[0]["attempts"] == "1"
