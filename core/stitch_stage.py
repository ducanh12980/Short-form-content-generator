"""Simple asset stitcher — combine user-provided images, TTS audio, and music into MP4."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

THEME_STYLES_PATH = _REPO_ROOT / "config" / "theme_styles.json"
FPS = 30


def get_audio_duration_ms(audio_path: str | Path) -> float:
    """Return duration of an audio file in milliseconds using mutagen."""
    try:
        from mutagen import File as MutagenFile
    except ImportError as exc:
        raise RuntimeError(
            "mutagen is required. Install it with: pip install mutagen"
        ) from exc

    path = Path(audio_path)
    if not path.is_file():
        raise FileNotFoundError(f"Audio file not found: {path}")

    audio = MutagenFile(str(path))
    if audio is None or audio.info is None:
        raise ValueError(f"Could not read audio metadata from: {path}")

    return audio.info.length * 1000.0


def _load_theme_styles() -> dict[str, Any]:
    return json.loads(THEME_STYLES_PATH.read_text(encoding="utf-8"))


def _normalize_font(font: str) -> str:
    aliases = {
        "Arial Bold": "Arial, Helvetica, sans-serif",
        "Impact": "Impact, Haettenschweiler, Arial Narrow Bold, sans-serif",
    }
    return aliases.get(font.strip(), font.strip())


def _normalize_themes(themes: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, theme in themes.items():
        if not isinstance(theme, dict):
            continue
        t = dict(theme)
        if isinstance(t.get("font"), str):
            t["font"] = _normalize_font(t["font"])
        result[name] = t
    return result


def build_stitch_props(
    image_paths: list[str | Path],
    audio_path: str | Path,
    *,
    music_path: str | Path | None = None,
    music_volume: float = 0.3,
    public_dir: str | Path,
    fps: int = FPS,
) -> tuple[dict[str, Any], Path]:
    """Build Remotion ShortVideoProps for the stitcher and return (props, public_dir).

    Copies all assets into public_dir so Remotion's staticFile() can resolve them.
    Image display time is divided equally across the full audio duration.
    """
    pub = Path(public_dir)
    pub.mkdir(parents=True, exist_ok=True)

    audio_src = Path(audio_path).resolve()
    dest_audio = pub / audio_src.name
    shutil.copy2(audio_src, dest_audio)

    duration_ms = get_audio_duration_ms(audio_src)

    n = len(image_paths)
    if n == 0:
        raise ValueError("At least one image is required.")

    # First and last slides get half the screen time of a content slide so the
    # opener/closer don't dominate. For N slides the unit is duration/(N-1),
    # giving: first=unit/2, middle×(N-2)=unit each, last=unit/2.
    # Total = unit/2 + (N-2)*unit + unit/2 = (N-1)*unit = duration. ✓
    # For N==1 the single slide fills the whole duration.
    if n == 1:
        slide_durations = [duration_ms]
    else:
        unit = duration_ms / (n - 1)
        slide_durations = [unit / 2] + [unit] * (n - 2) + [unit / 2]

    images_timeline: list[dict[str, Any]] = []
    cursor_ms = 0.0
    for i, img_path in enumerate(image_paths):
        src = Path(img_path).resolve()
        if not src.is_file():
            raise FileNotFoundError(f"Image not found: {src}")
        dest_img = pub / f"stitch_img_{i:03d}{src.suffix}"
        shutil.copy2(src, dest_img)
        start_ms = cursor_ms
        end_ms = cursor_ms + slide_durations[i]
        cursor_ms = end_ms
        images_timeline.append(
            {
                "src": dest_img.name,
                "start_ms": round(start_ms),
                "end_ms": round(end_ms),
            }
        )

    music_src_value: str | None = None
    if music_path is not None:
        music_src = Path(music_path).resolve()
        if not music_src.is_file():
            raise FileNotFoundError(f"Music file not found: {music_src}")
        dest_music = pub / music_src.name
        shutil.copy2(music_src, dest_music)
        music_src_value = dest_music.name

    themes = _normalize_themes(_load_theme_styles())

    props: dict[str, Any] = {
        "width": 1080,
        "height": 1920,
        "fps": fps,
        "durationMs": round(duration_ms),
        "themeName": "minimalist",
        "fontOverride": None,
        "themes": themes,
        "tokens": [],
        "narrationSrc": dest_audio.name,
        "images": images_timeline,
        "backgroundColor": "#000000",
        "musicSrc": music_src_value,
        "musicVolume": music_volume,
    }

    return props, pub


def run_stitch(
    image_paths: list[str | Path],
    audio_path: str | Path,
    output_path: str | Path,
    *,
    music_path: str | Path | None = None,
    music_volume: float = 0.3,
    fps: int = FPS,
) -> Path:
    """Stitch images + audio (+ optional music) into an MP4.

    Returns the resolved output path.
    """
    from core.remotion_render_stage import render_with_remotion

    out = Path(output_path).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    public_dir = out.parent / "stitch_public"
    props, pub = build_stitch_props(
        image_paths,
        audio_path,
        music_path=music_path,
        music_volume=music_volume,
        public_dir=public_dir,
        fps=fps,
    )

    return render_with_remotion(props, out, public_dir=pub)
