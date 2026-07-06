"""Font resolver — map theme font names to OpenType file paths for MoviePy TextClip."""

from __future__ import annotations

import re
import sys
from pathlib import Path

# MoviePy 2 / Pillow require a path to a .ttf/.otf file, not a bare display name.
_WINDOWS_FONTS = Path("C:/Windows/Fonts")
_REGISTRY_KEY = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"

_registry_cache: list[tuple[str, Path]] | None = None


def _normalize_font_label(name: str) -> str:
    """Normalize a font label for comparison (lowercase, spaces, no style suffix noise)."""
    cleaned = re.sub(r"\s*\([^)]*\)\s*", " ", name)
    cleaned = cleaned.replace("-", " ").replace("_", " ")
    return " ".join(cleaned.lower().split())


def _load_windows_registry_fonts() -> list[tuple[str, Path]]:
    """Read Windows font display names and filenames from the registry (cached).

    Goal: Use OS-provided font names instead of a hand-maintained alias table.
    Params: None.
    Output: List of (display_name, absolute .ttf/.otf path) pairs.
    """
    global _registry_cache
    if _registry_cache is not None:
        return _registry_cache

    import winreg

    entries: list[tuple[str, Path]] = []
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _REGISTRY_KEY) as key:
        count = winreg.QueryInfoKey(key)[1]
        for index in range(count):
            display_name, filename, _ = winreg.EnumValue(key, index)
            if not isinstance(filename, str):
                continue
            path = _WINDOWS_FONTS / filename
            if path.is_file() and path.suffix.lower() in {".ttf", ".otf", ".ttc"}:
                entries.append((display_name, path))

    _registry_cache = entries
    return entries


def _resolve_from_windows_fonts_dir(font: str) -> Path | None:
    """Try resolving font as a filename inside C:/Windows/Fonts.

    Goal: Support theme values like arialbd.ttf without extra mapping.
    Params: font — filename or stem (e.g. arialbd.ttf, impact).
    Output: Path if a matching file exists, else None.
    """
    name = font.strip()
    candidates = [name]
    if not name.lower().endswith((".ttf", ".otf", ".ttc")):
        candidates.extend([f"{name}.ttf", f"{name}.otf", f"{name}.TTF"])

    for candidate in candidates:
        path = _WINDOWS_FONTS / candidate
        if path.is_file():
            return path

    stem = Path(name).stem.lower()
    for path in _WINDOWS_FONTS.iterdir():
        if path.suffix.lower() in {".ttf", ".otf", ".ttc"} and path.stem.lower() == stem:
            return path

    return None


def _resolve_from_windows_registry(font: str) -> Path | None:
    """Match a human font name against the Windows fonts registry.

    Goal: Resolve names like Arial Bold or Impact using OS metadata.
    Params: font — display-style name from theme_styles.json or project override.
    Output: Path to matching font file, or None if no match.
    """
    query = _normalize_font_label(font)
    if not query:
        return None

    prefix_path: Path | None = None
    prefix_label_len: int | None = None

    for display_name, path in _load_windows_registry_fonts():
        label = _normalize_font_label(display_name)
        if label == query:
            return path
        if label.startswith(query) or query.startswith(label):
            if prefix_label_len is None or len(label) < prefix_label_len:
                prefix_path = path
                prefix_label_len = len(label)

    return prefix_path


def resolve_font_path(font: str) -> str:
    """Resolve a theme font name or path to an OpenType file usable by TextClip.

    Goal: Avoid MoviePy 2 'cannot open resource' errors without maintaining alias tables.
    Params: font — .ttf/.otf path, Fonts-folder filename, or Windows display name
        (e.g. Arial Bold, Impact, arialbd.ttf).
    Output: Absolute path string to an existing font file.
    """
    if not font or not str(font).strip():
        raise ValueError("Font name must not be empty.")

    candidate = Path(font)
    if candidate.is_file():
        return str(candidate.resolve())

    if sys.platform == "win32":
        from_dir = _resolve_from_windows_fonts_dir(font)
        if from_dir is not None:
            return str(from_dir)

        from_registry = _resolve_from_windows_registry(font)
        if from_registry is not None:
            return str(from_registry)

    raise ValueError(
        f"Font not found: {font!r}. Use a .ttf/.otf path, a filename under "
        f"C:\\Windows\\Fonts (e.g. arialbd.ttf), or a Windows font display name "
        f"(e.g. Arial Bold)."
    )
