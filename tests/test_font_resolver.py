"""Tests for core/font_resolver.py."""

from __future__ import annotations

import sys

import pytest

from core.font_resolver import resolve_font_path


def test_resolve_font_path_accepts_existing_file(tmp_path) -> None:
    font_file = tmp_path / "custom.ttf"
    font_file.write_bytes(b"fake")
    assert resolve_font_path(str(font_file)) == str(font_file.resolve())


@pytest.mark.skipif(sys.platform != "win32", reason="Windows font resolution")
def test_resolve_font_path_by_filename_on_windows() -> None:
    path = resolve_font_path("arialbd.ttf")
    assert path.lower().endswith("arialbd.ttf")


@pytest.mark.skipif(sys.platform != "win32", reason="Windows font resolution")
def test_resolve_font_path_by_display_name_on_windows() -> None:
    path = resolve_font_path("Arial Bold")
    assert path.lower().endswith("arialbd.ttf")


@pytest.mark.skipif(sys.platform != "win32", reason="Windows font resolution")
def test_resolve_font_path_impact_on_windows() -> None:
    path = resolve_font_path("Impact")
    assert path.lower().endswith("impact.ttf")


@pytest.mark.skipif(sys.platform != "win32", reason="Windows font resolution")
def test_resolve_font_path_arial_prefix_prefers_shortest_label() -> None:
    path = resolve_font_path("Arial")
    assert path.lower().endswith("arial.ttf")


def test_resolve_font_path_unknown_raises() -> None:
    with pytest.raises(ValueError, match="Font not found"):
        resolve_font_path("TotallyFakeFontXYZ123")
