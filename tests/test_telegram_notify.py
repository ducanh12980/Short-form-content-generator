"""Tests for Telegram delivery helpers (mocked HTTP — no live Bot API)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.batch_runner import init_jobs_csv, save_jobs
from core.telegram_notify import (
    TELEGRAM_MAX_FILE_BYTES,
    TelegramConfig,
    TelegramNotifyError,
    assert_video_uploadable,
    deliver_message,
    deliver_video_from_batch,
    find_latest_done_job,
    format_job_caption,
    load_config_from_env,
    send_message,
    send_video,
)


def test_load_config_from_env_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    assert load_config_from_env() is None


def test_load_config_from_env_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
    config = load_config_from_env()
    assert config == TelegramConfig(bot_token="token", chat_id="123")


def test_format_job_caption_truncates_long_topic() -> None:
    topic = "x" * 2000
    caption = format_job_caption(job_id="42", topic=topic)
    assert len(caption) <= 1024
    assert caption.endswith("…")


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


def test_assert_video_uploadable_rejects_large_file(tmp_path: Path) -> None:
    video = tmp_path / "big.mp4"
    video.write_bytes(b"x" * (TELEGRAM_MAX_FILE_BYTES + 1))
    with pytest.raises(TelegramNotifyError, match="50 MB"):
        assert_video_uploadable(video)


@patch("core.telegram_notify.requests.post")
def test_send_video_posts_multipart(mock_post: MagicMock, tmp_path: Path) -> None:
    video = tmp_path / "final.mp4"
    video.write_bytes(b"mp4")
    mock_post.return_value = MagicMock(
        ok=True,
        status_code=200,
        json=lambda: {"ok": True, "result": {"message_id": 1}},
    )
    config = TelegramConfig(bot_token="token", chat_id="99")

    send_video(video, caption="#1 — topic", config=config)

    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args.kwargs
    assert call_kwargs["data"]["chat_id"] == "99"
    assert call_kwargs["data"]["caption"] == "#1 — topic"
    assert "video" in call_kwargs["files"]


@patch("core.telegram_notify.requests.post")
def test_send_message(mock_post: MagicMock) -> None:
    mock_post.return_value = MagicMock(
        ok=True,
        status_code=200,
        json=lambda: {"ok": True, "result": {"message_id": 2}},
    )
    config = TelegramConfig(bot_token="token", chat_id="99")

    send_message("batch failed", config=config)

    mock_post.assert_called_once()
    assert mock_post.call_args.kwargs["data"]["text"] == "batch failed"


@patch("core.telegram_notify.requests.post")
def test_deliver_video_from_batch_skips_without_config(
    mock_post: MagicMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    video = tmp_path / "final.mp4"
    video.write_bytes(b"mp4")

    result = deliver_video_from_batch(video)

    assert result is None
    mock_post.assert_not_called()
    assert "skipped" in capsys.readouterr().out


@patch("core.telegram_notify.requests.post")
def test_deliver_message_raises_on_api_error(mock_post: MagicMock) -> None:
    mock_post.return_value = MagicMock(
        ok=False,
        status_code=400,
        text="bad request",
        json=lambda: {"ok": False, "description": "chat not found"},
    )
    config = TelegramConfig(bot_token="token", chat_id="99")

    with pytest.raises(TelegramNotifyError, match="chat not found"):
        send_message("hello", config=config)


@patch("core.telegram_notify.requests.post")
def test_deliver_message_skips_without_config(
    mock_post: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

    assert deliver_message("hello") is None
    mock_post.assert_not_called()
