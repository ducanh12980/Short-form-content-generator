"""ChatGPT slide image generation — real prompts, setting sweeps, token logging."""

from __future__ import annotations

import os
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from dotenv import load_dotenv

from core.slide_image_stage import (
    BOOKEND_SLIDE_PROMPT_COMPACT_PATH as BOOKEND_COMPACT,
    COVER_SLIDE_PROMPT_COMPACT_PATH as COVER_COMPACT,
    build_prompt_for_provider,
    generate_scene_images,
    get_image_prompt_static_prefix,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_EXPERIMENT_DIR = _REPO_ROOT / "output" / "image-experiments"

# Same topic + slide copy shape as the slideshow pipeline (Vietnamese physiognomy).
SAMPLE_TOPIC = "Nhân tướng học — hiểu người qua khuôn mặt"

SAMPLE_SLIDES: dict[str, dict] = {
    "content": {
        "id": 2,
        "role": "content",
        "content_index": 1,
        "title": "Hiểu người",
        "description": (
            "Nhìn vào khuôn mặt người khác không phải để phán xét — "
            "mà để hiểu cách họ nhìn thế giới."
        ),
    },
    "intro": {
        "id": 1,
        "role": "intro",
        "title": "Bạn có biết?",
        "visual_concept": (
            "Ánh bình minh xuyên qua cửa sổ gỗ chạm khắc, "
            "phản chiếu trên gương đồng cổ."
        ),
    },
    "ending": {
        "id": 5,
        "role": "ending",
        "title": "Hiểu người, hiểu mình",
        "visual_concept": "Lối đá cuội dẫn vào sương mù vàng hoàng hôn.",
    },
}

# Live setting matrix — filter with pytest -k, e.g. -k "content-compact-medium".
IMAGE_EXPERIMENT_CASES = [
    pytest.param("content", "compact", "low", "768x1360", id="content-compact-low-768"),
    pytest.param("content", "compact", "medium", "896x1600", id="content-compact-medium-896"),
    pytest.param("content", "compact", "high", "1152x2048", id="content-compact-high-1152"),
    pytest.param("content", "full", "medium", "896x1600", id="content-full-medium-896"),
    pytest.param("intro", "compact", "medium", "896x1600", id="intro-compact-medium-896"),
    pytest.param("intro", "full", "medium", "896x1600", id="intro-full-medium-896"),
    pytest.param("ending", "compact", "medium", "896x1600", id="ending-compact-medium-896"),
]


def _project_for_slide_role(role: str) -> dict:
    if role not in SAMPLE_SLIDES:
        raise ValueError(f"Unknown slide role: {role!r}")
    return {"topic": SAMPLE_TOPIC, "slides": [dict(SAMPLE_SLIDES[role])]}


def _expected_real_prompt(*, role: str, prompt_mode: str) -> str:
    slide = SAMPLE_SLIDES[role]
    if role == "content":
        return build_prompt_for_provider(
            "chatgpt",
            title=slide["title"],
            description=slide["description"],
            topic=SAMPLE_TOPIC,
            role="content",
            prompt_mode=prompt_mode,
        )
    return build_prompt_for_provider(
        "chatgpt",
        title=slide["title"],
        topic=SAMPLE_TOPIC,
        role=role,
        visual_concept=slide["visual_concept"],
        prompt_mode=prompt_mode,
    )


def _experiment_image_path(
    *,
    role: str,
    prompt_mode: str,
    quality: str,
    size: str,
) -> Path:
    safe_size = size.replace("x", "_")
    return _EXPERIMENT_DIR / f"{role}_{prompt_mode}_{quality}_{safe_size}.png"


def _mock_openai_image_response(
    *,
    input_tokens: int = 420,
    output_tokens: int = 1360,
    cached_tokens: int = 0,
    quality: str = "medium",
) -> MagicMock:
    usage: dict[str, int | dict[str, int]] = {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
    }
    if cached_tokens:
        usage["input_tokens_details"] = {"cached_tokens": cached_tokens}

    return MagicMock(
        status_code=200,
        json=lambda: {
            "data": [{"b64_json": "aGVsbG8="}],  # "hello"
            "usage": usage,
            "quality": quality,
        },
    )


@patch("core.slide_image_stage.requests.post")
@patch.dict(
    os.environ,
    {
        "OPENAI_IMAGE_API_KEY": "test-key",
        "OPENAI_IMAGE_QUALITY": "medium",
        "OPENAI_IMAGE_SIZE": "896x1600",
        "OPENAI_IMAGE_PROMPT_MODE": "compact",
    },
    clear=False,
)
def test_generate_one_chatgpt_image_uses_real_slide_prompt_and_logs_tokens(
    mock_post: MagicMock,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """One content slide: real compact cover prompt, mocked API, token lines in logs."""
    mock_post.return_value = _mock_openai_image_response(
        input_tokens=512,
        output_tokens=1280,
        cached_tokens=400,
    )
    expected_prompt = _expected_real_prompt(role="content", prompt_mode="compact")

    saved = generate_scene_images(
        _project_for_slide_role("content"),
        images_dir=tmp_path / "images",
        provider="chatgpt",
        force=True,
    )

    assert len(saved) == 1
    assert saved[0].read_bytes() == b"hello"
    assert mock_post.call_count == 1

    api_prompt = mock_post.call_args.kwargs["json"]["prompt"]
    assert api_prompt == expected_prompt
    assert SAMPLE_SLIDES["content"]["title"] in api_prompt
    assert "SCENE VARIABLES" in api_prompt
    assert get_image_prompt_static_prefix(COVER_COMPACT)[:80] in api_prompt

    payload = mock_post.call_args.kwargs["json"]
    assert payload["quality"] == "medium"
    assert payload["size"] == "896x1600"

    output = capsys.readouterr().out
    assert "in=512" in output
    assert "out=1280" in output
    assert "cached=400" in output
    assert "tokens in=512 out=1280" in output
    assert re.search(r"slide 2/1 saved: scene_1\.png", output)


@pytest.mark.live
@pytest.mark.parametrize(
    ("slide_role", "prompt_mode", "quality", "size"),
    IMAGE_EXPERIMENT_CASES,
)
@pytest.mark.skipif(
    not os.environ.get("RUN_LIVE_IMAGE_TESTS"),
    reason="Set RUN_LIVE_IMAGE_TESTS=1 to call the real OpenAI image API",
)
def test_live_slide_image_setting_experiment(
    slide_role: str,
    prompt_mode: str,
    quality: str,
    size: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Live: one slide per case using production prompts; saves PNG + logs token usage."""
    load_dotenv(_REPO_ROOT / ".env", override=False)
    if not os.environ.get("OPENAI_IMAGE_API_KEY", "").strip():
        pytest.skip("OPENAI_IMAGE_API_KEY not set")

    out_path = _experiment_image_path(
        role=slide_role,
        prompt_mode=prompt_mode,
        quality=quality,
        size=size,
    )
    _EXPERIMENT_DIR.mkdir(parents=True, exist_ok=True)

    env = {
        "OPENAI_IMAGE_PROMPT_MODE": prompt_mode,
        "OPENAI_IMAGE_QUALITY": quality,
        "OPENAI_IMAGE_SIZE": size,
    }
    with patch.dict(os.environ, env, clear=False):
        saved = generate_scene_images(
            _project_for_slide_role(slide_role),
            images_dir=out_path.parent,
            provider="chatgpt",
            force=True,
        )

    assert len(saved) == 1
    assert saved[0].stat().st_size > 0
    saved[0].replace(out_path)

    output = capsys.readouterr().out
    in_match = re.search(r"in=(\d+)", output)
    out_match = re.search(r"out=(\d+)", output)
    assert in_match, f"expected input token count in logs; got:\n{output}"
    assert out_match, f"expected output token count in logs; got:\n{output}"
    assert int(in_match.group(1)) > 0
    assert int(out_match.group(1)) > 0

    print(
        f"\n[experiment] {slide_role} prompt={prompt_mode} quality={quality} size={size}\n"
        f"  saved: {out_path}\n"
        f"  tokens: in={in_match.group(1)} out={out_match.group(1)}\n"
        f"  bytes: {out_path.stat().st_size:,}"
    )
