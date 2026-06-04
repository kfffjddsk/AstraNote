"""QSS stylesheet loader for AstraNotes desktop UI.

Stylesheets live next to this module as ``dark.qss`` and ``light.qss`` so
designers can iterate on them without touching Python.  Use
:func:`load_stylesheet` to read one by theme name and
:func:`stylesheet_path` to get the file path (useful for ``QFileSystemWatcher``
hot-reloading during development).
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

_HERE = Path(__file__).resolve().parent
_ICONS_URL = _HERE.joinpath("icons").as_posix()  # forward-slash path for QSS url()

Theme = Literal["dark", "light"]


def stylesheet_path(theme: str) -> Path:
    """Return the on-disk path of the QSS file for *theme* (falls back to light)."""
    name = "dark.qss" if theme == "dark" else "light.qss"
    return _HERE / name


def load_stylesheet(theme: str) -> str:
    """Read the QSS file for *theme* and return its contents.

    The literal token ``{ICONS}`` in the QSS source is substituted with the
    absolute forward-slash path to the icon directory, so ``url({ICONS}/x.svg)``
    in the stylesheet resolves to a real file on disk regardless of the
    working directory.
    """
    path = stylesheet_path(theme)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    return raw.replace("{ICONS}", _ICONS_URL)
