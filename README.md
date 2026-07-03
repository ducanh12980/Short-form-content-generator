# Short-form content generator

Tools and pipelines to create short-form video content — scripts, captions, media assembly, and platform-ready exports.

## Documentation

| Resource | Description |
|----------|-------------|
| [AGENTS.md](AGENTS.md) | Instructions for coding agents (start here for AI-assisted work) |
| [docs/domain/content-learning-system.md](docs/domain/content-learning-system.md) | Core product workflow — production, optimization, knowledge loop |
| [docs/architecture/ai-shorts-engine-spec.md](docs/architecture/ai-shorts-engine-spec.md) | Technical spec — modular AI shorts engine |
| [docs/](docs/) | Architecture, workflow, conventions, ADRs |

## Agentic workflow

1. Agents read [AGENTS.md](AGENTS.md) at session start.
2. Task board: [docs/workflow/current-tasks.md](docs/workflow/current-tasks.md)
3. Process: [docs/workflow/agentic-workflow.md](docs/workflow/agentic-workflow.md)

## Status

**MVP orchestrator done** (2026-07-03): topic → Vietnamese script → styled tokens → TTS → `output/narration.mp3` + `output/pipeline_payload.json`. Run: `python orchestrator_mvp.py "your topic"` (use project `.venv`). Next: caption render (T004). See [docs/workflow/current-tasks.md](docs/workflow/current-tasks.md).
