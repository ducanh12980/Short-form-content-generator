# CSV batch demo — one video per day

Run the slideshow pipeline on **pending CSV rows** (by date or retry). Schedule with cron / Task Scheduler / GitHub Actions for daily production.

## Quick start

```bash
# Create jobs.csv with example rows
python batch_runner.py --init

# Optional: pre-freeze script + images into assets/jobs/<id>/ (or let daily CI fill them)
python scripts/pregenerate_job_assets.py --csv jobs.csv

# Fill only today + future pending jobs (same as GitHub Actions asset step)
python scripts/pregenerate_job_assets.py --csv jobs.csv --from-today

# Daily: reuse assets when present; otherwise generate + persist, then TTS + Remotion + publish
python batch_runner.py --csv jobs.csv --select due-today --max-jobs 0 --publish

# Preview queue without running
python batch_runner.py --csv jobs.csv --dry-run
```

### Job asset library (`assets/jobs/<id>/`)

```
CSV
 │
 ▼
Đọc job
 │
 ▼
assets/jobs/<id> tồn tại?
 │
 ▼
Soát HẾT (inventory): script + từng PNG
 │
 ├─ Đủ hết ─────────────────────────┐
 │                                  │
 ├─ Thiếu bất kỳ phần nào ──────────┤
 │     → liệt kê toàn bộ phần thiếu │
 │     → GPT chỉ tạo phần còn thiếu │
 │       (giữ phần đã có)           │
 │                                  │
                ▼                   │
      Lưu assets/jobs/<id>/ ◄───────┘
                ▼
              TTS
                ▼
           Remotion
                ▼
            Publish
```

Khi phát hiện thiếu 1 phần, vẫn **soát hết** các phần còn lại rồi mới generate — không dừng ở phần đầu tiên thiếu, và không render lại phần đã có.

Layout:

```
assets/jobs/<id>/
  scenes_draft.json    # frozen LLM script + TTS text + publish metadata
  images/
    intro.png
    scene_1.png
    scene_2.png
    scene_3.png
    ending.png
```

```bash
# Optional: freeze all rows ahead of cron
python scripts/pregenerate_job_assets.py --csv jobs.csv

# Same as GitHub Actions asset step: today + future pending only
python scripts/pregenerate_job_assets.py --csv jobs.csv --from-today

# One job / regenerate
python scripts/pregenerate_job_assets.py --csv jobs.csv --job-id 1 --force
```

GitHub Actions runs `--from-today` every day before the video batch, then commits `assets/jobs/`. Later days skip complete libraries and only generate missing parts. The video step still fill-gaps for the due job if needed.

Each successful job writes artifacts under `output/final/` (the folder is cleared before each run):

```
output/final/
├── final.mp4
├── pipeline_payload.json
├── narration.mp3
├── images/
│   ├── intro.png
│   ├── scene_1.png
│   ├── scene_2.png
│   ├── scene_3.png
│   └── ending.png
└── <music>.mp3          # if a track was picked
```

The CSV row is updated: `status=done`, `output_path=<path to final.mp4>`. Copy `final.mp4` elsewhere if you need to keep it before the next job runs.

## CSV columns

| Column | Required | Description |
|--------|----------|-------------|
| `id` | yes | Stable job id (tracked in CSV; artifacts go to `output/final/`) |
| `topic` | yes | Passed to the slideshow script writer |
| `status` | yes | `pending` \| `running` \| `done` \| `failed` |
| `mode` | no | `slideshow` (default) or `mvp` |
| `image_provider` | no | `pollinations` \| `chatgpt` \| `mock` |
| `output_path` | no | Filled on success |
| `error` | no | Filled on failure |
| `created_at` | no | ISO timestamp; for GitHub **due-today** mode, the **calendar date in Asia/Ho_Chi_Minh** must match today |
| `completed_at` | no | ISO timestamp |
| `publish_status` | no | `ok` \| `failed:<platforms>` — set after a publish attempt |

Add many `pending` rows to the CSV. Set each row’s `created_at` to the Vietnam calendar day you want it to run. GitHub **00:00 VN** uses `--select due-today --max-jobs 0` (all matching rows that day). **06:00 VN** retries every `failed` row. Local default remains `--select pending --max-jobs 1` (next pending only).

A render that succeeds followed by a publish that fails leaves `status=done` with `publish_status=failed:telegram`. The row is not `failed` — the video exists — so `--select failed` will not pick it up; `--select publish-failed` does. That mode re-renders from the cached job assets (no LLM or image API calls) and re-publishes **only** the platforms named in `publish_status`, so platforms that already received the video do not get a duplicate.

> **Changing a row’s `topic` after its assets exist** discards `assets/jobs/<id>/images/` — slide images are rendered from the script, so a new script invalidates them. They are regenerated on the next run.

## Environment

```bash
# .env
CAPTION_MODE=none    # default for batch jobs (none | sentence | word)
IMAGE_PROVIDER=pollinations   # pollinations | chatgpt | mock
# ChatGPT images (when IMAGE_PROVIDER=chatgpt)
OPENAI_IMAGE_API_KEY=
OPENAI_IMAGE_MODEL=gpt-image-2
OPENAI_IMAGE_SIZE=1152x2048
OPENAI_IMAGE_QUALITY=auto          # auto | low | medium | high
OPENAI_IMAGE_PROMPT_MODE=compact   # compact (default) | full
MUSIC_DIR=assets/music   # or music/
JOBS_CSV=jobs.csv
PUBLISH_PLATFORMS=facebook,telegram   # optional — comma-separated
FACEBOOK_PAGE_ID=                       # required for facebook
FACEBOOK_ACCESS_TOKEN=                  # Page token with pages_manage_posts
```

## Daily schedule

### Linux / macOS (cron)

```cron
# Every day at 00:00 — all pending jobs due today (created_at date == today VN)
0 0 * * * cd /path/to/Short-form-content-generator && .venv/bin/python batch_runner.py --csv jobs.csv --select due-today --max-jobs 0 --publish >> logs/batch.log 2>&1

# Every day at 06:00 — retry all failed jobs
0 6 * * * cd /path/to/Short-form-content-generator && .venv/bin/python batch_runner.py --csv jobs.csv --select failed --max-jobs 0 --publish >> logs/batch.log 2>&1
```

### Windows (Task Scheduler)

1. **Action:** Start a program  
   - Program: `C:\path\to\Short-form-content-generator\.venv\Scripts\python.exe`  
   - Arguments (00:00): `batch_runner.py --csv jobs.csv --select due-today --max-jobs 0 --publish`  
   - Arguments (06:00 retry): `batch_runner.py --csv jobs.csv --select failed --max-jobs 0 --publish`  
   - Start in: `C:\path\to\Short-form-content-generator`
2. **Trigger:** Two daily triggers (midnight + 06:00), or one trigger per mode.
3. Ensure `.env` and Remotion (`cd remotion && npm install`) are set up on the machine.

### GitHub Actions (no server)

Runs the daily batch on GitHub-hosted **ubuntu-22.04** runners (glibc 2.35 — Remotion works without a VPS). Defined in [`.github/workflows/daily-batch.yml`](../.github/workflows/daily-batch.yml).

**Setup (one-time):**

1. Push `jobs.csv` and the workflow to the **default branch** (`main`) — scheduled workflows only run there.
2. Repo **Settings → Secrets and variables → Actions** → add:
   - `OPENAI_API_KEY` (required — Gemini text LLM for scripts/TTS writer)
   - `OPENAI_BASE_URL` (recommended — see [`.env.example`](../.env.example))
   - `OPENAI_IMAGE_API_KEY` (required — ChatGPT slide images; separate from `OPENAI_API_KEY`)
   - `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` (optional — failure alerts via `send-message`; also used when `PUBLISH_PLATFORMS` includes `telegram`)
   - `GOOGLE_DRIVE_CLIENT_ID`, `GOOGLE_DRIVE_CLIENT_SECRET`, `GOOGLE_DRIVE_REFRESH_TOKEN`, `GOOGLE_DRIVE_FOLDER_ID` (required when `telegram` is in `PUBLISH_PLATFORMS` — Telegram sends a Drive link, not the MP4)
   - `PUBLISH_PLATFORMS` (optional — comma-separated: `drive`, `facebook`, `telegram`)
   - `FACEBOOK_PAGE_ID` + `FACEBOOK_ACCESS_TOKEN` (optional — required when `facebook` is in `PUBLISH_PLATFORMS`)
3. Ensure **Settings → Actions → General → Workflow permissions** is set to **Read and write** so the run can commit `jobs.csv`.

**Image quality and size (workflow `env`, not secrets):** The daily workflow sets `IMAGE_PROVIDER=chatgpt` with defaults in [`.github/workflows/daily-batch.yml`](../.github/workflows/daily-batch.yml):

| Variable | Workflow default | Valid values |
|----------|------------------|--------------|
| `OPENAI_IMAGE_SIZE` | `896x1600` | `WxH` portrait; both edges divisible by 16 (e.g. `1152x2048` for higher resolution) |
| `OPENAI_IMAGE_QUALITY` | `low` | `auto`, `low`, `medium`, `high` |
| `OPENAI_IMAGE_PROMPT_MODE` | `compact` | `compact`, `full` |

Edit the workflow file to change these, or add optional repo secrets (`OPENAI_IMAGE_SIZE`, `OPENAI_IMAGE_QUALITY`) and reference them in `env:` if you prefer not to commit tuning values.

**How it runs:**

- Triggers (GitHub Actions schedule is UTC; times below are Vietnam / UTC+7). **Cron only runs from the default branch (`main`)** — merge workflow changes before expecting schedule to update.
  - `cron: "3 17 * * *"` → **00:03 VN** — (1) `--select due-today --max-jobs 0 --publish`, (2) prefill assets for **today + future** pending jobs
  - `cron: "3 23 * * *"` → **06:03 VN** — (1) `--select failed --max-jobs 0 --publish`, (2) `--select publish-failed --max-jobs 0`, (3) same prefill
  - Manual **Run workflow** (`workflow_dispatch`) with input `mode`: `due-today`, `pending`, `failed`, or `publish-failed`
  - GitHub may delay scheduled runs by minutes–hours (or skip a day on low-activity repos). Prefer **Run workflow** to verify.
- **Asset prefill step** (`scripts/pregenerate_job_assets.py --from-today`): pending rows with `created_at` date **≥ today (VN)**; skip libraries already complete; only generate missing script/images. First run after adding many future jobs can take a long time and cost many ChatGPT image calls; later days mostly skip.
  - It runs **after** the video steps and is `continue-on-error`. Prefill is an optimization for *later* days — the batch fills gaps for the due job on its own — so a future job's script/image failure must never block today's render. Ordering it first inverted that priority: one bad row two weeks out could skip the whole day.
  - Stops early when the LLM reports an exhausted daily quota (same rule as the batch): the free tier is shared, so every later job would fail identically. The remaining rows are picked up by the next run.
- One day may have **multiple** jobs; set each row’s `created_at` to that calendar day (e.g. `2026-07-10T00:00:00+07:00`). Empty `created_at` is skipped by `due-today` / `--from-today`.
- Slideshow jobs reuse `assets/jobs/<id>/` when complete; otherwise generate + persist missing parts, then TTS + Remotion + publish. Optional `--require-job-assets` fails if the library is missing.
- After each successful render, the batch publishes that MP4 via `publish_runner` (`--publish`) so multi-job runs do not lose earlier videos when `output/final/` is overwritten.
- Then commits the updated `jobs.csv` + `assets/jobs/` back to the repo.
- The last rendered `final.mp4` is also uploaded as a build **artifact** (retained 7 days). Artifacts are not committed to git.
- With `telegram` in `PUBLISH_PLATFORMS`, the bot uploads to Google Drive first and sends the link. Caption prefers `publish` metadata from `pipeline_payload.json`; falls back to `#<job id> — <topic>` from `jobs.csv`. On workflow failure, a plain Telegram `sendMessage` is sent (when `TELEGRAM_*` secrets are set).

**CLI select modes:**

```bash
# All pending due today (VN calendar date on created_at)
python batch_runner.py --csv jobs.csv --select due-today --max-jobs 0 --publish

# Retry every failed row
python batch_runner.py --csv jobs.csv --select failed --max-jobs 0 --publish

# Re-publish done rows whose publish failed (only the platforms that failed; implies --publish)
python batch_runner.py --csv jobs.csv --select publish-failed --max-jobs 0

# Legacy: next pending only (no date filter)
python batch_runner.py --csv jobs.csv --select pending --max-jobs 1
```

**Multi-platform publish (local or CI):**

```bash
# After a successful batch run — reads PUBLISH_PLATFORMS + per-platform creds from .env
python core/publish_runner.py output/final/final.mp4 --jobs-csv jobs.csv

# Publish to one platform only (overrides PUBLISH_PLATFORMS)
python core/publish_runner.py output/final/final.mp4 --platforms facebook

# Legacy Telegram-only CLI (still supported)
python core/telegram_notify.py send-video output/final/final.mp4 --jobs-csv jobs.csv
```

| Platform | Env vars | Notes |
|----------|----------|-------|
| `facebook` | `FACEBOOK_PAGE_ID`, `FACEBOOK_ACCESS_TOKEN` | Page Reels via Graph API; 9:16, ≤90s |
| `telegram` | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Bot API `sendVideo`; 50 MB limit |

If `PUBLISH_PLATFORMS` is unset, `publish_runner` exits 0 and skips all platforms. A listed platform with missing creds is skipped individually (no error).

**Facebook setup (one-time):**

1. Create a Meta app with Facebook Login.
2. Grant the app `pages_manage_posts`, `pages_show_list`, and `pages_read_engagement`.
3. Generate a **Page access token** for the target Facebook Page.
4. Set `PUBLISH_PLATFORMS=facebook`, `FACEBOOK_PAGE_ID`, and `FACEBOOK_ACCESS_TOKEN` in `.env` or GitHub Actions secrets.

Meta rate-limits API-published Reels to ~30 per Page per 24 hours.

**Telegram (local or CI):**

```bash
# After a successful batch run (reads TELEGRAM_* from .env)
python core/telegram_notify.py send-video output/final/final.mp4 --jobs-csv jobs.csv
# Caption: pipeline_payload.json publish block when present, else jobs.csv topic

# Status message only
python core/telegram_notify.py send-message "No pending jobs today."
```

If `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` are unset, the CLI exits 0 and skips delivery.

**First run:** trigger manually via **Run workflow** rather than waiting for the schedule, to confirm secrets and rendering work.


## Concurrency

A lock file (`jobs.csv.lock`) prevents overlapping runs. If cron fires while a job is still rendering, the second invocation exits quietly (exit code 0).

Stale `running` rows (e.g. after a crash) are reset to `pending` on the next run.

## Single video (manual)

Same chain as batch, without CSV:

```bash
python orchestrator_mvp.py "your topic" --caption-mode sentence
# → output/generations/<timestamp>/final.mp4
```

Use `--no-render` to generate assets only.

## Related

- Roadmap: [architecture/roadmap.md](architecture/roadmap.md)
- Pipeline map: `.cursor/skills/explain-pipeline-feature/pipeline-map.md`
