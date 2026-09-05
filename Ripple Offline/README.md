# Ripple Offline

The same Ripple, packaged for a machine with no internet at all — scanning a
repository that is already on that machine.

A colleague copies one folder across, double-clicks it, and uses it. No Python,
no `pip install`, no network, no terminal.

## Get it

**<https://github.com/aucksy/Ripple/releases/latest>** — download
`Ripple-Offline-vX.Y.Z.zip`, unpack it anywhere, double-click
`Ripple Offline.exe`.

The version is in the filename on purpose, and it is the same version the
settings screen shows once it is running, so a copy can always be told from
another one. Only the newest release is kept.

The zip is **not** in this repository. Git keeps every version of every file
for ever, and forty builds of a 22 MB download were the whole repository — a
fresh clone paid for all forty. It is built by `python build.py` into `dist/`,
which is not tracked, and published to the releases page from there. Nobody
builds it on their own machine: pushing a version tag (`v1.9.0`) runs
`.github/workflows/release.yml`, which runs both test suites, builds the zip,
starts the built program and drives it through its own API
(`tools/prove_build.py`), and only then publishes it, keeping only that one.

---

## What it is

Ripple reads an upstream change notification, searches the code for the tables
and attributes it names, follows each rename to the production tables it feeds,
and writes up what breaks — plus, just as importantly, what it could not read.

This edition changes four things and nothing else:

| | Online | Offline |
|---|---|---|
| Where the code comes from | a folder, or a GitHub repository | **a folder, chosen on screen** |
| The SQL dialect | an environment variable | **chosen on screen, BigQuery by default** |
| The AI | optional, with rules as the fallback | **not present at all** — rules are the only path |
| Saved history | lost when a hosted copy restarts | **kept on disk**, beside the program |

Every screen is otherwise identical, because it is literally the same front end
with the parts that reach out removed. See *How it stays in step* below.

---

## Getting it onto the other machine

1. On a machine that has Python and internet:

   ```
   python build.py
   ```

2. Copy `dist/Ripple Offline` — the whole folder — onto the locked-down machine.
   Anywhere will do: a desktop, a network share, a USB stick.

3. Double-click **Ripple Offline.exe**. The browser opens by itself.

4. The first screen asks for the repository folder. Point it at the code, check
   the SQL dialect underneath is right, and press save.

That is the entire installation. To remove it, delete the folder.

The build is about 44 MB and contains its own Python, so nothing has to be
installed on the other machine and nothing is left behind on it.

---

## What lives beside the program

Three files appear in the folder as it is used, and nothing is written anywhere
else on the machine:

| File | What it is |
|---|---|
| `ripple-settings.json` | the folder to scan, and the SQL dialect. Plain text — readable and editable by hand |
| `ripple-history.db` | saved analyses |
| `ripple-log.txt` | what the program would have printed if it had a terminal. The thing to ask for if it will not start |

Copy the folder to another machine and the settings and history go with it.

---

## Hard offline, and how that is proved

Not a promise on a screen — three separate things, each of which can be checked.

**Nothing that reaches out is on any screen.** The GitHub source option and the
AI key form are not disabled or hidden: they are deleted from the front end when
it is built, and the build then searches what it produced for the words that
should be gone. If any survive, the build stops and names the line.

**Nothing that reaches out is even in the program.** The AI layer, the GitHub
repository reader and the HTTP client they use are not packaged into the
executable. `tests/test_built_exe.py` reads the built file and checks.

**Outbound connections are blocked while it runs.** The program refuses any
connection that is not to itself before it starts. Loopback still works, because
Ripple's own web server and the browser talk over it. Anything else raises an
error naming the address it tried. The *Settings & checks* screen asks the
running program whether the block is on and reports what it says, rather than
claiming it.

The test suite runs the whole flow — reading a notification, scanning, the
summary, the drafted reply, saving history — with outbound connections blocked,
and fails if anything reaches out. A build machine with internet cannot make
that test pass by accident.

The fonts are bundled too. A font fetched from the internet is a page that looks
broken on a machine that has none.

---

## Why the SQL dialect is the setting that matters

It is on the settings screen, defaulted to BigQuery, because leaving it wrong
does not make the answer vaguer. It inverts it.

A small BigQuery pipeline is kept in the online test suite. It uses nothing
exotic — a `QUALIFY`, a `SELECT * EXCEPT`, an `UNNEST`, a `MERGE`, and table
names written the BigQuery way. Run against it:

| | read as generic SQL | read as BigQuery |
|---|---|---|
| Files parsed | 2 of 5 | 5 of 5 |
| Tables learned | 0 | 3 |
| Production tables affected | 0 | 1 |
| Verdict | **No impact** | **Medium risk, 2 breaking usages** |

The generic run is not a smaller answer. It is the opposite answer, and it is
wrong. Ripple does list the files it could not read, so the evidence is on
screen — but "no impact" is what gets remembered.

Offline this matters more, because there is no AI second opinion behind it.

---

## What is better here, and what is worse

**Better.** Saved history lasts, because there is a real disk. There is no 4 MB
limit on the notification file, because there is no host refusing large uploads.
Nothing leaves the machine, so there is no question about sending table names to
a third party.

**Worse.** There is no AI, so the rules-based reader is the only path rather
than a fallback. That is why the reader was improved as part of this work:
pasting the text of an email now finds the source system, the contact and the
subject line as well as uploading the file does. Before, pasting left them
blank — an annoyance online, where the AI covered it, and the normal case here.

---

## How it stays in step with the online version

There is **one** copy of Ripple's analysis engine, in `Codebase/ripple`, and
**one** front end, in `Codebase/web`. This folder holds neither.

* `build.py` reads the engine straight out of `Codebase/ripple` and packages it.
  Nothing is copied to disk, so the offline build cannot fall behind: it is
  built from whatever the online version is today.
* The front end is generated. `webbuild.py` takes `Codebase/web/app.js` and
  deletes the blocks marked `//<online-only>` — the GitHub source and the AI key
  form — then appends `web/offline.js`, which holds the screens that only exist
  here.

The markers are the fragile part, so nothing depends on them being remembered.
The build checks its own output: if a marker is lost and a form that reaches out
survives, the build fails and says which word it found and on which line. That
check is exercised by a test that deliberately removes a marker.

If a screen ever needs to differ offline, mark it in the shared file rather than
forking it. A fork would drift, and the drifting copy would be the one running
where nobody can check it.

---

## Running it from source

```
python run.py
```

The front end is rebuilt from the shared one every time it starts, so it can
never be a stale copy.

## Tests

```
python -m pytest tests -q
```

97 tests, covering: the settings and the folder checks, the whole flow through
the offline app, the absence of every route that reaches out, the network guard,
the front-end build and its safeguards, and — when a build exists — what is
inside the executable itself.

The shared engine has its own suite, which must also pass:

```
cd ..\Codebase
.venv\Scripts\python -m pytest tests -q
```

## The files

```
run.py                  start it (the built program runs this same code)
build.py                make the folder that gets copied across
tools/make_icon.py      redraw the icon; only needed if the mark changes
assets/ripple.ico       the icon, committed so a build never depends on redrawing it
web/offline.js          the screens that only exist offline
ripple_offline/
  engine.py             finds the one copy of the analysis engine
  app.py                the web routes - no GitHub, no AI
  prefs.py              the settings file, and checking the chosen folder
  paths.py              where things are written, beside the program
  nonet.py              the block on outbound connections
  folderpick.py         this machine's own folder chooser, when it has one
  webbuild.py           builds the offline front end out of the shared one
tests/                  the test suite
```

## Known limits

Everything in the online README's *Known limits* applies here too — it is the
same engine. On top of those:

- **There is no AI**, so the wording of the summary and the reply is the plainer,
  rules-written version. Every finding is the same; only the prose differs.
- **Windows only.** The build script produces a Windows executable. The code
  itself is not Windows-specific — `python run.py` works anywhere — but nobody
  has built or tested it elsewhere.
- **The folder chooser needs a desktop.** On a machine with no windowing
  session, the *Browse…* button is not shown at all and the path is typed or
  pasted instead.
- **Links to open a file in a code host are not offered**, because the files are
  on this machine and there is no address to send anyone to.
