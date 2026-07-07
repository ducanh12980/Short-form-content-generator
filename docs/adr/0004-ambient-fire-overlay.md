# ADR 0004: Ambient fire overlay via video loop + random picker

## Status

Accepted (amended — LLM selector removed)

## Context

Slideshow videos use Ken Burns motion on still images but can feel static. We want a lightweight ambient layer (fire/sparks) that makes backgrounds feel alive without distracting from captions.

Options considered:

1. **Procedural particles** in Remotion (canvas/SVG) — no assets, fully deterministic, but more code and harder to match cinematic quality.
2. **Pre-rendered video loops** with `mix-blend-mode: screen` on black — reuses stock footage, fast to ship, matches CapCut-style overlays.
3. **LLM on/off selection** vs **random pick** — LLM was deferred; random picker matches the existing `music_picker` pattern and keeps the pipeline simple.

## Decision

- Store **curated WebM loops** in `assets/overlays/` (Vecteezy welding sparks on black, compressed).
- Composite in Remotion with **`AmbientOverlay`** at z-index 50, **`screen` blend**, default opacity **0.40**.
- **`attach_random_ambient_overlay()`** picks a random manifest entry per run (like `attach_random_music()`).
- Schema field: `video.ambient` in `pipeline_payload.json`, mapped to Remotion props in `project_to_remotion_props()`.

## Consequences

- **Positive:** Minimal Remotion code; easy to add more manifest entries later (lights, snow).
- **Positive:** No extra LLM call; predictable pipeline cost and latency.
- **Negative:** Repo includes ~1–2 MB WebM per overlay; more assets increase clone size.
- **Negative:** Black-background clips rely on `screen` blend — not true alpha; wrong blend looks muddy.
- **Follow-up:** Additional effect types via `manifest.json`; optional CSV column for batch overrides.

## References

- [docs/ambient-fire-overlay.md](../ambient-fire-overlay.md)
- [assets/overlays/README.md](../../assets/overlays/README.md)
