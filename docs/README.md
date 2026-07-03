# Documentation

Index for humans and coding agents. Keep root `AGENTS.md` lightweight; put detail here.

## Structure

| Folder | Contents |
|--------|----------|
| [domain/](domain/) | Product domain: content pipeline, learning loop, KPIs |
| [architecture/](architecture/) | System design, modules, data flow, technical spec |
| [workflow/](workflow/) | Agentic workflow, tasks, PR process |
| [conventions/](conventions/) | Code style, naming, commit rules |
| [security/](security/) | Secrets, API usage, content handling |
| [adr/](adr/) | Architecture Decision Records |

## How agents should use this

1. Start with root `AGENTS.md` for orientation.
2. Read only the doc sections needed for the current task.
3. Update `workflow/current-tasks.md` when picking up or completing work.
4. Add an ADR when making a durable architectural choice.

## Conventions

- Markdown files, kebab-case filenames.
- ADRs: `adr/NNNN-short-title.md` (four-digit number, zero-padded).
- Keep docs actionable; avoid duplicating content across files — link instead.
