"""Load prompt templates from docs/prompts markdown files."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

DOCS_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "docs" / "prompts"

_FENCED_BLOCK_RE = re.compile(r"```(?:\w*\n)?(.*?)```", re.DOTALL)


@lru_cache(maxsize=32)
def _read_prompt_markdown(path_str: str) -> str:
    path = Path(path_str)
    if not path.is_file():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8")


def load_fenced_prompt(
    markdown_path: str | Path,
    *,
    block_index: int = 0,
    heading: str | None = None,
) -> str:
    """Extract a fenced code block from a prompt markdown file.

    Params: markdown_path — path to .md under docs/prompts; block_index — which
        ``` block to return (0 = static prefix, 1 = variable suffix for image prompts);
        heading — optional section hint (unused; reserved for multi-block files).
    Output: Prompt text inside the selected fenced block.
    """
    path = Path(markdown_path)
    content = _read_prompt_markdown(str(path.resolve()))
    blocks = _FENCED_BLOCK_RE.findall(content)
    if not blocks:
        raise ValueError(f"No fenced prompt block in {path}")
    if block_index < 0 or block_index >= len(blocks):
        raise ValueError(
            f"Prompt block index {block_index} out of range for {path} "
            f"({len(blocks)} block(s))"
        )

    prompt = blocks[block_index].strip()
    if heading and heading.lower() not in content.lower():
        pass  # heading is documentary only for now
    return prompt


def substitute_prompt(template: str, variables: dict[str, str]) -> str:
    """Replace {{KEY}} placeholders in a prompt template."""
    result = template
    for key, value in variables.items():
        result = result.replace(f"{{{{{key}}}}}", value)
    return result
