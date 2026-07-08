# Remotion renderer

Main video compositor for this project ([ADR 0003](../docs/adr/0003-remotion-render-and-editor.md)). Reads `project.json` / `pipeline_payload.json` props from Python and renders 9:16 MP4 with captions, optional b-roll images, and narration audio.

## Ubuntu 20.04 deploy branch

This branch (`chore/remotion-ubuntu-2004`) pins **Remotion 4.0.150** and **React 18** so the Linux compositor targets **glibc 2.31** (Ubuntu 20.04). The `main` branch uses newer Remotion and needs **Ubuntu 22.04+** (glibc 2.35).

On the server, install from the lockfile exactly:

```bash
cd remotion
rm -rf node_modules
npm ci
```

Verify glibc before rendering:

```bash
ldd --version   # expect 2.31 on Ubuntu 20.04
```

Full pipeline smoke test:

```bash
cd ..
source .venv/bin/activate
python orchestrator_mvp.py "test topic" --image-provider mock
```

Pass: `output/final/final.mp4` exists with no `GLIBC_2.3x not found` errors.

If render still fails, try older pins in `package.json` (one at a time): `4.0.100`, then `4.0.94`. If all fail, upgrade the server to Ubuntu 22.04+ and use `main`.

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
