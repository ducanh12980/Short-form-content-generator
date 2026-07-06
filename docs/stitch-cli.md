# Stitch CLI guide

Combine slide images, narration audio, and optional background music into a vertical **1080×1920** MP4 (TikTok / Reels / Shorts canvas).

Entry point: `stitch.py` → `core/stitch_stage.py` → Remotion `ShortVideo` composition.

## Prerequisites

```bash
python -m venv .venv
# Windows
.venv\Scripts\Activate.ps1
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
cd remotion && npm install && cd ..
```

You need **Python deps** (mutagen, etc.) and **Remotion** (`node` + `npm install` in `remotion/`).

## Quick start

```bash
python stitch.py \
  --images stitchTestData/1.jpg stitchTestData/2.jpg stitchTestData/3.jpg stitchTestData/4-slide.jpg \
  --audio stitchTestData/audio.mp3
```

With background music:

```bash
python stitch.py \
  --images stitchTestData/1.jpg stitchTestData/2.jpg stitchTestData/3.jpg stitchTestData/4-slide.jpg \
  --audio stitchTestData/audio.mp3 \
  --music stitchTestData/music.mp3 \
  --music-volume 0.25
```

## Command reference

```
python stitch.py --images IMG [IMG ...] --audio AUDIO [options]
```

| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `--images` | Yes | — | One or more image paths, in display order (JPG, PNG, WebP). |
| `--audio` | Yes | — | Narration / TTS track (MP3, WAV, M4A). **Sets total video length.** |
| `--music` | No | — | Background music (MP3, WAV, M4A). Mixed under narration. |
| `--music-volume` | No | `0.3` | Music level `0.0`–`1.0`. Narration stays at full volume. |
| `--output`, `-o` | No | `output/stitch/<timestamp>/stitch.mp4` | Output MP4 path. |
| `--fps` | No | `30` | Frame rate for the render. |

### Examples

**Custom output path**

```bash
python stitch.py --images a.jpg b.jpg --audio voice.mp3 -o output/my-video.mp4
```

**Single image (full audio duration)**

```bash
python stitch.py --images cover.jpg --audio voice.mp3
```

**Quieter bed music**

```bash
python stitch.py --images a.jpg b.jpg --audio voice.mp3 --music bed.mp3 --music-volume 0.15
```

## How slide timing works

Duration comes entirely from `--audio`. Images are split across that length:

| Slides | Timing |
|--------|--------|
| **1 image** | Fills the whole narration. |
| **2+ images** | First and last get **half** the time of middle slides (shorter opener/closer). |

For 4 images and 34 s audio, roughly: ~5.7 s → ~11.3 s → ~11.3 s → ~5.7 s.

Image order on the command line is the playback order.

## Audio mixing

- **Narration** (`--audio`): primary track, full volume, defines duration.
- **Music** (`--music`): secondary track at `--music-volume` (default 30%).
- Both are rendered together in Remotion. There is **no ducking** in stitch mode (music does not auto-dip under speech). Lower `--music-volume` if the bed competes with voice.

Music shorter than the video ends when the file ends. Music longer than the video is trimmed to match.

## Canvas size

Output is always **portrait 9:16**:

| | Value |
|--|-------|
| Width | `1080` |
| Height | `1920` |

Defined in `remotion/src/types.ts` (`CANVAS_WIDTH` / `CANVAS_HEIGHT`). If landscape dimensions are passed by mistake, they are auto-corrected before render.

Use **vertical source images** (9:16 or taller) for best results. Landscape photos are center-cropped to fill the frame.

## Output layout

Each run writes an isolated folder:

```
output/stitch/20260706_133443/
├── stitch.mp4          # final video
└── stitch_public/      # copied assets used by Remotion
    ├── audio.mp3
    ├── music.mp3       # if --music was passed
    ├── stitch_img_000.jpg
    ├── stitch_img_001.jpg
    └── ...
```

Timestamps in the folder name avoid overwriting previous runs.

## Visual effects (default)

Renders use `remotion/src/effects.tsx`:

| Phase | Effect |
|-------|--------|
| **Hold** | Ken Burns — slow center zoom in (1.0× → 1.08×). |
| **Exit** | Unified zoom out (~2 s ease-in → mirror reveal + blur). |
| **Enter** | Fast zoom back in on the next slide. |
| **Open** | Fast zoom in on the first slide. |

No captions are burned in during stitch (narration audio only). For captioned output, use the full orchestrator pipeline.

## Preview in Remotion Studio

To inspect the composition without a full stitch run:

```bash
cd remotion && npm run studio
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `Import error` / missing modules | `pip install -r requirements.txt` |
| Remotion / `npx` errors | `cd remotion && npm install` |
| `File not found` | Check paths; use quotes on Windows if paths have spaces. |
| `Could not read audio metadata` | Ensure the audio file is a valid MP3/WAV/M4A. |
| Music too loud | Lower `--music-volume` (try `0.15`–`0.25`). |
| Render is slow | Normal for Remotion; first run may compile bundles. |

## Related

| Path | Purpose |
|------|---------|
| `stitch.py` | CLI entry point |
| `core/stitch_stage.py` | Builds Remotion props, copies assets |
| `core/remotion_render_stage.py` | Invokes Remotion CLI |
| `remotion/src/effects.tsx` | Slide transitions and Ken Burns |
| `orchestrator_mvp.py` | Full pipeline (script → TTS → captions → video) |

## Shell completion (optional)

If `argcomplete` is installed, tab completion works for file paths:

```bash
pip install argcomplete
```
