# 0008. Durable per-job asset cache

- **Status**: accepted
- **Date**: 2026-07-10
- **Context**: CSV batch must follow: read job → if `assets/jobs/<id>/` exists, read `scenes_draft.json` + `images/*.png` → if incomplete, GPT script + GPT images → always save library → TTS → Remotion → Publish. A hard pregenerate-only gate blocked first runs.
- **Decision**:
  - Library path: `assets/jobs/<id>/` (`scenes_draft.json` + five PNGs).
  - Always run `inventory_job_assets` first: scan script + **every** required PNG in one pass (even when the first gap is found).
  - Then fill only gaps: reuse valid script; copy present images; `force=False` image generation for missing PNGs only.
  - Order: inventory → fill missing → save → spoken TTS → Remotion → publish.
  - Default `require_job_assets=False`; `--require-job-assets` for strict mode.
- **Consequences**:
  - Topic mismatch / broken draft / missing PNG → regenerate path.
  - CI needs committed `assets/jobs/` (or generate on the runner) because runners are ephemeral.
  - Spoken TTS is not stored in the library.
