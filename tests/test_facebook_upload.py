"""Tests for Facebook Reels publish adapter (mocked HTTP)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.publish.common import PublishError, VideoMetadata
from core.publish.facebook import (
    FacebookConfig,
    assert_facebook_reel_uploadable,
    deliver_video,
    format_facebook_reel_caption,
    load_config_from_env,
    upload_reel,
)


def test_load_config_from_env_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FACEBOOK_PAGE_ID", raising=False)
    monkeypatch.delenv("FACEBOOK_ACCESS_TOKEN", raising=False)
    assert load_config_from_env() is None


def test_load_config_from_env_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FACEBOOK_PAGE_ID", "page123")
    monkeypatch.setenv("FACEBOOK_ACCESS_TOKEN", "token")
    monkeypatch.setenv("FACEBOOK_GRAPH_VERSION", "v25.0")
    config = load_config_from_env()
    assert config == FacebookConfig(
        page_id="page123",
        access_token="token",
        graph_version="v25.0",
    )


def test_format_facebook_reel_caption_joins_description_and_hashtags() -> None:
    caption = format_facebook_reel_caption(
        {
            "title": "Reel title",
            "description": "Reel description",
            "hashtags": ["#tag1", "#tag2"],
        }
    )
    assert caption.title == "Reel title"
    assert "Reel description" in caption.description
    assert "#tag1 #tag2" in caption.description


@patch("core.publish.facebook.probe_video_metadata")
def test_assert_facebook_reel_uploadable_rejects_wrong_aspect(
    mock_probe: MagicMock,
    tmp_path: Path,
) -> None:
    video = tmp_path / "final.mp4"
    video.write_bytes(b"mp4")
    mock_probe.return_value = VideoMetadata(width=1920, height=1080, duration_sec=30)

    with pytest.raises(PublishError, match="9:16"):
        assert_facebook_reel_uploadable(video)


@patch("core.publish.facebook.probe_video_metadata")
def test_assert_facebook_reel_uploadable_rejects_long_duration(
    mock_probe: MagicMock,
    tmp_path: Path,
) -> None:
    video = tmp_path / "final.mp4"
    video.write_bytes(b"mp4")
    mock_probe.return_value = VideoMetadata(width=1080, height=1920, duration_sec=120)

    with pytest.raises(PublishError, match="90s"):
        assert_facebook_reel_uploadable(video)


@patch("core.publish.facebook.requests.post")
@patch("core.publish.facebook.assert_facebook_reel_uploadable")
def test_upload_reel_three_step_flow(
    mock_validate: MagicMock,
    mock_post: MagicMock,
    tmp_path: Path,
) -> None:
    video = tmp_path / "final.mp4"
    video.write_bytes(b"mp4-content")
    mock_validate.return_value = VideoMetadata(width=1080, height=1920, duration_sec=45)
    config = FacebookConfig(page_id="page1", access_token="tok")

    start_resp = MagicMock(ok=True, status_code=200)
    start_resp.json.return_value = {"video_id": "vid123"}
    upload_resp = MagicMock(ok=True, status_code=200)
    upload_resp.json.return_value = {"success": True}
    finish_resp = MagicMock(ok=True, status_code=200)
    finish_resp.json.return_value = {"success": True, "post_id": "post456"}
    mock_post.side_effect = [start_resp, upload_resp, finish_resp]

    result = upload_reel(
        video,
        config=config,
        title="Title",
        description="Description",
    )

    assert result["post_id"] == "post456"
    assert result["video_id"] == "vid123"
    assert mock_post.call_count == 3

    upload_call = mock_post.call_args_list[1]
    assert "rupload.facebook.com" in upload_call.args[0]
    assert upload_call.kwargs["headers"]["Authorization"] == "OAuth tok"
    assert upload_call.kwargs["headers"]["offset"] == "0"


@patch("core.publish.facebook.upload_reel")
def test_deliver_video_skips_without_config(
    mock_upload: MagicMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("FACEBOOK_PAGE_ID", raising=False)
    monkeypatch.delenv("FACEBOOK_ACCESS_TOKEN", raising=False)
    video = tmp_path / "final.mp4"
    video.write_bytes(b"mp4")

    result = deliver_video(video)

    assert result is None
    mock_upload.assert_not_called()
    assert "skipped" in capsys.readouterr().out


@patch("core.publish.facebook.upload_reel")
def test_deliver_video_uses_publish_metadata(
    mock_upload: MagicMock,
    tmp_path: Path,
) -> None:
    video = tmp_path / "final.mp4"
    video.write_bytes(b"mp4")
    payload_path = tmp_path / "pipeline_payload.json"
    payload_path.write_text(
        json.dumps(
            {
                "publish": {
                    "title": "FB title",
                    "description": "FB description",
                    "hashtags": ["#reel"],
                }
            }
        ),
        encoding="utf-8",
    )
    mock_upload.return_value = {"post_id": "p1"}
    config = FacebookConfig(page_id="page1", access_token="tok")

    deliver_video(video, payload_path=payload_path, config=config)

    mock_upload.assert_called_once()
    assert mock_upload.call_args.kwargs["title"] == "FB title"
    assert "FB description" in mock_upload.call_args.kwargs["description"]
    assert "#reel" in mock_upload.call_args.kwargs["description"]
