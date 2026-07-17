"""Project schema — load, normalize payloads, and expose caption/render settings."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.caption_tokens import (
    build_karaoke_tokens_from_scenes,
    build_sentence_tokens_from_scenes,
    enrich_tokens_with_timestamps,
)
from core.audio_volume import DEFAULT_MUSIC_VOLUME

DEFAULT_CANVAS = {"width": 1080, "height": 1920}
DEFAULT_THEME = "minimalist"
VALID_CAPTION_MODES = frozenset({"none", "sentence", "word"})
CONTENT_SCENE_COUNT = 3
TOTAL_SLIDE_COUNT = CONTENT_SCENE_COUNT + 1
SCENE_COUNT = CONTENT_SCENE_COUNT  # backward-compatible alias
# "ending" stays valid so drafts frozen before the brand end card replaced it still load.
VALID_SLIDE_ROLES = frozenset({"intro", "content", "ending"})
VALID_TRANSITIONS = frozenset({"pullIn", "teleportShake", "whipPan", "zoomBlur"})
DEFAULT_TRANSITION_ROTATION = ["pullIn", "teleportShake", "whipPan", "zoomBlur"]


def _parse_words_by_scene(audio: dict[str, Any]) -> dict[int, list[dict[str, Any]]]:
    """Parse audio.words_by_scene JSON (string keys) into int-keyed lookup."""
    raw = audio.get("words_by_scene")
    if not isinstance(raw, dict):
        return {}
    parsed: dict[int, list[dict[str, Any]]] = {}
    for key, entries in raw.items():
        if isinstance(entries, list):
            parsed[int(key)] = entries
    return parsed


def _tokens_have_karaoke_words(tokens: list[Any]) -> bool:
    if not tokens:
        return False
    return all(
        isinstance(token, dict)
        and isinstance(token.get("words"), list)
        and len(token["words"]) > 0
        for token in tokens
    )


def _ensure_scene_timestamps(
    scenes: list[dict[str, Any]],
    audio: dict[str, Any],
) -> None:
    """Mutate scenes with start_ms/end_ms from audio.scene_timestamps when missing."""
    if all(
        scene.get("start_ms") is not None and scene.get("end_ms") is not None
        for scene in scenes
    ):
        return

    scene_timestamps = audio.get("scene_timestamps", [])
    if not isinstance(scene_timestamps, list) or not scene_timestamps:
        return

    by_id = {int(entry["scene_id"]): entry for entry in scene_timestamps}
    for scene in scenes:
        if scene.get("start_ms") is not None and scene.get("end_ms") is not None:
            continue
        scene_id = int(scene.get("id", 0))
        timing = by_id.get(scene_id)
        if timing is None:
            continue
        scene["start_ms"] = int(timing["start_ms"])
        scene["end_ms"] = int(timing["end_ms"])


def _rebuild_sentence_caption_tokens(
    normalized: dict[str, Any],
    audio: dict[str, Any],
) -> None:
    """Rebuild per-sentence caption tokens from scenes and word timestamps."""
    scenes = normalized.get("scenes", [])
    if not isinstance(scenes, list) or not scenes:
        return

    _ensure_scene_timestamps(scenes, audio)
    captions = normalized.setdefault(
        "captions",
        {"theme": DEFAULT_THEME, "font": None, "tokens": []},
    )

    caption_mode = normalized.get("caption_mode", "none")
    words_by_scene = _parse_words_by_scene(audio)
    if caption_mode == "sentence" and words_by_scene:
        rebuilt = build_karaoke_tokens_from_scenes(scenes, words_by_scene)
        captions["tokens"] = rebuilt
        return

    word_timestamps = audio.get("word_timestamps", [])
    if not isinstance(word_timestamps, list) or not word_timestamps:
        return

    captions["tokens"] = build_sentence_tokens_from_scenes(scenes, word_timestamps)


def load_project(path: str | Path) -> dict[str, Any]:
    """Load a project or legacy pipeline_payload JSON file from disk.

    Goal: Read persisted pipeline state for render stages or a future edit UI.
    Params: path — filesystem path to project.json or pipeline_payload.json.
    Output: Normalized project dict with a captions section.
    """
    project_path = Path(path)
    data = json.loads(project_path.read_text(encoding="utf-8"))
    return normalize_project(data)


def normalize_project(data: dict[str, Any]) -> dict[str, Any]:
    """Ensure project has a captions section; upgrade legacy root-level tokens.

    Goal: Single in-memory shape for MVP payloads and full project.json files.
    Params: data — parsed JSON dict from disk.
    Output: Project dict with captions, video, and render sections populated.
    """
    normalized = dict(data)
    normalized.setdefault("project_version", 1)

    if "slides" in normalized and isinstance(normalized["slides"], list):
        normalized.setdefault("caption_mode", "none")
        normalized.setdefault(
            "captions",
            {"theme": DEFAULT_THEME, "font": None, "tokens": []},
        )
        normalized.setdefault(
            "video",
            {"canvas": dict(DEFAULT_CANVAS), "images": [], "clips": []},
        )
        normalized.setdefault(
            "scenes",
            get_content_slides(normalized["slides"]),
        )
        audio = normalized.get("audio", {})
        if isinstance(audio, dict) and audio.get("path"):
            normalized.setdefault(
                "render",
                {
                    "output_dir": str(Path(audio["path"]).parent),
                    "preview_path": None,
                    "final_path": None,
                },
            )
        if (
            isinstance(audio, dict)
            and normalized.get("caption_mode") == "sentence"
        ):
            existing_tokens: list[Any] = []
            captions_section = normalized.get("captions")
            if isinstance(captions_section, dict):
                raw_tokens = captions_section.get("tokens")
                if isinstance(raw_tokens, list):
                    existing_tokens = raw_tokens
            if not _tokens_have_karaoke_words(existing_tokens):
                _rebuild_sentence_caption_tokens(normalized, audio)
        return normalized

    if "scenes" in normalized and isinstance(normalized["scenes"], list):
        normalized.setdefault("caption_mode", "none")
        normalized.setdefault(
            "captions",
            {"theme": DEFAULT_THEME, "font": None, "tokens": []},
        )
        normalized.setdefault(
            "video",
            {"canvas": dict(DEFAULT_CANVAS), "images": [], "clips": []},
        )
        audio = normalized.get("audio", {})
        if isinstance(audio, dict) and audio.get("path"):
            normalized.setdefault(
                "render",
                {
                    "output_dir": str(Path(audio["path"]).parent),
                    "preview_path": None,
                    "final_path": None,
                },
            )
        if (
            isinstance(audio, dict)
            and normalized.get("caption_mode") == "sentence"
        ):
            existing_tokens: list[Any] = []
            captions_section = normalized.get("captions")
            if isinstance(captions_section, dict):
                raw_tokens = captions_section.get("tokens")
                if isinstance(raw_tokens, list):
                    existing_tokens = raw_tokens
            if not _tokens_have_karaoke_words(existing_tokens):
                _rebuild_sentence_caption_tokens(normalized, audio)
        return normalized

    if "captions" in data and isinstance(data["captions"], dict):
        return normalized

    tokens = data.get("tokens")
    audio = data.get("audio")
    if not isinstance(tokens, list) or not isinstance(audio, dict):
        raise ValueError("Project must include captions or legacy tokens + audio sections.")

    word_timestamps = audio.get("word_timestamps", [])
    enriched = enrich_tokens_with_timestamps(tokens, word_timestamps)

    normalized["captions"] = {
        "theme": DEFAULT_THEME,
        "font": None,
        "tokens": enriched,
    }
    normalized.setdefault(
        "video",
        {"canvas": dict(DEFAULT_CANVAS), "images": [], "clips": []},
    )
    normalized.setdefault(
        "render",
        {
            "output_dir": str(Path(audio.get("path", "output/narration.mp3")).parent),
            "preview_path": None,
            "final_path": None,
        },
    )
    return normalized


def get_caption_tokens(project: dict[str, Any]) -> list[dict[str, Any]]:
    """Return caption tokens for caption_renderer (same schema as MVP output).

    Goal: Pass tokens straight to render_caption_layers without conversion.
    Params: project — normalized project dict with captions.tokens.
    Output: List of token dicts (text, style, animation, optional start_ms/end_ms).
    """
    return list(project["captions"]["tokens"])


def get_word_timestamps(project: dict[str, Any]) -> list[dict[str, Any]]:
    """Return TTS word timestamps from the project audio section.

    Goal: Fallback timing alignment when tokens lack embedded start_ms/end_ms.
    Params: project — normalized project dict.
    Output: List of {text, start_ms, end_ms} dicts (empty list if missing).
    """
    audio = project.get("audio", {})
    narration = audio.get("narration", audio)
    timestamps = narration.get("word_timestamps", [])
    if not isinstance(timestamps, list):
        return []
    return timestamps


def get_caption_settings(project: dict[str, Any]) -> dict[str, Any]:
    """Return theme and optional font override for caption rendering.

    Goal: Resolve typography settings for a partial caption re-render.
    Params: project — normalized project dict.
    Output: Dict with theme_name (str) and font_override (str or None).
    """
    captions = project["captions"]
    return {
        "theme_name": captions.get("theme", DEFAULT_THEME),
        "font_override": captions.get("font"),
    }


def get_canvas_size(project: dict[str, Any]) -> tuple[int, int]:
    """Return the 9:16 render canvas dimensions.

    Goal: Size the base video clip for caption preview and final export.
    Params: project — normalized project dict.
    Output: (width, height) tuple in pixels.
    """
    video = project.get("video", {})
    canvas = video.get("canvas", DEFAULT_CANVAS)
    return int(canvas.get("width", DEFAULT_CANVAS["width"])), int(
        canvas.get("height", DEFAULT_CANVAS["height"])
    )


def get_raw_script(project: dict[str, Any]) -> str:
    """Return the narration script used for keyword and TTS stages.

    Goal: Source text for b-roll keyword extraction and re-voice flows.
    Params: project — normalized project dict.
    Output: Raw script string (empty if missing).
    """
    script = project.get("raw_script")
    return script.strip() if isinstance(script, str) else ""


def get_topic(project: dict[str, Any]) -> str:
    """Return the project topic or brief string."""
    topic = project.get("topic")
    return topic.strip() if isinstance(topic, str) else ""


def get_publish_metadata(project: dict[str, Any]) -> dict[str, Any] | None:
    """Return platform publish metadata when present and well-formed."""
    publish = project.get("publish")
    if not isinstance(publish, dict):
        return None

    title = publish.get("title")
    description = publish.get("description")
    hashtags = publish.get("hashtags")
    if not isinstance(title, str) or not title.strip():
        return None
    if not isinstance(description, str) or not description.strip():
        return None
    if not isinstance(hashtags, list) or not hashtags:
        return None
    if not all(isinstance(tag, str) and tag.strip() for tag in hashtags):
        return None

    return {
        "title": title.strip(),
        "description": description.strip(),
        "hashtags": [tag.strip() for tag in hashtags],
    }


def get_images_dir(project: dict[str, Any]) -> Path:
    """Resolve the directory for downloaded background image files.

    Goal: Keep image paths stable beside other render artifacts.
    Params: project — normalized project dict.
    Output: Path to images output folder (created by retrieval stage).
    """
    render = project.get("render", {})
    output_dir = render.get("output_dir")
    if output_dir:
        return Path(output_dir) / "images"
    narration = get_narration_path(project)
    return narration.parent / "images"


def get_broll_dir(project: dict[str, Any]) -> Path:
    """Alias for get_images_dir (legacy name)."""
    return get_images_dir(project)


def get_narration_duration_ms(project: dict[str, Any]) -> int:
    """Estimate narration length from word or scene timestamps.

    Goal: Spread b-roll clip slots across the voiceover timeline.
    Params: project — normalized project dict.
    Output: Duration in milliseconds (0 when no timestamps).
    """
    timestamps = get_word_timestamps(project)
    if timestamps:
        return max(int(entry.get("end_ms", 0)) for entry in timestamps)

    audio = project.get("audio", {})
    scene_ts = audio.get("scene_timestamps", [])
    if isinstance(scene_ts, list) and scene_ts:
        return max(int(entry.get("end_ms", 0)) for entry in scene_ts)

    scenes = get_scenes(project)
    if scenes:
        return max(int(scene.get("end_ms", 0)) for scene in scenes)

    return 0


def get_caption_mode(project: dict[str, Any]) -> str:
    """Return caption overlay granularity: none, sentence, or word."""
    mode = project.get("caption_mode", "none")
    if mode not in VALID_CAPTION_MODES:
        return "none"
    return mode


def get_slides(project: dict[str, Any]) -> list[dict[str, Any]]:
    """Return ordered slideshow slide list (intro + content)."""
    slides = project.get("slides")
    if isinstance(slides, list) and slides:
        return [slide for slide in slides if isinstance(slide, dict)]
    return get_scenes(project)


def drop_ending_slides(slides: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return slides without the retired ending slide.

    The brand end card closes every video now, so an ending slide from a draft
    frozen earlier would repeat that beat. Its ending.png is left on disk.
    """
    return [slide for slide in slides if slide.get("role") != "ending"]


def get_content_slides(slides: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return slides with role content (spoken narration slides)."""
    return [slide for slide in slides if slide.get("role") == "content"]


def get_scenes(project: dict[str, Any]) -> list[dict[str, Any]]:
    """Return content narration scenes (empty for legacy word-karaoke payloads)."""
    slides = project.get("slides")
    if isinstance(slides, list) and slides:
        content = get_content_slides(slides)
        if content:
            return content
    scenes = project.get("scenes")
    if not isinstance(scenes, list):
        return []
    return [scene for scene in scenes if isinstance(scene, dict)]


def slide_image_filename(slide: dict[str, Any]) -> str:
    """Return the canonical image filename for a slide based on role."""
    role = slide.get("role", "content")
    if role == "intro":
        return "intro.png"
    if role == "ending":
        return "ending.png"
    content_index = int(slide.get("content_index", slide.get("id", 1)))
    return f"scene_{content_index}.png"


def resolve_slide_transition(slide: dict[str, Any], index: int) -> str:
    """Outgoing transition for slide at index; rotates when unset."""
    raw = slide.get("transition")
    if isinstance(raw, str) and raw in VALID_TRANSITIONS:
        return raw
    return DEFAULT_TRANSITION_ROTATION[index % len(DEFAULT_TRANSITION_ROTATION)]


def assign_slide_transitions(slides: list[dict[str, Any]]) -> None:
    """Fill missing per-slide outgoing transition from the default rotation."""
    for index, slide in enumerate(slides):
        if not isinstance(slide, dict):
            continue
        if slide.get("transition") in VALID_TRANSITIONS:
            continue
        slide["transition"] = resolve_slide_transition(slide, index)


def build_image_timeline_from_slides(slides: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Copy slide timing and image paths into video.images timeline entries."""
    timeline: list[dict[str, Any]] = []
    for index, slide in enumerate(slides):
        image = slide.get("image")
        if not isinstance(image, dict) or not image.get("path"):
            continue
        timeline.append(
            {
                "path": str(Path(str(image["path"])).resolve()),
                "start_ms": int(slide.get("start_ms", 0)),
                "end_ms": int(slide.get("end_ms", 0)),
                "scene_id": slide.get("id"),
                "role": slide.get("role"),
                "source": image.get("source", "chatgpt"),
                "media_type": "image",
                "transition": resolve_slide_transition(slide, index),
            }
        )
    return timeline


def build_image_timeline_from_scenes(scenes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Copy scene timing and image paths into video.images timeline entries."""
    return build_image_timeline_from_slides(scenes)


def save_project(project: dict[str, Any], path: str | Path) -> None:
    """Write project dict to disk as pretty-printed UTF-8 JSON."""
    project_path = Path(path)
    project_path.parent.mkdir(parents=True, exist_ok=True)
    project_path.write_text(
        json.dumps(project, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def get_narration_path(project: dict[str, Any]) -> Path:
    """Resolve the narration MP3 path from the project.

    Goal: Locate voiceover audio for duration and muxing during caption render.
    Params: project — normalized project dict.
    Output: Path to narration.mp3 (raises ValueError if path is missing).
    """
    audio = project.get("audio", {})
    narration = audio.get("narration", audio)
    path = narration.get("path")
    if not path:
        raise ValueError("Project audio section must include narration path.")
    return Path(path)


def get_music_settings(project: dict[str, Any]) -> dict[str, Any] | None:
    """Return background music path and volume from audio.music, if set."""
    audio = project.get("audio", {})
    music = audio.get("music")
    if not isinstance(music, dict):
        return None
    path = music.get("path")
    if not path:
        return None
    return {
        "path": Path(str(path)),
        "volume": float(music.get("volume", DEFAULT_MUSIC_VOLUME)),
    }


def get_ambient_overlay(project: dict[str, Any]) -> dict[str, Any] | None:
    """Return ambient overlay settings from video.ambient, if set."""
    video = project.get("video", {})
    ambient = video.get("ambient")
    if not isinstance(ambient, dict):
        return None
    path = ambient.get("path")
    if not path:
        return None
    return {
        "effect": str(ambient.get("effect", "fire")),
        "variant": str(ambient.get("variant", "sparks")),
        "path": Path(str(path)),
        "opacity": float(ambient.get("opacity", 0.4)),
        "blend_mode": str(ambient.get("blend_mode", "screen")),
        "loop": bool(ambient.get("loop", True)),
        "duration_ms": int(ambient.get("duration_ms", 10_000)),
        "source": str(ambient.get("source", "auto")),
        "playback_rate": float(ambient.get("playback_rate", 1.0)),
    }
