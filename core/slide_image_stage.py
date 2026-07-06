"""Slide image stage — generate per-scene backgrounds via Gemini, Pollinations, or mock."""

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

from core.pipeline_log import log_step_done
from core.project_schema import (
    get_images_dir,
    get_scenes,
    get_topic,
    load_project,
    save_project,
)
from core.prompt_loader import DOCS_PROMPTS_DIR, load_fenced_prompt, substitute_prompt

COVER_SLIDE_PROMPT_PATH = DOCS_PROMPTS_DIR / "cover-slide-image.md"
DEFAULT_GEMINI_IMAGE_MODEL = "gemini-2.5-flash-image"
DEFAULT_POLLINATIONS_MODEL = "flux"
DEFAULT_ASPECT_RATIO = "9:16"
DEFAULT_SLIDE_WIDTH = 1080
DEFAULT_SLIDE_HEIGHT = 1920
GEMINI_API_ROOT = "https://generativelanguage.googleapis.com/v1beta"
POLLINATIONS_IMAGE_ROOT = "https://image.pollinations.ai/prompt"
API_RETRY_ATTEMPTS = 2
API_RETRY_DELAY_SECONDS = 5

VALID_IMAGE_PROVIDERS = frozenset({"gemini", "pollinations", "mock"})

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
    """Return image provider: gemini, pollinations (free), or mock (local placeholder)."""
    provider = (explicit or os.environ.get("IMAGE_PROVIDER", "pollinations")).strip().lower()
    if provider not in VALID_IMAGE_PROVIDERS:
        raise ValueError(
            f"IMAGE_PROVIDER must be one of {sorted(VALID_IMAGE_PROVIDERS)}; got {provider!r}."
        )
    return provider


def provider_step_label(provider: str) -> str:
    labels = {
        "gemini": "slide image stage (Gemini)",
        "pollinations": "slide image stage (Pollinations)",
        "mock": "slide image stage (mock)",
    }
    return labels.get(provider, f"slide image stage ({provider})")


def _get_gemini_api_key() -> str:
    """Same Gemini key as the LLM orchestrator (OPENAI_API_KEY in .env)."""
    _load_env()
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Missing OPENAI_API_KEY (Gemini API key). "
            "Copy .env.example to .env and add your Google AI Studio key."
        )
    return api_key


def _get_gemini_image_model() -> str:
    return os.environ.get("GEMINI_IMAGE_MODEL") or os.environ.get(
        "IMAGE_MODEL", DEFAULT_GEMINI_IMAGE_MODEL
    )


def _get_pollinations_model() -> str:
    return os.environ.get("POLLINATIONS_MODEL", DEFAULT_POLLINATIONS_MODEL)


def build_slide_image_prompt(
    *,
    title: str,
    description: str,
    topic: str,
    template_path: Path | None = None,
) -> str:
    """Fill cover-slide-image.md template with scene copy (Gemini / full-quality)."""
    path = template_path or COVER_SLIDE_PROMPT_PATH
    template = load_fenced_prompt(path)
    return substitute_prompt(
        template,
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


def build_prompt_for_provider(
    provider: str,
    *,
    title: str,
    description: str,
    topic: str,
) -> str:
    if provider == "pollinations":
        return build_pollinations_prompt(title=title, description=description, topic=topic)
    return build_slide_image_prompt(title=title, description=description, topic=topic)


def _extract_image_bytes(response_json: dict[str, Any]) -> bytes:
    """Parse generateContent JSON and return first inline image bytes."""
    candidates = response_json.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise RuntimeError("Gemini returned no candidates.")

    content = candidates[0].get("content", {})
    parts = content.get("parts", [])
    if not isinstance(parts, list):
        raise RuntimeError("Gemini response has no content parts.")

    for part in parts:
        if not isinstance(part, dict):
            continue
        inline = part.get("inlineData") or part.get("inline_data")
        if not isinstance(inline, dict):
            continue
        data = inline.get("data")
        if isinstance(data, str) and data.strip():
            return base64.b64decode(data)

    raise RuntimeError("Gemini response contained no inline image data.")


def _generate_gemini_image(
    prompt: str,
    output_path: Path,
    *,
    api_key: str | None = None,
    model: str | None = None,
    aspect_ratio: str = DEFAULT_ASPECT_RATIO,
) -> Path:
    key = api_key or _get_gemini_api_key()
    image_model = model or _get_gemini_image_model()
    url = f"{GEMINI_API_ROOT}/models/{image_model}:generateContent"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["IMAGE"],
            "imageConfig": {"aspectRatio": aspect_ratio},
        },
    }
    headers = {"Content-Type": "application/json", "x-goog-api-key": key}

    last_exc: Exception | None = None
    for attempt in range(1, API_RETRY_ATTEMPTS + 1):
        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=float(os.environ.get("OPENAI_TIMEOUT", "120")),
            )
            if response.status_code >= 400:
                raise RuntimeError(
                    f"Gemini image API HTTP {response.status_code}: {response.text[:500]}"
                )

            image_bytes = _extract_image_bytes(response.json())
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(image_bytes)
            return output_path.resolve()
        except (RuntimeError, requests.RequestException, ValueError) as exc:
            last_exc = exc
            if attempt >= API_RETRY_ATTEMPTS:
                break
            time.sleep(API_RETRY_DELAY_SECONDS)

    assert last_exc is not None
    raise RuntimeError(
        f"Gemini image generation failed after {API_RETRY_ATTEMPTS} attempt(s): {last_exc}"
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
    **kwargs: Any,
) -> Path:
    """Generate one slide image using the configured provider."""
    resolved = resolve_image_provider(provider)
    if resolved == "mock":
        return _generate_mock_image(output_path, scene_id=scene_id, title=title)
    if resolved == "pollinations":
        return _generate_pollinations_image(prompt, output_path, **kwargs)
    return _generate_gemini_image(prompt, output_path, **kwargs)


def generate_scene_images(
    project: dict[str, Any],
    *,
    images_dir: Path | None = None,
    force: bool = False,
    provider: str | None = None,
) -> list[Path]:
    """Generate slide images for each scene and update scene.image paths."""
    scenes = get_scenes(project)
    if not scenes:
        raise ValueError("Project has no scenes for slide image generation.")

    resolved_provider = resolve_image_provider(provider)
    topic = get_topic(project)
    out_dir = images_dir or get_images_dir(project)
    out_dir.mkdir(parents=True, exist_ok=True)

    saved: list[Path] = []
    total = len(scenes)
    step = provider_step_label(resolved_provider)

    if resolved_provider != "mock":
        print(VIETNAMESE_TEXT_WARNING)

    for index, scene in enumerate(scenes):
        scene_id = int(scene.get("id", index + 1))
        image_path = out_dir / f"scene_{scene_id}.png"

        if not force and image_path.is_file():
            scene["image"] = {
                "path": str(image_path.resolve()),
                "source": resolved_provider,
            }
            saved.append(image_path.resolve())
            log_step_done(step, f"scene {scene_id}/{total} cached: {image_path.name}")
            continue

        title = str(scene.get("title", "")).strip()
        description = str(scene.get("description", "")).strip()
        if not title or not description:
            raise ValueError(f"Scene {scene_id} must include title and description.")

        prompt = build_prompt_for_provider(
            resolved_provider,
            title=title,
            description=description,
            topic=topic,
        )
        image_kwargs: dict[str, Any] = {
            "scene_id": scene_id,
            "title": title,
        }
        if resolved_provider == "pollinations":
            # Random seed so repeated runs with the same prompt still get fresh images.
            image_kwargs["seed"] = secrets.randbelow(2**31)

        generate_slide_image(
            prompt,
            image_path,
            provider=resolved_provider,
            **image_kwargs,
        )
        scene["image"] = {"path": str(image_path.resolve()), "source": resolved_provider}
        saved.append(image_path.resolve())
        log_step_done(step, f"scene {scene_id}/{total} saved: {image_path.resolve()}")

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
        help="Image backend: pollinations (free), gemini, or mock (local placeholder)",
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
