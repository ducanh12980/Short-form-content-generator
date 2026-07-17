"""Tests for narration-based slide timing helpers."""

from __future__ import annotations

import pytest

from core.slide_timing import apply_narration_slide_timing, compute_slide_durations_ms


def _slides() -> list[dict]:
    return [
        {"id": 1, "role": "intro"},
        {"id": 2, "role": "content"},
        {"id": 3, "role": "content"},
        {"id": 4, "role": "content"},
    ]


def _scene_timestamps() -> list[dict]:
    return [
        {"scene_id": 2, "start_ms": 0, "end_ms": 20_000},
        {"scene_id": 3, "start_ms": 20_000, "end_ms": 40_000},
        {"scene_id": 4, "start_ms": 40_000, "end_ms": 60_000},
    ]


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


def test_content_slides_follow_their_own_narration() -> None:
    slides = _slides()
    apply_narration_slide_timing(slides, _scene_timestamps(), 60_000, intro_hold_ms=2500)

    # Intro holds the first 2.5s, so only scene 1 starts late; the rest are exact.
    assert (slides[0]["start_ms"], slides[0]["end_ms"]) == (0, 2500)
    assert (slides[1]["start_ms"], slides[1]["end_ms"]) == (2500, 20_000)
    assert (slides[2]["start_ms"], slides[2]["end_ms"]) == (20_000, 40_000)
    assert (slides[3]["start_ms"], slides[3]["end_ms"]) == (40_000, 60_000)


def test_slides_run_back_to_back_with_no_gaps() -> None:
    slides = _slides()
    apply_narration_slide_timing(slides, _scene_timestamps(), 60_000, intro_hold_ms=2500)

    for earlier, later in zip(slides, slides[1:]):
        assert earlier["end_ms"] == later["start_ms"]
    assert slides[0]["start_ms"] == 0
    assert slides[-1]["end_ms"] == 60_000


def test_intro_hold_never_eats_more_than_half_the_first_line() -> None:
    slides = _slides()
    timestamps = [
        {"scene_id": 2, "start_ms": 0, "end_ms": 3000},
        {"scene_id": 3, "start_ms": 3000, "end_ms": 40_000},
        {"scene_id": 4, "start_ms": 40_000, "end_ms": 60_000},
    ]
    apply_narration_slide_timing(slides, timestamps, 60_000, intro_hold_ms=30_000)

    assert slides[0]["end_ms"] == 1500
    assert slides[1]["start_ms"] == 1500
    assert slides[1]["end_ms"] == 3000


def test_zero_intro_hold_drops_the_intro_slide_to_nothing() -> None:
    slides = _slides()
    apply_narration_slide_timing(slides, _scene_timestamps(), 60_000, intro_hold_ms=0)

    assert slides[0]["end_ms"] == 0
    assert slides[1]["start_ms"] == 0


def test_intro_hold_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INTRO_HOLD_MS", "4000")
    slides = _slides()
    apply_narration_slide_timing(slides, _scene_timestamps(), 60_000)

    assert slides[0]["end_ms"] == 4000
    assert slides[1]["start_ms"] == 4000


def test_missing_tts_timing_is_an_error() -> None:
    slides = _slides()
    with pytest.raises(ValueError, match="Missing TTS timing"):
        apply_narration_slide_timing(slides, _scene_timestamps()[:2], 60_000)
