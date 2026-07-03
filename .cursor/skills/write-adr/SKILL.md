---
name: write-adr
description: >-
  Create or update Architecture Decision Records in docs/adr/. Use when making
  durable technical choices (stack, LLM provider, media pipeline, data retention).
---

# Write ADR

## When to use

- Choosing language, framework, or major dependencies
- LLM provider, prompt storage, cost controls
- Media pipeline (local vs cloud)
- Security or data retention policies

Skip for trivial refactors or obvious bug fixes.

## Steps

1. Read `docs/adr/README.md` for format and existing index.
2. Pick next number: highest NNNN + 1 (zero-padded, e.g. `0001`).
3. Create `docs/adr/NNNN-short-title.md`:

```markdown
# NNNN. Title

- **Status**: proposed
- **Date**: YYYY-MM-DD
- **Context**: ...
- **Decision**: ...
- **Consequences**: ...
```

4. Add a row to the index table in `docs/adr/README.md`.
5. Link from `docs/architecture/overview.md` if the decision affects modules or stack.

## Status values

- `proposed` — under review
- `accepted` — team/agent agreed
- `deprecated` — no longer recommended
- `superseded by NNNM` — replaced by another ADR
