# Bookend slide image (compact) — intro / ending

Essential art direction for intro/ending slides. Variables appended last (block 2) for prefix caching on repeated calls.

---

## Static prompt (block 1)

```
Create a premium vertical 9:16 illustration for a TikTok educational slideshow about Vietnamese Physiognomy (Nhân Tướng VN).

Bookend slide layout: **title typography at the top only** — **no description paragraph** anywhere on the image.

Luxury editorial digital painting. Semi-realistic. Soft golden-hour light. Premium Vietnamese philosophy aesthetic.

DO NOT create: anime, cartoon, comic, 3D CGI, photorealistic photo, flat vector, low-detail art.

Mood: wisdom, serenity, timeless philosophy, traditional Vietnamese cultural identity.

Color: warm ivory, muted gold, earth brown, deep burgundy (#7b0100). Golden hour light. No neon or oversaturated colors.

Composition (critical):
- Aspect ratio 9:16
- Upper ~30–35%: title typography only — clean, uncluttered
- Lower ~55–65%: single striking hero visual — cinematic, bold, scroll-stopping focal point
- No subtitle, body text, or bullet copy

Title style: very large, elegant, Vietnamese calligraphy-inspired, dark burgundy or deep brown, subtle golden rim light, centered, excellent mobile readability.

Negative: description paragraph, body text below title, CJK characters, English text, watermarks, cluttered layout, objects overlapping title, fantasy magic, AI artifacts.

Ultra detailed. Premium cinematic atmosphere. Designed for TikTok on a smartphone.
```

---

## Bookend variables suffix (block 2)

```
--------------------------------------------------
BOOKEND VARIABLES (apply last)
--------------------------------------------------

Slide role: {{SLIDE_ROLE}}
- intro: hook instantly — bold, intriguing, sets series tone
- ending: reflective close — warm, memorable, gentle completion

Topic context (hero visual symbolism — do not render as paragraph text):
{{TOPIC}}

Visual concept (paint in lower area — do not write as text):
{{VISUAL_CONCEPT}}

Reference title for upper typography (Vietnamese — may rephrase for layout):
{{TITLE}}
```
