# Remotion renderer

Main video compositor for this project ([ADR 0003](../docs/adr/0003-remotion-render-and-editor.md)). Reads `project.json` / `pipeline_payload.json` props from Python and renders 9:16 MP4 with captions, optional b-roll images, and narration audio.

## Setup

```bash
cd remotion
npm install
```

Requires **Node.js 18+** and **ffmpeg** on PATH (used by Remotion during export).

## Commands

| Action | Command |
|--------|---------|
| Preview in Studio | `npm run studio` |
| Render via npm | `npm run render -- ../output/caption_preview.mp4 --props=../output/.props.json` |
| Render from Python | `python core/remotion_render_stage.py output/pipeline_payload.json` |
| Caption preview alias | `python core/caption_render_stage.py output/pipeline_payload.json` |

Python builds props from the project file (tokens, themes, audio path, `video.images[]`) and invokes `npx remotion render`.

## Composition

- **Entry:** `src/index.ts`
- **Composition id:** `ShortVideo`
- **Props schema:** `src/types.ts` — mirrored by `core/remotion_render_stage.project_to_remotion_props()`

## Stack split

| Layer | Location |
|-------|----------|
| Generation (LLM, TTS, b-roll download) | Python `core/` |
| Project state | `project.json` |
| Video preview + export | This package |
