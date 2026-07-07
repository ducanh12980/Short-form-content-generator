# Ambient overlay library

Looping video overlays composited above slideshow images (below captions) during Remotion export. The pipeline picks **one overlay at random** per video (like background music).

## Current clips

| File | Effect | Source |
|------|--------|--------|
| `fire/smoke_fire_sparks.webm` | Fire / sparks | Vecteezy — "Loop of smoke fire sparks rising up particle" (id 7525563) |
| `snow/snow_storm.webm` | Snow storm | Vecteezy — "Snow storm element on black loop" (id 11393613) |
| `lights/gold_particles.webm` | Gold particles / bokeh | Vecteezy — "Abstract motion background shining gold particles" (id 4747801) |

**License:** Vecteezy free license — verify attribution requirements at [vecteezy.com](https://www.vecteezy.com/).

**Compositor:** black/dark background + CSS `mix-blend-mode: screen` in Remotion. Default opacity: fire **0.40**, snow **0.45** (playback **0.5×**), lights **0.42**.

## Adding overlays

1. Place WebM (VP9, yuv420p) under `fire/`, `snow/`, `lights/`, etc.
2. Register in `manifest.json` with `effect`, `tags`, `opacity_default`, `blend_mode`, `duration_ms`.
3. Override library path with `OVERLAYS_DIR` in `.env`.

```bash
ffmpeg -i input.mp4 -c:v libvpx-vp9 -pix_fmt yuv420p -b:v 2M -an output.webm
```
