"""Vocal Engine — converts narration text to MP3 via edge-tts and returns per-word millisecond timestamps for caption sync."""

from __future__ import annotations

import asyncio
import inspect
import tempfile
from pathlib import Path
from typing import Any

import edge_tts
from moviepy import AudioFileClip, concatenate_audioclips

from core.pipeline_log import log_step_done


def _create_communicate(text: str, voice: str) -> edge_tts.Communicate:
    """Create an edge-tts session with word-boundary events when supported.

    Goal: Enable per-word timestamp collection during TTS streaming.
    Params: text — narration script; voice — edge-tts neural voice name.
    Output: edge_tts.Communicate instance configured for synthesis.
    """
    params = inspect.signature(edge_tts.Communicate.__init__).parameters
    if "boundary" in params:
        return edge_tts.Communicate(text, voice, boundary="WordBoundary")
    return edge_tts.Communicate(text, voice)


def _word_boundary_to_ms(offset: int, duration: int) -> tuple[int, int]:
    """Convert edge-tts 100-nanosecond ticks to millisecond start/end.

    Goal: Normalize TTS boundary events for caption_renderer timing.
    Params: offset — word start offset in 100-ns units; duration — word length in 100-ns units.
    Output: (start_ms, end_ms) integer tuple.
    """
    start_ms = int(offset / 10_000)
    end_ms = start_ms + int(duration / 10_000)
    return start_ms, end_ms


async def _synthesize_async(
    text: str,
    output_path: Path,
    *,
    voice: str = "en-US-AriaNeural",
) -> list[dict[str, Any]]:
    """Stream TTS to disk and collect WordBoundary timestamps asynchronously.

    Goal: Write MP3 and build word-level timing data in one pass.
    Params: text — narration script; output_path — destination MP3 path; voice — edge-tts voice.
    Output: List of {text, start_ms, end_ms} dicts in spoken order.
    """
    communicate = _create_communicate(text, voice)
    word_timestamps: list[dict[str, Any]] = []

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as audio_file:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_file.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start_ms, end_ms = _word_boundary_to_ms(chunk["offset"], chunk["duration"])
                word_timestamps.append(
                    {
                        "text": chunk["text"],
                        "start_ms": start_ms,
                        "end_ms": end_ms,
                    }
                )

    return word_timestamps


def synthesize_speech(
    text: str,
    output_path: str | Path,
    *,
    voice: str = "en-US-AriaNeural",
) -> list[dict[str, Any]]:
    """Synchronous wrapper: write narration MP3 and return word timestamps.

    Goal: Callable TTS entry point for the orchestrator without async boilerplate.
    Params: text — narration script; output_path — MP3 file path; voice — edge-tts voice name.
    Output: List of {text, start_ms, end_ms} dicts from WordBoundary events.
    """
    return asyncio.run(_synthesize_async(text, Path(output_path), voice=voice))


def _offset_word_timestamps(
    word_timestamps: list[dict[str, Any]],
    offset_ms: int,
) -> list[dict[str, Any]]:
    """Shift word boundary times by a cumulative scene offset."""
    return [
        {
            "text": entry["text"],
            "start_ms": int(entry["start_ms"]) + offset_ms,
            "end_ms": int(entry["end_ms"]) + offset_ms,
        }
        for entry in word_timestamps
    ]


def synthesize_scene_speech(
    scenes: list[dict[str, Any]],
    output_path: str | Path,
    *,
    voice: str = "en-US-AriaNeural",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[int, list[dict[str, Any]]]]:
    """Synthesize each scene's tts, concatenate audio, return scene and word timestamps.

    Params: scenes — list of dicts with 'tts' text; output_path — final MP3 path; voice — edge-tts voice.
    Output: (scene_timestamps, merged_word_timestamps, words_by_scene) where:
        scene_timestamps — [{scene_id, start_ms, end_ms}] in scene order;
        merged_word_timestamps — flat [{text, start_ms, end_ms}] across all scenes;
        words_by_scene — {scene_id: [{text, start_ms, end_ms}]} pre-grouped for direct lookup.
    """
    if not scenes:
        raise ValueError("scenes must not be empty.")

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    scene_timestamps: list[dict[str, Any]] = []
    merged_words: list[dict[str, Any]] = []
    words_by_scene: dict[int, list[dict[str, Any]]] = {}
    temp_paths: list[Path] = []
    cursor_ms = 0
    total = len(scenes)
    step = "per-scene TTS + concat"

    try:
        with tempfile.TemporaryDirectory(prefix="scene_tts_") as tmp_dir:
            tmp = Path(tmp_dir)
            for index, scene in enumerate(scenes):
                tts_text = str(scene.get("tts", "")).strip()
                if not tts_text:
                    raise ValueError(f"Scene {index + 1} has empty tts text.")

                scene_path = tmp / f"scene_{index + 1}.mp3"
                word_ts = synthesize_speech(tts_text, scene_path, voice=voice)
                if not word_ts:
                    raise ValueError(f"TTS produced no word boundaries for scene {index + 1}.")

                clip = AudioFileClip(str(scene_path))
                duration_ms = int(clip.duration * 1000)
                clip.close()

                scene_id = int(scene.get("id", index + 1))
                start_ms = cursor_ms
                end_ms = cursor_ms + duration_ms
                offset_words = _offset_word_timestamps(word_ts, start_ms)

                scene_timestamps.append(
                    {"scene_id": scene_id, "start_ms": start_ms, "end_ms": end_ms}
                )
                merged_words.extend(offset_words)
                words_by_scene[scene_id] = offset_words
                temp_paths.append(scene_path)
                cursor_ms = end_ms
                log_step_done(
                    step,
                    f"scene {scene_id}/{total} ({start_ms}–{end_ms} ms)",
                )

            clips = [AudioFileClip(str(path)) for path in temp_paths]
            try:
                combined = concatenate_audioclips(clips)
                combined.write_audiofile(str(out), logger=None)
                combined.close()
            finally:
                for clip in clips:
                    clip.close()

    except OSError as exc:
        raise RuntimeError(f"Failed to concatenate scene audio: {exc}") from exc

    log_step_done(step, f"complete → {out.resolve()}")

    return scene_timestamps, merged_words, words_by_scene
