# Architecture Decision Records (ADRs)

Durable decisions that agents and humans should follow until superseded.

## Format

Create `NNNN-short-title.md` (e.g. `0001-choose-llm-provider.md`):

```markdown
# NNNN. Title

- **Status**: proposed | accepted | deprecated | superseded by NNNM
- **Date**: YYYY-MM-DD
- **Context**: What problem are we solving?
- **Decision**: What we chose.
- **Consequences**: Tradeoffs, follow-ups.
```

## Index

| ADR | Title | Status |
|-----|-------|--------|
| [0001](0001-gemini-openai-compatible-sdk.md) | Gemini via OpenAI-compatible SDK | accepted |

## When to write an ADR

- Choice of language, framework, or major library
- LLM provider, prompt storage, or cost controls
- Media pipeline design (local ffmpeg vs cloud)
- Data retention for generated content
- Authentication or multi-tenant design

Skip ADRs for trivial refactors or obvious bug fixes.
