"""Is Ripple itself sitting in a folder something is syncing to the cloud?

Ripple Offline keeps everything beside the executable -- the chosen folder, the
SQL dialect, the saved history, the log. That is deliberate: deleting the folder
really does remove Ripple, and copying the folder to another machine takes the
settings and the history with it.

It has one consequence worth saying out loud. Everyone in this office has
OneDrive sync switched on, so the folder Ripple is copied into is very likely a
folder OneDrive uploads. Two things follow, and neither is obvious:

* The saved history is a database file. A sync client holds a file open while it
  uploads it, and it copies files whenever it likes. A save can fail because of
  that, and a database copied mid-write can come back damaged.
* Everything in the folder goes up to the company's cloud -- the whole program,
  not just the settings. That is a decision somebody should make on purpose
  rather than discover afterwards.

Neither is a reason to stop. Both are a reason to say so.
"""
from __future__ import annotations

import os
from pathlib import Path

# The environment variables OneDrive sets to the root of each sync folder. This
# is the reliable signal: it comes from OneDrive itself rather than from a
# folder happening to be called something.
_ONEDRIVE_VARS = ("OneDrive", "OneDriveCommercial", "OneDriveConsumer")

# Fallbacks, for a machine where those are not set and for the other clients
# people have. Matched against whole folder names, never as substrings, so a
# folder called "dropbox-migration-notes" is not mistaken for Dropbox.
_KNOWN_CLIENTS = {
    "onedrive": "OneDrive",
    "dropbox": "Dropbox",
    "google drive": "Google Drive",
    "googledrive": "Google Drive",
    "my drive": "Google Drive",
    "box": "Box",
    "icloackdrive": "iCloud Drive",
    "icloud drive": "iCloud Drive",
}


def _roots() -> list[tuple[Path, str]]:
    out: list[tuple[Path, str]] = []
    for var in _ONEDRIVE_VARS:
        raw = os.environ.get(var, "").strip()
        if raw:
            out.append((Path(raw), "OneDrive"))
    return out


def _named_client(folder: Path) -> str:
    """The sync client whose folder this is inside, judged by folder name."""
    for part in folder.parts:
        name = part.strip().lower()
        if name in _KNOWN_CLIENTS:
            return _KNOWN_CLIENTS[name]
        # "OneDrive - Contoso Ltd" is how a work account names its root.
        if name.startswith("onedrive - ") or name.startswith("onedrive-"):
            return "OneDrive"
    return ""


def detect(folder: Path | str) -> dict:
    """What is syncing this folder, if anything, and what that means here.

    Returns a plain dict rather than raising or logging, because the only thing
    that is ever done with it is putting it on the screen.
    """
    try:
        folder = Path(folder).resolve()
    except OSError:                                   # pragma: no cover - defensive
        return {"synced": False, "client": "", "root": ""}

    for root, client in _roots():
        try:
            resolved = root.resolve()
        except OSError:                               # pragma: no cover - defensive
            continue
        if folder == resolved or resolved in folder.parents:
            return {"synced": True, "client": client, "root": str(resolved)}

    client = _named_client(folder)
    if client:
        return {"synced": True, "client": client, "root": ""}
    return {"synced": False, "client": "", "root": ""}
