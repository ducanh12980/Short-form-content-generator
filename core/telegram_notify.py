"""Telegram Bot API delivery — send rendered MP4s and status messages."""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core.batch_runner import load_jobs

TELEGRAM_MAX_FILE_BYTES = 50 * 1024 * 1024  # Bot API upload limit
TELEGRAM_CAPTION_MAX_LEN = 1024
_API_BASE = "https://api.telegram.org/bot{token}/{method}"


@dataclass(frozen=True)
class TelegramConfig:
    bot_token: str
    chat_id: str


class TelegramNotifyError(RuntimeError):
    """Raised when Telegram delivery fails."""


def load_config_from_env() -> TelegramConfig | None:
    """Return config when both env vars are set; otherwise None (delivery skipped)."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        return None
    return TelegramConfig(bot_token=token, chat_id=chat_id)


def format_job_caption(*, job_id: str, topic: str) -> str:
    caption = f"#{job_id} — {topic.strip()}"
    if len(caption) <= TELEGRAM_CAPTION_MAX_LEN:
        return caption
    suffix = "…"
    keep = TELEGRAM_CAPTION_MAX_LEN - len(suffix)
    return caption[:keep] + suffix


def find_latest_done_job(csv_path: str | Path) -> dict[str, str] | None:
    """Return the most recently completed done row from jobs.csv."""
    rows = load_jobs(csv_path)
    done_rows = [row for row in rows if row.get("status") == "done"]
    if not done_rows:
        return None
    return max(done_rows, key=lambda row: row.get("completed_at") or "")


def assert_video_uploadable(video_path: Path) -> int:
    """Ensure the MP4 exists and is within Telegram's upload limit."""
    if not video_path.is_file():
        raise TelegramNotifyError(f"Video not found: {video_path}")
    size = video_path.stat().st_size
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

    data: dict[str, str] = {"chat_id": config.chat_id}
    if caption:
        data["caption"] = caption[:TELEGRAM_CAPTION_MAX_LEN]

    with path.open("rb") as handle:
        response = requests.post(
            _api_url(config, "sendVideo"),
            data=data,
            files={"video": (path.name, handle, "video/mp4")},
            timeout=timeout,
        )
    return _check_response(response)


def deliver_video_from_batch(
    video_path: str | Path,
    *,
    jobs_csv: str | Path | None = None,
    caption: str | None = None,
    config: TelegramConfig | None = None,
) -> dict[str, Any] | None:
    """Send a rendered MP4 with an optional caption from jobs.csv."""
    resolved_config = config or load_config_from_env()
    if resolved_config is None:
        print("[telegram] skipped (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set)")
        return None

    resolved_caption = caption
    if resolved_caption is None and jobs_csv is not None:
        job = find_latest_done_job(jobs_csv)
        if job:
            resolved_caption = format_job_caption(job_id=job["id"], topic=job["topic"])

    path = Path(video_path)
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


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def main() -> None:
    _load_env()
    parser = argparse.ArgumentParser(
        description="Send rendered videos or status messages via Telegram Bot API.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    video_parser = subparsers.add_parser("send-video", help="Upload an MP4 with sendVideo")
    video_parser.add_argument("video", help="Path to final.mp4")
    video_parser.add_argument(
        "--jobs-csv",
        default=os.environ.get("JOBS_CSV", "jobs.csv"),
        help="Build caption from the latest done row (default: JOBS_CSV or jobs.csv)",
    )
    video_parser.add_argument(
        "--caption",
        default=None,
        help="Override caption (default: derived from jobs.csv)",
    )

    message_parser = subparsers.add_parser("send-message", help="Send a plain text message")
    message_parser.add_argument("text", help="Message body")

    args = parser.parse_args()

    try:
        if args.command == "send-video":
            deliver_video_from_batch(
                args.video,
                jobs_csv=args.jobs_csv,
                caption=args.caption,
            )
        else:
            deliver_message(args.text)
    except (TelegramNotifyError, FileNotFoundError, ValueError) as exc:
        print(f"Telegram delivery failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
