"""Slideshow pipeline — intro/content/ending slides, narration-based timing, per-scene TTS."""

from __future__ import annotations

import json
import re
from copy import deepcopy
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
from core.endcard import attach_endcard
from core.music_picker import attach_random_music
from core.overlay_picker import attach_random_ambient_overlay, resolve_overlays_dir
from core.project_schema import (
    CONTENT_SCENE_COUNT,
    DEFAULT_THEME,
    TOTAL_SLIDE_COUNT,
    VALID_CAPTION_MODES,
    assign_slide_transitions,
    build_image_timeline_from_slides,
    get_content_slides,
)
from core.slide_image_stage import generate_scene_images, provider_step_label, resolve_image_provider
from core.slide_timing import apply_slide_timing

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
SCENES_DRAFT_FILENAME = "scenes_draft.json"
PUBLISH_HASHTAG_MIN = 3
PUBLISH_HASHTAG_MAX = 12
DEFAULT_PUBLISH_HASHTAGS = ("#NhanTuongVn", "#huyenhoc", "#fyp", "#vietnam", "#learnontiktok")
TTS_WRITER_USER_TEMPLATE = (
    "Dựa trên nội dung các slide dưới đây, hãy tạo script TTS cho từng slide với các yêu cầu trên:\n\n"
    "{{SLIDE_CONTENT}}"
)


def _scenes_draft_path(output_dir: Path) -> Path:
    return output_dir / SCENES_DRAFT_FILENAME


def _save_scenes_draft(
    output_dir: Path,
    *,
    topic: str,
    slides: list[dict[str, Any]],
    publish: dict[str, Any],
) -> None:
    """Persist LLM slide + TTS script so a failed TTS pass can resume without new API calls."""
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {"topic": topic.strip(), "slides": slides, "publish": publish}
    _scenes_draft_path(output_dir).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _load_scenes_draft(
    output_dir: Path,
    *,
    topic: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]] | None:
    """Load cached slides + publish when topic matches and each content slide has tts text."""
    path = _scenes_draft_path(output_dir)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or data.get("topic", "").strip() != topic.strip():
        return None
    slides = data.get("slides")
    if not isinstance(slides, list) or len(slides) != TOTAL_SLIDE_COUNT:
        return None
    content_slides = get_content_slides(slides)
    if len(content_slides) != CONTENT_SCENE_COUNT:
        return None
    for slide in content_slides:
        if not isinstance(slide, dict) or not str(slide.get("tts", "")).strip():
            return None
    publish_raw = data.get("publish")
    if not isinstance(publish_raw, dict):
        return None
    try:
        publish = parse_publish_metadata({"publish": publish_raw})
    except ValueError:
        return None
    return slides, publish


def format_slide_content_for_tts(scenes: list[dict[str, Any]]) -> str:
    """Format scene title/description blocks for the TTS writer user message."""
    blocks: list[str] = []
    for index, scene in enumerate(scenes):
        scene_id = int(scene.get("content_index", index + 1))
        title = str(scene.get("title", "")).strip()
        description = str(scene.get("description", "")).strip()
        blocks.append(
            f"Slide {scene_id}\nTitle: {title}\nDescription: {description}"
        )
    return "\n\n".join(blocks)


def _validate_content_slide_copy(slide: dict[str, Any], label: str) -> tuple[str, str]:
    for field in ("title", "description"):
        value = slide.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{label} must include non-empty '{field}'.")
    return slide["title"].strip(), slide["description"].strip()


def _validate_bookend_slide_copy(slide: dict[str, Any], label: str) -> tuple[str, str]:
    title = slide.get("title")
    if not isinstance(title, str) or not title.strip():
        raise ValueError(f"{label} must include non-empty 'title'.")
    visual = slide.get("visual_concept")
    if not isinstance(visual, str) or not visual.strip():
        # Legacy drafts used description as visual brief.
        visual = slide.get("description")
    if not isinstance(visual, str) or not visual.strip():
        raise ValueError(f"{label} must include non-empty 'visual_concept'.")
    return title.strip(), visual.strip()


def _normalize_hashtag(tag: str) -> str:
    stripped = tag.strip()
    if not stripped:
        raise ValueError("Hashtag must not be empty.")
    return stripped if stripped.startswith("#") else f"#{stripped}"


def _coerce_hashtag_list(raw: Any) -> list[str]:
    """Accept list, comma/space-separated string, or missing — return string tags."""
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(tag) for tag in raw if tag is not None and str(tag).strip()]
    if isinstance(raw, str) and raw.strip():
        return [part for part in re.split(r"[\s,]+", raw.strip()) if part]
    return []


def _repair_publish_hashtags(raw_hashtags: list[str]) -> list[str]:
    """Normalize tags and pad with defaults when the LLM returns too few."""
    hashtags: list[str] = []
    seen: set[str] = set()
    for tag in raw_hashtags:
        try:
            normalized = _normalize_hashtag(tag)
        except ValueError:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        hashtags.append(normalized)

    if len(hashtags) < PUBLISH_HASHTAG_MIN:
        print(
            "[slideshow] publish metadata missing or sparse hashtags; "
            f"padding from defaults (got {len(raw_hashtags)})"
        )
        for fallback in DEFAULT_PUBLISH_HASHTAGS:
            if len(hashtags) >= PUBLISH_HASHTAG_MIN:
                break
            key = fallback.lower()
            if key not in seen:
                seen.add(key)
                hashtags.append(fallback)

    if len(hashtags) < PUBLISH_HASHTAG_MIN:
        raise ValueError(
            f"Publish metadata must include {PUBLISH_HASHTAG_MIN}–{PUBLISH_HASHTAG_MAX} hashtags; "
            f"got {len(hashtags)} after repair."
        )
    return hashtags[:PUBLISH_HASHTAG_MAX]


def parse_publish_metadata(parsed: dict[str, Any]) -> dict[str, Any]:
    """Parse and validate publish metadata from scene script writer JSON."""
    publish = parsed.get("publish")
    if not isinstance(publish, dict):
        raise ValueError('Scene script writer JSON must include a "publish" object.')

    title = publish.get("title")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("Publish metadata must include non-empty 'title'.")
    description = publish.get("description")
    if not isinstance(description, str) or not description.strip():
        raise ValueError("Publish metadata must include non-empty 'description'.")

    raw_hashtags = _coerce_hashtag_list(publish.get("hashtags"))
    hashtags = _repair_publish_hashtags(raw_hashtags)

    return {
        "title": title.strip(),
        "description": description.strip(),
        "hashtags": hashtags,
    }


def parse_scene_script_response_from_parsed(parsed: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse script writer JSON object and return TOTAL_SLIDE_COUNT slides with roles."""
    if not isinstance(parsed, dict):
        raise ValueError("Scene script writer JSON must be an object.")

    intro = parsed.get("intro")
    content_scenes = parsed.get("scenes")
    ending = parsed.get("ending")

    if not isinstance(intro, dict):
        raise ValueError('Scene script writer JSON must include an "intro" object.')
    if not isinstance(content_scenes, list):
        raise ValueError('Scene script writer JSON must include a "scenes" array.')
    if not isinstance(ending, dict):
        raise ValueError('Scene script writer JSON must include an "ending" object.')

    if len(content_scenes) != CONTENT_SCENE_COUNT:
        raise ValueError(
            f"Scene script writer must return exactly {CONTENT_SCENE_COUNT} content scenes; "
            f"got {len(content_scenes)}."
        )

    slides: list[dict[str, Any]] = []
    intro_title, intro_visual = _validate_bookend_slide_copy(intro, "Intro")
    slides.append(
        {
            "id": 1,
            "role": "intro",
            "title": intro_title,
            "visual_concept": intro_visual,
        }
    )

    for index, scene in enumerate(content_scenes):
        if not isinstance(scene, dict):
            raise ValueError(f"Content scene {index + 1} must be an object.")
        title, description = _validate_content_slide_copy(scene, f"Content scene {index + 1}")
        slides.append(
            {
                "id": index + 2,
                "role": "content",
                "content_index": index + 1,
                "title": title,
                "description": description,
            }
        )

    ending_title, ending_visual = _validate_bookend_slide_copy(ending, "Ending")
    slides.append(
        {
            "id": CONTENT_SCENE_COUNT + 2,
            "role": "ending",
            "title": ending_title,
            "visual_concept": ending_visual,
        }
    )
    return slides


def parse_scene_script_response(content: str) -> list[dict[str, Any]]:
    """Parse script writer JSON and return TOTAL_SLIDE_COUNT slides with roles."""
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Scene script writer returned invalid JSON: {exc}") from exc

    return parse_scene_script_response_from_parsed(parsed)


def parse_tts_writer_response(content: str) -> list[str]:
    """Parse TTS writer JSON and return exactly CONTENT_SCENE_COUNT tts strings."""
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"TTS writer returned invalid JSON: {exc}") from exc

    scenes = parsed.get("scenes") if isinstance(parsed, dict) else None
    if not isinstance(scenes, list):
        raise ValueError('TTS writer JSON must include a "scenes" array.')

    if len(scenes) != CONTENT_SCENE_COUNT:
        raise ValueError(
            f"TTS writer must return exactly {CONTENT_SCENE_COUNT} scenes; got {len(scenes)}."
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


def _attach_tts_to_content_slides(
    content_slides: list[dict[str, Any]],
    tts_blocks: list[str],
) -> None:
    """Mutate content slides with tts strings from the TTS writer."""
    if len(tts_blocks) != len(content_slides):
        raise ValueError("TTS block count must match content slide count.")
    for slide, tts in zip(content_slides, tts_blocks):
        slide["tts"] = tts


def _apply_tts_timestamps(
    content_slides: list[dict[str, Any]],
    scene_timestamps: list[dict[str, Any]],
) -> None:
    """Mutate content slides with start_ms/end_ms from TTS scene_timestamps."""
    by_id = {int(entry["scene_id"]): entry for entry in scene_timestamps}
    for slide in content_slides:
        slide_id = int(slide["id"])
        timing = by_id.get(slide_id)
        if timing is None:
            raise PipelineError(f"Missing TTS timing for content slide {slide_id}.")
        slide["start_ms"] = int(timing["start_ms"])
        slide["end_ms"] = int(timing["end_ms"])


def run_scene_script_writer(
    client: OpenAI,
    topic_prompt: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Generate intro + content + ending slideshow script and publish metadata from a topic."""
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

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Scene script writer returned invalid JSON: {exc}") from exc

    slides = parse_scene_script_response_from_parsed(parsed)
    publish = parse_publish_metadata(parsed)
    return slides, publish


def run_tts_writer(client: OpenAI, content_slides: list[dict[str, Any]]) -> list[str]:
    """Generate per-scene TTS narration from on-slide title + description."""
    if not content_slides:
        raise ValueError("content_slides must not be empty.")

    system_prompt = load_fenced_prompt(TTS_WRITER_PROMPT_PATH)
    slide_content = format_slide_content_for_tts(content_slides)
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


def _build_caption_tokens(
    client: OpenAI,
    content_slides: list[dict[str, Any]],
    caption_mode: str,
    word_timestamps: list[dict[str, Any]],
    words_by_scene: dict[int, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Build caption tokens based on caption_mode (content narration only)."""
    if caption_mode == "none":
        return []

    if caption_mode == "sentence":
        return build_karaoke_tokens_from_scenes(content_slides, words_by_scene)

    full_script = " ".join(slide["tts"] for slide in content_slides)
    caption_styler_content = run_caption_styler(client, full_script)
    tokens = parse_caption_styler_response(caption_styler_content)
    tokens = validate_tokens(tokens)
    return merge_styled_tokens_with_timestamps(tokens, word_timestamps)


def _narration_duration_ms(
    word_timestamps: list[dict[str, Any]],
    scene_timestamps: list[dict[str, Any]],
) -> int:
    if word_timestamps:
        return max(int(entry.get("end_ms", 0)) for entry in word_timestamps)
    if scene_timestamps:
        return max(int(entry.get("end_ms", 0)) for entry in scene_timestamps)
    return 0


def run_slideshow_pipeline(
    topic_prompt: str,
    *,
    output_dir: str | Path = "output",
    caption_mode: str = "none",
    skip_images: bool = False,
    image_provider: str | None = None,
    job_assets_id: str | None = None,
    require_job_assets: bool = False,
) -> dict[str, Any]:
    """CSV job flow: inventory all parts → fill only gaps → TTS.

    Detailed branch (when ``job_assets_id`` is set)::

        1. Soát hết assets/jobs/<id>/ (script + từng PNG) — inventory đầy đủ
        2. Nếu thiếu bất kỳ phần nào → chỉ GPT phần còn thiếu (không render lại phần đã có)
        3. Lưu lại library → TTS → (Remotion / Publish ngoài hàm này)
    """
    if caption_mode not in VALID_CAPTION_MODES:
        raise ValueError(
            f"caption_mode must be one of {sorted(VALID_CAPTION_MODES)}; got {caption_mode!r}."
        )

    resolved_provider = resolve_image_provider(image_provider)
    image_step = provider_step_label(resolved_provider)

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    voice = _tts_voice_from_env()
    topic = topic_prompt.strip()

    from core.job_assets import (
        copy_existing_job_images_into,
        copy_job_images_into,
        format_inventory_summary,
        inventory_job_assets,
        persist_job_assets_from_run_dir,
        purge_job_images,
        purge_slide_images_in,
        require_complete_job_assets,
    )

    assets_id = (job_assets_id or "").strip() or None
    script_from_library = False
    script_resumed = False
    images_complete = False
    slides: list[dict[str, Any]] | None = None
    publish: dict[str, Any] | None = None
    client = None
    inventory: dict[str, Any] | None = None

    if assets_id:
        # Always scan every part first (script + all 5 images), even if one is missing.
        inventory = inventory_job_assets(assets_id, topic=topic)
        log_step_done(
            "job assets inventory",
            f"id={assets_id}: {format_inventory_summary(inventory)}",
        )

        if require_job_assets:
            require_complete_job_assets(assets_id)
            from core.job_assets import load_job_scenes_draft

            slides, publish = load_job_scenes_draft(assets_id, topic=topic)
            script_from_library = True
            images_complete = True
        elif inventory["complete"]:
            slides = inventory["slides"]
            publish = inventory["publish"]
            script_from_library = True
            images_complete = True
        else:
            if inventory["script_ok"]:
                slides = inventory["slides"]
                publish = inventory["publish"]
                script_from_library = True
            # else: script will be generated below; images filled after with force=False

    if script_from_library:
        assert assets_id is not None and slides is not None and publish is not None
        log_step_done(
            "scene script writer (LLM, Gemini)",
            f"reused assets/jobs/{assets_id}/{SCENES_DRAFT_FILENAME}",
        )
        log_step_done(
            "TTS script writer (LLM)",
            f"reused assets/jobs/{assets_id}/{SCENES_DRAFT_FILENAME}",
        )
        _save_scenes_draft(out, topic=topic, slides=slides, publish=publish)
    else:
        client = _get_client()
        cached_draft = _load_scenes_draft(out, topic=topic)
        if cached_draft is not None:
            slides, publish = cached_draft
            script_resumed = True
            log_step_done(
                "scene script writer (LLM, Gemini)",
                f"resumed from {SCENES_DRAFT_FILENAME}",
            )
            log_step_done("TTS script writer (LLM)", f"resumed from {SCENES_DRAFT_FILENAME}")
        else:
            slides, publish = run_scene_script_writer(client, topic)

            step_script = "scene script writer (LLM, Gemini)"
            for slide in slides:
                role = slide.get("role", "content")
                log_step_done(
                    step_script,
                    f"{role} slide {slide['id']}/{TOTAL_SLIDE_COUNT}: \"{slide['title']}\"",
                )
            log_step_done(step_script, f"complete ({TOTAL_SLIDE_COUNT} slides)")
            log_step_done(
                "publish metadata (LLM)",
                f"\"{publish['title']}\" ({len(publish['hashtags'])} hashtags)",
            )

            content_slides = get_content_slides(slides)
            tts_blocks = run_tts_writer(client, content_slides)
            _attach_tts_to_content_slides(content_slides, tts_blocks)
            log_step_done(
                "TTS script writer (LLM)",
                f"complete ({CONTENT_SCENE_COUNT} narration blocks)",
            )
            _save_scenes_draft(out, topic=topic, slides=slides, publish=publish)

    assert slides is not None and publish is not None

    # A script that came from neither the library nor a resumed draft is brand new,
    # so any slide PNG lying around was rendered from a script we just discarded.
    script_regenerated = not script_from_library and not script_resumed

    # Images before spoken TTS so durable assets can be saved even if TTS fails later.
    project_stub: dict[str, Any] = {
        "topic": topic_prompt.strip(),
        "slides": slides,
        "scenes": get_content_slides(slides),
    }

    if images_complete:
        assert assets_id is not None
        copy_job_images_into(out, assets_id, slides=slides)
        log_step_done(image_step, f"reused assets/jobs/{assets_id}/images ({TOTAL_SLIDE_COUNT})")
        resolved_provider = "job_assets"
    elif not skip_images:
        if script_from_library and assets_id is not None:
            reused_paths = copy_existing_job_images_into(out, assets_id, slides=slides)
            missing = (inventory or {}).get("missing_images") or []
            if reused_paths or missing:
                log_step_done(
                    image_step,
                    (
                        f"inventory fill: keep {len(reused_paths)} existing, "
                        f"generate {len(missing) if missing else 'remaining'} missing"
                        + (f" ({', '.join(missing)})" if missing else "")
                    ),
                )
        elif script_regenerated:
            stale = purge_slide_images_in(out / "images")
            if assets_id is not None:
                stale += purge_job_images(assets_id)
            if stale:
                names = ", ".join(sorted(set(stale)))
                log_step_done(
                    image_step,
                    f"discarded {len(set(stale))} image(s) rendered from a previous script ({names})",
                )
        # force=False → only call the image API for PNGs still absent after inventory copy
        generate_scene_images(
            project_stub,
            images_dir=out / "images",
            force=False,
            provider=resolved_provider,
        )
        log_step_done(image_step, f"complete ({TOTAL_SLIDE_COUNT} images)")
        if assets_id is not None:
            persist_job_assets_from_run_dir(
                assets_id,
                out,
                topic=topic,
                slides=slides,
                publish=publish,
            )
            log_step_done("job assets", f"saved assets/jobs/{assets_id}/")
    else:
        log_step_done(image_step, "skipped (--skip-images)")

    content_slides = get_content_slides(slides)
    narration_path = out / "narration.mp3"
    scene_timestamps, word_timestamps, words_by_scene = synthesize_scene_speech(
        content_slides,
        narration_path,
        voice=voice,
    )
    if not word_timestamps:
        raise PipelineError("TTS produced no word boundaries.")

    content_for_captions = deepcopy(content_slides)
    _apply_tts_timestamps(content_for_captions, scene_timestamps)
    if caption_mode == "none":
        tokens: list[dict[str, Any]] = []
    else:
        if client is None:
            client = _get_client()
        tokens = _build_caption_tokens(
            client,
            content_for_captions,
            caption_mode,
            word_timestamps,
            words_by_scene,
        )

    narration_duration_ms = _narration_duration_ms(word_timestamps, scene_timestamps)
    if narration_duration_ms <= 0:
        raise PipelineError("TTS produced no usable narration duration.")
    apply_slide_timing(slides, narration_duration_ms)

    content_scenes = deepcopy(content_for_captions)

    assign_slide_transitions(slides)
    image_timeline = build_image_timeline_from_slides(slides)
    timing_summary = ", ".join(
        f"{img['start_ms']}-{img['end_ms']}ms" for img in image_timeline
    )
    log_step_done(
        "build slides + video.images timeline",
        f"{len(image_timeline)} images timed ({timing_summary})",
    )

    endcard = attach_endcard(image_timeline, out)
    if endcard is not None:
        hold_ms = endcard["end_ms"] - endcard["start_ms"]
        log_step_done(
            "brand end card",
            f"{endcard['original_name']} — {hold_ms}ms after narration",
        )
    else:
        log_step_done(
            "brand end card",
            "skipped — no image (add assets/endcard/endcard.jpg or set ENDCARD_PATH)",
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

    ambient_overlay = attach_random_ambient_overlay(out)
    if ambient_overlay is not None:
        log_step_done("ambient overlay", ambient_overlay["original_name"])
    else:
        log_step_done(
            "ambient overlay",
            f"skipped — no overlays in {resolve_overlays_dir()} (add WebMs to assets/overlays/)",
        )

    payload: dict[str, Any] = {
        "project_version": 1,
        "topic": topic_prompt.strip(),
        "caption_mode": caption_mode,
        "image_provider": resolved_provider,
        "publish": publish,
        "slides": slides,
        "scenes": content_scenes,
        "captions": {
            "theme": DEFAULT_THEME,
            "font": None,
            "tokens": tokens,
        },
        "video": {
            "canvas": {"width": 1080, "height": 1920},
            "images": image_timeline,
            "clips": [],
            **({"ambient": ambient_overlay} if ambient_overlay else {}),
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
    if images_complete or not skip_images:
        print(f"  ├── images/")
        print(f"  │     intro.png, scene_*.png, ending.png")
    if music is not None:
        print(f"  ├── {Path(str(music['path'])).name}")
    if ambient_overlay is not None:
        print(f"  ├── {Path(str(ambient_overlay['path'])).name}")
    print(f"  └── final.mp4  (after: python core/remotion_render_stage.py {payload_path.name})")
    print()

    return payload
