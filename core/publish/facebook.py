"""Facebook Page Reels publish adapter (Meta Graph API)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from core.publish.common import (
    PublishError,
    VideoMetadata,
    assert_video_exists,
    find_latest_done_job,
    format_job_caption,
    probe_video_metadata,
    resolve_publish_metadata,
)

FACEBOOK_MAX_DURATION_SEC = 90
FACEBOOK_ASPECT_RATIO = 9 / 16
FACEBOOK_ASPECT_TOLERANCE = 0.05
_RUPLOAD_BASE = "https://rupload.facebook.com/video-upload"


@dataclass(frozen=True)
class FacebookConfig:
    page_id: str
    access_token: str
    graph_version: str = "v25.0"


@dataclass(frozen=True)
class FacebookReelCaption:
    title: str
    description: str


def load_config_from_env() -> FacebookConfig | None:
    """Return config when required env vars are set; otherwise None."""
    page_id = os.environ.get("FACEBOOK_PAGE_ID", "").strip()
    access_token = os.environ.get("FACEBOOK_ACCESS_TOKEN", "").strip()
    if not page_id or not access_token:
        return None
    graph_version = os.environ.get("FACEBOOK_GRAPH_VERSION", "v25.0").strip() or "v25.0"
    return FacebookConfig(
        page_id=page_id,
        access_token=access_token,
        graph_version=graph_version,
    )


def format_facebook_reel_caption(publish: dict[str, Any]) -> FacebookReelCaption:
    """Map publish metadata to Facebook Reels title + description fields."""
    title = str(publish.get("title", "")).strip()
    description = str(publish.get("description", "")).strip()
    raw_tags = publish.get("hashtags")
    tags = (
        [str(tag).strip() for tag in raw_tags if str(tag).strip()]
        if isinstance(raw_tags, list)
        else []
    )
    hashtag_line = " ".join(tags)
    if hashtag_line:
        description = f"{description}\n\n{hashtag_line}".strip() if description else hashtag_line
    return FacebookReelCaption(title=title, description=description)


def _graph_url(config: FacebookConfig, path: str) -> str:
    return f"https://graph.facebook.com/{config.graph_version}/{path}"


def _check_graph_response(response: requests.Response, *, step: str) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as exc:
        raise PublishError(
            f"Facebook {step} returned non-JSON ({response.status_code}): {response.text[:200]}"
        ) from exc

    if not response.ok:
        error = payload.get("error") if isinstance(payload, dict) else None
        if isinstance(error, dict):
            code = error.get("code")
            message = error.get("message") or response.text[:200]
            if code == 613:
                raise PublishError(
                    f"Facebook rate limit (613): {message} — max ~30 Reels per Page per 24h"
                )
            raise PublishError(f"Facebook {step} error ({response.status_code}, code {code}): {message}")
        raise PublishError(f"Facebook {step} error ({response.status_code}): {response.text[:200]}")

    if not isinstance(payload, dict):
        raise PublishError(f"Facebook {step} returned unexpected payload")
    return payload


def assert_facebook_reel_uploadable(video_path: Path) -> VideoMetadata:
    """Validate file, 9:16 aspect ratio, and duration for Facebook Reels."""
    assert_video_exists(video_path)
    metadata = probe_video_metadata(video_path)
    if metadata is None:
        raise PublishError(
            f"Could not read video metadata (ffprobe required): {video_path}"
        )

    aspect = metadata.width / metadata.height
    if abs(aspect - FACEBOOK_ASPECT_RATIO) > FACEBOOK_ASPECT_TOLERANCE:
        raise PublishError(
            f"Video aspect ratio {metadata.width}x{metadata.height} is not 9:16 — "
            f"expected ~{FACEBOOK_ASPECT_RATIO:.4f}, got {aspect:.4f}"
        )

    if metadata.duration_sec > FACEBOOK_MAX_DURATION_SEC:
        raise PublishError(
            f"Video duration {metadata.duration_sec}s exceeds Facebook Reels limit "
            f"({FACEBOOK_MAX_DURATION_SEC}s)"
        )
    return metadata


def _resolve_reel_caption(
    video_path: Path,
    *,
    caption: str | None = None,
    payload_path: str | Path | None = None,
    jobs_csv: str | Path | None = None,
) -> FacebookReelCaption:
    if caption is not None:
        return FacebookReelCaption(title="", description=caption.strip())

    publish = resolve_publish_metadata(video_path, payload_path=payload_path)
    if publish is not None:
        return format_facebook_reel_caption(publish)

    if jobs_csv is not None:
        job = find_latest_done_job(jobs_csv)
        if job:
            text = format_job_caption(job_id=job["id"], topic=job["topic"])
            return FacebookReelCaption(title="", description=text)

    return FacebookReelCaption(title="", description="")


def upload_reel(
    video_path: str | Path,
    *,
    config: FacebookConfig,
    title: str = "",
    description: str = "",
    timeout: float = 600.0,
) -> dict[str, Any]:
    """Upload and publish a Reel to a Facebook Page (start → upload → finish)."""
    path = Path(video_path)
    metadata = assert_facebook_reel_uploadable(path)
    file_size = path.stat().st_size

    start_response = requests.post(
        _graph_url(config, f"{config.page_id}/video_reels"),
        params={"access_token": config.access_token},
        data={"upload_phase": "start"},
        timeout=timeout,
    )
    start_payload = _check_graph_response(start_response, step="start upload")
    video_id = str(start_payload.get("video_id", "")).strip()
    if not video_id:
        raise PublishError(f"Facebook start upload missing video_id: {start_payload}")

    upload_url = f"{_RUPLOAD_BASE}/{video_id}"
    with path.open("rb") as handle:
        upload_response = requests.post(
            upload_url,
            headers={
                "Authorization": f"OAuth {config.access_token}",
                "offset": "0",
                "file_size": str(file_size),
                "Content-Type": "application/octet-stream",
            },
            data=handle,
            timeout=timeout,
        )
    _check_graph_response(upload_response, step="binary upload")

    finish_data: dict[str, str] = {
        "upload_phase": "finish",
        "video_id": video_id,
        "video_state": "PUBLISHED",
    }
    if title:
        finish_data["title"] = title
    if description:
        finish_data["description"] = description

    finish_response = requests.post(
        _graph_url(config, f"{config.page_id}/video_reels"),
        params={"access_token": config.access_token},
        data=finish_data,
        timeout=timeout,
    )
    finish_payload = _check_graph_response(finish_response, step="finish upload")
    finish_payload["video_id"] = video_id
    finish_payload["duration_sec"] = metadata.duration_sec
    return finish_payload


def deliver_video(
    video_path: str | Path,
    *,
    jobs_csv: str | Path | None = None,
    caption: str | None = None,
    payload_path: str | Path | None = None,
    config: FacebookConfig | None = None,
) -> dict[str, Any] | None:
    """Publish a rendered MP4 as a Facebook Page Reel."""
    resolved_config = config or load_config_from_env()
    if resolved_config is None:
        print("[facebook] skipped (FACEBOOK_PAGE_ID / FACEBOOK_ACCESS_TOKEN not set)")
        return None

    path = Path(video_path)
    reel_caption = _resolve_reel_caption(
        path,
        caption=caption,
        payload_path=payload_path,
        jobs_csv=jobs_csv,
    )

    size = assert_video_exists(path)
    result = upload_reel(
        path,
        config=resolved_config,
        title=reel_caption.title,
        description=reel_caption.description,
    )
    mb = size / (1024 * 1024)
    post_id = result.get("post_id") or result.get("video_id")
    print(f"[facebook] published reel ({mb:.1f} MB) — post_id={post_id}")
    return result
