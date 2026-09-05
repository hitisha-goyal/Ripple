r"""Write BUILD-KIT-REPAIR.md: one prompt that routes a complaint to the right files.

    ..\Codebase\.venv\Scripts\python tools\make_repair_kit.py

WHAT IT IS FOR. Somebody has a working Ripple and something about it is wrong.
They do not know which of thirty Python files decides it, and they should not
have to. So they paste ONE prompt into a chat, type what is wrong underneath it,
and the chat answers with the files to open and where they are saved.

For that to work the prompt has to carry three things about every file, and all
three go stale the moment they are typed by hand:

  what it decides    taken from the file's own first docstring line
  how big it is      counted
  what it touches    the REAL import graph, read with ast

The version this replaces was hand-written, and by the time it was read
sqlread.py had grown from 3,573 lines to 3,720, repo.py from 832 to 964 and
app.js from 2,883 to 3,235. Sizes are the least of it: a hand-kept list of which
files depend on which is how a chat gets asked for one file when the change
needs three, and the answer that comes back is confident and half-right.

WHY THE DEPENDENCIES ARE THE POINT. Ripple's engine is not thirty independent
files. Change what ``repo.py`` puts in a SourceFile and five files read it.
Change a key in a scan result and ``app.js`` shows a blank with nothing anywhere
saying why. The prompt lists, for every file, what it needs AND what needs it,
so the chat asks for the whole set before writing a line.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(r"D:\Apps\Ripple")
CODE = ROOT / "Codebase"
OFF = ROOT / "Ripple Offline"
OUT = ROOT / "BUILD-KIT-REPAIR.md"

# Files that exist only in one of the two builds. Everything else is in both,
# and a card that does not say which is a card that sends somebody looking for
# a file their build does not have.
ONLY_NORMAL = {"ripple/ai.py", "ripple/providers.py", "ripple/scanner/github.py",
               "ripple/api.py", "run.py"}
ONLY_PACKAGED = {"ripple_offline/app.py", "ripple_offline/nonet.py",
                 "ripple_offline/lifecycle.py", "ripple_offline/prefs.py",
                 "ripple_offline/paths.py", "ripple_offline/folderpick.py",
                 "ripple_offline/synced.py", "ripple_offline/webbuild.py",
                 "ripple_offline/engine.py", "ripple_offline/__init__.py"}

# What a person says, and the file that decides it. Written as symptoms rather
# than as file names, because somebody with a complaint does not know the file --
# that is the whole reason this document exists.
SYMPTOMS: list[tuple[str, str]] = [
    ("Which folder is scanned, which SQL dialect, how many renames deep it follows, which folders are skipped, the biggest file it will open", "ripple/config.py"),
    ("Which table names count as the ones your team publishes", "ripple/production.py"),
    ("A file type Ripple should open and does not — .ipynb, .tf, .j2", "ripple/scanner/repo.py"),
    ("SQL kept inside YAML, XML, a shell script or a Python file that is being missed", "ripple/scanner/repo.py"),
    ("A file held in OneDrive, or a path too long to open", "ripple/scanner/repo.py"),
    ("A {{ placeholder }} shape that is not being filled in", "ripple/scanner/templating.py"),
    ("A scripting block — BEGIN, FOR, IF, DECLARE — hiding the SQL underneath", "ripple/scanner/templating.py"),
    ("A statement the parser refuses, reported as unreadable", "ripple/scanner/rescue.py"),
    ("A rename that is not being followed", "ripple/scanner/sqlread.py"),
    ("A chain that stops one hop early, or never starts", "ripple/scanner/sqlread.py"),
    ("A usage that should count as breaking and does not", "ripple/scanner/sqlread.py"),
    ("A column usage Ripple does not notice at all — QUALIFY, PIVOT, a window clause", "ripple/scanner/sqlread.py"),
    ("The risk badge being wrong", "ripple/scanner/lineage.py"),
    ("Something missing from \"what this result does not cover\"", "ripple/scanner/lineage.py"),
    ("A published table that should have been found, or should not have been", "ripple/scanner/lineage.py"),
    ("\"No impact\" appearing where it should not", "ripple/scanner/lineage.py"),
    ("Wording in the summary or the reply letter", "ripple/narrative.py"),
    ("The email upload getting the tables, the date or the contact wrong", "ripple/notification.py"),
    ("Wording, layout, or any card on any screen", "web/app.js"),
    ("Colours, spacing, fonts, anything visual", "web/styles.css"),
    ("The version line on the settings screen", "ripple/build_info.py"),
    ("The progress line while you wait", "ripple/progress.py"),
    ("Saved analyses — what is kept, what the table shows", "ripple/store.py"),
    ("A new web address, or the shape of what one returns", "ripple/api.py"),
    ("The AI reader, or which model it uses", "ripple/ai.py"),

    # Everything below was earned by following BUILD-KIT.md by hand, twice, on
    # 28 Aug 2026. Every one of these is what a build made from the kit actually
    # did, and none of them was in this table -- so somebody hitting them had
    # nowhere to be sent. They are symptoms as they LOOK, not as they are, which
    # is the only form somebody stuck can search for.
    ("Every screen is blank, the sidebar draws, and there is nothing in the "
     "browser console", "web/app.js"),
    ("Ripple will not start: ModuleNotFoundError naming one of its own files",
     "ripple/api.py"),
    ("A button that does nothing at all, with no error anywhere", "ripple/api.py"),
    ("The first screen is empty and /api/health answers 500", "ripple/progress.py"),
    ("The typefaces never arrived, or the screens are in the wrong font",
     "web/styles.css"),
    ("It says nothing can be scanned until the published list is set",
     "ripple/production.py"),
    ("The trail stops after a few renames and says the chain ended",
     "ripple/config.py"),
    ("A file it could not read is not on the check-by-hand list",
     "ripple/scanner/lineage.py"),
]

# The screens are not Python and have no imports to read, so they are described
# here. Nothing else in this file is hand-written.
WEB = [
    ("web/app.js", "Every screen. All seven steps, every card, every table and every "
     "word on them. No Python file draws anything.",
     ["reads the JSON that ripple/api.py (or ripple_offline/app.py) returns"],
     ["nothing imports it — the page loads it"]),
    ("web/styles.css", "Every colour, size and spacing rule.",
     ["nothing"], ["web/index.html loads it"]),
    ("web/index.html", "The empty page the screens are drawn into, and the seven "
     "<template> blocks each step is cloned from.",
     ["loads styles.css, app.js and the fonts"], ["nothing"]),
]


def load() -> dict[str, Path]:
    files: dict[str, Path] = {}
    for p in sorted((CODE / "ripple").rglob("*.py")):
        if "__pycache__" not in p.parts:
            files["ripple/" + p.relative_to(CODE / "ripple").as_posix()] = p
    files["run.py"] = CODE / "run.py"
    for p in sorted((OFF / "ripple_offline").glob("*.py")):
        files["ripple_offline/" + p.name] = p
    return files


def module_of(name: str) -> str:
    return name[:-3].replace("/", ".")


def graph(files: dict[str, Path]) -> tuple[dict[str, set], dict[str, set]]:
    """Who imports whom, read off the code with ast rather than guessed."""
    mods = {module_of(n): n for n in files}
    needs: dict[str, set[str]] = {n: set() for n in files}
    for name, path in files.items():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        pkg = module_of(name).rsplit(".", 1)[0]
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.level:
                    base = pkg
                    for _ in range(node.level - 1):
                        base = base.rsplit(".", 1)[0]
                    target = f"{base}.{node.module}" if node.module else base
                    for a in node.names:
                        for cand in (f"{target}.{a.name}", target):
                            if cand in mods:
                                needs[name].add(mods[cand])
                elif node.module:
                    for a in node.names:
                        for cand in (f"{node.module}.{a.name}", node.module):
                            if cand in mods:
                                needs[name].add(mods[cand])
            elif isinstance(node, ast.Import):
                for a in node.names:
                    if a.name in mods:
                        needs[name].add(mods[a.name])
        needs[name].discard(name)

    needed_by: dict[str, set[str]] = {n: set() for n in files}
    for name, deps in needs.items():
        for d in deps:
            needed_by[d].add(name)
    return needs, needed_by


def docstring(path: Path) -> tuple[str, str]:
    """The file's own words: its first sentence, and the rest of its reasoning.

    Written by whoever wrote the file, which is the only reason it stays true
    when the file changes and nobody remembers this document exists.

    The REST is not padding. Ripple's modules explain WHY they are the shape
    they are -- which mistake each rule prevents, and what it cost to find out.
    A chat that has read "sqlglot renames these keys between majors and the
    renames are silent" routes a complaint correctly; one given only the
    heading guesses. It is 229 lines across the engine and it is the most
    useful 229 lines in this document.

    Longest run of backticks in any of them is two, and the fence is four, so
    none of this can close the block early.
    """
    try:
        doc = ast.get_docstring(ast.parse(path.read_text(encoding="utf-8"))) or ""
    except SyntaxError:
        return "", ""
    lines = [l.rstrip() for l in doc.strip().splitlines()]
    if not lines or not lines[0].strip():
        return "", ""
    head = lines[0].strip()
    if len(lines) > 1 and lines[1].strip() and not head.endswith("."):
        head += " " + lines[1].strip()
        rest = lines[2:]
    else:
        rest = lines[1:]
    while rest and not rest[0].strip():
        rest.pop(0)
    return head, "\n".join(rest).strip()


def public_names(path: Path) -> list[str]:
    """The functions and classes another file could be calling."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return []
    out = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if not node.name.startswith("_"):
                out.append(node.name + ("" if isinstance(node, ast.ClassDef) else "()"))
    return out


def build_where(name: str) -> str:
    if name in ONLY_PACKAGED:
        return "packaged build only"
    if name in ONLY_NORMAL:
        return "normal build only"
    return "both builds"


def main() -> None:
    files = load()
    needs, needed_by = graph(files)

    catalogue: list[str] = []
    for name, path in files.items():
        if path.stat().st_size == 0:
            continue                              # the empty __init__.py files
        n = len(path.read_text(encoding="utf-8").splitlines())
        pub = public_names(path)
        head, rest = docstring(path)
        entry = (
            f"### {name}   ({n:,} lines, {build_where(name)})\n"
            f"WHAT IT DECIDES: {head or 'no description in the file'}\n"
            f"IT NEEDS      : {', '.join(sorted(needs[name])) or 'nothing else in Ripple'}\n"
            f"NEEDED BY     : {', '.join(sorted(needed_by[name])) or 'nothing else in Ripple'}\n"
            f"CALLABLE      : {', '.join(pub[:14]) or 'none'}"
            + (f" and {len(pub) - 14} more" if len(pub) > 14 else "")
        )
        if rest:
            indented = "\n".join("    " + l if l.strip() else "" for l in rest.splitlines())
            entry += f"\nWHY IT IS LIKE THIS, in the file's own words:\n{indented}"
        catalogue.append(entry)

    for name, what, n_needs, n_by in WEB:
        p = CODE / "web" / name.split("/", 1)[1]
        n = len(p.read_text(encoding="utf-8").splitlines())
        catalogue.append(
            f"### {name}   ({n:,} lines, both builds)\n"
            f"WHAT IT DECIDES: {what}\n"
            f"IT NEEDS      : {', '.join(n_needs)}\n"
            f"NEEDED BY     : {', '.join(n_by)}\n"
            f"CALLABLE      : not Python"
        )

    # ── the files only a Ripple BUILT FROM THE KIT has ───────────────────────
    # A catalogue that does not name a file cannot send anybody to it. Somebody
    # who built their Ripple by following BUILD-KIT.md has five files this
    # repository does not: measured 28 Aug 2026, they were paths.py, getfonts.py,
    # requirements.txt, start-ripple.bat and build.py, and none was catalogued.
    #
    # The list is READ OUT OF THE KIT'S OWN FOLDER PICTURE, never typed here, so
    # a file added to the kit cannot go missing from this catalogue quietly. A
    # picture file with no description below is printed as NOT DESCRIBED YET
    # rather than dropped, because a silent gap is what this is fixing.
    # Keyed by the path as it should APPEAR, because ripple/paths.py and
    # ripple_offline/paths.py are two different files with one basename.
    KIT_ONLY_WHAT = {
        "ripple/paths.py": (
            "Where things are, whether Ripple is running from source or packaged.",
            "nothing else in Ripple",
            "ripple/api.py, ripple/store.py, run.py",
            "web_dir(), data_dir()",
        ),
        "getfonts.py": (
            "Fetches the two typefaces, once. Run it and never again.",
            "nothing else in Ripple",
            "nothing - it is run by hand, once",
            "run as a program, not imported",
        ),
        "requirements.txt": (
            "The pinned versions, so a second machine gets the same Ripple.",
            "nothing else in Ripple",
            "start-ripple.bat names it when nothing is installed yet",
            "not Python",
        ),
        "start-ripple.bat": (
            "Starting Ripple with a double-click, and finding the right Python.",
            "run.py",
            "nothing - it is the way in",
            "not Python",
        ),
        "build.py": (
            "Packaging the folder into a program you can hand to somebody.",
            "the whole project folder",
            "nothing - it is run by hand, last",
            "run as a program, not imported",
        ),
    }

    kit_md = (ROOT / "BUILD-KIT.md").read_text(encoding="utf-8")
    picture = re.search(r"^C:\\ripple-build\\\n(.*?)^```", kit_md,
                        re.DOTALL | re.MULTILINE)
    kit_only: list[str] = []
    if picture:
        # Every file the kit says it builds, by basename. Tests are left out:
        # they are not files anybody repairs, and each phase already names its
        # own. build.py is named in the prose beside the picture, not inside it.
        drawn = {f for f in re.findall(
            r"(?<![\w.-])([a-z_][a-z0-9_-]*\.(?:py|txt|bat))\b", picture.group(1))
            if not f.startswith("test_") and f != "__init__.py"}
        if "build.py" in kit_md:
            drawn.add("build.py")

        catalogued_names = {n.rsplit("/", 1)[-1] for n in files}
        catalogued_names |= {n.rsplit("/", 1)[-1] for n, *_ in WEB}
        catalogued_paths = set(files) | {n for n, *_ in WEB}

        for want, what in KIT_ONLY_WHAT.items():
            if want.rsplit("/", 1)[-1] not in drawn or want in catalogued_paths:
                continue
            head, n_needs, n_by, callable_ = what
            kit_only.append(
                f"### {want}   (built from the kit only)\n"
                f"WHAT IT DECIDES: {head}\n"
                f"IT NEEDS      : {n_needs}\n"
                f"NEEDED BY     : {n_by}\n"
                f"CALLABLE      : {callable_}"
            )

        described = {w.rsplit("/", 1)[-1] for w in KIT_ONLY_WHAT}
        for fname in sorted(drawn - catalogued_names - described):
            kit_only.append(
                f"### {fname}   (built from the kit only)\n"
                f"WHAT IT DECIDES: NOT DESCRIBED YET - BUILD-KIT.md draws this "
                f"file and tools/make_repair_kit.py has no description for it. "
                f"Add one to KIT_ONLY_WHAT."
            )
            print(f"  !! {fname} is drawn in the kit and described nowhere here")
    catalogue.extend(kit_only)

    rows = "\n".join(f"| {sym} | `{f}` |" for sym, f in SYMPTOMS)
    total_py = sum(1 for n, p in files.items() if p.stat().st_size)
    total_lines = sum(len(p.read_text(encoding="utf-8").splitlines())
                      for p in files.values())

    # The three biggest files, measured rather than typed. "Expect a whole
    # evening" is only believable with the real number beside it, and a number
    # typed here would be stale within a week -- which is the entire reason
    # this document is generated instead of written.
    sizes = {n: len(p.read_text(encoding="utf-8").splitlines())
             for n, p in files.items() if p.stat().st_size}
    for wname, *_ in WEB:
        sizes[wname] = len((CODE / "web" / wname.split("/", 1)[1])
                           .read_text(encoding="utf-8").splitlines())
    biggest = "\n".join(f"* `{n}` — {c:,} lines" for n, c in
                        sorted(sizes.items(), key=lambda kv: -kv[1])[:3])

    OUT.write_text(f"""# Repairing Ripple

You have a working Ripple and something about it is wrong. This tells a chat
enough to work out **which files you need to open**, so you do not have to.

You do not need to read Python. You need to find a file, paste it, paste back
what you get, and run one command.

**If you have not built Ripple yet**, this is the wrong document. Open
`START-HERE.md` instead — it is in the same folder as this file, beside
`BUILD-KIT.md` — and it picks the right one for you.

**Two builds, and this page uses the same two names all the way through.** The
**normal build** is the one BUILD-KIT.md makes: a folder with `run.py` in it,
started by typing `python run.py` or by double-clicking `start-ripple.bat`. The
**packaged build** is the single program made at the end of the kit, the one
you can hand to somebody else: the same Ripple, wrapped up, for a machine with
no internet. Wherever you see the words **Ripple Offline**, that is the packaged
build. The file list further down tags every file with the build it belongs to,
in exactly those two words.

---

## How this works

**Step 1.** Copy the whole prompt below and paste it into a new chat window. It
starts at `YOU ARE REPAIRING RIPPLE` and ends at the line
`NOW READ WHAT I WANT CHANGED, BELOW, AND ANSWER WITH THE FILE LIST ONLY.` It is
about 650 lines, and a safe way to take all of it is printed just above the
prompt itself.

**Step 2.** Underneath it, in your own words, type what is wrong.

**Step 3.** The chat replies with the files to open and where they are saved. It
will name every file that has to change TOGETHER, not just the obvious one. Open
those, paste them in, and it gives you complete files back.

The more concrete you are in step 2, the better. *"The scan misses the table
built in load_final.sql.j2 and I want that file read"* beats *"improve template
support"*.

---

## Four rules. Break these and you lose an evening.

**1. Copy the file before you change it.** Right-click, Copy, Paste in the same
folder. Windows makes `sqlread - Copy.py`. That is your way back.

**2. One change at a time.** Ask for one thing, check it, then ask for the next.
Two changes in one window and you cannot tell which one broke it.

**3. Run the check before you believe it.** Every change ends with a command you
type yourself, in the black window. Until that command has printed the right
last line — **When the chat has named your files**, below, gives you the exact
words, and they are not the same words on every machine — the change is not
done, whatever the chat told you.

**4. Some of these files are enormous.** The three biggest:

{biggest}

Pasting one of those into a chat, and catching the new one coming back, is a
whole evening on its own — and the reply will usually arrive in two or three
parts, because no chat writes that much in one go. That is normal, not a
failure: when it stops in the middle, send the wording under **It stopped in the
middle of a long file**, near the end of this page. Before you start, look your
file up in the list further down. It gives the size of every one, so you know
what you are in for.

---

## THE PROMPT — copy all of this

**It is about 650 lines, so do not drag your mouse down it** — you will lose
the end and never notice. Two ways to take all of it:

* **If whatever you are reading this in draws a grey box round the prompt, with
  a Copy button in the corner of it**, click that button. One click takes the
  lot.
* **In Notepad there is no grey box and no button** — only a line of backtick
  characters above the prompt and another below it. Click once just before the
  `Y` of `YOU ARE REPAIRING RIPPLE`. Scroll down to the bottom of the prompt.
  Hold **Shift** and click once just after `FILE LIST ONLY.` Everything between
  your two clicks turns blue. Press **Ctrl+C**.

**Then check that what you copied ends with `ANSWER WITH THE FILE LIST ONLY.`**
That line is what makes the chat answer with a list of files instead of writing
code at you. Lose it and nothing warns you.

````text
YOU ARE REPAIRING RIPPLE. Read all of this before you answer.

WHAT RIPPLE IS
An upstream data team emails: "we are changing MARKET_CODE in
CUSTOMER_DEMOGRAPHICS on 18 September." Ripple reads our own pipeline
repository and answers: what breaks, where, and what do we tell them. A column
rarely keeps its name -- MARKET_CODE becomes mc, then mkt_cd -- so a word search
is useless. Ripple parses the SQL and follows the rename chain to the tables the
team publishes.

Its whole value is that when it says "no impact", that can be trusted.

WHAT I AM GOING TO DO
At the end of this message I will say what is wrong. You do NOT have my files.
Your first job is to tell me WHICH FILES TO SEND YOU, using the catalogue below.

HOW TO ANSWER MY FIRST MESSAGE
Reply with only this, and nothing else:

  1. WHICH FILES I SHOULD SEND, each on its own line, with its exact path -- both
     paths where a file is saved differently in the two builds. Use the FULL
     path as written in the catalogue, so I can find it.
  2. WHY EACH ONE, in one line each. If a file is on the list only because
     something in it might have to change too, say so.
  3. WHAT YOU THINK IS HAPPENING, in two or three plain sentences.
  4. Then stop and wait. Do not write any code yet.

ASK FOR EVERY FILE THAT MIGHT HAVE TO CHANGE TOGETHER, NOT ONLY THE OBVIOUS ONE.
The catalogue below gives, for every file, what it NEEDS and what NEEDS IT. Use
both directions:

  * changing what a file PRODUCES -- a new field, a renamed key, a different
    shape -- means every file under NEEDED BY has to be checked, and usually
    web/app.js as well, because a screen asking for a key nobody sends shows a
    blank and says nothing.
  * changing what a file CONSUMES means every file under IT NEEDS is worth
    reading before you write a line.
  * a new setting always touches ripple/config.py as well as wherever it is read.
  * anything that changes a number, a count or a warning on screen touches BOTH
    the file that works it out AND web/app.js, which draws it.

I would much rather paste four files than get a confident answer built on one.

ONCE I HAVE SENT THE FILES
1. Read them before writing anything.
2. Tell me in plain English what you are going to change, and what else it
   touches. Wait for me to say yes. I am a product manager, not a coder.
3. Then give me the COMPLETE new file, top to bottom, for every file that
   changes. Not a patch, not a diff, not "...rest unchanged". The whole file,
   in its own block, with its path written above it.
4. Keep every comment already in the file unless the code it explains has gone.
   Those comments record the mistakes the lines prevent.
5. Give me one command that proves it worked, and tell me what a pass looks like.

RULES YOU MAY NOT BREAK
* Change the least you can. If one line does it, change one line.
* Never remove something that reports a gap, a warning, or something Ripple
  could not read. Those ARE the product.
* Never make Ripple more confident than it was. Where it cannot tell two things
  apart it follows BOTH and says so -- it never picks one. A spare row is
  visible and can be dismissed by opening the file; a lost chain is invisible
  and reads as "no impact".
* "No impact" may never be printed over something Ripple could not look at. If
  there is a gap on the subject of the scan, the answer is "unknown", worded on
  screen as "Not sure -- needs a person".
* A caveat may never end up on a different screen from the answer it qualifies.
* Never invent a count, a percentage, a table or a column. Every number on
  screen is something that was actually counted.
* A loose name match is right for FOLLOWING a chain and catastrophic for
  EXCLUDING one.
* If what I am asking for would make Ripple quieter about something it does not
  know, say so and argue with me before you write it.
* Python 3.10. Every module starts with "from __future__ import annotations".
* British spelling. No emoji. Comments say WHY, not what.

WHERE THE FILES LIVE
Two builds, and a file can sit in a different place in each. When you name a
file, give both.

  The normal build, built from BUILD-KIT.md (normal laptop, pip works):
      the project root holds run.py, and folders ripple\\ , web\\ and tests\\
      example: ripple\\scanner\\sqlread.py

  The packaged build, also called Ripple Offline:
      the same, plus a folder ripple_offline\\ and a copied folder sqlglot\\
      example: ripple\\scanner\\sqlread.py   (the same place)
      but the web service is ripple_offline\\app.py, not ripple\\api.py

THE CATALOGUE — every file, what it decides, and what it touches
{total_py} Python files and the three screen files, {total_lines:,} lines in all.

{chr(10).join(catalogue)}

WHAT PEOPLE USUALLY WANT CHANGED, AND WHERE IT LIVES
Use this to check your answer, not instead of the catalogue -- a complaint that
is not on this list is ordinary, and the catalogue is what you reason from.

{rows}

TWO THAT ARE ALWAYS MORE THAN ONE FILE
* A blank where a number should be. The screen is asking for something the
  engine never sent. Ask for the file that works the number out AND web/app.js.
* A new setting. ripple/config.py holds every setting and nothing else may
  decide one for itself, so it is always in the set.

NOW READ WHAT I WANT CHANGED, BELOW, AND ANSWER WITH THE FILE LIST ONLY.
````

**Now type, underneath that, what is wrong.**

---

## When the chat has named your files

**Open each one in Notepad.** Right-click the file, choose **Open with**, then
**Notepad**. Never double-click a `.py` file: Windows either runs it, or throws
up a "How do you want to open this file?" list, and a wrong pick from that list
changes what happens to every `.py` file you open afterwards. If Notepad is not
offered, choose **Choose another app**, pick Notepad there, and leave **Always
use this app** unticked.

With the file open, press **Ctrl+A** to select all of it, then **Ctrl+C** to
copy, and paste it into the chat. When it gives files back:

* Save each one over the original with **Ctrl+S**, keeping the name exactly. The
  file already exists, so Notepad cannot add `.txt` to the name this time.
* Do not tidy the indentation. In Python the spaces at the start of a line
  decide which lines belong inside which.

**Now run the check it gave you.** Not in the chat — in the black Command
Prompt window. If you have not got one open: press the **Windows key**, type
`cmd`, press **Enter**. A black window opens.

**First, stand in the Ripple folder.** That is the folder with `run.py` in
it — `C:\\ripple-build` if you followed BUILD-KIT.md. That folder is what "the
project root" means, here and everywhere else in the kit. TYPE THIS INTO THE
BLACK WINDOW, then press Enter:

```
cd /d C:\\ripple-build
```

If your Ripple lives somewhere else, type `cd /d` and a space, then drag that
folder out of File Explorer and drop it on the black window. It writes the path
in for you. Then press Enter.

**Now the check itself. TYPE THIS INTO THE BLACK WINDOW.** It is a command, not
something to paste into the chat:

```
python -m pytest tests -q
```

**Read the last line it prints.** Done looks like this, and your numbers will
differ:

```
694 passed in 23.42s
```

**If instead it answers `No module named pytest`,** that machine has not got
pytest, and the command below is yours rather than the one above. Nothing is
broken, and nothing was harmed by trying the first. TYPE THIS INTO THE BLACK
WINDOW:

```
python -m unittest discover tests -v
```

**That one never prints the word "passed" at all.** It scrolls a long list and
ends with these two lines:

```
Ran 694 tests in 23.421s

OK
```

**`OK` on its own line is what done looks like there.** If you see `FAILED`
followed by a count, it is not done — whatever you were told in the chat.

### Then go and look, with your own eyes

**A green test does not mean your change worked.** It means nothing else broke.
The thing you complained about is on a screen, and only the screen can tell you.

1. **Stop Ripple properly.** Close the black window it is running in. On the
   packaged build, use the Stop button on the screen — closing the browser tab
   leaves it running, and you will be looking at the old copy without knowing.
2. **Start it again.** Double-click `start-ripple.bat`, or run `python run.py`.
   Ripple loads its code once, when it starts, so a file you saved five minutes
   ago is not in the copy that is still running.
3. **Do the exact thing you complained about**, and look at it.

That is the only proof. Somebody has spent an evening reporting a fix that
worked perfectly, in a copy of Ripple that was never restarted.

---

## What to say when it goes wrong

**It gave you a patch, or "rest of file unchanged".**
> *Give me the complete file, top to bottom, in one block. I am pasting it over
> the original and I cannot merge a patch.*

**It stopped in the middle of a long file.**
> *Continue from the last complete line. Do not start the file again from the
> top. Tell me which line you are resuming from.*

**It changed more than you asked.**
> *That is more than I asked for. Give me the smallest change that fixes only
> the thing I described, and tell me what you left out and why.*

**It quietly dropped a warning or a gap.**
> *You have removed something that reported what Ripple could not read. That is
> the product, not clutter. Put it back and fix the thing I asked about without
> touching it.*

**The tests fail after the change.** Paste the whole red block back into the same
window with nothing else except:
> *This is what happened when I ran it. Do not guess at the cause -- tell me
> which line you think produced it and why, then give me the corrected file
> whole.*

---

## About this page

**There is nothing on this page for you to run.** It writes itself out of
Ripple's own code: every file name, every size and every "what it touches" line
above was read off the code, not typed by a person.

What that means for you: **the moment you change a file, the sizes above go
slightly out of date.** That is harmless — the file names and the routing are
still right. If it ever looks badly wrong, say so in the chat and ask for this
page to be written out again.

*For whoever maintains Ripple: this file is generated by
`Ripple Offline/tools/make_repair_kit.py`, which reads each file's own first
sentence, counts its lines, and works out the import graph with `ast`. Do not
edit it by hand -- run that again instead. The version this replaced was
hand-written, and by the time anybody read it every size in it was wrong and the
dependency list did not exist at all.*
""", encoding="utf-8")

    kb = OUT.stat().st_size / 1024
    print(f"wrote {OUT.name}: {kb:,.0f} KB")
    print(f"  {total_py} Python files + 3 screen files catalogued")
    print(f"  {len(SYMPTOMS)} symptoms routed")
    deps = sum(len(v) for v in needs.values())
    print(f"  {deps} import edges read off the code")


main()
