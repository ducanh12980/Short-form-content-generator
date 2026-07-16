"""Tests for slideshow pipeline, schema helpers, and slide image prompts."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.caption_tokens import build_sentence_tokens_from_scenes
from core.project_schema import (
    CONTENT_SCENE_COUNT,
    DEFAULT_TRANSITION_ROTATION,
    TOTAL_SLIDE_COUNT,
    assign_slide_transitions,
    build_image_timeline_from_scenes,
    build_image_timeline_from_slides,
    get_caption_mode,
    get_narration_duration_ms,
    get_scenes,
    get_slides,
    normalize_project,
    slide_image_filename,
)
from core.prompt_loader import substitute_prompt
from core.slide_image_stage import (
    COVER_SLIDE_PROMPT_COMPACT_PATH,
    COVER_SLIDE_PROMPT_PATH,
    _extract_openai_image_bytes,
    _format_openai_image_usage,
    _parse_openai_image_usage,
    assemble_cached_image_prompt,
    build_pollinations_prompt,
    build_slide_image_prompt as stage_build_prompt,
    get_image_prompt_static_prefix,
    resolve_image_provider,
    resolve_openai_image_prompt_mode,
)
from core.slideshow_pipeline import (
    parse_publish_metadata,
    parse_scene_script_response,
    run_slideshow_pipeline,
)


def _sample_publish() -> dict:
    return {
        "title": "Hiểu người qua Nhân tướng học",
        "description": "Không phải bói toán — đây là cách nhìn người và hiểu mình sâu hơn.",
        "hashtags": ["#NhanTuongVN", "#trietly", "#hieunguoi", "#fyp"],
    }


def _sample_script_payload() -> dict:
    return {
        "intro": {
            "title": "Hook",
            "visual_concept": "Dawn light through carved wooden window, mirror reflection.",
        },
        "scenes": [
            {"title": "Hiểu người", "description": "Dòng mô tả một."},
            {"title": "Hiểu mình", "description": "Dòng mô tả hai."},
            {"title": "Sống khôn", "description": "Dòng mô tả ba."},
        ],
        "ending": {
            "title": "Kết",
            "visual_concept": "Stone path at sunset fading into soft mist.",
        },
        "publish": _sample_publish(),
    }


def _sample_slides() -> list[dict]:
    return [
        {
            "id": 1,
            "role": "intro",
            "title": "Hook",
            "visual_concept": "Dawn through wooden window.",
            "start_ms": 0,
            "end_ms": 2500,
            "image": {"path": "output/images/intro.png", "source": "dalle"},
        },
        {
            "id": 2,
            "role": "content",
            "content_index": 1,
            "title": "Hiểu người",
            "description": "Dòng mô tả một.",
            "tts": "Câu nói scene một.",
            "start_ms": 2500,
            "end_ms": 7500,
            "image": {"path": "output/images/scene_1.png", "source": "dalle"},
        },
        {
            "id": 3,
            "role": "content",
            "content_index": 2,
            "title": "Hiểu mình",
            "description": "Dòng mô tả hai.",
            "tts": "Câu nói scene hai.",
            "start_ms": 7500,
            "end_ms": 12500,
            "image": {"path": "output/images/scene_2.png", "source": "dalle"},
        },
        {
            "id": 4,
            "role": "content",
            "content_index": 3,
            "title": "Sống khôn",
            "description": "Dòng mô tả ba.",
            "tts": "Câu nói scene ba.",
            "start_ms": 12500,
            "end_ms": 17500,
            "image": {"path": "output/images/scene_3.png", "source": "dalle"},
        },
        {
            "id": 5,
            "role": "ending",
            "title": "Kết",
            "visual_concept": "Sunset stone path.",
            "start_ms": 17500,
            "end_ms": 20000,
            "image": {"path": "output/images/ending.png", "source": "dalle"},
        },
    ]


def _sample_scenes() -> list[dict]:
    return [
        {
            "id": 2,
            "role": "content",
            "content_index": 1,
            "title": "Hiểu người",
            "description": "Dòng mô tả một.",
            "tts": "Câu nói scene một.",
            "start_ms": 0,
            "end_ms": 5000,
            "image": {"path": "output/images/scene_1.png", "source": "dalle"},
        },
        {
            "id": 3,
            "role": "content",
            "content_index": 2,
            "title": "Hiểu mình",
            "description": "Dòng mô tả hai.",
            "tts": "Câu nói scene hai.",
            "start_ms": 5000,
            "end_ms": 10000,
            "image": {"path": "output/images/scene_2.png", "source": "dalle"},
        },
        {
            "id": 4,
            "role": "content",
            "content_index": 3,
            "title": "Sống khôn",
            "description": "Dòng mô tả ba.",
            "tts": "Câu nói scene ba.",
            "start_ms": 10000,
            "end_ms": 15000,
            "image": {"path": "output/images/scene_3.png", "source": "dalle"},
        },
    ]


def test_parse_scene_script_response_accepts_intro_content_ending() -> None:
    slides = parse_scene_script_response(json.dumps(_sample_script_payload()))
    assert len(slides) == TOTAL_SLIDE_COUNT
    assert slides[0]["role"] == "intro"
    assert slides[0]["id"] == 1
    assert "visual_concept" in slides[0]
    assert "description" not in slides[0]
    assert slides[1]["role"] == "content"
    assert slides[1]["content_index"] == 1
    assert slides[-1]["role"] == "ending"
    assert "tts" not in slides[0]


def test_parse_publish_metadata_accepts_valid_block() -> None:
    publish = parse_publish_metadata(_sample_script_payload())
    assert publish["title"] == "Hiểu người qua Nhân tướng học"
    assert "#fyp" in publish["hashtags"]


def test_parse_publish_metadata_normalizes_hashtags_without_hash() -> None:
    payload = _sample_script_payload()
    payload["publish"]["hashtags"] = ["tag1", "tag2", "tag3"]
    publish = parse_publish_metadata(payload)
    assert publish["hashtags"] == ["#tag1", "#tag2", "#tag3"]


def test_parse_publish_metadata_repairs_missing_hashtags() -> None:
    payload = _sample_script_payload()
    del payload["publish"]["hashtags"]
    publish = parse_publish_metadata(payload)
    assert len(publish["hashtags"]) >= 3
    assert "#fyp" in publish["hashtags"]


def test_parse_publish_metadata_coerces_string_hashtags() -> None:
    payload = _sample_script_payload()
    payload["publish"]["hashtags"] = "#tag1 #tag2 #tag3"
    publish = parse_publish_metadata(payload)
    assert publish["hashtags"] == ["#tag1", "#tag2", "#tag3"]


def test_parse_publish_metadata_rejects_missing_block() -> None:
    payload = _sample_script_payload()
    del payload["publish"]
    with pytest.raises(ValueError, match="publish"):
        parse_publish_metadata(payload)


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
    payload = {
        "intro": {"title": "A", "visual_concept": "hero visual"},
        "scenes": [{"title": "A", "description": "d"}],
        "ending": {"title": "Z", "visual_concept": "closing visual"},
    }
    with pytest.raises(ValueError, match=f"exactly {CONTENT_SCENE_COUNT}"):
        parse_scene_script_response(json.dumps(payload))


def test_parse_scene_script_response_rejects_missing_field() -> None:
    payload = _sample_script_payload()
    payload["ending"] = {"title": "only title"}
    with pytest.raises(ValueError, match="visual_concept"):
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


def test_build_image_timeline_from_slides() -> None:
    timeline = build_image_timeline_from_slides(_sample_slides())
    assert len(timeline) == TOTAL_SLIDE_COUNT
    assert timeline[1]["start_ms"] == 2500
    assert timeline[1]["role"] == "content"
    assert timeline[0]["transition"] == "pullIn"
    assert timeline[1]["transition"] == "teleportShake"


def test_assign_slide_transitions_rotation() -> None:
    slides = _sample_slides()
    assign_slide_transitions(slides)
    assert slides[0]["transition"] == DEFAULT_TRANSITION_ROTATION[0]
    assert slides[1]["transition"] == DEFAULT_TRANSITION_ROTATION[1]
    assert slides[2]["transition"] == "whipPan"
    assert slides[4]["transition"] == DEFAULT_TRANSITION_ROTATION[4 % len(DEFAULT_TRANSITION_ROTATION)]


def test_assign_slide_transitions_whip_pan_at_index_two() -> None:
    slides = _sample_slides()
    assign_slide_transitions(slides)
    assert slides[2]["transition"] == "whipPan"


def test_build_image_timeline_preserves_whip_pan_override() -> None:
    slides = _sample_slides()
    slides[1]["transition"] = "whipPan"
    timeline = build_image_timeline_from_slides(slides)
    assert timeline[1]["transition"] == "whipPan"


def test_assign_slide_transitions_respects_override() -> None:
    slides = _sample_slides()
    slides[1]["transition"] = "teleportShake"
    assign_slide_transitions(slides)
    assert slides[1]["transition"] == "teleportShake"
    assert slides[0]["transition"] == "pullIn"


def test_build_image_timeline_preserves_transition_override() -> None:
    slides = _sample_slides()
    slides[2]["transition"] = "zoomBlur"
    timeline = build_image_timeline_from_slides(slides)
    assert timeline[2]["transition"] == "zoomBlur"


def test_build_image_timeline_from_scenes() -> None:
    timeline = build_image_timeline_from_scenes(_sample_scenes())
    assert len(timeline) == CONTENT_SCENE_COUNT
    assert timeline[0]["start_ms"] == 0
    assert timeline[0]["scene_id"] == 2


def test_slide_image_filename_by_role() -> None:
    assert slide_image_filename({"role": "intro"}) == "intro.png"
    assert slide_image_filename({"role": "ending"}) == "ending.png"
    assert slide_image_filename({"role": "content", "content_index": 2}) == "scene_2.png"


def test_normalize_project_slideshow_shape() -> None:
    data = {
        "topic": "test",
        "slides": _sample_slides(),
        "scenes": _sample_scenes(),
        "audio": {"path": "output/narration.mp3"},
    }
    project = normalize_project(data)
    assert get_slides(project)
    assert len(get_scenes(project)) == CONTENT_SCENE_COUNT
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
    prompt = stage_build_prompt(
        title="Tiêu đề",
        description="Mô tả",
        topic="Chủ đề",
        prompt_mode="full",
    )
    assert "Tiêu đề" in prompt
    assert "Mô tả" in prompt
    assert "Chủ đề" in prompt
    assert "{{TITLE}}" not in prompt


@patch.dict(os.environ, {"OPENAI_IMAGE_PROMPT_MODE": "compact"}, clear=False)
def test_compact_prompt_shorter_than_full() -> None:
    kwargs = {"title": "Tiêu đề", "description": "Mô tả dài.", "topic": "Chủ đề"}
    compact = stage_build_prompt(**kwargs, prompt_mode="compact")
    full = stage_build_prompt(**kwargs, prompt_mode="full")
    assert len(compact) < len(full)
    assert "Tiêu đề" in compact
    assert "{{TITLE}}" not in compact


def test_resolve_openai_image_prompt_mode_defaults_compact() -> None:
    with patch.dict(os.environ, {}, clear=True):
        assert resolve_openai_image_prompt_mode() == "compact"


def test_cached_prompt_static_prefix_identical_for_same_template() -> None:
    prefix_a = get_image_prompt_static_prefix(COVER_SLIDE_PROMPT_PATH)
    prefix_b = get_image_prompt_static_prefix(COVER_SLIDE_PROMPT_COMPACT_PATH)
    assert prefix_a
    assert prefix_b
    prompt_a = assemble_cached_image_prompt(
        COVER_SLIDE_PROMPT_PATH,
        {"TITLE": "A", "DESCRIPTION": "Desc A", "TOPIC": "Topic"},
    )
    prompt_b = assemble_cached_image_prompt(
        COVER_SLIDE_PROMPT_PATH,
        {"TITLE": "B", "DESCRIPTION": "Desc B", "TOPIC": "Topic"},
    )
    assert prompt_a.startswith(prefix_a)
    assert prompt_b.startswith(prefix_a)
    assert prefix_a == get_image_prompt_static_prefix(COVER_SLIDE_PROMPT_PATH)
    assert prompt_a.split(prefix_a, 1)[1] != prompt_b.split(prefix_a, 1)[1]


def test_build_bookend_slide_image_prompt_includes_visual_concept() -> None:
    from core.slide_image_stage import build_bookend_slide_image_prompt

    prompt = build_bookend_slide_image_prompt(
        title="Mở đầu",
        visual_concept="Gương đồng trong ánh sáng bình minh.",
        topic="Nhân tướng học",
        slide_role="intro",
        prompt_mode="full",
    )
    assert "Mở đầu" in prompt
    assert "Gương đồng" in prompt
    assert "no description" in prompt.lower() or "No description" in prompt
    assert "{{TITLE}}" not in prompt


def test_build_pollinations_bookend_prompt_hero_visual() -> None:
    from core.slide_image_stage import build_pollinations_bookend_prompt

    prompt = build_pollinations_bookend_prompt(
        title="Kết",
        visual_concept="Stone path at sunset.",
        topic="Topic",
        slide_role="ending",
    )
    assert "Stone path" in prompt
    assert "No description paragraph" in prompt


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


def test_extract_openai_image_bytes_from_b64_json() -> None:
    payload = {
        "data": [
            {"b64_json": "aGVsbG8="},
        ]
    }
    assert _extract_openai_image_bytes(payload) == b"hello"


def test_parse_openai_image_usage() -> None:
    payload = {
        "usage": {
            "input_tokens": 1200,
            "output_tokens": 3400,
            "total_tokens": 4600,
            "input_tokens_details": {
                "text_tokens": 1200,
                "image_tokens": 0,
                "cached_tokens": 900,
            },
        }
    }
    assert _parse_openai_image_usage(payload) == {
        "input_tokens": 1200,
        "output_tokens": 3400,
        "total_tokens": 4600,
        "cached_tokens": 900,
    }
    assert (
        _format_openai_image_usage(_parse_openai_image_usage(payload))
        == "in=1200 (cached=900), out=3400"
    )


def test_parse_openai_image_usage_missing() -> None:
    assert _parse_openai_image_usage({}) is None
    assert _format_openai_image_usage(None) == "tokens unavailable"


@patch("core.slide_image_stage.requests.post")
@patch.dict(
    os.environ,
    {
        "OPENAI_IMAGE_API_KEY": "openai-test-key",
        "OPENAI_IMAGE_QUALITY": "medium",
    },
    clear=False,
)
def test_generate_slide_image_chatgpt_writes_file(mock_post: MagicMock, tmp_path: Path) -> None:
    from core.slide_image_stage import generate_slide_image

    mock_post.return_value = MagicMock(
        status_code=200,
        json=lambda: {
            "data": [
                {"b64_json": "aGVsbG8="},
            ],
            "usage": {
                "input_tokens": 500,
                "output_tokens": 1500,
                "total_tokens": 2000,
            },
            "quality": "medium",
        },
    )
    out = tmp_path / "scene_1.png"
    usage: list[dict[str, int]] = []
    qualities: list[str] = []
    generate_slide_image(
        "prompt text",
        out,
        provider="chatgpt",
        token_usage_out=usage,
        resolved_quality_out=qualities,
    )
    assert out.read_bytes() == b"hello"
    assert usage == [{"input_tokens": 500, "output_tokens": 1500, "total_tokens": 2000}]
    assert qualities == ["medium"]
    assert mock_post.call_args.kwargs["headers"]["Authorization"] == "Bearer openai-test-key"
    assert mock_post.call_args.kwargs["json"]["model"] == "gpt-image-2"
    assert mock_post.call_args.kwargs["json"]["quality"] == "medium"


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

    scene_payload = _sample_script_payload()
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
            {"scene_id": 2, "start_ms": 0, "end_ms": 1000},
            {"scene_id": 3, "start_ms": 1000, "end_ms": 2000},
            {"scene_id": 4, "start_ms": 2000, "end_ms": 3000},
        ],
        [
            {"text": "ta", "start_ms": 0, "end_ms": 500},
            {"text": "tb", "start_ms": 1000, "end_ms": 1500},
            {"text": "tc", "start_ms": 2000, "end_ms": 2500},
        ],
        {2: [{"text": "ta", "start_ms": 0, "end_ms": 500}], 3: [], 4: []},
    )

    def _fake_images(project: dict, **kwargs) -> list[Path]:
        provider = kwargs.get("provider")
        for slide in project["slides"]:
            from core.project_schema import slide_image_filename

            slide["image"] = {
                "path": str((tmp_path / "images" / slide_image_filename(slide)).resolve()),
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
    assert len(result["slides"]) == TOTAL_SLIDE_COUNT
    assert len(result["scenes"]) == CONTENT_SCENE_COUNT
    assert result["publish"]["title"] == _sample_publish()["title"]
    assert result["slides"][0]["start_ms"] == 0
    assert result["slides"][0]["end_ms"] == 312
    assert result["slides"][1]["end_ms"] == 937
    assert result["slides"][-1]["end_ms"] == 2500
    # One entry per slide, plus the brand end card appended after narration.
    images = result["video"]["images"]
    assert len(images) == TOTAL_SLIDE_COUNT + 1
    assert images[-1]["role"] == "endcard"
    assert images[-1]["start_ms"] == 2500
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
    scene_payload = _sample_script_payload()
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
            {"scene_id": 2, "start_ms": 0, "end_ms": 1000},
            {"scene_id": 3, "start_ms": 1000, "end_ms": 2000},
            {"scene_id": 4, "start_ms": 2000, "end_ms": 3000},
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
            2: [
                {"text": "Câu", "start_ms": 0, "end_ms": 100},
                {"text": "một", "start_ms": 100, "end_ms": 300},
                {"text": "Câu", "start_ms": 400, "end_ms": 500},
                {"text": "hai", "start_ms": 500, "end_ms": 700},
            ],
            3: [{"text": "Câu", "start_ms": 1000, "end_ms": 1100}, {"text": "ba", "start_ms": 1100, "end_ms": 1300}],
            4: [{"text": "Câu", "start_ms": 2000, "end_ms": 2100}, {"text": "bốn", "start_ms": 2100, "end_ms": 2300}],
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
