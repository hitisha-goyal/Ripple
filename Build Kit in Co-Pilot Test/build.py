"""Package Ripple as a Windows program with PyInstaller.

Run with:  python build.py

This script only packages. It does not edit any other file: ripple/paths.py
already answers where the front end and the database live when running
packaged, and run.py already hands uvicorn the app object rather than the
string "ripple.api:app". If either of those was skipped, fix it there. A
packaged build papers over neither, and both fail silently rather than loudly.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# Every path here is absolute and derived from this file rather than from the
# current working folder. PyInstaller resolves relative paths against its own
# working folder, and a relative "web" stops the build with "Unable to find
# ... web", which reads as a missing folder rather than as a wrong path.
ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
DIST = ROOT / "dist"
APP_DIR = DIST / "Ripple"
EXE = APP_DIR / "Ripple.exe"
BUNDLED_WEB = APP_DIR / "_internal" / "web"
BUNDLED_INDEX = BUNDLED_WEB / "index.html"
STAMP = APP_DIR / "BUILD-STAMP.json"

# The three keys the running program looks for. A key called "date" instead of
# "built" makes the settings screen find nothing and fall back to guessing from
# file dates, which only record when the files were copied.
STAMP_KEYS = ("version", "commit", "built")

# Anything that looks like the saved-history database. The name is decided in
# ripple/store.py and ripple/paths.py, so this checks by extension rather than
# by hard-coding a name here that could drift out of step with them.
DATABASE_SUFFIXES = (".db", ".sqlite", ".sqlite3")

# PyInstaller prints thousands of lines. The reason for a failure is almost
# always at the very bottom, so only the bottom is worth showing.
TAIL_LINES = 40


@dataclass
class Check:
    """One thing build.py confirms about its own output.

    PyInstaller's exit code says the packaging tool finished, not that the
    program it produced is correct, so each of these is checked by looking.
    """

    name: str
    passed: bool
    detail: str = ""


@dataclass
class BuildInfo:
    """What was read out of ripple/build_info.py."""

    version: str
    write_stamp: Callable[..., object]
    notes: list[str] = field(default_factory=list)


def say(message: str = "") -> None:
    """Print immediately.

    PyInstaller's own output is captured rather than streamed, so without
    flushing these lines can arrive after it, in the wrong order.
    """
    print(message, flush=True)


def load_build_info() -> BuildInfo:
    """Read VERSION and write_stamp() out of ripple/build_info.py.

    Read before the build starts, not after: a missing version is a two-second
    failure, and finding it out after ninety seconds of packaging wastes them.
    """
    # Running "python build.py" from the project root already puts the root on
    # the path, but running it by full path from somewhere else does not.
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    try:
        from ripple import build_info  # noqa: PLC0415  (deliberately late)
    except ImportError as problem:
        raise SystemExit(
            "Could not read ripple/build_info.py, so this build has no version "
            "number to name itself after.\n"
            f"  Python said: {problem}\n"
            "  Run this from the project root, the folder holding run.py."
        ) from problem

    version = getattr(build_info, "VERSION", None)
    if not isinstance(version, str) or not version.strip():
        raise SystemExit(
            "ripple/build_info.py does not give a VERSION string, so the zip "
            "would have no version in its name and nobody could tell which "
            "build they downloaded."
        )

    write_stamp = getattr(build_info, "write_stamp", None)
    if not callable(write_stamp):
        raise SystemExit(
            "ripple/build_info.py does not give a write_stamp function, so the "
            "packaged folder would carry no record of which build it is."
        )

    return BuildInfo(version=version.strip(), write_stamp=write_stamp)


def saved_databases() -> list[Path]:
    """Any non-empty history database sitting in the folder about to be deleted.

    Once the packaged program has been run, the analyses it saved live inside
    dist/Ripple. Rebuilding deletes that folder, so they go with it.
    """
    if not APP_DIR.exists():
        return []

    found: list[Path] = []
    for item in sorted(APP_DIR.rglob("*")):
        if not item.is_file():
            continue
        if item.suffix.lower() not in DATABASE_SUFFIXES:
            continue
        try:
            size = item.stat().st_size
        except OSError:
            # Unreadable is not the same as absent. Treat it as something worth
            # asking about rather than quietly walking past it.
            found.append(item)
            continue
        if size > 0:
            found.append(item)
    return found


def confirm_deleting(databases: list[Path]) -> bool:
    """Ask before destroying saved analyses. Silence counts as no."""
    say("")
    say("Rebuilding deletes dist/Ripple, and there is saved history inside it:")
    for item in databases:
        try:
            size = item.stat().st_size
        except OSError:
            say(f"  {item}  (size could not be read)")
            continue
        say(f"  {item}  ({size:,} bytes)")
    say("")
    say("Those saved analyses will be gone. Nothing copies them out.")
    try:
        answer = input("Type yes to delete them and carry on: ")
    except EOFError:
        # No one is there to answer, so the cautious reading wins.
        say("")
        say("Nothing was typed, so nothing was deleted and no build was made.")
        return False
    return answer.strip().lower() == "yes"


def tail_of(text: str, lines: int = TAIL_LINES) -> str:
    """The last part of a very long message, where the real reason usually is."""
    kept = [line for line in text.splitlines() if line.strip()]
    return "\n".join(kept[-lines:])


def locked_folder_advice() -> str:
    """Plain words for WinError 32, which says none of this itself."""
    return (
        "Windows would not let the old dist/Ripple folder be deleted, because "
        "something is sitting in it.\n"
        "  Usually one of these:\n"
        "    the packaged Ripple.exe from the last build is still running "
        "(close its window),\n"
        "    a terminal or an Explorer window has dist/Ripple as its current "
        "folder (move it somewhere else),\n"
        "    an antivirus scan is holding a file open (wait a few seconds and "
        "run this again).\n"
        "  Nothing is wrong with the build itself. Free the folder and rerun "
        "python build.py."
    )


def run_pyinstaller() -> subprocess.CompletedProcess[str]:
    """Run the packaging tool with the arguments this program needs.

    Every argument below is here because leaving it out produces a program that
    builds cleanly and then misbehaves:
      --onedir     a one-file build unpacks itself into a temporary folder on
                   every launch, which is slow, and a locked-down Windows
                   machine often refuses to run a program from there at all
      --console    leaves a plain window open showing the address, and showing
                   the error if there is one
      --add-data   the front end is read off disk at run time, so it has to be
                   carried along; WEB is absolute for the reason recorded above
      --collect-all  sqlglot and extract_msg both load parts of themselves by
                   name at run time, which PyInstaller cannot see by reading the
                   code, so without this they are silently left out and the
                   program fails the first time it reads any SQL
    """
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "run.py",
        "--name",
        "Ripple",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--console",
        "--add-data",
        f"{WEB}{os.pathsep}web",
        "--collect-all",
        "sqlglot",
        "--collect-all",
        "extract_msg",
    ]
    say("Running PyInstaller. This takes about ninety seconds, and nothing")
    say("prints while it runs, because its output is kept back so that the")
    say("last part of it can be shown if it fails.")
    say("")
    return subprocess.run(
        command,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )


def check_exe() -> Check:
    """The program itself is there."""
    if EXE.is_file():
        return Check("The program is there", True, str(EXE))
    return Check(
        "The program is there",
        False,
        f"No Ripple.exe at {EXE}. PyInstaller reported success but produced no "
        "program at the expected path.",
    )


def check_stamp() -> Check:
    """The build stamp is beside the program and names a real date."""
    if not STAMP.is_file():
        return Check(
            "The build stamp is beside it",
            False,
            f"No BUILD-STAMP.json at {STAMP}. The packaged copy cannot tell "
            "anybody which build it is, and the settings screen falls back to "
            "a file date that only records when the files were copied.",
        )

    try:
        data = json.loads(STAMP.read_text(encoding="utf-8"))
    except (OSError, ValueError) as problem:
        return Check(
            "The build stamp is beside it",
            False,
            f"BUILD-STAMP.json could not be read: {problem}",
        )

    if not isinstance(data, dict):
        return Check(
            "The build stamp is beside it",
            False,
            "BUILD-STAMP.json does not hold a set of named values.",
        )

    missing = [key for key in STAMP_KEYS if key not in data]
    if missing:
        return Check(
            "The build stamp is beside it",
            False,
            "BUILD-STAMP.json is missing " + ", ".join(missing) + ". The "
            "running program looks for exactly version, commit and built, and "
            "finds nothing if a key is named differently.",
        )

    built = data.get("built")
    if not isinstance(built, str) or not built.strip():
        return Check(
            "The build stamp is beside it",
            False,
            "BUILD-STAMP.json has a built key with nothing usable in it, so "
            "the packaged copy cannot say when it was made.",
        )

    text = built.strip()
    if text.endswith("Z"):
        # Python 3.10's fromisoformat cannot read a trailing Z, though 3.11 can.
        # Swapping it for the same thing written the long way keeps a perfectly
        # good stamp from being reported as an unreadable date.
        text = text[:-1] + "+00:00"

    try:
        when = datetime.fromisoformat(text)
    except ValueError:
        return Check(
            "The build stamp is beside it",
            False,
            f"BUILD-STAMP.json says it was built {built!r}, which this check "
            "cannot read as a date.",
        )

    detail = (
        f"Version {data.get('version')}, commit {data.get('commit')}, "
        f"built {when.isoformat(sep=' ')}."
    )
    extra = sorted(key for key in data if key not in STAMP_KEYS)
    if extra:
        detail += " It also holds " + ", ".join(extra) + "."
    return Check("The build stamp is beside it", True, detail)


def check_web() -> Check:
    """The front end came along, by finding index.html inside the bundle."""
    if BUNDLED_INDEX.is_file():
        return Check("The front end was bundled", True, str(BUNDLED_INDEX))
    return Check(
        "The front end was bundled",
        False,
        f"No index.html at {BUNDLED_INDEX}. The packaged program would start, "
        "look healthy, and show a blank page.",
    )


def folder_size_mb(folder: Path) -> float:
    """Total size of everything inside a folder, in MB."""
    total = 0
    for item in folder.rglob("*"):
        try:
            if item.is_file() and not item.is_symlink():
                total += item.stat().st_size
        except OSError:
            # A file that cannot be measured is left out of the total rather
            # than guessed at, so the number on screen is only what was counted.
            continue
    return total / (1024 * 1024)


def make_zip(version: str) -> Path:
    """Write dist/Ripple-v<version>.zip around the packaged folder.

    Named for the version so the zip, the release tag and the version on the
    settings screen are one thing that cannot disagree. A file called dist.zip
    is the same name for ever, so nobody can tell which build they downloaded.
    """
    base = DIST / f"Ripple-v{version}"
    made = shutil.make_archive(
        base_name=str(base),
        format="zip",
        root_dir=str(DIST),
        base_dir="Ripple",
    )
    return Path(made)


def main() -> int:
    say("Packaging Ripple")
    say(f"  project root : {ROOT}")

    if not (ROOT / "run.py").is_file():
        say("")
        say(f"There is no run.py in {ROOT}, so there is nothing to package.")
        say("Run this from the project root, the folder holding run.py.")
        return 1

    if not WEB.is_dir():
        say("")
        say(f"There is no web folder at {WEB}, so the packaged program would")
        say("start and show a blank page. Nothing was built.")
        return 1

    info = load_build_info()
    say(f"  version      : {info.version}  (from ripple/build_info.py)")
    say(f"  front end    : {WEB}")
    say(f"  output folder: {APP_DIR}")

    databases = saved_databases()
    if databases and not confirm_deleting(databases):
        say("Stopped. Nothing was deleted and nothing was built.")
        return 1

    say("")
    result = run_pyinstaller()
    output = (result.stdout or "") + "\n" + (result.stderr or "")

    if result.returncode != 0:
        say("PyInstaller failed. The last part of its output:")
        say("")
        say(tail_of(output))
        say("")
        if "WinError 32" in output or "being used by another process" in output:
            say(locked_folder_advice())
        return 1

    say("PyInstaller finished. Checking the result rather than trusting it.")
    say("")

    # The stamp is written before anything is checked or zipped, so that the
    # zip carries it and the check below is looking at the real thing.
    try:
        info.write_stamp(APP_DIR)
    except OSError as problem:
        if getattr(problem, "winerror", None) == 32:
            say(locked_folder_advice())
            return 1
        say(f"The build stamp could not be written: {problem}")
        return 1
    except TypeError as problem:
        say(
            "write_stamp() in ripple/build_info.py would not accept the "
            "packaged folder as its argument, so no build stamp was written."
        )
        say(f"  Python said: {problem}")
        return 1

    checks = [check_exe(), check_stamp(), check_web()]
    for check in checks:
        marker = "OK    " if check.passed else "FAILED"
        say(f"  {marker}  {check.name}")
        if check.detail:
            say(f"          {check.detail}")

    if not all(check.passed for check in checks):
        say("")
        say("The build produced something, but it is not right, so no zip was")
        say("made. Fix what is listed above and run python build.py again.")
        return 1

    say("")
    say(f"  size of dist/Ripple : {folder_size_mb(APP_DIR):.1f} MB")
    say(f"  the program         : {EXE}")

    try:
        archive = make_zip(info.version)
    except OSError as problem:
        if getattr(problem, "winerror", None) == 32:
            say("")
            say(locked_folder_advice())
            return 1
        say("")
        say(f"The zip could not be written: {problem}")
        return 1

    say(f"  the zip             : {archive}")
    say(f"  its size            : {archive.stat().st_size / (1024 * 1024):.1f} MB")

    say("")
    say("Done. What to do with it:")
    say(f"  Double-click {EXE} and walk one scan through it end to end. Every")
    say("  fault this phase can have fails quietly rather than loudly, so a")
    say("  program that starts is not yet a program that works.")
    say(f"  Do not commit the zip. dist/ is ignored on purpose: git keeps every")
    say("  version of every file for ever, and forty old builds become the")
    say("  whole repository, which every fresh clone then pays for.")
    say(f"  Publish {archive.name} to the releases page under the tag "
        f"v{info.version},")
    say("  and delete the previous zip there so only the newest one is kept.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# Later, once everything works: change "--console" in run_pyinstaller() to
# "--noconsole" for a cleaner program. It stops the plain black window opening
# beside the app. Leave it as --console until then, because that window is
# where the address is printed, and where an error appears if there is one.
