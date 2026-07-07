# Bookend slide image — intro / ending (title + hero visual)

Prompt for **intro and ending** slide images. Same luxury series look as content slides, but layout is:

- **Top:** large title typography only (same hierarchy as content slides)
- **Lower ~55–65%:** one **striking hero visual** — no description paragraph, no body text

**Inputs:** `{{TITLE}}`, `{{VISUAL_CONCEPT}}`, `{{TOPIC}}`, `{{SLIDE_ROLE}}` (`intro` or `ending`)

---

## Image generation prompt

```
Create a brand-new premium vertical illustration for a TikTok educational slideshow about Vietnamese Physiognomy (Nhân Tướng VN).

This is the {{SLIDE_ROLE}} slide of the video. It has **title typography at the top only** — there is **no description text block** on this slide.

Topic context (symbolism for the hero visual — do not render as literal paragraph text):
{{TOPIC}}

--------------------------------------------------
ART DIRECTION
--------------------------------------------------

Museum-quality digital painting. Luxury editorial illustration. Semi-realistic. Fine painterly brushwork. Soft cinematic golden-hour atmosphere. Premium Vietnamese philosophy aesthetic.

DO NOT create: anime, cartoon, comic, 3D CGI, photorealistic photo, flat vector, low-detail art.

--------------------------------------------------
MOOD
--------------------------------------------------

Wisdom, serenity, timeless East Asian philosophy, quiet confidence, traditional Vietnamese cultural identity.

{{SLIDE_ROLE}} slide tone:
- intro: hook the viewer instantly — bold, intriguing, sets the series tone
- ending: reflective close — warm, memorable, gentle sense of completion

--------------------------------------------------
COLOR & LIGHTING
--------------------------------------------------

Warm ivory, soft cream, muted gold, earth brown, deep burgundy (#7b0100). Golden hour light. Avoid neon, pure black, oversaturated colors.

--------------------------------------------------
COMPOSITION (CRITICAL)
--------------------------------------------------

Aspect ratio: 9:16

**Upper ~30–35%:** reserved for **title typography only**. Clean, uncluttered. No objects overlapping the title.

**Lower ~55–65%:** a **single striking hero visual** that directly illustrates the topic and visual concept below. This area should be cinematic, bold, and scroll-stopping — the main visual focus of the slide.

**No description paragraph.** No subtitle block. No bullet text. No secondary body copy anywhere on the image.

The hero visual must feel directly connected to {{TOPIC}} — not generic stock scenery.

--------------------------------------------------
HERO VISUAL (lower area — paint this, do not write it as text)
--------------------------------------------------

Visual concept from script writer:

{{VISUAL_CONCEPT}}

Make the scene specific, vivid, and memorable. Strong focal point. Dramatic but elegant. Symbolic elements from Vietnamese philosophy and physiognomy when relevant.

--------------------------------------------------
TITLE TYPOGRAPHY (upper area only)
--------------------------------------------------

Render exactly one large title — same luxury editorial style as other slides in the series:

Reference title (Vietnamese — may rephrase slightly for layout):

{{TITLE}}

Style: very large, elegant, Vietnamese calligraphy-inspired, dark burgundy or deep brown, subtle golden rim light, centered, high contrast, excellent mobile readability.

--------------------------------------------------
NEGATIVE PROMPT
--------------------------------------------------

DO NOT generate:

Description paragraph or subtitle block
Body text below the title
Chinese / Japanese / Korean characters
English text (except none expected)
Watermarks, logos, QR codes
Busy cluttered layout
Objects overlapping the title
Fantasy dragons / magic
AI artifacts, blurry image

--------------------------------------------------
QUALITY
--------------------------------------------------

Ultra detailed. Scroll-stopping hero visual. Perfect title hierarchy. Premium cinematic atmosphere. Designed for TikTok on a smartphone.
```

---

## Variables

| Variable | Source | Notes |
|----------|--------|-------|
| `{{TITLE}}` | Script writer → intro/ending `title` | On-image headline only |
| `{{VISUAL_CONCEPT}}` | Script writer → intro/ending `visual_concept` | Drives hero visual — never rendered as text |
| `{{TOPIC}}` | User topic brief | Direct correlation for symbolism |
| `{{SLIDE_ROLE}}` | `intro` or `ending` | Slight tone shift in mood section |
