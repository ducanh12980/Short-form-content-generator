"""Google Drive publish adapter."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.publish.common import (
    PublishError,
    assert_video_exists,
    find_latest_done_job,
    format_job_caption,
    resolve_publish_metadata,
)

DRIVE_DESCRIPTION_MAX_LEN = 4096
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.file"]


@dataclass(frozen=True)
class DriveConfig:
    folder_id: str
    client_id: str | None = None
    client_secret: str | None = None
    refresh_token: str | None = None
    credentials_json: str | None = None

    @property
    def uses_oauth(self) -> bool:
        return bool(self.client_id and self.client_secret and self.refresh_token)


def load_config_from_env() -> DriveConfig | None:
    """Return config when Google Drive env vars are set; otherwise None."""
    folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "").strip()
    if not folder_id:
        return None

    client_id = os.environ.get("GOOGLE_DRIVE_CLIENT_ID", "").strip()
    client_secret = os.environ.get("GOOGLE_DRIVE_CLIENT_SECRET", "").strip()
    refresh_token = os.environ.get("GOOGLE_DRIVE_REFRESH_TOKEN", "").strip()
    if client_id and client_secret and refresh_token:
        return DriveConfig(
            folder_id=folder_id,
            client_id=client_id,
            client_secret=client_secret,
            refresh_token=refresh_token,
        )

    credentials_json = os.environ.get("GOOGLE_DRIVE_CREDENTIALS_JSON", "").strip()
    if credentials_json:
        return DriveConfig(folder_id=folder_id, credentials_json=credentials_json)

    return None


def _require_google_packages() -> None:
    try:
        import google.oauth2  # noqa: F401
        import googleapiclient  # noqa: F401
    except ImportError as exc:  # pragma: no cover - exercised in runtime envs without deps
        raise PublishError(
            "google-api-python-client / google-auth packages are required for Drive upload"
        ) from exc


def build_drive_service(config: DriveConfig) -> Any:
    """Build a Google Drive API service from OAuth or service account config."""
    _require_google_packages()
    from googleapiclient.discovery import build

    if config.uses_oauth:
        from google.oauth2.credentials import Credentials

        credentials = Credentials(
            token=None,
            refresh_token=config.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=config.client_id,
            client_secret=config.client_secret,
            scopes=DRIVE_SCOPES,
        )
        return build("drive", "v3", credentials=credentials, cache_discovery=False)

    if not config.credentials_json:
        raise PublishError("Google Drive credentials are not configured")

    try:
        from google.oauth2 import service_account
    except ImportError as exc:  # pragma: no cover
        raise PublishError(
            "google-api-python-client / google-auth packages are required for Drive upload"
        ) from exc

    try:
        creds_info = json.loads(config.credentials_json)
    except json.JSONDecodeError as exc:
        raise PublishError("GOOGLE_DRIVE_CREDENTIALS_JSON is not valid JSON") from exc

    credentials = service_account.Credentials.from_service_account_info(
        creds_info,
        scopes=DRIVE_SCOPES,
    )
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def format_publish_description(publish: dict[str, Any]) -> str:
    """Build a Drive file description from publish metadata."""
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
    if len(caption) <= DRIVE_DESCRIPTION_MAX_LEN:
        return caption

    suffix = "…"
    keep = DRIVE_DESCRIPTION_MAX_LEN - len(suffix)
    return caption[:keep] + suffix


def resolve_upload_description(
    video_path: str | Path,
    *,
    caption: str | None = None,
    payload_path: str | Path | None = None,
    jobs_csv: str | Path | None = None,
) -> str | None:
    """Resolve description: explicit override, payload publish, then jobs.csv."""
    if caption is not None:
        return caption.strip() or None

    publish = resolve_publish_metadata(video_path, payload_path=payload_path)
    if publish is not None:
        return format_publish_description(publish)

    if jobs_csv is not None:
        job = find_latest_done_job(jobs_csv)
        if job:
            return format_job_caption(
                job_id=job["id"],
                topic=job["topic"],
                max_len=DRIVE_DESCRIPTION_MAX_LEN,
            )

    return None


def _format_drive_http_error(exc: Any, *, uses_oauth: bool) -> PublishError:
    status = exc.resp.status if exc.resp is not None else "?"
    detail = str(exc)
    detail_lower = detail.lower()

    if status == 403 and (
        "storage quota" in detail_lower or "storagequotaexceeded" in detail_lower
    ):
        return PublishError(
            "Google Drive service account cannot upload to personal Drive (no storage "
            "quota). Use OAuth instead: set GOOGLE_DRIVE_CLIENT_ID, "
            "GOOGLE_DRIVE_CLIENT_SECRET, GOOGLE_DRIVE_REFRESH_TOKEN "
            "(run: python scripts/drive_oauth_setup.py), remove "
            "GOOGLE_DRIVE_CREDENTIALS_JSON, and keep GOOGLE_DRIVE_FOLDER_ID. "
            "Alternatively, use a Google Workspace Shared Drive with a service account."
        )

    if status == 403:
        if uses_oauth:
            return PublishError(
                f"Google Drive upload denied (403). Check that GOOGLE_DRIVE_FOLDER_ID "
                f"is a folder you own or can edit. Details: {detail}"
            )
        return PublishError(
            "Google Drive upload denied (403). Share the target folder with the "
            "service account email from GOOGLE_DRIVE_CREDENTIALS_JSON "
            f"(client_email) as Editor, or use OAuth for personal Drive. Details: {detail}"
        )

    if status == 404:
        return PublishError(
            f"Google Drive folder not found (404). Check GOOGLE_DRIVE_FOLDER_ID. "
            f"Details: {detail}"
        )

    return PublishError(f"Google Drive upload failed ({status}): {detail}")


def deliver_video(
    video_path: str | Path,
    *,
    jobs_csv: str | Path | None = None,
    caption: str | None = None,
    payload_path: str | Path | None = None,
    config: DriveConfig | None = None,
) -> dict[str, Any] | None:
    """Upload a rendered MP4 to Google Drive in the configured folder."""
    resolved_config = config or load_config_from_env()
    if resolved_config is None:
        print(
            "[drive] skipped (set GOOGLE_DRIVE_FOLDER_ID plus OAuth vars or "
            "GOOGLE_DRIVE_CREDENTIALS_JSON)"
        )
        return None

    path = Path(video_path)
    assert_video_exists(path)

    try:
        from googleapiclient.errors import HttpError
        from googleapiclient.http import MediaFileUpload
    except ImportError as exc:  # pragma: no cover
        raise PublishError(
            "google-api-python-client / google-auth packages are required for Drive upload"
        ) from exc

    service = build_drive_service(resolved_config)
    media = MediaFileUpload(
        str(path),
        mimetype="video/mp4",
        resumable=False,
    )
    body: dict[str, Any] = {
        "name": path.name,
        "parents": [resolved_config.folder_id],
    }
    resolved_description = resolve_upload_description(
        path,
        caption=caption,
        payload_path=payload_path,
        jobs_csv=jobs_csv,
    )
    if resolved_description:
        body["description"] = resolved_description

    create_kwargs: dict[str, Any] = {
        "body": body,
        "media_body": media,
        "fields": "id,name,webViewLink",
    }
    if not resolved_config.uses_oauth:
        create_kwargs["supportsAllDrives"] = True

    try:
        result = service.files().create(**create_kwargs).execute()
    except HttpError as exc:
        raise _format_drive_http_error(exc, uses_oauth=resolved_config.uses_oauth) from exc

    link = result.get("webViewLink", "")
    if link:
        print(f"[drive] uploaded video — {path.resolve()} — {link}")
    else:
        print(f"[drive] uploaded video — {path.resolve()}")
    return result
