"""Telegram Bot API delivery — send rendered MP4s and status messages."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core.batch_runner import load_jobs
from core.project_schema import get_publish_metadata

TELEGRAM_MAX_FILE_BYTES = 50 * 1024 * 1024  # Bot API upload limit
TELEGRAM_CAPTION_MAX_LEN = 1024
_API_BASE = "https://api.telegram.org/bot{token}/{method}"


@dataclass(frozen=True)
class TelegramConfig:
    bot_token: str
    chat_id: str


class TelegramNotifyError(RuntimeError):
    """Raised when Telegram delivery fails."""


@dataclass(frozen=True)
class VideoMetadata:
    width: int
    height: int
    duration_sec: int


def _debug_log(message: str, *, data: dict[str, Any], hypothesis_id: str) -> None:
    # #region agent log
    try:
        entry = {
            "sessionId": "f45bc2",
            "timestamp": int(time.time() * 1000),
            "location": "telegram_notify.py",
            "message": message,
            "data": data,
            "hypothesisId": hypothesis_id,
        }
        (_REPO_ROOT / "debug-f45bc2.log").open("a", encoding="utf-8").write(
            json.dumps(entry) + "\n"
        )
    except OSError:
        pass
    # #endregion


def probe_video_metadata(video_path: Path) -> VideoMetadata | None:
    """Read width/height/duration via ffprobe for Telegram sendVideo hints."""
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        return None

    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height",
                "-show_entries",
                "format=duration",
                "-of",
                "json",
                str(video_path),
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        if result.returncode != 0:
            return None

        payload = json.loads(result.stdout)
        streams = payload.get("streams")
        if not isinstance(streams, list) or not streams:
            return None

        stream = streams[0]
        width = int(stream.get("width", 0))
        height = int(stream.get("height", 0))
        duration = float((payload.get("format") or {}).get("duration", 0))
        if width <= 0 or height <= 0 or duration <= 0:
            return None

        return VideoMetadata(
            width=width,
            height=height,
            duration_sec=max(1, int(round(duration))),
        )
    except (OSError, ValueError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return None


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

    # Keep title + hashtags; truncate description in the middle.
    overhead = len(title) + len(hashtag_line) + 4  # two blank lines between three parts
    if overhead >= TELEGRAM_CAPTION_MAX_LEN:
        suffix = "…"
        keep = TELEGRAM_CAPTION_MAX_LEN - len(suffix)
        return caption[:keep] + suffix

    max_description = TELEGRAM_CAPTION_MAX_LEN - overhead
    trimmed_description = description[: max(0, max_description - 1)].rstrip() + "…"
    return "\n\n".join(part for part in (title, trimmed_description, hashtag_line) if part)


def load_publish_from_payload(payload_path: str | Path) -> dict[str, Any] | None:
    """Read publish metadata from a pipeline_payload.json file."""
    path = Path(payload_path)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return get_publish_metadata(data)


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

    path = Path(video_path)
    resolved_payload = Path(payload_path) if payload_path else path.parent / "pipeline_payload.json"
    publish = load_publish_from_payload(resolved_payload)
    if publish is not None:
        return format_publish_caption(publish)

    if jobs_csv is not None:
        job = find_latest_done_job(jobs_csv)
        if job:
            return format_job_caption(job_id=job["id"], topic=job["topic"])

    return None


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

    metadata = probe_video_metadata(path)
    _debug_log(
        "send_video metadata",
        data={
            "path": str(path),
            "metadata": (
                {
                    "width": metadata.width,
                    "height": metadata.height,
                    "duration_sec": metadata.duration_sec,
                }
                if metadata
                else None
            ),
        },
        hypothesis_id="H3-H5",
    )

    data: dict[str, str] = {"chat_id": config.chat_id}
    if caption:
        data["caption"] = caption[:TELEGRAM_CAPTION_MAX_LEN]
    if metadata is not None:
        # Telegram iOS often shows a square preview unless these are explicit.
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


def deliver_video_from_batch(
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
        help="Override caption (default: pipeline_payload.json publish, else jobs.csv)",
    )
    video_parser.add_argument(
        "--payload",
        default=None,
        help="Path to pipeline_payload.json (default: next to the video file)",
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
                payload_path=args.payload,
            )
        else:
            deliver_message(args.text)
    except (TelegramNotifyError, FileNotFoundError, ValueError) as exc:
        print(f"Telegram delivery failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
