"""Slide display timing — content slides follow narration; stitch CLI splits evenly."""

from __future__ import annotations

import os
from typing import Any

DEFAULT_INTRO_HOLD_MS = 2500


def compute_slide_durations_ms(duration_ms: int | float, slide_count: int) -> list[int]:
    """Return per-slide durations in ms using the opener/closer formula.

    First and last slides get half the screen time of a content slide so the
    opener/closer don't dominate. For N slides the unit is duration/(N-1),
    giving: first=unit/2, middle×(N-2)=unit each, last=unit/2.
    Total = unit/2 + (N-2)*unit + unit/2 = (N-1)*unit = duration.
    For N==1 the single slide fills the whole duration.
    """
    if slide_count <= 0:
        raise ValueError("slide_count must be at least 1.")
    total = float(duration_ms)
    if slide_count == 1:
        return [int(round(total))]

    unit = total / (slide_count - 1)
    durations = [unit / 2] + [unit] * (slide_count - 2) + [unit / 2]
    rounded = [int(round(value)) for value in durations]
    # Absorb rounding drift on the last slide so the sum matches duration_ms.
    drift = int(round(total)) - sum(rounded)
    rounded[-1] += drift
    return rounded


def resolve_intro_hold_ms(explicit: int | None = None) -> int:
    """Return intro screen time in ms from explicit arg, INTRO_HOLD_MS env, or default."""
    if explicit is not None:
        return max(0, int(explicit))

    raw = os.environ.get("INTRO_HOLD_MS", "").strip()
    if not raw:
        return DEFAULT_INTRO_HOLD_MS
    try:
        value = int(float(raw))
    except ValueError:
        return DEFAULT_INTRO_HOLD_MS
    return value if value >= 0 else DEFAULT_INTRO_HOLD_MS


def apply_narration_slide_timing(
    slides: list[dict[str, Any]],
    scene_timestamps: list[dict[str, Any]],
    duration_ms: int,
    *,
    intro_hold_ms: int | None = None,
) -> None:
    """Mutate slides so each content slide is on screen while its own line is spoken.

    Content windows come from the TTS scene timestamps, so image and voice stay in
    sync. The intro has no narration, so it holds the opening moments over the start
    of the first line — capped at half that line so the slide it steals from still
    reads. Slides run back to back: each ends where the next begins, the last at
    duration_ms, leaving no gap for the end card to butt against.
    """
    if not slides:
        return

    content_slides = [slide for slide in slides if slide.get("role") == "content"]
    by_id = {int(entry["scene_id"]): entry for entry in scene_timestamps}
    starts_by_slide: dict[int, int] = {}
    for slide in content_slides:
        timing = by_id.get(int(slide["id"]))
        if timing is None:
            raise ValueError(f"Missing TTS timing for content slide {slide['id']}.")
        starts_by_slide[int(slide["id"])] = int(timing["start_ms"])

    intro_slides = [slide for slide in slides if slide.get("role") == "intro"]
    cursor_ms = 0
    if intro_slides and content_slides:
        first_id = int(content_slides[0]["id"])
        first_start = starts_by_slide[first_id]
        first_end = int(by_id[first_id]["end_ms"])
        budget = max(0, (first_end - first_start) // 2)
        hold = min(resolve_intro_hold_ms(intro_hold_ms), budget)
        for slide in intro_slides:
            slide["start_ms"] = first_start
            slide["end_ms"] = first_start + hold
        cursor_ms = first_start + hold

    for index, slide in enumerate(content_slides):
        slide["start_ms"] = max(starts_by_slide[int(slide["id"])], cursor_ms)
        is_last = index == len(content_slides) - 1
        next_start = (
            int(duration_ms) if is_last else starts_by_slide[int(content_slides[index + 1]["id"])]
        )
        slide["end_ms"] = max(next_start, slide["start_ms"])
        cursor_ms = slide["end_ms"]
