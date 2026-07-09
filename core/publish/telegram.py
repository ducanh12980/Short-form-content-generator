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
TELEGRAM_MESSAGE_MAX_LEN = 4096
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


def format_drive_link_message(caption: str | None, drive_link: str) -> str:
    """Build a Telegram message with optional caption and a Google Drive link."""
    link = drive_link.strip()
    if not link:
        raise TelegramNotifyError("Google Drive link is empty.")

    if caption is None or not caption.strip():
        return link

    message = f"{caption.strip()}\n\n{link}"
    if len(message) <= TELEGRAM_MESSAGE_MAX_LEN:
        return message

    overhead = len(link) + 2
    max_caption = TELEGRAM_MESSAGE_MAX_LEN - overhead
    if max_caption <= 0:
        return link[:TELEGRAM_MESSAGE_MAX_LEN]

    trimmed_caption = caption.strip()
    if len(trimmed_caption) > max_caption:
        suffix = "…"
        trimmed_caption = trimmed_caption[: max(0, max_caption - len(suffix))].rstrip() + suffix
    return f"{trimmed_caption}\n\n{link}"


def resolve_drive_link(
    video_path: str | Path,
    *,
    drive_link: str | None = None,
    jobs_csv: str | Path | None = None,
    caption: str | None = None,
    payload_path: str | Path | None = None,
) -> str:
    """Return a Drive web link, uploading the video when no link was provided."""
    if drive_link and drive_link.strip():
        return drive_link.strip()

    from core.publish import drive

    result = drive.deliver_video(
        video_path,
        jobs_csv=jobs_csv,
        caption=caption,
        payload_path=payload_path,
    )
    if result is None:
        raise TelegramNotifyError(
            "Google Drive is not configured. Set GOOGLE_DRIVE_FOLDER_ID plus OAuth vars "
            "or GOOGLE_DRIVE_CREDENTIALS_JSON before sending Telegram Drive links."
        )

    link = result.get("webViewLink")
    if not isinstance(link, str) or not link.strip():
        raise TelegramNotifyError("Drive upload succeeded but no webViewLink was returned.")
    return link.strip()


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
    drive_link: str | None = None,
) -> dict[str, Any] | None:
    """Upload to Google Drive and send the link via Telegram (no video upload)."""
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
    resolved_drive_link = resolve_drive_link(
        path,
        drive_link=drive_link,
        jobs_csv=jobs_csv,
        caption=caption,
        payload_path=payload_path,
    )
    message = format_drive_link_message(resolved_caption, resolved_drive_link)
    result = send_message(message, config=resolved_config)
    print(f"[telegram] sent drive link — {resolved_drive_link}")
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
