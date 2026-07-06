"""Load prompt templates from docs/prompts markdown files."""

from __future__ import annotations

import re
from pathlib import Path

DOCS_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "docs" / "prompts"


def load_fenced_prompt(markdown_path: str | Path, *, heading: str | None = None) -> str:
    """Extract the first fenced code block from a prompt markdown file.

    Params: markdown_path — path to .md under docs/prompts; heading — optional
        section hint (unused; reserved for multi-block files).
    Output: Prompt text inside the first ``` block.
    """
    path = Path(markdown_path)
    if not path.is_file():
        raise FileNotFoundError(f"Prompt file not found: {path}")

    content = path.read_text(encoding="utf-8")
    blocks = re.findall(r"```(?:\w*\n)?(.*?)```", content, re.DOTALL)
    if not blocks:
        raise ValueError(f"No fenced prompt block in {path}")

    prompt = blocks[0].strip()
    if heading and heading.lower() not in content.lower():
        pass  # heading is documentary only for now
    return prompt


def substitute_prompt(template: str, variables: dict[str, str]) -> str:
    """Replace {{KEY}} placeholders in a prompt template."""
    result = template
    for key, value in variables.items():
        result = result.replace(f"{{{{{key}}}}}", value)
    return result
