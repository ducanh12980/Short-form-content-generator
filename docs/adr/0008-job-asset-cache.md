# 0008. Durable per-job asset cache

- **Status**: accepted
- **Date**: 2026-07-10
- **Context**: CSV batch must follow: read job → if `assets/jobs/<id>/` exists, read `scenes_draft.json` + `images/*.png` → if incomplete, GPT script + GPT images → always save library → TTS → Remotion → Publish. A hard pregenerate-only gate blocked first runs.
- **Decision**:
  - Library path: `assets/jobs/<id>/` (`scenes_draft.json` + five PNGs).
  - Reuse script via `try_load_job_scenes_draft` even when some images are missing.
  - Full reuse only when draft + all images exist; otherwise copy existing PNGs and call image API with `force=False` so **only missing files** are generated.
  - Order: script (reuse or GPT) → fill missing images → save → spoken TTS → Remotion → publish.
  - Default `require_job_assets=False`; `--require-job-assets` for strict mode.
- **Consequences**:
  - Topic mismatch / broken draft / missing PNG → regenerate path.
  - CI needs committed `assets/jobs/` (or generate on the runner) because runners are ephemeral.
  - Spoken TTS is not stored in the library.
