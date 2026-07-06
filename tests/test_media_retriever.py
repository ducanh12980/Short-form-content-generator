"""Tests for core/media_retriever.py."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from core.media_retriever import (
    _pick_hd_file,
    _pick_photo_url,
    derive_search_keywords,
    download_broll_clips_for_keywords,
    download_images_for_keywords,
    extract_keywords,
)


def test_extract_keywords_skips_stopwords_and_short_tokens() -> None:
    text = "The quick brown fox jumps over the lazy river water"
    keywords = extract_keywords(text, max_keywords=3)
    assert keywords == ["quick", "brown", "jumps"]


def test_derive_search_keywords_uses_topic_fallback_for_vietnamese() -> None:
    topic = "90% mọi người đang uống nước sai cách"
    script = "Bạn có biết cách uống nước đúng không?"
    keywords = derive_search_keywords(script, topic, max_keywords=3)
    assert keywords == [topic]


def test_derive_search_keywords_prefers_english_tokens_in_topic() -> None:
    topic = "drinking water health tips"
    keywords = derive_search_keywords("", topic, max_keywords=2)
    assert keywords == ["drinking", "water"]


def test_pick_photo_url_prefers_portrait() -> None:
    photo = {
        "src": {
            "original": "https://example.com/original.jpg",
            "portrait": "https://example.com/portrait.jpg",
        }
    }
    assert _pick_photo_url(photo) == "https://example.com/portrait.jpg"


def test_pick_hd_file_prefers_portrait() -> None:
    video = {
        "video_files": [
            {"width": 1920, "height": 1080, "link": "landscape.mp4"},
            {"width": 1080, "height": 1920, "link": "portrait.mp4"},
        ]
    }
    picked = _pick_hd_file(video)
    assert picked is not None
    assert picked["link"] == "portrait.mp4"


@patch("core.media_retriever.requests.get")
def test_download_images_for_keywords_writes_files(
    mock_get: MagicMock,
    tmp_path: Path,
) -> None:
    search_response = MagicMock()
    search_response.raise_for_status.return_value = None
    search_response.json.return_value = {
        "photos": [
            {
                "id": 42,
                "src": {"portrait": "https://example.com/water.jpg"},
            }
        ]
    }

    download_response = MagicMock()
    download_response.raise_for_status.return_value = None
    download_response.content = b"fake-jpeg-bytes"
    mock_get.side_effect = [search_response, download_response]

    images = download_images_for_keywords(
        ["water"],
        tmp_path,
        api_key="test-key",
        max_images=1,
    )

    assert len(images) == 1
    assert images[0].name == "water_42.jpg"
    assert images[0].read_bytes() == b"fake-jpeg-bytes"
    assert mock_get.call_count == 2


@patch("core.media_retriever.requests.get")
def test_download_images_for_keywords_reuses_existing_file(
    mock_get: MagicMock,
    tmp_path: Path,
) -> None:
    existing = tmp_path / "water_42.jpg"
    existing.write_bytes(b"cached")

    search_response = MagicMock()
    search_response.raise_for_status.return_value = None
    search_response.json.return_value = {
        "photos": [
            {
                "id": 42,
                "src": {"portrait": "https://example.com/water.jpg"},
            }
        ]
    }
    mock_get.return_value = search_response

    images = download_images_for_keywords(["water"], tmp_path, api_key="test-key", max_images=1)

    assert images == [existing]
    mock_get.assert_called_once()


@patch("core.media_retriever.requests.get")
def test_download_broll_clips_for_keywords_writes_mp4(
    mock_get: MagicMock,
    tmp_path: Path,
) -> None:
    search_response = MagicMock()
    search_response.raise_for_status.return_value = None
    search_response.json.return_value = {
        "videos": [
            {
                "id": 42,
                "video_files": [{"width": 1080, "height": 1920, "link": "https://example.com/a.mp4"}],
            }
        ]
    }

    download_response = MagicMock()
    download_response.raise_for_status.return_value = None
    download_response.content = b"fake-mp4-bytes"
    mock_get.side_effect = [search_response, download_response]

    clips = download_broll_clips_for_keywords(
        ["water"],
        tmp_path,
        api_key="test-key",
        max_clips=1,
    )

    assert len(clips) == 1
    assert clips[0].name == "water_42.mp4"
    assert clips[0].read_bytes() == b"fake-mp4-bytes"
