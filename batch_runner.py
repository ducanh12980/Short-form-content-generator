"""CLI entry point: process pending video jobs from a CSV queue."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from core.batch_runner import (
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
        "--max-jobs",
        type=int,
        default=1,
        metavar="N",
        help="Pending rows to process per invocation (default: 1 — one video per daily cron run)",
    )
    parser.add_argument(
        "--output-base",
        default="output/batch",
        help="Base directory for per-job artifacts (default: output/batch)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List pending jobs without running the pipeline",
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
            output_base=args.output_base,
            dry_run=args.dry_run,
        )

        if not results:
            print("No pending jobs.")
            return

        for item in results:
            status = item["status"]
            job_id = item["id"]
            if status == "dry_run":
                print(f"[dry-run] would process job {job_id}: {item.get('topic', '')}")
            elif status == "done":
                print(f"Job {job_id} done → {item['output_path']}")
            else:
                print(f"Job {job_id} failed: {item.get('error', 'unknown error')}", file=sys.stderr)

        failed = sum(1 for item in results if item["status"] == "failed")
        if failed:
            raise SystemExit(1)

    except BatchLockError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(0) from exc
    except (BatchRunnerError, ValueError, FileNotFoundError, RuntimeError) as exc:
        print(f"Batch runner failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
