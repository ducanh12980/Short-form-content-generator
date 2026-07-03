# Architecture overview

> Status: **planning** — high-level index. Full technical spec: [ai-shorts-engine-spec.md](ai-shorts-engine-spec.md).

## Purpose

Generate short-form video content end-to-end or in stages. The full product workflow (Production → Optimization → Knowledge) is defined in [../domain/content-learning-system.md](../domain/content-learning-system.md).

- **Input**: topic, brief, brand voice, reference material
- **Generation**: script, hook, captions, metadata (title, hashtags)
- **Production**: voiceover, visuals, timing, subtitles (optional)
- **Output**: platform-ready assets (9:16, safe zones, duration limits)

## Planned modules (initial)

| Module | Responsibility |
|--------|----------------|
| **Core / domain** | Content models, platform constraints, validation |
| **Generation** | LLM prompts, structured output, retries |
| **Media** | Audio/video assembly, ffmpeg or cloud APIs |
| **Pipeline** | Orchestration, job queue, idempotent steps |
| **CLI / API** | Entry points for humans and automation |

## Platform constraints (reference)

| Platform | Aspect ratio | Typical max length |
|----------|--------------|-------------------|
| TikTok | 9:16 | 3 min (short-form often &lt; 60s) |
| Instagram Reels | 9:16 | 90s |
| YouTube Shorts | 9:16 | 60s |

Agents implementing features should verify current platform limits before hard-coding.

## Stack (TBD)

Document chosen stack here when decided:

- Language / runtime:
- Package manager:
- LLM provider(s):
- Media tooling:
- Deployment:

## Data flow (high level)

```mermaid
flowchart LR
  Input[Topic / Brief] --> Script[Script generation]
  Script --> Review[Optional review]
  Review --> Media[Media pipeline]
  Media --> Export[Platform export]
```

## Related

- Technical spec: [ai-shorts-engine-spec.md](ai-shorts-engine-spec.md)
- Product spec: [../domain/content-learning-system.md](../domain/content-learning-system.md)
- ADRs: [../adr/README.md](../adr/README.md)
- Agent workflow: [../workflow/agentic-workflow.md](../workflow/agentic-workflow.md)
