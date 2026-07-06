"""Remotion render stage — bridge project.json to Remotion ShortVideo composition."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core.project_schema import (
    get_canvas_size,
    get_caption_settings,
    get_caption_tokens,
    get_music_settings,
    get_narration_duration_ms,
    get_narration_path,
    load_project,
)

# Portrait 9:16 — must match remotion/src/types.ts CANVAS_WIDTH / CANVAS_HEIGHT
CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1920


def _normalize_canvas_props(props: dict[str, Any]) -> dict[str, Any]:
    """Force portrait 9:16 even if props carry swapped landscape dimensions."""
    w = int(props.get("width", CANVAS_WIDTH))
    h = int(props.get("height", CANVAS_HEIGHT))
    if w > h:
        w, h = h, w
    props = dict(props)
    props["width"] = w
    props["height"] = h
    return props

REMOTION_DIR = Path(__file__).resolve().parent.parent / "remotion"
THEME_STYLES_PATH = Path(__file__).resolve().parent.parent / "config" / "theme_styles.json"
COMPOSITION_ID = "ShortVideo"
ENTRY_POINT = "src/index.ts"


def _nodejs_bin_dirs() -> list[Path]:
    """Return common Node.js install directories (PATH may be stale after install)."""
    dirs: list[Path] = []
    program_files = os.environ.get("ProgramFiles")
    if program_files:
        dirs.append(Path(program_files) / "nodejs")
    local_app = os.environ.get("LOCALAPPDATA")
    if local_app:
        dirs.append(Path(local_app) / "Programs" / "node")
    return dirs


def _resolve_npx() -> str:
    """Return an npx executable that works on Windows and Unix."""
    for candidate in ("npx.cmd", "npx"):
        found = shutil.which(candidate)
        if found:
            return found

    for node_dir in _nodejs_bin_dirs():
        for candidate in ("npx.cmd", "npx"):
            path = node_dir / candidate
            if path.is_file():
                return str(path)

    raise RuntimeError(
        "npx not found. Install Node.js 18+ from https://nodejs.org/, "
        "restart your terminal, then run: cd remotion && npm install"
    )


def _render_env() -> dict[str, str]:
    """Build subprocess env with Node.js on PATH when the shell session is stale."""
    env = os.environ.copy()
    path_parts = [env["PATH"]] if env.get("PATH") else []
    for node_dir in _nodejs_bin_dirs():
        if node_dir.is_dir():
            node_path = str(node_dir)
            if node_path not in env.get("PATH", ""):
                path_parts.insert(0, node_path)
    if path_parts:
        env["PATH"] = ";".join(path_parts) if sys.platform == "win32" else ":".join(path_parts)
    return env


def _load_theme_styles() -> dict[str, Any]:
    return json.loads(THEME_STYLES_PATH.read_text(encoding="utf-8"))


def _remotion_font_name(logical_font: str) -> str:
    """Map theme font labels to CSS-friendly family names for Remotion."""
    normalized = logical_font.strip()
    aliases = {
        "Arial Bold": "Arial, Helvetica, sans-serif",
        "Impact": "Impact, Haettenschweiler, Arial Narrow Bold, sans-serif",
    }
    return aliases.get(normalized, normalized)


def _normalize_themes_for_remotion(themes: dict[str, Any]) -> dict[str, Any]:
    remotion_themes: dict[str, Any] = {}
    for name, theme in themes.items():
        if not isinstance(theme, dict):
            continue
        remotion_theme = dict(theme)
        if isinstance(remotion_theme.get("font"), str):
            remotion_theme["font"] = _remotion_font_name(remotion_theme["font"])
        remotion_themes[name] = remotion_theme
    return remotion_themes


def _to_static_src(path: Path, public_dir: Path) -> str:
    """Return a POSIX path relative to the Remotion public directory."""
    return path.resolve().relative_to(public_dir.resolve()).as_posix()


def _resolve_image_timeline(
    project: dict[str, Any],
    public_dir: Path,
) -> list[dict[str, Any]]:
    video = project.get("video", {})
    images = video.get("images", [])
    if not isinstance(images, list):
        return []

    timeline: list[dict[str, Any]] = []
    for image in images:
        if not isinstance(image, dict) or not image.get("path"):
            continue
        resolved = Path(str(image["path"])).resolve()
        timeline.append(
            {
                "src": _to_static_src(resolved, public_dir),
                "start_ms": int(image.get("start_ms", 0)),
                "end_ms": int(image.get("end_ms", 0)),
                "source": image.get("source"),
                "media_type": image.get("media_type"),
            }
        )
    return timeline


def project_to_remotion_props(
    project: dict[str, Any],
    *,
    background_color: str = "#000000",
    fps: int = 30,
) -> dict[str, Any]:
    """Build Remotion ShortVideo props from a normalized project dict.

    Goal: Single adapter from project.json to the Remotion composition contract.
    Params: project — normalized project dict; background_color — canvas fill;
        fps — output frame rate.
    Output: JSON-serializable props for `remotion render --props`.
    """
    width, height = get_canvas_size(project)
    settings = get_caption_settings(project)
    tokens = get_caption_tokens(project)
    narration_path = get_narration_path(project)
    duration_ms = get_narration_duration_ms(project)
    if duration_ms <= 0:
        duration_ms = 3000

    font_override = settings["font_override"]
    public_dir = narration_path.resolve().parent
    props: dict[str, Any] = {
        "width": width,
        "height": height,
        "fps": fps,
        "durationMs": duration_ms,
        "themeName": settings["theme_name"],
        "fontOverride": _remotion_font_name(font_override) if font_override else None,
        "themes": _normalize_themes_for_remotion(_load_theme_styles()),
        "tokens": tokens,
        "narrationSrc": _to_static_src(narration_path, public_dir),
        "images": _resolve_image_timeline(project, public_dir),
        "backgroundColor": background_color,
    }

    music_settings = get_music_settings(project)
    if music_settings is not None:
        music_path = music_settings["path"].resolve()
        if music_path.is_file():
            if not music_path.is_relative_to(public_dir.resolve()):
                staged = public_dir / music_path.name
                if staged.resolve() != music_path:
                    shutil.copy2(music_path, staged)
                music_path = staged
            props["musicSrc"] = _to_static_src(music_path, public_dir)
            props["musicVolume"] = music_settings["volume"]

    return props, public_dir


def _ensure_project_music(project: dict[str, Any], run_dir: Path) -> bool:
    """Attach random music to the project when missing; stage file in run_dir."""
    if get_music_settings(project) is not None:
        return False

    from core.music_picker import attach_random_music

    music = attach_random_music(run_dir)
    if music is None:
        return False

    audio = project.setdefault("audio", {})
    audio["music"] = music
    return True


def _persist_project(project_path: Path, project: dict[str, Any]) -> None:
    project_path.write_text(
        json.dumps(project, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _record_render_final_path(
    project_path: Path,
    project: dict[str, Any],
    final_mp4: Path,
) -> None:
    """Persist render.final_path beside other run artifacts."""
    render = project.setdefault("render", {})
    render["output_dir"] = str(project_path.parent.resolve())
    render["final_path"] = str(final_mp4.resolve())
    _persist_project(project_path, project)


def _ensure_remotion_ready() -> None:
    if not REMOTION_DIR.is_dir():
        raise RuntimeError(f"Remotion package not found at {REMOTION_DIR}")
    if not (REMOTION_DIR / "node_modules").is_dir():
        raise RuntimeError(
            f"Remotion dependencies missing. Run: cd remotion && npm install"
        )


def render_with_remotion(
    props: dict[str, Any],
    output_path: str | Path,
    *,
    remotion_dir: Path | None = None,
    public_dir: Path | None = None,
) -> Path:
    """Invoke Remotion CLI to render ShortVideo to an MP4 file.

    Goal: Headless export from composition props; used by caption render stage.
    Params: props — ShortVideo props dict; output_path — destination MP4;
        remotion_dir — optional override for the Remotion package root.
    Output: Resolved path to the rendered MP4.
    """
    _ensure_remotion_ready()
    work_dir = remotion_dir or REMOTION_DIR
    out = Path(output_path).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    props = _normalize_canvas_props(props)

    props_path = out.with_suffix(".remotion-props.json")
    props_path.write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")

    npx = _resolve_npx()
    cmd = [
        npx,
        "remotion",
        "render",
        ENTRY_POINT,
        COMPOSITION_ID,
        str(out),
        "--props",
        str(props_path),
    ]
    if public_dir is not None:
        cmd.extend(["--public-dir", str(public_dir.resolve())])

    env = _render_env()
    try:
        subprocess.run(
            cmd,
            cwd=work_dir,
            check=True,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        raise RuntimeError(
            f"Remotion render failed (exit {exc.returncode}). {detail}"
        ) from exc
    finally:
        props_path.unlink(missing_ok=True)

    if not out.is_file():
        raise RuntimeError(f"Remotion render did not produce output: {out}")

    return out


def render_project_video(
    project_path: str | Path,
    output_path: str | Path | None = None,
    *,
    background_color: str = "#000000",
    fps: int = 30,
) -> Path:
    """Render a project JSON file to MP4 via Remotion.

    Goal: Main video export entry point for preview and final output.
    Params: project_path — project.json or pipeline_payload.json;
        output_path — optional MP4 path; background_color — canvas fill; fps — frame rate.
    Output: Resolved path to rendered MP4.
    """
    project = load_project(project_path)
    project_file = Path(project_path)
    run_dir = project_file.parent

    if _ensure_project_music(project, run_dir):
        _persist_project(project_file, project)
        print(f"Background music: {project['audio']['music']['original_name']}")

    props, public_dir = project_to_remotion_props(
        project,
        background_color=background_color,
        fps=fps,
    )

    project_file = Path(project_path)
    default_out = project_file.parent / "final.mp4"
    final_out = render_with_remotion(
        props,
        output_path or default_out,
        public_dir=public_dir,
    )
    _record_render_final_path(project_file, project, final_out)
    return final_out


def main() -> None:
    """CLI entry point for Remotion render from a project JSON file."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Render project.json or pipeline_payload.json via Remotion.",
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
        help="Output MP4 path (default: beside project as final.mp4)",
    )
    parser.add_argument(
        "--background-color",
        default="#000000",
        help="Canvas background color when no b-roll images (default: #000000)",
    )
    args = parser.parse_args()

    try:
        out = render_project_video(
            args.project,
            args.output,
            background_color=args.background_color,
        )
        print(f"Remotion render: {out}")
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"Remotion render failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
