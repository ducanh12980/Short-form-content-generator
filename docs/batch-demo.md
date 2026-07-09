# CSV batch demo — one video per day

Run the slideshow pipeline on **one pending CSV row** per invocation. Schedule with cron (Linux/macOS) or Task Scheduler (Windows) for daily production.

## Quick start

```bash
# Create jobs.csv with example rows
python batch_runner.py --init

# Process the next pending row (generation + Remotion → final.mp4)
python batch_runner.py --csv jobs.csv

# Preview queue without running
python batch_runner.py --csv jobs.csv --dry-run
```

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
| `created_at` | no | ISO timestamp |
| `completed_at` | no | ISO timestamp |

Add many `pending` rows to the CSV. With the default **`--max-jobs 1`**, each scheduled run processes **only the next pending row** — suitable for one video per day.

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
# Every day at 08:00 — one pending video
0 8 * * * cd /path/to/Short-form-content-generator && .venv/bin/python batch_runner.py --csv jobs.csv --max-jobs 1 >> logs/batch.log 2>&1
```

### Windows (Task Scheduler)

1. **Action:** Start a program  
   - Program: `C:\path\to\Short-form-content-generator\.venv\Scripts\python.exe`  
   - Arguments: `batch_runner.py --csv jobs.csv --max-jobs 1`  
   - Start in: `C:\path\to\Short-form-content-generator`
2. **Trigger:** Daily at your chosen time.
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
   - `PUBLISH_PLATFORMS` (optional — comma-separated: `facebook`, `telegram`)
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

- Trigger: daily `cron: "0 1 * * *"` (01:00 UTC = 08:00 UTC+7) or manual **Run workflow** (`workflow_dispatch`).
- Processes one pending row (`--max-jobs 1`), then commits the updated `jobs.csv` (`status=done`, `output_path`) back to the repo.
- The rendered `final.mp4` is uploaded as a build **artifact** (retained 90 days) — download it from the run page. Artifacts are not committed to git.
- When `PUBLISH_PLATFORMS` is set, the workflow publishes `final.mp4` via `core/publish_runner.py`. Caption prefers `publish` metadata from `output/final/pipeline_payload.json` (title, description, hashtags); falls back to `#<job id> — <topic>` from `jobs.csv`. On failure, a plain Telegram `sendMessage` is sent (when `TELEGRAM_*` secrets are set).

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
