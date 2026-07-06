# Current tasks

Living task board for agent and human work. Agents: update this file when starting or finishing tasks.

## In progress

| ID | Task | Owner | Started | Notes |
|----|------|-------|---------|-------|
| — | — | — | — | — |

## Backlog

| ID | Task | Priority | Notes |
|----|------|----------|-------|
| T005 | B-roll + acoustic mix wiring | Medium | Uses existing core modules. **ADR 0002:** music from `audio.music`, not env-only |
| T007 | Project schema + partial re-render hooks | High | Phase 2 foundation — `project.json`, stage entrypoints for UI later |
| T009 | Remotion Phase B — Player preview | Medium | Same composition as export |
| T010 | Remotion Phase C — Timeline editor + regen UI | Medium | Player + Timeline; wires partial regen + export; blocked on T009 |
| T003 | Scaffold project structure and CI | Medium | pytest in place; add GitHub Actions |
| T006 | TTS reliability (retry / line-by-line synth) | Low | Optional hardening for long Vietnamese scripts |

## Blocked

| ID | Task | Blocker |
|----|------|---------|
| — | — | — |

## Done

| ID | Task | Completed | Notes |
|----|------|-----------|-------|
| T013 | Simple asset stitcher | 2026-07-06 | Demo complete. `stitch.py` + `core/stitch_stage.py`. Per-run folder `output/stitch/<timestamp>/`. Effects registry `remotion/src/effects.tsx`. First/last slides get half unit time; content slides share the rest equally. |
| T000 | Set up docs/ and agentic workflow | 2026-07-03 | AGENTS.md, docs/, .cursor/rules |
| **MVP** | **MVP orchestrator — script → tokens → TTS → payload** | **2026-07-03** | **Complete.** Entry: `orchestrator_mvp.py`. Outputs: `output/narration.mp3`, `output/pipeline_payload.json`. Vietnamese LLM prompts + `vi-VN-HoaiMyNeural`. Tests: `pytest tests/test_orchestrator_mvp.py`. ADR 0001. |
| T001 | MVP orchestrator (LLM + TTS + payload) | 2026-07-03 | See **MVP** row |
| T002 | Core content models for MVP payload | 2026-07-03 | `topic`, `raw_script`, `tokens`, `audio` in `pipeline_payload.json` |
| T004 | Phase 2.1 — Caption render stage | 2026-07-03 | Remotion via `remotion_render_stage`; `caption_render_stage` delegates |
| T004b | Phase 2.2 — B-roll retrieval | 2026-07-03 | `broll_retrieval_stage`, `media_retriever` keywords + Pexels → `video.clips[]` |
| T008 | Remotion Phase A — headless render | 2026-07-03 | `remotion/`, `core/remotion_render_stage.py`, ADR 0003 updated |
| T011 | Scene slideshow pipeline | 2026-07-03 | `--mode slideshow`, 3-scene script, DALL-E slides, per-scene TTS, `caption_mode` toggle. `core/slideshow_pipeline.py`, `core/slide_image_stage.py`, `docs/prompts/` |
| T012 | Per-sentence caption timing | 2026-07-03 | `caption_mode=sentence` splits on `.`/`?`/`!`, times via word timestamps; rebuild on `normalize_project`. `core/caption_tokens.py` |
