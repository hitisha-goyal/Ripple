# Running Ripple on the office laptop

This folder is a **working Ripple that installs nothing.** Copy it across,
double-click one file, and the browser opens on the real product — the same
screens, the same engine, the same answers as the copy on the home machine.

Read the next section before anything else. It corrects something you were told.

---

## About the `.exe` — you were told something that is not right

You were told the offline build kit gives you Python files and then, somehow, a
`Ripple.exe`. **It does not, and it cannot.**

Turning Python into a double-clickable `.exe` needs a tool called PyInstaller,
and PyInstaller is itself an install. On a laptop that refuses installs, it is
out of reach. There is no step you are missing.

That is not a problem, because there are two roads and **both of them end with
Ripple running.**

| | Road A — the `.exe` | Road B — this folder |
|---|---|---|
| What you copy across | one zip, about 29 MB | this folder, about 4 MB |
| Does the laptop need Python? | **No** | Yes, any 3.10 or newer |
| Does it install anything? | No | No |
| How you start it | double-click `Ripple Offline.exe` | double-click `START RIPPLE.bat` |
| Where the `.exe` came from | built on the home machine | there is no `.exe` |
| Best for | showing somebody, quickly | proving you could rebuild it there |

**Road A is easier and you already have it.** The `.exe` was built on the home
machine, where installing things is allowed, and then carried across. That is the
only way an `.exe` ever exists — it is never built on the locked-down laptop.
Download it from:

    https://github.com/aucksy/Ripple/releases/latest

**Road B is this folder**, and it is the one that answers the question "could I
have built this here?". Everything in it is either plain Python that a chat can
write, or one folder that has to be copied. Nothing is installed.

---

## What is in here

29 Python files of Ripple's own, and one folder that was copied rather than
written. (`mockrepo` holds two more, but those are pretend pipeline files to
scan, not part of Ripple.)

| Folder | What it is | Files |
|---|---|---|
| `ripple/` | The engine. Reads the repository, reads the SQL, follows the column, writes the summary. | 17 |
| `ripple_offline/` | The wrapper: the web service, the settings, the network guard, the Close button. | 10 |
| `web/` | The screens. JavaScript and CSS — **no Python builds the UI.** | 3 + fonts |
| `sqlglot/` | **The SQL parser. Copied, never written.** This is the one thing no chat can produce. | 183 |
| `mockrepo/` | A small pretend pipeline, so there is something to scan before you point it at real work. | 22 SQL files |
| `tests/` | One file that answers "does this work on this machine". | 1 |
| `run.py` | Starts it. | 1 |

**A note on the UI, because it is the usual surprise.** No Python file draws the
screens. Every screen, every card and every word on them is in `web/app.js`,
which is JavaScript. `web/styles.css` holds the colours and spacing. Python's
only job is to serve those files and hand them the numbers. If you ever want to
change something you can see, `web/app.js` is the file — the repair kit says the
same, under "Wording, layout or a card on any screen".

---

## The steps, on the office laptop

### 1. Check the laptop has Python

Open Command Prompt — press the Windows key, type `cmd`, press Enter. Then type:

    python --version

You want **3.10 or higher**. If you get a version number, go to step 2.

If it says Python is not recognised, try `py --version` instead. **If `py` is
the one that answers, use `py` in place of `python` in every command on this
page** — they are the same Python, reached by a different name.

If neither works, this laptop has no Python and Road B is closed — use Road A,
the `.exe`, which needs nothing at all.

### 2. Copy the whole folder across

Copy `RIPPLE COPILOT DEMO` onto the laptop **in one piece**, onto the Desktop or
into Documents.

**Not into Program Files, and not left on the memory stick.** Ripple writes its
settings and your saved analyses into its own folder, and both of those places
refuse writing. It will tell you so rather than failing quietly, but it is easier
to put it somewhere you own to begin with.

Copying part of the folder is the usual thing that goes wrong. The `sqlglot`
folder is 183 files and it must all arrive.

### 3. Prove it works, before opening anything

In Command Prompt, go to the folder and run the check:

    cd "%USERPROFILE%\Desktop\RIPPLE COPILOT DEMO"
    python run.py --demo --check

That first line assumes you put the folder on the Desktop. If you put it in
Documents, swap `Desktop` for `Documents`. If you put it somewhere else, or the
line just says the path cannot be found, do this instead and you cannot get it
wrong: type `cd ` — the three letters and a space — then **drag the folder onto
the Command Prompt window**. Windows types the correct path for you. Press Enter.

You should see something like:

      files read      : 24
      statements read : 28
      tables learned  : 18

      scanning ACCOUNT_MASTER.cust_id ...
      risk            : medium
      published tables: none
      files with impact: 2

      Ripple works on this machine.

**That is the whole product proving itself without a browser.** If you see it,
everything underneath the screens works, and anything odd after this point is the
browser rather than Ripple.

If it complains instead, the message says what is missing. The two common ones
are a partly-copied folder and a Python that is too old.

### 4. Start it

    python run.py --demo

The browser opens by itself at `http://localhost:8000`, already pointed at the
pretend pipeline so there is something to look at. Leave the black Command
Prompt window open — closing it stops Ripple.

After the first time, plain `python run.py` is enough: it remembers whatever
folder you last chose.

If something else on the laptop is already using port 8000, Ripple quietly takes
the next free one up to 8020 and prints the address it actually got. Read the
address off the screen rather than assuming.

### 5. Point it at real work

`--demo` points it at the pretend pipeline in `mockrepo`, so you can see it work
before committing to anything. It ships with no folder chosen at all — a folder
path from this machine would mean nothing on yours — so the first screen asks,
and `--demo` is just a shortcut past that question.

To scan something real: **Settings & checks** in the left-hand menu → put the
folder path in → choose the SQL dialect → put your published table names in →
Save. It reads the folder again and the numbers change.

The published-table list is the setting that matters most. Ripple only calls
something "production impact" if the table it ends at is on that list. You can
paste a list of names, or a pattern like `_PUBLISHED`.

### 6. Stop it

Press the **Close Ripple** button on the settings screen, or just close the
browser tab — Ripple notices the page has gone and stops itself a few seconds
later. You can also press `Ctrl+C` in the Command Prompt window.

---

## Making it a double-click

`START RIPPLE.bat` is already in the folder. Double-click it and it does steps 1
and 4 for you — it works out whether this laptop calls Python `python` or `py`,
and uses whichever answers:

```bat
@echo off
cd /d "%~dp0"
set PY=python
where python >nul 2>nul || set PY=py
where %PY% >nul 2>nul || (
  echo.
  echo This laptop has no Python, so this folder cannot start.
  echo Use the .exe instead - see HOW-TO-RUN-THIS.md, Road A.
  echo.
  pause
  exit /b 1
)
%PY% run.py --demo
if errorlevel 1 pause
```

Two things in there matter. If there is no Python at all it says so in a
sentence and waits, rather than a black window blinking shut and leaving you
none the wiser. And the last line keeps the window open when Ripple fails to
start, so you can read why.

---

## If you want an `.exe` after all

You cannot make one on the office laptop. You make it on a machine that allows
installs, and carry the result:

1. On the home machine, in `D:\Apps\Ripple\Ripple Offline`:

       ..\Codebase\.venv\Scripts\python build.py

2. That produces one zip in `dist\`, about 29 MB, named for the version it
   built — `Ripple-Offline-v<version>.zip`. There is only ever one in there, so
   take whichever one you find rather than looking for a number.
3. Copy the zip across, unzip it, double-click `Ripple Offline.exe`.

That copy needs no Python on the laptop at all. It is the same engine and the
same screens as this folder — the `.exe` is only a wrapper that carries its own
Python inside it, which is exactly why it has to be built where Python can be
installed.

---

## When something goes wrong

**"python is not recognised"**
Python is not installed, or not on the path. Try `py run.py` instead of
`python run.py`. If that fails too, use Road A.

**"Ripple could not find the SQL parser"**
The `sqlglot` folder did not arrive, or arrived incomplete. Copy the whole thing
again in one piece.

**"Ripple could not save its settings into ..."**
It is somewhere that refuses writing — Program Files, or a network share, or a
memory stick. Move the whole folder to your Desktop and start it again.

**The page is blank, or the styling is missing**
The `web` folder did not arrive. It needs `index.html`, `app.js` and
`styles.css`.

**Every port from 8000 to 8020 is in use**
Something else on the laptop has them. Close it, or restart the laptop.

**It says it is reading and never finishes**
A big repository genuinely takes minutes — the screen shows a counted number of
files, so you can watch it move. If the number is not moving, the folder may be
on a network drive or held in OneDrive; copy it locally first.

**Run the full self-test**

    python -m unittest tests.test_smoke -v

Thirteen checks, a second or two. They cover the parser arriving, the engine
arriving, the screens arriving, a column being followed end to end, and the rule
that Ripple must never say "no impact" over a file it could not read.

---

## What this folder is, and is not

**It is a snapshot.** The engine inside it is the engine as it stood on the day
it was made, and the version on the settings screen is that day's version. It
does not update itself.

**It is not the product's own offline build.** The real one keeps a single copy
of the engine and reaches back into it, so it can never fall behind. This folder
carries its own copy because on the office laptop there is nothing to reach back
to.

**Do not edit files in here to fix something.** An edited snapshot is a fork, and
a fork on a laptop nobody else can see is the copy that quietly goes wrong. Fix
it on the home machine, take a fresh snapshot, and carry that across.
