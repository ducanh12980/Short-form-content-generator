"""Tests for slideshow pipeline, schema helpers, and slide image prompts."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.caption_tokens import build_sentence_tokens_from_scenes
from core.project_schema import (
    build_image_timeline_from_scenes,
    get_caption_mode,
    get_narration_duration_ms,
    get_scenes,
    normalize_project,
)
from core.prompt_loader import substitute_prompt
from core.slide_image_stage import (
    _extract_image_bytes,
    build_pollinations_prompt,
    build_slide_image_prompt as stage_build_prompt,
    resolve_image_provider,
)
from core.slideshow_pipeline import parse_scene_script_response, run_slideshow_pipeline


def _sample_scenes() -> list[dict]:
    return [
        {
            "id": 1,
            "title": "Hiểu người",
            "description": "Dòng mô tả một.",
            "tts": "Câu nói scene một.",
            "start_ms": 0,
            "end_ms": 5000,
            "image": {"path": "output/images/scene_1.png", "source": "dalle"},
        },
        {
            "id": 2,
            "title": "Hiểu mình",
            "description": "Dòng mô tả hai.",
            "tts": "Câu nói scene hai.",
            "start_ms": 5000,
            "end_ms": 10000,
            "image": {"path": "output/images/scene_2.png", "source": "dalle"},
        },
        {
            "id": 3,
            "title": "Sống khôn",
            "description": "Dòng mô tả ba.",
            "tts": "Câu nói scene ba.",
            "start_ms": 10000,
            "end_ms": 15000,
            "image": {"path": "output/images/scene_3.png", "source": "dalle"},
        },
    ]


def test_parse_scene_script_response_accepts_three_scenes() -> None:
    payload = {
        "scenes": [
            {"title": "A", "description": "desc a"},
            {"title": "B", "description": "desc b"},
            {"title": "C", "description": "desc c"},
        ]
    }
    scenes = parse_scene_script_response(json.dumps(payload))
    assert len(scenes) == 3
    assert scenes[0]["id"] == 1
    assert scenes[2]["title"] == "C"
    assert "tts" not in scenes[0]


def test_parse_tts_writer_response_accepts_three_blocks() -> None:
    from core.slideshow_pipeline import parse_tts_writer_response

    payload = {
        "scenes": [
            {"tts": "tts a"},
            {"tts": "tts b"},
            {"tts": "tts c"},
        ]
    }
    blocks = parse_tts_writer_response(json.dumps(payload))
    assert blocks == ["tts a", "tts b", "tts c"]


def test_format_slide_content_for_tts() -> None:
    from core.slideshow_pipeline import format_slide_content_for_tts

    text = format_slide_content_for_tts(
        [{"id": 1, "title": "Tiêu đề", "description": "Mô tả ngắn."}]
    )
    assert "Slide 1" in text
    assert "Tiêu đề" in text
    assert "Mô tả ngắn." in text


def test_parse_scene_script_response_rejects_wrong_count() -> None:
    payload = {"scenes": [{"title": "A", "description": "d"}]}
    with pytest.raises(ValueError, match="exactly 3"):
        parse_scene_script_response(json.dumps(payload))


def test_parse_scene_script_response_rejects_missing_field() -> None:
    payload = {
        "scenes": [
            {"title": "A", "description": "d"},
            {"title": "B", "description": "d"},
            {"title": "C", "title": "only title"},
        ]
    }
    with pytest.raises(ValueError, match="description"):
        parse_scene_script_response(json.dumps(payload))


def test_build_sentence_tokens_from_scenes() -> None:
    scenes = _sample_scenes()
    tokens = build_sentence_tokens_from_scenes(scenes)
    assert len(tokens) == 3
    assert tokens[0]["text"] == "Câu nói scene một."
    assert tokens[0]["start_ms"] == 0
    assert tokens[0]["end_ms"] == 5000


def test_build_sentence_tokens_from_scenes_with_word_timestamps() -> None:
    scenes = [
        {
            "id": 1,
            "tts": "Câu nói scene một. Câu thứ hai.",
            "start_ms": 0,
            "end_ms": 5000,
        }
    ]
    word_timestamps = [
        {"text": "Câu", "start_ms": 0, "end_ms": 100},
        {"text": "nói", "start_ms": 100, "end_ms": 200},
        {"text": "scene", "start_ms": 200, "end_ms": 300},
        {"text": "một", "start_ms": 300, "end_ms": 400},
        {"text": "Câu", "start_ms": 800, "end_ms": 900},
        {"text": "thứ", "start_ms": 900, "end_ms": 1000},
        {"text": "hai", "start_ms": 1000, "end_ms": 1100},
    ]
    tokens = build_sentence_tokens_from_scenes(scenes, word_timestamps)
    assert len(tokens) == 2
    assert tokens[0]["end_ms"] == 400
    assert tokens[1]["start_ms"] == 800


def test_build_image_timeline_from_scenes() -> None:
    timeline = build_image_timeline_from_scenes(_sample_scenes())
    assert len(timeline) == 3
    assert timeline[1]["start_ms"] == 5000
    assert timeline[1]["scene_id"] == 2


def test_normalize_project_slideshow_shape() -> None:
    data = {
        "topic": "test",
        "scenes": _sample_scenes(),
        "audio": {"path": "output/narration.mp3"},
    }
    project = normalize_project(data)
    assert get_scenes(project)
    assert get_caption_mode(project) == "none"
    assert "captions" in project


def test_get_narration_duration_from_scene_timestamps() -> None:
    project = {
        "audio": {
            "scene_timestamps": [
                {"scene_id": 1, "start_ms": 0, "end_ms": 5000},
                {"scene_id": 2, "start_ms": 5000, "end_ms": 12000},
            ]
        }
    }
    assert get_narration_duration_ms(project) == 12000


def test_substitute_prompt_replaces_variables() -> None:
    result = substitute_prompt("Hello {{TITLE}} — {{TOPIC}}", {"TITLE": "X", "TOPIC": "Y"})
    assert result == "Hello X — Y"


def test_build_slide_image_prompt_includes_title() -> None:
    prompt = stage_build_prompt(title="Tiêu đề", description="Mô tả", topic="Chủ đề")
    assert "Tiêu đề" in prompt
    assert "Mô tả" in prompt
    assert "Chủ đề" in prompt
    assert "{{TITLE}}" not in prompt


def test_build_pollinations_prompt_is_background_only() -> None:
    prompt = build_pollinations_prompt(
        title="Quan Sát",
        description="Mô tả ngắn.",
        topic="Nhân tướng học",
    )
    assert "No text" in prompt
    assert "Nhân tướng học" in prompt
    assert len(prompt) < 2000


@patch.dict(os.environ, {"IMAGE_PROVIDER": "pollinations"}, clear=False)
def test_resolve_image_provider_defaults_to_pollinations() -> None:
    assert resolve_image_provider() == "pollinations"
    assert resolve_image_provider("mock") == "mock"


def test_resolve_image_provider_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="IMAGE_PROVIDER"):
        resolve_image_provider("unknown")


def test_extract_image_bytes_from_gemini_response() -> None:
    payload = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"inlineData": {"mimeType": "image/png", "data": "aGVsbG8="}}
                    ]
                }
            }
        ]
    }
    assert _extract_image_bytes(payload) == b"hello"


@patch("core.slide_image_stage.requests.post")
@patch.dict(os.environ, {"OPENAI_API_KEY": "gemini-test-key"}, clear=False)
def test_generate_slide_image_gemini_writes_file(mock_post: MagicMock, tmp_path: Path) -> None:
    from core.slide_image_stage import generate_slide_image

    mock_post.return_value = MagicMock(
        status_code=200,
        json=lambda: {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"inlineData": {"mimeType": "image/png", "data": "aGVsbG8="}}
                        ]
                    }
                }
            ]
        },
    )
    out = tmp_path / "scene_1.png"
    generate_slide_image("prompt text", out, provider="gemini")
    assert out.read_bytes() == b"hello"
    assert mock_post.call_args.kwargs["headers"]["x-goog-api-key"] == "gemini-test-key"


@patch("core.slide_image_stage.requests.get")
def test_generate_slide_image_pollinations_writes_file(mock_get: MagicMock, tmp_path: Path) -> None:
    from core.slide_image_stage import generate_slide_image

    mock_get.return_value = MagicMock(
        status_code=200,
        content=b"pollinations-bytes",
        headers={"Content-Type": "image/jpeg"},
    )
    out = tmp_path / "scene_1.png"
    generate_slide_image("mountain scene", out, provider="pollinations")
    assert out.read_bytes() == b"pollinations-bytes"
    assert "image.pollinations.ai" in mock_get.call_args.args[0]


def test_generate_slide_image_mock_writes_file(tmp_path: Path) -> None:
    from core.slide_image_stage import generate_slide_image

    out = tmp_path / "scene_1.png"
    generate_slide_image("", out, provider="mock", scene_id=2, title="Test title")
    assert out.is_file()
    assert out.stat().st_size > 0


@patch.dict(os.environ, {"OPENAI_API_KEY": "k", "OPENAI_BASE_URL": "http://x"}, clear=False)
@patch("core.slideshow_pipeline.generate_scene_images")
@patch("core.slideshow_pipeline.synthesize_scene_speech")
@patch("core.slideshow_pipeline._get_client")
def test_run_slideshow_pipeline_happy_path_none_captions(
    mock_get_client: MagicMock,
    mock_synthesize: MagicMock,
    mock_images: MagicMock,
    tmp_path: Path,
) -> None:
    client = MagicMock()
    mock_get_client.return_value = client

    scene_payload = {
        "scenes": [
            {"title": "A", "description": "da"},
            {"title": "B", "description": "db"},
            {"title": "C", "description": "dc"},
        ]
    }
    tts_payload = {
        "scenes": [
            {"tts": "ta"},
            {"tts": "tb"},
            {"tts": "tc"},
        ]
    }
    client.chat.completions.create.side_effect = [
        MagicMock(choices=[MagicMock(message=MagicMock(content=json.dumps(scene_payload)))]),
        MagicMock(choices=[MagicMock(message=MagicMock(content=json.dumps(tts_payload)))]),
    ]

    mock_synthesize.return_value = (
        [
            {"scene_id": 1, "start_ms": 0, "end_ms": 1000},
            {"scene_id": 2, "start_ms": 1000, "end_ms": 2000},
            {"scene_id": 3, "start_ms": 2000, "end_ms": 3000},
        ],
        [
            {"text": "ta", "start_ms": 0, "end_ms": 500},
            {"text": "tb", "start_ms": 1000, "end_ms": 1500},
            {"text": "tc", "start_ms": 2000, "end_ms": 2500},
        ],
        {1: [{"text": "ta", "start_ms": 0, "end_ms": 500}], 2: [], 3: []},
    )

    def _fake_images(project: dict, **kwargs) -> list[Path]:
        provider = kwargs.get("provider")
        for scene in project["scenes"]:
            scene["image"] = {
                "path": str((tmp_path / "images" / f"scene_{scene['id']}.png").resolve()),
                "source": provider or "pollinations",
            }
        return []

    mock_images.side_effect = _fake_images

    result = run_slideshow_pipeline(
        "topic",
        output_dir=tmp_path,
        caption_mode="none",
    )

    assert result["caption_mode"] == "none"
    assert len(result["scenes"]) == 3
    assert result["scenes"][0]["start_ms"] == 0
    assert len(result["video"]["images"]) == 3
    assert result["captions"]["tokens"] == []
    assert (tmp_path / "pipeline_payload.json").is_file()


@patch.dict(os.environ, {"OPENAI_API_KEY": "k", "OPENAI_BASE_URL": "http://x"}, clear=False)
@patch("core.slideshow_pipeline.generate_scene_images")
@patch("core.slideshow_pipeline.synthesize_scene_speech")
@patch("core.slideshow_pipeline._get_client")
def test_run_slideshow_pipeline_sentence_captions(
    mock_get_client: MagicMock,
    mock_synthesize: MagicMock,
    mock_images: MagicMock,
    tmp_path: Path,
) -> None:
    client = MagicMock()
    mock_get_client.return_value = client
    scene_payload = {
        "scenes": [
            {"title": "A", "description": "da"},
            {"title": "B", "description": "db"},
            {"title": "C", "description": "dc"},
        ]
    }
    tts_payload = {
        "scenes": [
            {"tts": "Câu một. Câu hai."},
            {"tts": "Câu ba."},
            {"tts": "Câu bốn."},
        ]
    }
    client.chat.completions.create.side_effect = [
        MagicMock(choices=[MagicMock(message=MagicMock(content=json.dumps(scene_payload)))]),
        MagicMock(choices=[MagicMock(message=MagicMock(content=json.dumps(tts_payload)))]),
    ]
    mock_synthesize.return_value = (
        [
            {"scene_id": 1, "start_ms": 0, "end_ms": 1000},
            {"scene_id": 2, "start_ms": 1000, "end_ms": 2000},
            {"scene_id": 3, "start_ms": 2000, "end_ms": 3000},
        ],
        [
            {"text": "Câu", "start_ms": 0, "end_ms": 100},
            {"text": "một", "start_ms": 100, "end_ms": 300},
            {"text": "Câu", "start_ms": 400, "end_ms": 500},
            {"text": "hai", "start_ms": 500, "end_ms": 700},
            {"text": "Câu", "start_ms": 1000, "end_ms": 1100},
            {"text": "ba", "start_ms": 1100, "end_ms": 1300},
            {"text": "Câu", "start_ms": 2000, "end_ms": 2100},
            {"text": "bốn", "start_ms": 2100, "end_ms": 2300},
        ],
        {
            1: [
                {"text": "Câu", "start_ms": 0, "end_ms": 100},
                {"text": "một", "start_ms": 100, "end_ms": 300},
                {"text": "Câu", "start_ms": 400, "end_ms": 500},
                {"text": "hai", "start_ms": 500, "end_ms": 700},
            ],
            2: [{"text": "Câu", "start_ms": 1000, "end_ms": 1100}, {"text": "ba", "start_ms": 1100, "end_ms": 1300}],
            3: [{"text": "Câu", "start_ms": 2000, "end_ms": 2100}, {"text": "bốn", "start_ms": 2100, "end_ms": 2300}],
        },
    )
    mock_images.side_effect = lambda project, **kwargs: []

    result = run_slideshow_pipeline(
        "topic",
        output_dir=tmp_path,
        caption_mode="sentence",
    )

    assert len(result["captions"]["tokens"]) == 4
    assert result["captions"]["tokens"][0]["text"] == "Câu một."
    assert result["captions"]["tokens"][0]["start_ms"] == 0
    assert result["captions"]["tokens"][0]["end_ms"] == 300
    assert result["captions"]["tokens"][1]["text"] == "Câu hai."


@patch.dict(os.environ, {"OPENAI_API_KEY": "k", "OPENAI_BASE_URL": "http://x"}, clear=False)
@patch("core.remotion_render_stage._load_theme_styles")
def test_project_to_remotion_props_slideshow_empty_tokens(
    mock_themes: MagicMock,
    tmp_path: Path,
) -> None:
    from core.remotion_render_stage import project_to_remotion_props

    mock_themes.return_value = {"minimalist": {"font": "Arial", "font_size": 72}}

    narration = tmp_path / "narration.mp3"
    narration.write_bytes(b"fake")
    img1 = tmp_path / "images" / "scene_1.png"
    img1.parent.mkdir(parents=True)
    img1.write_bytes(b"fake")

    project = normalize_project(
        {
            "topic": "t",
            "caption_mode": "none",
            "scenes": [
                {
                    "id": 1,
                    "title": "T",
                    "description": "D",
                    "tts": "tts",
                    "start_ms": 0,
                    "end_ms": 3000,
                    "image": {"path": str(img1.resolve()), "source": "dalle"},
                }
            ],
            "captions": {"theme": "minimalist", "tokens": []},
            "video": {
                "canvas": {"width": 1080, "height": 1920},
                "images": [
                    {
                        "path": str(img1.resolve()),
                        "start_ms": 0,
                        "end_ms": 3000,
                        "scene_id": 1,
                    }
                ],
            },
            "audio": {
                "path": str(narration.resolve()),
                "word_timestamps": [{"text": "tts", "start_ms": 0, "end_ms": 3000}],
                "scene_timestamps": [{"scene_id": 1, "start_ms": 0, "end_ms": 3000}],
            },
        }
    )

    props, _public = project_to_remotion_props(project)
    assert props["tokens"] == []
    assert len(props["images"]) == 1
    assert props["images"][0]["start_ms"] == 0
