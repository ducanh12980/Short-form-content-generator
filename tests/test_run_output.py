"""Tests for core/run_output.py."""

from __future__ import annotations

import re
from pathlib import Path

from core.run_output import (
    GENERATIONS_BASE,
    new_generation_run_dir,
    new_run_dir,
    resolve_generation_output_dir,
)


def test_new_generation_run_dir_under_generations_base() -> None:
    path = new_generation_run_dir()
    assert path.parent == GENERATIONS_BASE
    assert re.fullmatch(r"\d{8}_\d{6}", path.name)


def test_new_run_dir_custom_base(tmp_path: Path) -> None:
    base = tmp_path / "custom"
    path = new_run_dir(base)
    assert path.parent == base


def test_resolve_generation_output_dir_explicit() -> None:
    assert resolve_generation_output_dir("my/run") == Path("my/run")


def test_resolve_generation_output_dir_env(monkeypatch) -> None:
    monkeypatch.setenv("OUTPUT_DIR", "from/env")
    path = resolve_generation_output_dir()
    assert path.parent == Path("from/env")
    assert re.fullmatch(r"\d{8}_\d{6}", path.name)


def test_resolve_generation_output_dir_timestamp_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("OUTPUT_DIR", raising=False)
    path = resolve_generation_output_dir()
    assert path.parent == GENERATIONS_BASE
    assert len(path.name) == len("20260706_143742")
