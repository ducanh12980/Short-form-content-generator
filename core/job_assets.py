"""Per-job frozen script + slide images under assets/jobs/<id>/ (tracked in git)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from core.project_schema import (
    CONTENT_SCENE_COUNT,
    TOTAL_SLIDE_COUNT,
    get_content_slides,
    slide_image_filename,
)
from core.slideshow_pipeline import SCENES_DRAFT_FILENAME, parse_publish_metadata

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_JOBS_ASSETS_ROOT = REPO_ROOT / "assets" / "jobs"

REQUIRED_IMAGE_NAMES = (
    "intro.png",
    "scene_1.png",
    "scene_2.png",
    "scene_3.png",
    "ending.png",
)


class JobAssetsError(RuntimeError):
    """Raised when job library assets are missing or invalid."""


def jobs_assets_root(root: str | Path | None = None) -> Path:
    """Return the root directory for per-job asset libraries."""
    if root is not None and str(root).strip():
        return Path(root)
    return DEFAULT_JOBS_ASSETS_ROOT


def job_assets_dir(job_id: str, *, root: str | Path | None = None) -> Path:
    """Return assets/jobs/<job_id>/ for a job id."""
    cleaned = (job_id or "").strip()
    if not cleaned:
        raise ValueError("job_id must be non-empty.")
    if "/" in cleaned or "\\" in cleaned or cleaned in {".", ".."}:
        raise ValueError(f"Invalid job_id: {job_id!r}")
    return jobs_assets_root(root) / cleaned


def job_scenes_draft_path(job_id: str, *, root: str | Path | None = None) -> Path:
    return job_assets_dir(job_id, root=root) / SCENES_DRAFT_FILENAME


def job_images_dir(job_id: str, *, root: str | Path | None = None) -> Path:
    return job_assets_dir(job_id, root=root) / "images"


def expected_image_paths(job_id: str, *, root: str | Path | None = None) -> list[Path]:
    images = job_images_dir(job_id, root=root)
    return [images / name for name in REQUIRED_IMAGE_NAMES]


def has_complete_job_assets(job_id: str, *, root: str | Path | None = None) -> bool:
    """True when scenes_draft.json and all five slide PNGs exist."""
    draft = job_scenes_draft_path(job_id, root=root)
    if not draft.is_file():
        return False
    return all(path.is_file() for path in expected_image_paths(job_id, root=root))


def missing_job_asset_paths(job_id: str, *, root: str | Path | None = None) -> list[Path]:
    """List missing required files for a job library entry."""
    missing: list[Path] = []
    draft = job_scenes_draft_path(job_id, root=root)
    if not draft.is_file():
        missing.append(draft)
    for path in expected_image_paths(job_id, root=root):
        if not path.is_file():
            missing.append(path)
    return missing


def require_complete_job_assets(job_id: str, *, root: str | Path | None = None) -> Path:
    """Return job assets dir or raise JobAssetsError with a clear message."""
    if has_complete_job_assets(job_id, root=root):
        return job_assets_dir(job_id, root=root)
    missing = missing_job_asset_paths(job_id, root=root)
    rel = ", ".join(str(p) for p in missing[:6])
    raise JobAssetsError(
        f"Missing job assets for id={job_id!r}. "
        f"Run: python scripts/pregenerate_job_assets.py --csv jobs.csv --job-id {job_id}. "
        f"Missing: {rel}"
    )


def load_job_scenes_draft(
    job_id: str,
    *,
    topic: str,
    root: str | Path | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Load frozen slides + publish from assets/jobs/<id>/scenes_draft.json."""
    path = job_scenes_draft_path(job_id, root=root)
    if not path.is_file():
        raise JobAssetsError(f"Job assets draft not found: {path}")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise JobAssetsError(f"Invalid JSON in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise JobAssetsError(f"Job assets draft must be a JSON object: {path}")

    draft_topic = str(data.get("topic", "")).strip()
    if draft_topic != topic.strip():
        raise JobAssetsError(
            f"Job {job_id} assets topic mismatch: draft={draft_topic!r} job={topic.strip()!r}"
        )

    slides = data.get("slides")
    if not isinstance(slides, list) or len(slides) != TOTAL_SLIDE_COUNT:
        raise JobAssetsError(
            f"Job {job_id} draft must include exactly {TOTAL_SLIDE_COUNT} slides."
        )

    content_slides = get_content_slides(slides)
    if len(content_slides) != CONTENT_SCENE_COUNT:
        raise JobAssetsError(
            f"Job {job_id} draft must include exactly {CONTENT_SCENE_COUNT} content slides."
        )
    for slide in content_slides:
        if not isinstance(slide, dict) or not str(slide.get("tts", "")).strip():
            raise JobAssetsError(f"Job {job_id} draft content slides must include tts text.")

    publish_raw = data.get("publish")
    if not isinstance(publish_raw, dict):
        raise JobAssetsError(f"Job {job_id} draft must include publish metadata.")
    try:
        publish = parse_publish_metadata({"publish": publish_raw})
    except ValueError as exc:
        raise JobAssetsError(f"Job {job_id} draft publish invalid: {exc}") from exc

    return slides, publish


def save_job_scenes_draft(
    job_id: str,
    *,
    topic: str,
    slides: list[dict[str, Any]],
    publish: dict[str, Any],
    root: str | Path | None = None,
) -> Path:
    """Write scenes_draft.json into the job asset library."""
    dest_dir = job_assets_dir(job_id, root=root)
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = job_scenes_draft_path(job_id, root=root)
    payload = {"topic": topic.strip(), "slides": slides, "publish": publish}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def copy_job_images_into(
    run_dir: str | Path,
    job_id: str,
    *,
    root: str | Path | None = None,
    slides: list[dict[str, Any]] | None = None,
) -> list[Path]:
    """Copy library PNGs into run_dir/images/ and optionally attach paths on slides."""
    require_complete_job_assets(job_id, root=root)
    src_dir = job_images_dir(job_id, root=root)
    dest_dir = Path(run_dir) / "images"
    dest_dir.mkdir(parents=True, exist_ok=True)

    copied: list[Path] = []
    for src in expected_image_paths(job_id, root=root):
        dest = dest_dir / src.name
        shutil.copy2(src, dest)
        copied.append(dest.resolve())

    if slides is not None:
        for slide in slides:
            if not isinstance(slide, dict):
                continue
            name = slide_image_filename(slide)
            image_path = dest_dir / name
            if image_path.is_file():
                slide["image"] = {
                    "path": str(image_path.resolve()),
                    "source": "job_assets",
                }

    return copied


def attach_slide_images_from_dir(slides: list[dict[str, Any]], images_dir: Path) -> None:
    """Set slide.image.path from files already present under images_dir."""
    for slide in slides:
        if not isinstance(slide, dict):
            continue
        image_path = images_dir / slide_image_filename(slide)
        if not image_path.is_file():
            raise JobAssetsError(f"Expected slide image missing: {image_path}")
        slide["image"] = {
            "path": str(image_path.resolve()),
            "source": slide.get("image", {}).get("source", "job_assets")
            if isinstance(slide.get("image"), dict)
            else "job_assets",
        }
