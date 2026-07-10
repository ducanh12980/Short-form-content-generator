# 0008. Durable per-job asset cache

- **Status**: accepted
- **Date**: 2026-07-10
- **Context**: Operators want CSV jobs to reuse script + slide images when already generated, and otherwise generate once, persist under `assets/jobs/<id>/`, then always continue TTS → Remotion → publish. Requiring a separate pregenerate step blocked first-time runs.
- **Decision**:
  - Store durable assets in `assets/jobs/<id>/` (`scenes_draft.json` + five slide PNGs).
  - Batch slideshow passes `job_assets_id`. Complete cache → reuse; incomplete → LLM/image APIs then `persist_job_assets_from_run_dir`.
  - Pipeline order for generation path: script (+ TTS writer text) → images → persist → spoken TTS → Remotion → publish.
  - Default `require_job_assets=False`. Optional `--require-job-assets` / `require_job_assets=True` keeps the strict library mode. `scripts/pregenerate_job_assets.py` remains for offline freeze.
- **Consequences**:
  - Topic mismatch invalidates reuse.
  - CI still needs committed `assets/jobs/` (or secrets + generate on the runner) because runners are ephemeral.
  - Spoken TTS is not cached in the library (fresh each run).
