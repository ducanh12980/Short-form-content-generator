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
| Run slideshow pipeline | `python orchestrator_mvp.py "your topic" --mode slideshow` |
| Slideshow + free images | `python orchestrator_mvp.py "topic" --mode slideshow --image-provider pollinations` |
| Slideshow + mock images | `python orchestrator_mvp.py "topic" --mode slideshow --image-provider mock` |
| Generate slide images only | `python core/slide_image_stage.py output/pipeline_payload.json` |
| Render preview (Remotion) | `python core/remotion_render_stage.py output/pipeline_payload.json` |
| Remotion Studio | `cd remotion && npm run studio` |
| Run tests | `pytest -q` |
| Lint / format | TBD |

## Directory guide

| Path | Purpose |
|------|---------|
| `remotion/` | **Main video renderer** — Remotion compositions, Studio, export |
| `core/remotion_render_stage.py` | Python bridge: `project.json` → Remotion CLI |
| `docs/` | Human + agent documentation (architecture, workflow, ADRs) |
| `docs/domain/content-learning-system.md` | **Core product spec** — production, optimization, knowledge loop |
| `docs/workflow/` | Agentic workflow, task tracking, PR conventions |
| `docs/architecture/` | System design, module boundaries |
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
