#!/usr/bin/env python3
"""Pre-generate frozen script + slide images into assets/jobs/<id>/ for GitHub reuse.

Daily batch runs load these assets and only run TTS + Remotion + publish.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from dotenv import load_dotenv

from core.batch_runner import load_jobs
from core.job_assets import (
    has_complete_job_assets,
    job_assets_dir,
    job_images_dir,
    save_job_scenes_draft,
)
from core.pipeline_log import log_step_done
from core.project_schema import TOTAL_SLIDE_COUNT, get_content_slides
from core.slide_image_stage import generate_scene_images, resolve_image_provider
from core.slideshow_pipeline import (
    _attach_tts_to_content_slides,
    run_scene_script_writer,
    run_tts_writer,
)
from orchestrator_mvp import _get_client


def _load_env() -> None:
    load_dotenv(_REPO_ROOT / ".env")


def pregenerate_job(
    row: dict[str, str],
    *,
    force: bool = False,
    image_provider: str | None = None,
) -> str:
    """Freeze script + images for one CSV row. Returns status: created|skipped|error message."""
    job_id = row["id"].strip()
    topic = row["topic"].strip()
    if not job_id or not topic:
        return "error: missing id or topic"

    if has_complete_job_assets(job_id) and not force:
        return "skipped (already complete)"

    provider = resolve_image_provider(
        image_provider
        or (row.get("image_provider") or "").strip().lower()
        or None
    )

    assets_dir = job_assets_dir(job_id)
    assets_dir.mkdir(parents=True, exist_ok=True)
    images_dir = job_images_dir(job_id)

    client = _get_client()
    slides, publish = run_scene_script_writer(client, topic)
    log_step_done(
        "pregenerate script",
        f"job {job_id}: {TOTAL_SLIDE_COUNT} slides — \"{publish.get('title', '')}\"",
    )

    content_slides = get_content_slides(slides)
    tts_blocks = run_tts_writer(client, content_slides)
    _attach_tts_to_content_slides(content_slides, tts_blocks)
    log_step_done("pregenerate TTS writer", f"job {job_id}: {len(tts_blocks)} blocks")

    save_job_scenes_draft(job_id, topic=topic, slides=slides, publish=publish)

    project_stub = {"topic": topic, "slides": slides, "scenes": content_slides}
    generate_scene_images(
        project_stub,
        images_dir=images_dir,
        force=True,
        provider=provider,
    )
    log_step_done("pregenerate images", f"job {job_id}: {images_dir}")

    if not has_complete_job_assets(job_id):
        return "error: assets incomplete after generate"
    return "created"


def main() -> None:
    _load_env()
    default_csv = os.environ.get("JOBS_CSV", "jobs.csv")

    parser = argparse.ArgumentParser(
        description=(
            "Pre-generate scenes_draft.json + slide PNGs into assets/jobs/<id>/ "
            "for daily batch reuse on GitHub Actions."
        ),
    )
    parser.add_argument(
        "--csv",
        default=default_csv,
        help="Path to jobs CSV (default: JOBS_CSV or jobs.csv)",
    )
    parser.add_argument(
        "--job-id",
        default=None,
        help="Only pregenerate this job id (default: all rows)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate even when assets/jobs/<id>/ is already complete",
    )
    parser.add_argument(
        "--image-provider",
        default=None,
        help="Override IMAGE_PROVIDER / CSV image_provider for this run",
    )
    args = parser.parse_args()

    rows = load_jobs(args.csv)
    if args.job_id:
        target = args.job_id.strip()
        rows = [row for row in rows if row["id"].strip() == target]
        if not rows:
            print(f"No job with id={target!r} in {args.csv}", file=sys.stderr)
            raise SystemExit(1)

    if not rows:
        print("No jobs in CSV.")
        return

    failures = 0
    for row in rows:
        job_id = row["id"].strip()
        print(f"=== job {job_id}: {row['topic'][:60]} ===")
        try:
            status = pregenerate_job(
                row,
                force=args.force,
                image_provider=args.image_provider,
            )
        except Exception as exc:
            print(f"job {job_id} failed: {exc}", file=sys.stderr)
            failures += 1
            continue
        print(f"job {job_id}: {status}")
        if status.startswith("error"):
            failures += 1

    if failures:
        raise SystemExit(1)
    print("Done. Commit assets/jobs/ and push so GitHub Actions can reuse them.")


if __name__ == "__main__":
    main()
