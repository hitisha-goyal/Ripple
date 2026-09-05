"""Finding the analysis engine, in a copy that has been carried somewhere.

The product itself keeps ONE engine and never copies it: the packaged build
reaches back into ``Codebase/ripple`` so the offline copy can never quietly fall
behind the online one. That rule is right, and it is why this file is the only
part of the wrapper that differs here.

This folder is a SNAPSHOT, made to be put on a memory stick and opened on a
machine that has never heard of the rest of the repository. There is nothing to
reach back to, so the engine sits inside this folder, next to this file, and is
imported from there.

Two consequences worth being plain about.

**This copy does not update itself.** It is the engine as it stood on the day the
snapshot was taken, and the version on the settings screen is that day's version.
To move it forward, take a fresh snapshot rather than editing anything in here --
an edited snapshot is a fork, and a fork on a locked-down laptop is the copy
nobody can check.

**Replacing this file with the product's own would look like it worked.** The
product's version puts ``Codebase`` on the import path, and on the machine the
snapshot was assembled on, Codebase is right there -- so everything runs, every
test passes, and the failure only happens on the laptop the folder was made for.
That is why the snapshot tool keeps this file rather than copying it.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
APP_DIR = HERE.parent                            # the folder holding run.py
LOCAL_ENGINE = APP_DIR / "ripple"
LOCAL_PARSER = APP_DIR / "sqlglot"

# The rest of the wrapper asks for this by name. Kept under the name it uses in
# the product, so paths.py, prefs.py and the others are unedited copies and can
# be refreshed from the repository without a thought.
OFFLINE_DIR = APP_DIR

MISSING = f"""
Ripple could not find its own engine.

It expects a folder called "ripple" beside run.py:
    {LOCAL_ENGINE}

Copy the whole Ripple folder again, in one piece. Copying only some of it is
the usual reason for this - the folder has to arrive complete.
"""

NO_PARSER = f"""
Ripple could not find the SQL parser.

It expects a folder called "sqlglot" beside run.py:
    {LOCAL_PARSER}

That folder is the one thing here that nobody can write for you, and it is why
the whole folder has to be copied in one piece rather than assembled file by
file. Copy it again from a machine that has it.
"""


def frozen() -> bool:
    """True when running as a built program rather than from these files."""
    return bool(getattr(sys, "frozen", False))


def ensure_engine_importable() -> Path | None:
    """Make ``import ripple`` and ``import sqlglot`` work from this folder.

    The folder is put FIRST on the import path on purpose. On a machine that
    happens to have another Ripple, or another sqlglot, installed, this copy has
    to be the one that runs -- otherwise the answer on screen came from code
    nobody in this folder can look at.
    """
    if frozen():
        return None                              # a build collected it already
    if not (LOCAL_ENGINE / "config.py").is_file():
        raise SystemExit(MISSING)
    if not (LOCAL_PARSER / "__init__.py").is_file():
        raise SystemExit(NO_PARSER)
    here = str(APP_DIR)
    if sys.path[:1] != [here]:
        if here in sys.path:
            sys.path.remove(here)
        sys.path.insert(0, here)
    return APP_DIR
