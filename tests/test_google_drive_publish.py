"""Tests for Google Drive publish adapter."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.publish import drive
from core.publish.common import PublishError


def test_load_config_from_env_service_account(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_DRIVE_CREDENTIALS_JSON", "{}")
    monkeypatch.setenv("GOOGLE_DRIVE_FOLDER_ID", "folder-123")

    config = drive.load_config_from_env()

    assert config is not None
    assert config.folder_id == "folder-123"
    assert config.credentials_json == "{}"
    assert not config.uses_oauth


def test_load_config_from_env_oauth(monkeypatch) -> None:
    monkeypatch.delenv("GOOGLE_DRIVE_CREDENTIALS_JSON", raising=False)
    monkeypatch.setenv("GOOGLE_DRIVE_CLIENT_ID", "client-id")
    monkeypatch.setenv("GOOGLE_DRIVE_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("GOOGLE_DRIVE_REFRESH_TOKEN", "refresh-token")
    monkeypatch.setenv("GOOGLE_DRIVE_FOLDER_ID", "folder-123")

    config = drive.load_config_from_env()

    assert config is not None
    assert config.uses_oauth
    assert config.folder_id == "folder-123"


def test_deliver_video_uploads_file(tmp_path: Path) -> None:
    video = tmp_path / "final.mp4"
    video.write_bytes(b"fake-video")

    config = drive.DriveConfig(folder_id="folder-123", credentials_json="{}")

    service = MagicMock()
    service.files.return_value.create.return_value.execute.return_value = {
        "id": "123",
        "name": video.name,
        "webViewLink": "https://drive.google.com/file/d/123/view",
    }

    with patch("core.publish.drive.build_drive_service", return_value=service):
        result = drive.deliver_video(video, config=config)

    assert result["id"] == "123"
    create_call = service.files.return_value.create.call_args
    assert create_call is not None
    assert create_call.kwargs["media_body"].mimetype() == "video/mp4"
    assert create_call.kwargs["body"]["name"] == video.name
    assert create_call.kwargs["body"]["parents"] == ["folder-123"]
    assert create_call.kwargs["supportsAllDrives"] is True


def test_deliver_video_names_file_from_topic(tmp_path: Path) -> None:
    video = tmp_path / "final.mp4"
    video.write_bytes(b"fake-video")

    payload_path = tmp_path / "pipeline_payload.json"
    payload_path.write_text(
        '{"topic": "Cách uống nước đúng cách"}',
        encoding="utf-8",
    )

    service = MagicMock()
    service.files.return_value.create.return_value.execute.return_value = {"id": "123"}

    with patch("core.publish.drive.build_drive_service", return_value=service):
        drive.deliver_video(
            video,
            payload_path=payload_path,
            config=drive.DriveConfig(folder_id="folder-123", credentials_json="{}"),
        )

    create_call = service.files.return_value.create.call_args
    assert create_call is not None
    assert create_call.kwargs["body"]["name"] == "Cách uống nước đúng cách.mp4"


def test_deliver_video_uses_publish_metadata_as_description(tmp_path: Path) -> None:
    video = tmp_path / "final.mp4"
    video.write_bytes(b"fake-video")

    payload_path = tmp_path / "pipeline_payload.json"
    payload_path.write_text(
        (
            '{"publish": {"title": "Tiêu đề", "description": "Mô tả video", '
            '"hashtags": ["#shorts", "#health"]}}'
        ),
        encoding="utf-8",
    )

    service = MagicMock()
    service.files.return_value.create.return_value.execute.return_value = {"id": "123"}

    with patch("core.publish.drive.build_drive_service", return_value=service):
        drive.deliver_video(
            video,
            payload_path=payload_path,
            config=drive.DriveConfig(folder_id="folder-123", credentials_json="{}"),
        )

    create_call = service.files.return_value.create.call_args
    assert create_call is not None
    assert create_call.kwargs["body"]["description"] == (
        "Tiêu đề\n\nMô tả video\n\n#shorts #health"
    )


def test_deliver_video_wraps_storage_quota_error(tmp_path: Path) -> None:
    video = tmp_path / "final.mp4"
    video.write_bytes(b"fake-video")

    service = MagicMock()
    from googleapiclient.errors import HttpError

    response = MagicMock(status=403)
    service.files.return_value.create.return_value.execute.side_effect = HttpError(
        resp=response,
        content=b'{"error": {"message": "Service Accounts do not have storage quota"}}',
    )

    with patch("core.publish.drive.build_drive_service", return_value=service):
        with pytest.raises(PublishError, match="OAuth"):
            drive.deliver_video(
                video,
                config=drive.DriveConfig(folder_id="folder-123", credentials_json="{}"),
            )
