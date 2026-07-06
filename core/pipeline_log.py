"""Console logging for pipeline stage completion."""

from __future__ import annotations


def log_step_done(step: str, detail: str = "") -> None:
    """Print a single line when a pipeline step (or sub-step) completes."""
    if detail:
        print(f"[PIPELINE] ✓ {step} — {detail}")
    else:
        print(f"[PIPELINE] ✓ {step}")
