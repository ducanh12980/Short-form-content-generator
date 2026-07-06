"""Caption render stage — partial re-render via Remotion (project captions → preview MP4)."""

from __future__ import annotations

from pathlib import Path

from core.remotion_render_stage import render_project_video


def render_caption_preview(
    project_path: str | Path,
    output_path: str | Path | None = None,
    *,
    background_color: tuple[int, int, int] = (0, 0, 0),
) -> Path:
    """Render styled captions and optional b-roll from project JSON via Remotion.

    Goal: Produce caption_preview.mp4 for review or partial re-render after UI edits.
    Params: project_path — path to project.json or pipeline_payload.json;
        output_path — optional MP4 destination; background_color — RGB base fill.
    Output: Absolute path to the written preview MP4 file.
    """
    r, g, b = background_color
    hex_color = f"#{r:02x}{g:02x}{b:02x}"
    return render_project_video(
        project_path,
        output_path,
        background_color=hex_color,
    )


def main() -> None:
    """CLI entry point for caption preview render from a project JSON file."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Render styled captions from project.json or pipeline_payload.json.",
    )
    parser.add_argument(
        "project",
        nargs="?",
        default="output/pipeline_payload.json",
        help="Path to project or pipeline_payload JSON",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Output MP4 path (default: beside project as caption_preview.mp4)",
    )
    args = parser.parse_args()

    try:
        out = render_caption_preview(args.project, args.output)
        print(f"Caption preview: {out}")
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"Caption render failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
