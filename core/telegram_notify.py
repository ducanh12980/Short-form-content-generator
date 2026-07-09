"""Telegram Bot API delivery — backward-compatible wrapper around core.publish.telegram."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core.publish.common import VideoMetadata, find_latest_done_job, load_publish_from_payload
from core.publish.telegram import (
    TELEGRAM_CAPTION_MAX_LEN,
    TELEGRAM_MAX_FILE_BYTES,
    TelegramConfig,
    TelegramNotifyError,
    assert_video_uploadable,
    deliver_message,
    deliver_video,
    format_job_caption,
    format_publish_caption,
    load_config_from_env,
    probe_video_metadata,
    resolve_video_caption,
    send_message,
    send_video,
)

# Backward-compatible alias used by publish_runner and external callers.
deliver_video_from_batch = deliver_video


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(_REPO_ROOT / ".env")


def main() -> None:
    _load_env()
    parser = argparse.ArgumentParser(
        description="Send rendered videos or status messages via Telegram Bot API.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    video_parser = subparsers.add_parser(
        "send-video",
        help="Upload to Google Drive and send the link via Telegram",
    )
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
            deliver_video(
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
