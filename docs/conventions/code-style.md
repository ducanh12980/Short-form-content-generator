# Code style

Conventions for implementation work. Agents should match existing code before applying these defaults.

## General

- **Minimal scope** — fix or build only what the task requires.
- **Self-explanatory code** — comments for non-obvious *why*, not restating *what*.
- **Existing patterns first** — grep the repo for similar files before inventing structure.

## Naming

| Item | Convention |
|------|------------|
| Files | kebab-case (adjust if stack dictates otherwise) |
| Tests | Colocate or `*.test.*` / `*_test.*` per stack norm |
| Docs | kebab-case under `docs/` |
| ADRs | `NNNN-short-title.md` |

## Errors

- Do not swallow errors silently.
- Surface actionable messages for operators (missing API key, invalid duration, etc.).
- Fail fast on invalid platform constraints (aspect ratio, length).

## Dependencies

- Prefer stable, well-maintained libraries for media and HTTP.
- Pin versions in lockfile; document new env vars in `docs/architecture/overview.md` or README.

## Content generation

- Keep prompts and templates versioned in repo (not only in runtime memory).
- Structured LLM output: validate schema before passing to media pipeline.
- Idempotent pipeline steps where possible (safe retries).

## Commits

Conventional Commits:

- `feat:` new capability
- `fix:` bug fix
- `docs:` documentation only
- `chore:` tooling, deps, CI
- `refactor:` behavior-preserving restructure

Only commit when the user explicitly asks.
