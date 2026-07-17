# ADR 0009: Retire the ending slide; time content slides from narration

- **Status**: accepted
- **Date**: 2026-07-17
- **Context**: Every video closed with two ending beats in a row. The LLM-written `ending` slide (title + hero visual, no narration) played, then the fixed brand end card from `assets/endcard/` played on top of it. The end card already carries the closing message and CTA, so the ending slide repeated that beat and cost one generated image per job.

  Removing it exposed a latent bug in the timing formula. ADR 0005 split total narration across **all** slides, including the intro — which has no narration. The intro therefore consumed screen time that belonged to scene 1, pushing every content slide late. With two bookends the drift oscillated (+7.5s / +2.5s / −2.5s on a 60s narration) and roughly cancelled out. With only the intro left, it became a uniform +10s lag: scene 3's image appeared at 50s while its line had been spoken since 40s.
- **Decision**:
  - The script writer produces **1 intro + 3 content slides** (`TOTAL_SLIDE_COUNT = CONTENT_SCENE_COUNT + 1`). No `ending` object is requested or parsed.
  - The brand end card stays the only closer, appended by `core/endcard.py` after narration.
  - `role: "ending"` stays in `VALID_SLIDE_ROLES`, and `core/project_schema.drop_ending_slides()` strips ending slides when loading a draft. Drafts frozen before this change (`assets/jobs/1..20/`) still load and render, minus the ending beat.
  - `ending.png` left `assets/jobs/<id>/images/` and is no longer a required image, so cached jobs stay complete and are never regenerated. The orphaned PNGs stay on disk.
  - Slide timing moved from the even split to `apply_narration_slide_timing`: each content slide takes its window from `audio.scene_timestamps`, so image and voice stay in sync. The intro holds `INTRO_HOLD_MS` (default 2500) over the opening of scene 1, capped at half that line so the slide it borrows from still reads. Slides run back to back; the last ends at the narration end, where the end card begins.
  - `compute_slide_durations_ms` (the ADR 0005 even split) stays for the **stitch CLI**, where images have no narration of their own to follow.
- **Consequences**:
  - **Positive:** One less generated image per job; no duplicated closing beat.
  - **Positive:** The 20 pregenerated jobs kept their cached scripts and images — no LLM or image spend to adopt this.
  - **Positive:** Content images now land on their own lines (scenes 2–3 exact; scene 1 late by the intro hold alone, which is deliberate).
  - **Negative:** Pacing changes noticeably. The intro drops from ~`duration/6` to 2.5s, and videos run shorter by the ending slide's old screen time. Tune with `INTRO_HOLD_MS`.
  - **Negative:** `assets/jobs/*/images/ending.png` are orphaned until someone prunes them; `docs/prompts/bookend-slide-image.md` still documents an `ending` role that only `intro` now reaches.
  - **Supersedes:** the `intro | content | ending` slide roles **and** the all-slides even split in [ADR 0005](0005-slide-timing-narration-based.md), for the slideshow pipeline.

## References

- [ADR 0005](0005-slide-timing-narration-based.md) — narration-based slide timing
- [ADR 0008](0008-job-asset-cache.md) — durable per-job asset cache
- [core/endcard.py](../../core/endcard.py)
- [docs/prompts/slide-script-writer.md](../prompts/slide-script-writer.md)
