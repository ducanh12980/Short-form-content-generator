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
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from dotenv import load_dotenv

from core.batch_runner import is_quota_exhausted_error, load_jobs, select_pending_from_today
from core.job_assets import (
    format_inventory_summary,
    format_usage_summary,
    has_complete_job_assets,
    inventory_job_assets,
    job_assets_dir,
    job_images_dir,
    purge_job_images,
    save_job_image_usage,
    save_job_scenes_draft,
    summarize_image_usage,
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
    usage_out: list[dict[str, Any]] | None = None,
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

        stale = purge_job_images(job_id)
        if stale:
            log_step_done(
                "pregenerate images",
                f"job {job_id}: discarded {len(stale)} image(s) from the previous script "
                f"({', '.join(stale)})",
            )
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
    image_usage: list[dict[str, Any]] = []
    generate_scene_images(
        project_stub,
        images_dir=images_dir,
        force=force,
        provider=provider,
        usage_out=image_usage,
    )
    log_step_done("pregenerate images", f"job {job_id}: {images_dir}")

    if image_usage:
        usage_path = save_job_image_usage(job_id, topic=topic, records=image_usage)
        log_step_done(
            "pregenerate token usage",
            f"job {job_id}: {format_usage_summary(summarize_image_usage(image_usage))} "
            f"→ {usage_path.name}",
        )
        if usage_out is not None:
            usage_out.extend({**record, "job_id": job_id} for record in image_usage)

    # Mirror into canonical library layout (draft + images) for consistency
    save_job_scenes_draft(job_id, topic=topic, slides=slides, publish=publish)

    if not has_complete_job_assets(job_id):
        return "error: assets incomplete after generate"
    return "created" if not inventory["complete"] else "regenerated"


def format_run_usage_report(records: list[dict[str, Any]]) -> str:
    """Per-image token lines grouped by job, plus a run total."""
    lines = ["Prefill ảnh — token đã dùng"]
    for job_id in dict.fromkeys(str(record.get("job_id", "?")) for record in records):
        job_records = [r for r in records if str(r.get("job_id", "?")) == job_id]
        lines.append(f"\nJob {job_id}: {format_usage_summary(summarize_image_usage(job_records))}")
        for record in job_records:
            tokens = format_usage_summary(summarize_image_usage([record])).split(" — ", 1)
            detail = tokens[1] if len(tokens) > 1 else "tokens unavailable"
            lines.append(f"  • {record.get('image', '?')}: {detail}")
    lines.append(f"\nTổng: {format_usage_summary(summarize_image_usage(records))}")
    return "\n".join(lines)


def report_run_usage(records: list[dict[str, Any]], *, notify: bool) -> None:
    """Print the token report; optionally push the same text to Telegram."""
    if not records:
        print("No images generated — no token usage to report.")
        return

    report = format_run_usage_report(records)
    print(report)

    if not notify:
        return
    try:
        from core.telegram_notify import deliver_message

        deliver_message(report)
    except Exception as exc:
        # A reporting failure must never fail a prefill that produced real assets.
        print(f"[pregenerate] Telegram token report skipped: {exc}", file=sys.stderr)


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
    parser.add_argument(
        "--notify",
        action="store_true",
        help=(
            "Send a token summary via Telegram when images were generated "
            "(skipped when TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID are unset)"
        ),
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
    run_usage: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        job_id = row["id"].strip()
        print(f"=== job {job_id}: {row['topic'][:60]} ===")
        try:
            status = pregenerate_job(
                row,
                force=args.force,
                image_provider=args.image_provider,
                usage_out=run_usage,
            )
        except Exception as exc:
            print(f"job {job_id} failed: {exc}", file=sys.stderr)
            failures += 1
            # Free-tier Gemini quota is shared — every later job would fail the same way.
            if is_quota_exhausted_error(exc):
                remaining = len(rows) - index - 1
                if remaining:
                    print(
                        f"[pregenerate] stopping early after job {job_id}: API quota "
                        f"exhausted ({remaining} job(s) left for a later run).",
                        file=sys.stderr,
                        flush=True,
                    )
                break
            continue
        print(f"job {job_id}: {status}")
        if status.startswith("error"):
            failures += 1

    report_run_usage(run_usage, notify=args.notify)

    if failures:
        raise SystemExit(1)
    print("Done. Commit assets/jobs/ and push so GitHub Actions can reuse them.")


if __name__ == "__main__":
    main()
