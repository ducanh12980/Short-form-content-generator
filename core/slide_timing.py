"""Slide display timing — narration-based opener/closer formula shared with stitch CLI."""

from __future__ import annotations

from typing import Any


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


def apply_slide_timing(slides: list[dict[str, Any]], duration_ms: int) -> None:
    """Mutate slides with start_ms/end_ms from compute_slide_durations_ms."""
    if not slides:
        return
    durations = compute_slide_durations_ms(duration_ms, len(slides))
    cursor_ms = 0
    for slide, duration in zip(slides, durations):
        slide["start_ms"] = cursor_ms
        cursor_ms += duration
        slide["end_ms"] = cursor_ms
