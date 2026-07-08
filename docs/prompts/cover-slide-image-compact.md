# Cover slide image (compact) — Nhân Tướng VN

Essential art direction for ChatGPT images — shorter than full template, richer than Pollinations. Scene-specific variables are appended as a **suffix block** (block 2) for API prefix caching.

---

## Static prompt (block 1)

```
Create a premium vertical 9:16 illustration for a TikTok educational slideshow about Vietnamese Physiognomy (Nhân Tướng Học).

Luxury editorial digital painting. Semi-realistic. Fine brushwork. Soft golden-hour cinematic light. Museum-quality Vietnamese philosophy aesthetic. Elegant, minimal, highly readable on mobile.

DO NOT create: anime, cartoon, comic, 3D CGI, photorealistic photo, flat vector, low-detail art.

Mood: wisdom, serenity, timeless East Asian philosophy, quiet confidence, traditional Vietnamese cultural identity.

Color palette: warm ivory, soft cream, muted gold, earth brown, deep burgundy (#7b0100). Avoid neon, pure black, oversaturated colors.

Composition (critical):
- Aspect ratio 9:16
- Reserve TOP 70–75% for typography — clean, uncluttered, no overlapping objects
- Lower 25–30%: symbolic storytelling scene supporting the title message
- Large negative space; eyes guided upward toward title

Scene style: peaceful mountains, misty valley, ink wash, bamboo, lotus, scholar study, traditional Vietnamese architecture — symbolic, not literal stock scenery.

Typography hierarchy:
1. Large title — very large, elegant, Vietnamese calligraphy-inspired, dark burgundy or deep brown, subtle golden rim light, centered, high contrast
2. Small description — premium serif, dark brown, max 4–6 short lines, comfortable spacing

On-image text must relate to the scene variables below — same idea and tone, may rephrase for layout. Fluent natural Vietnamese. Do not contradict the message.

Negative: Chinese/Japanese/Korean characters, English text, watermarks, logos, busy cluttered layout, fantasy dragons, AI artifacts, blurry image, objects overlapping typography.

Ultra detailed. Premium cinematic atmosphere. Scroll-stopping cover quality for smartphone viewing.
```

---

## Scene variables suffix (block 2 — appended last for prompt caching)

```
--------------------------------------------------
SCENE VARIABLES (apply last)
--------------------------------------------------

Topic context (symbolic scene — do not render as literal text):
{{TOPIC}}

Reference title for on-image typography (Vietnamese — may rephrase for layout):
{{TITLE}}

Reference description for on-image typography (may shorten):
{{DESCRIPTION}}
```
