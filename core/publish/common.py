"""Shared helpers for platform publish adapters."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.batch_runner import load_jobs
from core.project_schema import get_publish_metadata


class PublishError(RuntimeError):
    """Raised when a platform publish operation fails."""


@dataclass(frozen=True)
class VideoMetadata:
    width: int
    height: int
    duration_sec: int


def probe_video_metadata(video_path: Path) -> VideoMetadata | None:
    """Read width/height/duration via ffprobe."""
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


def assert_video_exists(video_path: Path) -> int:
    """Ensure the video file exists and is non-empty."""
    if not video_path.is_file():
        raise PublishError(f"Video not found: {video_path}")
    size = video_path.stat().st_size
    if size <= 0:
        raise PublishError(f"Video is empty: {video_path}")
    return size


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


def find_latest_done_job(csv_path: str | Path) -> dict[str, str] | None:
    """Return the most recently completed done row from jobs.csv."""
    rows = load_jobs(csv_path)
    done_rows = [row for row in rows if row.get("status") == "done"]
    if not done_rows:
        return None
    return max(done_rows, key=lambda row: row.get("completed_at") or "")


def format_job_caption(*, job_id: str, topic: str, max_len: int = 1024) -> str:
    caption = f"#{job_id} — {topic.strip()}"
    if len(caption) <= max_len:
        return caption
    suffix = "…"
    keep = max_len - len(suffix)
    return caption[:keep] + suffix


def resolve_payload_path(
    video_path: str | Path,
    payload_path: str | Path | None = None,
) -> Path:
    if payload_path is not None:
        return Path(payload_path)
    return Path(video_path).parent / "pipeline_payload.json"


def resolve_publish_metadata(
    video_path: str | Path,
    *,
    payload_path: str | Path | None = None,
) -> dict[str, Any] | None:
    """Load publish metadata from the pipeline payload next to the video."""
    return load_publish_from_payload(resolve_payload_path(video_path, payload_path))
