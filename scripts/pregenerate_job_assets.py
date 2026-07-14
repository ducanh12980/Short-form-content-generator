#!/usr/bin/env python3
"""Pre-generate / fill frozen script + slide images into assets/jobs/<id>/.

Daily cron runs ``--from-today`` first to fill today + future pending jobs,
then the video batch reuses those assets (TTS + Remotion + publish only).
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

from core.batch_runner import load_jobs, select_pending_from_today
from core.job_assets import (
    format_inventory_summary,
    has_complete_job_assets,
    inventory_job_assets,
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
    """Fill script + images for one CSV row. Returns status label."""
    job_id = row["id"].strip()
    topic = row["topic"].strip()
    if not job_id or not topic:
        return "error: missing id or topic"

    inventory = inventory_job_assets(job_id, topic=topic)
    log_step_done(
        "pregenerate inventory",
        f"job {job_id}: {format_inventory_summary(inventory)}",
    )

    if inventory["complete"] and not force:
        return "skipped (already complete)"

    provider = resolve_image_provider(
        image_provider
        or (row.get("image_provider") or "").strip().lower()
        or None
    )

    assets_dir = job_assets_dir(job_id)
    assets_dir.mkdir(parents=True, exist_ok=True)
    images_dir = job_images_dir(job_id)
    images_dir.mkdir(parents=True, exist_ok=True)

    slides = inventory["slides"]
    publish = inventory["publish"]
    script_ok = bool(inventory["script_ok"]) and not force

    if not script_ok:
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
    else:
        assert slides is not None and publish is not None
        log_step_done(
            "pregenerate script",
            f"job {job_id}: reused scenes_draft.json",
        )

    assert slides is not None and publish is not None
    content_slides = get_content_slides(slides)
    project_stub = {"topic": topic, "slides": slides, "scenes": content_slides}

    # force=False → only generate PNGs still missing under images_dir
    generate_scene_images(
        project_stub,
        images_dir=images_dir,
        force=force,
        provider=provider,
    )
    log_step_done("pregenerate images", f"job {job_id}: {images_dir}")

    # Mirror into canonical library layout (draft + images) for consistency
    save_job_scenes_draft(job_id, topic=topic, slides=slides, publish=publish)

    if not has_complete_job_assets(job_id):
        return "error: assets incomplete after generate"
    return "created" if not inventory["complete"] else "regenerated"


def main() -> None:
    _load_env()
    default_csv = os.environ.get("JOBS_CSV", "jobs.csv")

    parser = argparse.ArgumentParser(
        description=(
            "Pre-generate / fill scenes_draft.json + slide PNGs into assets/jobs/<id>/ "
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
        help="Only pregenerate this job id (default: all rows, or --from-today)",
    )
    parser.add_argument(
        "--from-today",
        action="store_true",
        help=(
            "Only pending jobs with created_at date >= today (Asia/Ho_Chi_Minh). "
            "Skips complete libraries unless --force."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate script/images even when assets/jobs/<id>/ is already complete",
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
    elif args.from_today:
        rows = select_pending_from_today(rows)
        print(f"from-today: {len(rows)} pending job(s) with created_at >= today (VN)")

    if not rows:
        print("No jobs to pregenerate.")
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
