---
name: explain-pipeline-feature
description: >-
  Explains short-form video pipeline components and new technology integrations
  in depth — data flow, module boundaries, upstream/downstream handoffs, and
  under-the-hood behavior. Use when adding or swapping tech in core/ modules,
  implementing a new feature in the pipeline, or when the user asks how a
  component works, what happens behind the hood, or wants a deep walkthrough.
---

# Explain Pipeline Feature

Produce a **deep, readable explanation** so the operator understands what changed, why, and how data moves through the decoupled pipeline — not just what files were edited.

## When to run

- A new library, API, or pattern is introduced in any pipeline component
- The user asks "how does X work?", "explain the flow", or "what happens under the hood?"
- Before or after a tech swap (e.g., edge-tts → ElevenLabs, Pexels → local assets)
- When reviewing a PR that touches `core/` or `orchestrator_mvp.py`

## Before explaining

1. Read [pipeline-map.md](pipeline-map.md) for the canonical module graph and schemas.
2. Read the **actual changed files** (do not explain from memory alone).
3. Identify which component(s) changed and whether orchestrator handoff changed.
4. If technology was swapped, contrast **old vs new** behavior.

## Explanation workflow

```
1. Scope     → Which component + what new tech?
2. Context   → Where in the full pipeline?
3. Read code → Inputs, outputs, side effects
4. Explain   → Use template below (all required sections)
5. Validate  → Would a new teammate know what to debug?
```

## Required output structure

Copy this template and fill every section. Use plain language first; add technical depth second.

```markdown
# [Component Name]: [Feature or Technology]

## One-sentence summary
[What this piece does in the pipeline, in one line.]

## Where it sits in the pipeline
- **Stage:** [Production | Optimization | Knowledge | Orchestration]
- **Module:** `core/...` or `orchestrator_mvp.py`
- **Upstream:** [What calls it / what data it receives]
- **Downstream:** [What consumes its output]

## The problem it solves
[Why this module exists; what breaks if you remove it.]

## Under the hood (step by step)
Numbered steps of the runtime flow inside this component:
1. ...
2. ...

Include: API calls, file writes, async/event loops, error paths.

## Data contract
| Field | Type | Meaning |
|-------|------|---------|
| ... | ... | ... |

Show example input/output JSON or file paths when relevant.

## New technology: [name]
- **What it is:** [Library/service in plain terms]
- **Why we chose it here:** [Fit for this module]
- **How we use it:** [Specific functions, endpoints, config]
- **Alternatives considered:** [What you could swap in without touching other modules]

## Pipeline diagram (this component highlighted)
[Mermaid flowchart — upstream → THIS → downstream]

## Integration points
- **Env vars:** ...
- **Config files:** ...
- **Hard dependencies:** ...

## Failure modes & debugging
| Symptom | Likely cause | Where to look |
|---------|--------------|---------------|
| ... | ... | ... |

## Decoupling check
Answer explicitly:
- [ ] Can this tech be swapped without changing other `core/` modules?
- [ ] Is output schema-stable for downstream consumers?
- [ ] Are secrets/config externalized (not hardcoded)?

## What to read next
- [Links to source files and related docs]
```

## Depth guidelines

| Topic | Go deep on |
|-------|------------|
| **LLM agents** | Prompt role, JSON schema, retry/fallback, token cost |
| **TTS** | Voice selection, timestamp source, audio format, sync accuracy |
| **Media retrieval** | Keyword extraction logic, API auth, clip selection, caching |
| **Caption render** | Token ↔ timestamp matching, theme resolution, MoviePy layer stack |
| **Audio mix** | Ducking strategy, volume curves, output format |
| **Orchestrator** | Agent sequence, payload shape, what is deferred to later stages |

## Tone rules

- Teach **cause → effect**, not file listings alone.
- Use analogies sparingly; prefer concrete data paths (`topic → script.full_text → narration.mp3`).
- Call out **non-obvious** behavior (unit conversions, async, schema mismatches).
- If something is stubbed or not wired yet, say so explicitly.

## After a tech introduction

Also suggest (briefly):
1. `.env.example` keys if new secrets are needed
2. Whether an ADR is warranted (`write-adr` skill)
3. One manual test command to verify the component in isolation

## Reference

- Full pipeline map: [pipeline-map.md](pipeline-map.md)
- Product loop (Production → Optimization → Knowledge): `docs/domain/content-learning-system.md`
- Technical spec: `docs/architecture/ai-shorts-engine-spec.md`
