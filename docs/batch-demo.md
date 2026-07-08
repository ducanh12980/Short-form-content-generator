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
| `image_provider` | no | `pollinations` \| `gemini` \| `mock` |
| `output_path` | no | Filled on success |
| `error` | no | Filled on failure |
| `created_at` | no | ISO timestamp |
| `completed_at` | no | ISO timestamp |

Add many `pending` rows to the CSV. With the default **`--max-jobs 1`**, each scheduled run processes **only the next pending row** — suitable for one video per day.

## Environment

```bash
# .env
CAPTION_MODE=none    # default for batch jobs (none | sentence | word)
IMAGE_PROVIDER=pollinations
MUSIC_DIR=assets/music   # or music/
JOBS_CSV=jobs.csv
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
   - `OPENAI_API_KEY` (required)
   - `OPENAI_BASE_URL` (recommended — see [`.env.example`](../.env.example))
   - `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` (optional — sends `final.mp4` after a successful render)
3. Ensure **Settings → Actions → General → Workflow permissions** is set to **Read and write** so the run can commit `jobs.csv`.

**How it runs:**

- Trigger: daily `cron: "0 1 * * *"` (01:00 UTC = 08:00 UTC+7) or manual **Run workflow** (`workflow_dispatch`).
- Processes one pending row (`--max-jobs 1`), then commits the updated `jobs.csv` (`status=done`, `output_path`) back to the repo.
- The rendered `final.mp4` is uploaded as a build **artifact** (retained 90 days) — download it from the run page. Artifacts are not committed to git.
- When Telegram secrets are set, the workflow uploads `final.mp4` via Bot API `sendVideo` (50 MB limit). Caption prefers `publish` metadata from `output/final/pipeline_payload.json` (title, description, hashtags); falls back to `#<job id> — <topic>` from `jobs.csv`. On failure, a plain `sendMessage` is sent instead.

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
