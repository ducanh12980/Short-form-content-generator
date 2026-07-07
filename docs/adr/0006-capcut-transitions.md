# 0006. CapCut-style per-cut slide transitions

- **Status**: accepted
- **Date**: 2026-07-07
- **Context**: The Remotion slideshow used a single implicit `zoomBlur` transition (slow zoom-out + mirror grid) at every cut. Short-form editors like CapCut use varied movement transitions (pull in/out, shake + flash) to keep pacing fresh.
- **Decision**: Add three per-slide outgoing transitions selectable via `slide.transition` / `video.images[].transition`, wired through the payload to Remotion props:
  - `pullIn` — dolly zoom in + blur at impact
  - `teleportShake` — pre-cut shake → white-out flash → post-cut recovery shake to center (50% longer phase timing)
  - `zoomBlur` — existing mirror-grid zoom-out behavior
  Default assignment rotates `pullIn → teleportShake → zoomBlur` when unset.
- **Consequences**: `remotion/src/effects.tsx` branches `computeSlideStyle` on transition type; Python schema assigns and threads `transition` in `build_image_timeline_from_slides` and `project_to_remotion_props`. Tuning constants live in `effects.tsx`; visual polish may need iteration in Remotion Studio.
