# 0003. Remotion as render engine and editor

- **Status**: accepted
- **Date**: 2026-07-03
- **Context**: Tier 2 editability ([0002](0002-project-file-editability.md)) requires a review UI with live preview, timeline editing, and export that matches what the user sees. The project is early enough to adopt Remotion as the primary renderer rather than investing further in MoviePy compositing.
- **Decision**:
  1. **Remotion is the main renderer** for preview and export (captions, b-roll images, narration audio). Package lives in `remotion/`; Python bridge in `core/remotion_render_stage.py`.
  2. **Python remains the generation layer** — LLM script/caption styling, TTS, Pexels retrieval, and `project.json` persistence stay in `core/` and `orchestrator_mvp.py`. Remotion consumes normalized project JSON as composition props.
  3. **MoviePy is retained only for audio mix** (`core/acoustic_compositor.py`) until a Remotion or ffmpeg-native mix stage exists. `core/caption_renderer.py` is legacy reference; `caption_render_stage.py` delegates to Remotion.
  4. **Custom editor (later)** — Remotion Player + Timeline; UI reads/writes `project.json`, triggers selective Python regen or Remotion export per [0002 partial re-render table](0002-project-file-editability.md).
  5. **Phased rollout**:
     - Phase A (done): Headless Remotion render from `project.json`.
     - Phase B: Browser Player wired to same props as export.
     - Phase C: Timeline editor + selective regen hooks from UI.
- **Consequences**:
  - React/TypeScript + Node required for video export; `project.json` is the cross-stack contract ([0002](0002-project-file-editability.md)).
  - CI and dev machines need Node 18+, `npm install` in `remotion/`, and ffmpeg.
  - License: Remotion free tier for individuals/small companies; company license if applicable — verify before production.
