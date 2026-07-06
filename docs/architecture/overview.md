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

## Stack

| Layer | Choice | Notes |
|-------|--------|-------|
| **Generation / orchestration** | Python | `orchestrator_mvp.py`, `core/*` |
| **LLM** | Gemini via OpenAI-compatible SDK | ADR [0001](../adr/0001-gemini-openai-compatible-sdk.md) |
| **TTS** | edge-tts | Word-level timestamps for caption sync; per-scene concat in slideshow mode |
| **Slide images** | Gemini (`gemini-2.5-flash-image`) | `core/slide_image_stage.py` — same `OPENAI_API_KEY` as LLM |
| **Project state** | `project.json` | ADR [0002](../adr/0002-project-file-editability.md) |
| **Video render** | [Remotion](https://www.remotion.dev/) (`remotion/`) | ADR [0003](../adr/0003-remotion-render-and-editor.md) — captions, b-roll, export |
| **Audio mix (interim)** | MoviePy | `acoustic_compositor.py` until Remotion/ffmpeg mix |
| **Deployment** | TBD | Local Node SSR first; Lambda optional |

## Data flow (high level)

```mermaid
flowchart LR
  Input[Topic / Brief] --> Script[Script generation]
  Script --> Review[Optional review]
  Review --> Media[Media pipeline]
  Media --> Export[Platform export]
```

### Slideshow mode (3-scene)

```mermaid
flowchart LR
  topic[Topic] --> sw[SceneScriptWriter]
  sw --> scenes["scenes x3"]
  scenes --> dalle[DALL-E3 slides]
  scenes --> tts[PerScene TTS]
  dalle --> remotion[Remotion]
  tts --> remotion
```

Entry: `python orchestrator_mvp.py "topic" --mode slideshow`. Prompts: `docs/prompts/`. Image cuts align to `scene_timestamps`; default `caption_mode=none` (typography baked into slides). Use `--caption-mode sentence` for per-sentence overlay captions timed via TTS word boundaries.

## Related

- Technical spec: [ai-shorts-engine-spec.md](ai-shorts-engine-spec.md)
- Product spec: [../domain/content-learning-system.md](../domain/content-learning-system.md)
- ADRs: [../adr/README.md](../adr/README.md) (see [0002 project editability](../adr/0002-project-file-editability.md))
- Agent workflow: [../workflow/agentic-workflow.md](../workflow/agentic-workflow.md)
