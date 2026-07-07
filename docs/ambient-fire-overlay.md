# Ambient fire overlay

Looping **fire/sparks** video composited above slideshow images and below captions during Remotion export.

## Asset library

| Path | Purpose |
|------|---------|
| [`assets/overlays/`](../assets/overlays/) | Overlay WebM loops + `manifest.json` |
| [`assets/overlays/README.md`](../assets/overlays/README.md) | License and ingest notes |

Default clips: `fire/smoke_fire_sparks.webm`, `snow/snow_storm.webm`, and `lights/gold_particles.webm` (random per run). Dark background composites with CSS `mix-blend-mode: screen`.

Override library folder: `OVERLAYS_DIR` in `.env`.

## Pipeline behavior

During slideshow pipeline (`core/slideshow_pipeline.py`):

1. **Overlay picker** (`core/overlay_picker.py`) picks a **random** overlay from `assets/overlays/` (fire, snow, or lights today; like background music).
2. Stages the WebM into the run folder and writes `video.ambient` in `pipeline_payload.json`.
3. **Remotion** (`remotion/src/AmbientOverlay.tsx`) loops the overlay at z-index 50.

If the overlays folder is empty, the pipeline continues without an ambient layer.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OVERLAYS_DIR` | `assets/overlays` | Overlay library path |

## Opacity tuning

Default opacity: **0.40** (from manifest). Adjust in `assets/overlays/manifest.json` or per-run in `video.ambient.opacity`.

Preview in Remotion Studio:

```bash
cd remotion && npm run studio
```

Set `ambientOverlaySrc`, `ambientOpacity`, and `ambientBlendMode` in default props to preview.

## Manual test

Add to an existing `pipeline_payload.json`:

```json
"video": {
  "ambient": {
    "effect": "fire",
    "variant": "sparks",
    "path": "C:/path/to/run/smoke_fire_sparks.webm",
    "opacity": 0.4,
    "blend_mode": "screen",
    "duration_ms": 9830,
    "loop": true,
    "source": "manual"
  }
}
```

Copy `assets/overlays/fire/smoke_fire_sparks.webm` beside `narration.mp3`, then:

```bash
python core/remotion_render_stage.py output/generations/<run-id>/pipeline_payload.json
```

## Related

| Path | Role |
|------|------|
| `core/overlay_picker.py` | Random pick + stage overlay file |
| `remotion/src/AmbientOverlay.tsx` | Looping video layer |
| [`docs/stitch-cli.md`](stitch-cli.md) | Stitch / render stack |
