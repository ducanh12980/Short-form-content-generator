"""Unified CLI for multi-platform video publish after render."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core.publish.common import PublishError
from core.publish.registry import ADAPTERS, get_enabled_platforms


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(_REPO_ROOT / ".env")


def publish_video(
    video_path: str | Path,
    *,
    jobs_csv: str | Path | None = None,
    caption: str | None = None,
    payload_path: str | Path | None = None,
    platforms: list[str] | None = None,
) -> bool:
    """
    Publish video to configured platforms.

    Returns True when all attempted platforms succeed or skip; False on any failure.
    """
    resolved_platforms = platforms if platforms is not None else get_enabled_platforms()
    if not resolved_platforms:
        print("[publish] skipped (PUBLISH_PLATFORMS not set)")
        return True

    had_failure = False
    for name in resolved_platforms:
        adapter = ADAPTERS.get(name)
        if adapter is None:
            print(f"[publish] warning: unknown platform '{name}' — skipped")
            continue
        try:
            adapter(
                video_path,
                jobs_csv=jobs_csv,
                caption=caption,
                payload_path=payload_path,
            )
        except PublishError as exc:
            print(f"[{name}] publish failed: {exc}", file=sys.stderr)
            had_failure = True
    return not had_failure


def main() -> None:
    _load_env()
    parser = argparse.ArgumentParser(
        description="Publish a rendered MP4 to configured platforms.",
    )
    parser.add_argument("video", help="Path to final.mp4")
    parser.add_argument(
        "--jobs-csv",
        default=os.environ.get("JOBS_CSV", "jobs.csv"),
        help="Caption fallback from latest done row (default: JOBS_CSV or jobs.csv)",
    )
    parser.add_argument(
        "--caption",
        default=None,
        help="Override caption (default: pipeline_payload.json publish, else jobs.csv)",
    )
    parser.add_argument(
        "--payload",
        default=None,
        help="Path to pipeline_payload.json (default: next to the video file)",
    )
    parser.add_argument(
        "--platforms",
        default=None,
        help="Comma-separated platform list (overrides PUBLISH_PLATFORMS env)",
    )

    args = parser.parse_args()
    platforms = get_enabled_platforms(cli_override=args.platforms) if args.platforms else None

    if not publish_video(
        args.video,
        jobs_csv=args.jobs_csv,
        caption=args.caption,
        payload_path=args.payload,
        platforms=platforms,
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
