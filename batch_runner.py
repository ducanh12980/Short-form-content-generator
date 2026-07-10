"""CLI entry point: process pending video jobs from a CSV queue."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from core.batch_runner import (
    VALID_SELECT_MODES,
    BatchLockError,
    BatchRunnerError,
    init_jobs_csv,
    process_pending_jobs,
)


def _load_env() -> None:
    load_dotenv(Path(__file__).resolve().parent / ".env")


def main() -> None:
    _load_env()
    default_csv = os.environ.get("JOBS_CSV", "jobs.csv")

    parser = argparse.ArgumentParser(
        description="Process pending rows from a CSV job queue through the video pipeline.",
    )
    parser.add_argument(
        "--csv",
        default=default_csv,
        help=f"Path to jobs CSV (default: JOBS_CSV env or jobs.csv)",
    )
    parser.add_argument(
        "--select",
        choices=sorted(VALID_SELECT_MODES),
        default="pending",
        help=(
            "Which rows to process: pending (default), due-today "
            "(pending with created_at date == today VN), or failed (retry all failed)"
        ),
    )
    parser.add_argument(
        "--max-jobs",
        type=int,
        default=1,
        metavar="N",
        help="Rows to process per invocation (default: 1; 0 = all matched)",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help=(
            "Run folder for pipeline artifacts (default: output/final; "
            "cleared and recreated each job)"
        ),
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help="After each successful render, publish that MP4 via publish_runner",
    )
    parser.add_argument(
        "--allow-generate",
        action="store_true",
        help=(
            "Allow slideshow jobs without assets/jobs/<id>/ "
            "(calls LLM script + image APIs). Default requires pregenerated assets."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List selected jobs without running the pipeline",
    )
    parser.add_argument(
        "--init",
        action="store_true",
        help="Create a new jobs CSV with example pending rows, then exit",
    )
    parser.add_argument(
        "--no-examples",
        action="store_true",
        help="With --init, create headers only (no example rows)",
    )
    args = parser.parse_args()

    try:
        if args.init:
            path = init_jobs_csv(args.csv, examples=not args.no_examples)
            print(f"Created jobs CSV: {path.resolve()}")
            return

        results = process_pending_jobs(
            args.csv,
            max_jobs=args.max_jobs,
            output_dir=args.output_dir,
            dry_run=args.dry_run,
            select=args.select,
            publish=args.publish,
            require_job_assets=not args.allow_generate,
        )

        if not results:
            print(f"No jobs matched select={args.select!r}.")
            return

        for item in results:
            status = item["status"]
            job_id = item["id"]
            if status == "dry_run":
                print(f"[dry-run] would process job {job_id}: {item.get('topic', '')}")
            elif status == "done":
                pub = item.get("publish")
                suffix = f" (publish={pub})" if pub else ""
                print(f"Job {job_id} done → {item['output_path']}{suffix}")
            else:
                print(f"Job {job_id} failed: {item.get('error', 'unknown error')}", file=sys.stderr)

        failed = sum(1 for item in results if item["status"] == "failed")
        publish_failed = sum(1 for item in results if item.get("publish") == "failed")
        if failed or publish_failed:
            raise SystemExit(1)

    except BatchLockError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(0) from exc
    except (BatchRunnerError, ValueError, FileNotFoundError, RuntimeError) as exc:
        print(f"Batch runner failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
