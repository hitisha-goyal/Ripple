"""Where things are written on the machine Ripple is copied onto.

Everything Ripple keeps — the chosen folder, the SQL dialect, the saved history
— sits next to the executable, in the folder the user copied across. Nothing
goes into a hidden application-data folder, so deleting the folder really does
remove Ripple, and copying the folder to another machine takes the settings and
the history with it.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from .engine import OFFLINE_DIR, frozen

SETTINGS_NAME = "ripple-settings.json"
HISTORY_NAME = "ripple-history.db"


def app_dir() -> Path:
    """The folder a person actually sees: the one holding Ripple.exe.

    Running from source there is no executable, so the project folder stands in
    for it. Tests point RIPPLE_OFFLINE_HOME at a temporary folder so they never
    touch a real installation.
    """
    override = os.environ.get("RIPPLE_OFFLINE_HOME", "").strip()
    if override:
        return Path(override)
    if frozen():
        return Path(sys.executable).resolve().parent
    return OFFLINE_DIR


def settings_file() -> Path:
    return app_dir() / SETTINGS_NAME


def history_file() -> Path:
    return app_dir() / HISTORY_NAME


def web_dir() -> Path:
    """The offline front end.

    Built from the shared one rather than kept as a second copy — see
    ``webbuild.py``. In the executable it has already been built and bundled.
    """
    if frozen():
        return Path(getattr(sys, "_MEIPASS", ".")) / "web"
    return OFFLINE_DIR / "build" / "web"
