"""Tests for core/caption_tokens.py."""

from __future__ import annotations

import pytest

from core.caption_tokens import (
    _scene_word_timestamps,
    build_karaoke_tokens_from_scenes,
    build_sentence_tokens_from_scenes,
    enrich_tokens_with_timestamps,
    match_word_timestamp,
    merge_styled_tokens_with_timestamps,
    normalize_caption_token,
    normalize_match_text,
    split_tts_sentences,
)


def test_normalize_caption_token_canonical_unchanged() -> None:
    token = {"text": "hello", "style": "primary", "animation": "none"}
    assert normalize_caption_token(token) == token


def test_normalize_caption_token_from_legacy() -> None:
    legacy = {"word": "90%", "highlight_color": "yellow", "animation_pop": "sudden_snap"}
    normalized = normalize_caption_token(legacy)
    assert normalized["text"] == "90%"
    assert normalized["style"] == "highlight"
    assert normalized["animation"] == "pop"


def test_enrich_tokens_with_timestamps_sequential_match() -> None:
    tokens = [{"text": "Hello", "style": "primary", "animation": "none"}]
    timestamps = [{"text": "Hello", "start_ms": 0, "end_ms": 200}]
    enriched = enrich_tokens_with_timestamps(tokens, timestamps)
    assert enriched[0]["start_ms"] == 0
    assert enriched[0]["spoken_text"] == "Hello"


def test_merge_styled_tokens_by_index() -> None:
    styled = [
        {"text": "Nam.", "style": "primary", "animation": "none"},
        {"text": "4000", "style": "highlight", "animation": "pop"},
    ]
    timestamps = [
        {"text": "Nam", "start_ms": 100, "end_ms": 200},
        {"text": "4000", "start_ms": 200, "end_ms": 300},
    ]
    merged = merge_styled_tokens_with_timestamps(styled, timestamps)
    assert merged[0]["text"] == "Nam."
    assert merged[0]["spoken_text"] == "Nam"
    assert merged[0]["start_ms"] == 100
    assert merged[1]["animation"] == "pop"


def test_merge_styled_tokens_rejects_count_mismatch() -> None:
    with pytest.raises(ValueError, match="does not match"):
        merge_styled_tokens_with_timestamps([{"text": "a"}], [])


def test_enrich_tokens_skips_when_timing_already_present() -> None:
    tokens = [{"text": "Hi", "start_ms": 10, "end_ms": 50}]
    enriched = enrich_tokens_with_timestamps(tokens, [])
    assert enriched[0]["start_ms"] == 10


def test_normalize_match_text_strips_trailing_punctuation() -> None:
    assert normalize_match_text("Nam.") == "nam"
    assert normalize_match_text("vậy,") == "vậy"
    assert normalize_match_text("Nam") == "nam"


def test_enrich_tokens_matches_display_punctuation_to_tts() -> None:
    tokens = [{"word": "Nam.", "highlight_color": "none", "animation_pop": "none"}]
    timestamps = [{"text": "Nam", "start_ms": 1762, "end_ms": 2087}]
    enriched = enrich_tokens_with_timestamps(tokens, timestamps)
    assert enriched[0]["start_ms"] == 1762
    assert enriched[0]["text"] == "Nam."


def test_failed_match_does_not_drain_cursor_for_next_token() -> None:
    tokens = [
        {"text": "UNKNOWN", "style": "primary", "animation": "none"},
        {"text": "Hello", "style": "primary", "animation": "none"},
    ]
    timestamps = [{"text": "Hello", "start_ms": 0, "end_ms": 200}]
    enriched = enrich_tokens_with_timestamps(tokens, timestamps)
    assert "start_ms" not in enriched[0]
    assert enriched[1]["start_ms"] == 0


def test_match_word_timestamp_sequential_only_checks_cursor() -> None:
    timestamps = [
        {"text": "A", "start_ms": 0, "end_ms": 100},
        {"text": "B", "start_ms": 100, "end_ms": 200},
    ]
    timing, cursor = match_word_timestamp("B", timestamps, 0)
    assert timing is None
    assert cursor == 0

    timing, cursor = match_word_timestamp("A", timestamps, 0)
    assert timing is not None
    assert timing["text"] == "A"
    assert cursor == 1


def test_split_tts_sentences_splits_on_period_question_exclamation() -> None:
    assert split_tts_sentences("Câu một. Câu hai? Câu ba!") == [
        "Câu một.",
        "Câu hai?",
        "Câu ba!",
    ]


def test_split_tts_sentences_preserves_ellipsis() -> None:
    assert split_tts_sentences("Hơn cả thời... đôi mắt sâu. Kết thúc.") == [
        "Hơn cả thời... đôi mắt sâu.",
        "Kết thúc.",
    ]


def test_split_tts_sentences_keeps_trailing_fragment_without_punctuation() -> None:
    assert split_tts_sentences("Câu một. Không dấu") == ["Câu một.", "Không dấu"]


def test_build_sentence_tokens_two_sentences_one_scene() -> None:
    scenes = [
        {
            "id": 1,
            "tts": "Câu một. Câu hai.",
            "start_ms": 0,
            "end_ms": 3000,
        }
    ]
    word_timestamps = [
        {"text": "Câu", "start_ms": 0, "end_ms": 100},
        {"text": "một", "start_ms": 100, "end_ms": 500},
        {"text": "Câu", "start_ms": 800, "end_ms": 900},
        {"text": "hai", "start_ms": 900, "end_ms": 1200},
    ]
    tokens = build_sentence_tokens_from_scenes(scenes, word_timestamps)
    assert len(tokens) == 2
    assert tokens[0]["text"] == "Câu một."
    assert tokens[0]["start_ms"] == 0
    assert tokens[0]["end_ms"] == 500
    assert tokens[1]["text"] == "Câu hai."
    assert tokens[1]["start_ms"] == 800
    assert tokens[1]["end_ms"] == 1200


def test_build_sentence_tokens_three_scenes_one_sentence_each() -> None:
    scenes = [
        {"id": 1, "tts": "A.", "start_ms": 0, "end_ms": 1000},
        {"id": 2, "tts": "B.", "start_ms": 1000, "end_ms": 2000},
        {"id": 3, "tts": "C.", "start_ms": 2000, "end_ms": 3000},
    ]
    word_timestamps = [
        {"text": "A", "start_ms": 0, "end_ms": 200},
        {"text": "B", "start_ms": 1000, "end_ms": 1200},
        {"text": "C", "start_ms": 2000, "end_ms": 2200},
    ]
    tokens = build_sentence_tokens_from_scenes(scenes, word_timestamps)
    assert len(tokens) == 3
    assert tokens[1]["start_ms"] == 1000


def test_build_sentence_tokens_without_word_timestamps_uses_scene_boundaries() -> None:
    scenes = [
        {"id": 1, "tts": "Câu một. Câu hai.", "start_ms": 0, "end_ms": 5000},
    ]
    tokens = build_sentence_tokens_from_scenes(scenes)
    assert len(tokens) == 1
    assert tokens[0]["text"] == "Câu một. Câu hai."
    assert tokens[0]["start_ms"] == 0
    assert tokens[0]["end_ms"] == 5000


def test_scene_word_timestamps_includes_overlap_at_boundary() -> None:
    words = [
        {"text": "end", "start_ms": 13500, "end_ms": 13800},
        {"text": "start", "start_ms": 13700, "end_ms": 13900},
    ]
    scene2 = _scene_word_timestamps(words, 13700, 26680)
    assert len(scene2) == 2
    assert scene2[1]["text"] == "start"


def test_build_karaoke_tokens_per_scene_cursor_resets() -> None:
    scenes = [
        {"id": 1, "tts": "A.", "start_ms": 0, "end_ms": 1000},
        {"id": 2, "tts": "B.", "start_ms": 1000, "end_ms": 2000},
    ]
    words_by_scene = {
        1: [{"text": "A", "start_ms": 0, "end_ms": 200}],
        2: [{"text": "B", "start_ms": 1000, "end_ms": 1200}],
    }
    tokens = build_karaoke_tokens_from_scenes(scenes, words_by_scene)
    assert len(tokens) == 2
    assert tokens[1]["words"][0]["text"] == "B."
    assert len(tokens[1]["words"]) == 1
