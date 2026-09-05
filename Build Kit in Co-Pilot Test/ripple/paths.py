from __future__ import annotations

"""Where things live, running either way.

Ripple runs two ways: as ``python run.py`` from a folder of source files, and
later as a single packaged program with no source folder around it. The two
layouts disagree about every path, and the disagreement never raises - it just
finds an empty folder and carries on. So the guessing is done here, once, and
nothing else in Ripple works out a path for itself.
"""

import sys
from pathlib import Path


def frozen() -> bool:
    """True when running as the packaged program."""
    # The packager sets sys.frozen on the interpreter it builds in. It is
    # absent from an ordinary interpreter, hence getattr rather than sys.frozen.
    return bool(getattr(sys, "frozen", False))


def app_dir() -> Path:
    """The folder a person actually sees."""
    if frozen():
        # The folder holding the .exe, not the temporary unpack folder: this is
        # where a person can find, back up or delete their own files.
        return Path(sys.executable).resolve().parent
    # ripple/paths.py -> ripple/ -> the project root. This is the only place in
    # Ripple allowed to walk up from __file__; see web_dir for what happens
    # when anywhere else does it.
    return Path(__file__).resolve().parent.parent


def web_dir() -> Path:
    """Where index.html, styles.css and app.js are."""
    if frozen():
        # The packager unpacks bundled files to a folder of its own choosing
        # and records it in sys._MEIPASS. Walking up from __file__ instead
        # lands somewhere real but empty: every route still answers, the
        # browser shows a blank white page, and that reads as broken code
        # rather than as a folder that moved.
        base = getattr(sys, "_MEIPASS", "")
        if base:
            return Path(base) / "web"
        # A packager that sets sys.frozen but not _MEIPASS keeps the bundled
        # files beside the .exe. Falling back is better than returning a path
        # built from the literal string "None".
        return app_dir() / "web"
    return app_dir() / "web"


def data_dir() -> Path:
    """Where the history database goes, created if it is missing."""
    # app_dir() both ways, never beside the code. Packaged, beside-the-code is
    # inside the program's own internals: rebuilding destroys every saved
    # analysis, zipping the folder up to send to somebody sends the saved
    # analyses with it, and a read-only location fails the save silently.
    folder = app_dir()
    folder.mkdir(parents=True, exist_ok=True)
    return folder
