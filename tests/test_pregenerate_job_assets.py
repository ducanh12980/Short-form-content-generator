"""Tests for the job asset prefill CLI (scripts/pregenerate_job_assets.py)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from core.batch_runner import save_jobs
from scripts.pregenerate_job_assets import main

QUOTA_ERROR = RuntimeError(
    "429 RESOURCE_EXHAUSTED: You exceeded your current quota (generate_content_free_tier)"
)


def _pending_rows(count: int) -> list[dict[str, str]]:
    return [
        {
            "id": str(index),
            "topic": f"topic {index}",
            "status": "pending",
            "mode": "slideshow",
            "image_provider": "mock",
            "output_path": "",
            "error": "",
            "created_at": "2026-07-20T03:30:00+07:00",
            "completed_at": "",
            "publish_status": "",
        }
        for index in range(1, count + 1)
    ]


@patch("scripts.pregenerate_job_assets.pregenerate_job")
def test_prefill_stops_early_once_quota_is_exhausted(
    mock_job, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The free tier quota is shared, so later jobs would only fail the same way."""
    csv_path = tmp_path / "jobs.csv"
    save_jobs(csv_path, _pending_rows(4))
    mock_job.side_effect = ["created", QUOTA_ERROR, "created", "created"]
    monkeypatch.setattr("sys.argv", ["pregenerate_job_assets.py", "--csv", str(csv_path)])

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 1
    # Job 3 and 4 are left for a later run rather than burned against a dead quota.
    assert mock_job.call_count == 2


@patch("scripts.pregenerate_job_assets.pregenerate_job")
def test_prefill_continues_past_an_ordinary_job_failure(
    mock_job, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    csv_path = tmp_path / "jobs.csv"
    save_jobs(csv_path, _pending_rows(3))
    mock_job.side_effect = ["created", ValueError("malformed LLM JSON"), "created"]
    monkeypatch.setattr("sys.argv", ["pregenerate_job_assets.py", "--csv", str(csv_path)])

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 1
    assert mock_job.call_count == 3
