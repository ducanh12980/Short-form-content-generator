# 0006. CapCut-style per-cut slide transitions

- **Status**: accepted
- **Date**: 2026-07-07
- **Context**: The Remotion slideshow used a single implicit `zoomBlur` transition (slow zoom-out + mirror grid) at every cut. Short-form editors like CapCut use varied movement transitions (pull in/out, shake + flash, whip pan) to keep pacing fresh.
- **Decision**: Add per-slide outgoing transitions selectable via `slide.transition` / `video.images[].transition`, wired through the payload to Remotion props:
  - `pullIn` — dolly zoom in + blur at impact
  - `teleportShake` — pre-cut shake → white-out flash → post-cut recovery shake to center (shake phases +30% longer, stronger amplitude)
  - `whipPan` — pre-cut shake → ease-in-out horizontal whip (alternating L/R) → post-cut shake (no flash)
  - `zoomBlur` — existing mirror-grid zoom-out behavior
  Default assignment rotates `pullIn → teleportShake → whipPan → zoomBlur` when unset.
- **Consequences**: `remotion/src/effects.tsx` branches `computeSlideStyle` on transition type; Python schema assigns and threads `transition` in `build_image_timeline_from_slides` and `project_to_remotion_props`. Tuning constants live in `effects.tsx`; visual polish may need iteration in Remotion Studio.
