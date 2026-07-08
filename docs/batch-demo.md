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

**Old Linux servers (Ubuntu 20.04):** use branch `chore/remotion-ubuntu-2004` (pinned Remotion 4.0.150). See [remotion/README.md](../remotion/README.md). Ubuntu 22.04+ can use `main` with current Remotion.

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
