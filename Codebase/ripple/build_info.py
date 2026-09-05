"""Which build of Ripple is this one?

Nothing on any screen said. "It does not work" has more than once turned out to
be "that was fixed a while ago, on a copy that was never installed", and there
was no way at all to tell those two apart without reading the code.

So: one line, on the settings screen and in ``/api/health``, saying which build
is running.

Where the answer came from matters as much as the answer, and the two are never
allowed to look the same. A commit hash read out of git is a fact. The date of
the newest file in the folder is a guess -- it moves when anything is touched,
and it says nothing about whether that change was ever installed anywhere. So
each is labelled for what it is, and a guess always says so out loud.

Four places to look, best first:

* a stamp file written into the packaged folder at build time -- the only thing
  that can tell one copy of the executable from another, because an executable
  has no git and no source dates worth reading;
* the host's own environment, which is how Vercel says which commit it deployed;
* git, but ONLY when git actually tracks the files this copy is made of -- a
  folder copied into a repository inherits its .git by accident, and reporting
  that repository's commit is a confident answer about a copy nobody can check;
* the dates on its own files, which is a guess, and says so.
"""
from __future__ import annotations

import os
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# The one version number, and the only place it is written down. The build
# script reads it from here to name what it produces, so the filename, the
# release tag and the line on the settings screen can never disagree.
#
# Bump it whenever behaviour changes. Three parts: break.feature.fix.
VERSION = "1.9.1"

# Written into the packaged folder by the offline build script. Kept as a
# constant because two files have to agree on the name.
STAMP_FILE = "BUILD-STAMP.json"

_PKG = Path(__file__).resolve().parent          # .../Codebase/ripple
_ROOT = _PKG.parent                             # .../Codebase

_cached: dict | None = None


def _places_to_look() -> list[Path]:
    """Folders a stamp file could be sitting in."""
    out = [_PKG, _ROOT]
    if getattr(sys, "frozen", False):
        out.append(Path(sys.executable).resolve().parent)
        bundled = getattr(sys, "_MEIPASS", "")
        if bundled:
            out.append(Path(bundled))
    return out


def _from_stamp_file() -> dict | None:
    for folder in _places_to_look():
        f = folder / STAMP_FILE
        try:
            if not f.is_file():
                continue
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, dict) and data.get("built"):
            return {
                "commit": str(data.get("commit") or ""),
                "built": str(data["built"]),
                "from": "build",
            }
    return None


def _from_env() -> dict | None:
    """How a host says which commit it deployed. Vercel sets the first of these."""
    sha = os.environ.get("VERCEL_GIT_COMMIT_SHA") or os.environ.get("RIPPLE_BUILD_COMMIT")
    if not sha:
        return None
    return {
        "commit": sha[:7],
        "built": os.environ.get("RIPPLE_BUILD_DATE", ""),
        "from": "host",
    }


def _git_tracks(pkg: Path) -> bool:
    """Is this copy the working tree git knows, or a folder sitting inside one?

    A folder copied into a repository, or copied next to one, inherits its
    ``.git`` by accident. Ripple's own kit-shaped folder is exactly that: a
    generated copy of the engine, git-ignored, living inside the repository it
    was copied out of. Checking only for a ``.git`` nearby, it read that
    repository's HEAD off the disk beside it and printed the commit as its own
    build -- a confident, checkable-sounding answer about a copy git has never
    seen. Carry that folder onto a machine where some unrelated repository
    happens to be a level up and the answer is not even close.

    So the question is not "is there a ``.git`` nearby" but "does git track the
    files this copy is made of". If it does not, there is no commit to claim and
    the file dates below say so out loud.
    """
    try:
        done = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "build_info.py"],
            cwd=str(pkg), capture_output=True, text=True, timeout=5,
        )
    except Exception:
        return False
    return done.returncode == 0


def _from_git() -> dict | None:
    """The commit this working copy is actually on."""
    if not any((p / ".git").exists() for p in (_ROOT, _ROOT.parent)):
        return None
    if not _git_tracks(_PKG):
        return None
    try:
        done = subprocess.run(
            ["git", "log", "-1", "--format=%h|%cI"],
            cwd=str(_ROOT), capture_output=True, text=True, timeout=5,
        )
    except Exception:
        return None
    if done.returncode != 0 or "|" not in done.stdout:
        return None
    commit, when = done.stdout.strip().split("|", 1)
    commit = commit.strip()
    # A commit hash is only the truth about this copy if nothing has been edited
    # since. Left unmarked, a build made from a working copy with changes in it
    # claims to be the commit it is not, which is the exact confusion this whole
    # file exists to remove.
    if _has_edits():
        commit += "+edits"
    return {"commit": commit, "built": when.strip(), "from": "git"}


def _has_edits() -> bool:
    """Has anything been changed since that commit?"""
    try:
        done = subprocess.run(["git", "status", "--porcelain"],
                              cwd=str(_ROOT), capture_output=True, text=True, timeout=5)
    except Exception:
        return False
    return done.returncode == 0 and bool(done.stdout.strip())


def _from_file_dates() -> dict:
    """The newest of Ripple's own files. A guess, and labelled as one."""
    newest = 0.0
    folders = [(_PKG, "*.py"), (_ROOT / "web", "*")]
    for folder, pattern in folders:
        if not folder.is_dir():
            continue
        for f in folder.rglob(pattern):
            if "__pycache__" in f.parts or not f.is_file():
                continue
            try:
                newest = max(newest, f.stat().st_mtime)
            except OSError:
                continue
    when = datetime.fromtimestamp(newest).isoformat(timespec="seconds") if newest else ""
    return {"commit": "", "built": when, "from": "files"}


def _day(iso: str) -> str:
    """A date somebody can read, out of whatever shape the stamp is in."""
    if not iso:
        return ""
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%d %b %Y")
    except ValueError:
        return iso[:10]


def _label(info: dict) -> str:
    """The one line the screen shows. Says plainly when it is a guess."""
    bits = [f"Version {info['version']}"]
    if info["commit"]:
        bits.append(info["commit"])
    day = _day(info["built"])
    if info["from"] == "files":
        bits.append(f"newest file {day}" if day else "no build date")
        bits.append("no build record — this is a guess")
    elif day:
        bits.append(f"built {day}")
    return " · ".join(bits)


def build_info() -> dict:
    """Which build this is. Worked out once and kept -- it cannot change while
    the program is running, and ``/api/health`` is asked on every screen."""
    global _cached
    if _cached is None:
        found = _from_stamp_file() or _from_env() or _from_git() or _from_file_dates()
        info = {"version": VERSION, **found}
        info["label"] = _label(info)
        _cached = info
    return dict(_cached)


def write_stamp(folder: Path, commit: str = "", built: str = "") -> Path:
    """Record which build this is, into a folder being packaged.

    Called by the offline build script. Without it the executable falls back to
    file dates, which in a packaged folder are the dates the files were copied
    -- true, useless, and indistinguishable from a real build date.
    """
    if not built:
        built = datetime.now().astimezone().isoformat(timespec="seconds")
    if not commit:
        found = _from_git()
        commit = found["commit"] if found else ""
    out = folder / STAMP_FILE
    out.write_text(
        json.dumps({"version": VERSION, "commit": commit, "built": built}, indent=2),
        encoding="utf-8",
    )
    return out
