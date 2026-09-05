r"""Assemble a Ripple that can be carried onto a machine which installs nothing.

    ..\Codebase\.venv\Scripts\python tools\make_demo_snapshot.py

Writes D:\Apps\Ripple\RIPPLE COPILOT DEMO -- the engine, the wrapper, the
screens, the SQL parser and a pretend pipeline, in one folder that runs on
Python's own library alone.

WHY THIS EXISTS. The packaged build needs FastAPI to run and PyInstaller to
package, and both are installs. On a laptop that refuses installs neither is
reachable, so this leaves both behind: the web layer is rewritten on
http.server, and there is no .exe. What comes out is started with
``python run.py``.

WHAT IT DOES NOT DO. It does not touch the product. Everything it copies is
copied unchanged, and the eight files that cannot be copied from the product --
the web layer, the launcher, the engine finder, the smoke test, the batch file
and the instructions -- are kept in ``demo_files`` beside this script, in git,
and laid down on top each time this runs.

WHERE THE EIGHT OWNED FILES LIVE, AND WHY THAT MOVED. They used to live only
inside the output folder, and this script read them into memory, deleted the
folder, and wrote them back at the end. That worked until the delete failed
half way -- a command prompt left sitting inside the folder is enough -- and
then the files were already gone from the disk and the process that was holding
the only other copy had died with them. There was no second copy anywhere. Eight
files nobody could write again, ended by one open window. So they live in git
now, this script reads them from there, and the output folder is only ever
output. Deleting the output folder costs one re-run.

THE SNAPSHOT IS A FORK, DELIBERATELY, AND ONLY THIS ONCE. The product keeps ONE
engine and never copies it, because two copies drift and the fork is always the
one running where nobody can check it. A folder carried to another machine has
nothing to reach back to, so it carries its own. That is why the OUTPUT is
git-ignored, why it says so on its own settings screen, and why the way to move
it forward is to run this again rather than to edit anything inside it.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(r"D:\Apps\Ripple")
CODE = ROOT / "Codebase"
OFF = ROOT / "Ripple Offline"
DEMO = ROOT / "RIPPLE COPILOT DEMO"
# The eight files the snapshot owns, kept in git beside this script.
OWNED_SRC = OFF / "demo_files"

# The engine, exactly as it ships. ai.py, api.py and scanner/github.py are left
# out: all three reach the network, and none of them is on any path this build
# can take.
ENGINE = ["__init__.py", "build_info.py", "catalog.py", "config.py", "narrative.py",
          "notification.py", "production.py", "progress.py", "providers.py", "store.py"]
SCANNER = ["__init__.py", "dialectcompat.py", "lineage.py", "repo.py", "rescue.py",
           "sqlread.py", "templating.py"]
# The offline wrapper. app.py is rewritten by hand (FastAPI to http.server) and
# webbuild.py is only needed on the machine that assembles this.
# __init__.py and engine.py are NOT here. The product's pair points the import
# path at Codebase, which is right for the product and wrong for a folder that
# has been carried somewhere. The snapshot keeps its own, in OWNED.
WRAPPER = ["folderpick.py", "lifecycle.py", "nonet.py", "paths.py", "prefs.py",
           "synced.py"]

# Everything the product cannot give this folder. Written on top at the end of
# every run, read from git, never read back out of the output folder.
#
# The engine finder is the dangerous one. The PRODUCT's version puts Codebase on
# the import path, which is right for the product and wrong for a folder carried
# somewhere else. Let the product's copy win here and everything still works on
# THIS machine, because Codebase is next door, and every test passes -- it fails
# only on the laptop the folder was made for.
OWNED = ["ripple_offline/__init__.py", "ripple_offline/engine.py",
         "ripple_offline/app.py", "ripple_offline/webserver.py",
         "run.py", "HOW-TO-RUN-THIS.md", "tests/test_smoke.py",
         "START RIPPLE.bat"]


def check_sources_first() -> list[Path]:
    """Read the eight owned files BEFORE anything is deleted.

    A missing one has to stop this script while the output folder is still
    whole. Carry on regardless and what comes out is a folder with no launcher,
    no web layer or no engine finder -- broken in a way that prints no error and
    is only discovered on the laptop it was carried to.
    """
    missing = [n for n in OWNED if not (OWNED_SRC / n).is_file()]
    if missing:
        print("Stopping, and nothing has been touched.\n")
        print(f"These files are missing from {OWNED_SRC}:")
        for n in missing:
            print(f"  {n}")
        print("\nThey cannot be copied from the product -- they are the snapshot's")
        print("own. Restore them from git before running this again.")
        raise SystemExit(1)
    return [OWNED_SRC / n for n in OWNED]


def fresh(p: Path) -> None:
    """Empty the folder, keeping the folder itself.

    Removing the folder outright fails with 'used by another process' whenever
    anything is sitting in it -- a command prompt, an editor, a file browser --
    and on Windows that failure lands AFTER the contents are already gone.
    Emptying it instead succeeds in every one of those cases.
    """
    p.mkdir(parents=True, exist_ok=True)
    for child in p.iterdir():
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()


def main() -> None:
    sources = check_sources_first()

    fresh(DEMO)
    (DEMO / "ripple" / "scanner").mkdir(parents=True)
    (DEMO / "ripple_offline").mkdir()
    (DEMO / "tests").mkdir()

    for n in ENGINE:
        shutil.copy2(CODE / "ripple" / n, DEMO / "ripple" / n)
    for n in SCANNER:
        shutil.copy2(CODE / "ripple" / "scanner" / n, DEMO / "ripple" / "scanner" / n)
    for n in WRAPPER:
        shutil.copy2(OFF / "ripple_offline" / n, DEMO / "ripple_offline" / n)
    print(f"engine   : {len(ENGINE) + len(SCANNER)} files")
    print(f"wrapper  : {len(WRAPPER)} files")

    # The SQL parser, as a plain folder. Pure Python, no compiled parts, so it
    # travels by being copied -- which is the whole point on a machine where
    # nothing can be installed.
    src = CODE / ".venv" / "Lib" / "site-packages" / "sqlglot"
    shutil.copytree(src, DEMO / "sqlglot",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    n = len(list((DEMO / "sqlglot").rglob("*.py")))
    mb = sum(f.stat().st_size for f in (DEMO / "sqlglot").rglob("*")) / 1_000_000
    print(f"sqlglot  : {n} files, {mb:.1f} MB")

    # The front end, generated from the shared one the same way the real build
    # does it, so the screens here are the screens there.
    sys.path.insert(0, str(OFF))
    from ripple_offline import webbuild                       # noqa: PLC0415
    webbuild.build(out_dir=DEMO / "web")
    print(f"web      : {len(list((DEMO / 'web').rglob('*')))} files")

    shutil.copytree(CODE / "mockrepo", DEMO / "mockrepo",
                    ignore=shutil.ignore_patterns("__pycache__"))
    print(f"mockrepo : {len(list((DEMO / 'mockrepo').rglob('*.sql')))} .sql files to scan")

    for name, path in zip(OWNED, sources):
        out = DEMO / name
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, out)
    print(f"owned    : {len(OWNED)} files laid down from {OWNED_SRC.name}")

    total = len(list(DEMO.rglob("*.py"))) - n
    size = sum(f.stat().st_size for f in DEMO.rglob("*") if f.is_file()) / 1_000_000
    print(f"\nPython files a person has to have (sqlglot not counted): {total}")
    print(f"Folder to carry across: {size:.1f} MB")


main()
