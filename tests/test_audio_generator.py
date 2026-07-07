"""Tests for edge-tts audio generator retry and scene cache behavior."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from edge_tts.exceptions import NoAudioReceived

from core import audio_generator
from core.audio_generator import (
    _load_scene_cache,
    _save_scene_cache,
    _scene_cache_paths,
    synthesize_scene_speech,
    synthesize_speech,
)


def test_synthesize_speech_retries_on_no_audio(tmp_path: Path) -> None:
    out = tmp_path / "narration.mp3"
    word_ts = [{"text": "Hi", "start_ms": 0, "end_ms": 100}]

    with (
        patch.object(audio_generator, "TTS_RETRY_ATTEMPTS", 3),
        patch.object(audio_generator, "TTS_RETRY_DELAY_SECONDS", 0),
        patch("core.audio_generator.asyncio.run") as mock_run,
    ):
        mock_run.side_effect = [
            NoAudioReceived("no audio"),
            word_ts,
        ]
        result = synthesize_speech("Xin chào", out, voice="vi-VN-HoaiMyNeural")

    assert result == word_ts
    assert mock_run.call_count == 2


def test_synthesize_speech_raises_after_exhausted_retries(tmp_path: Path) -> None:
    out = tmp_path / "narration.mp3"

    with (
        patch.object(audio_generator, "TTS_RETRY_ATTEMPTS", 2),
        patch.object(audio_generator, "TTS_RETRY_DELAY_SECONDS", 0),
        patch("core.audio_generator.asyncio.run") as mock_run,
    ):
        mock_run.side_effect = NoAudioReceived("no audio")
        with pytest.raises(RuntimeError, match="edge-tts failed after 2 attempt"):
            synthesize_speech("Xin chào", out)

    assert mock_run.call_count == 2


def test_synthesize_speech_rejects_empty_text(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="empty"):
        synthesize_speech("   ", tmp_path / "narration.mp3")


def test_scene_cache_round_trip(tmp_path: Path) -> None:
    cache_dir = tmp_path / "scene_tts"
    cache_dir.mkdir()
    mp3, words_path, meta_path = _scene_cache_paths(cache_dir, 1)
    mp3.write_bytes(b"mp3")
    word_ts = [{"text": "Hi", "start_ms": 0, "end_ms": 100}]
    _save_scene_cache(words_path, meta_path, word_ts=word_ts, tts_text="Xin chào", voice="vi-VN-HoaiMyNeural")
    loaded = _load_scene_cache(
        mp3, words_path, meta_path, tts_text="Xin chào", voice="vi-VN-HoaiMyNeural"
    )
    assert loaded == word_ts


def test_scene_cache_miss_when_tts_changes(tmp_path: Path) -> None:
    cache_dir = tmp_path / "scene_tts"
    cache_dir.mkdir()
    mp3, words_path, meta_path = _scene_cache_paths(cache_dir, 1)
    mp3.write_bytes(b"mp3")
    _save_scene_cache(
        words_path,
        meta_path,
        word_ts=[{"text": "Hi", "start_ms": 0, "end_ms": 100}],
        tts_text="old",
        voice="vi-VN-HoaiMyNeural",
    )
    assert _load_scene_cache(
        mp3, words_path, meta_path, tts_text="new", voice="vi-VN-HoaiMyNeural"
    ) is None


@patch("core.audio_generator._concat_audio_files")
@patch("core.audio_generator._audio_duration_ms", return_value=1000)
@patch("core.audio_generator.synthesize_speech")
def test_synthesize_scene_speech_reuses_cached_scene(
    mock_synth: MagicMock,
    mock_duration: MagicMock,
    mock_concat: MagicMock,
    tmp_path: Path,
) -> None:
    out = tmp_path / "narration.mp3"
    cache_dir = tmp_path / "scene_tts"
    cache_dir.mkdir()
    mp3, words_path, meta_path = _scene_cache_paths(cache_dir, 1)
    mp3.write_bytes(b"mp3")
    _save_scene_cache(
        words_path,
        meta_path,
        word_ts=[{"text": "Hi", "start_ms": 0, "end_ms": 100}],
        tts_text="cached line",
        voice="vi-VN-HoaiMyNeural",
    )

    scenes = [{"id": 1, "tts": "cached line"}]
    synthesize_scene_speech(scenes, out, voice="vi-VN-HoaiMyNeural")

    mock_synth.assert_not_called()
    mock_duration.assert_called_once_with(mp3)
    mock_concat.assert_called_once_with([mp3], out)
