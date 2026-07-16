"""Remotion render stage — bridge project.json to Remotion ShortVideo composition."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core.pipeline_log import log_step, log_step_done
from core.audio_volume import resolve_narration_volume
from core.project_schema import (
    get_ambient_overlay,
    get_canvas_size,
    get_caption_settings,
    get_caption_tokens,
    get_music_settings,
    get_narration_duration_ms,
    get_narration_path,
    load_project,
    resolve_slide_transition,
)

# Portrait 9:16 — must match remotion/src/types.ts CANVAS_WIDTH / CANVAS_HEIGHT
CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1920


def _format_duration_ms(ms: int) -> str:
    if ms >= 60_000:
        minutes, seconds = divmod(ms / 1000, 60)
        return f"{int(minutes)}m {seconds:.1f}s"
    if ms >= 1000:
        return f"{ms / 1000:.1f}s"
    return f"{ms}ms"


def _format_file_size(path: Path) -> str:
    size = path.stat().st_size
    if size >= 1_048_576:
        return f"{size / 1_048_576:.1f} MB"
    if size >= 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size} B"


def _summarize_render_props(props: dict[str, Any]) -> str:
    parts = [
        f"{props['width']}x{props['height']} @ {props['fps']}fps",
        f"duration {_format_duration_ms(int(props['durationMs']))}",
        f"{len(props.get('images', []))} slides",
        f"{len(props.get('tokens', []))} caption tokens",
    ]
    if props.get("musicSrc"):
        parts.append("music")
    if props.get("ambientOverlaySrc"):
        parts.append("ambient overlay")
    return ", ".join(parts)


_RENDER_PROGRESS_RE = re.compile(
    r"^Rendered (\d+)/(\d+), time remaining: (.+)$"
)


def _remotion_progress_frame(line: str) -> str | None:
    """Return rendered frame number when line is a Remotion progress update."""
    match = _RENDER_PROGRESS_RE.match(line.strip())
    return match.group(1) if match else None


def _should_emit_remotion_line(
    line: str,
    *,
    last_line: str | None,
    last_progress_frame: str | None,
) -> tuple[bool, str | None, str | None]:
    """Drop duplicate Remotion progress lines when stdout is piped (non-TTY)."""
    stripped = line.rstrip("\n")
    if stripped == last_line:
        return False, last_line, last_progress_frame

    frame = _remotion_progress_frame(stripped)
    if frame is not None and frame == last_progress_frame:
        return False, last_line, last_progress_frame

    next_progress_frame = frame if frame is not None else None
    return True, stripped, next_progress_frame


def _run_remotion_cli(cmd: list[str], *, cwd: Path, env: dict[str, str]) -> None:
    """Run Remotion CLI and stream combined stdout/stderr to the terminal."""
    log_step("Remotion CLI", " ".join(cmd))

    # On a real terminal, inherit stdio so Remotion can overwrite progress in place.
    if sys.stdout.isatty():
        returncode = subprocess.run(cmd, cwd=cwd, env=env, check=False).returncode
        if returncode != 0:
            raise RuntimeError(f"Remotion render failed (exit {returncode}).")
        return

    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    output_lines: list[str] = []
    last_line: str | None = None
    last_progress_frame: str | None = None
    assert proc.stdout is not None
    for line in proc.stdout:
        emit, last_line, last_progress_frame = _should_emit_remotion_line(
            line,
            last_line=last_line,
            last_progress_frame=last_progress_frame,
        )
        if not emit:
            continue
        output_lines.append(last_line or "")
        print(last_line, flush=True)

    returncode = proc.wait()
    if returncode != 0:
        tail = "\n".join(output_lines[-20:]).strip()
        raise RuntimeError(
            f"Remotion render failed (exit {returncode})."
            + (f"\n{tail}" if tail else "")
        )


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


def _is_under_dir(path: Path, base_dir: Path) -> bool:
    """Return True when path resolves inside base_dir (Python 3.8-safe)."""
    try:
        path.resolve().relative_to(base_dir.resolve())
        return True
    except ValueError:
        return False


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
    for index, image in enumerate(images):
        if not isinstance(image, dict) or not image.get("path"):
            continue
        resolved = Path(str(image["path"])).resolve()
        entry: dict[str, Any] = {
            "src": _to_static_src(resolved, public_dir),
            "start_ms": int(image.get("start_ms", 0)),
            "end_ms": int(image.get("end_ms", 0)),
            "source": image.get("source"),
            "media_type": image.get("media_type"),
            "transition": resolve_slide_transition(image, index),
        }
        timeline.append(entry)
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
    images = _resolve_image_timeline(project, public_dir)
    # The end card sits past the last spoken word, so the timeline — not narration
    # alone — decides how long the composition runs.
    timeline_end_ms = max((int(image["end_ms"]) for image in images), default=0)
    duration_ms = max(duration_ms, timeline_end_ms)

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
        "narrationVolume": resolve_narration_volume(),
        "images": images,
        "backgroundColor": background_color,
    }

    music_settings = get_music_settings(project)
    if music_settings is not None:
        music_path = music_settings["path"].resolve()
        if music_path.is_file():
            if not _is_under_dir(music_path, public_dir):
                staged = public_dir / music_path.name
                if staged.resolve() != music_path:
                    shutil.copy2(music_path, staged)
                music_path = staged
            props["musicSrc"] = _to_static_src(music_path, public_dir)
            props["musicVolume"] = music_settings["volume"]

    ambient_settings = get_ambient_overlay(project)
    if ambient_settings is not None:
        overlay_path = ambient_settings["path"].resolve()
        if overlay_path.is_file():
            if not _is_under_dir(overlay_path, public_dir):
                staged = public_dir / overlay_path.name
                if staged.resolve() != overlay_path:
                    shutil.copy2(overlay_path, staged)
                overlay_path = staged
            props["ambientOverlaySrc"] = _to_static_src(overlay_path, public_dir)
            props["ambientOpacity"] = ambient_settings["opacity"]
            props["ambientBlendMode"] = ambient_settings["blend_mode"]
            props["ambientLoopDurationMs"] = ambient_settings["duration_ms"]
            rate = float(ambient_settings.get("playback_rate", 1.0))
            if rate > 0 and rate != 1.0:
                props["ambientPlaybackRate"] = rate

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
    log_step("Remotion render", _summarize_render_props(props))

    props_path = out.with_suffix(".remotion-props.json")
    props_path.write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")
    log_step_done("write Remotion props", props_path.name)

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
        log_step_done("public assets dir", str(public_dir.resolve()))

    env = _render_env()
    try:
        _run_remotion_cli(cmd, cwd=work_dir, env=env)
    finally:
        props_path.unlink(missing_ok=True)

    if not out.is_file():
        raise RuntimeError(f"Remotion render did not produce output: {out}")

    log_step_done("Remotion render", f"{out.name} ({_format_file_size(out)})")
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
    project_file = Path(project_path)
    run_dir = project_file.parent.resolve()
    log_step("Remotion render stage", str(project_file.name))

    project = load_project(project_path)
    log_step_done("load project", str(project_file.resolve()))

    if _ensure_project_music(project, run_dir):
        _persist_project(project_file, project)
        log_step_done("background music", project["audio"]["music"]["original_name"])

    props, public_dir = project_to_remotion_props(
        project,
        background_color=background_color,
        fps=fps,
    )
    log_step_done("build Remotion props", _summarize_render_props(props))

    default_out = project_file.parent / "final.mp4"
    final_out = render_with_remotion(
        props,
        output_path or default_out,
        public_dir=public_dir,
    )
    _record_render_final_path(project_file, project, final_out)
    log_step_done("save render metadata", f"render.final_path → {final_out.name}")
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
        print(f"[PIPELINE] ✓ final video — {out.resolve()}")
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"Remotion render failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
