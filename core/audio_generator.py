"""Vocal Engine — converts narration text to MP3 via edge-tts and returns per-word millisecond timestamps for caption sync."""

from __future__ import annotations

import asyncio
import inspect
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

import edge_tts
from edge_tts.exceptions import EdgeTTSException

from core.pipeline_log import log_step_done

TTS_RETRY_ATTEMPTS = int(os.environ.get("TTS_RETRY_ATTEMPTS", "5"))
TTS_RETRY_DELAY_SECONDS = float(os.environ.get("TTS_RETRY_DELAY_SECONDS", "5"))
SCENE_TTS_CACHE_DIR = "scene_tts"


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
    script = text.strip()
    if not script:
        raise ValueError("TTS text must not be empty.")

    out = Path(output_path)
    last_exc: EdgeTTSException | None = None

    for attempt in range(1, TTS_RETRY_ATTEMPTS + 1):
        try:
            return asyncio.run(_synthesize_async(script, out, voice=voice))
        except EdgeTTSException as exc:
            last_exc = exc
            out.unlink(missing_ok=True)
            if attempt >= TTS_RETRY_ATTEMPTS:
                break
            time.sleep(TTS_RETRY_DELAY_SECONDS * attempt)

    assert last_exc is not None
    raise RuntimeError(
        f"edge-tts failed after {TTS_RETRY_ATTEMPTS} attempt(s) "
        f"(voice={voice!r}, chars={len(script)}): {last_exc}"
    ) from last_exc


def _scene_cache_paths(cache_dir: Path, scene_id: int) -> tuple[Path, Path, Path]:
    """Return (mp3, words.json, meta.json) paths for a cached scene TTS."""
    prefix = f"scene_{scene_id}"
    return (
        cache_dir / f"{prefix}.mp3",
        cache_dir / f"{prefix}.words.json",
        cache_dir / f"{prefix}.meta.json",
    )


def _load_scene_cache(
    mp3_path: Path,
    words_path: Path,
    meta_path: Path,
    *,
    tts_text: str,
    voice: str,
) -> list[dict[str, Any]] | None:
    """Load cached word timestamps when mp3 + metadata match the current script."""
    if not mp3_path.is_file() or mp3_path.stat().st_size == 0:
        return None
    if not words_path.is_file() or not meta_path.is_file():
        return None
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        words = json.loads(words_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if meta.get("tts") != tts_text or meta.get("voice") != voice:
        return None
    if not isinstance(words, list) or not words:
        return None
    return words


def _save_scene_cache(
    words_path: Path,
    meta_path: Path,
    *,
    word_ts: list[dict[str, Any]],
    tts_text: str,
    voice: str,
) -> None:
    """Persist word timestamps and script metadata beside the scene mp3."""
    words_path.write_text(json.dumps(word_ts, ensure_ascii=False), encoding="utf-8")
    meta_path.write_text(
        json.dumps({"tts": tts_text, "voice": voice}, ensure_ascii=False),
        encoding="utf-8",
    )


def _audio_duration_ms(audio_path: Path) -> int:
    try:
        from mutagen import File as MutagenFile
    except ImportError as exc:
        raise RuntimeError(
            "mutagen is required. Install it with: pip install mutagen"
        ) from exc

    audio = MutagenFile(str(audio_path))
    if audio is None or audio.info is None:
        raise ValueError(f"Could not read audio metadata from: {audio_path}")
    return int(audio.info.length * 1000)


def _concat_audio_files(scene_paths: list[Path], output_path: Path) -> None:
    """Concatenate scene MP3s into one narration track via ffmpeg."""
    if len(scene_paths) == 1:
        shutil.copy2(scene_paths[0], output_path)
        return

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".txt",
        delete=False,
        dir=output_path.parent,
    ) as handle:
        for path in scene_paths:
            escaped = str(path.resolve()).replace("'", "'\\''")
            handle.write(f"file '{escaped}'\n")
        list_path = handle.name

    try:
        proc = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                list_path,
                "-c",
                "copy",
                str(output_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            stderr = (proc.stderr or "").strip() or "unknown error"
            raise RuntimeError(f"ffmpeg audio concat failed: {stderr}")
    finally:
        Path(list_path).unlink(missing_ok=True)


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
    cache_dir = out.parent / SCENE_TTS_CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)

    scene_timestamps: list[dict[str, Any]] = []
    merged_words: list[dict[str, Any]] = []
    words_by_scene: dict[int, list[dict[str, Any]]] = {}
    scene_paths: list[Path] = []
    cursor_ms = 0
    total = len(scenes)
    step = "per-scene TTS + concat"
    completed_scene_ids: list[int] = []

    try:
        for index, scene in enumerate(scenes):
            tts_text = str(scene.get("tts", "")).strip()
            if not tts_text:
                raise ValueError(f"Scene {index + 1} has empty tts text.")

            scene_id = int(scene.get("id", index + 1))
            mp3_path, words_path, meta_path = _scene_cache_paths(cache_dir, scene_id)
            word_ts = _load_scene_cache(
                mp3_path, words_path, meta_path, tts_text=tts_text, voice=voice
            )

            if word_ts is None:
                try:
                    word_ts = synthesize_speech(tts_text, mp3_path, voice=voice)
                except RuntimeError as exc:
                    saved = len(completed_scene_ids)
                    hint = (
                        f" Re-run the same pipeline command to resume from "
                        f"{cache_dir} ({saved}/{total} scene(s) already saved)."
                        if saved
                        else ""
                    )
                    raise RuntimeError(f"TTS failed on scene {scene_id}/{total}.{hint} {exc}") from exc
                if not word_ts:
                    raise ValueError(f"TTS produced no word boundaries for scene {scene_id}.")
                _save_scene_cache(
                    words_path,
                    meta_path,
                    word_ts=word_ts,
                    tts_text=tts_text,
                    voice=voice,
                )
                log_step_done(step, f"scene {scene_id}/{total} synthesized")
            else:
                log_step_done(step, f"scene {scene_id}/{total} reused cache")

            duration_ms = _audio_duration_ms(mp3_path)
            start_ms = cursor_ms
            end_ms = cursor_ms + duration_ms
            offset_words = _offset_word_timestamps(word_ts, start_ms)

            scene_timestamps.append(
                {"scene_id": scene_id, "start_ms": start_ms, "end_ms": end_ms}
            )
            merged_words.extend(offset_words)
            words_by_scene[scene_id] = offset_words
            scene_paths.append(mp3_path)
            cursor_ms = end_ms
            completed_scene_ids.append(scene_id)
            log_step_done(
                step,
                f"scene {scene_id}/{total} ({start_ms}–{end_ms} ms)",
            )

        _concat_audio_files(scene_paths, out)

    except OSError as exc:
        raise RuntimeError(f"Failed to concatenate scene audio: {exc}") from exc

    log_step_done(step, f"complete → {out.resolve()}")

    return scene_timestamps, merged_words, words_by_scene
