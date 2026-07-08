# Current tasks

Living task board for agent and human work. Agents: update this file when starting or finishing tasks.

**Current milestone:** workable batch demo — CSV job queue + daily cron. **Defaults:** slideshow + Remotion. See [roadmap.md](../architecture/roadmap.md).

## In progress

| ID | Task | Owner | Started | Notes |
|----|------|-------|---------|-------|
| — | — | — | — | — |

## Backlog (demo milestone)

| ID | Task | Priority | Notes |
|----|------|----------|-------|
| — | — | — | Demo success criteria verification on a real 3-row CSV |

## Deferred (post-demo)

| ID | Task | Notes |
|----|------|-------|
| T007 | Project schema + partial re-render hooks | Tier 2 edit UI — not needed for CSV batch demo |
| T009 | Remotion Phase B — Player preview | Editor track |
| T010 | Remotion Phase C — Timeline editor + regen UI | Blocked on T009 |
| T003 | Scaffold project structure and CI | GitHub Actions — post-demo |
| — | Optimization + Knowledge systems | See [content-learning-system.md](../domain/content-learning-system.md) |

## Out of scope (removed from Phase 2)

| ID | Task | Notes |
|----|------|-------|
| ~~2.2~~ / T004b | B-roll / Pexels retrieval | Slideshow uses AI slides; not on default path |
| ~~2.6~~ / T006 | TTS reliability | Deferred |

## Blocked

| ID | Task | Blocker |
|----|------|---------|
| — | — | — |

## Done

| ID | Task | Completed | Notes |
|----|------|-----------|-------|
| T025 | Remotion pin for Ubuntu 20.04 | 2026-07-08 | Branch `chore/remotion-ubuntu-2004`: Remotion 4.0.150 + React 18. Docs in `remotion/README.md`. **Human:** verify render on server (`ldd --version` → 2.31, then `npm ci` + full pipeline). |
| T024 | Remove MoviePy dependency | 2026-07-07 | Dropped `moviepy` from requirements; deleted legacy `caption_renderer.py` + `acoustic_compositor.py`. Scene audio concat uses ffmpeg; duration via mutagen. |
| T022 | CapCut-style per-cut transitions | 2026-07-07 | `pullIn`, `teleportShake`, `zoomBlur` in `effects.tsx`; per-slide `transition` in payload/props; rotation in `assign_slide_transitions`. ADR 0006. |
| T021 | Narration-based slide timing + intro/ending bookends | 2026-07-07 | 5 slides (intro + 3 content + ending); visual timing via `core/slide_timing.py`; TTS on content only. ADR 0005. |
| T020 | Ambient fire overlay MVP | 2026-07-07 | Vecteezy sparks WebM in `assets/overlays/fire/`; `AmbientOverlay.tsx`; random overlay via `overlay_picker.py` (like music). ADR 0004. |
| — | Regenerate slide images each pipeline run | 2026-07-06 | `force=True` in slideshow pipeline; random Pollinations seed |
| T018 | End-to-end batch wiring | 2026-07-06 | `run_slideshow_with_render`; batch `execute_job` |
| T017 | Cron / daily batch docs | 2026-07-06 | `docs/batch-demo.md`, `--max-jobs 1` default |
| T016 | CSV batch runner CLI | 2026-07-06 | `batch_runner.py`, lock file, status columns |
| T023 | Fixed orchestrator output folder | 2026-07-07 | All runs → `output/final/`; cleared each run (orchestrator + batch). Export/copy MP4 elsewhere deferred. |
| T019 | Orchestrator + render chain | 2026-07-06 | `render.final_path`, timestamped `output/generations/` (superseded by T023) |
| T015 | Stitch CLI guide + portrait canvas | 2026-07-06 | `docs/stitch-cli.md`, `AGENTS.md` link. `CANVAS_WIDTH`/`CANVAS_HEIGHT` 1080×1920 enforced in `Root.tsx`, `remotion_render_stage.py`, pixel-sized layers in `effects.tsx`. |
| T014 | TikTok-style stitch effects | 2026-07-06 | **Done.** CapCut-style default in `remotion/src/effects.tsx` + `SlideshowBackground`. Ken Burns center zoom (no pan). Unified zoom-out (2 s ease-in → mirror+blur). Fast zoom-in. 3×3 XY mirror grid. Mirror preloads 0.1 s before zoom-out. Optional `--music` via stitch CLI. |
| T013 | Simple asset stitcher | 2026-07-06 | Optional manual path. `stitch.py` + `core/stitch_stage.py`. Per-run folder `output/stitch/<timestamp>/`. |
| T000 | Set up docs/ and agentic workflow | 2026-07-03 | AGENTS.md, docs/, .cursor/rules |
| **MVP** | **MVP orchestrator — script → tokens → TTS → payload** | **2026-07-03** | **Complete.** Entry: `orchestrator_mvp.py`. Outputs: `output/narration.mp3`, `output/pipeline_payload.json`. Vietnamese LLM prompts + `vi-VN-HoaiMyNeural`. Tests: `pytest tests/test_orchestrator_mvp.py`. ADR 0001. |
| T001 | MVP orchestrator (LLM + TTS + payload) | 2026-07-03 | See **MVP** row |
| T002 | Core content models for MVP payload | 2026-07-03 | `topic`, `raw_script`, `tokens`, `audio` in `pipeline_payload.json` |
| T004 | Phase 2.1 — Caption render stage | 2026-07-03 | Remotion via `remotion_render_stage`; `caption_render_stage` delegates |
| T008 | Remotion Phase A — headless render | 2026-07-03 | `remotion/`, `core/remotion_render_stage.py`, ADR 0003 updated |
| T011 | Scene slideshow pipeline | 2026-07-03 | Default `--mode slideshow`. 3-scene script, slide images, per-scene TTS, `caption_mode` toggle. `core/slideshow_pipeline.py`, `core/slide_image_stage.py`, `docs/prompts/` |
| T012 | Per-sentence caption timing | 2026-07-03 | `caption_mode=sentence` splits on `.`/`?`/`!`, times via word timestamps; rebuild on `normalize_project`. `core/caption_tokens.py` |
| T005 | Acoustic mix — random music from library | 2026-07-06 | `core/music_picker.py` picks from `assets/music/` or `music/`; stored in `audio.music`; Remotion mixes via `musicSrc` / `musicVolume`. |
