"""Typography Layout Canvas — composites timed, styled text layers over a base video clip using MoviePy and theme_styles.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from moviepy import CompositeVideoClip, TextClip, VideoClip

from core.font_resolver import resolve_font_path


def load_theme_styles(config_path: str | Path | None = None) -> dict[str, Any]:
    """Load typography presets from theme_styles.json.

    Goal: Provide per-theme font, color, and stroke defaults for caption layers.
    Params: config_path — optional path to JSON; defaults to config/theme_styles.json.
    Output: Dict mapping theme name to style properties.
    """
    path = Path(config_path or Path(__file__).resolve().parent.parent / "config" / "theme_styles.json")
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_style(
    token: dict[str, Any],
    themes: dict[str, Any],
    theme_name: str,
    *,
    font_override: str | None = None,
) -> dict[str, Any]:
    """Map a caption token and theme to MoviePy TextClip style kwargs.

    Goal: Resolve font, color, stroke, and animation for one token.
    Params: token — caption token (text, style, animation); themes — loaded theme dict;
        theme_name — preset key; font_override — optional project-level font name.
    Output: Dict with font, font_size, color, stroke_color, stroke_width, animation.
    """
    theme = themes.get(theme_name, themes.get("minimalist", {}))
    variant = token.get("style", "primary")
    if token.get("color"):
        color = token["color"]
    elif variant == "highlight":
        color = theme["highlight_color"]
    else:
        color = theme["primary_text_color"]
    logical_font = font_override or theme.get("font", "Arial Bold")
    return {
        "font": resolve_font_path(logical_font),
        "font_size": theme.get("font_size", 72),
        "color": color,
        "stroke_color": theme.get("stroke_color", "black"),
        "stroke_width": theme.get("stroke_width", 2),
        "animation": token.get("animation", "none"),
    }


def _resolve_timing(token: dict[str, Any]) -> dict[str, Any] | None:
    """Read start_ms/end_ms embedded on the token (written at TTS merge or UI edit time).

    Goal: Render uses persisted timing only — TTS alignment happens upstream, not here.
    Params: token — caption token with optional start_ms/end_ms or timing dict.
    Output: {start_ms, end_ms} dict, or None if timing is missing.
    """
    if "start_ms" in token and "end_ms" in token:
        return {"start_ms": token["start_ms"], "end_ms": token["end_ms"]}

    timing = token.get("timing")
    if timing is not None:
        return timing

    return None


def render_caption_layers(
    base_clip: VideoClip,
    tokens: list[dict[str, Any]],
    *,
    theme_name: str = "minimalist",
    theme_styles_path: str | Path | None = None,
    font_override: str | None = None,
) -> CompositeVideoClip:
    """Composite styled, timed text layers over a base video clip.

    Goal: Produce a MoviePy composite with captions synced to narration.
    Params: base_clip — background video; tokens — caption tokens with start_ms/end_ms;
        theme_name — theme_styles.json key; theme_styles_path — optional theme file;
        font_override — optional project font.
    Output: CompositeVideoClip with base clip and all caption TextClips.
    """
    themes = load_theme_styles(theme_styles_path)

    layers: list[VideoClip] = [base_clip]

    for token in tokens:
        text = token.get("text", "").strip()
        if not text:
            continue

        timing = _resolve_timing(token)
        if timing is None:
            continue

        style = _resolve_style(
            token,
            themes,
            theme_name,
            font_override=font_override,
        )
        start_s = timing["start_ms"] / 1000.0
        end_s = timing["end_ms"] / 1000.0
        duration = max(end_s - start_s, 0.08)

        txt_clip = TextClip(
            text=text,
            font=style["font"],
            font_size=style["font_size"],
            color=style["color"],
            stroke_color=style["stroke_color"],
            stroke_width=style["stroke_width"],
            method="caption",
            size=(int(base_clip.w * 0.9), None),
        ).with_start(start_s).with_duration(duration).with_position("center")

        if style["animation"] == "pop":
            txt_clip = txt_clip.resized(lambda t: 1.0 + 0.15 * (1 - min(t / 0.12, 1.0)))

        layers.append(txt_clip)

    return CompositeVideoClip(layers, size=(base_clip.w, base_clip.h))
