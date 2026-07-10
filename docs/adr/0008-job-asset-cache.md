# 0008. Durable per-job asset cache

- **Status**: accepted
- **Date**: 2026-07-10
- **Context**: CSV batch must follow: read job → if `assets/jobs/<id>/` exists, read `scenes_draft.json` + `images/*.png` → if incomplete, GPT script + GPT images → always save library → TTS → Remotion → Publish. A hard pregenerate-only gate blocked first runs.
- **Decision**:
  - Library path: `assets/jobs/<id>/` (`scenes_draft.json` + five PNGs).
  - Decision helper: `try_load_reusable_job_assets` (exists → read → validate topic/schema/images → reuse or None).
  - Incomplete/missing → LLM script + image APIs → `persist_job_assets_from_run_dir`.
  - Order: script → images → save → spoken TTS → Remotion → publish.
  - Default `require_job_assets=False`; `--require-job-assets` for strict mode. `scripts/pregenerate_job_assets.py` optional offline freeze.
- **Consequences**:
  - Topic mismatch / broken draft / missing PNG → regenerate path.
  - CI needs committed `assets/jobs/` (or generate on the runner) because runners are ephemeral.
  - Spoken TTS is not stored in the library.
