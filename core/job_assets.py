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


def job_assets_dir_exists(job_id: str, *, root: str | Path | None = None) -> bool:
    """True when ``assets/jobs/<id>/`` exists as a directory."""
    return job_assets_dir(job_id, root=root).is_dir()


def has_all_required_images(job_id: str, *, root: str | Path | None = None) -> bool:
    """True when all five slide PNGs exist under ``assets/jobs/<id>/images/``."""
    return all(path.is_file() for path in expected_image_paths(job_id, root=root))


def has_complete_job_assets(job_id: str, *, root: str | Path | None = None) -> bool:
    """True when scenes_draft.json and all five slide PNGs exist (files only)."""
    draft = job_scenes_draft_path(job_id, root=root)
    if not draft.is_file():
        return False
    return has_all_required_images(job_id, root=root)


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


def try_load_job_scenes_draft(
    job_id: str,
    *,
    topic: str,
    root: str | Path | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]] | None:
    """Load draft when present and valid for topic (images may still be incomplete)."""
    if not job_scenes_draft_path(job_id, root=root).is_file():
        return None
    try:
        return load_job_scenes_draft(job_id, topic=topic, root=root)
    except JobAssetsError:
        return None


def try_load_reusable_job_assets(
    job_id: str,
    *,
    topic: str,
    root: str | Path | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]] | None:
    """Return slides+publish only when draft is valid **and** all images exist."""
    if not job_assets_dir_exists(job_id, root=root):
        return None
    if not has_all_required_images(job_id, root=root):
        return None
    return try_load_job_scenes_draft(job_id, topic=topic, root=root)


def missing_image_names(job_id: str, *, root: str | Path | None = None) -> list[str]:
    """Return required PNG filenames that are not yet on disk."""
    return [path.name for path in expected_image_paths(job_id, root=root) if not path.is_file()]


def inventory_job_assets(
    job_id: str,
    *,
    topic: str,
    root: str | Path | None = None,
) -> dict[str, Any]:
    """Scan **all** library parts once: script + each required PNG.

    Returns a dict used by the pipeline to fill only gaps::

        {
          "folder_exists": bool,
          "script_ok": bool,
          "slides": list | None,
          "publish": dict | None,
          "present_images": ["intro.png", ...],
          "missing_images": ["scene_2.png", ...],
          "complete": bool,  # script_ok and no missing images
        }

    Call this before any GPT work so one missing part still triggers a full
    scan of every remaining part.
    """
    folder_exists = job_assets_dir_exists(job_id, root=root)
    present_images: list[str] = []
    missing_images: list[str] = []
    for path in expected_image_paths(job_id, root=root):
        if path.is_file():
            present_images.append(path.name)
        else:
            missing_images.append(path.name)

    slides: list[dict[str, Any]] | None = None
    publish: dict[str, Any] | None = None
    script_ok = False
    if folder_exists or job_scenes_draft_path(job_id, root=root).is_file():
        loaded = try_load_job_scenes_draft(job_id, topic=topic, root=root)
        if loaded is not None:
            slides, publish = loaded
            script_ok = True

    return {
        "folder_exists": folder_exists,
        "script_ok": script_ok,
        "slides": slides,
        "publish": publish,
        "present_images": present_images,
        "missing_images": missing_images,
        "complete": script_ok and not missing_images,
    }


def format_inventory_summary(inventory: dict[str, Any]) -> str:
    """Human-readable one-line inventory for pipeline logs."""
    if inventory.get("complete"):
        return "complete (script + 5 images)"
    parts: list[str] = []
    if inventory.get("script_ok"):
        parts.append("script OK")
    else:
        parts.append("script MISSING")
    present = inventory.get("present_images") or []
    missing = inventory.get("missing_images") or []
    if present:
        parts.append(f"images present={','.join(present)}")
    if missing:
        parts.append(f"images missing={','.join(missing)}")
    elif not present:
        parts.append("images missing=all")
    return "; ".join(parts)


def purge_slide_images_in(images_dir: str | Path) -> list[str]:
    """Delete the canonical slide PNGs from a directory. Returns removed filenames.

    Slide images render the script, so a regenerated script leaves them showing
    content the narration no longer mentions.
    """
    directory = Path(images_dir)
    removed: list[str] = []
    for name in REQUIRED_IMAGE_NAMES:
        path = directory / name
        if path.is_file():
            path.unlink()
            removed.append(name)
    return removed


def purge_job_images(job_id: str, *, root: str | Path | None = None) -> list[str]:
    """Delete every library slide PNG for a job. Returns removed filenames."""
    return purge_slide_images_in(job_images_dir(job_id, root=root))


def copy_existing_job_images_into(
    run_dir: str | Path,
    job_id: str,
    *,
    root: str | Path | None = None,
    slides: list[dict[str, Any]] | None = None,
) -> list[Path]:
    """Copy whatever library PNGs already exist into run_dir/images/ (partial OK)."""
    src_dir = job_images_dir(job_id, root=root)
    dest_dir = Path(run_dir) / "images"
    dest_dir.mkdir(parents=True, exist_ok=True)

    copied: list[Path] = []
    if not src_dir.is_dir():
        return copied

    for src in expected_image_paths(job_id, root=root):
        if not src.is_file():
            continue
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
    """Copy all library PNGs into run_dir/images/ (requires a complete library)."""
    require_complete_job_assets(job_id, root=root)
    return copy_existing_job_images_into(run_dir, job_id, root=root, slides=slides)


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


def persist_job_assets_from_run_dir(
    job_id: str,
    run_dir: str | Path,
    *,
    topic: str,
    slides: list[dict[str, Any]],
    publish: dict[str, Any],
    root: str | Path | None = None,
) -> Path:
    """Save script draft + slide PNGs from a run folder into ``assets/jobs/<id>/``."""
    save_job_scenes_draft(
        job_id,
        topic=topic,
        slides=slides,
        publish=publish,
        root=root,
    )
    src_images = Path(run_dir) / "images"
    dest_images = job_images_dir(job_id, root=root)
    dest_images.mkdir(parents=True, exist_ok=True)
    for name in REQUIRED_IMAGE_NAMES:
        src = src_images / name
        if not src.is_file():
            raise JobAssetsError(f"Cannot persist job {job_id}: missing {src}")
        shutil.copy2(src, dest_images / name)
    return job_assets_dir(job_id, root=root)
