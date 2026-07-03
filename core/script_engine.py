"""Copywriting Module — AGENT 1 (The Creative Writer).

Passes a raw video topic to the LLM and returns high-retention hook + body script text.
"""

from __future__ import annotations

import json
import os
from typing import Any

from openai import OpenAI

AGENT_1_SYSTEM_PROMPT = """You are AGENT 1: The Creative Writer for short-form vertical video.

Write a high-retention script for a faceless TTS video (30–45 seconds when spoken).

Output JSON only with this schema:
{
  "hook": "0-3 second opening line — curiosity, shock stat, or pattern interrupt",
  "body": "2-3 conversational beats, natural spoken language, no stage directions",
  "full_text": "hook + body as one continuous narration string"
}

Rules:
- Hook must stand alone in the first 3 seconds.
- Body uses short sentences; no bullet markers in spoken text.
- No hashtags, emojis, or camera directions.
"""


def generate_script(
    topic: str,
    *,
    api_key: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """Generate hook and body script text from a video topic."""
    client = OpenAI(api_key=api_key or os.environ["OPENAI_API_KEY"])
    response = client.chat.completions.create(
        model=model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": AGENT_1_SYSTEM_PROMPT},
            {"role": "user", "content": f"Topic: {topic}"},
        ],
    )
    content = response.choices[0].message.content or "{}"
    script = json.loads(content)

    if "full_text" not in script:
        script["full_text"] = f"{script.get('hook', '').strip()} {script.get('body', '').strip()}".strip()

    return script
