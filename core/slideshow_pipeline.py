"""Slideshow pipeline — 3-scene script, DALL-E slides, per-scene TTS, timed image cuts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from openai import OpenAI

from core.audio_generator import synthesize_scene_speech
from core.caption_tokens import (
    build_karaoke_tokens_from_scenes,
    build_sentence_tokens_from_scenes,
    merge_styled_tokens_with_timestamps,
)
from core.pipeline_log import log_step_done
from core.music_picker import attach_random_music
from core.project_schema import (
    DEFAULT_THEME,
    SCENE_COUNT,
    VALID_CAPTION_MODES,
    build_image_timeline_from_scenes,
)
from core.slide_image_stage import generate_scene_images, provider_step_label, resolve_image_provider

# Re-use orchestrator helpers (avoid circular import at module level for tests)
from orchestrator_mvp import (
    PipelineError,
    _get_client,
    _model_from_env,
    _tts_voice_from_env,
    parse_caption_styler_response,
    run_caption_styler,
    save_payload,
    validate_tokens,
    _call_with_api_retry,
    SCRIPT_WRITER_MODEL,
)

from core.prompt_loader import DOCS_PROMPTS_DIR, load_fenced_prompt, substitute_prompt

SCENE_SCRIPT_PROMPT_PATH = DOCS_PROMPTS_DIR / "slide-script-writer.md"
TTS_WRITER_PROMPT_PATH = DOCS_PROMPTS_DIR / "slide-tts-writer.md"
TTS_WRITER_USER_TEMPLATE = (
    "Dựa trên nội dung các slide dưới đây, hãy tạo script TTS cho từng slide với các yêu cầu trên:\n\n"
    "{{SLIDE_CONTENT}}"
)


def format_slide_content_for_tts(scenes: list[dict[str, Any]]) -> str:
    """Format scene title/description blocks for the TTS writer user message."""
    blocks: list[str] = []
    for scene in scenes:
        scene_id = int(scene.get("id", len(blocks) + 1))
        title = str(scene.get("title", "")).strip()
        description = str(scene.get("description", "")).strip()
        blocks.append(
            f"Slide {scene_id}\nTitle: {title}\nDescription: {description}"
        )
    return "\n\n".join(blocks)


def parse_scene_script_response(content: str) -> list[dict[str, Any]]:
    """Parse script writer JSON and return exactly SCENE_COUNT scenes (title + description)."""
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Scene script writer returned invalid JSON: {exc}") from exc

    scenes = parsed.get("scenes") if isinstance(parsed, dict) else None
    if not isinstance(scenes, list):
        raise ValueError('Scene script writer JSON must include a "scenes" array.')

    if len(scenes) != SCENE_COUNT:
        raise ValueError(
            f"Scene script writer must return exactly {SCENE_COUNT} scenes; got {len(scenes)}."
        )

    normalized: list[dict[str, Any]] = []
    for index, scene in enumerate(scenes):
        if not isinstance(scene, dict):
            raise ValueError(f"Scene {index + 1} must be an object.")
        for field in ("title", "description"):
            value = scene.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Scene {index + 1} must include non-empty '{field}'.")
        normalized.append(
            {
                "id": index + 1,
                "title": scene["title"].strip(),
                "description": scene["description"].strip(),
            }
        )
    return normalized


def parse_tts_writer_response(content: str) -> list[str]:
    """Parse TTS writer JSON and return exactly SCENE_COUNT tts strings."""
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"TTS writer returned invalid JSON: {exc}") from exc

    scenes = parsed.get("scenes") if isinstance(parsed, dict) else None
    if not isinstance(scenes, list):
        raise ValueError('TTS writer JSON must include a "scenes" array.')

    if len(scenes) != SCENE_COUNT:
        raise ValueError(
            f"TTS writer must return exactly {SCENE_COUNT} scenes; got {len(scenes)}."
        )

    tts_blocks: list[str] = []
    for index, scene in enumerate(scenes):
        if not isinstance(scene, dict):
            raise ValueError(f"TTS scene {index + 1} must be an object.")
        tts = scene.get("tts")
        if not isinstance(tts, str) or not tts.strip():
            raise ValueError(f"TTS scene {index + 1} must include non-empty 'tts'.")
        tts_blocks.append(tts.strip())
    return tts_blocks


def _attach_tts_to_scenes(scenes: list[dict[str, Any]], tts_blocks: list[str]) -> None:
    """Mutate scenes with tts strings from the TTS writer."""
    if len(tts_blocks) != len(scenes):
        raise ValueError("TTS block count must match scene count.")
    for scene, tts in zip(scenes, tts_blocks):
        scene["tts"] = tts


def run_scene_script_writer(client: OpenAI, topic_prompt: str) -> list[dict[str, Any]]:
    """Generate 3-scene slideshow script from a topic via LLM."""
    topic = topic_prompt.strip()
    if not topic:
        raise ValueError("topic_prompt must not be empty.")

    system_prompt = load_fenced_prompt(SCENE_SCRIPT_PROMPT_PATH)
    model = _model_from_env("SCRIPT_WRITER_MODEL", SCRIPT_WRITER_MODEL)
    response = _call_with_api_retry(
        lambda: client.chat.completions.create(
            model=model,
            temperature=0.7,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": topic},
            ],
        ),
        stage_name="Scene script writer",
    )

    content = (response.choices[0].message.content or "").strip()
    if not content:
        raise PipelineError("Scene script writer returned an empty response.")

    return parse_scene_script_response(content)


def run_tts_writer(client: OpenAI, scenes: list[dict[str, Any]]) -> list[str]:
    """Generate per-scene TTS narration from on-slide title + description."""
    if not scenes:
        raise ValueError("scenes must not be empty.")

    system_prompt = load_fenced_prompt(TTS_WRITER_PROMPT_PATH)
    slide_content = format_slide_content_for_tts(scenes)
    user_message = substitute_prompt(
        TTS_WRITER_USER_TEMPLATE,
        {"SLIDE_CONTENT": slide_content},
    )
    model = _model_from_env("TTS_WRITER_MODEL", _model_from_env("SCRIPT_WRITER_MODEL", SCRIPT_WRITER_MODEL))
    response = _call_with_api_retry(
        lambda: client.chat.completions.create(
            model=model,
            temperature=0.7,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        ),
        stage_name="TTS writer",
    )

    content = (response.choices[0].message.content or "").strip()
    if not content:
        raise PipelineError("TTS writer returned an empty response.")

    return parse_tts_writer_response(content)


def _apply_scene_timestamps(
    scenes: list[dict[str, Any]],
    scene_timestamps: list[dict[str, Any]],
) -> None:
    """Mutate scenes with start_ms/end_ms from TTS scene_timestamps."""
    by_id = {int(entry["scene_id"]): entry for entry in scene_timestamps}
    for scene in scenes:
        scene_id = int(scene["id"])
        timing = by_id.get(scene_id)
        if timing is None:
            raise PipelineError(f"Missing TTS timing for scene {scene_id}.")
        scene["start_ms"] = int(timing["start_ms"])
        scene["end_ms"] = int(timing["end_ms"])


def _build_caption_tokens(
    client: OpenAI,
    scenes: list[dict[str, Any]],
    caption_mode: str,
    word_timestamps: list[dict[str, Any]],
    words_by_scene: dict[int, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Build caption tokens based on caption_mode."""
    if caption_mode == "none":
        return []

    if caption_mode == "sentence":
        # True karaoke: full sentence visible, each word highlighted as spoken.
        return build_karaoke_tokens_from_scenes(scenes, words_by_scene)

    # word mode: join all scene tts, run caption styler, merge with word timestamps
    full_script = " ".join(scene["tts"] for scene in scenes)
    caption_styler_content = run_caption_styler(client, full_script)
    tokens = parse_caption_styler_response(caption_styler_content)
    tokens = validate_tokens(tokens)
    return merge_styled_tokens_with_timestamps(tokens, word_timestamps)


def run_slideshow_pipeline(
    topic_prompt: str,
    *,
    output_dir: str | Path = "output",
    caption_mode: str = "none",
    skip_images: bool = False,
    image_provider: str | None = None,
) -> dict[str, Any]:
    """Run scene script writer → TTS writer → slide images → per-scene TTS → pipeline_payload.json."""
    if caption_mode not in VALID_CAPTION_MODES:
        raise ValueError(
            f"caption_mode must be one of {sorted(VALID_CAPTION_MODES)}; got {caption_mode!r}."
        )

    resolved_provider = resolve_image_provider(image_provider)
    image_step = provider_step_label(resolved_provider)

    client = _get_client()
    out = Path(output_dir)
    voice = _tts_voice_from_env()

    scenes = run_scene_script_writer(client, topic_prompt)

    step_script = "scene script writer (LLM, Gemini)"
    for scene in scenes:
        log_step_done(
            step_script,
            f"scene {scene['id']}/{SCENE_COUNT}: \"{scene['title']}\"",
        )
    log_step_done(step_script, f"complete ({SCENE_COUNT} scenes)")

    tts_blocks = run_tts_writer(client, scenes)
    _attach_tts_to_scenes(scenes, tts_blocks)
    log_step_done("TTS script writer (LLM)", f"complete ({SCENE_COUNT} narration blocks)")

    narration_path = out / "narration.mp3"
    scene_timestamps, word_timestamps, words_by_scene = synthesize_scene_speech(
        scenes,
        narration_path,
        voice=voice,
    )
    if not word_timestamps:
        raise PipelineError("TTS produced no word boundaries.")

    _apply_scene_timestamps(scenes, scene_timestamps)

    project_stub: dict[str, Any] = {
        "topic": topic_prompt.strip(),
        "scenes": scenes,
    }

    if not skip_images:
        generate_scene_images(
            project_stub,
            images_dir=out / "images",
            force=True,
            provider=resolved_provider,
        )
        log_step_done(image_step, f"complete ({SCENE_COUNT} images)")
    else:
        log_step_done(image_step, "skipped (--skip-images)")

    tokens = _build_caption_tokens(client, scenes, caption_mode, word_timestamps, words_by_scene)

    image_timeline = build_image_timeline_from_scenes(scenes)
    timing_summary = ", ".join(
        f"{img['start_ms']}-{img['end_ms']}ms" for img in image_timeline
    )
    log_step_done(
        "build scenes + video.images timeline",
        f"{len(image_timeline)} images timed ({timing_summary})",
    )

    audio_section: dict[str, Any] = {
        "path": str(narration_path.resolve()),
        "voice": voice,
        "word_timestamps": word_timestamps,
        "words_by_scene": {str(k): v for k, v in words_by_scene.items()},
        "scene_timestamps": scene_timestamps,
    }
    music = attach_random_music(out)
    if music is not None:
        audio_section["music"] = music
        log_step_done("background music", music["original_name"])
    else:
        from core.music_picker import resolve_music_dir

        log_step_done(
            "background music",
            f"skipped — no tracks in {resolve_music_dir()} (add MP3s to assets/music/ or music/)",
        )

    payload: dict[str, Any] = {
        "project_version": 1,
        "topic": topic_prompt.strip(),
        "caption_mode": caption_mode,
        "image_provider": resolved_provider,
        "scenes": scenes,
        "captions": {
            "theme": DEFAULT_THEME,
            "font": None,
            "tokens": tokens,
        },
        "video": {
            "canvas": {"width": 1080, "height": 1920},
            "images": image_timeline,
            "clips": [],
        },
        "audio": audio_section,
        "render": {
            "output_dir": str(out.resolve()),
            "preview_path": None,
            "final_path": None,
        },
    }

    payload_path = out / "pipeline_payload.json"
    save_payload(payload, payload_path)
    log_step_done("save pipeline_payload.json", str(payload_path.resolve()))

    print("=" * 60)
    print("RUN FOLDER")
    print("=" * 60)
    print(f"  {out.resolve()}/")
    print(f"  ├── pipeline_payload.json")
    print(f"  ├── narration.mp3")
    if not skip_images:
        print(f"  ├── images/")
        print(f"  │     scene_*.png")
    if music is not None:
        print(f"  ├── {Path(str(music['path'])).name}")
    print(f"  └── final.mp4  (after: python core/remotion_render_stage.py {payload_path.name})")
    print()

    return payload
