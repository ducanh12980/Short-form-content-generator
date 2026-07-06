# 0002. Project file as source of truth (Tier 2 editability)

- **Status**: accepted
- **Date**: 2026-07-03
- **Context**: The product will eventually need a review/edit UI (Tier 2): change specific caption words, swap background music, and change caption font — without re-running the full LLM pipeline. Phase 2 adds video render stages. If we only emit a flat `final.mp4`, those edits require full regeneration or external NLE tools.
- **Decision**:
  1. **`project.json` is the source of truth** for anything the UI may edit. `final.mp4` (and intermediate MP3/clip files) are **derived artifacts** produced by a render pass.
  2. **Evolve `pipeline_payload.json` into `project.json`** starting in Phase 2. Keep backward-compatible fields (`topic`, `raw_script`, `tokens`, `audio`) and add structured timeline sections (see [pipeline-map.md](../../.cursor/skills/explain-pipeline-feature/pipeline-map.md#project-schema-tier-2-editability)).
  3. **Partial re-render stages** — each stage reads only its project section plus on-disk assets:
     | User edit | Re-render stage | LLM / TTS needed? |
     |-----------|-----------------|-------------------|
     | Caption display word | Caption render | No |
     | Caption font / theme / color | Caption render | No |
     | Background music path or volume | Acoustic mix | No |
     | Spoken narration text | TTS → acoustic mix → (caption sync) | TTS only |
     | B-roll clip selection / trim | Video compositor → export | No |
  4. **Caption words are first-class objects** — each token carries `word` (display), optional `spoken_word` (TTS alignment; defaults to `word`), styling, and timing (`start_ms` / `end_ms` or link to `audio.word_timestamps` index). UI text edits update `word` without touching TTS until the user explicitly changes spoken script.
  5. **Music and font live in the project file**, not only in env vars. Env vars (`BACKGROUND_MUSIC_PATH`, etc.) may seed defaults on first generation; persisted values in `project.json` override them on re-render.
  6. **Render modules stay stateless** — `core/*` accept a project section + paths, write outputs, return updated paths. No hidden global config that the UI cannot see or change.
- **Consequences**:
  - Phase 2 orchestrator must write and update `project.json` on every run; render stages read from it.
  - `caption_renderer` must accept per-project `font` override (fallback: theme from `config/theme_styles.json`).
  - `acoustic_compositor` must accept `music.path` and volume from project, not only `BACKGROUND_MUSIC_PATH`.
  - A future UI/API loads `project.json`, mutates editable fields, and calls selective re-render endpoints — no schema redesign required.
  - Slightly larger payload files and explicit schema versioning (`project_version: 1`) — acceptable tradeoff for editability.
