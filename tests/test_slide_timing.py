"""Tests for narration-based slide timing helpers."""

from __future__ import annotations

import pytest

from core.slide_timing import apply_slide_timing, compute_slide_durations_ms


def test_compute_slide_durations_single_slide() -> None:
    assert compute_slide_durations_ms(5000, 1) == [5000]


def test_compute_slide_durations_five_slides_even_split() -> None:
    assert compute_slide_durations_ms(40_000, 5) == [5000, 10_000, 10_000, 10_000, 5000]


def test_compute_slide_durations_three_slides() -> None:
    assert compute_slide_durations_ms(20_000, 3) == [5000, 10_000, 5000]


def test_compute_slide_durations_sum_matches_total() -> None:
    durations = compute_slide_durations_ms(33_333, 5)
    assert sum(durations) == 33_333


def test_compute_slide_durations_rejects_zero_count() -> None:
    with pytest.raises(ValueError, match="slide_count"):
        compute_slide_durations_ms(1000, 0)


def test_apply_slide_timing_mutates_slides() -> None:
    slides = [
        {"id": 1, "role": "intro"},
        {"id": 2, "role": "content"},
        {"id": 3, "role": "content"},
        {"id": 4, "role": "content"},
        {"id": 5, "role": "ending"},
    ]
    apply_slide_timing(slides, 40_000)
    assert slides[0]["start_ms"] == 0
    assert slides[0]["end_ms"] == 5000
    assert slides[1]["start_ms"] == 5000
    assert slides[1]["end_ms"] == 15_000
    assert slides[-1]["end_ms"] == 40_000
