"""Tests for core/run_output.py."""

from __future__ import annotations

import re
from pathlib import Path

from core.run_output import (
    DEFAULT_OUTPUT_BASE,
    FINAL_RUN_DIR_NAME,
    GENERATIONS_BASE,
    new_generation_run_dir,
    new_run_dir,
    prepare_default_run_dir,
    reset_run_dir,
    resolve_final_output_dir,
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


def test_resolve_final_output_dir_env(monkeypatch) -> None:
    monkeypatch.setenv("OUTPUT_DIR", "from/env")
    assert resolve_final_output_dir() == Path("from/env") / FINAL_RUN_DIR_NAME


def test_resolve_generation_output_dir_default_final(monkeypatch) -> None:
    monkeypatch.delenv("OUTPUT_DIR", raising=False)
    path = resolve_generation_output_dir()
    assert path == DEFAULT_OUTPUT_BASE / FINAL_RUN_DIR_NAME


def test_reset_run_dir_clears_existing(tmp_path: Path) -> None:
    run_dir = tmp_path / "final"
    run_dir.mkdir()
    stale = run_dir / "stale.mp4"
    stale.write_text("old", encoding="utf-8")

    reset_run_dir(run_dir)

    assert run_dir.is_dir()
    assert not stale.exists()


def test_prepare_default_run_dir_clears_final(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    final_dir = tmp_path / FINAL_RUN_DIR_NAME
    final_dir.mkdir()
    (final_dir / "old.mp4").write_text("old", encoding="utf-8")

    prepared = prepare_default_run_dir()

    assert prepared == final_dir.resolve()
    assert prepared.is_dir()
    assert not (prepared / "old.mp4").exists()
