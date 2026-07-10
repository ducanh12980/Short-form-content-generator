# AGENTS.md

Lightweight index for coding agents. Read this at session start; follow links for detail instead of loading everything into context.

## Project overview

Short-form content generator: tools and pipelines to create short-form video content (scripts, captions, assets, and exports for platforms like TikTok, Reels, and YouTube Shorts).

Stack and layout will evolve as code lands. Treat `docs/` as the source of truth for architecture, workflow, and decisions.

## Quick commands

```bash
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cd remotion && npm install && cd ..
cp .env.example .env   # fill OPENAI_API_KEY (Gemini), OPENAI_BASE_URL
```

| Action | Command |
|--------|---------|
| Install Python deps | `pip install -r requirements.txt` |
| Install Remotion deps | `cd remotion && npm install` |
| Run MVP pipeline | `python orchestrator_mvp.py "your topic"` |
| Run slideshow pipeline (default) | `python orchestrator_mvp.py "your topic"` or `--mode slideshow` |
| Slideshow + free images | `python orchestrator_mvp.py "topic" --mode slideshow --image-provider pollinations` |
| Slideshow + ChatGPT images | `python orchestrator_mvp.py "topic" --mode slideshow --image-provider chatgpt` — set `OPENAI_IMAGE_*` in `.env` (`PROMPT_MODE=compact\|full`, `QUALITY=auto\|low\|medium\|high`) |
| Slideshow + mock images | `python orchestrator_mvp.py "topic" --mode slideshow --image-provider mock` |
| Run slideshow + final MP4 | `python orchestrator_mvp.py "topic"` (no captions by default) |
| Slideshow + sentence captions | `python orchestrator_mvp.py "topic" --caption-mode sentence` |
| Payload only (no render) | `python orchestrator_mvp.py "topic" --no-render` |
| **Pregenerate job assets** | `python scripts/pregenerate_job_assets.py --csv jobs.csv` — optional freeze into `assets/jobs/<id>/` (batch also generates+persists when missing) |
| **Daily CSV batch** | `python batch_runner.py --csv jobs.csv --select due-today --max-jobs 0 --publish` — see [docs/batch-demo.md](docs/batch-demo.md) |
| **Daily batch on GitHub Actions** | `.github/workflows/daily-batch.yml` (scheduled) — see [docs/batch-demo.md](docs/batch-demo.md#github-actions-no-server) |
| Send MP4 to Telegram | `python core/telegram_notify.py send-video output/final/final.mp4 --jobs-csv jobs.csv` |
| **Publish to platforms** | `python core/publish_runner.py output/final/final.mp4 --jobs-csv jobs.csv` — set `PUBLISH_PLATFORMS=facebook,telegram` |
| Generate slide images only | `python core/slide_image_stage.py output/final/pipeline_payload.json` |
| Render final MP4 (Remotion) | `python core/remotion_render_stage.py output/final/pipeline_payload.json` |
| **Stitch images + audio** | `python stitch.py --images img.jpg --audio voice.mp3` — see [docs/stitch-cli.md](docs/stitch-cli.md) |
| Remotion Studio | `cd remotion && npm run studio` |
| Run tests | `pytest -q` |
| Lint / format | TBD |

## Directory guide

| Path | Purpose |
|------|---------|
| `remotion/` | **Main video renderer** — Remotion compositions, Studio, export |
| `core/telegram_notify.py` | Telegram delivery (legacy CLI; also used for failure alerts) |
| `core/publish_runner.py` | Multi-platform publish CLI (`PUBLISH_PLATFORMS`) |
| `core/publish/` | Per-platform publish adapters (facebook, telegram) + shared helpers |
| `docs/` | Human + agent documentation (architecture, workflow, ADRs) |
| `docs/domain/content-learning-system.md` | **Core product spec** — production, optimization, knowledge loop |
| `docs/workflow/` | Agentic workflow, task tracking, PR conventions |
| `docs/architecture/` | System design, module boundaries |
| `docs/architecture/roadmap.md` | **Current milestone** — CSV batch demo + cron (Optimization/Knowledge deferred) |
| `docs/architecture/ai-shorts-engine-spec.md` | **Technical spec** — modular shorts engine, hybrid orchestration |
| `docs/adr/` | Architecture Decision Records |
| `.cursor/rules/` | Scoped Cursor rules (coding standards, safety) |
| `.cursor/skills/` | On-demand project skills (invoke when relevant) |
| `.cursor/skills/explain-pipeline-feature/` | Deep-dive explanations when adding/swapping pipeline tech |

## Working agreements

- **Reproduce before fixing.** Confirm the failure, change one thing, verify.
- **Batch independent work.** Parallel reads/searches/commands when possible.
- **Index, don't encyclopedia.** Read linked docs only when the task needs them.
- **Record decisions.** Non-trivial choices go in `docs/adr/`.
- **Track work.** Update `docs/workflow/current-tasks.md` when starting or finishing agent tasks.
- **Be honest.** Say when tests were skipped or a step failed.

## Code style (summary)

Full detail: `docs/conventions/code-style.md` and `.cursor/rules/`.

- Match existing patterns in the repo before introducing new ones.
- Prefer small, focused changes over large refactors.
- Comments explain *why*, not *what* the code already shows.

## Security

- Never commit secrets (`.env`, API keys, credentials).
- Never interpolate untrusted input into shell/SQL strings.
- See `docs/security/guidelines.md` for content-generation specifics (API keys, user content).

## Testing & PRs

- Run the full test suite before committing when tests exist.
- Conventional Commits: `feat:`, `fix:`, `docs:`, `chore:`.
- PR checklist: `docs/workflow/pr-checklist.md`.

## Nested docs

When working in a subdirectory, prefer the closest `AGENTS.md` or relevant doc under that path (add nested files as the repo grows).
