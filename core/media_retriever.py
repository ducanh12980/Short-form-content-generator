"""Visual Sourcing Engine — keyword extraction and Pexels b-roll download."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import requests

PEXELS_VIDEO_SEARCH_URL = "https://api.pexels.com/videos/search"


def extract_keywords(script_text: str, *, max_keywords: int = 5) -> list[str]:
    """Pull high-emphasis keywords from script text for stock video search."""
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


def download_broll_clips(
    script_text: str,
    output_dir: str | Path,
    *,
    api_key: str | None = None,
    max_clips: int = 3,
) -> list[Path]:
    """Download b-roll clips for extracted script keywords into output_dir."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    downloaded: list[Path] = []
    for keyword in extract_keywords(script_text):
        if len(downloaded) >= max_clips:
            break

        videos = search_pexels_videos(keyword, api_key=api_key, per_page=1)
        if not videos:
            continue

        file_info = _pick_hd_file(videos[0])
        if not file_info or not file_info.get("link"):
            continue

        clip_path = output_path / f"{keyword}_{videos[0]['id']}.mp4"
        if clip_path.exists():
            downloaded.append(clip_path)
            continue

        video_response = requests.get(file_info["link"], timeout=120)
        video_response.raise_for_status()
        clip_path.write_bytes(video_response.content)
        downloaded.append(clip_path)

    return downloaded
