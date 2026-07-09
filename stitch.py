"""CLI entry point: stitch images + TTS audio + optional music into a TikTok MP4.

Each run produces an isolated folder under output/stitch/<YYYYMMDD_HHMMSS>/ that
contains the rendered MP4 and a stitch_public/ sub-directory with all copied assets.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from argcomplete import autocomplete
    from argcomplete.completers import FilesCompleter
    _ARGCOMPLETE = True
except ImportError:
    _ARGCOMPLETE = False

from core.audio_volume import DEFAULT_MUSIC_VOLUME, resolve_music_volume
from core.run_output import STITCH_BASE, new_run_dir

def main() -> None:
    run_dir = new_run_dir(STITCH_BASE)
    default_output = run_dir / "stitch.mp4"

    parser = argparse.ArgumentParser(
        prog="stitch",
        description=(
            "Combine images, TTS audio, and optional background music into a "
            "1080×1920 MP4 (TikTok canvas). Images are shown for equal durations "
            "across the full audio length, with a fade-in transition between slides. "
            f"Artifacts are written to output/stitch/<run-id>/ by default."
        ),
    )
    _images_arg = parser.add_argument(
        "--images",
        nargs="+",
        required=True,
        metavar="IMG",
        help="One or more image paths, in display order.",
    )
    _audio_arg = parser.add_argument(
        "--audio",
        required=True,
        metavar="AUDIO",
        help="TTS narration audio file (MP3/WAV). Drives total video duration.",
    )
    _music_arg = parser.add_argument(
        "--music",
        default=None,
        metavar="MUSIC",
        help="Optional background music file (MP3). Mixed at lower volume.",
    )
    parser.add_argument(
        "--music-volume",
        type=float,
        default=None,
        metavar="VOL",
        help=f"Background music volume (0–1). Default: MUSIC_VOLUME env or {DEFAULT_MUSIC_VOLUME}.",
    )
    _output_arg = parser.add_argument(
        "--output",
        "-o",
        default=str(default_output),
        metavar="OUT",
        help=f"Output MP4 path. Default: {default_output}.",
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=30,
        metavar="FPS",
        help="Frame rate. Default: 30.",
    )

    if _ARGCOMPLETE:
        _images_arg.completer = FilesCompleter(["jpg", "jpeg", "png", "webp"])  # type: ignore[attr-defined]
        _audio_arg.completer = FilesCompleter(["mp3", "wav", "m4a"])  # type: ignore[attr-defined]
        _music_arg.completer = FilesCompleter(["mp3", "wav", "m4a"])  # type: ignore[attr-defined]
        _output_arg.completer = FilesCompleter(["mp4"])  # type: ignore[attr-defined]
        autocomplete(parser)

    args = parser.parse_args()
    music_volume = resolve_music_volume(args.music_volume)

    try:
        from core.stitch_stage import run_stitch
    except ImportError as exc:
        print(f"Import error: {exc}", file=sys.stderr)
        print("Make sure you have installed dependencies: pip install -r requirements.txt", file=sys.stderr)
        raise SystemExit(1) from exc

    image_paths = [Path(p) for p in args.images]
    audio_path = Path(args.audio)
    music_path = Path(args.music) if args.music else None
    output_path = Path(args.output)

    missing = [str(p) for p in image_paths if not p.is_file()]
    if not audio_path.is_file():
        missing.append(str(audio_path))
    if music_path and not music_path.is_file():
        missing.append(str(music_path))
    if missing:
        for m in missing:
            print(f"File not found: {m}", file=sys.stderr)
        raise SystemExit(1)

    print(f"Run folder : {output_path.parent}")
    print(f"Images     : {len(image_paths)} file(s)")
    print(f"Audio      : {audio_path.name}")
    if music_path:
        print(f"Music      : {music_path.name} (volume {music_volume})")
    print(f"Output     : {output_path}")

    try:
        result = run_stitch(
            image_paths,
            audio_path,
            output_path,
            music_path=music_path,
            music_volume=music_volume,
            fps=args.fps,
        )
        print(f"Done: {result}")
    except (ValueError, FileNotFoundError, RuntimeError) as exc:
        print(f"Stitch failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
