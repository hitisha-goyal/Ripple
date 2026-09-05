"""Make the folder a colleague copies onto the locked-down machine.

    python build.py

What comes out is ``dist/Ripple Offline``: an executable, the things it needs
beside it, and nothing to install. Copy that folder anywhere and double-click.

Two things are pulled in here rather than kept as copies, which is the whole
point of how this is put together:

* the analysis engine, from ``Codebase/ripple`` — one copy, so the offline
  build can never quietly fall behind the online one;
* the front end, built from ``Codebase/web`` with the parts that reach out
  deleted.

Both are read at build time. Neither exists as a second copy on disk.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from ripple_offline import webbuild                                  # noqa: E402
from ripple_offline.engine import SHARED_DIR, SHARED_ENGINE          # noqa: E402

# The one engine, again: the stamp writer lives beside the code it stamps.
sys.path.insert(0, str(SHARED_DIR.parent))
from ripple.build_info import VERSION, write_stamp                   # noqa: E402

APP_NAME = "Ripple Offline"
WORK = HERE / "build"
DIST = HERE / "dist"
# The download, named for the version inside it. It used to be a file called
# dist.zip committed straight into the repository, which meant two things: no
# download could ever be told apart from another, and git kept every 22 MB
# version of it for ever -- forty of them, which was the whole repository.
#
# It is written into dist/, which is not tracked, and published to the releases
# page instead. Only the latest one is kept.
ZIP = DIST / f"{APP_NAME.replace(' ', '-')}-v{VERSION}.zip"
WEB_OUT = WORK / "web"
ICON = HERE / "assets" / "ripple.ico"
SAMPLES = SHARED_DIR / "samples"


def say(message: str) -> None:
    print(f"  {message}", flush=True)


def folder_size(path: Path) -> str:
    total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    return f"{total / 1_000_000:.0f} MB"


IT_NOTE = """RIPPLE OFFLINE - what this program is, for whoever has to approve it
====================================================================

This is an internal tool for our own data engineering work. It reads a copy of
our pipeline code that is already on the machine and reports which production
tables an upstream change would break. It is not downloaded from anywhere and it
is not a commercial product.

It is unsigned. There is no code-signing certificate behind it, so Windows will
not recognise a publisher. That is the only reason it may be stopped.


WHAT IT DOES

  * Runs as the person who starts it. Its manifest asks Windows for
    "asInvoker" - it never requests administrator rights and cannot prompt for
    them. It has been run and tested end to end by a standard, non-administrator
    user.
  * Starts a small web server bound to 127.0.0.1 (this machine only) on the
    first free port from 8000 to 8020, and opens the default browser at it.
    It never listens on a network interface, so it cannot be reached by anyone
    else, on the network or otherwise.
  * Reads the folder of source code the user points it at. Read only. It never
    writes to that folder.


WHAT IT DOES NOT DO

  * No internet access of any kind. Outbound connections are blocked inside the
    program itself before anything else starts, and the components that could
    make one - the AI client and the repository downloader used by the online
    version, along with the HTTP library they need - are not packaged into this
    build at all. There is a screen inside the program that reports whether the
    block is active, and any attempt to reach out is refused and recorded.
  * No installer. Nothing is registered, no service is created, nothing is added
    to startup, and nothing is written to the registry.
  * Nothing is unpacked into the temporary folder. The program is a plain folder
    of files that runs where it sits.
  * No data leaves the machine. Nothing is uploaded and nothing is reported back
    to anyone. The source code it reads never goes anywhere.


WHAT IT WRITES, AND WHERE

  Only inside its own folder, and only these three files:

    ripple-settings.json    the code folder to scan, and the SQL dialect
    ripple-history.db       past analyses, so they are not lost
    ripple-log.txt          what it would have printed if it had a console

  Deleting the folder removes the program and everything it ever wrote.


IDENTIFYING IT

  File     : {name}
  Size     : {size:,} bytes
  SHA-256  : {digest}
  Built    : from source held in our own repository, using PyInstaller

  Rebuilding from the same source produces the same program but not a
  byte-identical file, so please allow by this hash and ask for a new one if the
  program is ever updated.


HOW TO CHECK THE NETWORK CLAIM YOURSELF

  Start the program and use it normally, then look at its connections in
  Resource Monitor (Network tab, filtered to this process), or run:

      netstat -ano | findstr <the process id>

  The only sockets it should ever have are a listener on 127.0.0.1 and the
  browser's own connections back to that same address. Any connection to a
  public address would be a defect and we want to know about it.

  Your own endpoint monitoring will show the same thing, and is better evidence
  than anything we can tell you.


IF THE ANSWER IS STILL NO

  We would rather hear that than have people work around it. Please tell us what
  would make it acceptable - a signed build, a different location, or reviewing
  the source, which is ours and can be read in full.
"""


def write_it_note(out: Path, exe: Path) -> Path:
    """A page to hand to whoever has to approve an unsigned program.

    An unsigned executable on a managed laptop is refused by policy, not by
    accident, and the person refusing it is asking a reasonable question. This
    answers it: what it is, what it touches, and the fingerprint to allow.
    """
    import hashlib

    digest = hashlib.sha256(exe.read_bytes()).hexdigest().upper()
    note = out / "READ-ME-FIRST-for-IT.txt"
    note.write_text(
        IT_NOTE.format(name=exe.name, size=exe.stat().st_size, digest=digest),
        encoding="utf-8")
    return note


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Ripple Offline for Windows.")
    parser.add_argument("--keep-work", action="store_true",
                        help="leave PyInstaller's working files behind, for debugging")
    args = parser.parse_args()

    print(f"\n  Building {APP_NAME}\n")

    if not (SHARED_ENGINE / "api.py").is_file():
        say(f"ERROR: the shared engine is not at {SHARED_ENGINE}.")
        say("Ripple Offline has no copy of its own on purpose. Nothing can be built without it.")
        return 1
    say(f"engine     : {SHARED_ENGINE}  (read, never copied)")

    # ── the front end, with everything that reaches out removed ────────────
    try:
        webbuild.build(out_dir=WEB_OUT)
    except webbuild.BuildError as exc:
        say("ERROR: the offline front end could not be built.")
        say(str(exc))
        return 1
    say(f"front end  : built from {SHARED_DIR / 'web'} into {WEB_OUT}")

    # ── the executable ─────────────────────────────────────────────────────
    if DIST.exists():
        shutil.rmtree(DIST, ignore_errors=True)
    if DIST.exists():
        # Windows will not delete a folder that something is sitting in: the
        # previous copy still running, or a command prompt whose current
        # directory is inside it. PyInstaller's own failure here is a wall of
        # traceback ending in "WinError 32", which says none of that.
        say(f"ERROR: {DIST} could not be cleared out.")
        say("Something is holding it open - usually the last build still running,")
        say("or a terminal sitting inside that folder. Close it and build again.")
        return 1
    command = [
        sys.executable, "-m", "PyInstaller",
        str(HERE / "run.py"),
        "--name", APP_NAME,
        "--noconfirm",
        "--clean",
        # A folder rather than one big file: it starts straight away instead of
        # unpacking itself into a temporary folder on every launch, and some
        # locked-down machines refuse to run programs out of one.
        "--onedir",
        # No console window. Nothing is lost -- everything it would have said
        # goes to ripple-log.txt beside the program.
        "--noconsole",
        # Where the shared engine is found at build time. This is the line that
        # keeps there being one copy of it.
        "--paths", str(SHARED_DIR),
        "--add-data", f"{WEB_OUT}{os.pathsep}web",
        "--collect-all", "sqlglot",
        "--collect-all", "extract_msg",
        "--distpath", str(DIST),
        "--workpath", str(WORK / "pyinstaller"),
        "--specpath", str(WORK),
    ]
    if ICON.is_file():
        command += ["--icon", str(ICON)]
    say("packaging  : PyInstaller (this takes a minute)")
    started = time.time()
    done = subprocess.run(command, capture_output=True, text=True)
    if done.returncode != 0:
        say("ERROR: PyInstaller failed.")
        print(done.stdout[-4000:])
        print(done.stderr[-4000:])
        return 1
    say(f"packaged   : in {time.time() - started:.0f} seconds")

    out = DIST / APP_NAME
    exe = out / f"{APP_NAME}.exe"
    if not exe.is_file():
        say(f"ERROR: PyInstaller reported success but {exe} is not there.")
        return 1

    # ── a couple of example notifications, so it can be tried immediately ──
    if SAMPLES.is_dir():
        target = out / "example-notifications"
        target.mkdir(exist_ok=True)
        for f in SAMPLES.glob("*.eml"):
            shutil.copyfile(f, target / f.name)
        say(f"examples   : {len(list(target.glob('*.eml')))} example emails to try it with")

    # ── which build this is ────────────────────────────────────────────────
    # Recorded here because nothing inside the packaged folder can work it out.
    # An executable has no git, and the file dates in there are the dates the
    # files were copied -- true, useless, and impossible to tell from a real
    # build date. Without this the settings screen falls back to a guess, and
    # "it does not work" goes on meaning "an old copy nobody replaced".
    stamp = write_stamp(out)
    say(f"stamp      : {stamp.name} - {json.loads(stamp.read_text())['commit'] or 'no commit'}")

    note = write_it_note(out, exe)
    say(f"for IT     : {note.name} - the page to send if the program is blocked")

    # ── the zip that gets handed to somebody ──────────────────────────────
    # Made here, every time, so the download can never disagree with the source
    # it was built from. It went four commits out of date once without anything
    # saying so, which is the worst possible state for a file whose whole job is
    # to BE the program: somebody unpacks it, gets a build from before the
    # fixes, and every answer it gives is one this code no longer gives.
    say(f"zip        : packing {ZIP.name}")
    # Anything a previous run of the program left in that folder goes into the
    # zip with it, and this zip is handed to other people. The settings file
    # names a real folder on a real machine and the history database holds real
    # analyses -- neither belongs in a download, and neither belongs to whoever
    # unpacks it either: they should start with nothing set.
    for leftover in ("ripple-settings.json", "ripple-history.db", "ripple-log.txt"):
        stray = out / leftover
        if stray.exists():
            stray.unlink()
            say(f"zip        : left out {leftover} from an earlier run")
    if ZIP.exists():
        ZIP.unlink()
    made = Path(shutil.make_archive(str(ZIP.with_suffix("")), "zip",
                                    root_dir=DIST, base_dir=APP_NAME))
    say(f"zip        : {made.name} - {made.stat().st_size / 1_000_000:.0f} MB")

    if not args.keep_work:
        shutil.rmtree(WORK / "pyinstaller", ignore_errors=True)

    print()
    say(f"Done. {folder_size(out)} in {out}")
    say(f"Copy that whole folder to the other machine and double-click {exe.name}.")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
