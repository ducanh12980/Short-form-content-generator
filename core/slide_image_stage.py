"""Slide image stage — generate per-scene backgrounds via ChatGPT, Pollinations, or mock."""

from __future__ import annotations

import base64
import os
import secrets
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests
from dotenv import load_dotenv

from core.pipeline_log import log_step, log_step_done
from core.project_schema import (
    get_images_dir,
    get_scenes,
    get_slides,
    get_topic,
    load_project,
    save_project,
    slide_image_filename,
)
from core.prompt_loader import DOCS_PROMPTS_DIR, load_fenced_prompt, substitute_prompt

COVER_SLIDE_PROMPT_PATH = DOCS_PROMPTS_DIR / "cover-slide-image.md"
COVER_SLIDE_PROMPT_COMPACT_PATH = DOCS_PROMPTS_DIR / "cover-slide-image-compact.md"
BOOKEND_SLIDE_PROMPT_PATH = DOCS_PROMPTS_DIR / "bookend-slide-image.md"
BOOKEND_SLIDE_PROMPT_COMPACT_PATH = DOCS_PROMPTS_DIR / "bookend-slide-image-compact.md"
DEFAULT_OPENAI_IMAGE_MODEL = "gpt-image-2"
DEFAULT_OPENAI_IMAGE_BASE_URL = "https://api.openai.com/v1"
DEFAULT_OPENAI_IMAGE_SIZE = "1152x2048"  # exact 9:16 phone portrait (multiples of 16 for gpt-image-2)
DEFAULT_OPENAI_IMAGE_QUALITY = "auto"
DEFAULT_OPENAI_IMAGE_PROMPT_MODE = "compact"
DEFAULT_POLLINATIONS_MODEL = "flux"
DEFAULT_ASPECT_RATIO = "9:16"
DEFAULT_SLIDE_WIDTH = 1080
DEFAULT_SLIDE_HEIGHT = 1920
POLLINATIONS_IMAGE_ROOT = "https://image.pollinations.ai/prompt"
API_RETRY_ATTEMPTS = 2
API_RETRY_DELAY_SECONDS = 5

VALID_IMAGE_PROVIDERS = frozenset({"chatgpt", "pollinations", "mock"})
VALID_OPENAI_IMAGE_QUALITIES = frozenset({"auto", "low", "medium", "high"})
VALID_OPENAI_IMAGE_PROMPT_MODES = frozenset({"full", "compact"})

VIETNAMESE_TEXT_WARNING = (
    "AI image models render Vietnamese text poorly. "
    "Prefer Remotion text overlay for accurate diacritics; review images before publishing."
)

# Minimal valid 1x1 PNG (scaled to cover in Remotion). Used when Pillow is unavailable.
_MINIMAL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def _load_env() -> None:
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def resolve_image_provider(explicit: str | None = None) -> str:
    """Return image provider: chatgpt, pollinations (free), or mock (local placeholder)."""
    provider = (explicit or os.environ.get("IMAGE_PROVIDER", "pollinations")).strip().lower()
    if provider not in VALID_IMAGE_PROVIDERS:
        raise ValueError(
            f"IMAGE_PROVIDER must be one of {sorted(VALID_IMAGE_PROVIDERS)}; got {provider!r}."
        )
    return provider


def provider_step_label(provider: str) -> str:
    labels = {
        "chatgpt": "slide image stage (ChatGPT)",
        "pollinations": "slide image stage (Pollinations)",
        "mock": "slide image stage (mock)",
    }
    return labels.get(provider, f"slide image stage ({provider})")


def _get_openai_image_api_key() -> str:
    """OpenAI API key for image generation (separate from Gemini text LLM key)."""
    _load_env()
    api_key = os.environ.get("OPENAI_IMAGE_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "Missing OPENAI_IMAGE_API_KEY. "
            "Copy .env.example to .env and add your OpenAI API key for image generation."
        )
    return api_key


def _get_openai_image_base_url() -> str:
    return os.environ.get("OPENAI_IMAGE_BASE_URL", DEFAULT_OPENAI_IMAGE_BASE_URL).rstrip("/")


def _get_openai_image_model() -> str:
    return os.environ.get("OPENAI_IMAGE_MODEL") or os.environ.get(
        "IMAGE_MODEL", DEFAULT_OPENAI_IMAGE_MODEL
    )


def _get_openai_image_size() -> str:
    return os.environ.get("OPENAI_IMAGE_SIZE", DEFAULT_OPENAI_IMAGE_SIZE)


def _get_openai_image_quality() -> str:
    quality = os.environ.get("OPENAI_IMAGE_QUALITY", DEFAULT_OPENAI_IMAGE_QUALITY).strip().lower()
    if quality not in VALID_OPENAI_IMAGE_QUALITIES:
        raise ValueError(
            f"OPENAI_IMAGE_QUALITY must be one of {sorted(VALID_OPENAI_IMAGE_QUALITIES)}; "
            f"got {quality!r}."
        )
    return quality


def resolve_openai_image_prompt_mode(explicit: str | None = None) -> str:
    """Return ChatGPT image prompt mode: compact (default) or full."""
    mode = (explicit or os.environ.get("OPENAI_IMAGE_PROMPT_MODE", DEFAULT_OPENAI_IMAGE_PROMPT_MODE))
    mode = mode.strip().lower()
    if mode not in VALID_OPENAI_IMAGE_PROMPT_MODES:
        raise ValueError(
            f"OPENAI_IMAGE_PROMPT_MODE must be one of {sorted(VALID_OPENAI_IMAGE_PROMPT_MODES)}; "
            f"got {mode!r}."
        )
    return mode


def _cover_template_path(prompt_mode: str) -> Path:
    if prompt_mode == "compact":
        return COVER_SLIDE_PROMPT_COMPACT_PATH
    return COVER_SLIDE_PROMPT_PATH


def _bookend_template_path(prompt_mode: str) -> Path:
    if prompt_mode == "compact":
        return BOOKEND_SLIDE_PROMPT_COMPACT_PATH
    return BOOKEND_SLIDE_PROMPT_PATH


def assemble_cached_image_prompt(template_path: Path, variables: dict[str, str]) -> str:
    """Build prompt as static prefix + variable suffix for OpenAI prefix caching."""
    static = load_fenced_prompt(template_path, block_index=0)
    suffix = load_fenced_prompt(template_path, block_index=1)
    filled_suffix = substitute_prompt(suffix, variables)
    return f"{static}\n\n{filled_suffix}"


def get_image_prompt_static_prefix(template_path: Path) -> str:
    """Return the cacheable static prefix for a slide image template."""
    return load_fenced_prompt(template_path, block_index=0)


def _get_pollinations_model() -> str:
    return os.environ.get("POLLINATIONS_MODEL", DEFAULT_POLLINATIONS_MODEL)


def build_slide_image_prompt(
    *,
    title: str,
    description: str,
    topic: str,
    template_path: Path | None = None,
    prompt_mode: str | None = None,
) -> str:
    """Build cover slide prompt: static art direction + scene variable suffix."""
    mode = prompt_mode or resolve_openai_image_prompt_mode()
    path = template_path or _cover_template_path(mode)
    return assemble_cached_image_prompt(
        path,
        {
            "TITLE": title.strip(),
            "DESCRIPTION": description.strip(),
            "TOPIC": topic.strip(),
        },
    )


def build_pollinations_prompt(
    *,
    title: str,
    description: str,
    topic: str,
) -> str:
    """Short background-only prompt for Pollinations (no baked-in text; fits URL limits)."""
    return (
        "Premium vertical 9:16 TikTok educational slideshow background. "
        "Luxury editorial Vietnamese philosophy illustration, warm ivory and muted gold, "
        "museum-quality digital painting, soft cinematic golden-hour light, minimal composition. "
        f"Symbolic scene inspired by: {topic.strip()}. Theme: {title.strip()}. "
        f"Mood: {description.strip()[:200]}. "
        "Misty mountains, ink wash, bamboo, lotus, traditional scholar study, large clean upper area. "
        "No text, no letters, no watermark, no anime, no cartoon."
    )


def build_bookend_slide_image_prompt(
    *,
    title: str,
    visual_concept: str,
    topic: str,
    slide_role: str,
    template_path: Path | None = None,
    prompt_mode: str | None = None,
) -> str:
    """Build intro/ending prompt: static art direction + bookend variable suffix."""
    mode = prompt_mode or resolve_openai_image_prompt_mode()
    path = template_path or _bookend_template_path(mode)
    return assemble_cached_image_prompt(
        path,
        {
            "TITLE": title.strip(),
            "VISUAL_CONCEPT": visual_concept.strip(),
            "TOPIC": topic.strip(),
            "SLIDE_ROLE": slide_role.strip(),
        },
    )


def build_pollinations_bookend_prompt(
    *,
    title: str,
    visual_concept: str,
    topic: str,
    slide_role: str,
) -> str:
    """Background + hero visual for bookend slides (no baked-in text; title overlaid in Remotion if needed)."""
    return (
        "Premium vertical 9:16 TikTok educational slideshow. "
        "Luxury editorial Vietnamese philosophy illustration, warm ivory and muted gold, "
        "museum-quality digital painting, soft cinematic golden-hour light. "
        f"{slide_role} slide layout: clean minimal upper third for title overlay, "
        f"lower two-thirds striking hero visual directly about: {topic.strip()}. "
        f"Hero scene: {visual_concept.strip()[:220]}. "
        f"Title theme (do not render as text): {title.strip()}. "
        "Bold scroll-stopping focal point, dramatic elegant composition. "
        "No description paragraph, no body text, no letters, no watermark, no anime, no cartoon."
    )


def build_prompt_for_provider(
    provider: str,
    *,
    title: str,
    topic: str,
    role: str = "content",
    description: str = "",
    visual_concept: str = "",
    prompt_mode: str | None = None,
) -> str:
    is_bookend = role in ("intro", "ending")
    chatgpt_mode = prompt_mode if provider == "chatgpt" else None
    if is_bookend:
        if provider == "pollinations":
            return build_pollinations_bookend_prompt(
                title=title,
                visual_concept=visual_concept,
                topic=topic,
                slide_role=role,
            )
        return build_bookend_slide_image_prompt(
            title=title,
            visual_concept=visual_concept,
            topic=topic,
            slide_role=role,
            prompt_mode=chatgpt_mode,
        )
    if provider == "pollinations":
        return build_pollinations_prompt(title=title, description=description, topic=topic)
    return build_slide_image_prompt(
        title=title,
        description=description,
        topic=topic,
        prompt_mode=chatgpt_mode,
    )


def _extract_openai_image_bytes(response_json: dict[str, Any]) -> bytes:
    """Parse OpenAI images/generations JSON and return first image bytes."""
    data = response_json.get("data")
    if not isinstance(data, list) or not data:
        raise RuntimeError("OpenAI image API returned no data.")

    first = data[0]
    if not isinstance(first, dict):
        raise RuntimeError("OpenAI image API response data entry is invalid.")

    b64_json = first.get("b64_json")
    if isinstance(b64_json, str) and b64_json.strip():
        return base64.b64decode(b64_json)

    url = first.get("url")
    if isinstance(url, str) and url.strip():
        image_response = requests.get(url, timeout=60)
        if image_response.status_code >= 400:
            raise RuntimeError(
                f"OpenAI image download HTTP {image_response.status_code}: "
                f"{image_response.text[:500]}"
            )
        return image_response.content

    raise RuntimeError("OpenAI image API response contained no b64_json or url.")


def _parse_openai_image_usage(response_json: dict[str, Any]) -> dict[str, int] | None:
    """Extract token usage from an OpenAI images/generations response."""
    usage = response_json.get("usage")
    if not isinstance(usage, dict):
        return None

    parsed: dict[str, int] = {}
    for key in ("input_tokens", "output_tokens", "total_tokens"):
        value = usage.get(key)
        if isinstance(value, (int, float)) and value >= 0:
            parsed[key] = int(value)

    details = usage.get("input_tokens_details")
    if isinstance(details, dict):
        cached = details.get("cached_tokens")
        if isinstance(cached, (int, float)) and cached >= 0:
            parsed["cached_tokens"] = int(cached)

    top_cached = usage.get("cached_tokens")
    if isinstance(top_cached, (int, float)) and top_cached >= 0:
        parsed.setdefault("cached_tokens", int(top_cached))

    return parsed or None


def _format_openai_image_usage(usage: dict[str, int] | None) -> str:
    if not usage:
        return "tokens unavailable"
    parts: list[str] = []
    if "input_tokens" in usage:
        in_part = f"in={usage['input_tokens']}"
        cached = usage.get("cached_tokens")
        if cached:
            in_part = f"{in_part} (cached={cached})"
        parts.append(in_part)
    if "output_tokens" in usage:
        parts.append(f"out={usage['output_tokens']}")
    if "total_tokens" in usage and len(parts) < 2:
        parts.append(f"total={usage['total_tokens']}")
    return ", ".join(parts) if parts else "tokens unavailable"


def _generate_chatgpt_image(
    prompt: str,
    output_path: Path,
    *,
    api_key: str | None = None,
    model: str | None = None,
    size: str | None = None,
    quality: str | None = None,
    aspect_ratio: str = DEFAULT_ASPECT_RATIO,
) -> tuple[Path, dict[str, int] | None, str | None]:
    del aspect_ratio  # size env drives portrait output; kept for call-site compatibility
    key = api_key or _get_openai_image_api_key()
    image_model = model or _get_openai_image_model()
    image_size = size or _get_openai_image_size()
    image_quality = quality or _get_openai_image_quality()
    base_url = _get_openai_image_base_url()
    url = f"{base_url}/images/generations"
    payload = {
        "model": image_model,
        "prompt": prompt,
        "size": image_size,
        "quality": image_quality,
        "n": 1,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}",
    }

    last_exc: Exception | None = None
    timeout = float(
        os.environ.get("OPENAI_IMAGE_TIMEOUT")
        or os.environ.get("OPENAI_TIMEOUT", "120")
    )
    for attempt in range(1, API_RETRY_ATTEMPTS + 1):
        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=timeout,
            )
            if response.status_code >= 400:
                raise RuntimeError(
                    f"OpenAI image API HTTP {response.status_code}: {response.text[:500]}"
                )

            response_json = response.json()
            image_bytes = _extract_openai_image_bytes(response_json)
            usage = _parse_openai_image_usage(response_json)
            resolved_quality = response_json.get("quality")
            if not isinstance(resolved_quality, str) or not resolved_quality.strip():
                resolved_quality = None
            else:
                resolved_quality = resolved_quality.strip()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(image_bytes)
            return output_path.resolve(), usage, resolved_quality
        except (RuntimeError, requests.RequestException, ValueError) as exc:
            last_exc = exc
            if attempt >= API_RETRY_ATTEMPTS:
                break
            time.sleep(API_RETRY_DELAY_SECONDS)

    assert last_exc is not None
    raise RuntimeError(
        f"ChatGPT image generation failed after {API_RETRY_ATTEMPTS} attempt(s): {last_exc}"
    ) from last_exc


def _generate_pollinations_image(
    prompt: str,
    output_path: Path,
    *,
    model: str | None = None,
    width: int = DEFAULT_SLIDE_WIDTH,
    height: int = DEFAULT_SLIDE_HEIGHT,
    seed: int | None = None,
) -> Path:
    """Fetch image from Pollinations free API (GET)."""
    image_model = model or _get_pollinations_model()
    url = f"{POLLINATIONS_IMAGE_ROOT}/{quote(prompt, safe='')}"
    params: dict[str, str | int] = {
        "width": width,
        "height": height,
        "model": image_model,
        "nologo": "true",
    }
    if seed is not None:
        params["seed"] = seed

    last_exc: Exception | None = None
    for attempt in range(1, API_RETRY_ATTEMPTS + 1):
        try:
            response = requests.get(
                url,
                params=params,
                timeout=float(os.environ.get("POLLINATIONS_TIMEOUT", "180")),
            )
            if response.status_code >= 400:
                raise RuntimeError(
                    f"Pollinations HTTP {response.status_code}: {response.text[:500]}"
                )
            content_type = response.headers.get("Content-Type", "")
            if not response.content or "image" not in content_type.lower():
                raise RuntimeError(
                    f"Pollinations returned non-image response ({content_type or 'unknown'})"
                )

            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(response.content)
            return output_path.resolve()
        except (RuntimeError, requests.RequestException) as exc:
            last_exc = exc
            if attempt >= API_RETRY_ATTEMPTS:
                break
            time.sleep(API_RETRY_DELAY_SECONDS)

    assert last_exc is not None
    raise RuntimeError(
        f"Pollinations image generation failed after {API_RETRY_ATTEMPTS} attempt(s): {last_exc}"
    ) from last_exc


def _generate_mock_image(
    output_path: Path,
    *,
    scene_id: int,
    title: str,
) -> Path:
    """Write a local placeholder slide (no network). For pipeline dev/CI."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import Image, ImageDraw

        img = Image.new(
            "RGB",
            (DEFAULT_SLIDE_WIDTH, DEFAULT_SLIDE_HEIGHT),
            color=(123, 1, 0),
        )
        draw = ImageDraw.Draw(img)
        label = f"Scene {scene_id}\n{title[:80]}"
        draw.multiline_text(
            (DEFAULT_SLIDE_WIDTH // 2, DEFAULT_SLIDE_HEIGHT // 2),
            label,
            fill=(250, 240, 220),
            anchor="mm",
            align="center",
        )
        img.save(output_path, format="PNG")
    except ImportError:
        output_path.write_bytes(_MINIMAL_PNG)

    return output_path.resolve()


def generate_slide_image(
    prompt: str,
    output_path: Path,
    *,
    provider: str | None = None,
    scene_id: int = 1,
    title: str = "",
    token_usage_out: list[dict[str, int]] | None = None,
    resolved_quality_out: list[str] | None = None,
    **kwargs: Any,
) -> Path:
    """Generate one slide image using the configured provider."""
    resolved = resolve_image_provider(provider)
    if resolved == "mock":
        return _generate_mock_image(output_path, scene_id=scene_id, title=title)
    if resolved == "pollinations":
        return _generate_pollinations_image(prompt, output_path, **kwargs)
    path, usage, resolved_quality = _generate_chatgpt_image(prompt, output_path, **kwargs)
    if usage is not None and token_usage_out is not None:
        token_usage_out.append(usage)
    if resolved_quality and resolved_quality_out is not None:
        resolved_quality_out.append(resolved_quality)
    return path


def generate_scene_images(
    project: dict[str, Any],
    *,
    images_dir: Path | None = None,
    force: bool = False,
    provider: str | None = None,
) -> list[Path]:
    """Generate slide images for each slide and update slide.image paths."""
    slides = get_slides(project)
    if not slides:
        raise ValueError("Project has no slides for slide image generation.")

    resolved_provider = resolve_image_provider(provider)
    topic = get_topic(project)
    out_dir = images_dir or get_images_dir(project)
    out_dir.mkdir(parents=True, exist_ok=True)

    saved: list[Path] = []
    token_usage: list[dict[str, int]] = []
    resolved_qualities: list[str] = []
    total = len(slides)
    step = provider_step_label(resolved_provider)

    if resolved_provider != "mock":
        print(VIETNAMESE_TEXT_WARNING)

    if resolved_provider == "chatgpt":
        prompt_mode = resolve_openai_image_prompt_mode()
        requested_quality = _get_openai_image_quality()
        log_step(
            step,
            (
                f"prompt={prompt_mode} quality={requested_quality} "
                f"size={_get_openai_image_size()}"
            ),
        )

    for index, slide in enumerate(slides):
        slide_id = int(slide.get("id", index + 1))
        image_path = out_dir / slide_image_filename(slide)

        if not force and image_path.is_file():
            slide["image"] = {
                "path": str(image_path.resolve()),
                "source": resolved_provider,
            }
            saved.append(image_path.resolve())
            log_step_done(step, f"slide {slide_id}/{total} cached: {image_path.name}")
            continue

        title = str(slide.get("title", "")).strip()
        role = str(slide.get("role", "content"))
        if role in ("intro", "ending"):
            visual_concept = str(slide.get("visual_concept") or slide.get("description", "")).strip()
            if not title or not visual_concept:
                raise ValueError(
                    f"Slide {slide_id} ({role}) must include title and visual_concept."
                )
            prompt = build_prompt_for_provider(
                resolved_provider,
                title=title,
                topic=topic,
                role=role,
                visual_concept=visual_concept,
            )
        else:
            description = str(slide.get("description", "")).strip()
            if not title or not description:
                raise ValueError(f"Slide {slide_id} must include title and description.")
            prompt = build_prompt_for_provider(
                resolved_provider,
                title=title,
                description=description,
                topic=topic,
                role=role,
            )
        image_kwargs: dict[str, Any] = {
            "scene_id": slide_id,
            "title": title,
        }
        if resolved_provider == "pollinations":
            # Random seed so repeated runs with the same prompt still get fresh images.
            image_kwargs["seed"] = secrets.randbelow(2**31)

        usage_before = len(token_usage)
        generate_slide_image(
            prompt,
            image_path,
            provider=resolved_provider,
            token_usage_out=token_usage if resolved_provider == "chatgpt" else None,
            resolved_quality_out=resolved_qualities if resolved_provider == "chatgpt" else None,
            **image_kwargs,
        )
        slide["image"] = {"path": str(image_path.resolve()), "source": resolved_provider}
        saved.append(image_path.resolve())
        detail = f"slide {slide_id}/{total} saved: {image_path.name}"
        if resolved_provider == "chatgpt" and len(token_usage) > usage_before:
            detail = f"{detail} — {_format_openai_image_usage(token_usage[-1])}"
            if len(resolved_qualities) > usage_before and resolved_qualities[-1]:
                detail = f"{detail}, quality={resolved_qualities[-1]}"
        log_step_done(step, detail)

    if resolved_provider == "chatgpt" and token_usage:
        total_in = sum(entry.get("input_tokens", 0) for entry in token_usage)
        total_cached = sum(entry.get("cached_tokens", 0) for entry in token_usage)
        total_out = sum(entry.get("output_tokens", 0) for entry in token_usage)
        summary = (
            f"{len(token_usage)} API call(s) — "
            f"tokens in={total_in} out={total_out}"
        )
        if total_cached:
            summary = f"{summary} (cached in={total_cached})"
        if resolved_qualities:
            unique_qualities = sorted({q for q in resolved_qualities if q})
            if unique_qualities:
                summary = f"{summary} — resolved quality: {', '.join(unique_qualities)}"
        log_step_done(step, summary)

    return saved


def generate_slide_images_for_project(
    project_path: str | Path,
    *,
    force: bool = False,
    provider: str | None = None,
) -> list[Path]:
    """Load project, generate scene images, save project back to disk."""
    project_file = Path(project_path)
    project = load_project(project_file)
    paths = generate_scene_images(project, force=force, provider=provider)
    save_project(project, project_file)
    return paths


def main() -> None:
    """CLI entry point for slide image generation from a project JSON file."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate slide images for each scene in project JSON.",
    )
    parser.add_argument(
        "project",
        nargs="?",
        default="output/pipeline_payload.json",
        help="Path to project or pipeline_payload JSON",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-generate images even when scene files already exist",
    )
    parser.add_argument(
        "--image-provider",
        choices=sorted(VALID_IMAGE_PROVIDERS),
        default=None,
        help="Image backend: pollinations (free), chatgpt, or mock (local placeholder)",
    )
    args = parser.parse_args()

    try:
        paths = generate_slide_images_for_project(
            args.project,
            force=args.force,
            provider=args.image_provider,
        )
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"Slide image generation failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print(f"Updated project: {Path(args.project).resolve()}")
    for path in paths:
        print(f"  {path}")


if __name__ == "__main__":
    main()
