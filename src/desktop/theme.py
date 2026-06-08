"""Stylesheet loading, accent-colour swapping, and live QSS hot-reload.

Refs: [BL B-109, B-110, B-111]
"""
from __future__ import annotations

import os
from typing import Optional

from src.desktop.styles import load_stylesheet, stylesheet_path

# Loaded once at import time; re-loaded by the hot-reload watcher when edited.
DARK_STYLESHEET: str = load_stylesheet("dark")
LIGHT_STYLESHEET: str = load_stylesheet("light")

_QSS_WATCHER: Optional["QFileSystemWatcher"] = None

ACCENT_COLORS: dict[str, str] = {
    "purple": "#bd93f9",
    "pink":   "#ff79c6",
    "cyan":   "#8be9fd",
    "green":  "#50fa7b",
    "orange": "#ffb86c",
}


def _stylesheet_with_accent(theme: str, accent: str) -> str:
    """Return the QSS for *theme* with the purple accent token swapped."""
    base = DARK_STYLESHEET if theme == "dark" else LIGHT_STYLESHEET
    hex_value = ACCENT_COLORS.get((accent or "purple").lower(), ACCENT_COLORS["purple"])
    if hex_value.lower() == "#bd93f9":
        return base
    return base.replace("#bd93f9", hex_value)


def _install_qss_hotreload(app: "QApplication", theme: str, accent: str = "purple") -> None:
    """Install a QFileSystemWatcher that re-applies the QSS file on save.

    Safe to call repeatedly; the watcher is cached at module scope.  Skipped
    silently if QFileSystemWatcher is unavailable (e.g. headless test env).
    """
    global _QSS_WATCHER
    try:
        from PySide6.QtCore import QFileSystemWatcher
    except ImportError:  # pragma: no cover
        return
    if _QSS_WATCHER is None:
        _QSS_WATCHER = QFileSystemWatcher()

        def _on_changed(path: str) -> None:
            global DARK_STYLESHEET, LIGHT_STYLESHEET  # noqa: PLW0603
            DARK_STYLESHEET = load_stylesheet("dark")
            LIGHT_STYLESHEET = load_stylesheet("light")
            current = "dark" if "PyDracula dark" in app.styleSheet() else "light"
            app.setStyleSheet(_stylesheet_with_accent(current, accent))
            if path not in _QSS_WATCHER.files():
                _QSS_WATCHER.addPath(path)

        _QSS_WATCHER.fileChanged.connect(_on_changed)

    for t in ("dark", "light"):
        p = str(stylesheet_path(t))
        if p not in _QSS_WATCHER.files():
            _QSS_WATCHER.addPath(p)


def apply_theme(
    app: "QApplication",
    theme: str,
    font_size: int = 12,
    font_family: str = "",
    accent: str = "purple",
) -> None:
    """Apply theme stylesheet, font family, and font size to *app*.  [B-109–B-111]"""
    app.setStyleSheet(_stylesheet_with_accent(theme, accent))
    font = app.font()
    if font_family:
        font.setFamily(font_family)
    font.setPointSize(font_size)
    app.setFont(font)
    try:
        for w in app.allWidgets():
            w.setFont(font)
    except Exception:  # pragma: no cover
        pass
    if os.environ.get("ASTRANOTES_QSS_HOTRELOAD") == "1":
        _install_qss_hotreload(app, theme, accent)
