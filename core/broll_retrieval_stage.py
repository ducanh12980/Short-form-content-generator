"""B-roll retrieval stage — download Pexels stock images and populate video.images[]."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from core.media_retriever import derive_search_keywords, download_images_for_keywords
from core.project_schema import (
    get_images_dir,
    get_narration_duration_ms,
    get_raw_script,
    get_topic,
    load_project,
    save_project,
)


def _existing_image_paths(project: dict[str, Any]) -> list[Path]:
    video = project.get("video", {})
    images = video.get("images", [])
    if not isinstance(images, list):
        return []
    paths: list[Path] = []
    for image in images:
        if isinstance(image, dict) and image.get("path"):
            paths.append(Path(str(image["path"])))
    return paths


def _build_image_timeline(
    image_paths: list[Path],
    duration_ms: int,
) -> list[dict[str, Any]]:
    """Assign sequential start/end slots across the narration duration."""
    if not image_paths:
        return []

    total = max(duration_ms, 1000)
    slot_ms = max(total // len(image_paths), 500)
    timeline: list[dict[str, Any]] = []
    cursor = 0

    for index, image_path in enumerate(image_paths):
        start_ms = cursor
        end_ms = total if index == len(image_paths) - 1 else min(cursor + slot_ms, total)
        timeline.append(
            {
                "path": str(image_path.resolve()),
                "start_ms": start_ms,
                "end_ms": end_ms,
                "source": "pexels",
                "media_type": "image",
            }
        )
        cursor = end_ms

    return timeline


def retrieve_broll(
    project_path: str | Path,
    *,
    force: bool = False,
    max_images: int = 3,
    api_key: str | None = None,
) -> list[Path]:
    """Download background images for the project and write video.images to the project file.

    Goal: Populate editable image timeline entries for downstream video compositor.
    Video clips (video.clips[]) are deferred — see media_retriever.download_broll_clips_for_keywords.
    Params: project_path — path to project.json or pipeline_payload.json;
        force — re-fetch even when images already exist; max_images — download cap;
        api_key — optional Pexels API key override.
    Output: List of downloaded image paths.
    """
    project_file = Path(project_path)
    project = load_project(project_file)

    if not force:
        existing = _existing_image_paths(project)
        if existing:
            return existing

    raw_script = get_raw_script(project)
    topic = get_topic(project)
    if not raw_script and not topic:
        raise ValueError("Project must include raw_script or topic for b-roll search.")

    keywords = derive_search_keywords(raw_script, topic, max_keywords=max_images)
    if not keywords:
        raise ValueError("Could not derive search keywords from project script or topic.")

    key = api_key or os.environ.get("PEXELS_API_KEY")
    if not key:
        raise RuntimeError(
            "Missing PEXELS_API_KEY. Copy .env.example to .env and add your Pexels API key."
        )

    images_dir = get_images_dir(project)
    image_paths = download_images_for_keywords(
        keywords,
        images_dir,
        api_key=key,
        max_images=max_images,
    )
    if not image_paths:
        raise RuntimeError(
            "Pexels returned no downloadable images for keywords: "
            + ", ".join(keywords)
        )

    duration_ms = get_narration_duration_ms(project)
    timeline = _build_image_timeline(image_paths, duration_ms)

    video = project.setdefault("video", {})
    video.setdefault("canvas", {"width": 1080, "height": 1920})
    video.setdefault("clips", [])  # video clips — low priority / future
    video["images"] = timeline

    save_project(project, project_file)
    return image_paths


def main() -> None:
    """CLI entry point for background image retrieval from a project JSON file."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Download Pexels background images and update video.images in project JSON.",
    )
    parser.add_argument(
        "project",
        nargs="?",
        default="output/pipeline_payload.json",
        help="Path to project or pipeline_payload JSON",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download images even when video.images is already populated",
    )
    parser.add_argument(
        "--max-images",
        type=int,
        default=3,
        help="Maximum number of images to download (default: 3)",
    )
    args = parser.parse_args()

    try:
        images = retrieve_broll(
            args.project,
            force=args.force,
            max_images=args.max_images,
        )
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"B-roll retrieval failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print(f"Updated project: {Path(args.project).resolve()}")
    for image in images:
        print(f"  {image.resolve()}")


if __name__ == "__main__":
    main()
