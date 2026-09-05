"""Which copy of Ripple is this one.

Without an answer to that on screen, "it does not work" cannot be told apart
from "that was fixed a while ago, on a copy nobody installed", and those two
need completely different conversations.

ONE version number lives here and nothing anywhere else in Ripple writes one.
The packaged folder's name, the zip handed to somebody, and the line on the
settings screen all read it from here.

The commit and the build time are worked out by trying four things in order and
taking the first that answers, recording in "from" which one did:

  1. stamp         a BUILD-STAMP.json sitting beside the code
  2. environment   the machine that built it set the values there
  3. git           but ONLY where git tracks the files this copy is made of
  4. file dates    the newest date on Ripple's own source files

Step 3 is the one that goes wrong, and it goes wrong silently. The obvious test
is "is there a .git folder nearby". Do it that way and any copy of Ripple that
happens to sit inside somebody's repository picks up that repository's latest
commit and prints it as its own build, with nothing on screen hedging. Measured
on this build on 27 August 2026: a copy generated into the parent folder, which
git had never seen, printed a real commit hash and a real date. So ask git
whether it knows THESE files - git ls-files --error-unmatch build_info.py, run
inside the folder holding it - and where nothing is tracked, claim no commit at
all and fall through to the file dates, which say out loud that they are a guess.

A wrong answer that looks checkable is worse than an honest guess. That is the
whole reason this file exists.
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any

# The number itself. Raise it whenever behaviour changes.
VERSION = "1.5.0"

STAMP_NAME = "BUILD-STAMP.json"

_HERE = Path(__file__).resolve().parent

# Worked out once and remembered: the git calls below are subprocesses, and the
# health route is asked for this on every page load.
_LOCK = Lock()
_INFO: dict[str, str] | None = None

# git is asked four short questions and none of them should ever hang the health
# route; a repository on a network drive can be slow enough to matter.
_GIT_TIMEOUT_SECONDS = 5


def _pretty(when: str) -> str:
    """A date a person reads: 23 Aug 2026.

    Built without %d so a single-digit day is not printed as 05, and without the
    platform-only %-d and %#d, which differ between Windows and everything else.
    """
    text = str(when or "").strip()
    if not text:
        return "an unknown date"
    try:
        moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        # Something wrote a date this file does not recognise. Print it as it was
        # written rather than swallow it - a strange date on screen is a question
        # somebody can ask, a blank one is not.
        return text
    return "{day} {rest}".format(day=moment.day, rest=moment.strftime("%b %Y"))


def _label(commit: str, built: str, source: str) -> str:
    """The one line the settings screen prints, put together here.

    Here rather than in the screen, so the browser and the double-clickable
    program print it identically.
    """
    line = "Version " + VERSION
    if commit:
        line += " - " + commit
    line += " - built " + _pretty(built)
    if source == "file dates":
        # A file date moves whenever anything is touched and proves nothing about
        # what was installed, so the line says so rather than reading as a fact.
        line += " - date taken from the files on disk, not from a recorded build"
    elif not commit:
        line += " - no commit recorded"
    return line


def _read_stamp(path: Path) -> dict[str, str] | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None
    commit = str(raw.get("commit", "") or "")
    built = str(raw.get("built", "") or "")
    if not commit and not built:
        return None
    # The version is NOT read back from the stamp. One version number lives in
    # this file; a stale stamp must not be able to rename the build.
    return {"commit": commit, "built": built}


def _from_stamp() -> dict[str, str] | None:
    """A BUILD-STAMP.json written into a packaged folder at build time."""
    for folder in (_HERE, _HERE.parent):
        found = _read_stamp(folder / STAMP_NAME)
        if found is not None:
            return found
    return None


def _from_environment() -> dict[str, str] | None:
    """The machine that built this copy left the values in the environment."""
    commit = ""
    for name in ("RIPPLE_COMMIT", "VERCEL_GIT_COMMIT_SHA", "GITHUB_SHA"):
        value = os.environ.get(name, "").strip()
        if value:
            commit = value
            break
    built = ""
    for name in ("RIPPLE_BUILT", "RIPPLE_BUILD_TIME"):
        value = os.environ.get(name, "").strip()
        if value:
            built = value
            break
    if not commit and not built:
        return None
    return {"commit": commit, "built": built}


def _git(args: list[str]) -> tuple[bool, str]:
    """Ask git one question, from inside the folder holding this file.

    Returns whether git answered at all, and what it said. The two are separate
    because "git status printed nothing" means the working copy is clean, and
    "git is not installed" also prints nothing.
    """
    try:
        finished = subprocess.run(
            ["git", *args],
            cwd=str(_HERE),
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return False, ""
    if finished.returncode != 0:
        return False, ""
    return True, finished.stdout.strip()


def _from_git() -> dict[str, str] | None:
    """git, but only where git tracks the files this copy is made of."""
    tracked, _ = _git(["ls-files", "--error-unmatch", Path(__file__).name])
    if not tracked:
        # git knows nothing about this copy. Any repository sitting above it on
        # disk is somebody else's, and its commit is not ours to print.
        return None
    answered, commit = _git(["rev-parse", "--short", "HEAD"])
    if not answered or not commit:
        return None
    _, built = _git(["log", "-1", "--format=%cI"])
    clean, changes = _git(["status", "--porcelain"])
    if clean and changes.strip():
        # Marked in the commit itself, because the commit is the thing somebody
        # would otherwise paste into a bug report as though it were a build.
        commit = commit + " (uncommitted edits)"
    return {"commit": commit, "built": built}


def _newest_source_date() -> str:
    """The newest date on Ripple's own Python files."""
    newest = 0.0
    try:
        for found in _HERE.rglob("*.py"):
            try:
                stamp = found.stat().st_mtime
            except OSError:
                continue
            if stamp > newest:
                newest = stamp
    except OSError:
        newest = 0.0
    if newest <= 0.0:
        # Something is very wrong with the folder. Now is still an answer, and an
        # answer is what this step exists to guarantee.
        return datetime.now().isoformat(timespec="seconds")
    return datetime.fromtimestamp(newest).isoformat(timespec="seconds")


def _from_file_dates() -> dict[str, str]:
    """The step that always answers, so the screen can never be blank.

    No commit at all: there is nothing here to claim one from, and a made-up one
    is exactly what this whole file is written to prevent.
    """
    return {"commit": "", "built": _newest_source_date()}


def build_info() -> dict[str, str]:
    """version, commit, built, from, label. Worked out once and remembered."""
    global _INFO
    with _LOCK:
        if _INFO is not None:
            return dict(_INFO)

        found: dict[str, str] | None = None
        source = ""
        for name, step in (
            ("stamp", _from_stamp),
            ("environment", _from_environment),
            ("git", _from_git),
        ):
            found = step()
            if found is not None:
                source = name
                break
        if found is None:
            found = _from_file_dates()
            source = "file dates"

        built = found.get("built", "")
        if not built:
            # A stamp or an environment that recorded a commit but no time. The
            # commit is what "from" is about, so it keeps its source, and the
            # date falls back to the files rather than printing nothing.
            built = _newest_source_date()

        info = {
            "version": VERSION,
            "commit": found.get("commit", ""),
            "built": built,
            "from": source,
            "label": _label(found.get("commit", ""), built, source),
        }
        _INFO = info
        return dict(info)


def write_stamp(folder: str | Path) -> Path:
    """Write BUILD-STAMP.json into a folder, for a copy prepared for somebody.

    "built" is the moment this copy was prepared, which is what somebody holding
    the copy wants to know. The commit is whatever this build could honestly
    claim - empty where it could claim none, so the copy hedges too.
    """
    target = Path(folder)
    target.mkdir(parents=True, exist_ok=True)
    info = build_info()
    body: dict[str, Any] = {
        "version": VERSION,
        "commit": info["commit"],
        "built": datetime.now().isoformat(timespec="seconds"),
    }
    stamp = target / STAMP_NAME
    stamp.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    return stamp
