# CSV batch demo — three videos per day

Run the slideshow pipeline on **pending CSV rows** (by date or retry). Schedule with cron / Task Scheduler / GitHub Actions for daily production.

Production cadence is **three videos a day** at **04:33, 08:33, and 16:33 VN**. Each slot renders **one** row (`--max-jobs 1`), so `jobs.csv` needs three `pending` rows per calendar day.

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
  usage.json           # tokens each image cost (ChatGPT provider)
  images/
    intro.png
    scene_1.png
    scene_2.png
    scene_3.png
    ending.png
```

### Image token usage (`usage.json`)

Image tokens are spent **during prefill**, not during the video batch — by render time the
PNGs are cached, so a report there would always read zero. `pregenerate_job_assets.py`
therefore writes what each image cost next to the image itself:

```json
{
  "topic": "...",
  "images": [
    {"image": "intro.png", "slide_id": 1, "role": "intro", "provider": "chatgpt",
     "model": "gpt-image-2", "quality": "low", "generated_at": "2026-07-16T04:20:09+00:00",
     "input_tokens": 486, "cached_tokens": 384, "output_tokens": 4160, "total_tokens": 4646}
  ],
  "totals": {"images": 5, "input_tokens": 2430, "cached_tokens": 1920,
             "output_tokens": 20800, "total_tokens": 23230}
}
```

- **Records only images actually generated.** A cached PNG costs nothing, so a gap-fill run
  replaces just the entry it regenerated and leaves the other four at what they really cost.
- **Never invents numbers.** Providers that report no usage (`pollinations`, `mock`) get an
  entry with no token fields and summaries read `tokens unavailable`. No USD conversion —
  token counts come from the API, prices would be a guess.
- CI commits it with `assets/jobs/`, so history lives in git rather than expiring CI logs.
- `--notify` sends the same per-image breakdown to Telegram (skipped quietly when
  `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` are unset; a Telegram failure never fails prefill).

```bash
# Prefill with a token report in the log + Telegram (same as CI)
python scripts/pregenerate_job_assets.py --csv jobs.csv --from-today --notify
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
├── endcard.jpg          # brand card, staged from assets/endcard/
└── <music>.mp3          # if a track was picked
```

Every video ends with the brand end card from `assets/endcard/endcard.jpg`, held for
`ENDCARD_DURATION_MS` (default 2500) **after** the last spoken word — narration and
slide timing are unchanged, the video just runs that much longer. Set `ENDCARD_PATH=off`
to drop it.

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
| `attempts` | no | Runs so far; incremented **before** each render. Retry modes stop at `--max-attempts` (default 3). Clear the cell to grant a fresh budget. |

Add many `pending` rows to the CSV — three per day for the current cadence. Set each row’s `created_at` to the Vietnam calendar day you want it to run; only the **date** is matched, but keep the time aligned with its slot (`04:33` / `08:33` / `16:33`) so the file reads in run order. Within a day the slots consume rows **top to bottom**, since `--max-jobs 1` takes the first match. GitHub runs `--select due-today --max-jobs 1` in each of the three slots and retries every `failed` row at **22:03 VN**. Local default remains `--select pending --max-jobs 1` (next pending only).

### Each slot repairs the day before adding to it

A slot does not just render its own job — it first checks whether the day's earlier slots
actually succeeded, and fixes what did not:

1. `--select failed-today --max-jobs 0 --publish` — retry today's failed renders
2. `--select publish-failed-today --max-jobs 0` — re-publish today's renders that never reached a platform
3. `--select due-today --max-jobs 1 --publish` — render this slot's own job

So a job that fails at 04:33 is retried at 08:33 *and* job 2 still renders — the day catches
up instead of waiting for the 22:03 sweep. Steps 1–2 are `continue-on-error`: a row that fails
again must never stop the slot from rendering its own job.

**Why `failed-today` and not `failed`:** the nightly `failed` sweep retries every failure ever
recorded. Running that in each slot would re-attempt weeks-old rows three times a day and burn
the image quota that today's videos need.

**The attempt cap** (`--max-attempts`, default 3) is what stops a job failing for a fixed reason
— a topic the image API always refuses, say — from consuming a retry in every slot forever. The
`attempts` column is incremented *before* the render, so even a hard crash burns its attempt.
Once a row hits the cap, both `failed-today` and the nightly `failed` sweep skip it and wait for
you. To force another try, clear that row's `attempts` cell, or pass `--max-attempts 0`.
The cap never affects `due-today`: a fresh job always renders, whatever `attempts` says.

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
ENDCARD_PATH=assets/endcard/endcard.jpg   # brand card after narration; "off" to disable
ENDCARD_DURATION_MS=2500                  # how long it holds
JOBS_CSV=jobs.csv
PUBLISH_PLATFORMS=facebook,telegram   # optional — comma-separated
FACEBOOK_PAGE_ID=                       # required for facebook
FACEBOOK_ACCESS_TOKEN=                  # Page token with pages_manage_posts
```

## Daily schedule

### Linux / macOS (cron)

```cron
# Three videos a day — each slot renders the next pending job due today (VN date)
33 4  * * * cd /path/to/Short-form-content-generator && .venv/bin/python batch_runner.py --csv jobs.csv --select due-today --max-jobs 1 --publish >> logs/batch.log 2>&1
33 8  * * * cd /path/to/Short-form-content-generator && .venv/bin/python batch_runner.py --csv jobs.csv --select due-today --max-jobs 1 --publish >> logs/batch.log 2>&1
33 16 * * * cd /path/to/Short-form-content-generator && .venv/bin/python batch_runner.py --csv jobs.csv --select due-today --max-jobs 1 --publish >> logs/batch.log 2>&1

# Every day at 22:03 — retry all failed jobs, after the three slots
3 22 * * * cd /path/to/Short-form-content-generator && .venv/bin/python batch_runner.py --csv jobs.csv --select failed --max-jobs 0 --publish >> logs/batch.log 2>&1
```

### Windows (Task Scheduler)

1. **Action:** Start a program  
   - Program: `C:\path\to\Short-form-content-generator\.venv\Scripts\python.exe`  
   - Arguments (04:33 / 08:33 / 16:33): `batch_runner.py --csv jobs.csv --select due-today --max-jobs 1 --publish`  
   - Arguments (22:03 retry): `batch_runner.py --csv jobs.csv --select failed --max-jobs 0 --publish`  
   - Start in: `C:\path\to\Short-form-content-generator`
2. **Trigger:** Three daily triggers (04:33, 08:33, 16:33) for the render task, plus one at 22:03 for the retry task.
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
  - `cron: "33 21 * * *"` → **04:33 VN (next day)** — (1) repair today (`failed-today`, then `publish-failed-today`), (2) `--select due-today --max-jobs 1 --publish`, (3) prefill assets for **today + future** pending jobs
  - `cron: "33 1 * * *"` → **08:33 VN** — same as above (second video of the day)
  - `cron: "33 9 * * *"` → **16:33 VN** — same as above (third video of the day)
  - `cron: "3 15 * * *"` → **22:03 VN** — after all three renders: (1) `--select failed --max-jobs 0 --publish`, (2) `--select publish-failed --max-jobs 0`, (3) same prefill
  - Every prefill step runs `--notify`, so a run that generated images reports their token cost to Telegram.
  - Manual **Run workflow** (`workflow_dispatch`) with input `mode`: `due-today`, `pending`, `failed`, or `publish-failed`
  - GitHub may delay scheduled runs by minutes–hours (or skip a day on low-activity repos). Prefer **Run workflow** to verify.
- **Asset prefill step** (`scripts/pregenerate_job_assets.py --from-today`): pending rows with `created_at` date **≥ today (VN)**; skip libraries already complete; only generate missing script/images. First run after adding many future jobs can take a long time and cost many ChatGPT image calls; later days mostly skip.
  - It runs **after** the video steps and is `continue-on-error`. Prefill is an optimization for *later* days — the batch fills gaps for the due job on its own — so a future job's script/image failure must never block today's render. Ordering it first inverted that priority: one bad row two weeks out could skip the whole day.
  - Stops early when the LLM reports an exhausted daily quota (same rule as the batch): the free tier is shared, so every later job would fail identically. The remaining rows are picked up by the next run.
- One day has **three** jobs, one per slot; set each row’s `created_at` to that calendar day (e.g. `2026-07-16T04:33:00+07:00`). Empty `created_at` is skipped by `due-today` / `--from-today`. A day with fewer than three rows simply produces fewer videos — a slot that finds nothing exits cleanly.
- **A missed slot strands its row.** `due-today` only matches *today’s* VN date, so a row that no slot consumed (GitHub skipped the run, or you added three rows for a day whose slots had already passed) stays `pending` forever — the next day it no longer matches. Recover it with **Run workflow → mode `pending`**, which ignores the date filter, or move its `created_at` to a future day.
- Slideshow jobs reuse `assets/jobs/<id>/` when complete; otherwise generate + persist missing parts, then TTS + Remotion + publish. Optional `--require-job-assets` fails if the library is missing.
- After each successful render, the batch publishes that MP4 via `publish_runner` (`--publish`) so multi-job runs do not lose earlier videos when `output/final/` is overwritten.
- Then commits the updated `jobs.csv` + `assets/jobs/` back to the repo.
- The last rendered `final.mp4` is also uploaded as a build **artifact** (retained 7 days). Artifacts are not committed to git.
- With `telegram` in `PUBLISH_PLATFORMS`, the bot uploads to Google Drive first and sends the link. Caption prefers `publish` metadata from `pipeline_payload.json`; falls back to `#<job id> — <topic>` from `jobs.csv`. On workflow failure, a plain Telegram `sendMessage` is sent (when `TELEGRAM_*` secrets are set).

**CLI select modes:**

```bash
# Next pending job due today (VN calendar date on created_at) — one per slot
python batch_runner.py --csv jobs.csv --select due-today --max-jobs 1 --publish

# Every pending job due today, in one go
python batch_runner.py --csv jobs.csv --select due-today --max-jobs 0 --publish

# Retry every failed row (nightly sweep)
python batch_runner.py --csv jobs.csv --select failed --max-jobs 0 --publish

# Retry only today's failures — what each slot runs before its own job
python batch_runner.py --csv jobs.csv --select failed-today --max-jobs 0 --publish

# Ignore the attempt cap and retry regardless
python batch_runner.py --csv jobs.csv --select failed --max-jobs 0 --publish --max-attempts 0

# Re-publish done rows whose publish failed (only the platforms that failed; implies --publish)
python batch_runner.py --csv jobs.csv --select publish-failed --max-jobs 0

# Same, limited to today
python batch_runner.py --csv jobs.csv --select publish-failed-today --max-jobs 0

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
