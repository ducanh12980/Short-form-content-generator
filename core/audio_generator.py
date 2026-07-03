"""Vocal Engine — edge-tts synthesis with word-level millisecond timestamps."""

from __future__ import annotations

import asyncio
import inspect
from pathlib import Path
from typing import Any

import edge_tts


def _create_communicate(text: str, voice: str) -> edge_tts.Communicate:
    """Create an edge-tts ``Communicate`` session; request word boundaries when the library supports it."""
    params = inspect.signature(edge_tts.Communicate.__init__).parameters
    if "boundary" in params:
        return edge_tts.Communicate(text, voice, boundary="WordBoundary")
    return edge_tts.Communicate(text, voice)


def _word_boundary_to_ms(offset: int, duration: int) -> tuple[int, int]:
    """Convert edge-tts timing (100-nanosecond ticks) to ``(start_ms, end_ms)`` for one word."""
    start_ms = int(offset / 10_000)
    end_ms = start_ms + int(duration / 10_000)
    return start_ms, end_ms


async def _synthesize_async(
    text: str,
    output_path: Path,
    *,
    voice: str = "en-US-AriaNeural",
) -> list[dict[str, Any]]:
    """Stream TTS audio to ``output_path`` and collect ``WordBoundary`` events as timestamp dicts."""
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
    """Synchronous wrapper: write narration MP3 to ``output_path`` and return word-level timestamps."""
    return asyncio.run(_synthesize_async(text, Path(output_path), voice=voice))
