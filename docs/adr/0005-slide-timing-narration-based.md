# ADR 0005: Narration-based slide timing with intro/ending bookends

- **Status**: superseded for the slideshow pipeline by [ADR 0009](0009-retire-ending-slide.md) — no ending slide, and content slides now follow their TTS windows instead of the even split. The formula below still drives the stitch CLI.
- **Date**: 2026-07-07
- **Context**: Slideshow slide duration was tied 1:1 to per-scene TTS MP3 length, so uneven narration made some slides dominate. We also needed visual-only intro/ending bookends without spoken TTS.
- **Decision**:
  - Slideshow payloads use `slides[]` with `role`: `intro` | `content` | `ending` (5 slides for 3 content scenes today).
  - Intro and ending are visual-only; TTS runs on content slides only.
  - Total narration duration is split across all slides using the opener/closer formula shared with stitch CLI (`core/slide_timing.py`): first/last = `unit/2`, middle = `unit`, where `unit = duration / (N - 1)`.
  - `audio.scene_timestamps` keeps TTS truth for captions; `slides[].start_ms/end_ms` are display windows for Remotion.
- **Consequences**:
  - **Positive:** Predictable visual pacing; intro/ending don't steal time from content narration.
  - **Positive:** Same timing helper for stitch CLI and slideshow pipeline.
  - **Negative:** Slide cuts may not align with per-scene TTS boundaries; captions follow speech, not slide transitions.
  - **Follow-up:** Configurable content scene count; role-specific image prompts for intro/ending.

## References

- [docs/stitch-cli.md](../stitch-cli.md)
- [core/slide_timing.py](../../core/slide_timing.py)
