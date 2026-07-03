"""Typography Layout Canvas — timed styled text layers over video."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from moviepy import CompositeVideoClip, TextClip, VideoClip


def load_theme_styles(config_path: str | Path | None = None) -> dict[str, Any]:
    path = Path(config_path or Path(__file__).resolve().parent.parent / "config" / "theme_styles.json")
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_style(token: dict[str, Any], themes: dict[str, Any], theme_name: str) -> dict[str, Any]:
    theme = themes.get(theme_name, themes.get("minimalist", {}))
    variant = token.get("style", "primary")
    color = theme["highlight_color"] if variant == "highlight" else theme["primary_text_color"]
    return {
        "font": theme.get("font", "Arial-Bold"),
        "font_size": theme.get("font_size", 72),
        "color": color,
        "stroke_color": theme.get("stroke_color", "black"),
        "stroke_width": theme.get("stroke_width", 2),
        "animation": token.get("animation", "none"),
    }


def render_caption_layers(
    base_clip: VideoClip,
    layout_tokens: list[dict[str, Any]],
    word_timestamps: list[dict[str, Any]],
    *,
    theme_name: str = "minimalist",
    theme_styles_path: str | Path | None = None,
) -> CompositeVideoClip:
    """Paint moving text layers using LLM Director layout + word timestamps."""
    themes = load_theme_styles(theme_styles_path)
    timestamp_by_text = {entry["text"].strip().lower(): entry for entry in word_timestamps}

    layers: list[VideoClip] = [base_clip]
    cursor = 0

    for token in layout_tokens:
        text = token.get("text", "").strip()
        if not text:
            continue

        timing = token.get("timing")
        if timing is None:
            while cursor < len(word_timestamps):
                candidate = word_timestamps[cursor]
                cursor += 1
                if candidate["text"].strip().lower() == text.lower():
                    timing = candidate
                    break
            if timing is None:
                timing = timestamp_by_text.get(text.lower())

        if timing is None:
            continue

        style = _resolve_style(token, themes, theme_name)
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
