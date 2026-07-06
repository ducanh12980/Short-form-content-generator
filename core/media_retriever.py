"""Visual Sourcing Engine — keyword extraction and Pexels stock image download."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import requests

PEXELS_PHOTO_SEARCH_URL = "https://api.pexels.com/v1/search"
PEXELS_VIDEO_SEARCH_URL = "https://api.pexels.com/videos/search"


def _safe_filename_part(text: str) -> str:
    """Sanitize a keyword for use in a downloaded asset filename."""
    safe = re.sub(r"[^\w\-]+", "_", text.strip(), flags=re.UNICODE)
    return (safe[:40] or "asset").strip("_")


def extract_keywords(script_text: str, *, max_keywords: int = 5) -> list[str]:
    """Pull high-emphasis keywords from script text for stock media search."""
    stopwords = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
        "being", "have", "has", "had", "do", "does", "did", "will", "would",
        "could", "should", "may", "might", "must", "shall", "can", "need",
        "you", "your", "we", "they", "it", "this", "that", "these", "those",
        "i", "my", "our", "their", "its", "not", "no", "so", "if", "as",
    }
    tokens = re.findall(r"[A-Za-z]{4,}", script_text.lower())
    seen: set[str] = set()
    keywords: list[str] = []
    for token in tokens:
        if token in stopwords or token in seen:
            continue
        seen.add(token)
        keywords.append(token)
        if len(keywords) >= max_keywords:
            break
    return keywords


def derive_search_keywords(
    raw_script: str,
    topic: str = "",
    *,
    max_keywords: int = 3,
) -> list[str]:
    """Build Pexels search terms from topic/script (English tokens or topic fallback)."""
    for text in (topic, raw_script):
        keywords = extract_keywords(text, max_keywords=max_keywords)
        if keywords:
            return keywords

    fallback = (topic or raw_script).strip()[:80]
    return [fallback] if fallback else []


def search_pexels_photos(
    query: str,
    *,
    api_key: str | None = None,
    per_page: int = 3,
) -> list[dict[str, Any]]:
    """Search Pexels for portrait-oriented stock photos matching a keyword."""
    key = api_key or os.environ["PEXELS_API_KEY"]
    response = requests.get(
        PEXELS_PHOTO_SEARCH_URL,
        headers={"Authorization": key},
        params={"query": query, "per_page": per_page, "orientation": "portrait"},
        timeout=30,
    )
    response.raise_for_status()
    return response.json().get("photos", [])


def _pick_photo_url(photo: dict[str, Any]) -> str | None:
    src = photo.get("src") or {}
    for key in ("portrait", "large2x", "large", "original"):
        url = src.get(key)
        if url:
            return str(url)
    return None


def download_images_for_keywords(
    keywords: list[str],
    output_dir: str | Path,
    *,
    api_key: str | None = None,
    max_images: int = 3,
) -> list[Path]:
    """Download portrait stock images for explicit search keywords into output_dir."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    downloaded: list[Path] = []
    for keyword in keywords:
        if len(downloaded) >= max_images:
            break

        query = keyword.strip()
        if not query:
            continue

        photos = search_pexels_photos(query, api_key=api_key, per_page=1)
        if not photos:
            continue

        image_url = _pick_photo_url(photos[0])
        if not image_url:
            continue

        safe_name = _safe_filename_part(query)
        image_path = output_path / f"{safe_name}_{photos[0]['id']}.jpg"
        if image_path.exists():
            downloaded.append(image_path)
            continue

        image_response = requests.get(image_url, timeout=120)
        image_response.raise_for_status()
        image_path.write_bytes(image_response.content)
        downloaded.append(image_path)

    return downloaded


def download_broll_images(
    script_text: str,
    output_dir: str | Path,
    *,
    api_key: str | None = None,
    max_images: int = 3,
) -> list[Path]:
    """Download stock images for extracted script keywords into output_dir."""
    return download_images_for_keywords(
        extract_keywords(script_text),
        output_dir,
        api_key=api_key,
        max_images=max_images,
    )


# --- Video clips (low priority — future compositor support) ---


def search_pexels_videos(
    query: str,
    *,
    api_key: str | None = None,
    per_page: int = 3,
) -> list[dict[str, Any]]:
    """Search Pexels for vertical-friendly stock videos matching a keyword."""
    key = api_key or os.environ["PEXELS_API_KEY"]
    response = requests.get(
        PEXELS_VIDEO_SEARCH_URL,
        headers={"Authorization": key},
        params={"query": query, "per_page": per_page, "orientation": "portrait"},
        timeout=30,
    )
    response.raise_for_status()
    return response.json().get("videos", [])


def _pick_hd_file(video: dict[str, Any]) -> dict[str, Any] | None:
    files = video.get("video_files") or []
    portrait = [f for f in files if f.get("height", 0) >= f.get("width", 0)]
    candidates = portrait or files
    if not candidates:
        return None
    return max(candidates, key=lambda f: f.get("height", 0))


def download_broll_clips_for_keywords(
    keywords: list[str],
    output_dir: str | Path,
    *,
    api_key: str | None = None,
    max_clips: int = 3,
) -> list[Path]:
    """Download portrait b-roll video clips for explicit search keywords (future use)."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    downloaded: list[Path] = []
    for keyword in keywords:
        if len(downloaded) >= max_clips:
            break

        query = keyword.strip()
        if not query:
            continue

        videos = search_pexels_videos(query, api_key=api_key, per_page=1)
        if not videos:
            continue

        file_info = _pick_hd_file(videos[0])
        if not file_info or not file_info.get("link"):
            continue

        safe_name = _safe_filename_part(query)
        clip_path = output_path / f"{safe_name}_{videos[0]['id']}.mp4"
        if clip_path.exists():
            downloaded.append(clip_path)
            continue

        video_response = requests.get(file_info["link"], timeout=120)
        video_response.raise_for_status()
        clip_path.write_bytes(video_response.content)
        downloaded.append(clip_path)

    return downloaded


def download_broll_clips(
    script_text: str,
    output_dir: str | Path,
    *,
    api_key: str | None = None,
    max_clips: int = 3,
) -> list[Path]:
    """Download b-roll video clips for extracted script keywords (future use)."""
    return download_broll_clips_for_keywords(
        extract_keywords(script_text),
        output_dir,
        api_key=api_key,
        max_clips=max_clips,
    )
