"""Telegram Bot API publish adapter."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from core.publish.common import (
    PublishError,
    assert_video_exists,
    find_latest_done_job,
    format_job_caption,
    probe_video_metadata,
    resolve_publish_metadata,
)

TELEGRAM_MAX_FILE_BYTES = 50 * 1024 * 1024
TELEGRAM_CAPTION_MAX_LEN = 1024
_API_BASE = "https://api.telegram.org/bot{token}/{method}"


@dataclass(frozen=True)
class TelegramConfig:
    bot_token: str
    chat_id: str


class TelegramNotifyError(PublishError):
    """Raised when Telegram delivery fails."""


def load_config_from_env() -> TelegramConfig | None:
    """Return config when both env vars are set; otherwise None."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        return None
    return TelegramConfig(bot_token=token, chat_id=chat_id)


def format_publish_caption(publish: dict[str, Any]) -> str:
    """Build a Telegram caption from publish metadata (title + description + hashtags)."""
    title = str(publish.get("title", "")).strip()
    description = str(publish.get("description", "")).strip()
    raw_tags = publish.get("hashtags")
    tags = (
        [str(tag).strip() for tag in raw_tags if str(tag).strip()]
        if isinstance(raw_tags, list)
        else []
    )
    hashtag_line = " ".join(tags)

    parts = [part for part in (title, description, hashtag_line) if part]
    caption = "\n\n".join(parts)
    if len(caption) <= TELEGRAM_CAPTION_MAX_LEN:
        return caption

    overhead = len(title) + len(hashtag_line) + 4
    if overhead >= TELEGRAM_CAPTION_MAX_LEN:
        suffix = "…"
        keep = TELEGRAM_CAPTION_MAX_LEN - len(suffix)
        return caption[:keep] + suffix

    max_description = TELEGRAM_CAPTION_MAX_LEN - overhead
    trimmed_description = description[: max(0, max_description - 1)].rstrip() + "…"
    return "\n\n".join(part for part in (title, trimmed_description, hashtag_line) if part)


def resolve_video_caption(
    video_path: str | Path,
    *,
    caption: str | None = None,
    payload_path: str | Path | None = None,
    jobs_csv: str | Path | None = None,
) -> str | None:
    """Resolve caption: explicit override, then payload publish, then jobs.csv."""
    if caption is not None:
        return caption

    publish = resolve_publish_metadata(video_path, payload_path=payload_path)
    if publish is not None:
        return format_publish_caption(publish)

    if jobs_csv is not None:
        job = find_latest_done_job(jobs_csv)
        if job:
            return format_job_caption(
                job_id=job["id"],
                topic=job["topic"],
                max_len=TELEGRAM_CAPTION_MAX_LEN,
            )

    return None


def assert_video_uploadable(video_path: Path) -> int:
    """Ensure the MP4 exists and is within Telegram's upload limit."""
    size = assert_video_exists(video_path)
    if size > TELEGRAM_MAX_FILE_BYTES:
        mb = size / (1024 * 1024)
        raise TelegramNotifyError(
            f"Video is {mb:.1f} MB — Telegram Bot API limit is 50 MB: {video_path}"
        )
    return size


def _api_url(config: TelegramConfig, method: str) -> str:
    return _API_BASE.format(token=config.bot_token, method=method)


def _check_response(response: requests.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as exc:
        raise TelegramNotifyError(
            f"Telegram API returned non-JSON ({response.status_code}): {response.text[:200]}"
        ) from exc

    if not response.ok or not payload.get("ok"):
        description = payload.get("description") or response.text[:200]
        raise TelegramNotifyError(f"Telegram API error ({response.status_code}): {description}")
    return payload


def send_message(text: str, *, config: TelegramConfig, timeout: float = 30.0) -> dict[str, Any]:
    if not text.strip():
        raise TelegramNotifyError("Message text is empty.")
    response = requests.post(
        _api_url(config, "sendMessage"),
        data={"chat_id": config.chat_id, "text": text},
        timeout=timeout,
    )
    return _check_response(response)


def send_video(
    video_path: str | Path,
    *,
    caption: str | None = None,
    config: TelegramConfig,
    timeout: float = 300.0,
) -> dict[str, Any]:
    path = Path(video_path)
    assert_video_uploadable(path)

    metadata = probe_video_metadata(path)
    data: dict[str, str] = {"chat_id": config.chat_id}
    if caption:
        data["caption"] = caption[:TELEGRAM_CAPTION_MAX_LEN]
    if metadata is not None:
        data["width"] = str(metadata.width)
        data["height"] = str(metadata.height)
        data["duration"] = str(metadata.duration_sec)
        data["supports_streaming"] = "true"

    with path.open("rb") as handle:
        response = requests.post(
            _api_url(config, "sendVideo"),
            data=data,
            files={"video": (path.name, handle, "video/mp4")},
            timeout=timeout,
        )
    return _check_response(response)


def deliver_video(
    video_path: str | Path,
    *,
    jobs_csv: str | Path | None = None,
    caption: str | None = None,
    payload_path: str | Path | None = None,
    config: TelegramConfig | None = None,
) -> dict[str, Any] | None:
    """Send a rendered MP4 with caption from payload publish metadata or jobs.csv."""
    resolved_config = config or load_config_from_env()
    if resolved_config is None:
        print("[telegram] skipped (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set)")
        return None

    path = Path(video_path)
    resolved_caption = resolve_video_caption(
        path,
        caption=caption,
        payload_path=payload_path,
        jobs_csv=jobs_csv,
    )

    size = assert_video_uploadable(path)
    result = send_video(path, caption=resolved_caption, config=resolved_config)
    mb = size / (1024 * 1024)
    print(f"[telegram] sent video ({mb:.1f} MB) — {path.resolve()}")
    return result


def deliver_message(
    text: str,
    *,
    config: TelegramConfig | None = None,
) -> dict[str, Any] | None:
    resolved_config = config or load_config_from_env()
    if resolved_config is None:
        print("[telegram] skipped (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set)")
        return None

    result = send_message(text, config=resolved_config)
    print("[telegram] sent message")
    return result
