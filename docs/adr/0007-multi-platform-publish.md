# 0007. Multi-platform publish adapters

- **Status**: accepted
- **Date**: 2026-07-08
- **Context**: The batch demo delivers rendered MP4s via Telegram only. Operators need to publish to native platforms (starting with Facebook Page Reels) and toggle targets without code changes. Each platform has different APIs, caption formats, and credential requirements.

- **Decision**:
  - Add a `core/publish/` subpackage with shared helpers (`common.py`) and per-platform adapters (`facebook.py`, `telegram.py`).
  - Use `PUBLISH_PLATFORMS` (comma-separated env var) as the master toggle; e.g. `facebook,telegram`.
  - Expose a unified CLI at `core/publish_runner.py`, invoked after render (manual or in `daily-batch.yml`). `batch_runner` stays render-only.
  - Each adapter: `load_config_from_env() -> Config | None`, `deliver_video(...) -> dict | None` (None = skipped).
  - Facebook v1 targets **Page Reels** via Meta Graph API (start → rupload binary → finish with `video_state=PUBLISHED`). Credentials: `FACEBOOK_PAGE_ID` + `FACEBOOK_ACCESS_TOKEN` (Page token).
  - Keep `core/telegram_notify.py` as a backward-compatible CLI wrapper around `core/publish/telegram.py`.
  - Caption source: `--caption` override → `pipeline_payload.json` `publish` block → `jobs.csv` fallback (shared resolution in `common.py`; platform-specific formatting in each adapter).
  - No OAuth flow in v1 — operators supply tokens via env / GitHub secrets (same pattern as Telegram bot token).

- **Consequences**:
  - Adding a platform = new `core/publish/{name}.py` + registry entry + env vars in `.env.example`.
  - Telegram remains useful for failure alerts and manual handoff even when native publish is enabled.
  - Facebook Reels: 9:16 and ≤90s validated before upload; Meta rate limit (~30 Reels/Page/24h) surfaced in errors.
  - Deferred: OAuth token refresh, per-platform publish metadata variants, `jobs.csv` publish status columns, draft/scheduled posts.
