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
| T039 | Batch: reset run dir + stop on Gemini quota | 2026-07-10 | Each job clears `output/final`; stop remaining pending rows when API quota exhausted. |
| T038 | Full inventory then fill gaps only | 2026-07-10 | `inventory_job_assets` soát hết script+từng PNG trước; chỉ GPT phần còn thiếu. |
| T037 | Partial image fill for job assets | 2026-07-10 | Script OK + thiếu ảnh → giữ PNG có sẵn, `force=False` chỉ generate phần còn thiếu. |
| T035 | Job asset cache auto generate+persist | 2026-07-10 | Flow: tồn tại → đọc draft+images → đủ thì reuse / không đủ thì GPT script+ảnh → lưu → TTS → Remotion → Publish. `try_load_reusable_job_assets`. ADR 0008. |
| — | Dual cron: due-today + retry-failed | 2026-07-10 | `--select due-today\|failed`, `--max-jobs 0`, per-job `--publish`; GHA crons 00:00 + 06:00 VN. |
| — | Shift daily-batch cron to 00:00 VN | 2026-07-10 | `cron: "0 17 * * *"` (17:00 UTC = 00:00 UTC+7); docs updated. |
| T036 | Fix duplicate Drive uploads in GitHub Actions | 2026-07-09 | Batch jobs now render with `publish=False`; GitHub workflow remains the single publish step, preventing duplicate Drive uploads. |
| T034 | Teleport shake tuning + whipPan transition | 2026-07-09 | Stronger/longer shake (+30% frames, 3.75 amplitude); new `whipPan` with ease-in-out pan + shake bookends; 4-item rotation. ADR 0006 updated. |
| T033 | GHA ChatGPT image quality/size | 2026-07-09 | `daily-batch.yml`: `IMAGE_PROVIDER=chatgpt`, `OPENAI_IMAGE_SIZE=896x1600`, `OPENAI_IMAGE_QUALITY=low`; pending `jobs.csv` rows → `chatgpt`; docs updated. **Human:** add `OPENAI_IMAGE_API_KEY` secret, push, run workflow. |
| T032 | ChatGPT image cost controls | 2026-07-08 | `OPENAI_IMAGE_QUALITY`, `OPENAI_IMAGE_PROMPT_MODE=compact\|full`, cache-friendly prompts, cached token logging. |
| T031 | Replace Gemini image provider with ChatGPT | 2026-07-08 | `chatgpt` provider, `OPENAI_IMAGE_*` env; model `gpt-image-2`. Text LLM stays on Gemini. |
| T030 | Multi-platform publish (Facebook Reels) | 2026-07-08 | `core/publish/`, `publish_runner.py`, `PUBLISH_PLATFORMS` env; ADR 0007. **Human:** Meta app + Page token secrets. |
| T029 | Preserve output/final on default orchestrator run | 2026-07-08 | `prepare_default_run_dir` keeps `scenes_draft.json` + `scene_tts/`; `--fresh` wipes. |
| T028 | Publish metadata via scene script writer | 2026-07-08 | `publish` block in LLM #1 + `pipeline_payload.json`; Telegram caption from payload. |
| T027 | Telegram delivery (Phase 2) | 2026-07-08 | `core/telegram_notify.py`, workflow step, tests. **Human:** add `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` secrets. |
| T026 | GitHub Actions daily batch | 2026-07-08 | `.github/workflows/daily-batch.yml`, tracked `jobs.csv`, docs in `batch-demo.md` + `AGENTS.md`. **Human:** add repo secrets, enable workflow write perms, run `workflow_dispatch` once on `main`. |
| T003 | CI — pytest on GitHub Actions | 2026-07-08 | Partial (was post-demo). `.github/workflows/ci.yml` on `pull_request` + `push` to `main`. No Remotion render in CI. |
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
