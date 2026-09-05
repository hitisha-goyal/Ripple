# Building Ripple, one chat window at a time

**What this is.** A kit for building a working piece of software using nothing but
a chat assistant — Copilot chat on your own laptop — and three or four evenings. You
do not need to know how to code. The chat writes the code; you save it into files
and type one command to check it worked. This document is every prompt you will
paste, in order, and every command you will type, in order.

**What Ripple does.** An upstream data team sends an email: *"we are changing
MARKET_CODE in CUSTOMER_DEMOGRAPHICS on 18 September."* Somebody then has to
answer: what does that break on our side, where, and what do we tell them. Today
that means searching the code for the word MARKET_CODE — and that search is close
to useless, because a column almost never keeps its name as it travels through a
pipeline. MARKET_CODE becomes `mc`, then `mkt_cd`. The search comes back empty
while the change quietly breaks three published tables. Ripple reads the SQL
properly, follows the renames from one table to the next, and reports what actually
breaks, in which file, on which line.

**Why twelve chat windows and not one.** A chat can hold only so much at once, and
what these twelve windows produce is about twenty-two thousand lines, measured.
So it is built one file at a time, twelve windows, each producing one or two
finished files. The
catch is that every window
is a stranger: it cannot see the other eleven and has no memory of them. That is
the whole difficulty of this approach, and the contract card is the
answer to it — the same page of rules pasted at the top of every window, so that
all twelve build the same product. To see it now, press Ctrl+F and search for
**PHASE 0**.

---

## The two files, and which one you want

| File | When |
|---|---|
| **BUILD-KIT.md** | You are building Ripple. This document, start to finish, twelve windows, three or four evenings. It ends with a working Ripple and a program you can double-click and hand to somebody. |
| **BUILD-KIT-REPAIR.md** | You have finished building, and now want to change something. One prompt; it answers with which files to open and where they are saved. |

**Everything you need is in this document.** There is nothing else to open and
nothing else to get hold of. Every phase ends with one command, and that command
tells you either that the phase passed or exactly what is wrong.

---

## What is in here, and where

It is a long document. This is so you can find your way back to a page at ten
o'clock at night with a red error on the screen. **Use Ctrl+F and search for the
words in bold** — they are exactly as they are written further down.

**Read these before you touch anything** — about fifteen minutes.

| If you want to know | Search for |
|---|---|
| What this is, and what it will and will not do for you | **What this document is** |
| Why one piece has to be installed and cannot come out of a chat | **The one thing this document cannot hold** |
| What the chat can and cannot do, so you stop expecting the wrong things | **What the chat can and cannot do** |
| The two ways a build like this fails, and what stops them | **The two ways this goes wrong** |
| Which of the two documents you want — this one, or the one for changing Ripple later | **The two files, and which one you want** |

**Do these once, on the machine.** About twenty minutes, before any chat window.

| If you want to | Search for |
|---|---|
| Get Python and the pieces Ripple needs installed | **Getting ready** |
| Get past a laptop that blocks the install completely | **If the install step will not work at all** |
| Ask IT for the right thing, when none of those got the SQL reader on | **When none of them work** |
| Make the folders everything goes into | **Making the folders** |

**Then the building, twelve chat windows.**

| If you want to | Search for |
|---|---|
| Know what order to do them in and how long each takes | **The build order** |
| Copy the page that goes at the top of every window | **PHASE 0** |
| Save a file the chat gave you, without Notepad ruining the name | **Saving a file the chat gives you** |
| Save a file that arrived in several parts | **When one file arrives in several parts** |
| Check a phase worked | **Checking that a phase worked** |
| Stop for the night without losing anything | **Closing down for the night** |
| Come back the next evening and carry on where you stopped | **Starting the next evening** |
| Know which single file decides what, when something is wrong later | **What each file is for** |
| Get the 16 font files — the one part of the screens no chat can hand you | **The two typefaces** |

**The windows themselves, Phase 1 to Phase 13.** This is the page for *where was
I* and *take me to Phase 5*. The sizes are the ones counted in **The build
order**, and they are what tells you whether you can finish a phase tonight.

| # | The window builds | Roughly | Search for |
|---|---|---|---|
| 1 | Settings, and the list of table names your team publishes | 1,100 lines | **PHASE 1** |
| 2 | Walking your repository folder and deciding which files to open | 1,450 lines | **PHASE 2** |
| 3 | SQL with placeholders left in it, and scripting blocks | 1,550 lines | **PHASE 3** |
| 4 | Reading the SQL properly. The hard one, and it will stop part way | 4,900 lines | **PHASE 4** |
| 5 | The catalogue of tables and columns, and following one column through | 2,600 lines | **PHASE 5** |
| 6 | Reading the notification email | 1,750 lines | **PHASE 6** |
| 7 | Writing the summary and the reply letter | 1,950 lines | **PHASE 7** |
| 8 | Progress, saved history, and the service the screens talk to | 1,600 lines | **PHASE 8** |
| 9 | The page and its styles — and the fonts, which you fetch by hand | 1,450 lines | **PHASE 9** |
| 10 | The first three screens: notification, review, repository | 1,300 lines | **PHASE 10** |
| 11 | The last five screens: findings, map, summary, reply, settings | 2,200 lines | **PHASE 11** |
| 12 | Nothing new. You start it up and check twelve things on screen | — | **PHASE 12** |
| 13 | Packaging it into a program you can hand to somebody | 500 lines | **PHASE 13** |

**When something goes wrong.** These are the pages to come back to.

| What happened | Search for |
|---|---|
| Phase 4 came back wrong, or trailed off | **When Phase 4 goes wrong** |
| Phase 8 came back wrong | **When Phase 8 goes wrong** |
| A reply stopped part way through, or quietly skipped a piece | **Two ways a reply goes wrong** |
| The exact words to send back when a reply stops or drifts | **The four replies worth keeping to hand** |
| The chat is arguing, inventing, or writing something you did not ask for | **When the chat goes wrong** |
| The command window is saying something you do not understand | **When your own machine goes wrong** |
| Somebody has asked what this thing is, or whether it is a server on the network | **What to tell your IT team** |

**At the end.**

| If you want to | Search for |
|---|---|
| Prove the whole thing works, twelve things to look at on screen | **PHASE 12** |
| Start it with a double-click instead of a command | **Starting it with a double-click** |
| Turn it into a program you can hand to somebody | **PHASE 13** |

Two of the twelve phases are the ones that usually go wrong — 4 and 8 — so they
have ready-written sentences you can paste straight back into the chat. They are
in the table above.

---

## What this document is

Read this part first. Getting it wrong is what wastes an evening.

**It is a set of instructions, not the finished code.** It does not hold Ripple's
code for you to copy out. It describes, in order, what each part has to do. You
paste a section into the chat, the chat writes the code, you save it, and you
type one command that tells you whether it worked.

So **the code you end up with is your own**. Somebody else following this same
document would get code that looks different from yours. Both would work. That
is normal, and it is not a sign that anything has gone wrong.

The things that matter, though, are decided here and not by the chat.

**This document decides these, and the chat may not change them:**

* **What Ripple is allowed to say.** It must never answer "nothing breaks" when
  there was something it could not read. These rules are the whole point of
  Ripple, and each one is written out here with the reason behind it.
* **How it follows a column through the SQL.** Every renaming rule, every
  awkward case, and what went wrong the day each rule was added.
* **What appears on the screen, and in what words.**
* **The colours and the fonts.** Phase 9 gives the exact colours, and they are
  exact on purpose.

**You and the chat decide these:**

* **The code itself** — how it is arranged, and what things are named.
* **The tests.** Each phase says what has to be proved. You and the chat write
  the tests that prove it.

### The one thing this document cannot hold

Ripple reads SQL using a free tool called `sqlglot`. It is 183 files and 2.7
megabytes — far too big to paste into a chat, and no chat could write it. It has
to be installed onto the machine instead. That happens in **Getting ready**,
below, before any of the numbered phases start. It is the only part of this
whole document that is not a chat window.

**Getting ready is not a numbered phase.** Nothing here is called Phase 0 except
the contract card, which is a page you copy. If you are ever asking yourself
"have I done Phase 0?", the answer is about the card, not about this install.

Without the SQL reader, Ripple is only a word search. So this step is not
optional and it is not one anybody skipped. If your laptop blocks the install,
there are three other ways to get the reader on. Do **Making the folders** first
— every one of those three copies something into a folder that does not exist
until you have — and then press Ctrl+F and search for
**If the install step will not work at all**.


---

## What the chat can and cannot do

It cannot see your screen, your files or your folders. It cannot run anything, test
anything, or check whether what it just wrote works. It does not remember the other
windows. Everything it knows is what you paste into it.

So your side of the job is small and mechanical, and it is the same four moves
every time: **paste the contract card, paste the phase prompt, save the files it
gives you, run one command to check.** Nothing in this kit is harder than that.

---

## Getting ready — the machine, before any phase starts

**This has no number.** It is not Phase 0 and it is not Phase 1. It is the
twenty minutes of setting up that happens before the numbered phases begin.


A one-off, about twenty minutes. Five steps, in order.

**Step 1 — open a Command Prompt.** Press the Windows key, type `cmd`, press
Enter. A black window opens. Everything in this kit that looks like a command gets
typed into that window, followed by Enter.

**Step 2 — check Python is there.**

**Type this into the black window.**
```
python --version
```

It should print something like `Python 3.10.4`. Ripple needs 3.10 or newer.

- **"python is not recognized..."** — Python is installed but Windows was never
  told where it lives. Use the full path instead, quotes and all, everywhere this
  kit says `python`: `"C:\Program Files\Python310\python.exe"`
- **Nothing at all, or "not found"** — Python is not installed. That is a request
  to whoever manages your laptop.

**Step 3 — check pip.** pip is the thing that fetches ready-made pieces of code, so
that nobody has to write them again.

**Type this into the black window.**
```
python -m pip --version
```

Three things go wrong here on a managed laptop. Every one of them looks like a
locked door and none of them is:

- **"pip is not recognized as an internal or external command."** Nothing is
  blocked. Typing `pip` on its own makes Windows hunt for a file it was never told
  about. Type `python -m pip` instead — always, everywhere — and it works.
- **"No module named pip."** Python was installed without it. Python carries a
  spare copy inside itself, needing no internet and no admin rights:
  `python -m ensurepip --upgrade --user`
- **It hangs, then times out reaching pypi.org.** The public package site is
  blocked. Almost every large firm runs its own internal copy instead. Ask whoever
  sits near you *"how do you pip install here?"*, then point pip at their address
  once and forget about it:
  `python -m pip config set global.index-url <their address>`

**One rule about pointy brackets, and it holds for the whole kit.** Everywhere
else, a grey box is copied and typed exactly as it stands. Where a command has
something in `<pointy brackets>`, that bit is a gap only you can fill — here, the
address your colleague just gave you. Type your own words in place of it and
**delete the brackets with them**; they are not part of the command. The line
above ends up reading something like
`python -m pip config set global.index-url https://pkgs.yourfirm.com/simple`,
with no `<` or `>` left anywhere on it. This comes up once more, much later, in
Route 3.

**Step 4 — install the pieces Ripple needs.** One command. It is long; copy the
whole line.

**Type this into the black window.**
```
python -m pip install --user sqlglot==30.17.0 fastapi==0.115.0 uvicorn==0.30.6 pydantic==2.13.4 typing-inspection==0.4.2 python-multipart==0.0.9 extract-msg==0.48.7 httpx==0.27.2 pytest==8.3.3
```

What each one is for, so nothing on that line is a mystery:

| Piece | What it does |
|---|---|
| `sqlglot` | **Reads SQL properly.** The one piece that cannot be replaced, and the one a chat cannot write for you. It is what makes Ripple more than a word search. |
| `fastapi`, `uvicorn` | Serve the screens to your browser |
| `pydantic`, `typing-inspection` | Come along with FastAPI. Pinned here so they cannot drift |
| `python-multipart` | Lets you upload the notification email. Leave it out and that screen fails the moment the app starts |
| `extract-msg` | Opens Outlook `.msg` files, which is how most notifications actually arrive |
| `httpx` | Only used if you later switch on the optional AI reader. Safe to leave out |
| `pytest` | Runs the check at the end of each phase |

The versions are pinned on purpose. Left unpinned, the install takes whatever was
published this morning, and these phase prompts are written against how these
particular versions behave.

**If one package alone is refused with a 403** while everything around it downloads
perfectly, the mirror is not broken. A company mirror routinely holds back a
version published in the last few days, because nothing has scanned it for security
yet. The answer is an older version of that one package, and you do not have to
work out which. **Open a chat window and paste this, with the red text
underneath it:**

**Paste this into the chat.**
````text
This is what my company's package mirror said when I ran the install line
below. Give me the same line back with an earlier version of ONLY the package
it refused, and nothing else changed. Then tell me, in one line, what to try if
that one is refused too.
````

Copy the line it gives you and run the whole thing again.

**A refusal is not a partial install.** pip downloads everything before it
installs anything, so one refusal near the end means nothing was installed,
however much of it you watched come down. You have not made a mess; you can just
run the corrected line.

**Step 5 — check they all arrived.**

**Type this into the black window.**
```
python -c "import sqlglot,fastapi,uvicorn,pydantic,multipart,extract_msg,httpx,pytest;print('all set - sqlglot',sqlglot.__version__)"
```

You want `all set - sqlglot 30.17.0`. If instead it names one thing it could not
find, install that one on its own and run this again.

**If it names something you know you just installed, you have more than one
Python.** Windows commonly does. Measured on one ordinary laptop, 27 Aug 2026,
three separate things answered to the word `python`: a real 3.12 with everything
in it, a shortcut to a 3.14 with nothing in it, and a zero-byte Microsoft Store
placeholder that is not Python at all. `pip` put the packages in one of them and
this line asked a different one. Ask Windows which ones exist:

**Type this into the black window.**
```
where python
```

```
py --list
```

Then install through the launcher and the exact version instead of the bare word,
so both steps are certainly talking to the same Python — for example:

**Type this into the black window.**
```
py -3.12 -m pip install --user sqlglot==30.17.0 fastapi==0.115.0 uvicorn==0.30.6 pydantic==2.13.4 typing-inspection==0.4.2 python-multipart==0.0.9 extract-msg==0.48.7 httpx==0.27.2 pytest==8.3.3
```

```
py -3.12 -c "import sqlglot,fastapi,uvicorn,pydantic,multipart,extract_msg,httpx,pytest;print('all set - sqlglot',sqlglot.__version__)"
```

Use whichever version that turns out to be, and use the same form for every
`python` in this kit from here on. It is worth the extra keystrokes: this exact
confusion produced a raw Python traceback about `uvicorn` on a machine where
nothing whatsoever was wrong.

**That is the setting up done. Go straight on to Making the folders, directly
below.** Do that even if the install above refused you, because those folders are
needed either way. If `pip` could not be made to work at all, make the folders
first and then press Ctrl+F for **If the install step will not work at all**,
which now sits at the end of this document with the other pages you only need
when something breaks.

---

## Making the folders

One command builds every folder. It does not matter which folder you are standing
in when you run it, because every path is written out in full.

**Type this into the black window.**
```
mkdir C:\ripple-build\ripple\scanner C:\ripple-build\web C:\ripple-build\tests C:\ripple-build\mockrepo
```

Then two empty files. They look pointless and they are not: Python refuses to find
your code without them.

**Type this into the black window.**
```
type nul > C:\ripple-build\ripple\__init__.py
```

```
type nul > C:\ripple-build\ripple\scanner\__init__.py
```

From here on, every command in this kit is run from that folder, so start by going
there. The `/d` matters if your Command Prompt opened on a different drive:

**Type this into the black window.**
```
cd /d C:\ripple-build
```

**Why `C:\ripple-build` rather than Documents or Desktop.** Those two are usually
synced to OneDrive on a work laptop, and OneDrive leaves files listed on disk while
their contents are still up in the cloud. Ripple has an entire rule about detecting
that in *other* people's folders, because it makes a half-read repository look like
a clean result — you do not want your own project living in it. A short path also
keeps you clear of Windows' 260-character limit once the folders get deep.

**One note on how paths are written from here on.** The phases below say
`ripple-build/ripple/config.py` with forward slashes. That means exactly the same
place as `C:\ripple-build\ripple\config.py` — the folder you just made. The kit
writes it the short way because that is the form the chat should use, and Windows
accepts either.

This is what you are building towards. Every phase says exactly which of these
files it produces:

**Read this — there is nothing to type.**
```
C:\ripple-build\
  run.py                   <- the one you type to start Ripple
  start-ripple.bat         <- so you can double-click it instead (near the end)
  requirements.txt         <- the pinned versions, so a second machine matches
  getfonts.py              <- the one-off font fetcher (Phase 9)
  ripple\
    __init__.py            <- empty, but it must exist
    paths.py  config.py  production.py  catalog.py
    notification.py  narrative.py  progress.py  store.py
    api.py  build_info.py
    providers.py             <- which AI company a key belongs to (Phase 8)
    ai.py                    <- the optional AI reader (Phase 8)
    scanner\
      __init__.py          <- empty, but it must exist
      repo.py  templating.py  sqlread.py  lineage.py
      rescue.py            <- reading SQL the parser choked on
      dialectcompat.py     <- copes when the parser changes its wording
      github.py            <- reading a repository over the network (Phase 8,
                              optional — skip it and skip its two routes)
  web\
    index.html  styles.css  app.js
  tests\
    test_production.py  test_repo.py  test_templating.py
    test_sqlread.py  test_lineage.py  test_notification.py
    test_narrative.py
  mockrepo\                <- a small fake pipeline to test against (Phase 12)
```

That is the whole of it. Nothing else appears in that folder, and nothing else
needs to. If you do the optional Phase 13 at the very end, one more file joins
it — `build.py` — along with the folders the packaging tool writes for itself.

**Two files in that picture reach the network: `ripple/ai.py` and
`ripple/scanner/github.py`.** Those two, and only those two, are the ones this
kit treats as optional. Ripple answers every question without them: they add a
reader that turns a pasted email into a filled-in form, and a way to point at a
repository you have no local copy of.

A third file sits beside them and is easy to mistake for one of them:
`ripple/providers.py`. It is not optional, and by itself it reaches nothing.
**Phase 8 writes all three, and tells the chat what to do about the two you might
skip, so there is nothing here for you to decide or remember.**

* `providers.py` — **always built.** It is a small list of the three AI
  companies and what their keys look like, so the settings screen can tell you
  whose key you have pasted before it sends it anywhere. It is a list, not a
  feature: it never goes near the internet. Build it even if you never turn the
  AI on.
* `ai.py` and `scanner/github.py` — **the only two things in Ripple that reach
  the internet.** One turns a pasted email into a filled-in form; the other
  reads a repository you have no copy of. Ripple answers every question without
  them. If your laptop will not allow either, skip them and everything else
  still works.

---

## Saving a file the chat gives you

This is the step that trips people up, and there is a trick that makes it
foolproof.

**The problem.** Notepad quietly adds `.txt` to whatever you name a file. You save
`config.py` and you actually get `config.py.txt`, which Python cannot see. Nothing
warns you. The next command fails and it looks like broken code.

**The trick: create the empty file from the command line first, then open that file
and paste into it.** The name is then already correct and Notepad cannot change it.
Two commands per file — this is the pattern for every file in the kit:

**Type this into the black window.**
```
type nul > C:\ripple-build\ripple\config.py
```

```
notepad C:\ripple-build\ripple\config.py
```

Notepad opens, empty. Go to the chat and **use the copy button at the top of the
code block** rather than selecting it with the mouse — dragging across a long block
loses the last line more often than you would believe, and a Python file missing
its last line fails in a way that reads as the chat's fault. Paste, press Ctrl+S,
close the window. That is one file done.

**Two things not to do.** Never retype code by hand, and never tidy up the
indentation. In Python the spacing at the start of a line is not decoration — it is
what tells the language which lines belong inside which. Paste it exactly as given.

### When one file arrives in several parts

This happens, and it is the fiddliest twenty minutes of the whole evening, so it
is worth reading before you meet it. Some files are long enough that the chat
cannot give you the whole thing in one reply. It will say so, and hand you
"PART 1 OF 4" and so on. **Phase 4 always does this. Nothing else usually does.**

**All the parts go into ONE file, in order, one after another.** Not four files.
Not four folders. One file, exactly as if the chat had given it to you whole.

Here is the whole method, with your hands:

1. Make the empty file and open it, the same two commands as always:
   `type nul > C:\ripple-build\ripple\scanner\sqlread.py`
   then `notepad C:\ripple-build\ripple\scanner\sqlread.py`
2. Copy PART 1 with the copy button. Paste it into Notepad.
3. **Do not close Notepad. Do not press Ctrl+S yet.** Leave it open on screen.
4. Ask the chat for the next part. When it arrives, click into Notepad, press
   **Ctrl+End** — that jumps to the very bottom of what is already there — press
   Enter once, and paste the next part underneath.
5. Repeat until the last part is in.
6. **Now** press Ctrl+S, and close it.

**Count the parts before you save.** Ask the chat at the start how many there
will be, and check you have that many. A file missing its last part fails in a
way that reads exactly like bad code, and you will look for the mistake in the
wrong place.

**If a part arrives that starts at the top of the file again**, tell the chat:
*"do not start again from the top — carry on from the last complete line you
gave me, and tell me which line that was."* Pasting a restarted part underneath
gives you the same code twice and nothing will run.

---

## Checking that a phase worked

Every phase ends with one command, run from `C:\ripple-build`. You are reading it
for one word.

**Each phase prints its own command at the end of the chat's reply. Use that one.**
Here is what one of them looks like — this is Phase 1's, and it will not work
after any other phase, because every phase checks a different file:

**Type this into the black window.**
```
python -m pytest tests/test_production.py -q
```

- A row of dots and then **`passed`** — green. Move on to the next phase.
- **`failed`** or **`error`** — copy the whole red block and paste it straight back
  into the same chat window with *"this is what happened when I ran it"*. That
  window still has everything it wrote in front of it and will usually fix it in
  one go. Never start a fresh window for a failure; a fresh one knows nothing.
- **`no tests ran`** — the file is not where the command is looking. Almost always
  the `.txt` problem above, or the file went into the wrong folder.

---

## The two ways this goes wrong

**Drift.** Window 6 invents its own names for what window 4 already built, and
nothing fits together. The fix is the contract card: paste it at the top of *every*
window, every time, before the phase prompt. It is the shared memory the chats do
not have.

**Confident wrong answers.** A chat asked to build "a SQL impact analyser" will
build one that gives a clean green result whenever it fails to understand
something, because that is the obvious thing to build and it looks better in a
demo. A tool that reports "no impact" when what it means is "I could not read half
of this" is worse than no tool at all, because somebody will act on it. The rules
that stop it are in the contract card under **THE ONE RULE**. Do not trim them to
save space. They are the product.

---

## The build order

Three or four evenings, not two, and Phases 4, 5 and 8 are the hard ones. If you
get only as far as Phase 5, you already have the part that no other tool does.

**Three evenings, and this page says where each one ends.** The thirteen windows
split like this, by the counted sizes in the table below. The three evenings are
not the same number of windows, because they are not the same amount of work:

* **Evening one — windows 0, 1, 2, 3 and 4.** About 9,000 lines. Windows 1, 2
  and 3 go quickly. Window 4 is the one that eats the night.
* **Evening two — windows 5, 6 and 7.** About 6,300 lines. Three windows, all
  big, none of them as bad as window 4.
* **Evening three — windows 8 to 13.** About 7,050 lines, and window 12 is an
  hour of looking at a screen rather than saving files.

**Stop at an evening's end. Never stop in the middle of a window.** A window you
have not started costs you nothing to leave until tomorrow. A window you are
halfway through costs you the whole file, because tomorrow that window is gone
and no other window can finish what it started. So if it is late and you have
not begun the next one, stop where you are, even if the clock says you had time.

When you stop, search for **Closing down for the night** — there are two of
those pages, one at the end of each of the first two evenings. When you come
back, search for **Starting the next evening**.

**The sizes below were counted, not guessed.** Every phase in this document was
pasted into a fresh chat and what came back was measured. They are bigger than
you would expect, and the reason is simple: this document asks for a great many
rules, and it asks the chat to explain each one in the code. Both together add up.

**Phase 4 is the big one — about 4,900 lines.** No chat will give you that in
one go. It will stop part way through. That is normal and it is not broken: ask
it to carry on and it will, and the contract card already tells it to pick up
where it left off rather than start again. Expect three or four goes at that one
phase.

**That is the worst of it, but it is not the only phase it happens to.** Phases
5, 6 and 7 are big too — 2,600, 1,750 and 1,950 lines — and any of them may stop
part way through as well. Handle those exactly the same way. Phase 4's page is
where the method is written out: it tells you how to tell a reply that simply
stopped from one that quietly skipped a piece, and gives you the words to type
for each. Ctrl+F for **Two ways a reply goes wrong**.

**The words to type when a reply stops.** Click into the chat and send exactly
this: *"that was cut off — tell me the total line count, then give it to me in
numbered parts, and start again from the last complete line you gave me."* Then
join the parts into one file with your hands, the way **When one file arrives in
several parts** describes, above.

| # | The window builds | The files it writes | Roughly |
|---|---|---|---|
| 0 | *The contract card — not a build. Paste it at the top of every window.* | — | — |
| 1 | Settings, and the published-tables list | `ripple/paths.py`, `ripple/config.py`, `ripple/production.py`, `tests/test_production.py` | 1,100 lines |
| 2 | Walking the repository folder | `ripple/scanner/repo.py`, `tests/test_repo.py` | 1,450 lines |
| 3 | Templated SQL and scripting blocks | `ripple/scanner/templating.py`, `ripple/scanner/rescue.py`, `tests/test_templating.py` | 1,550 lines |
| 4 | Reading SQL into statements and usages | `ripple/scanner/dialectcompat.py`, `tests/test_dialectcompat.py`, `ripple/scanner/sqlread.py`, `tests/test_sqlread.py` | 4,900 lines — the big one |
| | **EVENING ONE ENDS HERE. Search for Closing down for the night.** | | **9,000 lines** |
| 5 | The catalogue, and following a column | `ripple/catalog.py`, `ripple/scanner/lineage.py`, `tests/test_lineage.py` | 2,600 lines |
| 6 | Reading the notification email | `ripple/notification.py`, `tests/test_notification.py` | 1,750 lines |
| 7 | Writing the summary and the reply | `ripple/narrative.py`, `tests/test_narrative.py` | 1,950 lines |
| | **EVENING TWO ENDS HERE. Search for Closing down for the night.** | | **6,300 lines** |
| 8 | Progress, saved history, and the web service | `ripple/progress.py`, `ripple/store.py`, `ripple/build_info.py`, `ripple/api.py`, `run.py` | 1,600 lines |
| 9 | The page and its styles | `web/index.html`, `web/styles.css` | 1,450 lines |
| 10 | The screens: notification, review, repository | `web/app.js` — this window creates it | 1,300 lines |
| 11 | The screens: findings, map, summary, reply, settings | `web/app.js` — appended to the same file | 2,200 lines |
| 12 | Starting it up, and the checklist that says it works | — | — |
| 13 | Packaging it as a program you can hand to somebody | `build.py` | 500 lines |
| | **EVENING THREE ENDS HERE. Ripple is built.** | | **7,050 lines** |

### What each file is for

You never need to hold all of this in your head. It is here so that when
something is wrong later you know which single file to open.

| File | What it decides |
|---|---|
| `ripple/paths.py` | Where things are, whether Ripple is running from source or packaged |
| `ripple/config.py` | Every setting: which folder to read, which flavour of SQL it is written in, how many steps to follow a column for, which folders to skip, how big a file to open |
| `ripple/production.py` | **Which table names count as the ones this team publishes** |
| `ripple/catalog.py` | What tables and columns exist, learned from the repository itself |
| `ripple/scanner/repo.py` | **Which files get opened**, and the SQL pulled out of ones that are not `.sql` |
| `ripple/scanner/templating.py` | Filling in placeholders, and unwrapping scripting blocks |
| `ripple/scanner/rescue.py` | Shapes the parser refuses, rewritten into ones it accepts |
| `ripple/scanner/dialectcompat.py` | Keeps Ripple working when the SQL reader changes its own wording between versions |
| `ripple/scanner/sqlread.py` | **Reading SQL properly**: what each statement builds, reads, publishes and uses |
| `ripple/scanner/lineage.py` | **Following the column**, and judging the answer: risk, coverage, what was missed |
| `ripple/notification.py` | Reading the notification, and the form you correct it on |
| `ripple/narrative.py` | The summary and the reply letter, with no AI |
| `ripple/progress.py` | What Ripple is doing right now, so a screen can say so |
| `ripple/store.py` | History of past analyses |
| `ripple/build_info.py` | One version number, and the build stamp on the settings screen |
| `ripple/providers.py` | Which AI company a pasted key belongs to, worked out from the key. Needed by `config.py` whether or not you build the reader |
| `ripple/ai.py` | The optional AI reader. Turns a pasted email into a filled-in form |
| `ripple/scanner/github.py` | Reading a repository over the network, for when there is no local copy |
| `ripple/api.py` | The web service: every address the screens call and what comes back |
| `web/app.js` | **Every screen** — all six steps, every card, every word |
| `web/styles.css` | Colours, spacing, fonts |
| `web/index.html` | The empty page the screens are drawn into |
| `run.py` | Starting it up |
| `build.py` | Packaging it into a folder you can hand to somebody |

**One thing to test before you invest an evening.** Two of these files are 800
lines long. Paste Phase 1 into a window and see whether you get complete files back
or something that trails off into "... rest of the implementation". If it
truncates, ask for the file in clearly labelled parts and paste them together — and
ask it to tell you the total line count first, so you know when you have all of it.

Every phase says where its files go, and the contract card makes the chat repeat it
back to you at the end of every reply. **If a reply does not end with a SAVE THESE
FILES block, ask for one before you save anything.** One file in the wrong folder
makes the next window fail for a reason that looks like bad code.

---

## Starting the next evening

You closed the laptop last night. Tonight the chat windows are gone, the black
window has forgotten which folder it was in, and nothing on the screen tells you
where you got to. This page puts you back, in five steps.

**Nothing you built last night lives in a chat window.** It lives in files on
your disk. That is the whole reason this kit makes you save every file by hand.
A chat window you have finished with is worth nothing tonight, and closing it
cost you nothing.

**1. Open a new black window and go to the folder.** Press the Windows key, type
`cmd`, press Enter. Then this, because a new window always starts somewhere else:

**Type this into the black window.**
```
cd /d C:\ripple-build
```

**2. Prove where you actually got to.** This runs every check you have built so
far, not only last night's:

**Type this into the black window.**
```
python -m pytest -q
```

- A row of dots and then **`passed`** — everything you have built is on disk and
  still works. Go on to step 3.
- **`failed`** or **`error`** — one of last night's files is half saved or in the
  wrong folder. Do not start tonight's window on top of it. The red block names
  the test file; find the phase that wrote that test in the table under **The
  build order**, and fix that phase first.
- **`no tests ran`** — you are not standing in `C:\ripple-build`. Run the `cd /d`
  command above again.

**3. See what is on disk, so you know which window you are on.**

**Type this into the black window.**
```
dir /s /b C:\ripple-build
```

Read the names against the third column of the table under **The build order**.
The last window whose files are all in that list is the last one you finished.
The next one down is where you start tonight.

**4. Read your own note from last night.**

**Type this into the black window.**
```
notepad C:\ripple-build\where-i-got-to.txt
```

It says the same thing as step 3, in your words, and it is the only place a name
you had to invent is written down.

**5. Open a fresh chat window and paste the card.** Same as every other window:

**Type this into the black window.**
```
notepad C:\ripple-build\card.txt
```

Ctrl+A, Ctrl+C, click into the new chat window, Ctrl+V, Enter. Then paste
tonight's phase prompt underneath and press Enter again. Nothing about this is
different because a night has passed — every phase in this kit starts with a
fresh window anyway.

### If last night stopped in the middle of a window

This is the expensive one, and Phase 4 is where it happens, because Phase 4 is
4,900 lines and arrives in four or five parts. You had parts 1 to 3 pasted into
an open Notepad and part 4 had not come yet. Tonight the window that was writing
them is gone.

**A fresh window cannot carry on from where the old one stopped.** It never saw
parts 1 to 3. Ask it to continue and it will cheerfully write you a part 4 — for
a file it has imagined, with its own names, in its own shape. Joined onto your
parts 1 to 3, that is two different programs in one file. It will not run, and
the error it gives you will point at a line that is perfectly fine, so you will
look for the mistake everywhere except where it is.

**So throw away the parts you have and ask a fresh window for the whole file
again, from PART 1 OF N.** It is an hour you did not want to spend, and it is
the cheapest of the choices in front of you.

1. Delete the half-written file. If it was `sqlread.py`:
   `del C:\ripple-build\ripple\scanner\sqlread.py`
   If you cannot tell which of that window's files are whole, delete every file
   that window was meant to write — the list is in the third column of the table
   under **The build order** — and take the phase from the top.
2. Open a fresh chat window. Paste the card, then that phase's prompt, exactly
   as if you had never started it.
3. Ask for it in parts before it starts: *"tell me the total line count first,
   then give it to me in numbered parts, starting at PART 1 OF N."* The longer
   words for this are under **When Phase 4 goes wrong**.
4. Join the parts into one file the way **When one file arrives in several
   parts** describes.

**Never join a fresh window's part onto last night's file, for any reason.** Half
a file from one window and half from another is the single most expensive mistake
in this kit, because nothing on your screen tells you that is what happened.

**Files from windows you FINISHED are safe.** This page is only about the one
window that was still writing when you stopped. Everything before it is on disk,
has passed its check, and needs no chat to remember it.

---

# PHASE 0 — the contract card

**You do not read this page. You copy it.** It is written for the chat, not for
you, and there is nothing in it you need to understand. It is long on purpose:
it is the only thing the twelve chat windows have in common, and every line of
it is there because leaving it out made two windows build things that did not
fit together.

**Do this once, now, before you start.** It saves you eleven awkward copies:

**Type this into the black window.**
```
type nul > C:\ripple-build\card.txt
```

```
notepad C:\ripple-build\card.txt
```

Notepad opens, empty. Come back here, press the **copy button at the top of the
block below** — the button, not the mouse, because dragging across something
this long loses the last line more often than you would believe — then paste
into Notepad, press Ctrl+S and close it.

From now on, every window starts the same way: open `card.txt`, select all
(Ctrl+A), copy (Ctrl+C), paste into the chat, press Enter. Then paste that
phase's prompt underneath and press Enter again. That is the whole of your job,
twelve times.

**How to tell it arrived whole.** The last line of the card is *"...I will put
it in the wrong place and the next chat will fail."* If the chat's window does
not end with that, it did not all go in — paste it again.

**`card.txt` is yours to edit, and once or twice it will need editing.** Twice
over, the card tells a window that if it genuinely needs a name the card does
not have, it must invent one and say so in a line at the top of its reply. When
a window does that, carrying the name to the other eleven is your job and
nobody else's. Open the file again:

**Type this into the black window.**
```
notepad C:\ripple-build\card.txt
```

Press Ctrl+End to get to the very bottom, type that one line in, press Ctrl+S
and close it. Every window you open after that then gets the name too. Nod and
carry on instead, and eight windows later nothing fits together — which is the
one thing this card exists to stop.

**Paste this into the chat.**
````text
You are helping me build a tool called Ripple, one file at a time, across
several separate chats. You cannot see the other chats, so this card is the
shared contract. Follow it exactly. Do not rename anything in it.

You also cannot see my files, run anything, or test anything. I am the only
one who finds out whether your code works, by saving it and running it, and
every round of that costs me real time. So never tell me something is tested,
verified or working -- say what you believe it does and what you are unsure
of. If you are guessing about how a library behaves, say which line you are
guessing about. A named doubt I can check in thirty seconds is worth far more
than confident prose.

WHAT RIPPLE IS
An upstream data team emails us: "we are changing MARKET_CODE in
CUSTOMER_DEMOGRAPHICS on 18 September." Ripple reads our own pipeline
repository and answers: what breaks, where, and what do we tell them.
A column rarely keeps its name — MARKET_CODE becomes mc, then mkt_cd — so a
word search is useless. Ripple parses the SQL and follows the rename chain to
the tables our team publishes.

THE ONE RULE THAT OVERRIDES EVERYTHING
Never claim more than was actually read.
- If files could not be opened, or could not be parsed, the headline, the
  summary and the drafted reply must all say so. Never "no impact, proceed as
  planned" over a repository that was only partly read.
- If nothing was read at all, say "nothing was scanned", never "no impact".
- Never invent a count, a percentage, or a progress bar. Every number on
  screen is something that was actually counted. Where there is genuinely no
  total, show the count and no fraction.
- Anything the reader could not follow is listed on screen with the file and
  the line, never dropped.
- Never show a green tick unless it is genuinely earned.
When in doubt the more cautious wording wins. A tidier screen that says less
is a worse screen.

STACK
Python 3.10 or newer — assume 3.10, so put "from __future__ import annotations"
at the top of every module. FastAPI + uvicorn + pydantic for the service, and
sqlglot 30.17.0 for the SQL: write against how that version behaves.

READ THE PARSE TREE THROUGH ONE SMALL MODULE, NOT DIRECTLY. sqlglot renames the
keys inside its own nodes between major versions, and the renames that matter
are SILENT -- the old key just returns None, so the code carries on and finds
nothing. Three of them switch off things this tool exists to do:

    Star.args["except"]        -> "except_"     SELECT * EXCEPT(col) stops
                                                being noticed, so a column
                                                dropped BY NAME is reported as
                                                carried through
    Merge.args["expressions"]  -> "whens"       every rename a MERGE makes
                                                disappears, and a MERGE is how
                                                a published table is loaded
    Select.args["from"]        -> "from_"       the check that decides which
                                                tables a SELECT * covers finds
                                                nothing

Nothing raises. Every test goes on passing and the answers go quietly wrong.

EVERY read of that kind goes in ripple/scanner/dialectcompat.py, and NOTHING
ELSE ANYWHERE IN RIPPLE reads one directly. Phase 4 builds that file and names
all nine functions; the three above are only the ones with the worst
consequences. Two more of them -- the TEMP-table property and the PIVOT and
UNPIVOT fields -- decide behaviour this kit spends whole pages on, and Phase 5
is a different window that needs the MERGE one again. Import it there rather
than reading the key a second time.

Pin the parser to one version in the project's requirements, and write tests
that fail LOUDLY when a key stops resolving OR when the installed version is not
the pinned one -- against the real parser, because the gap being guarded is
exactly the one between what the code expects and what the library returns.


The front end is plain HTML, CSS and JavaScript in three files — no build
step, no framework, no npm, no CDN, no TypeScript, no inline event handlers.
Tests with pytest.

FILE MAP (build order)
ripple/paths.py                where things live, running either way
ripple/config.py               settings, read from environment variables
ripple/production.py           which tables the team publishes
ripple/scanner/repo.py         walking the folder, holding files, word search
ripple/scanner/templating.py   filling {{placeholders}}, dropping scripting
ripple/scanner/rescue.py       shapes the parser refuses, rewritten on the way in
ripple/scanner/dialectcompat.py  reading parse-tree keys safely, whichever
                               parser version is installed - NOTHING ELSE MAY
                               READ THOSE KEYS DIRECTLY
ripple/scanner/sqlread.py      parsing SQL into statements and usages
ripple/catalog.py              tables and columns learned from CREATE
ripple/scanner/lineage.py      following a column, producing findings
ripple/notification.py         reading a .msg / .eml / pasted email
ripple/narrative.py            writing the summary and the reply, without AI
ripple/progress.py             what the engine is doing this second
ripple/store.py                saving analyses to SQLite
ripple/build_info.py           the one version number, and the build stamp
ripple/providers.py            which AI company a pasted key belongs to -
                               imported by config.py, so always built
ripple/ai.py                   the optional AI reader (reaches the network)
ripple/scanner/github.py       reading a repository over the network (optional)
ripple/api.py                  the web service
web/index.html web/styles.css web/app.js    the front end

DATA SHAPES THAT CROSS FILE BOUNDARIES — do not change these names
SourceFile  : path (repo-relative, forward slashes), abs_path, text, lang
Statement   : file, lang, line_offset, line_end, sql, target, sources
              (set of table names read), select (sqlglot Select or None),
              expr (sqlglot node), and these, every one defaulting to
              empty so an ordinary statement carries nothing extra:
                line_end        the last line of the file this statement
                                occupies. A finding is only ever pointed
                                at a line inside its own statement.
                whole_copy      the word the file used to copy a whole
                                table - COPY, CLONE, LIKE or RENAME
                star_note       what the file writes where the column list
                                should be, when a SELECT * is really a
                                placeholder filled in at run time
                guessed_columns names read back as columns by hand, so a
                                usage of one is never asserted as certain
                named_by        how the target was worked out when the
                                statement does not name it - "dbt",
                                "Dataform" or "file"
                built_as_text   the words the file used to run this
                                statement as text
                export_uri      where an EXPORT DATA delivers to
                script_var      the script variable this statement fills
ParsedRepo  : statements[], unreadable[], parsed_files (set of paths),
              opaque {path: [{line, text, sql}]}, runs_sql_from[],
              references[], procedure_calls[]
Usage       : kind, column, alias, detail, certain, via_star
              via_star is true when the column only leaves the statement
              because of a SELECT *. It really is carried, but the column
              list is written down nowhere, so every finding past one says
              it was worked out rather than read.
              kind is one of: filter, join_key, ranking, dedup_key,
              transform, aggregation, sort, layout, pivoted, excluded,
              renamed, dropped, retyped, select, star

A finding, as JSON sent to the browser:
  {inter, from, attr, roots[], alias, logic, mode, impact, breaking,
   noLocalFix, file, lang, lines[{n, t, hit}],
   certain, viaStar, copiedBy, builtAsText, feed, inferredHops, whole,
   starKnown}
  inter         the intermediate table THIS hop builds, as a person reads it.
                "" when the hop builds no table anybody can name. In Python the
                field is inter_table; one function maps the whole row to this
                JSON, and that is where the renaming happens
  from          the table this hop READS. "from" is a Python reserved word, so
                the field is from_table in Python and becomes "from" in the same
                mapping function. Never write from= anywhere
  attr          the column's name AT THIS HOP, after every rename so far
  roots[]       the original column names this hop descends from, so a screen
                can say which of the changed attributes led here
  alias         the name this hop gives the column onwards, "" if unchanged
  logic         one of the fifteen Usage kinds above, as the word the screen
                shows: filter, join_key, ranking, dedup_key, transform,
                aggregation, sort, layout, pivoted, excluded, renamed, dropped,
                retyped, select, star
  mode          how the whole statement uses the column when several usages
                land on one row, worked out from those usages by one function.
                Same fifteen words, the most serious one winning
  impact        one plain-English sentence a non-engineer can act on. Never a
                code word, never a stack trace
  breaking      true when the change actually stops this statement working
  noLocalFix    true when nothing in THIS file can fix it — a ranking or a
                dedup key. The only route to risk "high"
  certain       false when anything about this hop was worked out rather than
                read. Any uncertainty upstream makes every hop past it uncertain
  lines[]       the few lines of code the screen shows. n is the 1-based line
                number in the file, t is the text of that line, hit is true for
                the one line the finding points at
  viaStar       this hop is carried by a SELECT *, so the table it builds has
                no column list Ripple can read
  copiedBy      "" when the file really does say SELECT *; otherwise the word
                it used to copy a whole table instead — COPY, CLONE, LIKE or
                RENAME. No screen may tell somebody the file says SELECT *
                when it does not
  builtAsText   "" for SQL written out in the file; otherwise the words the
                file used to run it as text, so the row can admit that the
                line it points at holds a quoted string
  feed          "" for an ordinary statement; otherwise where this EXPORT DATA
                delivers to
  inferredHops  how many SELECT * hops are behind this row, counting this one.
                Zero means every step to here was written down in the SQL
  whole         true when the row is about the TABLE itself rather than a
                column of it — see WHOLE TABLES in Phase 5. attr is then the
                words "whole table", alias is "", logic says how the statement
                takes the table ("Reads this table", "Joined to this table",
                "Copied whole by COPY", "Exported from this table") and mode
                is "Whole table"
  starKnown     true when this hop is a SELECT * whose column list is written
                down after all — the table it copies has its columns listed,
                so the built table's list was filled in from there (see
                catalog.derived in Phase 5). Read, not inferred: inferredHops
                does not count it, and viaStar stays true

A scan result, as JSON sent to the browser:
  {attributes[], groups[], reached[], other[], graphs[], unreadable[],
   mentionsOnly[], heldOnline[], pathTooLong[], starTables[], cutShort[],
   mergedNames[], wildcardNames[], namedByFile[], builtAsText[],
   twoDefinitions[], skippedInFolders[], skippedFolderNames[],
   fileTypesUnopened[], stopsLoading[], referencedHere[], feeds[],
   stopsLoadingCapped, maxHops, filesScanned, filesMatched, risk,
   lookupFailed, coverage{}, stats{}}
  fileTypesUnopened = [{ext, count}], most first, then by extension
  coverage = {complete, gaps[{count, what}], filesMatched, filesUnread}
  risk is one of: high, medium, low, unknown, none
  "none" is the only thing this tool sells, so it is the one word that must
  never cover a gap: see Phase 5.
  stats = {productionTables, tablesReached, intermediateTables,
           attributesImpacted, filesWithImpact, breakingUsages,
           couldNotRead, neverOpened, tablesNotVisible, inferredFindings,
           trailsCutShort, productionStopsLoading, feedsBroken, wholeTables}
  wholeTables counts the items asked about that were whole tables rather than
  columns; the screen names its counted card "Tables and attributes impacted"
  when it is not zero.
  attributes[] = one entry per thing asked about: {table, attr, found, files,
              mentionedIn, reachesProduction, endsAt[], cutShortAt[],
              notVisible[], inferred, nameInTables, tablesRead, lookupFailed,
              tableColumns[], uncertain} — and for a whole table also
              whole: true, readers (statements that read the table itself)
              and builtHere (whether anything in the repository builds it).
  graphs[]  = per attribute {attr, table, branches[], endBranches[]}, each
              branch a list of boxes {name, kind, alias, prod?, cut?,
              inferred?, how?, twoDefinitions?, namedByFile?, builtAsText?}.
              A whole-table walk adds whole: true on the graph and on every
              box, with alias "".
  groups[]  = tables ON the published list, each {prod, note, rows[]}
  reached[] = tables the chain ends at that are NOT on the published list.
              These must never be thrown away: a real breaking impact shown
              as a clean result because the tables are not called _PROD is
              the exact failure this tool exists to prevent.
              THE SAME SHAPE AS groups[], and for the same reason:
              {prod, note, cut, rows[]} with the FULL rows, every finding,
              file, line, code snippet and impact sentence. A list of bare
              table names is not "kept" -- it tells somebody six tables are
              hit and nothing whatever about how, which is a list nobody can
              act on. note says why it is here, in words: "Last table in the
              chain - not matched by your production naming rule". cut is
              true only where the hop limit stopped the trail.
  other[]   = real usages in code that builds no table Ripple can name
  productionStopsLoading and feedsBroken are counted APART from
  productionTables. Three different kinds of impact, and one number covering
  more than one of them is a number that means none of them.
  attributesImpacted counts the attributes that were actually CONFIRMED, not
  every column name a finding touches: a column renamed twice on the way down
  is one attribute, and the card says "of those you confirmed".
  tablesNotVisible and inferredFindings are two sizes of the same problem —
  "3 tables Ripple could not see inside" and "40 findings that depend on
  them" — so both are counted.

FUNCTION MAP — the names that cross a window boundary
Build the insides of your own file however you like. These names are the seams
between windows, and a window that renames one silently breaks a window it
cannot see. Nothing raises; the import simply fails, or worse, a different
function is found. Use them exactly. If you need one that is not here, invent
it and SAY SO in one line at the top of your reply so I can carry it across.

IMPORT STYLE: absolute, everywhere. "from ripple.scanner.sqlread import
parse_repo", never "from .sqlread import parse_repo".

  ripple/paths.py
    web_dir() -> Path          static files, running from source or packaged
    data_dir() -> Path         where ripple.db is allowed to live

  ripple/config.py
    settings                   the module-level Settings instance. There is no
                               get_settings() function; import the object.
    class Settings
      fields   repo_path repo_label repo_branch sql_dialect max_hops
               code_extensions skip_dirs max_file_bytes max_upload_bytes
               db_path production_text
      methods  branch() production() set_production(text) has_production()
               is_production_table(name) production_rule()

  ripple/production.py
    DEFAULT_PRODUCTION         suggestion text only, NEVER applied
    parse(text) -> ProductionRule
    family_of(name) -> (family, how)     how is "shard", "placeholder" or ""
    check_against_repo(rule, index, parsed) -> dict
    class ProductionRule
      methods  matches(name) match_how(name) names() patterns() is_empty()
               one_line() to_dict()
               match_how answers "name", "glob", "suffix", "shard",
               "placeholder" or "" — matches(name) is bool(match_how(name))

  ripple/scanner/repo.py
    class SourceFile           path abs_path text lang;  lines()
                               lang is one of: sql sqlx ddl hql py scala java
                               sh xml yaml — the extension without its dot
    class Match                file, line_no (1-based), line, name
    class RepoIndex            files skipped root held_online too_long
                               in_skipped_dirs unknown_ext skipped_dir_names
      methods  build(root, cfg=None, on_progress=None)   a classmethod
               search(names: list[str]) -> list[Match]
               files_mentioning(names: list[str]) -> list[SourceFile]
               get(path) -> SourceFile | None
      skipped[] entries are {"file": path, "reason": plain English}
      held_online[], too_long[], in_skipped_dirs[] hold plain paths
      unknown_ext is {extension: count}
    statements_for(f) -> list[(sql, line_offset)]     line_offset is 0-based
    sql_file_refs(f) -> list[dict]   each {"name": path named, "line": 1-based}
    looks_like_unread_sql(f, blocks) -> bool
    written_tables(f) -> list[str]
    unopened_code_types(unknown_ext) -> dict
    LANG_BY_EXT

  ripple/scanner/templating.py
    has_placeholders(text) -> bool     describe(text) -> str
    placeholder_names(text) -> set     fill_placeholders(text) -> str
    has_blocks(text) -> bool           unwrap_blocks(text) -> str
    renderings(text) -> list[str]      every way the file runs

  ripple/scanner/rescue.py
    rescue_text(text) -> str           the one entry point. NOT rescue_sql.
    export_targets(text) -> list[(line, uri)]

  ripple/scanner/dialectcompat.py     NOTHING ELSE MAY READ A PARSE-TREE KEY
    RENAME_NODE   SET_OPERATION
    from_of(select)        star_except(star)     star_replace(star)
    is_unpivot(pivot)      pivot_fields(pivot)   pivot_columns(pivot)
    is_temporary(stmt)     merge_whens(merge)    set_branches(node)
    output_names(query)

  ripple/scanner/sqlread.py
    short_name(t) dataset_of(t) canonical(t) is_wildcard(t)
    wildcard_match(pattern, name) -> "shard" | "family" | "both" | ""
    same_table(a, b) -> bool
    reads_metadata(stmt) -> bool
    class Usage        the DATA SHAPES entry above;  label
    class Statement    the DATA SHAPES entry above
    class ParsedRepo   the DATA SHAPES entry above
      methods  reading(table) wildcards_covering(t) wildcards_covering_how(t)
               ambiguous_names() datasets_for(n) spellings_for(n)
               display(table) rebuilt_in(t) statements_in(path)
    parse_repo(index, cfg=None, on_progress=None) -> ParsedRepo
    suffix_verdict(stmt, table) -> "reads" | "maybe" | "excluded"
    output_names(stmt, column, limit=6) -> list[str]
    usages_of(stmt, column, table="") -> list[Usage]
    star_sources(stmt) -> list[(star, tables[])]   each star in the statement's
                                                    own projection, with the
                                                    tables it covers
    mode_of(usages) -> str
    locate(f, column, kind, line_offset=0, line_end=None) -> int
    snippet(f, hit_line, note, before=2, after=2) -> list[dict]

  ripple/catalog.py
    class Catalog      tables defined_in gaps derived
      methods  has_table(t) columns(t) has_column(t, c) listed_in(t) to_dict()
    build_catalog(parsed) -> Catalog

  ripple/scanner/lineage.py
    trace(index, parsed, upstream, change_type="unknown", cfg=None,
          on_progress=None, catalog=None) -> ScanResult
    catalog is the Catalog the service already built; built inside when it
    is not handed in. It is what says whether a SELECT * hop has a column
    list Ripple can read.
    WHOLE_TABLE = "whole table"     the attr every whole-table row carries
    upstream entries are {table, attrs[], whole}; whole: true walks the
    table itself — see WHOLE TABLES in Phase 5
    class ScanResult   to_dict() produces exactly the scan-result JSON above

  ripple/notification.py
    class Notification  subject body from_name from_email attachments
                        source_kind warnings;  text()
    read_upload(filename, raw) -> Notification
    read_pasted(text) -> Notification
    extract_by_rules(n, catalogue) -> dict
    names_the_whole_table(text, table) -> bool

  ripple/narrative.py
    summarise(scan, vals) -> dict      NOT write_summary
    draft_reply(scan, vals, summary) -> dict
    days_until(iso) -> int | None

  ripple/progress.py
    start(job, label="")  step(done, total, label="")  finish()
    snapshot() -> dict
    reader(job) -> on_progress    the callback every slow call is handed

  ON_PROGRESS — ONE SHAPE, EVERYWHERE, AND IT IS NOT OBVIOUS
    on_progress(done: int, total: int, label: str = "")
  Three arguments, in that order, from every caller: repo.py while it walks the
  folder, sqlread.py while it parses, lineage.py while it follows the column.
  total is 0 where there is genuinely no total to give — never a guess, and
  never a path.

  Measured on a build made from this kit: the window that walks the folder
  called on_progress(files_read, path) and the window that made the callback
  expected (done, total, label). The path landed in the total slot,
  int() blew up on it, and /api/health answered 500 — so the very first screen
  showed nothing at all, over a repository that read perfectly well. A callback
  is a name that crosses a window like any other, and its ARGUMENT ORDER
  crosses with it.

  ripple/store.py
    save(vals, scan, summary, mode, cfg=None) -> int
    listing(cfg=None, limit=50) -> list[dict]
    get(analysis_id, cfg=None) -> dict | None
    set_status(analysis_id, status, cfg=None) -> bool
    STATUSES = ("New", "In progress", "Verified", "Closed")

  ripple/build_info.py
    VERSION            build_info() -> dict

  ripple/providers.py                built even if you never build the reader
    detect(key) -> dict | None        name_of_unsupported(key) -> str
    by_id(provider_id) -> dict | None is_chat_model(model_id) -> bool
    rank_models(provider, models) -> list[str]

  ripple/ai.py                                      OPTIONAL - reaches network
    read_email(text, cfg=None) -> dict
    write_summary(payload, cfg=None) -> dict
    write_reply(payload, cfg=None) -> dict
    check_key(cfg=None) -> dict       list_models(cfg) -> list[str]
    class AIUnavailable(Exception)

  ripple/scanner/github.py                          OPTIONAL - reaches network
    parse_repo_ref(text, branch="") -> RepoRef
    describe(ref, token, cfg=None) -> dict
    download_archive(ref, token, cfg=None) -> bytes
    index_from_archive(data, cfg=None) -> (RepoIndex, dict)
    connect(repo_text, token, branch="", cfg=None) -> dict

ROUTE MAP — every address, and nothing else
The window that writes api.py and the two that write the screens cannot see
each other. A screen calling an address the server does not serve is a button
that does nothing, and no test catches it.

EVERY BODY IS WRITTEN OUT. The window that writes api.py turns these into its
request models; the windows that write the screens send exactly these keys. A
body the server does not recognise comes back 422 with a wall of validation
text, and the screen shows nothing at all.

  GET   /                       the page
  GET   /api/health             settings, catalogue summary, build, ai block
  GET   /api/progress           what the engine is doing this second
  GET   /api/catalog            tables and columns learned from the repository
  POST  /api/reindex            read the folder again.        no body
  GET   /api/production         the published-table rule in force
  POST  /api/production         set it.                       {text}
  POST  /api/production/read    read a pasted list without setting it.  {text}
  POST  /api/repo/folder        point at a local folder.      {path}
  POST  /api/repo/connect       a GitHub repository (optional).
                                {repo, branch, token} — blank branch means the
                                default one, blank token means keep the one set
  POST  /api/repo/disconnect    back to the local folder.     no body
  POST  /api/read-email         the notification. multipart with the field
                                named "file", or {text} for a paste
  POST  /api/scan               run the analysis.
                                {upstream: [{table, attrs: []}],
                                 changeKind: str,
                                 maxHops: int | null}
                                Each upstream entry may also carry
                                whole: bool. whole: true means the TABLE
                                itself is changing and every statement that
                                reads it is followed; attrs is then empty.
                                An entry with attrs empty AND whole false is
                                REFUSED with a 400 whose detail says to add
                                the attribute or tick "Whole table" — never
                                scanned as nothing, which came back as a
                                clean "no usage found".
                                UPSTREAM IS A LIST OF OBJECTS, NOT A LIST OF
                                STRINGS. One entry per upstream table, each
                                carrying the attributes being changed on it.
                                maxHops is null for the setting in force, and
                                a number only for the "follow it deeper" button
                                on a trail that was cut short.
                                -> the scan result JSON above
  POST  /api/summary            {scan, vals, useAI: bool}
                                -> {summary, reply}
  POST  /api/history            save one.  {vals, scan, summary, mode}
  GET   /api/history            list saved analyses
  GET   /api/history/{id}       open one
  PATCH /api/history/{id}       change its status.            {status}
  GET   /api/file               one file's text, for the code snippet.
                                ?path= and the line to centre on
  POST  /api/ai/check           really call the selected model.  no body
  POST  /api/ai/connect         {key, model} — blank key means keep the one
                                already set, blank model likewise
  POST  /api/ai/forget          forget the key.               no body

THESE THREE ARE ALWAYS BUILT, even in a build with no AI reader in it. What is
optional is ripple/ai.py, the thing behind them. Without it the three routes
still exist and answer "there is no reader in this build", and /api/health
reports ai.available false so the settings screen hides the key box before
anybody presses anything.

Written that way round because "optional" is the one thing two windows that
cannot see each other are guaranteed to disagree about. Measured: the window
building the server took the "leave it out" branch and the window building the
screens built the key box, so three addresses were called that nothing served,
and the only sign of it was a button that did nothing.

There is no /api/notification, no /api/analyses, no /api/ai/key and no
/api/ai/providers. The provider prefixes come down inside /api/health.

PAGE MAP — the element ids and templates the screens look up
Phase 9 writes index.html. Phases 10 and 11 write the JavaScript that reaches
into it. They are three different windows, and an id that does not match
produces NO ERROR AT ALL: getElementById returns null, the screen draws
nothing, and the console stays clean. Measured: a build where the page called
its templates t-step1 and the script asked for tpl-step-1 came up with a
perfect sidebar and a completely blank main pane on every screen.

  id="view"          the one element every screen is drawn into
  id="steps"         the numbered rail down the left
  id="status"        the small line of dots at the bottom of the rail
  id="hTitle"        the page heading, rewritten per step
  id="hSub"          the line under it
  id="hRight"        the right-hand side of the header strip
  id="navHistory"    the Past analyses button
  id="navSettings"   the Settings and checks button
  id="drop"          the area a notification file is dropped on
  id="file"          the hidden <input type="file"> behind it

  id="t-step1" ... "t-step7"    ONE <template> PER STEP, named exactly like
                                that. Not tpl-step-1, not step1, not
                                template-step-1. The script clones them by
                                't-step' + n

Everything else inside a template is found by a data-x attribute, not an id,
so the two halves only have to agree on this list. Reach for an element with
  const x = (root, name) => root.querySelector(`[data-x="${name}"]`);
and give every field the page owns a data-x name, so Phase 9 and Phase 10 are
naming the same things in the same way.

CLASS NAMES THE PAGE SHELL OWNS. These belong to the frame the page is drawn
in, not to anything inside a screen. NOTHING BUILT BY THE SCRIPT MAY CARRY ONE
OF THEM, and no rule for them may be written so that it can reach inside the
screen:

    side  main  head  scroll  col  shell  wrap

Measured, on a build made by thirteen windows that could not see each other:
one window styled .side as the navy sidebar -- position:fixed, top 0, left 0,
full height -- and another window, meaning "a card at the side of this step",
wrote <section class="card side"> inside a screen. It became a fixed panel over
the whole left edge and covered the numbered rail completely. Every step number
gone, on the first screen, with no error anywhere and every test still passing.
An id that clashes draws nothing and is obvious. A CLASS that clashes draws the
wrong thing, in the wrong place, over something else.

So: the window that writes the stylesheet scopes every shell rule to the shell
itself -- body > .side, never a bare .side -- and the windows that write the
screens pick a different word. A card beside something is .aside or .beside.

HOW web/app.js IS WRITTEN — Phase 10 starts the file, Phase 11 appends to it,
and they are two windows that cannot see each other. So the way the file is
written is fixed here, not decided twice.

  BUILD DOM NODES. NEVER ASSEMBLE HTML STRINGS. No innerHTML, no
  '<div class="...">' + value + '</div>', anywhere, in either half. It is not
  only the escaping: measured on a build made from this kit, Phase 10 wrote
  node builders and Phase 11 wrote string builders, so one file held two
  different programs, Phase 11 used Phase 10's element helper zero times out of
  2,060 lines, and a single unclosed bracket inside one of those long
  concatenations stopped the whole file parsing.

  PHASE 10 DEFINES THESE, AT THE TOP, AND PHASE 11 USES THEM RATHER THAN
  WRITING ITS OWN:
    el(tag, opts, ...children)   opts: {class, text, html?, data:{}, on:{}}
    x(root, name)                the data-x lookup above
    api(path, body)              fetch wrapper, returns the parsed JSON
    render()                     redraw the current step
    S                            the one state object
  Phase 11: if you find yourself about to write esc(), say(), str() or any
  other helper of your own, it is because you are building strings. Build nodes
  and you do not need any of them - textContent escapes by itself.

  ONE CHECK CATCHES A BROKEN BRACKET BEFORE THE BROWSER DOES, and I have no
  other way of finding one: an unparsed file simply leaves every screen blank.
  So in Phase 11, put this line in the THEN RUN block at the end of your reply,
  where I will see it:
      node --check web/app.js
  and say in that same block that if node is not on my machine I should open the
  page, press F12 and read the Console tab instead, where an unparsed file shows
  as one red line on load.

HOUSE STYLE
- Comments explain WHY, not what. A comment restating the code is noise; a
  comment recording the mistake the line prevents is worth keeping.
- Every string shown on screen is plain English a non-engineer can act on.
  Not "ParseError at line 42" but "1 of 14 statements in this file could not
  be read — line 42 · CREATE OR REPLACE PROCEDURE ...".
- British spelling. No emoji. No exclamation marks.
- Type hints on function signatures. Dataclasses over dicts internally.
- Every table and column name in examples and tests is invented. Never use a
  real-looking internal name.

WHERE THINGS GO — the project root is the folder I run python from
  ripple-build/
    run.py
    build.py                 (Phase 13 -- packaging)
    ripple/
      __init__.py            (empty file, but it must exist)
      paths.py  config.py  production.py  catalog.py  notification.py
      narrative.py  progress.py  store.py  api.py
      build_info.py
      providers.py           (always built -- config.py imports it)
      ai.py                  (optional -- reaches the network)
      scanner/
        __init__.py          (empty file, but it must exist)
        repo.py  templating.py  sqlread.py  lineage.py
        rescue.py  dialectcompat.py
        github.py            (optional -- reaches the network)
    web/
      index.html  styles.css  app.js
    tests/
      test_production.py  test_repo.py  test_templating.py
      test_sqlread.py  test_lineage.py  test_notification.py
      test_narrative.py  test_dialectcompat.py
    mockrepo/                (a small fake pipeline to test against)

BEFORE YOU ANSWER, CHECK YOUR OWN WORK
You are a capable model and you will be tempted to improve on this brief. The
trouble is that eleven other windows are building against it and none of them
can see what you decided. So before you reply:
- Re-read DATA SHAPES above and confirm every name that crosses a file
  boundary matches it exactly. If you genuinely needed one that is not there,
  invent it, but SAY SO in one line at the top so I can carry it to the other
  windows. A silent invention is the single most expensive thing that can
  happen here.
- Confirm every file is complete. No "...", no "rest unchanged", no TODO, no
  placeholder, no function body left as pass.
- Confirm you added nothing I did not ask for. No extra packages, no logging
  framework, no command-line options, no retry logic, no caching layer,
  no abstraction "for later". Cleverness in one window is a mismatch in the
  next.
- Confirm the tests would actually FAIL if the behaviour were missing. A test
  that passes against an empty function is worse than no test, because it
  makes a missing feature look finished.
- Confirm it runs on Python 3.10.
If something in the prompt genuinely contradicts this card, stop and ask me
instead of choosing. The question costs me a minute. A wrong guess costs me a
whole window.

WHAT I WANT BACK
Complete files, ready to save. No "...rest unchanged", no placeholders, no
TODOs, no function body left as pass.

Some of these files are 800 lines and may be longer than one reply can hold.
Before writing a long file, say how many lines you expect it to be. Then, if
it will not fit, give it in clearly labelled parts -- PART 1 OF 3 and so on --
each part ending at a sensible boundary rather than mid-function, and tell me
in what order to paste them. If a reply is cut off, do not restart the file
from the top when I ask you to continue: carry on from the last complete line
and tell me which line that was.

END EVERY REPLY WITH A BLOCK EXACTLY LIKE THIS, and nothing after it:

  SAVE THESE FILES
    ripple-build/ripple/config.py          <- the first code block above
    ripple-build/ripple/production.py      <- the second code block above
    ripple-build/tests/test_production.py  <- the third code block above
  FOLDERS THAT MUST EXIST FIRST
    ripple-build/ripple/   ripple-build/tests/
  EMPTY FILES TO CREATE IF THEY ARE NOT THERE YET
    ripple-build/ripple/__init__.py
  THEN RUN
    cd ripple-build
    python -m pytest tests/test_production.py -q

Paths are always relative to the project root and always use forward
slashes. Name every file you produced, in the order you produced it, and say
which code block is which. If you split one file into parts, say so and say
what order to paste them in. I am saving these by hand, so if you are vague
about the path I will put it in the wrong place and the next chat will fail.
````

---

# PHASE 1 — settings, and the published-tables list

**Saves to:** `ripple-build/ripple/paths.py`, `ripple-build/ripple/config.py`,
`ripple-build/ripple/production.py`, `ripple-build/tests/test_production.py`

**Those four are written the chat's way. What you type is different.**
`ripple-build/ripple/paths.py` and `C:\ripple-build\ripple\paths.py` are the
same place: put `C:\` on the front and turn every slash the other way. So the
first file on that line is these two commands, and every other file follows the
same shape:

**Type this into the black window.**
```
type nul > C:\ripple-build\ripple\paths.py
```

```
notepad C:\ripple-build\ripple\paths.py
```

Every "Saves to" line in this kit, and every SAVE THESE FILES block the chat
sends back, is written the chat's way. Everything you type into the black window
is written yours. A path typed the wrong way round makes the next window fail
for a reason that looks like bad code.

**One block in the reply is not a file to paste into.** Every reply ends with a
short list headed *EMPTY FILES TO CREATE IF THEY ARE NOT THERE YET*, naming
things like `ripple-build/ripple/__init__.py`. Those files are meant to stay
empty. They are the one exception to the two-command pattern: for those, and
only those, run the first command — the `type nul >` one — and stop there. Do
not open them in Notepad. There is nothing to paste, and being empty is the
whole point of them. You already made the two Ripple needs back in **Making the
folders**, so most evenings this block is nothing to do.

**Paste this into the chat.**
````text
[PASTE THE CONTRACT CARD FIRST]

Build ripple/paths.py, ripple/config.py, ripple/production.py and
tests/test_production.py.

--- ripple/paths.py

Small, and first, because everything else asks it where things are. Ripple has
to run two ways: as `python run.py` while it is being built, and later as a
packaged program with no folder of source files around it. Anything that
assumes the second case looks like the first fails silently, so the guessing is
done here, once.

  frozen()   -> bool   True when running as the packaged program. It is
                       getattr(sys, "frozen", False).
  app_dir()  -> Path   The folder a person actually sees. Packaged, the folder
                       holding the .exe: Path(sys.executable).resolve().parent.
                       From source, the project root.
  web_dir()  -> Path   Where the three front-end files are. Packaged,
                       Path(sys._MEIPASS) / "web", because the packager unpacks
                       bundled files to a folder of its own choosing and
                       _MEIPASS is where it says it put them. From source, the
                       web folder beside the code.
  data_dir() -> Path   Where the history database goes. app_dir() both ways;
                       create it if it is missing.

Nothing else in Ripple may work out a path for itself. Two rules follow, and
both exist because breaking them fails quietly rather than loudly:
  The front end is found with web_dir(), never by walking up from __file__.
  Packaged, that walk lands somewhere real but empty, so every route still
  answers and the browser shows a blank white page — which reads as broken
  code rather than as a folder that moved.
  The database is written under data_dir(), never beside the code. Packaged,
  beside-the-code is inside the program's own internals: rebuilding destroys
  every saved analysis, zipping the folder to send to somebody sends your
  saved analyses too, and a read-only location fails the save without saying
  so.

This file needs no test of its own; Phase 13 exercises it.

--- ripple/config.py

A Settings dataclass with a module-level `settings` instance. Every field has
a default read from an environment variable, so a laptop, a demo host and a
locked-down machine differ only by environment. Fields:

  repo_path, repo_label
  repo_branch          EMPTY, and read off the folder when it is empty. Not
                       "main". A folder on somebody's disk may be a copied-out
                       git checkout, in which case .git/HEAD holds the real
                       branch and it is worth showing, or it may be a plain
                       folder, in which case there is no branch at all.
                       Defaulting to "main" put "Branch main" on the Repository
                       step over every folder on earth: specific,
                       checkable-looking, and true of nothing.
  sql_dialect          ONE default, and it is the literal string "bigquery".
                       Write it out: sql_dialect defaults to "bigquery", read
                       from RIPPLE_SQL_DIALECT if that is set. Do not leave it
                       generic, do not leave it blank, and do not let any second
                       copy of Ripple pick its own.

                       This is not a cosmetic setting. Read as generic, a
                       BigQuery-ism the parser does not recognise becomes an
                       unreadable statement, the chain running through it is
                       never followed, and the answer comes back CLEANER than
                       the truth. That is the one failure this whole tool
                       exists to prevent, arriving through a dropdown.

                       Two builds of Ripple once disagreed about exactly this -
                       one defaulted to generic, the other to bigquery - so the
                       same folder was read as two different languages
                       depending which one somebody opened. Neither build's
                       tests noticed, because each only ever asked itself.
  max_hops             DEFAULT ZERO, and zero means follow until the code runs
                       out. Not "follow nothing" — read that way round and
                       Ripple stops at the first hop and reports every chain as
                       ending immediately.

                       A counter here reports itself as a fact about the
                       warehouse. "The chain ends here and does not reach
                       production" is a sentence about a setting wearing the
                       clothes of a sentence about somebody's data, and the two
                       are indistinguishable on screen. Measured on a 36-hop
                       chain: ten renames cut the trail short, twenty cut it
                       short, and twenty-five cut it short as well — three whole
                       scans, three identical empty answers, and no number a
                       person could choose that produced one.

                       Following to the end is safe because the walk already
                       carries a set of every (table, column) pair it has been
                       through, so a ring of tables closes on itself whatever
                       any counter says. Measured on a real warehouse of 7,304
                       files: 10.6 seconds to the end against 10.5 at ten hops,
                       finding the same tables plus the ones past the limit.

                       A limit somebody sets ON PURPOSE is still obeyed, and a
                       trail stopped by it is reported as stopped rather than as
                       a chain that ended. Zero is a REAL request, not a missing
                       one, so test it with "is not None", never "if value".
  code_extensions      .sql .sqlx .ddl .hql .py .scala .java .sh .xml .yaml
                       .yml  —  .sqlx is Dataform, Google's own way of writing a
                       BigQuery pipeline. Leave it out and a whole Dataform
                       repository is never opened, never read and never counted,
                       and the scan reports no lineage anywhere in it.
  skip_dirs            .git .venv venv node_modules __pycache__ target build dist
  max_file_bytes       2_000_000
  max_upload_bytes     25_000_000
  db_path              defaults to paths.data_dir() / "ripple.db", never a
                       path worked out from this file's own location
  production_patterns  tuple of recognised entries — what is matched against
  production_text      the raw paste, kept exactly as it arrived so the box
                       can be opened and edited again rather than handing
                       somebody back a tidied version of their own list

Environment variables: RIPPLE_REPO, RIPPLE_REPO_LABEL, RIPPLE_SQL_DIALECT,
RIPPLE_MAX_HOPS, RIPPLE_PROD_TABLES, RIPPLE_DB.

**RIPPLE_REPO is the one that decides whether this was worth building.** It is
the folder Ripple reads. Left unset it falls back to `mockrepo` — the small
practice pipeline from Phase 12, which exists only to prove the machinery runs.
A Ripple pointed at the practice pipeline answers questions about the practice
pipeline, confidently and correctly and about nothing anybody cares about.

**There is also a box for it on the settings screen**, and Phase 10 builds it —
type a folder, press *Read this folder*, and Ripple reads that one instead. It
was not there at first, and the build was very nearly useless without it: on a
laptop, "edit a file and restart" is not a way to choose anything.

That box holds the choice only while Ripple is running. There is nowhere for
this build to write it down — the same is true of the published-table list, the
GitHub token and the AI key — and the line under the button says so rather than
letting somebody believe tomorrow's Ripple will still be reading their folder.

So `RIPPLE_REPO` is the one that lasts. In the batch file from the end of this
kit, one line above the rest:

```
set "RIPPLE_REPO=C:\work\our-pipeline"
```

or, for one run from a Command Prompt:

```
set RIPPLE_REPO=C:\work\our-pipeline
python run.py
```

Have `run.py` print the folder it is about to read, every single time, before
anything else — it already prints the dialect and the address. Somebody who
forgets this variable gets a full, confident, entirely irrelevant answer, and
the printed folder is the only thing standing between them and acting on it.

**And check the folder exists before starting.** A path with a typo in it is not
an empty repository; it is a mistake. Ripple already prints a WARNING when the
folder is not there — keep it, and make the batch file refuse to start at all
rather than scan nothing and report nothing found.

Methods: production() returning the parsed rule (cached, because it is asked
once per table visited on every hop of every scan); set_production(text);
is_production_table(name); production_rule() returning a SHORT one-line
summary — two hundred pasted names do not fit on a line, so a long list is
counted ("44 table names and 1 pattern (_PROD)") while a short one is shown
in full.

--- ripple/production.py

This is the important file. It decides which tables count as "published by
our team", which decides whether a finding counts as production impact —
which is what the headline, the risk level and the drafted reply are all
built from. Getting it wrong turns a change that really breaks three
published tables into a calm "no impact".

It must accept a PASTED LIST of real table names in whatever shape the list
arrives, because it will be copied out of Excel, Slack, Confluence or a query
result. Handle all of these with no tidying up by the user:

- one table per line; comma separated on one line; comma separated across
  several lines; semicolons; tab separated
- a paste from Excel with SEVERAL columns: work out which column holds the
  table names, and REPORT which one it took. A heading containing the word
  "table" settles it. Otherwise score each column by how many of its cells
  look like a real table name, where "real" means it also contains an
  underscore, a dot or a digit.
- a heading row on top. This list has to be long, because a heading that is
  not recognised becomes a published table name — and a published-table list
  with a word like "Status" on it matches nothing, quietly, on the one setting
  that decides whether "no production table is impacted" is a result or an
  accident. Match on the cell's own text, lower-cased and trimmed, against all
  of these:

    #  no  s no  sr no  sl no  row  id  index
    name  names  table  tables  tablename  table name  table names
    full name  full table name  qualified name  fully qualified name
    fully qualified table name
    target table  output table  published table  prod table
    production table  downstream table
    dataset  datasets  schema  project  database  db
    owner  team  layer  domain  env  environment  source  type  status
    sla  frequency  comment  comments  notes  description

  The last dozen are there because a real list is copied out of a spreadsheet
  that had other columns beside the table names, and every one of those column
  headings arrives with it.
- Slack and Confluence decoration: bullets • - * and numbering 1. 1) (1),
  backticks, ``` code fences, quotes, trailing commas and semicolons,
  markdown table pipes and ruled lines
- fully qualified prj-p-x.dataset.table, two-part dataset.table, and bare
  table, all mixed together in one paste
- different capitalisation, duplicates, blank lines, stray spaces

Classification of each entry, and this must not change existing behaviour:
  contains * or ?   -> a glob pattern, matched against the whole table name
  starts with _     -> a suffix pattern, matches the END of a table name
  anything else     -> an exact table name, matched exactly
So rules somebody set months ago (_PROD, PROD_*) go on meaning exactly what
they meant. SQL only ever gives us the last part of a name, so an exact name
is matched on its last dot-separated part, while the whole thing as pasted is
kept for showing back on screen. A glob is keyed the same way: "mart.snap_daily_*"
is matched as "snap_daily_*", because no bare name ever has a dot in it, and a
dotted pattern compared to bare names matched nothing for ever.

FOUR MORE SHAPES A REAL LIST ARRIVES IN, each measured as a real published
table reported "did not look like a table name". Read each one as the name it
holds, and write down that you did, one note per kind (see below):
  invisible characters   a zero-width space or a no-break space inside the
                         name, from Confluence or Excel — strip them
  project:dataset.table  the older BigQuery spelling with a colon — read it
                         as project.dataset.table
  a note in brackets     "sales_daily (partitioned by day)" — keep the name,
                         drop the note
  a description after    "sales_daily - daily sales", "sales_daily: the daily
    the name             sales" — keep the name, drop the rest
The last two are only ever used when the part kept could not be an English
word: it has an underscore, a dot or a digit in it. "please - confirm by
friday" is exactly this shape and must still come back as ignored.

BE HONEST ABOUT THE PASTE. Return, alongside the entries, a list of notes
saying what was left out and why, each already written as a sentence ready to
show on screen, with examples:
  "1 line looked like a heading row and was ignored."
  "3 duplicates removed."
  "The paste had 3 columns. Ripple read the column headed \"Table name\" and
   ignored the other 2."
  "2 lines did not look like a table name and were ignored."
  "1 pair of names is the same table to Ripple, so only the first was kept:
   SQL only ever says the last part of a table name."
  "2 names had a note in brackets after them. Ripple kept the name and
   dropped the note."
  "1 line had invisible characters in it - a zero-width space or a no-break
   space, the kind a copy out of Confluence or Excel brings along. Ripple
   removed them."
Nothing may be dropped silently. And never split prose into invented table
names — "please confirm by friday" must come back as ignored, not as four
published tables Ripple would then never find.

Also provide:

  check_against_repo(rule, index, parsed) -> dict

which answers the question this whole feature exists for: WHICH OF THE
PASTED TABLES HAS RIPPLE NEVER SEEN. Three answers, and the difference sends
a person to two completely different places:
  found    the table is in the SQL that was read. Each found entry says HOW:
           "exact", or "shard" / "placeholder" when it was found as a family
           (below), with the spellings the code uses in as[] and asCount
  written  the name is in the repository, but nothing readable builds it
  nowhere  the name is not in this repository at all
A FAMILY MATCH. A date-sharded table is written with its day on the end —
order_lines_20260101 — and pasted without it, because the family is what the
team publishes. A run-time placeholder glued onto a name is the same shape:
fact_returns_${RUN_DATE} reaches the parser as fact_returns_RUN_DATE. Neither
is a different table from the one on the list. So matches() also tries the
FAMILY of a name: strip a trailing _YYYYMMDD, _YYYYMM or _YYYY_MM_DD (and a
time after it), or a trailing run-time word — DATE, DT, DS, DS_NODASH,
RUN_DATE, LOAD_DATE, EXECUTION_DATE, PARTITION_DATE, TABLE_SUFFIX, SUFFIX,
SHARD, YYYYMMDD, RUN_ID, BATCH_ID, TIMESTAMP, TS, ENV and their close
spellings — and match what is left against the exact names. Never a version
or a word that is not one of those: order_lines_v2 and order_lines_backup are
different tables, as they always were. Loose on purpose, and in the safe
direction: a family match COUNTS a table as published, which can only add a
finding, never hide one — and every such match is reported as the family
match it is (familyCount on the check, how on each found entry), never as an
exact one.
For a name that matches nothing but IS the ending of tables that do exist,
report how many, so the screen can ask "did you mean it as a pattern?"
instead of quietly deciding. Also report, per pattern, how many tables here
it matches — a pattern matching zero tables is doing nothing at all, and
that is worth knowing before a result from it is believed.
Do the file scan for missing names in ONE pass over all files, not one pass
per name: a real repository is tens of megabytes.

AN EMPTY LIST NEVER FALLS BACK TO ANYTHING. This is the single most expensive
mistake this tool has ever made, so read it twice.

A published table is one people outside the team read. It is the thing every
finding is measured against, and it is the only setting Ripple cannot work out
for itself. It used to ship with a default — _PROD, _PRD, _PUBLISHED. On a
warehouse that names its published tables any other way, that default matches
NOTHING. And matching nothing does not read as "I do not know which tables are
yours". It reads as "no production table is affected", in green, over a change
that breaks all of them. A wrong list and a right list produce answers that look
identical.

So there is no default, anywhere, and empty means NOT GIVEN rather than
"nothing is published":

* `set_production` keeps an empty box empty. It does not fall back.
* `has_production()` is the one question every entry point asks, and it is
  simply "did anybody give me a list".
* The scan route REFUSES, with a message naming what to go and do, rather than
  answering against a rule nobody chose.
* The screen blocks the scan button and says why on the same screen. A button
  that runs and comes back with an error is a worse way of being told than a
  button that says what is missing before it is pressed.

DEFAULT_PRODUCTION (_PROD, _PRD, _PUBLISHED) still exists, as SUGGESTION TEXT
shown beside the empty box so somebody can see the shape of an answer. It is
never applied. Any wording on screen that says Ripple "falls back to" it is
wrong and must not be written.

--- tests/test_production.py

Write these tests, using only invented table names:
  a list survives however it was copied — one per line, commas on one line,
    commas across lines, semicolons, blank lines and spaces, Slack bullets,
    numbering, backticks, a code fence, quotes and trailing commas, space
    separated on one line
  an Excel column keeps its heading out of the list
  several Excel columns pick the one with the tables in it, and say which
  several columns with no heading still pick the table column
  a markdown table from Confluence reads as a list
  qualified, two-part and bare names mix in one paste
  duplicates and capitalisation are reduced and reported
  two names Ripple cannot tell apart are reported, not silently deduplicated
  a line that is not a table name is reported, never dropped silently
  prose is never split into invented table names
  every pattern still does exactly what it did before (parametrised)
  an exact name matches only that table — stg_sales_daily is NOT sales_daily
  names and patterns work side by side
  an empty box stays empty, has_production() answers false, and NOTHING
    falls back to _PROD, _PRD or _PUBLISHED
  the one-line form counts a long list instead of printing it
````

**How to tell the prompt arrived whole.** These blocks are long, and what drops
off a long paste is always the end — and the end of every one of them is the
list of tests. Lose that and the chat hands back a file with no tests, nothing
looks wrong, and you find out three evenings later. So look at the bottom of
what you just pasted into the chat. The last line of the block above is *"the
one-line form counts a long list instead of printing it"*. If the chat's window
does not end with that line, it did not all go in — paste it again.

**Check it worked.** From `C:\ripple-build`:

**Type this into the black window.**
```
python -m pytest tests/test_production.py -q
```

You want `passed`. There is one test worth checking on before you move on, and
you do not have to open a file or read any code to check it. Paste this back
into the same chat window:

**Paste this into the chat.**
````text
Show me the test where the pasted list of published tables is messy - bullets on
some lines, a heading row, and a line of ordinary prose in among them. Quote for
me, as plain English outside the code, the list it feeds in and the notes it
expects back. If there is no such test, say plainly that there is not, and write
one.
````

If it answers that there is no such test, ask for one and run the command again.
This file decides whether "no production table is impacted" is a real answer or
an accident, and a file tested only against tidy lists will quietly call a messy
list empty.

**If it will not work.** Two pages of this document exist for exactly that, and
both are a Ctrl+F away. Search for **Checking that a phase worked**, near the
top: it says what `passed`, `failed` and `no tests ran` each mean, and what to
do about each. Then search for **When the chat goes wrong**, at the very end: it
has ready-written sentences you can paste straight back into the window. Every
page in this kit is listed in the table at the top, under **What is in here, and
where**.

---

# PHASE 2 — walking the repository folder

**Saves to:** `ripple-build/ripple/scanner/repo.py`, `ripple-build/tests/test_repo.py`

**Two things in the block below look like copying mistakes and are not.** Some
passages appear twice, word for word or near enough — the one about a query kept
as a template, `load_final.sql.j2`, and the one about a shell script handing a
query over two ways. That is on purpose: this window has to get both of them
right, and a rule stated once at the top of a very long prompt is a rule that
gets skimmed. And several passages are marked *[ BUILT IN PHASE 4 ... this
window builds none of it ]*. Those are background, so this window knows what the
others are doing. Paste the block exactly as it is. Do not tidy either of them
out.

**Paste this into the chat.**
````text
[PASTE THE CONTRACT CARD FIRST]

Build ripple/scanner/repo.py and tests/test_repo.py.

A RepoIndex dataclass holding every readable file in memory, built by
RepoIndex.build(root, cfg, on_progress=None). Text compresses well and only
files with a useful extension are kept, so a real repository fits easily.

Fields: files[] of SourceFile, skipped[], root, held_online[], too_long[],
in_skipped_dirs[], skipped_dir_names[], unknown_ext{}.

Rules that matter, each for a reason:

1. LONG PATHS. On Windows, prefix the walk root with \\?\ (or \\?\UNC\ for a
   share) so the walk gets past the 260-character limit whether or not long
   path support is switched on. A managed laptop usually has it switched off,
   and real repository folders are 140 characters before the filename starts.
   A file that still cannot be opened and whose path is over 260 characters
   goes in too_long, not in a generic error list.

   The \\?\ form is for OPENING files and for nothing else. Work every path a
   person will read out against the walk root, so what reaches the screen is
   the path INSIDE the repository with forward slashes —
   src/sql/DML/load_final.sql — carrying no \\?\ and no drive letter. A finding
   pointing at a filename that does not exist as printed is a finding nobody
   can check, and one they cannot check is one they dismiss.

2. FILES THAT ARE NOT REALLY THERE. OneDrive Files On-Demand leaves a file in
   the listing, with its real name and size, when the contents are still in
   the cloud. Opening it asks OneDrive to fetch it, which on a machine with no
   network hangs and then fails, once per file, and there can be thousands.
   Detect it BEFORE opening, from the Windows file attributes:
     FILE_ATTRIBUTE_RECALL_ON_OPEN         0x40000
     FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS  0x400000
   Either of those means the contents are not here: record in held_online and
   do not open. FILE_ATTRIBUTE_OFFLINE (0x1000) is older and much looser —
   some backup software sets it on perfectly local files — so on its own treat
   it as suspicion only and still open the file. Also treat a read failure
   whose message contains the word "cloud" as the same thing.
   This is the most dangerous thing that can happen to a scan: half a
   repository never read comes back with a short finding list and a green
   tick, and the green tick is the only thing this tool sells.

   Counted THERE AND NOWHERE ELSE. A file held in the cloud never also goes on
   the check-by-hand list. There is nothing on this machine to open, so listing
   it in both places counts two problems where there is one and sends somebody
   off to read a file that is not there. On the answer these come back as
   "never opened", which is a different and worse thing from "read and not
   understood" and gets its own count and its own sentence.
   A read that FAILS on a file carrying the loose OFFLINE flag is the same
   problem, said the same way: record it as held online rather than as an error
   code nobody can act on. That pairing is what makes it safe to go ahead and
   open an OFFLINE-flagged file in the first place.
   Ask for the attributes defensively. A machine that is not Windows, and a
   Python that does not report them, both mean "an ordinary file" — not a crash
   in the middle of a walk.

3. SKIPPED FOLDERS. Judge the skip-dirs names against the path INSIDE the
   repository, never the whole path — a repository that happens to live under
   a folder called build or venv must not read as empty. And when a file that
   WOULD have been read is skipped because of its folder, record it in
   in_skipped_dirs and the folder name in skipped_dir_names. In most
   repositories "build" and "target" hold generated output; in a few they hold
   the pipeline, and then this is a scan of half a repository with nothing on
   screen to say so.

4. Files over max_file_bytes go in skipped[] with a plain-English reason.

5. HOW THE FILE WAS SAVED. Read the bytes and work the encoding out; do not
   just ask for UTF-8. Windows writes byte-order marks by default — Notepad,
   PowerShell's Out-File, Excel's CSV export, every Office "save as UTF-8" box
   — and a mark is invisible in every editor and lethal to a SQL parser. It
   lands on the FIRST statement of the file, which in a pipeline file is the
   one that names the source table, so the statement that matters is the one
   that is lost and the file still reports as read. Get this wrong and the
   first statement failed, risk came back "none", and with two statements in
   the file the wording actively reassured — "1 of 2 statements in this file
   could not be read - the other 1 was".
     Check for a mark first: EF BB BF is utf-8-sig; FF FE 00 00 and
     00 00 FE FF are utf-32; FF FE and FE FF are utf-16.
     With no mark, look at the first 4 KB. Real text has no NUL bytes at all,
     so more than about a tenth of them being NUL means UTF-16 with no mark —
     PowerShell's ">" redirection has written UTF-16-LE by default for twenty
     years. Decide which way round from whether byte 2 is NUL.
     Then UTF-8, and latin-1 as the last fallback.
   If a NUL byte SURVIVES all that, do not index the file: put it in skipped[]
   saying it contains NUL bytes and is either not text or was saved in an
   encoding Ripple could not work out. A NUL left in the text makes the parser
   swallow the statement it sits in and say nothing — measured at
   couldNotRead 0, no warning of any kind, risk none.

6. SQL THAT IS NOT IN A .sql FILE, AND CONFIG THAT IS NOT SQL AT ALL.
   .yaml, .yml and .xml are on the read list, and handing one of them to a SQL
   parser whole can only ever fail. Two things go wrong at once:
     * An Airflow YAML holding "sql: |", an Oozie workflow.xml holding
       "<script>", and a shell script running "bq query <<EOF" each held the
       whole CREATE that builds a published table, and every one of them gave
       risk unknown and no lineage at all.
     * Every ordinary Kubernetes YAML in the repository landed on the "check by
       hand" list. Without it, twelve config files and one genuinely broken query
       gave couldNotRead 13, sorted alphabetically, with the real failure last.
       That list is the one place Ripple admits what it missed, and flooding it
       is how a real miss stops being seen.
   So: mine the SQL out (see statements_for below), and when nothing comes out
   of a markup file, say NOTHING about it — no statements, and no entry on the
   check-by-hand list. The guard on that silence is looks_like_unread_sql: a
   file with SELECT or CREATE written in it that yielded no block IS reported,
   because that is a query Ripple failed to mine rather than a config file.
   sql_file_refs also has to read markup, where the filename carries no quotes:
   "sql: queries/load_final.sql" is an ordinary Airflow shape and the
   quoted-string rule that covers .py files found nothing in it at all.

7. FILE TYPES YOU DO NOT OPEN. Count them. When a file is passed over because
   its extension is not on the read list, add one to unknown_ext[ext]. The walk
   must not have a bare "continue" with no counter: a repository whose
   pipeline is written in .ipynb, .tf or .json files reported "indexed False,
   risk none, prod []" with NOTHING anywhere recording that a file had been
   passed over. The point is not to read them. It is that the NEXT unlisted
   extension is visible instead of silent.

8. WHICH UNOPENED TYPES REACH THE ANSWER. unknown_ext holds every extension
   passed over and the repository screen lists all of them. The ANSWER carries
   only the ones that could plausibly hold a pipeline, decided by one function
   that lives beside the walk:

     unopened_code_types(unknown_ext) -> dict   the same tally with the types
                                                that are KNOWN not to be code
                                                taken out

   Write that list as what is NOT code, never as what is. Then a file type
   nobody thought of counts as a gap by default, which is how a middle hop
   written in a notebook, in Terraform, or in something nobody has met stops
   going missing without a word. The other way round, every unheard-of
   extension is silently harmless, which is the failure this exists to stop.
   Known not to be code, and this is the whole list:
     prose, documents   .md .markdown .rst .txt .adoc .pdf .doc .docx .odt
                        .rtf .tex
     images             .png .jpg .jpeg .gif .svg .ico .webp .bmp .tif .tiff
                        .psd
     styling, fonts, browser build output
                        .css .scss .sass .less .woff .woff2 .ttf .eot .otf .map
     packed data        .csv .tsv .parquet .avro .orc .xlsx .xls .pb
     archives, binaries .zip .gz .tgz .tar .bz2 .xz .7z .rar .jar .war .whl
                        .egg .so .dll .dylib .exe .bin .pyc .pyo .class .o .a
                        .lib .pdb
     media              .mp3 .mp4 .mov .avi .wav .webm .flac .ogg
     locks, logs, housekeeping
                        .lock .log .bak .swp .ds_store
   Leave any of them off and the warning fires on every scan of every
   repository — every one has a README, a lock file and a logo — and a warning
   printed every time is one nobody reads. It takes "no impact" with it,
   because a scan carrying an unopened code type may not answer "none".
   Count only files that HAVE an extension. A Makefile, a Dockerfile or a
   LICENSE would otherwise be tallied under a blank one, and the card beside
   the answer would name a file type that is not a file type.

9. A QUERY KEPT AS A TEMPLATE IS NAMED TWICE: load_final.sql.j2. Python calls
   that file's suffix ".j2", so nothing opens it — and the "runs the SQL in X,
   which is not in this repository" warning cannot fire either, because that
   only matches names ending ".sql". A double miss, and the double is what
   makes it silent: no file read, no gap reported, and a published table that
   traces back to nothing.
   So every place in this file that decides what a file IS asks one helper
   rather than reading the last suffix:

     effective_ext(path) -> str    the last suffix, EXCEPT that where the last
                                   suffix is a known template one AND the one
                                   before it is a SQL one, the SQL one comes
                                   back instead

   Template suffixes: .j2 .jinja .jinja2 .tmpl .template .tpl .mustache .hbs
   .erb. SQL ones: .sql .sqlx .ddl .hql. Only those, and only in that order.
   Read anything at all past a .sql and load_final.sql.bak comes with it, and a
   backup read as a live file turns into "this table is built in two files" —
   a fork reported on every scan, over a file nothing runs.
   Use effective_ext in the walk (which files to open, and which language to
   label them with) and in statements_for, extract_markup_sql, sql_file_refs,
   looks_like_unread_sql and written_tables. So they can ask again later,
   SourceFile keeps the absolute path it was read from alongside the tidy
   repo-relative one it shows on screen.
   Give sql_file_refs the same tail as an OPTIONAL ending on the name it looks
   for, so a .sql.j2 kept outside the repository is still reported by name.
   Keep each distinct name once, matched without regard to case, with the line
   it is first written on.

Also in this file:

  search(names) -> Match[]        every line mentioning any of these names as
                                  a whole word, case-insensitive
  files_mentioning(names)
  get(path)
  extract_sql_blocks(f)           SQL inside triple-quoted and long single
                                  strings in .py .scala .java .sh files,
                                  returning (text, 0-based line offset) so a
                                  finding still points at a real line
  extract_markup_sql(f)           SQL taken out of a .yaml, .yml or .xml
                                  file, with the line each block starts on.
                                  YAML: a key whose name contains sql, query,
                                  script or statement, holding a block scalar
                                  (| or >) or a one-line value that really is a
                                  query. Take the block's own indent off, and
                                  measure from the KEY's column rather than the
                                  line's, so "- sql: |" works. XML: the text of
                                  an element whose tag contains script, query,
                                  sql, statement or command, plus any CDATA
                                  section, with the five XML escapes undone
                                  (&amp; last, or &amp;lt; decodes twice). If
                                  nothing comes out and the file's first line of
                                  code is a SQL keyword, treat the whole file as
                                  SQL.
  _heredoc_blocks(text)           SQL fed to a command through a shell heredoc:
                                  <<EOF, <<-EOF, <<'EOF', <<"EOF", ending at a
                                  line whose only content is the tag.
  statements_for(f)               extract_markup_sql for .yaml .yml .xml;
                                  extract_sql_blocks — plus heredocs, for .sh —
                                  for .py .scala .java .sh; the whole text for
                                  .sql, .sqlx, .ddl and .hql.
  sql_file_refs(f)                every "something.sql" string a program
                                  names, with its line. A DAG that runs the
                                  most important query in the pipeline used to
                                  look identical to an empty file.
  written_tables(f)               tables a program writes to, from
                                  saveAsTable / insertInto /
                                  createOrReplaceTempView / registerTempTable,
                                  and from destination= / destination_table= /
                                  to_gbq(. Take the last part after a dot OR
                                  a colon. Spark and BigQuery jobs run a bare
                                  SELECT and name the destination in the
                                  program, not the SQL, so without this the
                                  chain stops exactly where the interesting
                                  renames are. Three more spellings of the
                                  SAME destination, every one of which otherwise gives
                                  "no lineage to a production table":
                                  * a quoted value carrying a COLON --
                                    'prj:marts.final_published'. bq's own
                                    separator between project and dataset is a
                                    colon, so the character class needs one.
                                  * Airflow's BigQueryInsertJobOperator, which
                                    hands over BigQuery's API shape instead:
                                    "destinationTable": {"projectId": ...,
                                    "datasetId": ..., "tableId": "final_..."}.
                                    Anchor on destinationTable and stop at the
                                    closing brace -- a bare tableId also sits
                                    under sourceTable, and reading that turns
                                    a READ into a write and invents a chain.
                                  * the bq command line itself, where nothing
                                    is quoted at all:
                                    --destination_table=prj:marts.final_pub.
                                    Require the unquoted name to be QUALIFIED,
                                    one dot or one colon in it, or
                                    destination_table=None becomes a published
                                    table called None.
A TEMPLATED QUERY IS NAMED TWICE: load_final.sql.j2. Python calls that file's
suffix ".j2", so it was never opened — AND the "runs the SQL in X, which is not
in this repository" warning could not fire either, because that only matched
names ending ".sql". A double miss, which is what made it silent. Decide how to
read a file on the INNER extension when the outer one is a known template
suffix (.j2 .jinja .jinja2 .tmpl .template .tpl .mustache .hbs .erb), and let
the file-reference pattern carry an optional template tail so a .j2 kept outside
the repository is still reported. Only a KNOWN template suffix, and only over a
SQL one: reading anything at all past a .sql takes load_final.sql.bak with it,
and a backup read as a live file becomes "this table is built in two files".

                                  Give the names back in the order they appear
                                  in the file, and each one only once. A Spark
                                  job writing the same table on two lines has
                                  one destination, not two. Counted twice, the
                                  job reports "writes to 2 tables (sales,
                                  sales)", loses the single destination that
                                  lets its bare SELECT be joined to a table at
                                  all, and the chain stops dead at the job —
                                  which is exactly where the interesting
                                  renames happen. Read this only for the
                                  program files, .py .scala .java .sh, since
                                  that is where a destination is named outside
                                  the SQL.

A SHELL SCRIPT HANDS A QUERY OVER TWO WAYS, NOT ONE. The heredoc is read. The
other way is one quoted argument written across several lines:
    bq query --use_legacy_sql=false 'CREATE OR REPLACE TABLE final_published AS
    SELECT id, cm13 FROM customer_demographics'
A shell leaves a single-quoted string completely alone, so this is every bit as
ordinary. The string miner every language shares refuses a newline inside a
quoted value — it has to, or one stray apostrophe in a comment swallows the rest
of the file — so this shape was mined by nothing at all. Anchor on a command
that RUNS SQL (bq query, psql, mysql, hive -e, spark-sql, snowsql, beeline and
the rest) and read from there to the closing quote: starting from the command
cannot be set off by "don't" in a comment. Dedupe the blocks afterwards — a
one-line bq query is found by the ordinary string miner as well, and reading it
twice counts every finding in it twice.

  A BARE WORD IN SQL IS NOT ALWAYS A COLUMN. Where a name is read back out of
  text rather than off the parse tree, check it against the words that are
  never a column before recording one, or a WHERE clause reports a usage of a
  column called AND:

    AND  OR  NOT  IN  IS  NULL  TRUE  FALSE  LIKE  BETWEEN
    CASE  WHEN  THEN  ELSE  END  AS  CAST  ANY  ALL
    STRING  INT64  FLOAT64  BOOL  DATE  TIMESTAMP
    SESSION_USER  CURRENT_DATE  CURRENT_TIMESTAMP

  The type names matter as much as the keywords: CAST(cm13 AS FLOAT64) holds
  two bare words and only one of them is a column.

  looks_like_unread_sql(f, blocks)  SQL is plainly written in this file and
                                  none could be extracted — the shape where a
                                  statement is built by adding short strings
                                  together and never exists as one thing.

A UNION TAKES ITS OUTPUT NAMES FROM ITS FIRST BRANCH, BY POSITION.
  [ BUILT IN PHASE 4, in scanner/sqlread.py and scanner/dialectcompat.py.
    Phase 4 carries this rule in full. It is repeated here as background
    for the walk, and this window builds none of it. ]


  SQL names a set operation's output columns from the branch written FIRST, and
  applies those names to every other branch by position. The other branches'
  own names are never published at all:

      CREATE OR REPLACE TABLE stage_u AS
      SELECT id, other_col AS market FROM legacy_demographics
      UNION ALL
      SELECT id, cm13          FROM customer_demographics

  builds a table whose columns are id and market. Nothing downstream can read
  cm13 from it, because there is no such column.

  The projection walk groups a union's branches together, because they sit side
  by side at the same depth rather than one inside the other. Merge their select
  lists without lining up positions and cm13 leaves under its own name, the next
  statement reads market, the two never meet, and the trail ends at the staging
  table: prod empty, no production table affected, and no gap reported anywhere
  because as far as the trail knows there was no branch. Which of the two
  branches the traced column happens to be written in then decides whether a
  real break is found at all. A current table UNION ALL an archive one, written
  in whichever order somebody typed them, is how a large part of a staging layer
  is built, so this is a coin toss over the answer this tool exists to give.

  So: for every set operation, take the output names off the whole node, and for
  every branch after the first map position i of that branch to name i. Read the
  set-operation class through the small parse-tree module, never by naming
  exp.Union directly -- one sqlglot major has only Union and the next has
  SetOperation above it, and the wrong name matches nothing while raising
  nothing. Flatten the branches: a three-way union is nested to the left, so
  Union(Union(a, b), c) has to come out as a, b, c in written order.

  Only line the positions up when the branch has the same number of select-list
  items as there are output names and no star is in the way. Where the count
  cannot be checked, leave the names alone: a name put on the wrong column is
  worse than a name not put on at all. Keep each column's own name as well as
  the position name -- it reaches nothing downstream, because no such column
  exists on the table, so a miscount costs a spare row rather than a lost chain.

ONE STATEMENT WRITTEN AS SEVERAL STRINGS IS STILL ONE STATEMENT.

  A program that has to fill something in writes its SQL in pieces:

      sql  = "CREATE OR REPLACE TABLE final_published AS SELECT cm13 "
      sql += "FROM customer_demographics WHERE dt = @d"

  Every miner looks for a whole statement inside ONE pair of quotes, so what it
  finds is the first piece. And the first piece PARSES, because BigQuery is
  happy with a SELECT that has no FROM. Nothing fails, nothing reaches the
  check-by-hand list, and the scan comes back risk none, prod empty, coverage
  complete -- a green tick with "I could see all of it" printed beside it, over
  a job that really does rebuild the published table out of that column. It is
  the worst answer this tool is capable of giving, and the only one where the
  coverage card itself says there is nothing missing.

  So weld the pieces back together before mining. Find each quoted piece that
  sits on one line, then join a run of them wherever what lies between is
  plainly still one string: whitespace, a line continuation, a plus, or the same
  variable being added to with a plus-equals. Give back the joined body with the
  line the FIRST piece starts on.

  Three things this must not do. It must never join across a comma -- that is a
  LIST of separate queries, and welding those together invents a statement that
  is in no file, which is the opposite failure and just as wrong. A plus-equals
  must only join to the variable the run before it was assigned to, or two
  variables holding two different queries become one. And a run of two or more
  pieces must SUPPRESS the ordinary miner over the same characters: the first
  piece is a quoted string in its own right, so a statement read once whole and
  once in half puts every finding in it on screen twice.

  Blank the triple-quoted regions before looking for pieces. Three quote
  characters in a row read as two empty pieces, and the docstring then welds
  itself onto whatever follows it. Replace them with spaces of the same length,
  never remove them, so every offset is still an offset into the real file. What
  is inside them is already mined as a block of its own.

  Measured on a real BigQuery warehouse: 111 of its Python files hold SQL, 52 of
  them build it out of adjacent strings, 37 with a plus, and 11 with a
  plus-equals.

WHAT COUNTS AS SQL INSIDE A PROGRAM INCLUDES THE STATEMENTS WITH NO SELECT.

  The test that decides whether a block of text is worth handing to the parser
  is matched against ordinary prose as well as against code, so it is written
  tightly -- and written too tightly it leaves out every statement that has no
  SELECT in it. A DELETE that clears a published table before a reload, a
  TRUNCATE, a CREATE FUNCTION: mined by nothing, read by nothing, lineage
  nowhere. The file then lands on the check-by-hand list saying there is SQL in
  it that could not be taken out, which names neither the table nor the column.

  Include SELECT, INSERT INTO, INSERT OVERWRITE, MERGE INTO, UPDATE, DELETE
  FROM, TRUNCATE TABLE, CREATE OR REPLACE, and CREATE followed by TABLE, VIEW or
  FUNCTION with at most one real SQL modifier in between -- TEMP, TEMPORARY,
  MATERIALIZED, EXTERNAL or SNAPSHOT.

  Only those modifiers, and this is the whole difficulty of the list. Allow any
  word between CREATE and its noun and a docstring saying it will "create the
  destination table for you" becomes a statement, and a table that exists
  nowhere appears on screen as a fact. Measured: three docstrings in one
  repository turned into statements that way.

  Measured the other way: 24 blocks in 9 files of a real BigQuery warehouse,
  18 of them a DELETE against a table that same repository publishes.

  Say it in whole sentences when part of a file was mined and part was not.
  Slotting a phrase into one sentence produced "Ripple could not take some of
  out of it", which is not English -- on the one list whose whole job is to
  persuade somebody to go and open a file.

THE TRAIL ENDS WHERE THE CODE ENDS, NOT WHERE A COUNTER DOES.
  [ BUILT IN PHASE 1, as the max_hops default in config.py, and obeyed in
    PHASE 5's walk. Phase 1 carries the rule and the measurements. It is
    repeated here as background, and this window builds none of it. ]


  A limit on how many renames deep to follow a column reports itself as a fact
  about the warehouse. "The chain ends here and does not reach production" is a
  sentence about a setting wearing the clothes of a sentence about somebody's
  data, and it is indistinguishable from the real thing.

  Ten was still a wall, just a further-off one. The result screen offered to
  follow twice as far, and on a chain longer than that offer it changed NOTHING:
  measured on a 36-hop chain, ten renames cut the trail short, twenty cut it
  short, and twenty-five -- the deepest the screen would offer -- cut it short as
  well. Three whole scans, three identical empty answers, and no number a person
  could choose that produced one. That is what "the button does nothing" is.

  So the default is ZERO, and zero means follow until the code runs out.

  This is safe, and the reason it is safe is already in the walk: it carries a
  set of every (table, column) pair it has been through, so a ring of tables
  closes on itself whatever any counter says. The counter was a second guard
  that could only ever truncate a real answer. Measured on a real BigQuery
  warehouse of 7,304 files: following to the end costs 10.6 seconds against 10.5
  at ten hops, and finds the same tables plus the ones that were past the limit.

  Three things to get right around it:

  * A limit somebody sets ON PURPOSE is still obeyed, and a trail stopped by it
    is still reported as stopped rather than as a chain that ended.
  * Zero is a REAL request, not a missing one. Test it with "is not None",
    never for truthiness -- read as falsy, the button that asks for the end of
    the code sends nothing, the saved limit is used anyway, and the same
    cut-short answer comes back. That is the bug this replaced, reintroduced.
  * Do not print zero as a number. "0 hops deep" reads as "Ripple follows no
    renames at all", which is the opposite of what it means. Say it in words.

  The other walk with a counter -- the one that finds published tables which
  stop being refreshed -- takes the same treatment. Its own seen-set grows every
  round and is never cleared, so it ends when the frontier does. Its real limit
  is the downstream cap, and THAT one is reported.

NOTHING IS SCANNED UNTIL SOMEBODY SAYS WHICH TABLES THEY PUBLISH.
  [ BUILT IN PHASE 1 (production.py and config.py: no default,
    has_production), PHASE 8 (the scan route refuses) and PHASE 11 (the
    button says why before it is pressed). Each of those phases carries
    it. Repeated here as background; this window builds none of it. ]


  A published table is one people outside the team read. It is the thing every
  finding is measured against, it is the only setting Ripple cannot work out for
  itself, and it used to ship with a default: _PROD, _PRD, _PUBLISHED.

  On a warehouse that names its published tables any other way, that default
  matches NOTHING. And matching nothing does not read as "I do not know which
  tables are yours". It reads as "no production table is affected", in green,
  over a change that breaks all of them. It is the most expensive thing this
  tool has ever done, because a wrong list and a right list produce answers that
  look identical.

  So there is no default, anywhere, and empty means NOT GIVEN rather than
  "nothing is published":

  * ``set_production`` keeps an empty box empty. It does not fall back.
  * ``has_production`` is the one question every entry point asks.
  * The scan route REFUSES with a message naming what to go and do, rather than
    answering against a rule nobody chose.
  * The screen blocks the scan button and says why on the same screen. A button
    that runs and comes back with an error is a worse way of being told than a
    button that says what is missing before it is pressed.
  * Offline, "configured" means a folder AND a list. A folder on its own is a
    Ripple that can read every file and still not know what any of it means.

  Whoever deploys a hosted copy can still set the list in the environment. What
  cannot happen is a copy scanning with a list nobody chose.

  Set the button's state in ONE place. It was assigned twice in the same
  function and the second assignment quietly undid the first, so the gate showed
  its own label on a button that was still pressable -- measured on the rendered
  screen: the text said "Add your published tables first" and disabled came back
  false. A control whose state is written twice cannot be reasoned about by
  reading the code, which is how the second one got there.

READING THE REPOSITORY MUST NOT HOLD THE FIRST SCREEN BLANK.
  [ BUILT IN PHASE 8, in api.py, and shown by PHASE 11. Phase 8 carries
    it. Repeated here as background; this window builds none of it. ]


  Reading a repository the size of a real warehouse takes minutes, and the
  health request is the one the screen makes before it can paint anything at
  all. Measured on 7,304 files: 101 seconds inside that request, during which
  the window is blank and has no way to ask what is happening -- because the one
  request that would tell it is the one it is already waiting on.

  A working program that says nothing for a hundred seconds is reported as a
  hung one. Offline that window IS the product.

  So the read happens on a thread, health answers straight away with
  ``indexing: true``, and the screen shows the counted file numbers that were
  always being recorded and never had anywhere to go. It waits there, polling,
  until the read is done.

  Four things this depends on:

  * The still-reading answer is the SAME SHAPE as the finished one, with the
    counts at zero. One screen file paints both, and a key left out of it is a
    blank on screen that no test would ever see. Pin that with a test comparing
    the two sets of keys.
  * One reader at a time. The read now happens on a thread while other requests
    keep arriving, and two threads reading the same repository would do all of
    it twice and then disagree about which answer to keep.
  * A read that FAILED and a read that never finished look identical from the
    screen. Keep the error and show it; one of them needs somebody to act.
  * Every number stays counted. Nothing is estimated, nothing is smoothed, and
    no bar moves on a timer -- the numbers on that screen are files that have
    really been opened.

TWO MORE THINGS ABOUT MINING SQL OUT OF A FILE

  A quoted YAML value may run over several lines. Taking only the key's own line
  gave back "CREATE OR REPLACE TABLE final_published AS" with no SELECT -- half
  a statement, which parses, and was therefore counted as READ. When the value
  starts with a quote that does not close on that line, gather following lines
  until it does, and fold them into one. If the quote never closes, give back
  the first line only rather than swallowing the file.

  looks_like_unread_sql COUNTS, it does not ask "were there any blocks". An
  Airflow YAML, an Oozie workflow and a shell job normally hold several tasks of
  DIFFERENT kinds, and Ripple knows how to mine some of them. One recognised
  `sql:` block must not buy silence for the `bash_command:` beside it --
  at couldNotRead 0 with the coverage card reporting no gaps, and deleting the
  recognised block from that same file put it straight back on the check-by-hand
  list. So: count the SQL-statement starts in the whole file, count them in what
  was mined, and report the file when the second number is smaller.

  A SHELL SCRIPT HANDS A QUERY OVER TWO WAYS, NOT ONE. The heredoc is one. The
  other is a single quoted argument written across several lines, and a shell
  leaves a single-quoted string completely alone, so it is every bit as
  ordinary:
      bq query --use_legacy_sql=false 'CREATE OR REPLACE TABLE final_published AS
      SELECT id, cm13 FROM customer_demographics'
  The plain string miner every other language shares refuses a newline inside a
  quoted value — it has to, or one stray apostrophe in a comment swallows the
  rest of the file — so this shape is mined by nothing, and the CREATE that
  builds the published table is invisible while sitting in the file in plain
  sight.
  Add a second miner for .sh, anchored on a command that RUNS SQL rather than
  on the quote: bq query, psql, mysql, hive -e, impala-shell, spark-sql,
  snowsql, sqlcmd, clickhouse-client, beeline, athena. From the end of that
  command step over the flags — spaces, tabs, and a backslash-continued line
  break, because bq's destination flag is usually written on the line above the
  query — then read from the opening quote to the next matching one. Starting
  at the command is what stops "don't" in a comment setting it off.
  statements_for adds these to the heredoc blocks for .sh, and then DEDUPES the
  whole list: a one-line bq query is found by the ordinary string miner as
  well, and read twice it counts every finding in it twice over.

  A YAML BLOCK MARKER IS RARELY JUST "|". YAML writes | and >, and it also
  writes |- >- |+ >+ and |2 — the dash or plus says what to do with the blank
  line at the end, the digit says how far in the block is indented. Airflow
  DAGs are full of "sql: |-". So accept | or >, then an optional - or +, then
  optional digits, then nothing else on the line. Match "|" and ">" exactly and
  "sql: |-" reads as a one-line value of "|-", the CREATE indented underneath
  is mined by nothing, and the file goes silent: no statement, no gap, and the
  published table it builds is known to Ripple nowhere.

  A BLANK LINE DOES NOT END A BLOCK. End it at the first line that has
  something on it and is indented no further than the KEY. Stop at the blank
  line instead and you hand the parser the first half of a statement — which
  parses, and is therefore counted as read.

Write tests/test_repo.py with a tmp_path repository covering: extensions,
skip-dirs judged inside the repository only, skipped code files being counted
and named, a too-large file reported, SQL pulled out of a Python triple-quoted
string with the right line offset, a .sql reference found, a write target
found, and whole-word search not matching a substring.
````

**How to tell the prompt arrived whole.** The last line of the block above is
*"found, and whole-word search not matching a substring."* If the bottom of what
you pasted into the chat is not that line, it did not all go in — paste it
again.

**Check it worked.** From `C:\ripple-build`:

**Type this into the black window.**
```
python -m pytest tests/test_repo.py -q
```

You want `passed`. You will point this at a real folder of your own in Phase 12,
where you can see the counts on screen rather than having to ask for them.

**If it will not work.** Ctrl+F for **Checking that a phase worked**, near the
top, and then **When the chat goes wrong**, at the very end. Between them they
cover every way a phase comes back wrong.

---

# PHASE 3 — templated SQL and scripting blocks

**Saves to:** `ripple-build/ripple/scanner/templating.py`,
`ripple-build/tests/test_templating.py`

**Paste this into the chat.**
````text
[PASTE THE CONTRACT CARD FIRST]

Build ripple/scanner/templating.py and tests/test_templating.py.

Almost no production SQL is plain SQL, and both problems below cause the same
disaster: a repository that is almost entirely readable is reported as almost
entirely unreadable, and a scan over a repository that was never read reports
no impact.

PART ONE — placeholders.

Airflow, dbt and in-house generators wrap the parts that change:

  CREATE OR REPLACE TABLE {{tgt_project_id}}.{{stage_dataset}}.web_activity AS

A SQL parser has never met a { in that position and refuses the whole file.
Ripple is not the templating engine and does not need to be: it needs the
shape of the statement and the names in it, and the table name is sitting
right there. So replace each placeholder with an ordinary identifier made out
of its own text, giving tgt_project_id.stage_dataset.web_activity, which
parses as the three-part name it always was.

Handle: {# comments #}, {% tags %} (remove the tag, keep the SQL between),
{{ vars }} including Jinja filters {{ x | upper }}, ${ dollar } for shell and
Databricks, and { python_format } — the last one deliberately narrow, so that
a regular expression's {3} inside a string literal is left alone. For dbt,
ref('orders') and source('raw','orders') resolve to the last quoted name,
because that is a real table and taking it is the whole point of ref().

RUN THE FIVE IN THIS ORDER, AND { python_format } LAST OF ALL:

  {# comment #}  ->  nothing at all
  {% tag %}      ->  nothing at all, the SQL between the tags stays
  {{ var }}      ->  the identifier
  ${ var }       ->  the identifier
  { var }        ->  the identifier

The order is load-bearing. Take the narrow { name } pattern first and it
matches the inner half of {{ name }}, leaving a stray brace behind -- and
every templated file in the repository comes back unreadable, which is the
exact thing this part is here to prevent.

Three fallbacks in the identifier rule, so it always gives back something
that parses:
  anything that is not a letter, a digit or an underscore becomes an
  underscore, and leading and trailing underscores come off;
  if nothing is left, the identifier is the word placeholder -- an empty one
  leaves FROM .orders behind, a parse error that costs the whole file;
  if it starts with a digit, put p_ in front, and cut it at 60 characters.

One placeholder must resolve to NOTHING AT ALL: a dbt directive. {{ config(
materialized='table') }} — and set, test, macro, endmacro, snapshot,
endsnapshot, do, print, log — are instructions to dbt, not values. Turned into
a bare identifier, a word lands where SQL expects a keyword and THE WHOLE FILE
stops parsing: not one table, not one column, nothing. Get this wrong and adding a
config header to a readable dbt model took it from a full chain to 100%
unreadable, in every spelling tried. Every dbt model in the world opens with
one. Return an empty string for those, and make sure the "which words came out
of a hole" set skips the empties rather than collecting a blank name.

READ A TEMPLATE THAT USES CONTROL FLOW EVERY WAY IT RUNS, NOT ONE WAY.

  Filling in placeholders treats templating as holes with names in them. Real
  pipeline SQL also uses it as a small programming language, and three shapes do
  not survive having their tags blanked and every body kept:

      an if with an else       both branches kept, run on, and no parser takes it
      set ... endset           a value, left sitting inside the statement
      a placeholder alone      a whole block of SQL, turned into a bare word that
        on its own line          welds itself to the statement below

  None of those parse, so the file is not half-read: it is not read at all.
  Measured on a real BigQuery warehouse of 7,304 files, 329 of its 2,320 .sql
  files are templated and 176 of them produced no statement, no table and no
  column anywhere in any answer -- while every one sat on the check-by-hand list
  saying only that it would not parse.

  So render the file again with its control flow resolved. Walk the tags,
  keeping a stack of which blocks are open: an if keeps one side and blanks the
  other, a set or macro block keeps nothing because its body is a value, a for
  body is kept once. Blank every tag itself. Render it TWICE, once taking every
  condition and once taking none, and read BOTH -- nothing in the file says
  which way it runs, that is decided by a variable set somewhere else entirely,
  and of 103 such files that read more than one way, 26 name DIFFERENT tables in
  their two branches. Choosing one of those and calling the file read loses a
  source table with nothing anywhere saying a branch existed.

  De-duplicate the statements on the SQL the parser actually saw. Nearly all of
  a file is outside its branches, and read once per rendering it comes back as
  the same table built twice -- which reads on screen as "this table is built in
  two places", a warning about something that is not there.

  Try a rendering only on a file that did NOT parse as it stands. That is what
  makes this safe: a file that reads today cannot start reading differently.
  Order matters for the same reason. A placeholder alone on its line is blanked
  LAST, because a source table written on its own line under a FROM is exactly
  that shape, and blanking it on a file that already parses throws a real table
  away with nothing said.

  Keep the line count. Every replacement puts back the newlines it swallowed, so
  a finding still points at the real line of the real file -- the only line
  anybody can go and open. And allow a carriage return before the end of a line
  when matching a placeholder that stands alone: a repository cloned on Windows
  has CRLF endings, and a pattern that ends at the newline leaves the CR sitting
  there, so the same file reads one way on one machine and another way on the
  next with nothing saying so.

  A file that still will not parse any way round stays on the check-by-hand
  list. The renderings are a second chance, never a way of claiming a file was
  read.

NAME THAT SET AND HAND IT OUT, because Phase 4 cannot work without it.

  placeholder_names(text)  ->  a set of identifiers, in UPPER CASE

Walk only the three patterns that stand for a value -- {{ vars }},
${ dollar } and { python_format }. Comments and tags carry nothing and are
not walked. Run each body through the same identifier rule fill_placeholders
uses, drop the empties a dbt directive gives back, and upper-case what is
left.

This is the set that stops Ripple inventing a dataset. One file writes a
table as {{tgt_project_id}}.{{stage_dataset}}.card_guid_umdl and the DAG that
reads it writes {{ params.src }}.raw.card_guid_umdl. Once both are filled in,
one says the dataset is stage_dataset and the other says raw -- and those are
not two datasets, they are two holes. Knowing which words came out of a hole
is what stops Ripple deciding those are two different tables, cutting a real
chain in half and reporting no impact.

TWO RULES THIS FILE KEEPS:
  Line numbers do not move. Every replacement puts back exactly as many line
  breaks as it swallowed, so a finding still points at the real line of the
  real file, which is the only line anybody can go and look at.
  The original text is never changed. This is done to a copy on the way into
  the parser; everything shown on screen comes from the file as written.

Also provide describe(text) returning what kind of templating is in a file,
in words, for the screen: "{{ ... }} templating (Airflow, dbt or similar)".

PART TWO — scripting blocks.

Every file in a real BigQuery pipeline is wrapped in DECLARE ... BEGIN ...
END, often with a FOR loop or an IF inside. A SQL parser hands back BEGIN as
something it cannot read and, because BEGIN has no semicolon of its own,
SWALLOWS THE STATEMENT THAT FOLLOWS IT. That is the quietest possible
failure: the file parses, nothing is reported, and the first real statement
of every file has vanished.

Replace scripting keywords with an empty statement on the copy going into the
parser, keeping every line where it was:
  always scripting: BEGIN [TRANSACTION], END IF/FOR/WHILE/LOOP,
    COMMIT/ROLLBACK, EXCEPTION WHEN ... THEN, LOOP, LEAVE/ITERATE/BREAK/
    CONTINUE
  scripting only when no CASE is open: a bare END, a bare ELSE, and
    [ELSE]IF ... THEN

That last group is the trap. ELSE and END are also how an ordinary CASE
expression is written down the page:

  CASE WHEN status = 'A' THEN 'Active'
  ELSE
    'Unknown'
  END AS status_desc

Cutting those two lines puts a semicolon in the middle of a CASE and destroys
the statement they sit in — a 600-line CREATE TABLE thrown away whole, with
every table and column in it. So track CASE depth as the file is walked, and
only treat those two words as scripting when no CASE is open.

FOUR RULES FOR THAT COUNT, none of them optional.
  Count CASE and END on the same line in the order they appear, left to
  right: CASE adds one, END takes one away. A whole
  CASE WHEN x THEN 1 ELSE 2 END written on one line nets to nothing, and must
  not leave a CASE open over the rest of the file -- everything below it then
  keeps its scripting keywords and the parser refuses the lot.
  Never let the count go below zero. A stray END with nothing open is a
  scripting END; let the count go negative and the NEXT real CASE looks
  already closed, so its ELSE is cut and the statement around it is thrown
  away.
  Count on every line you KEEP, including a bare END or ELSE you kept
  because a CASE was open. That END is the one that closes it.
  Do not count on a line you replaced. A line that is gone contributes
  nothing to the depth.

Count CASE depth on a copy of each line with STRING LITERALS AND COMMENTS
BLANKED OUT, carrying quote and comment state across lines. A keyword inside a
quoted string is not scripting, and a 600-line statement is exactly where a
stray '... END ...' turns up. Handle ' " ` ''' """ -- /* */ and #.

THREE RULES FOR THAT BLANKED COPY, ALL THREE LOAD-BEARING.

  It comes back EXACTLY as long as the line it was made from. Replace each
  character you are hiding with a space -- two spaces for /*, three for ''' --
  rather than deleting it. Positions measured on the copy are used to cut the
  real line, which is how the BEGIN-on-one-line rewrite keeps the body, and a
  copy that is one character short cuts the body in the wrong place.

  EVERY line goes through it, including lines you are already dropping as
  part of a multi-line RAISE or a signature. Quote and comment state carries
  across lines; skip a line and the state is stale for everything after it,
  so an END inside a long quoted string reads as scripting and the 600-line
  statement holding it is destroyed.

  Any look-ahead -- finding where a RAISE or a signature ends, gathering a
  loop header -- gets a COPY of that state, never the live one. Hand it the
  live state and it walks lines the main pass has not reached yet, and every
  quote from there to the end of the file is tracked wrong.

Three more shapes:
  RAISE USING MESSAGE = @@error.message — the last line of the exception
    handler every generated file ends with, and by a distance the commonest
    thing a parser refuses. It re-throws an error, reads no table and touches
    no column, so it is nothing to a scan — but one of them puts the file on
    the "check by hand" list, and a list padded with hundreds of files nobody
    needs to check is a list nobody reads. Consume it up to its semicolon,
    which may be several lines later.
  CREATE OR REPLACE PROCEDURE `x.y.z`(IN tbl STRING, ...) — drop the
    signature, which no parser reads, and KEEP the BEGIN ... END body, which
    is ordinary SQL worth reading.
  FOR x IN (SELECT ...) DO / WHILE ... LOOP — a loop header names a real
    table, and a FOR header also names the rows it walks. Turn a FOR header
    into "CREATE TEMP TABLE <x> AS SELECT * FROM (...);" so both survive: the
    table is seen, and the rows become a thing with a name. WHILE has no
    variable — turn that one into "SELECT * FROM (...);", the plain read it is.
    Read the table name off the line AS WRITTEN, not off the blanked copy —
    it is usually a quoted name and blanking would leave an empty query.
    Headers written across several lines must be gathered.

    Drop the variable and the two halves of ONE statement never join up: the
    header reads the table and builds nothing, the INSERT in the body has no
    source of its own, and the row on screen says the column goes into the next
    table while naming no next table at all.

    Match the word RAISE at the start of the line and nothing more. All four
    shapes turn up in one generated pipeline --
      RAISE USING MESSAGE = @@error.message;
      RAISE USING MESSAGE = "No latest feed data to be processed";
      RAISE USING MESSAGE = msg;
      RAISE;
    -- and a pattern written around USING MESSAGE misses the bare one, which
    is enough on its own to put a perfectly readable file on the check-by-hand
    list. Only when no CASE is open: a line starting with that word inside an
    open CASE is part of a statement, not the end of a handler.

    Where the signature ENDS is not where a RAISE ends, and reusing the RAISE
    rule here is expensive: a procedure's first semicolon sits inside its
    body, so "drop up to the semicolon" throws the body away. No parse error,
    no unreadable entry, nothing on any screen -- the table that procedure
    builds is known to Ripple nowhere and the scan reports no lineage to
    production. Count brackets instead, on the blanked copy, from the CREATE
    line downwards:
      the signature ends on the line where the argument list's brackets close
      again, or on the line BEFORE the first always-scripting line, whichever
      comes first -- that always-scripting line is the body's own BEGIN;
      the BEGIN line itself is never dropped as part of the signature. It is
      handled as scripting in its own right, and everything under it is read
      as the ordinary SQL it is.

    A FOR LOOP'S ROW VARIABLE IS PART OF THE CHAIN, SO THE HEADER KEEPS IT.
    A loop body writes through the variable and through nothing else:

      FOR rec IN (SELECT id, cm13 AS seg FROM customer_demographics) DO
        INSERT INTO final_published (id, seg) VALUES (rec.id, rec.seg);
      END FOR;

    Rewrite that header to a bare read and the INSERT in the body has no
    source of its own, so the two halves of ONE statement never join up: the
    scan comes back with no production table, and the finding's own text says
    the column goes "into the next table" while naming no next table at all.
    The rows the loop walks are a thing with a name, built here, read below,
    gone at the end of the file -- a temporary table in all but spelling, and
    its name is written on the very line the row points at. So put ONE helper
    in templating.py and send every loop rewrite through it:

      loop_read(variable, query)
        with a variable  ->  CREATE TEMP TABLE <variable> AS SELECT * FROM <query>;
        without one      ->  SELECT * FROM <query>;

    FOR has a variable and keeps it. WHILE has none and stays the plain read
    it always was. Use the same helper for the whole-loop-on-one-line shape
    further down, so both spellings of one loop give the same answer. The
    temp table it builds is fenced to its own file exactly like any other
    temporary, so two files that both loop over a variable called rec do not
    join up into a chain that never runs.

unwrap_blocks(text) returns the text UNCHANGED when there is no scripting in
it, so callers can hand everything to it without asking first. Asking first
means walking every line of every file twice, which on a few thousand files
is minutes rather than seconds.

BUILD THE RESULT ONE LINE AT A TIME: exactly one line out for every line in,
joined back together with newlines at the end. A rewrite that covers several
lines -- a RAISE, a signature, a gathered loop header -- puts its whole
rewrite on the FIRST of those lines and an empty statement on each of the
others. Nothing is ever joined, nothing is ever deleted. Line 412 of the copy
is line 412 of the file, so a finding points at a line somebody can open, and
that is the only line anybody can go and look at.

Keep a flag as you go, and where no line matched anything, hand back the text
you were given, the same object, untouched. That is what lets Phase 4 send
every file through this without asking first.

TWO WAYS THIS FILE CAN DELETE THE ANSWER

Both silent, both producing a clean "no impact":

  IF (SELECT MAX(cm13) FROM customer_demographics) IS NOT NULL THEN
      Replace the whole header line with an empty statement and the query in the
      condition goes with it -- so the file comes back with risk none and every
      count zero. The identical guard written as ASSERT reads correctly, and
      that is the test to keep applying: where two spellings of one guard give
      opposite answers, the difference is a bug.
      Before dropping an IF, an ELSEIF or a WHILE header, look in it for the
      first balanced bracket group holding a SELECT. If there is one, replace
      the line with `SELECT * FROM <that group>;` instead of with `;`. It is a
      real read of a real table, building nothing -- which is exactly what an
      ASSERT already produces. Where there is no query in the condition, drop
      the line as before; keeping every IF would hand the parser scripting it
      cannot read.

      Find that bracket group on the LINE AS WRITTEN, never on the copy with
      the strings blanked out -- the same rule as the loop header, for the
      same reason. The table inside a BigQuery guard is normally a backticked
      name, and the blanked copy has emptied those backticks, so what comes
      back is `SELECT * FROM (SELECT COUNT(*) FROM ``)`: the read of
      customer_demographics has gone, and the file reports risk none with
      every count zero, which is the answer this whole trap exists to stop.
      Skip quoted text while you count the brackets, so an apostrophe inside
      a string literal cannot unbalance them.

  FOR rec IN (SELECT tbl FROM cfg_tables) DO SELECT 1; END FOR;
      A whole loop on ONE line. It matches "a loop header" and does not END with
      DO, so it was treated as a header written across several lines -- and the
      gather then looked for a line ending in DO, never found one, and returned
      "everything to the end of the file". Every line after it became an empty
      statement. No parse error, no unreadable entry, nothing on any screen: the
      trail stops one table short and that is reported as where the chain
      ends. The same loop written across two lines gave the right answer.
      Match the one-line form first and rewrite it in place -- the bracket group
      becomes `SELECT * FROM (...)`, the body is kept, and the trailing
      `END FOR` goes. And when a gathered header never finishes, give up on THAT
      LINE, never on the rest of the file.

BEGIN WITH THE BODY ON THE SAME LINE IS STILL A BODY.

The always-scripting check above wants BEGIN alone on its line, which is how
a procedure is normally written. Written on one line --

  BEGIN CREATE OR REPLACE TABLE ds.final_published AS SELECT ... ; END;

-- the whole body goes to the parser as part of the BEGIN and comes back as a
single thing nobody can read: no target, no sources. The table that procedure
builds is then known to Ripple nowhere, and the scan says there is no lineage
to production over code that loads a published table.

So match a BEGIN that has something other than TRANSACTION after it on the
same line, and swap JUST THE KEYWORD for a statement end, leaving the rest of
the line exactly where it is:

  BEGIN CREATE OR REPLACE TABLE ...   ->   ; CREATE OR REPLACE TABLE ...

Leave BEGIN TRANSACTION to the always-scripting list -- it opens a
transaction rather than a block and has no body to keep. Count CASE depth on
what is left of the line AFTER the keyword, not on the whole line.

Tests: line numbers preserved through every substitution; a CASE written down
the page survives intact; a scripting END is dropped; a keyword inside a
string is not treated as scripting; BEGIN does not eat the statement after
it; a procedure body is kept; a loop header keeps its table; a multi-line
RAISE is consumed whole.
````

**How to tell the prompt arrived whole.** The last line of the block above is
*"RAISE is consumed whole."* If the bottom of what you pasted into the chat is
not that line, it did not all go in — paste it again.

**Check it worked.** From `C:\ripple-build`:

**Type this into the black window.**
```
python -m pytest tests/test_templating.py -q
```

You want `passed`. There is one test worth checking on here too, and again you do
not have to read any code to check it. Paste this back into the same chat window:

**Paste this into the chat.**
````text
Show me the test that proves a CASE written down the page comes through this file
intact. Quote for me, as plain English outside the code, the SQL it feeds in and
what it expects back. If there is no such test, say plainly that there is not,
and write one.
````

If it answers that there is no such test, ask for one and run the command again.
Without it this file quietly destroys 600-line statements, and everything
downstream then reports a clean result over code nobody read.

**If it will not work.** Ctrl+F for **Checking that a phase worked**, near the
top, and then **When the chat goes wrong**, at the very end. Between them they
cover every way a phase comes back wrong.

---

## Phase 3, part three — the shapes the parser simply refuses

**Saves to:** `ripple-build/ripple/scanner/rescue.py`

Placeholders and scripting blocks are two reasons a real file will not parse.
There is a third, and it needs a file of its own so that nobody is ever tempted
to work around a parse failure somewhere further downstream.

**Paste this into the chat.**
````text
[PASTE THE CONTRACT CARD FIRST]

Build ripple/scanner/rescue.py.

Some BigQuery statements are perfectly ordinary and the SQL parser still refuses
them. When it refuses one, it does not refuse only that statement - it can lose
the statements either side of it too, so one unusual line costs a whole file.

This file rewrites those shapes into ones the parser accepts. It keeps the SAME
TWO RULES as the templating file, and for the same reasons:

  The rewrite is done to a COPY on the way INTO the parser. The file on disk is
  never touched, and everything shown on screen comes from the file as written.
  Somebody sent to a line to check must find what they were told they would find.

  Every replacement puts back exactly as many line breaks as it swallowed. A
  finding points at a line number, and that number is the only thing anybody can
  act on.

Shapes to handle, each with a note on what it costs to get wrong:

  UNDROP TABLE t
      A hard parse error, which takes the statements around it down as well.
      Rewrite it so it lands as a generic command and read the table name back
      out of that.

  CREATE TABLE a CLONE b, ... COPY b, ... LIKE b,
  CREATE SNAPSHOT TABLE a CLONE b, CLONE b FOR SYSTEM_TIME AS OF <expr>,
  CREATE MATERIALIZED VIEW a AS REPLICA OF b
      Whole-table copies. These have no SELECT in them at all, so without a
      rewrite the chain stops dead on the one line that promotes a staging table
      into the published one. Keep the word THE FILE USED - COPY, CLONE, LIKE,
      SNAPSHOT - and hand it out with the statement, so the row on screen can say
      what the file says rather than calling everything a SELECT *.

  A function called without brackets that the parser reads as a keyword.
      Put the name back as a column, and record that it was a guess: whether the
      writer meant the column or the built-in is not knowable from the file, so
      a usage found this way is never asserted as certain.

  SELECT ... FROM APPENDS(TABLE `p.d.cust`, NULL)
  SELECT ... FROM `p.d.f`(TABLE `p.d.orders`, 'apple')
  SELECT ... FROM ML.PREDICT(MODEL `p.d.m1`, TABLE `p.d.cust`)
      A bare TABLE in argument position is a hard parse error, and a hard parse
      error takes the neighbouring statements down with it. Drop the word
      TABLE and leave the name behind. This is how an incremental load is
      written, which is how a published table is kept up to date.

  CREATE EXTERNAL TABLE t ... WITH CONNECTION `p.us.c`
  CREATE EXTERNAL TABLE t ... WITH PARTITION COLUMNS (dt DATE)
      On every BigLake, object and Iceberg table, and on every hive-partitioned
      one. Drop each clause. Match the brackets yourself: an OPTIONS clause is
      full of quoted strings, and a bracket inside one closes nothing.

  LOAD DATA INTO t (a STRING) FROM FILES (format='CSV', uris=[...])
      Often the only place a landing table's columns are written down anywhere
      in the repository. Rewrite it as CREATE TABLE t (a STRING) and drop the
      FROM FILES clause, which names a bucket rather than a table.

  EXPORT DATA OPTIONS(uri='gs://feed/partner/*.csv') AS SELECT ...
      Leave the SELECT and take everything before it away. Also provide
      export_targets(text), which returns (0-based line of each EXPORT, the
      feed it delivers to) - read BEFORE the rewrite, because the rewrite takes
      the OPTIONS clause with it.

  config { } and js { } blocks in a .sqlx file
      Drop them whole. pre_operations { } and post_operations { } hold real SQL
      that really runs: drop the braces, keep the contents, and end them with a
      semicolon so they read as one more statement in the file. Match braces
      yourself, for the same reason as the brackets.

Two things this file does NOT do.

  A column named after a bracket-less built-in is put back on the PARSE TREE,
  in the reading file, not by rewriting text here. Which of the two the writer
  meant is not knowable from the file, so both are followed and the usage is
  marked as not certain - that is a decision about a parsed node, and doing it
  in text would change what the statement says.

  Turning a whole-table copy into the SELECT * it is also happens on the parsed
  copy, in the reading file, and the word handed out with the statement is
  COPY, CLONE, LIKE or RENAME. What belongs here is only the text that stops
  the parser reading the copy at all: CREATE SNAPSHOT TABLE becomes CREATE
  TABLE, CREATE MATERIALIZED VIEW x AS REPLICA OF y becomes CREATE TABLE x COPY
  y, and FOR SYSTEM_TIME AS OF <expr> is dropped - but ONLY when the statement
  already holds a CLONE or a COPY, because the same words are legal on an
  ordinary FROM and the parser reads those.

Guard all of it behind ONE cheap scan of the text: if none of these words is
there, hand the text straight back. Almost every file in a repository contains
none of them, and walking every file twice is minutes rather than seconds on a
few thousand. Do not put the TABLE-argument test behind a word boundary - a
backticked function name ends in a backtick, so `p.d.f`(TABLE x) would be
skipped while APPENDS(TABLE x) was caught.

Everything you rewrite here must be reported honestly downstream. A statement
that only became readable because of a rewrite is still a real statement, but a
statement you could NOT rescue must end up on the "check by hand" list rather
than silently producing nothing.

Where a new shape turns up later that the parser refuses, it is added HERE. Never
work around a parse failure in the reading file or the lineage file - by the time
the trouble reaches those, the statement has already been lost.

Tests: each shape above parses after the rewrite and not before; the line count
of the rewritten text matches the original exactly; the copy handed to the parser
is not the text that ends up on screen.
````

**How to tell the prompt arrived whole.** The last line of the block above is
*"is not the text that ends up on screen."* If the bottom of what you pasted
into the chat is not that line, it did not all go in — paste it again.

---

# PHASE 4 — reading SQL into statements and usages

**Saves to:** `ripple-build/ripple/scanner/dialectcompat.py`,
`ripple-build/tests/test_dialectcompat.py`,
`ripple-build/ripple/scanner/sqlread.py`, `ripple-build/tests/test_sqlread.py`

This is the file the whole tool rests on, and this is the longest phase in the
kit. Expect to spend a whole window on it, and expect the reply to come back in
parts.

**Two ways a reply goes wrong, and they need different words from you.** They
look different on your screen, so work out which one you are looking at before
you type anything. This is the same in every phase, but Phase 4 is where you will
meet it.

* **It stopped dead.** The last thing on the screen breaks off in the middle of a
  word or a line, as though somebody pulled the plug. Nothing has been left out
  on purpose. Type into the same window: *"carry on from the last complete line,
  and tell me which line that was."*
* **It ended tidily, but it skipped.** The reply finishes politely and offers to
  help you further — and somewhere up in the middle you can see
  `...rest of the implementation`, or a section it says it will "add later", or a
  line on its own that just says `pass`. That is not a stop, it is a hole, and
  telling it to carry on will not fill the hole. Do not paste the phase in again
  either. Type: *"Give me PART 1 OF N only, complete, ending at the end of a
  whole function rather than halfway through one, and tell me what N is."*

Either way, stay in the SAME window and ask for each part in turn, so the chat
still remembers what it decided in part one. A second window has forgotten
everything and will invent different names. All the parts go into ONE file — the
method, with your hands, is under **When one file arrives in several parts**,
near the top of this document.

**If this phase comes back wrong — and it is the one most likely to — do not
improvise.** Ctrl+F for **When Phase 4 goes wrong**. It is the next heading after
this phase, and it holds five ready-written replies, one for each way this file
goes wrong.

**Do the small file first, in its own window.** It is ninety lines and it takes
ten minutes, and everything in the big file depends on it. Paste the block below,
save what comes back, then start a fresh window for the big one.

**Paste this into the chat.**
````text
[PASTE THE CONTRACT CARD FIRST]

Build ripple/scanner/dialectcompat.py.

sqlglot renames the keys inside its own parse-tree nodes between major versions.
Some of those renames are SILENT: ask for the old key and you are handed nothing
at all rather than an error. Code written against the old name keeps running and
quietly stops finding anything, on a machine where every test still passes.

Three of them switch off things this tool exists to do:
  Star.args["except"]        became  except_       SELECT * EXCEPT(col) stops
                                                   being noticed, so a column
                                                   dropped by name is reported
                                                   as carried through
  Merge.args["expressions"]  became  whens         every rename a MERGE makes
                                                   disappears - and a MERGE is
                                                   how a published table is
                                                   normally loaded
  Select.args["from"]        became  from_         empties the check that
                                                   decides which tables a
                                                   SELECT * covers

So every key of that kind is read through a function here, and NOTHING ANYWHERE
ELSE IN RIPPLE reads one directly. That rule is the whole point of the file.

Provide exactly these:

  RENAME_NODE            The class for ALTER TABLE a RENAME TO b. Newer versions
                         call it AlterRename, older ones RenameTable. Take
                         whichever exists; this one is loud rather than silent,
                         but it belongs with the rest.
  from_of(select)        The FROM clause of a SELECT. Try "from", then "from_".
  star_except(star)      The columns named in SELECT * EXCEPT(a, b), as a list.
                         Try "except", then "except_".
  star_replace(star)     The columns swapped by SELECT * REPLACE(x AS a).
                         Try "replace", then "replace_".
  is_unpivot(pivot)      True for UNPIVOT, false for PIVOT. PIVOT turns rows
                         into columns; UNPIVOT turns columns into rows, and the
                         two do opposite things to a column's future.
  pivot_fields(pivot)    The FOR x IN (...) parts, as a list. Try "fields", then
                         "field". For an UNPIVOT the IN list IS the column list
                         being folded away, so reading the wrong key means a
                         statement that hard-fails on the day the column goes is
                         reported as carrying it through untouched.
  pivot_columns(pivot)   The output column names a PIVOT produces - total_Q1,
                         total_Q2. sqlglot works these out itself and that is
                         worth having: the rule involves the aggregate's alias,
                         whether it has one, and each IN value. An empty list
                         means it did not work them out, and the caller must not
                         pretend to know the names.
  is_temporary(stmt)     Was this CREATE written TEMP or TEMPORARY? Look through
                         the statement's properties for a TemporaryProperty. A
                         temporary table lives inside one script, so two files
                         that each build a "t" are not sharing a table. Read the
                         wrong key and they get merged, which INVENTS a chain to
                         a published table nobody touched - and that finding
                         looks exactly like a real one.
  merge_whens(merge)     Every WHEN branch of a MERGE, whichever shape it
                         arrives in. Newer versions wrap them in a Whens node
                         under "whens"; older ones put them under "expressions".

Every one of these must return an empty list or a plain false rather than
raising when the key is missing entirely, so that an unfamiliar version degrades
to finding less rather than to a crash.

PIN THE PARSER. Write the exact version into the project's requirements, and
write one test that fails loudly if the installed version is not the pinned one.
Write another that calls every function above against a parsed statement of the
right shape and fails if any of them comes back empty when it should not. Those
two tests are the only warning anybody gets when the library moves underneath
them, so they are not optional and they are not "nice to have".

Give me the complete file, and put both tests in tests/test_dialectcompat.py.
````

**Check it worked.** From `C:\ripple-build`:

**Type this into the black window.**
```
python -m pytest tests/test_dialectcompat.py -q
```

You want `passed`. Those two tests are the only warning anybody gets on the day
somebody installs a different version of the SQL reader underneath Ripple, so it
is worth knowing they are real ones. Do not go hunting for version numbers to
change by hand to find out — paste this into the same window instead:

**Paste this into the chat.**
````text
Show me the pin test. If a different version of sqlglot were installed tomorrow,
which line of that test goes red, and what would I see on my screen? Then show me
the test that calls every function in dialectcompat.py, and tell me which test
goes red if one of those functions is emptied out. If either test would stay
green, it is not testing anything - fix it and give me both tests again.
````

---

Now the big file. This is the one that arrives in parts, and the one most likely
to come back wrong. If anything about the reply looks off, do not improvise:
Ctrl+F for **When Phase 4 goes wrong**, the next heading after this phase.

**Paste this into the chat.**
````text
[PASTE THE CONTRACT CARD FIRST]

Build ripple/scanner/sqlread.py and tests/test_sqlread.py.

The whole value of Ripple is in this file. A word search can tell you that
MARKET_CODE appears in a file. Only parsing can tell you it appears inside a
WHERE clause compared against the literal 'US' — which is the difference
between "mentioned here" and "this breaks on the 18th".

PARSING

parse_file(f, cfg) -> (statements, problems, opaque)
parse_repo(index, cfg, on_progress) -> ParsedRepo

Parse each block with sqlglot at cfg.sql_dialect. If the whole block is
refused, SPLIT IT AND PARSE STATEMENT BY STATEMENT. sqlglot reads a file as
one piece and gives up at the first statement it cannot follow, taking every
other statement down with it — so one GRANT, one procedure call, one line in
another dialect costs the entire file. Splitting first means one bad
statement costs one statement, and the file is reported as "3 of 14 could not
be read" rather than "unreadable".

Write the splitter yourself: split on semicolons that are NOT inside quotes
or comments, returning (statement_text, 0-based start line). Handle ' " `
escapes, -- and # line comments, and /* */ blocks.

Give each statement its own SPAN, not the block's. The splitter already knows
where each statement begins and costs a single character scan rather than
another parse, so: where the split chunks and the parsed statements line up one
for one, give each statement its own start line and its own last line. Where
the two counts do not match, give every statement the block's offset and the
block's last line rather than a span that might be wrong.

Carry the last line on the Statement as line_end, and BOUND every finding to
it:

  locate(file, column, kind, line_offset, line_end) -> 1-based line

Score only the lines inside the statement first. Only when nothing inside it
matches - which happens where the name exists only after a placeholder is
filled in - widen the search to the whole file, rather than dropping the
finding.

In a 600-line generated file holding sixty statements, an unbounded search
regularly picks the best-scoring WHERE clause in somebody else's statement
about somebody else's table: the finding right, the line wrong, and the whole
finding wasted because the person opens the file and sees nothing there.

Run every block through fill_placeholders (only when needed) and then
unwrap_blocks from Phase 3, on the way into the parser ONLY.

A TEMPLATED DATASET IS NOT A DATASET. Where a block had placeholders in it,
keep the set that placeholder_names gives back, and before anything reads the
parsed statement, walk every table in it: if its DATASET part is one of those
words, take the dataset off and leave the table name alone.

A filled-in {{stage_dataset}} looks exactly like a dataset called
stage_dataset, and the file next door writes the very same dataset as a
different hole. Record it as what it honestly is -- the table, dataset not
stated. A name with no dataset goes on matching any dataset, which is the
safe direction: Ripple would rather show a finding somebody can dismiss by
opening the file than hide one nobody will ever know was missed.

For each parsed statement build a Statement with:
  target   from Create, Insert, MERGE, Delete and Update. MERGE matters as
           much as CREATE and INSERT: on BigQuery, Snowflake and Databricks it
           is the usual way a production table is loaded, and without it the
           chain stops one step short of the table anyone actually reads.
           DELETE and UPDATE matter for a different reason — they build
           nothing, so they look uninteresting, but a DELETE whose WHERE
           filters on the attribute being decommissioned stops working on the
           day it goes, and the table it prunes quietly fills up instead.
           If the file is a program with exactly one write target, use that.
           More than one write target: report that lineage past this job is
           not traced, and say which tables.
  sources  every table the statement reads, EXCLUDING names defined by
           WITH — a CTE is a name for a query, and treating one as a table
           invents a link that is not there. A DELETE or UPDATE also reads its
           own target, or nothing ever looks at its WHERE clause.

           Gather sources by walking EVERY table node in the WHOLE statement,
           not the tables of its first SELECT. A union is two SELECTs side by
           side, and reading only the first leaves the second half's table
           recorded nowhere - so a change to it produces no findings anywhere
           and the scan comes back clean.

           That walk finds the table the statement WRITES as well, so leave it
           out - and leave it out BY NODE IDENTITY, never by comparing names.
           Hold on to the target's table node before you walk, and skip the one
           table in the walk that IS that node.

           Comparing names means comparing through same_table, which is
           deliberately loose: a name with no dataset has to go on matching one
           that has a dataset, or every templated chain in the repository
           breaks. Loose is right for FOLLOWING a chain and catastrophic for
           EXCLUDING a source. Three ordinary shapes lose everything they read:

             CREATE OR REPLACE TABLE ds.events_rollup AS
               SELECT ... FROM ds.events_*
             CREATE OR REPLACE TABLE {{target_dataset}}.orders AS
               SELECT ... FROM stage.orders
             INSERT INTO t SELECT ... FROM t

           In the first the wildcard covers the target's own name. In the
           second the templated dataset is dropped, leaving a bare "orders"
           that matches "stage.orders". The third really does read the table it
           writes. Any of them, compared by name, is indexed as reading nothing
           at all, and the scan over it comes back clean and confident.

           Comparing the node cannot make that mistake and costs nothing.

           Do NOT gate this on the statement having a SELECT in it. A MERGE
           whose USING names a table, and an UPDATE ... FROM, both read a whole
           second table and have no SELECT anywhere. Gating on one meant they
           recorded no sources, were never indexed as reading anything, and no
           scan could reach them — on BigQuery that is the statement that loads
           the published table.

           A WHOLE-TABLE COPY has no SELECT in it either, and it is how a
           staging table is promoted into a published one:

             CREATE OR REPLACE TABLE published.customers COPY  stage.customers
             CREATE TABLE            published.customers CLONE stage.customers
             CREATE TABLE            published.customers LIKE  stage.customers
             ALTER TABLE stage.customers RENAME TO published.customers

           That single line is what connects everything upstream to the table
           people actually read. With no source recorded the trail died at the
           staging table and the screen said "last table in the chain — not
           matched by your production naming rule", which reads as an answer.

           A whole-table copy carries every column and writes none of them
           down, which is exactly what SELECT * means. So rewrite it, on the
           parsed copy only, into `CREATE TABLE <target> AS SELECT * FROM
           <source>` — then every piece that already follows a star works on it
           unchanged: the column is carried on, the hop is marked worked out
           rather than read, and the table is listed as one whose column list
           cannot be seen. Keep the word the file used (COPY, CLONE, LIKE,
           RENAME) on the Statement and carry it all the way to the screen. A
           row that says "Carried by SELECT *" about a file that says COPY
           sends somebody to the line to look for a statement that is not there,
           and then to doubt the finding rather than the label.

           CREATE SNAPSHOT TABLE is the same thing, but those two extra words
           make the parser give up on the whole statement. Retry it with
           "CREATE SNAPSHOT TABLE" replaced by "CREATE TABLE", and only after
           the parser has already failed, so it costs nothing on the statements
           that read normally.

           TABLE FUNCTIONS. A BigQuery TABLE FUNCTION is a table as far as
           lineage is concerned — it is named, it is read in a FROM clause, and
           every column of its body travels through it:

             CREATE OR REPLACE TABLE FUNCTION ds.recent(d STRING) AS (
               SELECT cm13 FROM customer_demographics WHERE dt = d)
             CREATE OR REPLACE TABLE published.summary AS
               SELECT cm13 FROM ds.recent('2026-01-01')

           BOTH halves are invisible to a naive reader. The definition parses as
           a function, not a table, so it publishes nothing; and the call parses
           as a function call whose table node carries NO NAME AT ALL, so it
           reads nothing. The chain breaks in the middle and the published table
           is never mentioned.

           Take the name off the function signature for the target, and off the
           call for the source. Two traps: a scalar UDF parses as the very same
           node with the very same kind, so tell them apart by their BODY — a
           table function's is a SELECT, a scalar one's is an expression, and
           getting this wrong turns every helper in the repository into a table.
           And some things written in a FROM clause look exactly like a table
           and are not. BigQuery's own built-in table functions WRAP a table
           rather than being one; the table they wrap is parsed separately and
           found anyway, so taking the wrapper's name as well only invents a
           table nobody has — on the answer, in the dependency picture, and in
           the letter. Skip every one of these, and skip nothing else:

             EXTERNAL_QUERY  APPENDS  CHANGES  GAP_FILL  VECTOR_SEARCH
             RANGE_SESSIONIZE  SESSIONIZE  OBJECT_METADATA  SEARCH_INDEX_STATUS
             TABLE_DATE_RANGE  TABLE_QUERY
             GENERATE_ARRAY  GENERATE_DATE_ARRAY  GENERATE_TIMESTAMP_ARRAY

           The last three are the ones that catch people out: a generated range
           of dates or numbers is written in a FROM clause exactly like a table
           and is not one, and a repository that builds a calendar that way
           reports a table called GENERATE_DATE_ARRAY feeding production.

           Write the list as a set matched on the name in CAPITALS, so the
           spelling in the file does not matter. Anything not on it that sits
           in a FROM clause IS treated as a table — the other way round, an
           unfamiliar function name silently swallows a real read.

           A TABLE HANDED INTO A FUNCTION IS A REAL READ, AND IT IS NOT A
           TABLE NODE.

             SELECT cm13 FROM APPENDS(TABLE `p.ds.customer_demographics`, NULL)
             SELECT cm13 FROM `p.ds.pick`(TABLE `p.ds.orders`, 'apple')
             SELECT cm13 FROM ML.PREDICT(MODEL `p.ds.m1`,
                                         TABLE `p.ds.customer_demographics`)

           The rescue pass takes the word TABLE out so the statement parses at
           all, and what is left arrives among the function's arguments as an
           ordinary column reference. So on top of the table walk, look at the
           arguments of any function sitting in a FROM clause and take every
           COLUMN-shaped one as a source as well.

           Only column-shaped ones. A literal, a number or a nested call is not
           a table, and inventing one out of a string puts a table nobody has
           on the answer.

           Miss this and the real table is nowhere in the statement: an
           incremental load - which is exactly how a published table is kept up
           to date - reads nothing at all, and the chain stops one hop short of
           production.

           Skipping the wrapper is only half of it. BigQuery hands a table to
           one of these with the word TABLE in front of it:

             SELECT cm13 FROM APPENDS(TABLE `prj.ds.customer_demographics`, NULL)
             SELECT cm13 FROM `prj.ds.pick`(TABLE `prj.ds.orders`, 'x')
             SELECT cm13 FROM ML.PREDICT(MODEL `prj.ds.m1`,
                                         TABLE `prj.ds.customer_demographics`)

           The parser refuses that word outright, so it has to come out on the
           way in — and what is left arrives as an ordinary COLUMN reference
           among the call's arguments, not as a table node at all. So walk the
           arguments of any call sitting in a FROM clause and record every
           column-shaped one as a table this statement reads, under the call's
           alias as well if it has one. Miss it and an incremental load — which
           is exactly how a published table is kept up to date — is recorded as
           reading nothing, and the trail into that table never exists.

           Only column-shaped arguments count. A string, a number or a nested
           call is not a table, and building one out of a literal puts a table
           nobody has on the answer.

           BIGQUERY WILDCARD TABLES. Date-sharded tables are ordinary, and the
           only way to read one is a wildcard:

             SELECT cm13 FROM `prj.ds.customer_demographics_*`
             WHERE _TABLE_SUFFIX BETWEEN '20260101' AND '20260131'

           The source name recorded is `customer_demographics_*`, asterisk and
           all. Nobody has a table called that, so scanning a real shard matched
           nothing and scanning the family name matched nothing either — zero
           findings, a clean "no impact", on a change that breaks a published
           table.

           What a wildcard matches is not a guess: BigQuery only allows the star
           at the end, and it stands for every table in that dataset whose name
           starts with the part in front of it. So a wildcard covers a name when
           the name starts with that prefix. Match it in same_table AND in the
           lookup index — the index is keyed on the exact short name, so fixing
           only the comparison changes nothing.

           One deliberate addition to BigQuery's own rule: a person asked what
           breaks types the family the way they think of it — "customer_
           demographics", with no trailing separator, which BigQuery would not
           match. Match that too. It costs a row somebody can dismiss by opening
           the file; refusing it costs the clean "no impact" this tool exists to
           prevent. Do not go further than that: `ev` must never match
           `events_*`.

           Say so on the result. A finding reached through a wildcard names the
           wildcard, as the file spells it, in a card beside the findings — never
           on another screen. The dataset still rules a match out exactly as it
           does for an ordinary name.

           A $ ON THE END OF A NAME IS A DAY, NOT A DIFFERENT TABLE. BigQuery
           writes and reads one single partition by hanging a decorator on the
           table name:

             INSERT INTO `prj.ds.customer_demographics$20260101` SELECT ...
             SELECT cm13 FROM `prj.ds.customer_demographics$20260101`

           That is one day of customer_demographics. Keep the $20260101 as part
           of the name and every decorated read splits off from the table it
           belongs to: nothing matches, the chain is never followed, and the
           answer comes back as a clean "no impact" on a pipeline that writes
           that table every morning. Strip a trailing $ followed by digits
           wherever you cut a name down — both in the short name and in the
           dataset.name form — and leave everything else about the name alone.

Statements sqlglot returns as a Command — a procedure call, a loop, an
EXECUTE IMMEDIATE, a scripting block — go into `opaque` keyed by file, with
line, first code line, and the SQL text. Kept, not reported: whether they
matter depends entirely on whether the name somebody is chasing turns up
inside one, which is not known here.

Report as unreadable, with plain English, a line number and the line itself:
  a file where some statements failed ("2 of 63 statements in this file could
    not be read — the other 61 were")
  a file that was read but NOT ONE statement was understood — the quietest way
    to lose a file, and the reason the wrong SQL dialect can look like a
    clean repository
  a file that plainly contains SQL none of which could be extracted
  a program that runs a .sql file which is not in this repository — Ripple has
    never read that query, so nothing it does is covered by any scan
Add a hint when the file is a template, and when the repository is being read
as generic SQL. Collapse repeated failures in one file to a single entry with
a count: it is still one file for a person to go and check.

Reading a repository takes minutes, so one unexpected shape must never end it.
Wrap the reading of EACH FILE in its own guard. If it throws, log it, add one
entry to the unreadable list naming the file and the kind of error - "Ripple
could not read this file at all (AttributeError) - check it by hand" - and
carry on with the next file. Without that guard every file after the bad one is
lost too, and the person gets a traceback instead of an answer.

The same care one level down, everywhere in this file: check that a slot holds
an expression before you walk into it. sqlglot puts plain booleans in some of
them, and reaching for .find on one takes the whole file down.

  Two guards on the binding itself. A statement that FILLS a variable must
  never be given that variable as one of its own sources, or the chain reads
  itself and walks in a circle. And where a variable's own statement comes out
  of the source walk with nothing, take every table named anywhere in it,
  metadata reads apart: a DECLARE holds its query in a place the ordinary walk
  does not reach, and without this the table the watermark is read FROM is
  recorded nowhere at all.

WHICH TABLE A COLUMN CAME FROM

In a real warehouse the same two or three key columns are in nearly every
table, so nearly every join has the same name on both sides. Matching on the
name alone reports a filter on the OTHER table's column as a usage of the one
being changed — a finding about the wrong table, in a repository where that
is the ordinary case rather than an edge one.

The statement usually says which is which, and when it does, that is a fact
about the SQL rather than a guess: a.cm13 belongs to whatever a is. Write
_belongs_to(...) returning "yes", "no" or "unknown":
  no qualifier    -> yes if the statement reads only one table, else unknown
  qualifier resolves to another table -> no
  qualifier resolves to a CTE          -> unknown (that IS the chain being
                                          followed, so not a reason to rule
                                          the usage out)
Where it says "no", drop the usage. Where it says "unknown", KEEP the usage
and set certain=False. Nothing is thrown away; the table is marked as
inferred rather than asserted.

WHAT NAME A COLUMN LEAVES UNDER

output_names(stmt, column) -> list[str]

Renames often happen inside a subquery — c.last_upd AS lut_ts buried in a
ranking, then carried out unchanged by the enclosing SELECT — so resolve from
the innermost query outwards. That is what keeps the chain joined up; without
it the trail goes cold at exactly the statements that matter most.

A WHOLE ROW CAN BE CARRIED AS ONE VALUE, AND THAT IS A STAR TOO.

BigQuery lets a query pass an entire row around as a single value, and the
standard dbt-utils `deduplicate` macro is written exactly that way:

    SELECT unique_row.* FROM (
      SELECT ARRAY_AGG(original ORDER BY loaded_at DESC LIMIT 1)[OFFSET(0)]
               AS unique_row
      FROM customer_demographics original
      GROUP BY id)

`original` on its own — a bare name that is the table's ALIAS rather than any
column of it — is the whole row. So `unique_row.*` publishes every column the
table has, which is precisely what SELECT * means, and it has to be treated the
same way: the column is carried on, and the table built from it is listed as one
whose column list cannot be read.

Miss it and a deduplicated staging table, an ordinary thing to find in a dbt
repository, gives a clean "no impact" with no warning of any kind.

Only a BARE reference counts. `original.loaded_at` is one column, and
`STRUCT(a, b) AS s` is two named ones; treating either as a whole row would put
every column of the table on a chain the statement never touched.

the INNERMOST query outwards. A SELECT * means every name passes through
untouched.

GROUP THE STATEMENT'S SELECTs BY HOW DEEPLY NESTED EACH ONE IS, AND WORK THE
LEVELS INNERMOST FIRST. Depth is simply how many SELECTs a SELECT sits inside.
Every SELECT at one depth is read into ONE set of maps, and that set is applied
once before you move out a level.

Do it by nesting instead — each SELECT handing its answer to its parent — and a
union comes out wrong, and a union is ordinary:

    CREATE OR REPLACE TABLE deduped_bca_union AS
    SELECT cm13 AS a_name FROM customer_demographics
    UNION ALL
    SELECT cm13 AS b_name FROM other_source

The two halves sit side by side; neither is inside the other. Treat the second
as if it wrapped the first and you feed the wrong map into the next step, so
cm13 is followed under the second half's name while the table downstream reads
the first half's — and the trail goes cold with a clean "no impact".

Read the branches in THE ORDER THEY ARE WRITTEN, and keep that order in what you
return. SQL takes a union's output names from its FIRST branch, so the first
branch's name must be the first name on your list: it is the one the rest of the
warehouse is reading.

A column also leaves under MORE THAN ONE name more often than it looks:

  SELECT CAST(cm13 AS STRING) AS cm13_str, cm13 FROM customer_demographics

Following only the first was a silent, expensive mistake: the next table
reads cm13, not cm13_str, so the chain stopped one step short and a change
that really does reach a published table is reported as no production
impact. Return every name, capped at 6, with the name carried through
UNCHANGED always first so it survives the cap.

Build the projection maps for a statement in ONE pass and cache them on the
statement. One scan asks the same statement about the same column many times,
and on a 600-line statement each answer means walking the whole tree again.
Measured on a real repository, this was most of the time a scan took.

Cache a statement's sources the same way, upper-cased, because reads_from is
asked over and over. THREE things widen a statement's sources AFTER it is
built - fencing a file's temporary tables, binding its script variables, and
unfencing a temp name along a CALL edge - and every one of them has to clear
that cached copy. Leave it stale and all three look as though they were never
applied: the fence does not hold, the variable joins nothing, the CALL edge
carries nothing, and every test written against those functions on their own
goes on passing.

WHAT ONE LEVEL HOLDS. Read each level into four things, and cache the whole list
on the statement:

    direct       a column name -> the names it is carried through or plainly
                 renamed as (cm13 -> customer_code)
    derived      a column name -> the names it is reshaped into: a CAST, a
                 function, a STRUCT field, a PIVOT's output
    passthrough  true when any SELECT * at this level is carrying the
                 remaining names through untouched
    dropped      the names no star at this level carries on — named in an
                 EXCEPT, standing in front of a REPLACE, renamed away by a
                 RENAME, or folded away by a PIVOT

That dropped set is the one the PIVOT and REPLACE rules further down both write
into.

Then, level by level, innermost first: resolve the names you are holding through
that level's two maps. Where the level is a pass-through, keep every name it did
NOT drop and put those FIRST, ahead of anything the maps produced — the
untouched name is the one the rest of the warehouse is likeliest to be reading.

If every name you hold is dropped at a level, the column really does stop inside
the statement. Return nothing and let the trail end there; saying so is the
point of tracking this at all.

If a level names the column NOWHERE — no rename, no star, nothing — keep the
name you arrived with and carry on to the next level. A level that is silent
about the column is the ordinary case, not a dead end:

    CREATE OR REPLACE TABLE stage_c AS
    WITH other AS (SELECT x FROM y)
    SELECT cm13 FROM customer_demographics JOIN other USING (k)

That CTE is a level of its own and says nothing about cm13. Empty the list of
names there and the statement publishes nothing under any name, so the table it
builds is never reached — one unrelated CTE, and the whole chain is gone.

Where a screen needs ONE name for a row, show the first name published, and fall
back to the name the column arrived under when nothing is published at all. A
row still has to say which column it is about.

HOW A COLUMN IS USED

usages_of(stmt, column, table) -> Usage[]

Look for the column in: the select list (Column -> select, anything else ->
transform with the function name), WHERE and HAVING and QUALIFY (filter, with
the literal it is compared against as `detail`), JOIN ... ON (join_key),
UNNEST in a join (transform), GROUP BY (aggregation), the statement's own
ORDER BY (ranking if there is a LIMIT under it, otherwise sort), window ORDER
BY (ranking — where removal is silent and awful), window PARTITION BY
(dedup_key), and MAX/MIN (dedup_key, which decides which row survives).

THIS LIST IS THE WHOLE GAME, AND A SHORT ONE IS THE WORST BUG THIS TOOL HAS.
A clause you do not read is a column you cannot see, and the answer that comes
back is not "unreadable" — it is "the name appears, but no lineage to a
production table", which reads as a reassurance. Every one of these was found
that way:

  QUALIFY            BigQuery and Snowflake filter on a window result, and
                     where nearly every dedup in a real pipeline is written.
                     The column often appears NOWHERE else in the statement.
  window PARTITION BY  the other half of a dedup. The ORDER BY picks the
                     winner; the PARTITION BY says what it wins against. Take
                     it away and one record survives for the whole table
                     instead of one per key, silently.
  WINDOW w AS (...)  the same dedup written as a named window clause instead
                     of inline. Writing it the other way round is not a reason
                     to miss it.
  UNNEST             FROM t, UNNEST(col) has no ON clause to look at.
  ORDER BY           writes the name down, so removing the column stops the
                     statement compiling and the table stops loading.

A DELETE or UPDATE has a WHERE clause and no SELECT at all. Requiring a SELECT
made both invisible, so "DELETE FROM stage WHERE market_code = 'US'" was
reported as no usage whatsoever.

Two more places to look in one of those, and neither is the WHERE.

An UPDATE's SET list is a usage in its own right:

    UPDATE final_published t SET t.market = s.cm13
    FROM customer_demographics s WHERE t.pub_id = s.pub_id

cm13 is named nowhere else in that statement. Read every assignment in the SET
list and record a transform whose detail is the word SET. Miss it and the one
statement that patches the published table reports nothing.

And once you have read the WHERE and the SET, if you have still found nothing,
look at the whole statement once more and record a plain select usage for any
reference to the column you find anywhere in it. A DELETE or an UPDATE can name
the column inside a subquery or a USING clause, and half a reading is worse
than none here: the statement stops running on the day of the change either
way, and the table it prunes quietly fills up instead.

A MERGE is worse again, and it is how a published table is normally loaded on
BigQuery, Snowflake and Databricks. When USING names a table directly there is
no SELECT anywhere in the statement, so it recorded no sources at all, was
never indexed as reading anything, and no scan could reach it however hard it
looked. Read all four parts of one:
  ON <condition>                       join_key
  WHEN ... AND <condition> THEN ...    filter — often the only place the
                                       column is named in the whole statement
  THEN UPDATE SET t.market = s.col     the column is published as `market`
  THEN INSERT (a, b) VALUES (x, y)     renames by position, like a plain INSERT
The last two are renames: follow the target's name onwards, not the source's,
or the chain walks off the end at the one statement that loads the table.

                                       Read ONLY the right-hand side of that
                                       SET. It reads s.col and writes t.market;
                                       reading the whole assignment reports the
                                       target table's own column as a usage of
                                       the source, so a scan of the source
                                       grows a finding about a column that
                                       never came from it.

Each part records its own kind, and a statement can record several: the ON
condition is a join_key, a WHEN's extra condition is a filter and carries the
literal it is compared against, and the UPDATE SET value and the INSERT's
VALUES expression are both a select.

A COLUMN LIST WRITTEN OUTSIDE THE SELECT RENAMES BY POSITION. Two shapes, and
the last thing output_names does is walk the name through both of them.

    INSERT INTO stage_tbl (member_id) SELECT cm13 FROM customer_demographics
    CREATE OR REPLACE VIEW  v1(a, b)          AS SELECT cm13, region FROM ...
    CREATE OR REPLACE TABLE s1(a STRING, b STRING) AS SELECT cm13, region FROM ...

The SELECT hands its values over by POSITION, not by name, so the name the
column carries downstream is the one in the list on the left. The INSERT shape
is the load statement at the heart of most foundation files — a TRUNCATE, then
an INSERT with the target's whole column list written out. The CREATE shape is
the ordinary way a team publishes friendly names over cryptic warehouse codes; a
view, a materialized view and a CTAS all allow it, and a CTAS list carries types
where a view's does not, but both give the name the same way.

Follow the SELECT's own name past either of these and the chain walks off the
end at the statement that loads the table everybody downstream reads. The CREATE
shape goes wrong in both directions at once: the trail stops at the view, AND a
downstream table reading the OLD name is reported as a confident break — when
after the rename that name is not a column of the view at all.

Only line the two lists up when they are plainly the same length and there is no
star in the select list. Where the arity cannot be checked, leave the name
exactly as it arrived rather than inventing a position for it.

Return the most informative reading of each kind, most consequential first:
ranking, dedup_key, filter, join_key, transform, aggregation, select. One the
SQL was explicit about beats one it was not; after that, one carrying a
detail beats one that does not.

              sort, excluded, pivoted, layout, star, renamed, retyped,
              dropped
              Usage also carries via_star: whether this column only leaves the
              statement because of a SELECT *

There are fifteen kinds, not seven. The first one left after the sort is the
finding's headline: it picks the words on the row, the impact sentence, and
whether the finding counts as breaking at all. Sort them most consequential
first, in this order, and give each one the words it wears on screen:

  ranking      Ranking
  dedup_key    Dedup key
  layout       Partition or cluster key
  filter       Filter
  join_key     Join key
  transform    Transform
  aggregation  Aggregation
  sort         Sort order
  pivoted      Named in PIVOT
  excluded     Named in EXCEPT
  renamed      Renamed by ALTER TABLE
  dropped      Dropped by ALTER TABLE
  retyped      Changed by ALTER TABLE
  select       Select
  star         Carried by SELECT *

Get that order wrong and a table partitioned by the column being decommissioned
heads its row with "Select" and reads as a column quietly passing through, on a
statement that stops compiling on the day of the change.

Four of those words are swapped when the file says something more exact, so
that the row matches the line it points at: "Named in UNPIVOT" when the detail
says UNPIVOT, "Named in REPLACE" when a REPLACE rather than an EXCEPT names the
column, "Carried by COPY" (or CLONE, LIKE, RENAME) for a whole-table copy, and
"Carried by a placeholder" where the file writes a hole where the column list
goes.

Carry a detail on the usage wherever there is one, because the screen prints
it: the literal a filter compares against, PARTITION BY or CLUSTER BY for a
layout, PIVOT or UNPIVOT, REPLACE, MAX or MIN for a dedup key, UNNEST or SET or
the function's own name for a transform, and the new name for a rename.

Also: mode_of(usages) returning "Transformed" if any transform, dedup_key or
aggregation, else "Direct pull"; locate(file, column, kind, line_offset)
giving the best guess at the real 1-based line, scoring lines by whether they
also contain the keywords that kind lives near; snippet(file, line, note)
returning a few lines of real code with the important one marked.

A FILE THAT IS ONE QUERY AND BUILDS NOTHING. A dbt model is a bare SELECT.
There is no CREATE, no INSERT and no MERGE, so nothing in the file names the
table it builds — dbt does, after the file. models/marts/customer_published.sql
builds customer_published. Get this wrong and a three-hop dbt chain gives
productionTables 0, reachesProduction false, and the finding text "Selected
straight through into the next table" when there was no next table. EVERY dbt
repository produced zero lineage, and dbt is the commonest way a BigQuery
pipeline is written. That is the loudest possible version of this tool's worst
failure: a calm, clean, complete no-impact answer over none of the picture.

  The name is not a guess. A dbt model's name IS its file stem — that is the
  rule dbt itself runs on, and ref('customer_published') elsewhere in the
  repository resolves through exactly the same rule. Dataform (.sqlx) and every
  hand-rolled one-query-per-file runner work the same way.

  Three levels of evidence, labelled differently because they are not equally
  sure. Record which one applied on the statement, as named_by:
    "Dataform" — the file is .sqlx, or it opens with a config { } block.
    "dbt"      — the file is under models/, snapshots/ or definitions/, or it
                 calls ref(), source(), config() or this().
    "file"     — a .sql file holding exactly ONE query and no CREATE anywhere.
                 Something runs it and puts the rows somewhere; naming that
                 somewhere after the file is the convention every such runner
                 uses. Following it costs a row somebody can dismiss by opening
                 the file. Not following it costs the chain.

  Only ever name the ONE statement in the file that has no target and is a bare
  query. Two bare SELECTs in one file cannot both be the table the file is
  named after. For "dbt" and "file" also require that the whole file is that
  one query; a Dataform model may have pre_operations beside it.

  THE TRAP: check the FILE'S OWN FIRST LINE OF CODE, not the parse tree. Several
  statements that build nothing and are named after nothing are rewritten into a
  bare SELECT on the way into the parser — EXPORT DATA is the one that caught
  this — and by the time the tree exists they are indistinguishable from a dbt
  model. EXPORT DATA delivers a file to somebody outside the warehouse; naming
  its destination "a.sql" would be a table that exists nowhere. So for the "dbt"
  and "file" readings, require the file to say SELECT or WITH on its first line
  of code once comments and placeholders are taken off.

  Say it on the result. Anybody sent to that line to check will not find the
  table name written on it, and a finding somebody cannot verify is one they
  dismiss. See the namedByFile list in Phase 5.

A TEMPORARY TABLE BELONGS TO ONE FILE. A TEMP table is gone when its script
finishes, so two files that both build a "t" are not sharing a table — they
cannot be, because a static scan can never know two files ran in one session.
Temp names in real repositories are t, tmp, stg, base, deduped, so collisions
are the norm. Get this wrong and two unrelated files, each building its own
"t", put BOTH of their published tables on the chain, marked the second one
breaking, and printed no warning of any kind.

  The dataset rule that keeps stage.orders apart from archive.orders cannot
  help, because a temp table has no dataset. So invent one: a scope standing for
  "inside this file", made of the file's own path with every non-alphanumeric
  character turned into an underscore, and marked with a "#" — a character no
  warehouse allows in a name. Apply it once the whole file is parsed, so a temp
  table used above the line that creates it is still caught.

  Move a name only when it has no dataset, or the _SESSION dataset BigQuery uses
  for them. ds.t is a real table that happens to share a short name with a temp
  one, and taking it would cut a genuine chain.

  same_table must treat a scoped name as ABSOLUTE: if either side carries the
  mark, the two datasets have to be identical. This is the one place the loose
  "no dataset given matches anything" rule is switched off, and it has to be —
  nothing outside that file can be reading a table that exists only inside it.
  For the same reason, when reading() is asked for a name with no dataset, drop
  any statement whose only matching source is scoped.

  Do NOT count the scope as a dataset when working out which names are
  ambiguous, or every "t" in the repository is reported as a name standing for
  more than one table. And STRIP THE MARK for display: it is your fence, not
  something anybody wrote, and a name on screen that is in no file sends
  somebody looking for a table that does not exist.

  Watch the leak one screen further along. Anything that walks ONWARDS from a
  finding — "published tables that stop being refreshed" does — must use the
  name the reader keyed, not the name shown on screen. Carry the real target on
  the finding for that purpose. Fencing the chain off moves the false
  claim rather than removing it, and the unrelated published table reappeared
  under "stops being refreshed", worded as certainly as before.

INFORMATION_SCHEMA IS NOT DATA. It is BigQuery's catalogue of its own tables,
and its views are called COLUMNS, TABLES, JOBS, VIEWS, PARTITIONS — ordinary
words, and a warehouse of any size has real tables called some of them.
Without this, a real p.base.columns is reported as feeding a published table it
never touches, with a warning beside it that blamed CAPITALISATION — so the one
thing on screen pointing at the problem named the wrong cause, and following it
would not have found anything.
  If ANY dot-separated part of a qualified name is INFORMATION_SCHEMA, or the
  first part starts with "region-", it is the warehouse describing itself: never
  record it as a source, never record it as a target, never merge it with
  anything. Nothing that changes in a real table changes a COLUMN of
  INFORMATION_SCHEMA.COLUMNS — a ROW of it changes, and a row is not lineage.

PIVOT AND UNPIVOT. Both fold a column away and build differently-named ones out
of it, and both NAME the column while doing it, so the statement itself fails on
the day the column goes. Neither was read at all, and each failed in its own
direction.

  UNPIVOT was the worse of the two and the only case in the whole suite that
  hedges DOWNWARDS on a statement that hard-fails:
    CREATE OR REPLACE TABLE s1 AS SELECT * FROM customer_demographics
    UNPIVOT (val FOR metric IN (cm13, other_col));
  read as a plain SELECT *, so the answer was risk "low", breaking false, and
  the sentence "Nothing here fails on the day of the change" — printed about a
  statement whose UNPIVOT list stops being valid SQL.

  PIVOT failed the other way: the columns it builds are total_Q1 and total_Q2,
  worked out from the aggregate's alias and each IN value. Nothing derived them,
  so the trail was declared finished one hop early with the note "Last table in
  the chain", and the published table reading total_Q1 was never named.

  A PIVOT hangs off the FROM clause, not off any select list, so nothing that
  walks projections, WHERE clauses or joins can ever see it. Collect them from
  the FROM's table or subquery and from every join's, then:
    which columns it NAMES — an UNPIVOT's IN list; a PIVOT's IN list plus the
      columns inside its aggregates
    which columns it BUILDS — for a PIVOT, the output names the parser works
      out for you; for an UNPIVOT, the value column names plus the name column
      (renaming the source column changes what is written into the name column
      just as surely, so follow both)
  Map each named column to each built one as a reshape, add every named column
  to the "dropped by the star over it" set, and record a usage of its own kind —
  breaking on removal, rename and type change, but NOT on a value change, since
  an UNPIVOT folds whatever is there into rows either way. Suppress the SELECT *
  usage for a column a pivot consumes: the pivot is definitive about that one
  column, and letting the star speak as well puts "carried through untouched"
  beside "named here, and this statement fails without it". And label the row
  with the word the FILE uses — PIVOT and UNPIVOT are opposite operations.

PARTITION BY AND CLUSTER BY ON THE CREATE LINE. These sit outside the SELECT, so
nothing that walks a query can see them. Without this, a table partitioned by the
very column being decommissioned returned NO usages at all, and the whole chain
came back risk low, groups 0, couldNotRead 0. It is not a column of the table
being built, so no chain follows from it — but the name is written on the CREATE
line, so the day the column goes the statement stops compiling, the table stops
being built, and every published table underneath it quietly serves data that
has stopped being refreshed. Walk the CREATE's properties for anything whose
name mentions Partition or Cluster and record a usage. Note that PARTITION BY
cm13 with nothing round it parses as a bare IDENTIFIER, not a column, so
searching for columns alone finds nothing.

A COLUMN NAMED AFTER A PARENLESS FUNCTION. BigQuery lets CURRENT_DATE,
CURRENT_TIME, CURRENT_TIMESTAMP and CURRENT_DATETIME be written with no
brackets, so "SELECT current_date FROM customer_demographics" parses as a call
and not as a column at all. A table with a column of that name then produces the
cleanest possible zero: risk none, prod [], found 0, nameInTables 0 — Ripple did
not miss the column, it never saw one. Backticked, the very same scan is risk
medium and reaches production.
  Which of the two the writer meant cannot be known from the file: both are
  valid BigQuery and both are written exactly the same way. So FOLLOW BOTH —
  read the node back as a column — and mark every usage of that name in that
  statement as not certain. Only where the file writes the name with NO brackets
  after it; CURRENT_DATE() is unambiguously the function.

A HOLE WHERE THE COLUMN LIST GOES. A great many Airflow DAGs build SQL as
  cols = "cm13, cm14"
  sql = f"CREATE OR REPLACE TABLE ds.final_published AS SELECT {cols} FROM ..."
The placeholder is filled in before BigQuery ever sees it, so the column list
genuinely is "cm13, cm14" — but it is not in the file, and Ripple reads
"SELECT cols FROM ...". Without this, Ripple believes the published table has
exactly one column, called "cols", and answered reachesProduction False, risk
none, unreadable 0, couldNotRead 0. Identical with .format().
  A hole standing where a projection goes is a SELECT * that has not been filled
  in yet. Replace it with a star, which makes the whole existing star machinery
  work: the trail carries on, the table is listed as one whose column list is
  not visible, and every finding past it is marked worked out rather than read.
  Record on the statement that the star came from a placeholder, and use that
  everywhere the screen would otherwise say the file writes SELECT *. It does
  not, and a row that claims it does sends somebody to a line where no such
  statement is written.

A VALUE PASSED THROUGH A SCRIPT VARIABLE IS STILL LINEAGE. A BigQuery script
does not only pass values from table to table. Two shapes, both measured as
groups [] over a change that really does break the published table.
    DECLARE cutoff DATE DEFAULT (SELECT MAX(cm13) FROM customer_demographics);
    CREATE OR REPLACE TABLE final_published AS
    SELECT order_id, amount FROM orders WHERE order_date > cutoff;
  final_published's whole row set is chosen by cutoff, and cutoff IS MAX(cm13).
  Filed as a dead end two lines above the CREATE that uses it.
    FOR rec IN (SELECT id, cm13 AS seg FROM customer_demographics) DO
      INSERT INTO final_published (id, seg) VALUES (rec.id, rec.seg);
    END FOR;
  The loop HEADER was rewritten to a read with no target and the INSERT in the
  BODY had no source, so the two halves of ONE statement never joined up — and
  the finding's own text said the column went "into the next table" while naming
  no next table at all.
  Treat the variable as what it behaves like: a thing with a name, built here,
  read further down, gone at the end of the file — a temporary table in all but
  spelling. Fence it to its file exactly as you fence a temp table, then add it
  to the SOURCES of every statement in that file that names it. Count BOTH
  spellings: the bare name for a scalar, and the qualifier for a loop row
  (rec.seg). Rewrite the loop header to build a temp table of the variable's
  name so the row it walks can be followed like anything else; WHILE has no
  variable and stays the plain read it was.
  Two things this must NOT do. Only a variable filled FROM A QUERY counts —
  DECLARE i INT64 DEFAULT 0 binds nothing anybody can follow, and giving every
  loop counter a name on screen fills it with dead ends. And a DECLARE publishes
  ONE thing, the variable, whatever fed it: MAX(cm13) is named nothing at all,
  so without that the column came out still called cm13 and the statement below
  it matched nothing.
  Guard the shapes you walk. sqlglot puts plain BOOLEANS in some of these slots
  — BEGIN TRANSACTION is an exp.Set with no assignment in it — and reaching for
  .find on one takes down the whole file with an AttributeError.
  INSERT ... VALUES has no SELECT anywhere in it, so every usage check keyed on
  a SELECT was skipped and the statement recorded no usage of anything. That is
  exactly how a loop body is written. Read the values.

  A LOOP ROW IS A SCRIPT VARIABLE TOO, and the file is the only place that says
  so. The rewritten header reaches the reader as an ordinary CREATE TEMP TABLE,
  indistinguishable from any other. So once the file is parsed, for each
  temporary table it builds, look at the file's OWN line at that statement's
  offset: if that line reads FOR <that same name> IN, the temporary table is
  that loop's row variable, and it joins the DECLAREs and the SETs in the
  variable map.
  Read it off the file rather than off the tree for two reasons. The rewrite is
  what took the word FOR away, so the file is where the original wording still
  is - and the name really is written on the line the reader is sent to, which
  is the whole test for whether Ripple is allowed to use it.

  Say it again where usages_of is written, because that is where it gets
  forgotten: an INSERT with a VALUES list has no SELECT anywhere in it, so
  check for one BEFORE you give up on a statement for having no SELECT. Find
  the VALUES clause anywhere in the statement, look for the column inside it,
  and record a plain select usage for it. That is what carries the loop row's
  field into the published table, and without it the finding's own text says
  the column went "into the next table" while naming no next table at all.

A TEMP TABLE CROSSES A CALL, BECAUSE THE PROCEDURE RUNS IN THE SAME SESSION.
    -- a.sql
    CREATE TEMP TABLE stg AS SELECT id, cm13 FROM customer_demographics;
    CALL ds.publish_it();
    -- b.sql
    CREATE OR REPLACE PROCEDURE ds.publish_it()
    BEGIN CREATE OR REPLACE TABLE final_published AS SELECT id, cm13 FROM stg; END;
  A BigQuery TEMP table IS visible inside a procedure called in that session, so
  this chain really runs. The per-file fence renamed the CALLER's stg to
  "#A_SQL.stg" and left the procedure's stg alone, the two stopped matching, and
  the trail died on the temp table — with the file that actually breaks filed
  under "the name appears, but no lineage to a production table", the one
  sentence this tool exists to stop anybody printing over a live chain.
  Do NOT weaken the fence and do NOT change same_table. Record the CALL EDGE
  instead: which file calls a procedure which other file defines. Read both ends
  off the file TEXT, because neither survives parsing — the procedure signature
  is dropped on the way in (that is what lets the body be read at all) and the
  CALL comes out as a statement nobody understood. Then unfence a temp name only
  along an edge you can point at, WIDENING sources rather than replacing them,
  in BOTH directions and the whole way down a chain of calls: a procedure a
  procedure calls is still the first caller's session, and a temp table built
  inside a procedure is visible to whatever called it.
  Match the procedure on its SHORT name and take every file that defines it.
  This is FOLLOWING a chain, the side of that rule where a loose match is right,
  and it can only add a chain, never cut one. Where two callers hand their own
  stg to the SAME procedure, add both and follow both. A name the SQL QUALIFIED
  is a real table that happens to share a short name — leave it alone. And never
  report an unresolved CALL as a gap: every real pipeline is full of calls to
  procedures kept somewhere else, and one line each would bury the list.

THE CTEs OF ONE WITH ARE ALL AT THE SAME DEPTH, AND THEY FEED EACH OTHER. That
is two separate clean wrong answers, and both come from grouping a statement's
SELECTs by nesting depth and then reading each group ONCE.
  A rename fed by a rename in the same WITH is lost:
    WITH src     AS (SELECT k, cm13 FROM customer_demographics),
         renamed AS (SELECT k, cm13 AS customer_code FROM src),
         final   AS (SELECT k, customer_code AS cust_code FROM renamed)
    SELECT * FROM final
  All three are at one depth, so the map holds cm13 -> customer_code AND
  customer_code -> cust_code, and reading it once applied only the first.
  Get this wrong and the trail stops at customer_code, while the published table reads
  cust_code — a name Ripple never said out loud — and the scan comes back clean.
  Which CTE feeds which is not knowable from depth. Do NOT try to put them in
  order: run the level to a FIXPOINT instead, which gets the same answer
  whatever order they are written in. The set only grows and every name comes
  out of the statement, so it terminates; keep a counter as a backstop. Keep the
  name carried through UNCHANGED first, so it survives the six-name cap and is
  still what the screen shows.

A SIBLING'S EXCEPT MUST NOT DELETE A COLUMN ANOTHER STAR IS CARRYING. Same
cause, opposite harm:
    CREATE OR REPLACE TABLE stage_p AS
    WITH cust AS (SELECT * FROM customer_demographics),
         hits AS (SELECT * EXCEPT (cm13) FROM web_events)
    SELECT cust.*, hits.url FROM cust JOIN hits USING (k)
  That EXCEPT belongs to hits, which never reads the scanned table at all.
  Applied to the whole level it deleted the column arriving through cust.*, the
  trail died INSIDE the statement, and a change that really does break the
  published table came back risk none. Give every star ONE VOTE and drop a
  column only when EVERY star at that level drops it. Which star a column flows
  through cannot be told from the select list, so this keeps it whenever any
  star could still be carrying it — a spare row rather than a lost chain. The
  single-star case is unchanged, and SELECT * EXCEPT on its own still stops the
  trail and still says so.

ONE ALIAS CAN MEAN TWO THINGS IN ONE STATEMENT. Build the alias map PER SCOPE,
never flat across the whole statement.
    CREATE OR REPLACE TABLE final_published AS
    SELECT t.k, o.amount
    FROM (SELECT * FROM customer_demographics) t
    JOIN orders o ON o.k = t.k
    WHERE t.cm13 = 'A'
      AND EXISTS (SELECT 1 FROM legacy_dim t WHERE t.k = o.k)
  The inner EXISTS re-binds t to legacy_dim. Flat, that was the ONLY binding of
  t the map held — the outer t is a subquery alias, which is not a table at all
  and so was never recorded — so the breaking WHERE t.cm13 was ruled out as some
  other table's column. Get this wrong and the answer reads risk low, breaking false, over a change that
  stops this statement compiling and stops the published table loading.
  Two halves to the fix, and both are needed. Bind a SUBQUERY's alias to every
  table that subquery reads — a list, because where it reads more than one the
  SQL has not said which. And resolve a qualifier by walking OUT from the column
  to the nearest SELECT that binds that name, which is what SQL itself does.
  Keep the flat map as the FALLBACK: it is what answers for a qualifier bound
  somewhere you cannot see, and it must still answer "unknown" there rather than
  ruling the usage out.

A STRUCT IS ONE COLUMN, AND ITS FIELDS ARE STILL READ BY NAME.
    SELECT k, STRUCT(cm13 AS code, seg AS segment) AS payload FROM ...
  The table really does have one column, payload, so publishing "code" as a
  column of it would invent a column that is not there — SELECT code FROM that
  table is an error. But payload.code IS how the field is read, and following
  the struct only under "payload" ended the trail at the wrapper. Get this wrong and the
  chain stopped at the struct while payload.code was both selected AND filtered
  on one hop later, and the scan reported no production table at all.
  Publish each field under its DOTTED name and never its bare one. Carry it
  ALONGSIDE the wrapper's own name, not instead of it, so a statement that reads
  payload whole is still followed. Match a dotted name against the QUALIFIER too
  — matching on the leaf alone is exactly the invented-column mistake above —
  and register an aliased qualified reference (payload.code AS customer_code)
  under its dotted name as well as its bare one. SELECT AS VALUE STRUCT is the
  other spelling and is different: AS VALUE dissolves the wrapper outright, so
  there the fields ARE the columns and are published bare.

TWO WAYS A STRUCT FIELD IS WRITTEN, AND ONE OF THEM HAS NO "AS".

    STRUCT(cm13 AS code) AS payload     the field is code   -> payload.code
    STRUCT(cm13)         AS payload     named after itself  -> payload.cm13

Take the field name from whichever is written. Read past the bare one and a
struct built out of plain column names publishes nothing at all, so the trail
ends at the wrapper.

Then map EVERY column inside the field's value to that dotted name, not just a
bare one: STRUCT(UPPER(cm13) AS code) is still cm13 leaving as payload.code.

A struct inside a struct nests the same way, and the column is published under
each level of the path — payload.inner and payload.inner.code both. Follow three
deep and stop: that covers everything hand-written, and the cap is only there so
a generated nest cannot run away.

AS VALUE only dissolves the wrapper when that STRUCT is the WHOLE select list.
Written beside other columns it is an ordinary struct column and keeps its
wrapper.

A SELECT WRITTEN AS A VALUE IS NOT A SOURCE OF ROWS. When you group a
statement's SELECTs by nesting depth to work out what each column leaves as,
skip any SELECT that sits in the select list, or inside a WHERE, HAVING,
QUALIFY, GROUP BY or ORDER BY. Those are values — one number, one list to test
against — and the names inside them are their own business.
    SELECT o.k,
           (SELECT MAX(d.cm13) AS c_alias FROM customer_demographics d
            WHERE d.k = o.k) AS peak_cm
    FROM other_source o
  Get this wrong and the statement's output name for cm13 comes back as
  c_alias — a name that exists only inside the brackets and appears on no table
  anywhere. The real name is peak_cm, which is what the next table reads, so the
  chain went cold one hop early and reported no production impact. The mirror is
  just as bad: WHERE k IN (SELECT cm13 AS c_alias FROM ...) INVENTED a column
  called c_alias on the table being built. A subquery in FROM or JOIN, and a
  CTE, really do hand their columns to the query around them: leave those alone.
  Walk up from the nested SELECT to the enclosing one and look at which argument
  of it the chain arrived through.

A JOIN HAS TWO HALVES AND THEY ARE OPPOSITE. Its SOURCE really does hand its
columns to the query around it — that is what a joined subquery is, and its
renames survive. Its ON CONDITION is a value, exactly like a WHERE, and the
names inside it are its own business:

    SELECT c.k, c.cm13
    FROM customer_demographics c
    LEFT JOIN ref_bands r
      ON r.k = c.k
     AND c.cm13 IN (SELECT cm13 AS band_code FROM allowed_bands)

Both halves arrive under the same argument of the join, so walking straight past
it counts the condition as a source. Get this wrong and the statement publishes
cm13 as band_code — a name written inside a join condition and belonging to no
table anywhere — while the next table reads plain cm13, is never reached, and
the scan says no production impact.

So as you walk out from a nested SELECT to the enclosing one, stop at a join and
ask which half you came through. A SELECT reached through the join's ON is a
value and contributes no names. Anything else reached through the join is a
source and contributes all of them. Count LIMIT as a value position too,
alongside the select list, WHERE, HAVING, QUALIFY, GROUP BY and ORDER BY.

SELECT * REPLACE(legacy_code AS cm13) NAMES cm13. Remove it and this statement
fails, exactly as it does with EXCEPT — and the column of that name downstream
is fed by the replacement from here on, not by this one. Ripple got the right
answer for the wrong reason: the rename was followed, but nothing said the name
was written down here, so the row read "breaking: false" about a statement that
stops compiling. Record a usage on the REPLACE target, add the replaced name to
the star's dropped set, and suppress the plain SELECT * usage for it. Label the
row REPLACE rather than EXCEPT — they are different statements and the file says
which.

A STAR IS NOT A COLUMN REFERENCE, SO SKIP IT WHEN YOU WALK THE SELECT LIST.
The names hanging off a star — EXCEPT(cm13), REPLACE(x AS cm13) — really do sit
inside it as ordinary column references, and a plain search for the column
finds them there. Read them as select-list usages and SELECT * EXCEPT(cm13)
reports cm13 as reshaped and carried onward into the next table, which is the
opposite of what that statement does with it — and "Transform" outranks "Named
in EXCEPT", so the wrong reading is the one that ends up on the row.

So when you walk the select list, spot a star first and handle it on its own
terms rather than as a column:
  EXCEPT(cm13)              nothing here. The star machinery at the bottom of
                            the function reports this one, as excluded.
  REPLACE(UPPER(cm13) AS x) the value really is reshaped, so record a transform
                            whose detail is the word REPLACE.
  REPLACE(other AS cm13)    the column's own NAME is written down here, so
                            record an excluded usage with the detail REPLACE.
                            The output column of that name is fed by the
                            replacement from here on, not by this one.
Then move to the next item without reading the star as a column.

SELECT * RENAME (cm13 AS cm13_new) IS THE THIRD SHAPE A STAR TAKES, and it does
two things at once. The star stops carrying cm13 on under its own name — add it
to the level's dropped set exactly as EXCEPT and REPLACE do — and it carries it
on under cm13_new, which is a plain rename and belongs in the direct map. The
old name is written down here, so this statement stops compiling on the day the
column goes.

Miss it and the star carries cm13 through untouched, so the trail follows a name
the table it builds does not have, and the finding points somebody at a column
that is not there.

Read all three off the star itself — EXCEPT, REPLACE and RENAME — the same
guarded way you read EXCEPT.

_TABLE_SUFFIX. A wildcard table reads a whole family of date-sharded tables, and
the query almost always narrows that down on the very next line:
    SELECT cm13 FROM `p.ds.customer_demographics_*`
    WHERE _TABLE_SUFFIX = '20260101'
Ripple followed the wildcard and never read the line under it, so scanning
customer_demographics_19991231 — a shard from 1999 this query provably never
touches — came back risk medium, breaking true, CERTAIN true, with no hedge
anywhere. The predicate is on the same line as the wildcard, inside the snippet
Ripple prints, and the answer contradicted it.
  Work out the shard's suffix from the wildcard's own prefix, then read the
  _TABLE_SUFFIX comparisons in the WHERE: =, !=, <, <=, >, >=, IN and BETWEEN
  against string literals. Excluded means drop the finding. Anything you cannot
  evaluate — a parameter, a date calculation, a variable — sets certain=false and
  the finding STAYS; guessing at one would trade an over-confident answer for a
  missing one. Only ANDs: an OR or a NOT above the comparison means other shards
  are read too. And never narrow when the person typed the family name with the
  asterisk in it, because then no one suffix can be tested.

  Two rules inside that reading, and both are the difference between a fact and
  a guess. Only judge a comparison when _TABLE_SUFFIX is on the LEFT of it:
  '20260101' = _TABLE_SUFFIX is legal, rare, and reading it backwards excludes
  the wrong shard — so treat that shape as one you cannot evaluate. And treat an
  IN list or a BETWEEN as one you cannot evaluate the moment ANY of its values
  is something other than a plain string literal, rather than judging on the
  values you can read and ignoring the rest.
  There are three answers per statement, not two. "Excluded" drops the finding.
  "Maybe" keeps every usage from that statement and sets certain=false on all of
  them — and that is also the answer when an OR or a NOT sits above the
  comparison, not a reason to ignore the predicate. "Reads" leaves the usages
  alone, and is also the answer for every statement with no _TABLE_SUFFIX in it
  anywhere.

ONE TABLE, TWO FILES THAT BUILD IT. A CREATE OR REPLACE replaces the whole
table, so only one of them can be the definition that runs. Two of them in two
files is a fork — usually a live copy and a stale one under archive/ or dev/
that nothing schedules. Without this, the ONLY finding reported comes from the
archive copy, presented with breaking true and certain true and the same wording
as any live finding, while the live definition appeared under "mentions only".
Where the real build is generated at deploy time and only the stale copy is
committed, that is a confident, clean answer about a pipeline that no longer
exists. Keep a map of short table name to the files that fully REPLACE it, and
report the ones with more than one. An INSERT or a MERGE adds to a table and
several files loading one that way is ordinary; only a CREATE forks it.

DATAFORM FILES. A .sqlx file is Google's own way of writing a BigQuery pipeline:
an ordinary SELECT with blocks on top that are JavaScript, not SQL.
    config { type: "table" }
    js { const x = 1 }
    pre_operations { DELETE FROM ... }

    SELECT cm13 FROM ${ref("customer_demographics")}
The parser refuses the whole file on the first line, so nothing at all is
learned from it. In the same place you rewrite the other shapes the parser
refuses, drop the config and js blocks whole (keeping their line breaks), and
for pre_operations and post_operations drop the brackets and KEEP the contents
as one more statement — those hold real SQL that really runs. Match braces
yourself rather than with a regular expression, because a brace inside a quoted
string closes nothing.

FOUR SHAPES THAT NAME A TABLE AND WERE INVISIBLE

Each measured as a clean answer over less than the whole picture.

  EXECUTE IMMEDIATE '<one quoted string>'
      The parser gives up and hands back a generic command, so the CREATE inside
      the string was read, understood as nothing, and produced no lineage — with
      the whole statement sitting in the file in plain sight. Parse the contents
      of the literal when the WHOLE thing after IMMEDIATE is one quoted string
      and nothing else (an INTO or a USING after it is allowed). Mark every
      statement that comes out built_as_text = "EXECUTE IMMEDIATE", carry that
      onto the finding, and say so on screen: the line it points at holds a
      string, not the CREATE the row describes, and somebody who opens it
      expecting the statement doubts the finding rather than the label.
      REFUSE, and stay unreadable, when the name is built rather than quoted:
      FORMAT(...), 'CREATE TABLE ' || env || '_mid', or a literal containing a
      "?" placeholder. In each of those the statement never exists as text
      anywhere, so there is nothing to read, and inventing the missing piece is
      the exact failure this reader exists to avoid.

      Try the TRIPLE quotes first — ''' and """ — and only then the single ones.
      A whole CREATE written inside an EXECUTE IMMEDIATE is nearly always
      triple-quoted, because it holds quotes of its own; check ' first and you
      read the opening ''' as an empty string, refuse the statement, and lose
      the chain that was written out in full in the file.
      One more refusal to build in: if the text inside the quotes parses to
      nothing but another statement the parser could not understand, you have
      learned nothing from it — leave the file's own statement unreadable and
      say so, rather than recording an empty one.

  ALTER TABLE t RENAME COLUMN a TO b
      _target_of covered Create, Insert, Merge, Delete and Update and NOT Alter,
      so a repository holding its own rename migration gave target None,
      sources [] and reported no impact at all for the column the migration
      renames. That is the plainest statement of a rename the language has. Add
      Alter to _target_of, add it beside Delete and Update where the target is
      also added to sources, and read its actions:
        RenameColumn   -> usage kind "renamed", and output_names returns the
                          NEW name, so it is followed as the alias hop it is
        Drop(Column)   -> usage kind "dropped", and output_names returns []
                          — the column stops here, in this file, by name
        AlterColumn    -> usage kind "retyped", the name is written down so the
                          migration itself fails without it
      "renamed" and "retyped" break on removal and rename. "dropped" breaks
      nothing: it is not broken BY the change, it IS the change — and it is
      worth reporting for exactly that reason.

  CREATE SEARCH INDEX / VECTOR INDEX / ROW ACCESS POLICY / UNDROP TABLE
      All name a table, most name columns of it, and none carries a column
      anywhere. The parser gives up on every one, so the whole statement was
      invisible: the file landed on the check-by-hand list with nothing saying
      which table or which column it was about. Read the table and the column
      list out of them with a REGULAR EXPRESSION rather than a parser, and
      record them as "referenced here" — never as lineage, never as an edge,
      never as a hop. Reading it loosely can add a row to a list; it must never
      move a chain. A row access policy filtering on the scanned column stops
      working the day the column goes, so risk may not read "none" while one of
      these names it. UNDROP TABLE is a HARD parse error, which in sqlglot loses
      the statements either side of it — rewrite it in the rescue pass so it
      lands as a generic command, and read the table name out of that. Report a
      statement read this way ONCE: on the "named here, but nothing is carried"
      card, and NOT also as a file nobody could understand.

  EXPORT DATA OPTIONS(uri='gs://feed/partner/*.csv') AS SELECT ...
      An export builds no table, so the trail had nothing to carry the column on
      to, and the answer read "no production table is affected" — true, and
      useless. The delivery is what breaks, and whoever reads that file every
      morning is outside this repository, so no scan of it will ever find them.
      Read the uri BEFORE the rescue pass strips the OPTIONS clause, drop the
      last path segment when it holds a "*" or a "." (that is a filename
      pattern, not a place), and hang the result on the statement as export_uri.
      Match exports to statements in FILE ORDER, not by line number: the rewrite
      removes the whole "EXPORT DATA OPTIONS(...) AS", so what is left starts on
      the line after the export's own.

Tests: a statement split rescues the readable statements around a bad one;
MERGE, DELETE and UPDATE are seen; CTE names are not treated as tables; a
column renamed inside a subquery is followed out; a column leaving under two
names returns both; a filter records the literal; a join on the other table's
column of the same name is not reported; where the SQL does not say, the
usage is kept with certain=False; a window ORDER BY is a ranking.
````

**Check it worked.** From `C:\ripple-build`:

**Type this into the black window.**
```
python -m pytest tests/test_sqlread.py -q
```

You want `passed`. Later, when you point Ripple at real code and most of it comes
back unreadable, the cause is almost never this file — it is the SQL dialect being
set wrong, or Phase 3 not being applied on the way in.

---

## When Phase 4 goes wrong — the five things to paste back

This is the longest file in the kit and the one most likely to come back wrong.
Every one of these is a sentence to paste into **the same window**, never a
fresh one — a fresh window has forgotten what it decided and will invent
different names.

**It ended tidily, but it skipped a piece** — "...rest of the implementation", a
section it says it will add later, or a line on its own that just says `pass`.
(If it simply stopped dead in the middle of a line, you do not need this one:
type *"carry on from the last complete line, and tell me which line that was."*)

**Paste this into the chat.**
````text
That file is not complete. Do not paste it again from the top.

Tell me first: how many lines do you expect the whole file to be, and how many
parts will you need to give it to me in? Then give me PART 1 OF N only,
complete, ending at a function boundary rather than mid-function, and say which
line it ends on. I will ask for the next part in this same window.

No "...", no "rest unchanged", no TODO, no function body left as pass. If a part
would still be too long, use more parts.
````

**It used a name that is not in the contract card.**

**Two letters in this one are yours to fill in before you paste it.** Where it
says X, type the name the contract card uses. Where it says Y, type the name the
chat used instead. Everything else goes in exactly as it is written.

**Paste this into the chat.**
````text
The contract card calls that X, not Y. Window 5 and window 8 are being built
against the card and will be looking for X. They cannot see what you renamed and
nothing will fail loudly -- it will simply find nothing.

Use the card's name everywhere and give me the file again. If you genuinely
needed a name that is not in the card, say so in one line at the top so I can
carry it to the other windows.
````

**Every test passes and you do not believe them.**

**Paste this into the chat.**
````text
Would any of those tests fail if the behaviour were missing? Show me the one
that catches it. Delete the body of the function it tests, in your head, and
tell me which test goes red.

If there is not one, add it. A test that passes against an empty function makes
a missing feature look finished, which is worse than having no test at all.
````

**It reads a parse-tree key directly.** The one rule in this phase that fails
silently, so check it every time. You do not have to read the code yourself — ask
the window that wrote it. Paste this in first:

**Paste this into the chat.**
````text
Which of the files you have just given me contain the six characters .args[ ?
List each one with the line number. Only ripple/scanner/dialectcompat.py is
allowed to have any.
````

If you would rather check with your own hands: open each file you saved in
Notepad, press Ctrl+F, and type `.args[` — exactly those six characters.

If any file except `dialectcompat.py` has one, paste the block below.

**Where it says `<line>`, type the line number you were just given** — or delete
the two words "at <line>" if you do not have one.

**Paste this into the chat.**
````text
You are reading a parse-tree key directly, at <line>. Nothing except
ripple/scanner/dialectcompat.py may do that.

sqlglot renames those keys between major versions and the renames are SILENT --
the old key returns None, so the code carries on and quietly finds nothing.
Star.args["except"] became "except_", Merge.args["expressions"] became "whens",
Select.args["from"] became "from_". Nothing raises, every test goes on passing,
and the answers go wrong.

Use the function in dialectcompat.py that already covers that key. If there is
no function for it, tell me which key you need and I will have it added there
first. Then give me the file again.
````

**It drops what it could not parse.** This is the big one, and it will do it,
because dropping things makes the result look cleaner.

**Paste this into the chat.**
````text
You are throwing away statements you could not read. That is the one thing this
tool may never do.

Anything the reader could not follow is reported on screen with the file and the
line, never dropped. A file where some statements failed reads "2 of 63
statements in this file could not be read - the other 61 were". A file where
NOTHING was understood is reported as its own case, because that is the quietest
way to lose a file and it is what a wrong SQL dialect looks like.

Put it back and give me the file again.
````

---

## Closing down for the night — end of evening one

Windows 0 to 4 are done. That is about 9,000 lines of the 22,000, and the single
hardest window of the thirteen is behind you.

**Do not start window 5 tonight.** It is 2,600 lines and it will not finish. A
window you have not started costs you nothing to leave. A window you are halfway
through costs you the whole file. Stop here even if the clock says you had time.

**1. Check the files are all on disk.**

**Type this into the black window.**
```
dir /s /b C:\ripple-build
```

Fifteen files, and you should be able to find every one of these in the list:

**Read this — there is nothing to type.**
```
ripple\__init__.py              ripple\paths.py
ripple\config.py                ripple\production.py
ripple\scanner\__init__.py      ripple\scanner\repo.py
ripple\scanner\templating.py    ripple\scanner\rescue.py
ripple\scanner\dialectcompat.py ripple\scanner\sqlread.py
tests\test_production.py        tests\test_repo.py
tests\test_templating.py        tests\test_dialectcompat.py
tests\test_sqlread.py
```

`card.txt` is in there too, and that is fine. If one of the fifteen is missing,
look for the same name with `.txt` on the end — that is Notepad, and the fix is
under **Saving a file the chat gives you**. Rename it tonight, while you still
remember which window wrote it.

**2. Run everything once, so tomorrow starts from a known answer.**

**Type this into the black window.**
```
python -m pytest -q
```

You want `passed`. **If it is red, fix it tonight**, in the window that wrote the
file, while that window is still open and still remembers what it did. A red
check left overnight is a red check you have to solve with a stranger.

**3. Write down four things.** Notepad will ask whether to create the file — say
yes:

**Type this into the black window.**
```
notepad C:\ripple-build\where-i-got-to.txt
```

Four lines, in your own words:

* tonight's date, and *"finished window 4, check passed"*
* any name a window invented and told you about, and whether you have already
  added it to `card.txt`
* anything you had to do by hand that this document did not mention
* if you did not finish a window: which one, and which file was half written

That file is the only memory the build has. Nothing else survives tonight.

**4. Now close everything, chat windows included.** All four of tonight's chat
windows are finished with. Nothing in them is needed tomorrow and nothing is
lost by closing them. The rule about never opening a fresh window is about the
middle of a phase, not the gap between two — every phase in this kit tells you
to open a fresh window anyway.

Tomorrow, search for **Starting the next evening**. It puts you back in five
steps, and then you carry on below.

---

# PHASE 5 — the catalogue, and following a column

**Saves to:** `ripple-build/ripple/catalog.py`,
`ripple-build/ripple/scanner/lineage.py`, `ripple-build/tests/test_lineage.py`

**Open a fresh chat window for this phase.** Paste the contract card into it
first, then the block below. This one is big — about 2,600 lines — so the reply
may well come back in parts. That is normal. Handle it the way Phase 4's page
describes, under **Two ways a reply goes wrong**.

**Paste this into the chat.**
````text
[PASTE THE CONTRACT CARD FIRST]

Build ripple/catalog.py, ripple/scanner/lineage.py and tests/test_lineage.py.

--- ripple/catalog.py

Rather than being handed a data dictionary, Ripple reads every CREATE it can
find and builds one. build_catalog(parsed) -> Catalog with tables
{TABLE: [columns]}, defined_in {TABLE: file}, and gaps[].
CREATE TABLE x (col type, ...) gives the columns directly. CREATE TABLE x AS
SELECT gives them from the projection. A table created without a readable
column list goes in gaps with a plain reason.

A STAR IS FILLED IN FROM THE TABLE IT COPIES. CREATE TABLE x AS SELECT * FROM
y publishes every column y has. When y's columns are written down — a CREATE
TABLE with the list, a query that names them, or a star filled in the same
way one step earlier — x's list is known too: y's columns, minus any named in
EXCEPT (REPLACE keeps the names), plus any other projected columns, in order.
`a.*` takes only the table the alias stands for; a bare `*` over a JOIN takes
every table the SELECT reads directly, and needs ALL their lists. Pass over
the star statements more than once, so a chain of stars fills in from its
root. Record each one in derived {TABLE: {table, from[], columns, file,
listedIn[]}} — listedIn being the files that write the copied lists down,
which is where a person can READ the list, not the file with the star in it —
and give Catalog a listed_in(table) that answers that for any table.
Measured on a real file: `select distinct a.*` from a stage table built with a
full projection two files earlier was reported as a table with no column list
to read, and read as Ripple failing to read a file. A star whose source has
no written list anywhere goes in gaps, with from[] and a reason that names
the source and says its own list is not written down — so this table's is
not either, and a scan still follows the column through it.

--- ripple/scanner/lineage.py

trace(index, parsed, upstream, change_type, cfg, on_progress) -> ScanResult
where upstream is [{"table": "...", "attrs": ["...", ...]}].

Walk each attribute out from its table: find every statement that READS the
current table, ask usages_of for the current column, record a Finding, then
recurse into the statement's target under EVERY name the column leaves as,
up to cfg.max_hops, with a seen-set so a cycle cannot loop.

WHOLE TABLES. Sometimes the notice is not about a column: the table itself is
being dropped, renamed, moved or rebuilt. An upstream entry then carries
whole: true and an empty attrs, and the question is "what reads it". Walk the
TABLE, not a column: every statement that reads the current table is a
Finding (kind "table", attr WHOLE_TABLE = "whole table", alias "", mode
"Whole table"), whatever columns it names — a SELECT COUNT(*) names none and
is still a reader — and then recurse into the statement's target as a table,
up to cfg.max_hops, with the same seen-set and the same cut-short reporting.
The row says HOW the statement takes the table: "Reads this table", "Joined
to this table" when it sits on the JOIN side, "Copied whole by COPY" for a
whole-table copy, "Exported from this table" for an EXPORT DATA. breaking is
true for removal, rename and unknown (the statement stops running without the
table) and false for a value or type change (it runs; what it makes changes).
The impact sentence says which, names the table the statement builds, and on
a hop past the first adds "X is itself built from the table that is changing,
so this is the same change one step further down". An export names the
delivery and says whoever reads the file is outside the repository. Group
under the published tables exactly as the column walk does; feeds[],
stopsLoading, mergedNames, wildcardNames, twoDefinitions, namedByFile and
builtAsText are recorded the same way. The attributes[] entry carries whole:
true, readers (statements that read the table itself) and builtHere;
lookupFailed is true only when nothing reads the table AND nothing builds it
— "nothing reads it" over a table something builds is an answer, "Ripple
never met it" is the question not having been asked. stats.wholeTables counts
these entries. Measured before this existed: a table with no attribute went
through the column walk with nothing to walk and came back "No usage found"
with a blank where the name should have been, in a letter ready to send.

THE HOP LIMIT IS A SETTING. A TRAIL IT CUT IS NOT A TRAIL THAT ENDED.

max_hops is a number on the settings screen. When the walk stops because of it,
nothing at all has been learned about the warehouse — so unless you carry that
fact out with the answer, the screen reads "the chain ends at t4, it does not
reach production", which is a setting reported as a fact about somebody's
pipeline, on the screen where they decide whether to worry.

So the walk returns two things, not one: whether it recorded anything, and
whether the limit is what stopped it. Every caller passes the second one up.

Record each stop on the result, and carry the limit that actually applied:

    cutShort[]   {table, attr, hop, roots[]}  one entry per table-and-column
                                              the limit stopped at
    maxHops      the number of renames this scan followed

Then keep the two apart everywhere they meet:

  * endsAt on an attribute holds ONLY the branches that genuinely ran out of
    code. A branch the limit cut goes in cutShortAt instead, never in endsAt.
  * the last box on a cut branch carries cut: true, so the picture says
    "Ripple stopped here — hop limit, not the end of the chain".
  * a table in reached[] that the limit stopped at carries cut: true and its
    own note — "Ripple stopped following here, the hop limit was reached, so
    this is not where the chain ends" — rather than "last table in the chain".
  * stats gains trailsCutShort, and coverage counts it as a gap.

And make it followable, because a trail that was cut is a trail somebody can
ask for again. POST /api/scan takes an optional maxHops; when it is present and
differs from the setting, copy the settings for that one scan, clamp the number
between 1 and 25, and use the copy. The setting on the settings screen is left
exactly where it was, so running one scan deeper does not quietly change every
later scan. The screen offers "follow these N renames deep instead", which runs
the same scan over code already read — no file is opened a second time.


A TABLE THAT STOPS BEING REFRESHED IS A SECOND KIND OF IMPACT, AND MUST BE
REPORTED SEPARATELY.

A column used only in a WHERE, a JOIN or a GROUP BY never reaches the table the
statement builds. The trail for that COLUMN genuinely ends there, and saying so
is right. But the STATEMENT stops working on the day the column goes, so the
table it builds stops being rebuilt — and every published table under that one
goes on serving whatever it held yesterday. Nothing errors on the screen of
whoever reads it. The numbers are simply out of date, and stay out of date.

So: collect the tables built by any statement with a BREAKING finding on it,
follow those tables DOWNSTREAM at the level of tables rather than columns (which
column carries onwards stops mattering once the job has stopped), and report the
published ones they reach.

Three rules about how it is shown, and they matter more than the walk:

* It is a DIFFERENT question from "what breaks", so it gets its own heading, its
  own words and its own count. Folding it into the production-table number makes
  one number that means neither thing.
* Leave out any table already reported above. Saying it twice under two headings
  reads as two problems.
* Cap the walk (400 tables is plenty) and SAY SO when the cap is hit. A list cut
  short without a word reads as "there were only these".

What it puts on the result:

    stopsLoading[]      {prod, because, via[]} — the published table, the
                        table directly below the broken statement, and the
                        whole path from one to the other, so the reader can
                        see how far the staleness travels rather than being
                        told a name with no route to it
    stopsLoadingCapped  true when the 400-table cap stopped the walk
    stats.productionStopsLoading  the count, apart from productionTables

Walk onwards from the target the READER keyed, not the one shown on screen. A
temporary table is fenced to the file that built it and the fence is stripped
for display, so looking it up by the shown name matches every other file's
temporary table of the same name — and the unrelated published table reappears
here, worded as certainly as anywhere else. Carry the keyed name on the finding
for exactly this. Go no deeper than max_hops.

When the target is on the published list: record it as a production group AND
KEEP GOING. One published table feeding another is exactly how a change
spreads, and stopping at the first under-counts the number the whole tool is
judged on, while drawing a shorter chain than the real one.

When nothing further is built from a table, the chain ends there. Record it —
do not drop it. A chain ending at a table that does not happen to match the
published-table rule is still a table somebody has to look at, and dropping
those was how a real breaking impact got shown as a clean result.

A Finding carries: source table and column, target table, alias, the usage
kind and its label, mode, a plain-English impact sentence, breaking,
no_local_fix, file, lang, snippet lines, hop, certain, the line its own
statement starts on, and `roots` — the attributes the person actually asked
about.

The line the statement starts on is part of what makes two findings the same
finding, and it has to be. One file very often builds several tables and
filters on the same source column in each of them. Keyed on file, table,
column and kind alone, the second and third statements were folded into the
first: the row shown under a published table pointed at another statement's
lines, named another statement's target, and the count of usages was quietly
short. Two renames down, the column on a
row is no longer called what they typed, and without roots the row cannot be
traced back to the question. roots must NOT be part of what makes two
findings equal: one usage can be on the path of more than one attribute.

Which changes break which usages. Every kind you record has to appear here, or
it is silently harmless:
  removal, rename : filter, join_key, ranking, dedup_key, transform,
                    aggregation, sort, excluded, pivoted, layout, select,
                    renamed, retyped
  value_change    : filter, join_key, transform
  type_change     : filter, join_key, transform, pivoted, layout, retyped
  unknown         : filter, join_key, ranking, dedup_key, transform, sort,
                    pivoted, layout, renamed, retyped

Two kinds are in none of them, and both on purpose:
  star     a SELECT * does not fail when a column disappears. It quietly builds
           a narrower table, and what breaks is whatever reads the missing
           column further down. Call the star hop breaking and you put a red
           badge on the one row in the chain that carries on working.
  dropped  an ALTER TABLE ... DROP COLUMN of the very column being
           decommissioned is not broken BY the change, it IS the change — and
           it is worth reporting for exactly that reason.

This table decides more than a badge. The "stops being refreshed" walk starts
from the tables built by any statement carrying a breaking finding, so a kind
left out of this list takes that whole second answer down with it. Leave layout
out and a table partitioned by the column being decommissioned reports risk
low with nothing under that heading, while in the warehouse the CREATE stops
compiling, the table stops being built, and every published table below it goes
on serving yesterday's numbers with no error anywhere.

No local fix: ranking and dedup_key, when the change is a removal or a
rename. The replacement has to come from the upstream team, so the row says
so rather than suggesting something that cannot be done here.

The impact sentence is the thing a person reads and acts on, so write real
sentences, not labels. For example: a join on the raw value — "Unless both
sides change on the same day, matching rows are dropped silently — no error,
just fewer rows." A ranking — "This column is the sort order inside a ranking
that picks one row per key. Without it the choice becomes arbitrary; the
wrong record can win, and nothing is raised to tell you."

Risk: high if any finding has no local fix, medium if any breaks, low if
there are findings.

WITH NO FINDINGS THERE ARE STILL THREE DIFFERENT ANSWERS, AND "none" IS ONLY ONE
OF THEM.

  unknown  something on the subject of this scan went unread — see the gap list
           below — or a whole file type in this repository was never opened.
  low      no lineage anywhere, but something in the repository NAMES this very
           column and stops working without it: a row access policy filtering on
           it, a search index built over it. It carries the column nowhere, so it
           produces no finding, and "No impact" printed over it is the one
           sentence this tool may not print. See referencedHere.
  none     nothing found, nothing unread, and nothing naming the column.

  TWO DIFFERENT QUESTIONS, AND THEY ARE MEANT TO DIFFER. coverage.complete
  asks "did I see everything in this repository", and the risk badge asks "did
  I see everything ABOUT THIS COLUMN". So risk "none" beside coverage
  complete:false is legitimate — a repository always has some file the reader
  cannot make sense of, and a badge reading "not sure" on every scan ever run
  is one nobody reads. That is why the gap test above is narrow.

  WHAT IS NOT LEGITIMATE, and it is the failure to write a test for: risk
  "none" when a gap ON THE SUBJECT exists — a file that could not be read AND
  mentions one of the names, a file never opened at all, a file held online or
  path-too-long, or a whole file type never opened. Measured on a build made
  from this kit: a scan for a column not in the repository came back risk
  "none" where the same folder and the same question gave the shipped answer
  "unknown", because the build had found ONE unreadable file where there were
  three. It had not detected the gap, so the gate never fired. The badge was
  not lying about the rule; the rule was being asked about a repository the
  build had only half read.

  So the test that catches it is not "none never appears beside an incomplete
  coverage block" — that would fail on an honest answer. It is: count the files
  this scan could not read, and if any of them mentions one of the names being
  followed, risk may not be "none". Assert that against a fixture that holds
  such a file, so the test goes red if the detection ever weakens.

  And on screen, never put a tick or the words "everything was read" beside a
  coverage block that is not complete, whatever the badge says.

With no findings at all the answer is "none" — EXCEPT where there is a gap
Ripple knows about, and then it is "unknown", worded on screen as "Not sure —
needs a person". "No impact" is the only thing this tool sells, so it is the
one word that must never be printed over something Ripple could not look at.
"I found nothing" and "I could not look" are not the same answer, however
similar they look on screen. A gap means any of:
  a file that could not be read AND that mentions one of the names being
    followed — restricted that way because every real pipeline has some file
    the reader cannot make sense of, and a badge that says "not sure" on every
    scan ever run is one nobody reads;
  a file that could not be read and was never OPENED either, so nothing can say
    whether it mentions the name — which is exactly the problem with it;
  any file held online-only, or whose path was too long to open.
Get this wrong and an EXECUTE IMMEDIATE holding a whole CREATE ... SELECT of
the scanned column printed a green "No impact" with couldNotRead 1 sitting
underneath it, and a file whose first statement was eaten by a byte-order mark
did the same. So did a whole repository read with the wrong SQL dialect, where
three files failed and nothing at all was learned.

Also carry the target table AS THE READER KEYED IT on each finding, beside the
one shown on screen. They are not always the same name — a temporary table is
fenced to the file that built it and the fence is stripped for display — and
anything that walks onwards from a finding has to use the keyed one or it looks
the table up by a name that matches every other file's temporary table.

Order groups WORST FIRST — most impacts, then by name. On a real repository
this list is hundreds of tables long, and alphabetical order means the first
thing somebody reads is decided by the alphabet rather than by how much of it
is broken.

A QUERY RIPPLE HAS NEVER READ IS NOT A QUERY WITH NO IMPACT. Phase 2 fills
parsed.runs_sql_from[] with every program that runs a .sql file which is not in
this repository. THIS PHASE MUST CARRY THAT ONTO THE ANSWER, because it is the
quietest hole of the lot: the program is perfectly readable, so nothing about it
looks unreadable, and the query it runs was never seen by anybody. Put each one
on the check-by-hand list with the file, the line and the name of the file it
wanted, worded as "runs the SQL in <path>, which is not in this repository".
Count it as a gap, so coverage stops reading complete and risk cannot read
"none". Measured: a build that filed these under "mentions only" -- the
reassuring case -- reported one file it could not read where the same repository
really held three.

THE HONEST HALF. After the walk, for every file the word search matched:
  If the name is inside an opaque statement, or appears as a QUOTED STRING
  inside any statement, report it under "check by hand" with the file, the
  line and the line itself. Real pipeline code reads
    substr(decrypt_sde(get_sde_tag('cm13','triumph_demographics'), cm13),1,11)
  and both cm13s break when cm13 is renamed. Ripple reports the second,
  because it is a column. The first is a quoted string and no parser can see
  it as anything but text. Report it EVEN IN A FILE THAT ALREADY HAS
  FINDINGS, and say so explicitly — fixing the findings does not fix that
  one, the text still says the old name.
  Count how many LINES of the file name it as text, not merely whether any
  does. A real file sets one tag per column and runs to sixty of them, and a
  report naming one line sends somebody to fix one line out of sixty.
  Otherwise, if the file could not be parsed, say "mentions the name, but
  Ripple could not read it as SQL — check by hand".

  THE ORDER OF THOSE THREE TESTS IS THE WHOLE RULE, and it is easy to write
  them the other way round without noticing. mentionsOnly is the REASSURING
  case — "the name appears but carries nowhere" — so anything that lands there
  by mistake is a warning turned into a comfort. Test for the quoted string
  FIRST, then for the file that would not parse, and only then fall through to
  mentionsOnly. Measured on a build made from this kit: a Python file naming
  the column on four lines as text was filed under mentionsOnly, the answer
  reported one file it could not read where the repository held three, and the
  risk badge printed "none" — over a coverage block on the same screen that
  said it was not complete.
  Otherwise it goes in mentionsOnly: the name appears but carries nowhere,
  which is the reassuring case and must be told apart from the others.

ONE MORE PASS, AND IT IS THE QUIETEST HOLE LEFT. Keep a set of every table the
chain actually STOOD ON as you walk. Then look through the statements Ripple
could not understand for one that names any of them, and add it to the
"check by hand" list with the file, the line, the statement, and a hint saying
the chain may carry on inside it.

The file parses. The readable statements in it produce findings. The one
statement that carries the chain onwards — a procedure call, SQL built as text,
a shape the parser gave up on — is simply absent, and nothing on the result
says a word about it.

Deliberately narrow. Every real pipeline is full of DECLAREs and CALLs that
carry no lineage at all, and reporting those buries the list this is trying to
protect. Only a statement naming a table on THIS trail counts, one entry per
file, and never a file already on the list.

AND ORDER THE LIST, worst first. It is the one place Ripple admits what it
missed, and it is only useful for as long as somebody reads to the bottom of
it. Score each entry: four if the file mentions one of the names being scanned
(that is a hole in THIS answer rather than in the reader), two more if it is a
SQL file by extension, one more if SQL words are written in it anywhere — or if
it was never opened, because then nothing can say what is in it. Alphabetical
order instead puts twelve config files above the one genuinely broken query,
because that query's filename happened to start with a z.

  SORT THAT LIST WORST FIRST, and sort it last, after everything has been added
  to it. It is the one place Ripple admits what it missed, and it is worth
  something only for as long as somebody reads to the bottom of it. Left
  alphabetical, what they read first is decided by the first letter of a
  filename: twelve config files above the one genuinely broken query, because
  that query's file happened to start with a z.
  Score each entry, then sort by the score highest first and by filename after
  that:
      +4  the word search matched this file — that is a hole in THIS answer
          rather than in the reader, and on its own it settles the order
      +2  it is a query file by name: .sql, .sqlx, .ddl or .hql
      +1  SQL words are written in it anywhere — SELECT, INSERT INTO,
          CREATE TABLE, CREATE OR REPLACE, MERGE INTO, UPDATE, EXECUTE
          IMMEDIATE — or the file was never opened at all, so nothing can say
          what is in it, which is the whole problem with it

Per attribute, report: found, files, mentionedIn (how many files write the
name down at all — zero here is the answer to "why did it find nothing?"),
reachesProduction, endsAt, uncertain (findings where the table was inferred),
and how widely the name is used as a name (in how many of the tables Ripple
could read). A scan for a column half the warehouse shares looks identical on
screen to a scan for one only this table has, and they are not remotely the
same answer.

Also per attribute, five more:

  cutShortAt    the tables the hop limit stopped at. endsAt must never hold
                one of these — a branch Ripple gave up on has not ended.
  notVisible    the tables on this trail whose column list is written down
                nowhere.
  inferred      how many of this attribute's findings sit past one of those.
  tablesRead    how many tables Ripple could read at all, so nameInTables has
                a denominator beside it rather than a bare number.
  lookupFailed  for this ONE attribute: true when it produced no findings AND
                the name never turned up as a column on any table in the
                repository. That is what tells "I never saw that column" apart
                from "that column goes nowhere".

FOUR MORE LISTS ON THE RESULT, each a caveat that must sit BESIDE the answer
it qualifies and never on another screen:

  namedByFile[]      {table, file, how} — tables whose name is nowhere in the
                     file that builds them, because the tool names them after
                     the file. "how" is "dbt", "Dataform" or "file". Without
                     this, somebody who opens the file to check the finding
                     will not find the table name written on it, and a finding
                     they cannot verify is one they dismiss.
  twoDefinitions[]   {table, files[]} — tables more than one file builds FROM
                     SCRATCH. Only one of those can be the definition that
                     runs, and nothing in the code says which.
  skippedInFolders[] the code files Ripple walked past because of the folder
                     they sit in, with skippedFolderNames[]. This count used to
                     reach the repository screen and nothing else, so a scan of
                     a dbt project — whose target/ folder holds the SQL that
                     actually runs — came back "risk none, prod []" with the
                     reason on a screen nobody was looking at.
  starTables[]       gains a "filledIn" field. A table whose column list is not
                     visible is not always a SELECT *: it can be a placeholder
                     the job fills in when it runs. No screen may tell somebody
                     the file says SELECT * when it does not.

                     Full shape: {table, file, from, attr, roots[], how,
                     filledIn, known, columns, listedIn, listedWithout[]}.
                     Built WHILE THE WALK IS HAPPENING, not read
                     off the repository screen afterwards, so it travels with
                     the answer it qualifies. "how" is the word the file used
                     to copy a whole table — COPY, CLONE, LIKE or RENAME — and
                     is empty when the file really does say SELECT *.
                     "filledIn" is set when the column list is a placeholder
                     the job fills in at run time.

                     "known" is true when the built table's column list IS
                     written down after all — the catalogue filled it in from
                     the table the star copies (catalog.derived), or the built
                     table has a CREATE TABLE of its own — AND the column
                     being followed is on that list. Then the hop is READ:
                     the finding carries starKnown instead of adding to
                     inferredHops, the box on the map carries starKnown
                     rather than inferred, and the entry says how many
                     columns and which file lists them ("listedIn", from
                     Catalog.listed_in). tablesNotVisible, the coverage gap
                     and notVisible count only the entries whose known is
                     false. When the list is written down WITHOUT the column
                     being followed, the star is still followed — excluding
                     on a list that may be stale is the catastrophic
                     direction — and the column's name goes in
                     listedWithout[], said on screen, so a gap nobody could
                     see becomes a sentence somebody can check.

                     THE STAR HOP ITSELF IS NEVER BREAKING. Mark it breaking
                     and you put a red badge on the one row in the chain that
                     carries on working. Mark what it costs instead: that row
                     carries viaStar, the box on the map carries inferred:
                     true with the same "how", and every row from there
                     onwards carries inferredHops — how many star hops are
                     behind it — so the screen can say which findings were
                     worked out rather than read.

SIX MORE THINGS ON THE RESULT. Every one exists because two DIFFERENT facts
were printing as the same sentence, which costs exactly as much as a missed hop.

  feeds[]            {uri, file, line, from, attrs[], breaking} — deliveries out
                     of the warehouse. Counted as feedsBroken and kept OUT of
                     productionTables: a file in a bucket is not a published
                     table, and one number covering both means neither.

                     The IMPACT SENTENCE on those rows changes too. An EXPORT
                     DATA writes a file to a bucket; there is no published
                     table to gain or lose a column, which is exactly why the
                     ordinary wording is no use here. Unless the usage is a
                     filter or a join key — where the statement simply fails,
                     and the ordinary words are right — say instead: this
                     column is written into the file delivered to <uri>, no
                     table in this warehouse gains or loses anything, the
                     delivery does, and whoever reads it is outside this
                     repository. Tell them before the change ships.

  referencedHere[]   Index, policy and UNDROP DDL naming a table the chain stood
                     on or a column being followed, with the columns it names.
                     Narrow on purpose — every warehouse is full of indexes on
                     tables this scan never heard of, and listing those buries
                     the ones that matter.

                     Each entry: {kind, table, file, line, snippet, verb,
                     columns[], namesColumns[]}. "kind" is the plain words the
                     screen prints — "row access policy", "search index",
                     "vector index", "UNDROP". "namesColumns" is the subset of
                     the columns being FOLLOWED that this statement names, and
                     it is what the risk badge reads: a policy naming the
                     column stops working the day the column goes, so risk is
                     "low" there and never "none".

                     Work this list out BEFORE the honesty lists below it. A
                     file already accounted for here belongs on this card and
                     on no other — not also as a file nobody could read, not
                     also as a file that mentions the name and carries it
                     nowhere. It is one statement, and counted twice it reads
                     as two separate problems on the one list that has to stay
                     short enough to read to the bottom of.

                     None of this is lineage. Reading one of these loosely may
                     add a row to a list; it must never move a chain.

  builtAsText[]      Statements the file runs as text — EXECUTE IMMEDIATE. The
                     hop is real; the line is a quoted string.

  lookupFailed       True when EVERY attribute asked about is a name Ripple
                     never met as a column on ANY table, and nothing was found.
                     "I never saw that column" and "that column goes nowhere"
                     were byte-for-byte the same answer — found 0, no findings,
                     a green tick — and they are OPPOSITE answers: the first is
                     the question never having been asked, so a typo in an
                     attribute name shipped as "no impact". Per attribute also
                     carry tableColumns: the columns Ripple DID see on that
                     table, taken from the statements that build it AND from the
                     statements that read only it (nothing in a repository ever
                     builds a source table, so its columns are only written down
                     by the queries that read it). That turns a silent wrong
                     answer into a spelling mistake somebody spots in two
                     seconds. Work it out ONLY when a lookup actually fails, and
                     only once per table: it walks every statement.

A CAVEAT MAY NEVER LIVE ON A DIFFERENT SCREEN FROM THE ANSWER — INCLUDING THE
FILE TYPES YOU DID NOT OPEN. The repository screen lists these. The ANSWER must
list them too: leave it off and a chain whose middle hop sits in a .ipynb prints
"the name appears, but no lineage to a production table" with nothing beside it
saying a file was passed over. Carry the tally onto the scan payload, count it as a
gap so coverage stops reading complete, put it on its own card, and say it in
the letter. With nothing found and a whole file type unread, risk is "unknown",
never "none" — "I found nothing" and "I could not look" are not the same answer.
  The trap: every repository has a README, and a warning printed over every scan
  is one nobody reads — it would take "no impact" down with it. So keep a list
  of the types that are KNOWN not to be code (prose, images, packed data,
  archives, binaries, media, locks) and count everything else. Written that way
  round on purpose: a file type nobody thought of is a gap by default, which is
  how the middle hop goes missing. The repository screen still lists EVERY
  skipped extension, this one included, so nothing is hidden from anybody.


  coverage           How much of this trail Ripple could see, as COUNTS of what
                     it has already worked out and must not throw away: unreadable
                     files, files never opened, tables built with SELECT *,
                     trails cut short at the hop limit, findings sitting past
                     one of those, merged names, findings on a line that did not
                     say which table, code files walked past because of the
                     folder they sit in, and FILES OF A TYPE RIPPLE DOES NOT
                     OPEN AT ALL. "No impact, and I could follow every
                     step of it" and "no impact, and three tables on the way
                     were invisible to me" printed as the same three words.
                     NOT a percentage: there is no honest denominator for "how
                     much of a trail exists", and a made-up one puts a precise
                     number on a guess.

                     A NINTH COUNT, and it is the one most easily left out:
                     the files whose TYPE Ripple never opens — a notebook, a
                     Terraform file, a file with no extension at all. The
                     repository screen has always listed those. The answer must
                     too, because a middle hop written in a notebook otherwise
                     produces "the name appears, but no lineage to a production
                     table" with nothing anywhere beside it saying a file had
                     been passed over. Count every one of them as a gap, so
                     coverage stops reading complete.

                     coverage returns:
                       complete      true only when no gap has a count
                       gaps[]        {count, what} — one entry per gap that
                                     actually has a count, in plain words
                       filesMatched  files that mention one of these names
                       filesUnread   files that mention them and could not be
                                     read
                     Those last two are the one honest ratio on the screen,
                     because both halves are files Ripple actually listed.

  wildcardNames[]    Only the wildcards that actually PRODUCED a finding. The
                     card says "the usages below are real", and it was being
                     printed over an empty list: a wildcard in one dataset
                     covering a shard in another matches by short name and is
                     then ruled out by same_table, so it produced nothing.
                     Each entry also carries shorthand[]: the patterns that
                     matched only because the family name was typed without the
                     separator BigQuery requires. So wildcard_match returns
                     "shard", "family", "both" or "" rather than a yes/no — a
                     shard match is a fact about the SQL and stays certain; a
                     family match is a guess about what somebody meant and sets
                     certain=False on every usage from it. Matching it at all is
                     right, because typing the name you say out loud must not
                     produce a clean "no impact"; shipping it as certain was not.

  mergedNames[]      {table, reason, spellings[], datasets[]} — names this
                     repository uses for more than one table, where the SQL
                     being followed did not say which one it meant. Ripple
                     follows both, because losing a chain is far worse than
                     showing a row somebody can dismiss by opening the file —
                     and then says so, or the finding reads as a fact about
                     one table when it may be about the other.

                     Two reasons, and the card says which. "dataset": one file
                     writes archive_dataset.cust_stage and another writes a
                     bare cust_stage, and a bare name has said nothing to rule
                     anything out. "capitals": BigQuery treats
                     ccm_Wireless_Enroll and ccm_wireless_enroll as two
                     different tables, and Ripple matches them as one.

                     Report it because it HAPPENED, not because it might.
                     Two tables of the same name in two NAMED datasets are
                     kept apart, and nothing is said about them. And for the
                     very first table — the one a person typed rather than one
                     read out of the code — say nothing unless the repository
                     really does have that name in more than one dataset.
                     Somebody typing a table name without its dataset is not
                     an ambiguity in the warehouse, and flagging it would put
                     a warning on every scan ever run.

THE INFORMATION_SCHEMA HINT. A statement that looks a table up in BigQuery's own
catalogue by name — WHERE table_name = 'customer_demographics' — was reported
with the hint "which is how in-house helpers take a column or table name". That
is correct code doing exactly what it should, and the one line on screen pointing
at the problem named a cause nobody could find. Ask the parse TREE whether the
statement reads a metadata view, not the Statement's sources: a metadata view is
deliberately never recorded as a source.

"I NEVER SAW THAT COLUMN" IS A CONFIDENT CLAIM

lookupFailed says Ripple read everywhere it could and this name is not a column
anywhere. It may only be set when that is true. Measured, all three printing a
green "check your spelling" over a real gap:

* a file naming the column that could not be read;
* the whole chain sitting in a build/ folder Ripple is told to skip;
* a row access policy naming that very column, on the same screen.

So set it only when every attribute failed AND coverage is complete AND nothing
on the subject went unread AND no index or policy names the column.

Coverage counts the skipped folders too -- a folder Ripple was told to skip is
exactly as unread as a file it could not open. And risk reads "unknown" rather
than "none" when NOTHING was found and code files were skipped by folder. Only
when nothing was found: skipping build, dist and target is ordinary, and a badge
reading "not sure" on every scan of every dbt project is one nobody reads.

Also produce graphs[] for the dependency picture: per attribute, the branches
that reach a published table and the branches that end elsewhere, each a list
of {name, kind, alias, prod}. Drop any branch that is only the start of a
longer one already listed.

Tests: a chain through two renames reaches the published table; a column
leaving under two names does not lose the chain; findings are reported even
when NOTHING matches the published rule, and the risk is not "none";
correcting the rule turns them into production tables; a genuinely clean
result is still clean; a name inside a quoted string is reported even in a
file that has findings, with a count of lines; groups come back worst first;
a repository with nothing found but a file it could not read comes back
"unknown", and a clean one still comes back "none".
````

**Check it worked.** From `C:\ripple-build`:

**Type this into the black window.**
```
python -m pytest tests/test_lineage.py -q
```

You want `passed`. The one test to insist on: *findings are reported even when
nothing matches the published-table rule, and the risk is not "none"*. If the chat
quietly returns an empty result there, it has rebuilt the exact bug this tool
exists to prevent, and no amount of green elsewhere makes up for it.

---

# PHASE 6 — reading the notification email

**Saves to:** `ripple-build/ripple/notification.py`,
`ripple-build/tests/test_notification.py`

**Open a fresh chat window for this phase.** Paste the contract card into it
first, then the block below. About 1,750 lines, so the reply may come back in
parts — handle that the way Phase 4's page describes, under **Two ways a reply
goes wrong**.

**Paste this into the chat.**
````text
[PASTE THE CONTRACT CARD FIRST]

Build ripple/notification.py and tests/test_notification.py.

read_upload(filename, raw_bytes) -> Notification
read_pasted(text) -> Notification
extract_by_rules(notification, catalog) -> dict

A Notification holds subject, body, from_name, from_email, attachments[],
source_kind. Read three shapes:
  .eml   with the standard library email package, walking multipart, taking
         text/plain in preference to text/html, decoding whatever charset is
         declared and falling back rather than raising
  .msg   Outlook's compound file format. Use extract_msg, the package Phase 0
         installed. Open the bytes with extract_msg.Message wrapped around an
         io.BytesIO, and take the subject, the sender and the body from it. The
         sender's name is the part before the "<"; pull the address out of the
         same line with the address pattern. When the plain body is empty, fall
         back to the HTML body and strip the tags - decode it first if it
         arrives as bytes. Keep the attachment names: the long filename, or the
         short one, or the word "attachment".
         WHERE IT CANNOT: if the import fails, if opening the file raises, or if
         the file opens and holds no readable text, come back with a warning
         that names what happened and what to do instead - never a silently
         empty email. An empty email extracts nothing, and the screen then shows
         a confident blank form as though the email said nothing at all.

extract_by_rules matches the text against the repository catalogue built in
Phase 5, so what comes out is names that actually exist in the code rather
than a guess. Return: source, changeType, changeKind (one of unknown,
removal, value_change, type_change, rename), changeDesc, subject,
effectiveDate (ISO), pocName, pocEmail, pocTeam, upstream[{table, attrs,
whole}], warnings[], extractedBy: "rules".

whole is true when the notice says the TABLE itself is changing and names no
attribute on it. names_the_whole_table(text, table) looks, around the table's
own name, for "<table> will be / is being dropped, removed, decommissioned,
retired, renamed, migrated, moved, deprecated, deleted, replaced, sunset,
rebuilt, discontinued, archived", for "dropping / removing / ... <table>",
for "decommission / removal / retirement / deletion / migration / deprecation
/ rename of <table>", and anywhere in the text for "whole table", "entire
table", "the table itself", "all columns", "all attributes", "every column".
A NAMED ATTRIBUTE ALWAYS WINS: a table with attributes found on it is a
column change however the sentence is worded. Then a warning per table, in
the words the screen shows: a whole-table one says it reads as a whole-table
change — every column, and every statement that reads the table — and to
untick "Whole table" on the next screen if only some attributes change; a
table with no attribute and no such words says to tick "Whole table" if the
table itself is changing, otherwise add the attribute, or nothing can be
scanned for it. The change labels no longer say "attribute" in front:
classify_change gives ("removal", "Decommission"), ("rename", "Rename"),
("value_change", "Value format change"), ("type_change", "Data type change")
and ("unknown", "Not specified") — "Attribute decommission" printed over a
table being dropped described a change that was not the one happening.

Rules worth having: a table name in the text that IS in the catalogue is an
upstream table; a column name that belongs to one of those tables is one of
its attributes; MATCH NAMES IN ANY CASE, and do not require an underscore.
Matching only SHOUTED_NAMES looks reasonable and is a quiet disaster: BigQuery
names are written in lower case, real repositories have tables like
ccm_Wireless_Enroll in mixed case, and plenty of columns - cm13, pub_guid -
are one word. An email reading "we are removing cm13 from
customer_demographics ... ACCOUNT_MASTER is unaffected" produced exactly one
table to scan: ACCOUNT_MASTER, the only one the email says is fine, with no
warning of any kind. Being wide costs nothing, because a word only becomes a
table or a column once the catalogue confirms it is one - and a spare name on
the confirm screen is a tick somebody can clear, while a missing one is
invisible. Keep the narrow SHOUTED_NAME rule for one job only: listing the
names an email mentions that the repository has never heard of, which would
otherwise become every ordinary word in the message; a date in any common written form becomes ISO; words like
"decommission", "retire", "format change", "rename" pick the change kind.

BE HONEST. Any table named in the notification that is NOT in the connected
repository must come back as a warning: "Not found in the connected
repository: X. Scanning will still run, but expect no results for those."
Nothing is scanned until the person has confirmed the fields, so what is
extracted is a suggestion, never an answer.

extract_by_rules hands back three kinds of warning, and all three have to be in
the list:

  whatever the reader itself put there. Start the list as a copy of the
  notification's own warnings. That is the only way "Could not open the Outlook
  file" or "The email had no readable text body" reaches the screen at all.

  names the email SHOUTED that the repository has never heard of:
    "These names were mentioned but are not in the connected repository:
     A, B, C"
  The first eight only, and only names in capitals with an underscore. Every
  ordinary word in the message is already checked against the catalogue, and
  listing all of those back would bury the one line that matters.

  no table matched at all:
    "No table from the connected repository was recognised. Add the table and
     attributes by hand before scanning."

A saved .eml or .msg hands you real headers. A plain .txt upload does not, and
neither does a forwarded email, which hides the original sender inside its own
body. So read the same facts out of the words themselves, on every path in, and
the same email must give the same fields whichever way it arrives.

  split_pasted_headers(body) -> ({header: value}, the body without them)
      Lift an Outlook header block out of the text. A block only counts when it
      is anchored on a From: line, so a sentence beginning "To: be clear" is
      left alone. The block reaches as far as header-shaped lines go in both
      directions - somebody who opens a saved .eml in Notepad and pastes the lot
      brings Content-Type and MIME-Version with them, and left in the body one
      of those becomes Ripple's description of the change. Take out every block
      found, a twice-forwarded email has several, but report the values of the
      FIRST. Take the row of dashes or underscores Outlook draws above a
      forwarded block out with it, or it is left floating.
      Also read the one-line attribution phones and Gmail write instead of a
      block: "On Mon, 3 Aug 2026 at 09:14, Priya Raman <priya@corp.example.com>
      wrote:". The name is the part after the LAST comma, so it may not hold a
      comma itself, or the whole date swallows it.
  parse_sender(value) -> (name, email)
      One From: value in any of its four shapes:
        "Priya Raman" <priya@corp.example.com>
        Priya Raman <priya@corp.example.com>
        Priya Raman [mailto:priya@corp.example.com]
        priya.raman@corp.example.com        -> name "Priya Raman"

Call this from read_pasted, from read_eml, from read_msg and again from
extract_by_rules, and never overwrite a name or an address the envelope already
carried.

One ordering decides whether the answer is right: the effective date is the date
in the MESSAGE, not the Sent: date. Both are written the same way, so whichever
is read first wins - which is why the header block comes out of the body before
the date is looked for.

Also provide an email-address extractor that pulls every address out of a
blob of text, once each, lower-cased. People do not type addresses one at a
time into a form; they paste an Outlook To line — "Priya Raman
<priya@corp.example.com>; Marcus Hale <marcus@corp.example.com>".

Three more readers, all of them working on the words rather than the envelope:

  signature(body) -> {name, team, email}
      The name, team and address a notice is signed off with. Read the last
      eight non-blank lines from the BOTTOM UP - reading down from the top, the
      first tidy-looking line of the message wins instead. Skip the closing
      itself ("Regards,", "Thanks,", "Best wishes"): the name comes after it.
      A person is two to four words, each capitalised, under 45 characters, with
      no digits and none of @ : _ / \ | or a tab in them. A tab means a table
      cell, not a person - an HTML table flattens to tabs.
      A team has to SAY what the team does. Accept it only when one of its words
      is data, governance, office, team, platform, engineering, operations, ops,
      group, dept, department, services, service, support, delivery, programme,
      program, function, domain or coe. Without that rule the second name in a
      sign-off becomes somebody's team. Handle both layouts: the team on the
      line directly under the name, and "Priya Raman, C360 Data Governance" on
      one line.
      Guess nothing. An unrecognised shape leaves the field blank for a person
      to fill in, which is recoverable; a wrong one is not.
  source_system(team, subject) -> str
      Which upstream system this came from, never who typed the email. Take the
      team and drop the trailing words that describe what a team does, so "C360
      Data Governance" gives "C360" and "Data Governance" gives nothing. With no
      team, take a bracketed tag off the front of the subject line - but only
      when it is a code, meaning all capitals or holding a digit, and never a
      priority flag: action required, notice, fyi, urgent, reminder, important,
      confidential, internal, update, alert. When neither yields anything the
      field is "Unknown".
  first_sentence(body) -> the changeDesc
      The first line over forty characters that is not a greeting, capped at 240
      characters. Skip header lines that are plumbing rather than words somebody
      wrote: Content-Type, Content-Transfer-Encoding, Content-Disposition,
      MIME-Version, Message-ID, Received, Return-Path, Delivered-To,
      Authentication-Results, DKIM-Signature, Thread-Topic, Thread-Index,
      Accept-Language and anything beginning X-. Keep that list narrow:
      "Impact: this breaks the nightly load" is a real first sentence, and a
      rule that skipped every line with a colon in it would throw it away.

Keep upstream[] in the order the names appear in the email, so the table the
email is actually about comes first.

The test that holds all of this together: take a sample .eml, upload it, then
paste its body as plain text. source, pocName, pocTeam, changeKind,
effectiveDate and the list of tables must come out identical both ways.

Tests with invented names and a fabricated .eml built in the test.
````

**Check it worked.** From `C:\ripple-build`:

**Type this into the black window.**
```
python -m pytest tests/test_notification.py -q
```

You want `passed`. You will feed it a real notification email in Phase 12, on the
screen, where you can see what it made of it.

---

# PHASE 7 — writing the summary and the reply

**Saves to:** `ripple-build/ripple/narrative.py`,
`ripple-build/tests/test_narrative.py`

**Open a fresh chat window for this phase.** Paste the contract card into it
first, then the block below. About 1,950 lines, so the reply may come back in
parts — handle that the way Phase 4's page describes, under **Two ways a reply
goes wrong**.

**Paste this into the chat.**
````text
[PASTE THE CONTRACT CARD FIRST]

Build ripple/narrative.py and tests/test_narrative.py.

summarise(scan, vals) -> {headline, narrative, bullets[], actions[],
                          writtenBy: "rules"}
draft_reply(scan, vals, summary) -> {subject, body, writtenBy: "rules"}

WHAT IS CHANGING, IN WORDS. Both functions name the subject the same way,
from vals.upstream: the attributes, joined — or "the whole of <table>" for an
entry with whole: true or no attributes at all. Measured before this: a table
with no attribute printed "No usage of  was found" in a letter ready to send.
A whole-table row has no alias, so its bullet reads "<table> - reads this
table" and its action "Change the statement that reads this table in <file>."
When every item asked about was a whole table and lookupFailed is true, the
headline is "<table> was not found - nothing has been checked", the narrative
says nothing here reads it and nothing here builds it, and the reply asks for
the exact table name rather than a column name.

This is what runs when there is no AI, when a key stops working, or when
somebody decides no data may leave the network. It must be worth reading on
its own.

THE HEADLINE IS QUOTED IN MEETINGS AND THE REPLY IS SENT TO ANOTHER TEAM, so
neither may claim more than was read. Work out first how much of the
repository the answer does NOT cover: files never opened plus files that could
not be followed.

Work out first how much of the repository this answer does NOT cover. FIVE
things count, and the number is the sum of all five:

  files never opened        stats.neverOpened
  files not followed        unreadable[]
  trails cut short          cutShort[] - trails Ripple stopped following at the
                            hop limit while they were still going
  files in a skipped        skippedInFolders[], with the folders themselves in
    folder                  skippedFolderNames[]
  file types Ripple         fileTypesUnopened[{ext, count}] - add up the counts
    does not open

Leave any of them out and a chain whose middle hop sits in a notebook, or in
build/, or four renames further down, is a chain nobody looked at - while the
headline reads "No impact" and the letter reads "Please proceed as planned"
over it. summarise() and draft_reply() must work the number out the SAME way,
because a screen and a letter that disagree about how much was read are worse
than either one alone.

Say WHICH kinds, not only the total, in the narrative, joined with "and":

  "3 files could not be opened at all"
  "2 files could not be followed"
  "7 code files sit in a folder Ripple is told to skip (build, target) and were
   never read"
  "1 file is of a type Ripple does not open (.ipynb)"
  "1 trail was stopped at 4 renames deep and was still going"

Name the folders and name the extensions. A caveat somebody cannot act on is a
caveat they skip.

  nothing scanned at all
     -> "Nothing was scanned — there was no code to search", and a reply that
        says no answer is possible yet. Never "no impact": that is a statement
        about an empty folder wearing the clothes of a statement about a
        pipeline.
  no findings, but some files uncovered
     -> "No usage found in the N files that could be read — M others could
        not be", and a reply that says the assessment is still being
        confirmed. NEVER "no impact, proceed as planned".
  no findings, everything read
     -> "No impact — nothing in this repository consumes the attribute", and
        the confident reply. This is the only case that earns it.
  findings, and a usage with no local fix
     -> "Ranking logic has no replacement — escalate before the date"
  findings that break, and some files uncovered
     -> "N production tables at risk, and M files Ripple could not follow".
        Never "all fixable in code": the fix that has no substitute may well
        be inside one of the files nobody could follow.
  findings that break, everything read
     -> "N production tables at risk, all fixable in code"
  findings, none breaking
     -> "Labels change, but nothing breaks"

The letter for a confirmed impact is assembled from what the summary already
worked out, not written a second time:

  "Impact confirmed. <attributes> is consumed by N pipeline objects feeding M
   production tables: <names, capped at ten with 'and N more'>."
  N is counted the same way the summary counts it — rows across the groups,
  listed ONCE. A finding upstream of two published tables appears under both, so
  counting them raw makes the letter say 9 one click after the summary said 8.
  Two numbers for one thing, and the wrong one is the one that leaves the
  building.
  then "What we will do before the effective date:" and the summary's first
    four actions, one per line, each indented with a dash
  then, if any usage has no local fix, one ask of the upstream team: at least
    one usage orders or deduplicates on the attribute and has no local
    substitute - can they confirm a replacement attribute, or retain this one,
    before the effective date
  then, if any file could not be followed, a line saying so and that the
    assessment may still grow
  then, if any file could not be opened at all on this machine, a line saying
    this assessment does not cover them

The last two are the difference between a letter another team can rely on and a
letter that quietly claims more than was read.

There is a further case: findings exist but NONE of them reach a table on the
published list. That is either a genuinely internal chain or a published-table
rule that does not match this repository, and only a person can tell which. So
say exactly that — "not a clean result, an unfinished one" — and the drafted
reply must say the assessment is in progress. It must never say "no impact"
while the analysis behind it is holding a list of usages.

In that branch, say what happened to each chain separately. A chain Ripple
stopped following has not ended, so never describe it with the word "end":

  chains that finished  ->  "Those chains end at A, B and C."
  chains cut short      ->  "Ripple stopped following D and E at 4 renames
                            deep - those trails were still going, so nothing
                            past that point has been looked at."

Take the names from cutShort[].table and the depth from maxHops on the scan
rather than writing a number into the sentence, so the caveat still tells the
truth when somebody raises the limit. Add a bullet and an action that send the
reader back: "N trails were cut short by the hop limit rather than by the
code. Run the scan again, deeper, before treating this as the whole answer."

Cap every list of table names at six or ten with "and N more". On a real
repository one key column reaches hundreds of tables, and joining them all
into a sentence produces a paragraph nobody reads, in the one place on the
screen written to be read.

Whenever starTables[] holds an entry whose known is false, end the narrative
with one more sentence, counting only those - in the no-findings branch and in
the nothing-published branch alike. A star whose list was filled in was read,
and a letter saying it "could not be read" says something false:

  "2 tables on the way are built with SELECT *, so the column list could not be
   read and the steps past them are worked out rather than read."

Without it, a step Ripple inferred and a step Ripple read off the code print as
the same sentence, and a guess gets acted on as a fact.

Bullets and actions come from the real findings, most consequential first,
and always include the caveats: files that could not be opened go FIRST and
worded hardest, because every other number on the page is a number about the
files that WERE opened.

Tests, and these are the ones that matter:
  the summary never says "no impact" over a list of findings
  no impact is never claimed over files that could not be read — check the
    headline AND the reply body, and that "proceed as planned" is absent
  nothing scanned is never reported as no impact
WHAT THE LETTER MUST NEVER SAY

"No impact. Please proceed as planned" is the most consequential sentence this
tool writes, and it was being written over every one of these. The summary and
the reply have to read the SAME facts the findings screen does:

  lookupFailed        Its own branch, before anything else. The question was not
                      answered, so the letter asks the upstream team to confirm
                      the column name. It does not report an impact either way.
  feeds[]             Name the destination. Without it the letter says the data
                      feeds "tables in our own pipeline" about an EXPORT DATA
                      going to a partner's bucket.
  stopsLoading[]      When a published table stops being refreshed, the headline
                      must say so -- and must NOT say "none of them reaching a
                      table on your published list", nor send the reader off to
                      fix a production rule that matched perfectly.
  referencedHere[]    A row access policy naming the column is not "no impact".
                      It carries the column nowhere and stops working all the
                      same, so it gets its own paragraph.
  skippedInFolders[]  Counted with the files that could not be opened. A folder
                      Ripple was told to skip is exactly as unread.

Keep only the referencedHere[] entries whose namesColumns is true. An index on
a table the chain happened to stand on is not a reason to warn anybody; a
statement that names the column being followed is.

When nothing carries the column anywhere and one of those is left:

  headline   "No lineage, but 1 statement names <attributes> directly"
  narrative  name each one as its kind and its table - "row access policy on
             customer_demographics" - and say that it stops working on the day
             the column changes
  actions    "Update the row access policy that names <attributes>."
  the letter its own paragraph, and never the confident reply

Print the kind Ripple recorded, not a word of your own. Somebody reading the
letter has to be able to go and find the thing.

In that branch the headline depends on what Ripple DID name, in this order:

  stopsLoading[] not empty  ->  "2 published tables stop being refreshed"
  feeds[] not empty         ->  "1 delivery out of the warehouse breaks"
  neither                   ->  "9 usages found - none of them reaching a table
                                on your published list"

Only in the third case may the narrative say the production naming rule might
be wrong and send the reader to the settings screen. Say it in either of the
first two and you are telling somebody to go and fix a rule that matched
perfectly, one line under a table it matched.

The letter carries the same two facts. When a published table stops being
refreshed, say so as a confirmed thing: no column of it changes, the job that
fills it stops running, so it quietly serves stale data. When a delivery leaves
the warehouse, name the destination - whoever reads that file is outside this
repository and no scan of it will ever find them.

Take the branches in this order, and no other:

  1. findings exist but none reach a published table
  2. filesScanned is zero
  3. lookupFailed
  4. no findings at all
  5. findings that reach published tables

lookupFailed comes AFTER "nothing was scanned". A scan that read no files also
meets every condition for a failed lookup, and "check the spelling" printed
over an empty folder sends somebody hunting for a typo that is not there.

When lookupFailed is true, write:

  headline   "<attributes> was not found - nothing has been checked"
  narrative  how many files were read, that the name was never met as a column
             on that table or on anything else in this repository, that this is
             not the same as the change being safe because the question has not
             been answered, and "Check the spelling before replying." Then
             print back the columns Ripple DID read on that table, from
             attributes[].tableColumns, capped at twelve with "and N more". If
             that list is empty, say instead that nothing in this repository
             writes down the columns of that table.
  bullets    no answer either way about the attribute; and what Ripple did read
             on the table.
  actions    "Check the spelling of <attributes> against the list above, then
             run the scan again." and "Do not reply to the upstream team on the
             strength of this scan."

Printing the column list back is the whole point of this branch: it turns a
confident wrong answer into a spelling mistake somebody spots in two seconds.

  a genuinely clean result still says no impact, in both
````

**Check it worked.** From `C:\ripple-build`:

**Type this into the black window.**
```
python -m pytest tests/test_narrative.py -q
```

You want `passed`. Then read the four drafted replies out loud. These are the
words that leave the building and get forwarded to another team, so if any of
them would embarrass you, say so in the same chat and have it rewritten.

You do not have to open a code file to read them. Paste this into the same
window:

**Paste this into the chat.**
````text
Show me the four drafted replies exactly as they will come out on screen -
subject line and body, as plain English, outside the code, one after the other.
No code and no explanation.
````

---

## Closing down for the night — end of evening two

Windows 5, 6 and 7 are done — about 6,300 lines. Ripple can now read a
repository, follow a column through it, read a notification email and write the
reply that goes back. What is left is the part you can see: the web service and
the screens.

**Do not start window 8 tonight.** Same reason as last night. Stop between
windows, never inside one.

**1. Check tonight's files are on disk.**

**Type this into the black window.**
```
dir /s /b C:\ripple-build
```

Seven new names since last night, twenty-two in all:

**Read this — there is nothing to type.**
```
ripple\catalog.py               ripple\scanner\lineage.py
ripple\notification.py          ripple\narrative.py
tests\test_lineage.py           tests\test_notification.py
tests\test_narrative.py
```

A missing one is almost always Notepad's `.txt` again. Rename it tonight.

**2. Run everything once.**

**Type this into the black window.**
```
python -m pytest -q
```

Seven test files now, and you want `passed`. If it is red, fix it tonight in the
window that wrote the file, while that window is still open.

**3. Add tonight's lines to your note.** The file already exists from last
night — put tonight's lines at the bottom, do not replace what is there:

**Type this into the black window.**
```
notepad C:\ripple-build\where-i-got-to.txt
```

Tonight's date and *"finished window 7, check passed"*, plus anything a window
invented a name for, anything you did by hand, and any window you left unfinished.

**4. Now close everything, chat windows included.** Tonight's three windows are
finished with. Nothing in them is needed tomorrow. Tomorrow you open a fresh
one for window 8 the way you have every other time.

Tomorrow, search for **Starting the next evening**, then carry on below. It is
the last evening: at the end of it Ripple is on your screen.

---

# PHASE 8 — progress, saved history, and the web service

**Saves to:** `ripple-build/ripple/progress.py`, `ripple-build/ripple/store.py`,
`ripple-build/ripple/build_info.py`, `ripple-build/ripple/providers.py`,
`ripple-build/ripple/api.py`, `ripple-build/requirements.txt`, and
`ripple-build/run.py` at the project root.

**Optional, and only if you want the AI reader:** `ripple-build/ripple/ai.py`
and `ripple-build/ripple/scanner/github.py`. Both reach the network. **If you
skip them, the prompt below still builds all three of the AI addresses** — they
simply answer, plainly, that there is no AI reader in this copy, and the settings
screen hides the key box on the strength of that answer. Leave the addresses out
and Phase 11 — a different window, which cannot be told what you chose — puts a
key box on the settings screen with nothing behind it: buttons that do nothing,
no error anywhere, and somebody typing a real key into it. `providers.py` is NOT
optional either. It is only a list of which company each kind of key belongs to,
it never goes near the network, and the settings screen uses it to name the
company as you type a key — reader or no reader.

**`requirements.txt` is nine lines and it is the whole of it.** The same pins as
the install command at the top of this document, so a second machine gets the
same Ripple rather than whatever was published this morning, and so the batch
file's "not installed yet" message has something to point at.

**This is one you make yourself.** The chat does not hand it to you — it is the
same two commands you used for `card.txt`:

**Type this into the black window.**
```
type nul > C:\ripple-build\requirements.txt
```

```
notepad C:\ripple-build\requirements.txt
```

Notepad opens, empty. Press the copy button at the top of the block below, paste
it in, press Ctrl+S and close it. Nine lines, and nothing else:

**Paste this into Notepad and save it.**
```
sqlglot==30.17.0
fastapi==0.115.0
uvicorn==0.30.6
pydantic==2.13.4
typing-inspection==0.4.2
python-multipart==0.0.9
extract-msg==0.48.7
httpx==0.27.2
pytest==8.3.3
```

`httpx` only matters if you built the AI reader, and `extract-msg` only if you
want Outlook `.msg` files opened. Leave them in anyway: a pinned line nobody
uses costs nothing, and a missing one is discovered by somebody else, later,
on a machine you cannot see

**Paste this into the chat.**
````text
[PASTE THE CONTRACT CARD FIRST]

Build ripple/progress.py, ripple/store.py, ripple/build_info.py and
ripple/api.py.

--- ripple/progress.py

A tiny module holding what the engine is doing this second, so the page can
ask while it waits: {job, label, done, total}. reader(job) returns a callback
the scanners already expect: on_progress(done, total, label). finish() clears
it. snapshot() returns the current state.

Reading a real repository takes minutes and a scan about a minute. A spinner
and a fixed sentence for that long is indistinguishable from a program that
has hung. Show only what has actually been counted — files really read,
statements really followed. Where there is genuinely no total, because a chain
looks at as many statements as it turns out to need, report the count and NO
fraction. A fraction would need a denominator nobody knows.

--- ripple/store.py

SQLite. save(vals, scan, summary, mode, settings) -> {saved, id, reason};
listing(settings); get(id, settings); set_status(id, status, settings).
Statuses: New, In progress, Verified, Closed. Create the table on first use.
If the database cannot be written, return saved=False with a reason a person
can act on, and never crash — the screen has to be able to say "history is
not available here" rather than showing a saved analysis that was not saved.

THE COLUMN NAMES ARE PART OF THE ANSWER. listing() returns one row per saved
analysis, newest first, at most fifty, and the Past analyses table reads these
names exactly as they are written here:

  id           the number the save came back with
  created_at   when it was saved, as ISO text
  subject      the notification's subject
  source       the upstream system
  change_type  what kind of change it was
  effective    the date it lands
  risk         the risk word from that scan
  status       New, In progress, Verified or Closed
  mode         whether the fields were read from a file or typed by hand

Underscores, not a capital in the middle. Call them createdAt and changeType
instead and every row in the table prints a dash, with nothing on screen saying
why — the rows are all there, and all empty.

get(id) returns that same row plus the three stored blobs, with vals_json,
scan_json and summary_json already read back into objects rather than handed
over as text.

Open the connection with a fifteen-second timeout rather than the default five.
This database usually sits in a folder something is syncing to the cloud, and a
sync holds a file open while it uploads it. Five seconds is short enough to lose
a saved analysis to a routine upload; fifteen rides it out, and a lock that is
real rather than passing still comes back as a plain refusal.

--- ripple/build_info.py

Which copy of Ripple is this one? Without an answer to that on screen, "it does
not work" cannot be told apart from "that was fixed a while ago, on a copy nobody
installed" - and those two need completely different conversations.

ONE version number lives here, as a plain string, and NOTHING ANYWHERE ELSE IN
RIPPLE writes a version. The packaged program's folder name, the name of the zip you
hand to somebody, and the line on the settings screen all read it from here.

Provide:

  VERSION              The number itself. Raise it whenever behaviour changes.
  build_info()         A dictionary: version, commit, built, from, label.
                       Worked out once and remembered.
  write_stamp(folder)  Writes a small BUILD-STAMP.json into a folder, holding
                       the version, the commit and the time. Used when a copy is
                       prepared for somebody else.

Work out the commit and the build time by trying these in order, taking the first
that answers, and recording in "from" which one did:

  1. a BUILD-STAMP.json sitting beside the code, if there is one
  2. the environment, if the machine that built it set the values there
  3. git - but ONLY if git actually tracks the files this copy is made of. If
     the working copy also has uncommitted edits, mark the commit so it cannot
     be mistaken for a clean build
  4. the newest date on the source files themselves

That last one is the reason the list exists. It always answers, so the screen can
never be blank - and "from" tells anybody reading it how much the answer is worth.

**Step 3 is the one that goes wrong, and it goes wrong silently.** The obvious
test is "is there a `.git` folder nearby". Do it that way and any copy of Ripple
that happens to sit inside somebody's repository picks up that repository's
latest commit and prints it as its own build. Measured on this build on 27 Aug
2026: a copy generated into the parent folder, which git had never seen, printed
a real commit hash and a real date, and nothing on the screen hedged. Move that
same folder to a machine where an unrelated repository is one level up and it
would confidently print that project's commit instead.

So ask git whether it knows THIS copy, not whether a repository exists nearby -
`git ls-files --error-unmatch build_info.py`, run inside the folder holding it.
Nothing tracked, no commit to claim, fall through to step 4, which says out loud
that it is guessing. A wrong answer that looks checkable is worse than an honest
guess, and that is the whole reason this file exists.

"label" is the one line the settings screen shows, already put together and ready
to print: "Version 1.5.0 - b6f650d - built 23 Aug 2026". Build the sentence here
rather than in the screen, so the browser and the double-clickable program print
it identically.

Serve build_info() on the health route as well, so the version can be read without
a browser.

Tests: the version is a plain string and not worked out from anything; every route
above produces a label; an uncommitted edit is visible in the commit; the stamp
file is read in preference to git when both are present; and a copy of the folder
that git does NOT track reports no commit at all rather than the commit of some
repository it happens to be sitting inside.

That last one sounds far-fetched and is not. Copy your finished folder somewhere
inside any other project that uses git, and the obvious version of this file --
"is there a .git nearby?" -- reads that project's latest commit off the disk and
prints it as Ripple's own build, with nothing hedged. Ask git whether it knows
THESE files instead:

    git ls-files --error-unmatch build_info.py

run from the folder holding it. Nothing tracked, no commit to claim, fall through
to the file dates, which say out loud that they are a guess.

--- ripple/api.py

FastAPI, thin on purpose: every route is a few lines calling the modules
above. Build the index once and keep it until re-read.

GET  /api/health      includes `build` — which build this is, so a screen can
                      say it. Nothing did, and "it does not work" has more than
                      once turned out to be "that was fixed a while ago, on a
                      copy that was never installed". Look in four places, best
                      first: a stamp file written into a packaged folder at
                      build time, the host's environment (Vercel sets
                      VERCEL_GIT_COMMIT_SHA), git ONLY where git tracks this
                      copy's own files, and last the dates on
                      Ripple's own files. Return where the answer came from as
                      well as the answer, and say plainly on screen when it is
                      the last one — a file date moves whenever anything is
                      touched and proves nothing about what was installed. A
                      guess dressed as a fact is worse than no line at all.
                      Also: the shape in the contract card: repo counts including
                      heldOnline, pathTooLong, inSkippedDirs, skippedDirNames,
                      unreadable, statements, kinds[]; catalog counts;
                      sqlDialect; maxHops; production (the one-line form);
                      productionRule (the full parsed rule); limits
GET  /api/progress    progress.snapshot()
GET  /api/catalog
POST /api/reindex
GET  /api/production            the list in force, checked against the repo
POST /api/production/read       read a pasted list WITHOUT saving it, and
                                return what was made of it plus the check —
                                this is what the settings box calls as it is
                                typed into
POST /api/production            use this list from now on
POST /api/repo/folder           {path} — read THIS folder on this machine from
                                now on, and answer with the whole health block
                                so the screen repaints from one reply.

                                THIS ROUTE IS WHY THE BUILD IS USABLE. Without
                                it the only way to point Ripple at real SQL is
                                to set RIPPLE_REPO and restart, and until
                                somebody does, every answer describes the small
                                practice pipeline — confidently, correctly, and
                                about nothing anybody cares about.

                                REFUSE A PATH THAT IS NOT THERE. A folder that
                                does not exist is a typo, and a typo is not an
                                empty repository. Accepted quietly it indexes
                                zero files, and zero files found reads on every
                                screen after it as "no impact" — the one
                                sentence this tool may never get wrong. Say
                                which path, and say a typo is what this
                                probably is. Refuse a file that is not a folder
                                too, and an empty box.

                                Strip quotation marks off the path first.
                                Windows Explorer's "Copy as path" wraps it in
                                them, and pasting that in is the single most
                                likely thing anybody will do.

                                THROW AWAY EVERYTHING READ FROM THE OLD FOLDER
                                before reading the new one — the index, the
                                parse, the catalogue. Half of one repository and
                                half of another answers about neither, and
                                nothing on screen could show that had happened.
POST /api/read-email  (file upload — .msg, .eml or a plain text file)

RIPPLE/PROVIDERS.PY, WHICH IS NOT OPTIONAL. A small table of which AI company a
pasted key belongs to, worked out from the key itself. It reaches nothing and it
is needed even in a build with no reader, because the settings screen names the
company as somebody types, and it reads that list out of /api/health.

  Three providers, one box, not three. Asking which company is one more thing to
  get wrong, and a key sent to the wrong one comes back rejected, which reads as
  "your key is bad" when it is not.

    openai   label "OpenAI"         prefixes ("sk-proj-", "sk-")
             endpoint https://api.openai.com/v1
    gemini   label "Google Gemini"  prefixes ("AIza",)
             endpoint https://generativelanguage.googleapis.com/v1beta/openai
    groq     label "Groq"           prefixes ("gsk_",)
             endpoint https://api.groq.com/openai/v1

  Each entry also carries where to get a key, for the screen to link to.

  detect(key) matches the LONGEST prefix, because an Anthropic key begins "sk-"
  exactly as an OpenAI one does. Keep a second list of shapes you recognise but
  cannot use — "sk-ant-" is Anthropic — so name_of_unsupported(key) lets the
  screen say "that is an Anthropic key" instead of "rejected".

  is_chat_model(id) filters out what cannot hold a conversation: embeddings,
  audio, image, moderation, rerank. rank_models(provider, models) puts the
  preferred ones first and KEEPS every other one — hiding a model somebody is
  paying for because you have not heard of it is the worse mistake.

  DO NOT WRITE A LIST OF MODEL NAMES INTO THE CODE. It is wrong within months.

THE AI ROUTES, IF THIS BUILD HAS AN AI READER AT ALL. The settings screen in
Phase 11 has a key box on it, and a box with no route behind it is a screen that
looks finished and does nothing. Either build these three routes here, or take
the key box out of Phase 11 — one or the other, never one of the two.

If you build them you must ALSO write `ripple-build/ripple/ai.py`, because these
routes import it and nothing else in this kit produces it. It offers
read_email(text, cfg), write_summary(payload, cfg), write_reply(payload, cfg),
check_key(cfg), list_models(cfg) and an AIUnavailable exception. All three
providers speak the same OpenAI-shaped POST /chat/completions, so there is one
code path and only the address, the key and the model change. Ask the provider
GET /models with the key — that proves the key and produces the real list in the
same call. If a provider refuses the optional response_format field, send the
request again without it rather than losing the whole call; the prompt asks for
JSON in words as well.

IF YOU ARE NOT BUILDING THE READER, STILL BUILD ALL THREE ROUTES. Omit ai.py,
build providers.py as always, and have each route answer plainly that there is
no reader in this build. Report `ai.available` false in /api/health, and the
settings screen hides the key box on that alone.

Do NOT omit the routes. Phase 11 is a different window and cannot be told what
you chose. Measured on a build made from this kit: this window took the "leave
it out" branch, Phase 11 built the key box anyway, and three addresses were
called that nothing served — with no error anywhere, just buttons that did
nothing. A route that exists and says "not in this build" is the only version
of this that two strangers can both get right.

POST /api/ai/check      really call the model that is really selected, and say
                        which one. A key that is present is not a key that
                        works, and a key that works with one model can be
                        refused by another. The only honest check is the round
                        trip.
POST /api/ai/connect    {key, model} — a blank key means keep the one already
                        set, a blank model means keep the model already chosen.
                        Work out which company issued the key from the key
                        itself, ask that provider which models the key can
                        really use, prove it answers, and only then keep it. If
                        anything in that sequence fails, put back exactly what
                        was there before and refuse with the provider's own
                        reason — a half-set key is worse than no key.
POST /api/ai/forget     forget a key typed into the screen. One set on the host
                        stays.

All three answer with the whole /api/health block, because the page replaces its
copy of it with the answer.

The key lives in this process and nowhere else: never written to disk, never
logged, and never returned by this or any other route. What /api/health may say
about it is facts, never the key:

  ai   available      whether a key and a model are both in place
       model          the model id
       modelLabel     the one line the screen prints. The id IS the label. A
                      hand-written pretty name for every model of every provider
                      is a list that rots, and a wrong pretty name on screen is
                      worse than the real id, which somebody can search for
       provider       which company issued the key
       providerLabel  that company's name, for a screen
       keyFrom        "entered", "environment", or empty — so "it stopped
                      working" has an explanation
       models         the models this key can really use, as the provider listed
                      them. Empty until a key has been accepted, and never a
                      guessed list
       providers      each one's id, label, key prefixes and where to get a key,
                      so the screen can name the company as the key is typed,
                      before anything is sent anywhere — one box, not one box
                      per company
       unsupported    the key shapes you recognise but cannot use, so the screen
                      can say "that is an Anthropic key" instead of "rejected"
       keyLasts       whether a key typed in here survives

                      The answer is everything the rules reader found, plus one
                      more key the review screen needs:

                        emailPreview  subject
                                      body        the first 4000 characters
                                      fromName
                                      fromEmail
                                      attachments
                                      kind        which of the three shapes it
                                                  was read as

                      That block is what lets the review screen show the email
                      beside the fields pulled out of it. Without it there is no
                      way on screen to check a field against the sentence it came
                      from — which is the entire point of asking somebody to
                      confirm before anything is scanned.

                      WHAT THESE TWO ANSWER WITH. Both /api/production and
                      /api/production/read return the parsed rule itself —
                      text, entries, names, patterns, nameCount, patternCount,
                      notes, column, oneLine — and one extra key sitting beside
                      those, at the same level:

                        check   which of the tables on this list Ripple has
                                never seen in the repository that is loaded

                      Flat, with check alongside the rule's own keys. Wrap the
                      rule in a key of its own and the settings box shows an
                      empty list of chips above a red warning about nothing.

                      POST /api/production answers with the WHOLE /api/health
                      block instead, because the page replaces its copy of that
                      block with whatever comes back, and the published-table
                      line has to change on screen the moment it is saved.

                      SAVING THE LIST MUST NOT RE-READ THE REPOSITORY. Which
                      tables count as published changes nothing about the files
                      that were read off the disk, and a full re-read costs
                      minutes on a real repository. Charge somebody minutes for
                      correcting a typo and they stop correcting it — on the one
                      setting that decides whether "no production table is
                      impacted" is a result or an accident.

GET  /api/catalog     everything learned from the CREATE statements, asked for
                      as its own request because the review screen fetches it
                      separately while the rest of the page is already up:

                        tables       {table name: [column names]}
                        definedIn    {table name: the file that builds it}
                        gaps         the tables Ripple could not fully read
                        tableCount   how many tables
                        columnCount  how many columns across all of them

                      The counts are called tableCount and columnCount HERE, and
                      tables and columns inside /api/health. Two shapes, two
                      sets of names, and the same screen reads both. Swap them
                      and the card on the review screen prints "undefined tables
                      found" over a repository that was read perfectly well.

                      WIRE IT IN, OR IT COUNTS NOTHING. progress.py on its own
                      reports an empty job for ever; api.py is what fills it.
                      Pass progress.reader(...) as the on_progress argument of
                      all three slow calls, and call progress.finish() when each
                      one ends — including when a scan fails, so a failed scan
                      does not leave the screen counting for ever:

                        reading the folder
                          RepoIndex.build(..., on_progress=progress.reader("reading"))
                        understanding the SQL
                          parse_repo(..., on_progress=progress.reader("parsing"))
                        following the column
                          trace(..., on_progress=progress.reader("scanning"))

                      Those three words — reading, parsing, scanning — are a
                      contract with the page, which is built in a different
                      window and turns each one into a sentence a person can
                      read. Invent a fourth name and the page falls back to the
                      single word "Working" for the entire wait.

                      job is a non-empty string only while something is really
                      happening, and empty the moment it stops. The page shows
                      nothing when job is empty, which is what makes the line
                      disappear on its own instead of sticking at a number.

                      total is the real denominator when there is one — files to
                      read, files to parse — and 0 when there is not. Following
                      a chain looks at as many statements as it turns out to
                      need, so it reports a rising count against a total of 0,
                      and the page prints "1,400 so far" rather than a fraction
                      over a denominator nobody could check.

                      THE WHOLE BLOCK, KEY BY KEY. app.js reads whatever this
                      route returns, and a key it looks for that is not here
                      fails nowhere: no error, no warning, the screen simply
                      shows nothing where a number belongs, and nobody finds
                      out. Write every key below, spelled exactly this way.
                      If you ever add a key here, add it to every place that
                      builds this block, or one of them goes blank in silence.

                        ok               always true
                        build            the whole dictionary from
                                         build_info(): version, commit, built,
                                         from, label
                        source           "folder"
                        limits           maxUploadBytes  the biggest email file
                                                         that will be accepted;
                                                         the drop zone checks a
                                                         file against this
                                                         before it sends
                                                         anything
                                         historyKept     true when saved
                                                         analyses really last
                        sqlDialect       the dialect in force, or "generic"
                        maxHops          how many renames deep a scan follows
                        production       the ONE-LINE form of the
                                         published-table rule, for a status row
                        productionRule   the full parsed rule. It must carry
                                         text — the paste exactly as it
                                         arrived — because the settings box is
                                         filled from it, and a tidied version
                                         handed back is not the list somebody
                                         typed
                        productionFrom   "entered", "environment" or
                                         "default". Leave it out and the screen
                                         cannot tell "nobody has ever said
                                         which tables we publish" from
                                         "somebody set the list this morning",
                                         so the warning that a clean result is
                                         being judged against a guessed naming
                                         rule never appears at all
                        catalog          tables   how many table names were
                                                  learned
                                         columns  how many columns across them
                        repo             the fourteen keys below

                      The repo block, all fourteen, every one counted from what
                      was really read rather than repeated back from a setting:

                        label            the repository's name, for a heading
                        branch           the branch, or empty when the folder
                                         was never a checkout — empty, never
                                         "main", because a guessed branch is
                                         printed as a fact
                        path             the folder on disk
                        files            how many files are in the index
                        statements       how many SQL statements were
                                         understood
                        unreadable       how many files would not parse
                        heldOnline       files never opened because the cloud
                                         is holding them
                        pathTooLong      files never opened because the path
                                         was too long
                        inSkippedDirs    code files walked past because of the
                                         folder they sit in
                        skippedDirNames  the names of those folders, as a list
                        unknownExt       the file types Ripple does not open,
                                         biggest group first, as {ext, files},
                                         at most twelve. Leave this out and a
                                         repository whose pipeline is written
                                         in a type you do not read looks
                                         exactly like a repository with no
                                         pipeline in it
                        runsSqlFrom      how many programs run SQL kept in a
                                         separate .sql file that Ripple did
                                         find. Whole folders of DAGs are
                                         written that way, and without this
                                         they read as empty
                        exists           whether the folder is really there
                        kinds            what kinds of file are in the index,
                                         biggest group first, as {lang, files}

                      Every route that CHANGES what Ripple is set to — re-read,
                      and saving the published-table list — answers with this
                      whole block rather than an acknowledgement. The page keeps
                      one copy of it and replaces that copy with whatever comes
                      back, so a route that returns {"ok": true} leaves every
                      number on screen showing the old answer.

There is no route that takes typed-in email text. There was one, and it went:
a box somebody pastes an email into produces a notification with no envelope —
no From, no Subject, nothing but words — so the source system and the contact
came back blank far more often than from the same email uploaded as a file. Two
ways in that behave differently is one too many. Upload the file, or use the
manual tab. The function that reads message text STAYS, because a plain .txt
upload is read with it.
POST /api/scan        {upstream[], changeKind} -> the scan result JSON
POST /api/summary     {scan, vals} -> {summary, reply}
POST /api/history     GET /api/history     GET /api/history/{id}
PATCH /api/history/{id}  {status}
GET  /api/file?path=  the real text of a scanned file

POST /api/scan        {upstream[], changeKind, maxHops} -> the scan result JSON

                      maxHops is optional, and it is the whole of what makes the
                      "follow these trails deeper" button on the findings screen
                      do something. When it arrives, use it FOR THIS SCAN ONLY —
                      copy the settings and change the copy — so running one
                      scan deeper does not quietly change every later scan.
                      Clamp it between 1 and 25. Twenty-five is not a guess
                      about how pipelines are built; it is a stop on a scan that
                      has clearly gone wrong, set far above any real chain,
                      because every extra hop is more statements to look at and
                      a scan nobody can cancel is worse than one that stopped
                      too soon.

                      An empty upstream list is refused with 400 and a sentence,
                      never scanned. Nothing is scanned until the person has
                      confirmed the names on screen, so a request carrying no
                      names is a mistake — not an instruction to search
                      everything.

                      So is an entry with attrs empty and whole false. Refuse
                      it with 400 and the sentence "<table> has no attribute on
                      it and is not marked as a whole-table change. Add the
                      attribute that is changing, or tick 'Whole table' to
                      follow every column and every statement that reads it."
                      Measured before this: such an entry went through the
                      column walk with nothing to walk and came back "no usage
                      found" — a clean answer to a question never asked. Each
                      entry is passed to trace as {table, attrs, whole}.

                      Add a repo block to the result — label, branch,
                      urlTemplate — so the findings screen can say where the
                      code came from. On a folder there is no address to send
                      anyone to, so urlTemplate is an empty string and the
                      screen offers no link rather than a broken one.

POST /api/scan also accepts an optional maxHops. When it is given and differs
from the setting, copy the settings for that one call and use the copy — never
write it back, so following one trail deeper does not quietly change every later
scan. Clamp it between 1 and a ceiling of 25. This is what the "follow these N
renames deep instead" button on the findings screen calls, and without the field
the button has nothing to ask for.

Refuse an upload over max_upload_bytes with a message saying what the real
ceiling is and why, not a bare 413.

Serve web/ at /static and web/index.html at /, finding that folder with
paths.web_dir() from Phase 1 and never by walking up from __file__ — see the
reason there. Send Cache-Control: no-store
for the page and the script — during a demo or an edit, a cached script is
the difference between seeing a change and staring at yesterday's page. Cache
the fonts, if any, for a month.

Also write run.py at the project root: print the repository, the dialect and
the address, whether it is running packaged or from source, then start uvicorn
on host 127.0.0.1, with a --no-browser flag.

TAKE THE PORT BEFORE YOU ANNOUNCE IT. The obvious run.py names port 8000,
prints "open http://localhost:8000", opens the browser and only then hands the
number to uvicorn. Measured on a managed work laptop, 27 Aug 2026: Windows
refused 8000, and by the time anyone knew, the browser was already sitting on
an address that would never load. So bind first, print second.

  Try 8000, then 8001, up to 8020, and last of all port 0, which means "any
  free one you like" and is what saves a machine where the whole range is
  refused. BIND to each -- do not ask whether anything is listening on it.
  Those are different questions, and the gap between them is the bug: nothing
  was listening on 8000, and the machine still would not allow it.
  Report the port you actually got, never the one you hoped for.

  If somebody set a PORT environment variable, use that one and no other. Quietly
  searching past a number somebody typed starts Ripple somewhere they did not
  ask for, and the printed address is the only clue it happened.

AND SAY WHICH OF THE TWO PROBLEMS IT IS. A refused port is either occupied by a
program or RESERVED by Windows itself -- Hyper-V, WSL and Docker each reserve
whole ranges, and a work laptop often has several. Windows reports the second as
error 10013. The fixes are opposites: for one, close the program; for the other,
there is no program to close and closing things is wasted effort. "They are all
in use, close whatever is using them" is a confident, actionable, wrong answer,
which is the one kind of answer Ripple may never give. When 10013 appears, say
the ports are reserved, say closing things will not help, and give the command
that lists the reserved ranges:

    netsh interface ipv4 show excludedportrange protocol=tcp

Pass uvicorn the app OBJECT -- from ripple.api import app -- and not the string
"ripple.api:app". Both work today. Only the object still works once this is
packaged in Phase 13, because a packaged program has no importable module of
that name to look up, and the string form exits immediately with "Could not
import module".

BIND TO 127.0.0.1 AND NEVER TO 0.0.0.0. The two look interchangeable and are
not. 127.0.0.1 is the machine talking to itself and cannot be reached from
outside it. 0.0.0.0 offers the whole application to everyone on the office
network, which would put an analysis of internal source code on a port any
colleague could open, with no password on it. Tutorials are full of 0.0.0.0
because they are written for containers. This is a laptop.
````

**Check it worked.** From `C:\ripple-build`:

**Type this into the black window.**
```
python run.py --no-browser
```

It prints the folder it will read, the SQL dialect and an address, and then sits
there doing nothing. That is correct — it is waiting for a browser. **Leave it
running** and open a second Command Prompt, then:

**Type this into the black window.**
```
curl http://127.0.0.1:8000/api/health
```

**Use the address it actually printed.** It will not always be 8000, and on a
managed laptop it often is not. If it printed 8014, put 8014 in that line. An
address you assumed rather than read is the thing this whole phase is about.

A wall of text starting with `{"ok":true` is a pass.

**Now the second check, and it is the one that matters.** Leave that first Ripple
running, open a THIRD Command Prompt, go to `C:\ripple-build`, and start Ripple
again:

**Type this into the black window.**
```
python run.py --no-browser
```

It must print a **different** address and keep running. Both are now up, on two
ports, each answering `/api/health`.

If instead it fails with something about an address already in use, or prints the
same address as the first one, then your `run.py` NAMED a port instead of taking
one. That is a real bug and it will not show up on your own machine — it waits
until a laptop refuses the port, which a managed one does, and by then the
browser is already open on an address that will never load. Go back and read
"TAKE THE PORT BEFORE YOU ANNOUNCE IT" above, and paste the chat this:

**Paste this into the chat.**
````text
run.py is naming a port instead of taking one. Starting Ripple a second time
while the first is still running either fails or prints the same address.

Rewrite the port part of run.py so that:
  it BINDS a socket to test each candidate, because whether anything is
    listening on a port is a different question from whether this machine will
    allow the bind, and only the second one matters
  it tries 8000, 8001 ... 8020, and then port 0, which means "any free one"
  it reports the port it actually got, never the one it hoped for
  it takes the port BEFORE printing the address or opening the browser
  if PORT is set in the environment it uses that one and no other, and says
    which port and why when that one cannot be used
  when every candidate is refused it tells apart the two causes: Windows error
    10013 means the ports are RESERVED by this machine, not held by a program,
    so it must say that closing things will not help and give the command
    netsh interface ipv4 show excludedportrange protocol=tcp
    anything else means they really are in use, and it says that instead

Give me the whole of run.py again.
````

To stop both servers, go back to each window and hold Ctrl and press C.

---

## When Phase 8 goes wrong — the six things to paste back

Phase 8 builds five files at once and every one of its failures is silent: the
program starts, looks healthy, and is wrong. Check these in order before you
move on, and paste the matching block into the same window.

**The screen shows a blank where a number should be.** One of Ripple's addresses
answered with a tick instead of the whole block of facts the page redraws from.

**Paste this into the chat.**
````text
That route answers with {"ok": true}. It has to answer with the WHOLE
/api/health block instead.

The page keeps one copy of that block and REPLACES its copy with whatever comes
back. A route that returns an acknowledgement leaves every number on screen
showing the answer from before the change, and nothing anywhere says so. Every
route that changes what Ripple is set to -- re-reading the repository, saving
the published-table list -- answers with the whole block.

Give me the file again.
````

**The progress line never moves.** `progress.py` on its own reports an empty job
for ever; `api.py` is what fills it.

**Paste this into the chat.**
````text
progress.py is built but never wired in, so it reports an empty job for ever and
the screen shows a spinner for four minutes.

Pass progress.reader(...) as the on_progress argument of all three slow calls,
and call progress.finish() when each one ends -- including when a scan FAILS, or
a failed scan leaves the screen counting for ever:

  RepoIndex.build(..., on_progress=progress.reader("reading"))
  parse_repo(..., on_progress=progress.reader("parsing"))
  trace(..., on_progress=progress.reader("scanning"))

Those three words are a contract with the page, which is built in a different
window and turns each one into a sentence. Invent a fourth name and the page
falls back to the single word "Working" for the whole wait.

Give me the file again.
````

**A card on a screen is empty and nothing errors.** A key is missing from the
health block.

**Paste this into the chat.**
````text
Check the health block against the list of keys I pasted into this window
earlier -- the one under THE WHOLE BLOCK, KEY BY KEY -- key by key, and tell me
which ones you have left out.

One app.js reads that block in both builds, so a key present in one and absent
from the other fails nowhere: the screen simply shows nothing where the other
one shows a number. Every key on that list, spelled exactly that way, including
all fourteen in the repo block.

Then give me the file again.
````

**It hands uvicorn a string.** Works today, breaks the day it is packaged.

**Paste this into the chat.**
````text
run.py passes uvicorn the string "ripple.api:app". Pass it the app OBJECT
instead -- from ripple.api import app -- and hand that over.

Both work while running from source. Only the object still works once this is
packaged, because a packaged program has no importable module of that name to
look up, and the string form exits immediately with "Could not import module".
That is a whole evening lost in Phase 13, on a fault that looks nothing like
this one.

Give me run.py again.
````

**It binds to 0.0.0.0.** Search what it gave you for that number.

**Paste this into the chat.**
````text
Bind to 127.0.0.1, never 0.0.0.0.

The two look interchangeable and are not. 127.0.0.1 is the machine talking to
itself and cannot be reached from outside it. 0.0.0.0 offers an analysis of
internal source code to everyone on the office network, on a port with no
password on it. Tutorials are full of 0.0.0.0 because they are written for
containers. This is a laptop.

Give me the file again.
````

**There is a key box on the settings screen and its buttons do nothing.** Or the
three AI addresses are built and there is no box. It has to be both or neither,
never one of the two.

**Paste this into the chat.**
````text
Either build all three AI routes here -- /api/ai/check, /api/ai/connect,
/api/ai/forget -- or tell me to take the key box out of Phase 11. A box with no
route behind it is a screen that looks finished and does nothing, and somebody
will paste a real key into it.

If you build them: the key lives in this process and nowhere else. Never written
to disk, never logged, never returned by any route. What /api/health may say
about it is facts -- which provider, which model, where the key came from --
never the key.
````

---

# PHASE 9 — the page and its styles

**Saves to:** `ripple-build/web/index.html`, `ripple-build/web/styles.css`

**Paste this into the chat.**
````text
[PASTE THE CONTRACT CARD FIRST]

Build web/index.html and web/styles.css. No framework, no CDN, no build step.

This phase builds how it looks, and it is the one phase where the words below are
a specification rather than a suggestion. The colour values are exact. Use them as
given.

LAYOUT
A fixed dark navy sidebar 288px wide: the product name, a numbered list of the
seven steps (Notification, Review fields, Repository, Impact analysis,
Dependency map, Summary, Reply), then Past analyses and Settings & checks,
then a status block pinned to the bottom showing the repository, whether the
SQL dialect is set, and a coloured dot for each.
To the right: a white header strip with the current step and a slot for a
progress line, then a scrolling area with a 1200px-wide content column.

The seven steps live in <template> elements — t-step1 to t-step7 — each
holding the static skeleton for that step with data-x="..." hooks the script
fills in. Keep the templates dumb: no text that changes, only the frame.

STYLE
The palette is not a matter of taste. It is the design, already settled, and
it is settled already. Define exactly these CSS variables at the top
and use them everywhere -- never a colour written inline:

  --navy:#00175A; --blue:#006FCF; --blued:#005CAD; --pale:#E3F0FC;
  --line:#DCE4EE; --line2:#C7D4E4; --line3:#E7EDF5; --hair:#F0F4F9;
  --bg:#F2F5F9; --card:#fff; --tint:#FAFCFE;
  --ink:#10243E; --body:#33445E; --mute:#5C6C84; --faint:#8595AB;
  --chip:#EDF2F8; --chipink:#45566E;
  --red:#B01C2E; --redbg:#FDE8E8; --redln:#F3C4C4;
  --amber:#8A6100; --amberbg:#FFF4D9; --amberln:#EFDFAF;
  --green:#006B40; --greenbg:#E4F5EC; --greenln:#BFE5CE;
  --violet:#6D4B9E; --violetbg:#F0EAFA; --violetln:#D8C9EF;
  --codebg:#FBFCFE; --codehead:#0B1F45; --codenum:#93A3B8;
  --hit:#FFF7E1; --hitln:#F0DFAE; --hitbar:#E3A008; --hitpill:#FFF1CC;
  --shadow:0 1px 2px rgba(16,36,62,.06);

They are named for what they do, which is why there are four greys for lines:
--line is a card border, --line2 an input border, --line3 a divider inside a
card, --hair a row separator. The four ink tones run the same way, strongest
first: --ink for headings, --body for paragraphs, --mute for card labels,
--faint for field labels and hints.

Cards are white with a 1px --line border, 12px radius and --shadow. Body text
is 14px with line height 1.5. The sans family is 'Public Sans' falling back to
Segoe UI and system-ui. The monospace family, used for every table and column
name on screen, is 'IBM Plex Mono' falling back to Consolas.

SCOPE THE SHELL RULES OR THEY REACH INSIDE A SCREEN. The frame -- the navy
sidebar, the header strip, the scrolling middle -- is yours. The screens inside
it are written by two other windows that cannot see this stylesheet. Write every
shell rule against the shell itself, `body > .side`, never a bare `.side`, and
the same for main, head, scroll, col, shell and wrap. Measured: a bare
`.side{position:fixed;top:0;left:0;bottom:0}` also caught a card another window
had called "card side", turned it into a fixed panel over the whole left edge,
and hid the numbered rail. No error, and every test still green.

Components to define, because the script uses these class names:
  .card .pad .pad.lg .clip .chead      cards and their tinted header strip
  .grid2 .grid2.even .rail             two-column layouts
  .lbl .small .muted .faint .prose     type scale
  button.pri .ghost .sm .link .danger  buttons
  .pill .pill.on .pill.tab             the mode and source toggles
  .badge with .blue .red .amber .green .grey .violet, and .badge.sm
  .tag                                  the small upper-case row label
  .chip .chip.mono .chip.alias .chip.pattern .chips .scrollbox
  .note with .info .warn .good .bad     the four kinds of on-screen note
  .iwrap .ifact button.i .ipanel        the information button and its panel
  .statgroups .stats .stat              the counted cards
  .groups .group .ghead .rowhead .row .detail        the findings list
  .code .code .f .code .body .code .ln .ln.hit .why  the code snippet
  .maprow .mapsrc .branches .branch .node .arrow .legend   the map
  .tree .tree .node.end .tree .tail     the map's tree of boxes (Phase 11)
  .fold .fhead .ftitle .fhint .fbody .fextra   the folded list (Phase 11)
  .wholetoggle .chip.whole              the whole-table checkbox and chip
  .factrow .drop .foot .spin .big .hist

Five rules that keep it usable with real data. Every one of them was measured
on a repository the size of the one this is built for, not guessed at:
  A real table name runs to forty characters and a real path to a hundred and
  sixty. Give every grid cell min-width:0 and overflow-wrap:anywhere, or one
  long name widens the grid until the page scrolls sideways and the findings
  walk off the right of the screen.
  .scrollbox is a chip container with a max height and its own scrollbar, for
  the lists that are genuinely hundreds long. Use it for every list a real
  repository makes long, not only the obvious ones: a card that grows without
  a limit is a card that swallows the page.
  Every row of stat cards is the SAME grid — five columns, three below 1500px,
  two below 900px — and a short row simply leaves the rest of the row empty.
  Give a row its own column count and it goes wrong twice over: a row of two
  stretches each card to half the page while the row above holds five narrow
  ones, and a row of one strands it. Order the cards worst first, so when there
  are more than fit a row it is the mildest one that wraps.
  The dependency map is a tree (Phase 11): each box sits on its own line under
  the box it is built from, indented and joined by a connector line, so nothing
  scrolls sideways and nothing wraps into unconnected boxes. Keep the .branch
  rule all the same — it still scrolls sideways inside its own row, with a
  visible scrollbar — for any chain drawn as a row.
  Long lists are capped in the DRAWING, never in the analysis, and what was
  dropped is said out loud with its count. Measured: two hundred and twelve
  files to check by hand, each with a name, a reason and a snippet, made that
  one card 22,000 pixels tall inside a 40,000-pixel page. Draw forty in full and
  name the rest as chips in a .scrollbox, inside a list that folds shut (Phase
  11). Sixty branches folded into one tree on the map, the rest counted out
  loud. A page nobody scrolls to the end of hides its own ending.

THE INFORMATION BUTTON, AND WHAT MAY GO BEHIND IT
Every screen here carries more explanation than a person needs while they are
reading an answer. Build ONE disclosure control in this phase and have every
screen call it. Two of them drift apart, and then they behave differently on
screens nobody ever compares side by side.

One helper in app.js:

  why(fact, label, ...explanation)

`fact` is the node that stays visible. `label` names it for a screen reader and
keys whether the panel is open, so a redraw does not shut a panel somebody is in
the middle of reading. Everything after that is the explanation — a string
becomes a paragraph, a node is appended as it is. It returns one block: a line
holding the fact with a small round i after it, and a hidden panel underneath.

Three more helpers live in the same file under the same rule, and Phases 10
and 11 both call them, so their names are fixed here: fold(label, head, body,
opts) and foldFrom(label, card, opts) for the folded list, wholeToggle(on,
onchange) for the whole-table checkbox. What each does is in the phase that
draws it.

What the control must be:
  a real <button type="button">, so Tab reaches it and Enter or Space opens it
  aria-expanded, flipped on every click
  aria-controls naming the panel, which carries role="note" and hidden
  aria-label saying what it explains, or it is announced as the letter i
  Escape closes it and hands the focus back to the button that opened it
  nothing downloaded at run time — the offline copy refuses outbound
  connections and a panel built from a library would simply be empty

Never a title= tooltip. One cannot be opened on a touch screen, cannot be
reached from a keyboard, and vanishes while it is being read.

The panel opens in the normal flow, underneath the fact, never as a floating
box. Cards clip their own contents, so a positioned panel inside one is cut off
at the card's edge at some window width nobody tested.

Name the family so it cannot collide: .iwrap, .ifact, button.i, .ipanel. In
particular do NOT call it .why — that class already names the amber tag riding
on a matched line inside a code snippet, and a bare .why rule reaches it too.

The same trap in the script. Nothing may declare a local `why` — a const, a let
or a var — inside a function that also calls the helper, because a local shadows
the shared function for the whole of that function and the call throws. The
offline build refuses to run when it finds one, and names it, because that fault
appears only in the packaged copy nobody can check.

WHAT MAY GO BEHIND THE BUTTON, AND WHAT MAY NOT
This is the line the whole product rests on, and getting it wrong breaks the
tool rather than making it untidy.

  STAYS ON THE PAGE   the fact, the number and the names. "1 file is of a type
                      Ripple does not open — .ipynb". "4 production tables at
                      risk". "2 gaps in what Ripple could see."
  MAY GO BEHIND THE i the explanation of why that fact matters, what Ripple did
                      about it, and what somebody should do next.

Somebody who never presses the button still sees everything Ripple knows it
missed. They lose the reasoning, never the fact. If you find yourself moving a
count, a table name, or a warning that something was not read behind the button,
stop — that one stays out.

Cut the words on the page down to the fact and the number. A card that reads
heading, paragraph, finding becomes heading, finding, i. That is the pattern for
every screen in Phases 10 and 11, and it is not optional: this front end carried
2,800 words on nine screens, and most of them were the middle paragraph.

The test that holds the line is Codebase/tests/test_screen_details.py. It walks
every why() call in app.js, blanks out the explanation arguments, and then looks
for each count and each warning in what is left. If one of them survives only
inside a panel, it has been hidden, and the test says which.
````

**The fonts come after this, and they are the one thing a chat cannot hand you.**
Save the two files first, then come back for them.

### The two typefaces, which no chat can hand you

This is the one part of the screens that does not come out of a chat window, and
it is the second and last thing in this kit that has to arrive as files — the
first being `sqlglot` in Phase 0. **Public Sans** and **IBM Plex Mono** are 16
compressed font files, 306 KB in total. They are binary. A chat can write you the
code that fetches them; it cannot write the fonts.

Both are free and open — Public Sans is the United States government's typeface,
IBM Plex Mono is IBM's, and both are published under the SIL Open Font License,
which allows exactly this. Nothing here needs a licence, an account or a purchase.

**Three ways to get them. Try them in this order.**

**Route 1 — have the chat write a small downloader.** This is the one to try
first, because it keeps the fonts on your own machine and Ripple then needs no
network at all, ever. Paste this:

**Paste this into the chat.**
````text
Write me ripple-build/getfonts.py, a one-off script I run once and then never
again. It has to:

  ask Google Fonts for the stylesheet covering Public Sans at weights
  400,500,600,700,800 and IBM Plex Mono at weights 400,500,600, using the css2
  API and display=swap

  send a normal desktop browser User-Agent header on that request. This is the
  part that catches people out: without it Google returns .ttf files, and with
  it Google returns the much smaller .woff2 ones. Do not skip it and do not use
  urllib's default agent

  keep ONLY the "latin" and "latin-ext" subsets and skip the rest. Google now
  answers with cyrillic, greek and vietnamese as well - 30 files rather than 16,
  and nearly a third more to download - and Ripple's screens never show a word
  in any of them

  read every font URL out of the stylesheet it gets back, download each one into
  ripple-build/web/fonts/, and name each file for its family, weight and subset,
  lower case with hyphens - for example public-sans-600-latin.woff2

  write ripple-build/web/fonts/fonts.css containing the same @font-face rules,
  with every src url rewritten to /static/fonts/<the local filename> and every
  unicode-range kept exactly as Google gave it. The unicode-range is what makes
  the browser fetch only the file it needs, so losing it is a real cost

  print how many files it saved and their total size, and exit with an error if
  it saved none, so a silent failure cannot look like success

Use only the Python standard library.
````

Then run it once:

**Type this into the black window.**
```
python getfonts.py
```

You want it to report 16 files and about 306 KB. Check the folder:

**Type this into the black window.**
```
dir web\fonts
```

**Route 2 — if that laptop cannot reach Google.** Run the same script on any
machine that can — a home laptop, a phone hotspot — and carry the resulting
`web\fonts` folder across. It is 348 KB, which fits anywhere. Unlike Ripple's
own code, these are somebody else's published files and carrying them is the
normal way to get them.

**Route 3 — go without them, and know exactly what you lose.** Delete this line
from `web/index.html`:

**This is the line to find and delete.**
```
<link rel="stylesheet" href="/static/fonts/fonts.css">
```

Everything works. Every number, every rule, every answer is identical, because
the fonts are only shapes. The screens use Segoe UI and Consolas instead, which
is why those two are named as the fallbacks. Headings sit slightly wider and
table columns line up slightly differently. Nothing is broken, and nobody who has
not seen both would know.

**Delete the line if you skip them — do not just leave the folder empty.** Left
in, the browser asks for a stylesheet that is not there, gets a 404 on every
single page load, and puts a red line in the browser's console. Harmless, and it
sits there for ever looking like a fault somebody should investigate.


**Check it worked.** From `C:\ripple-build`:

**Type this into the black window.**
```
python run.py
```

Your browser opens by itself. You should see the dark navy sidebar down the left
and the header strip across the top, **in colour**, with an empty area in the
middle. Nothing else works yet, and that is expected — the screens arrive in the
next two phases. If what you get is black text on a plain white page with no
layout at all, the stylesheet did not load rather than being wrong.

---

# PHASE 10 — the screens: notification, review, repository

**Saves to:** `ripple-build/web/app.js` — this window creates the file. Window 11
adds to the **end of the same file**, so do not close it off or start a second one.

**Paste this into the chat.**
````text
[PASTE THE CONTRACT CARD FIRST]

Build the first part of web/app.js — plain JavaScript, no framework, no build
step. I will paste Phase 11 underneath it, so end this part cleanly and do
not write a closing boot block yet.

Every card on these screens says the fact and puts the reasoning behind the
information button from Phase 9 — why(fact, label, ...explanation). Read the
line in Phase 9 about what may go behind it before you write a word of copy: the
count, the table name and the warning stay on the page, always.

STRUCTURE
A single state object S: {step, maxStep, view, mode, health, vals,
emailPreview, scan, summary, reply, savedId, manRows, man, busy, busyWhat,
openGroup, openRow, graphTab, prod, why, folds}. folds keys which folded
lists are open, by label — see fold() in Phase 11. A manRows entry is
{table, attrs, whole}. A render() that clears the view, clones
the template for the current step and calls the function for it. Small
helpers: $, $$, el(tag, props, ...children), x(root, name) for the data-x
hooks, api(path, opts) that throws with the server's own message.

run(fn, what) wraps everything slow: sets busy, renders, starts a poll of
/api/progress twice a second, and re-renders only when the progress line
changes. Show the counted line if there is one and the fixed sentence until
there is. Never animate anything that is not really happening.

STEP 1 — the notification.
Two modes on a toggle: from email, or entered by hand.
Email mode: a drop zone that also opens a file picker. No paste box — see the
routes above for why — and beside the drop zone a short card pointing at the
manual tab, so "I have no file" has a visible answer rather than a dead end.
Check the file size in the browser as well as on the server, and say what the
real ceiling is. Nothing is scanned until the person confirms — say so on
screen.
Manual mode: rows of upstream table + comma-separated attributes, add and
remove, each row with the "Whole table" checkbox described below; and a
details panel with source system, change type (a select with the five kinds
the scan actually understands, labelled Not specified, Decommission, Value
format change, Data type change, Rename — no "attribute" in front, because a
whole table can be what changes), effective date (a real date
picker, plus the date written out in words underneath so a slip is visible),
what is changing, contact name, contact email, contact team.
The contact email box takes ANY number of addresses: it pulls every address
out of whatever is pasted — including a whole Outlook To line — and shows
them back as separate chips, so what was understood is obvious. It must
update itself without re-rendering the page, or the cursor jumps out of the
box on every keystroke.
Manual mode goes STRAIGHT to step 3. Being shown "check what Ripple read"
after typing it yourself is being asked to check your own typing, so the
review step is not in the wizard at all in that mode — not greyed out, not
silently skipped while the count still says 7.

THE WHOLE TABLE CHECKBOX, on every upstream row, on this screen and on step 2.
Ticked, the attribute box is emptied and disabled and its placeholder reads
"every column — the table itself is changing"; the row is sent as
{table, attrs: [], whole: true}. A row can go forward when it names a table
and EITHER names an attribute OR is ticked. A named table with neither is
refused by the server, so refuse it here first: the count line reads
"N tables · N attributes · N whole tables", the hint under the button says a
table with no attribute and not marked whole will not be scanned, and on step
2 a red note on the row reads "Nothing to scan on this row" and the Continue
button stays disabled until the row is fixed or removed. A ticked row on step
2 carries an amber note: "Whole table. Ripple will follow every statement that
reads <table>, and every table built from those. Untick this if only some
attributes change, and name them instead." One helper for both screens,
wholeToggle(on, onchange) -> a <label> holding a real checkbox, so a keyboard
reaches it and both screens behave the same.

STEP 2 — what Ripple read.
Warnings first. Four editable cards: source system, change type, effective
date (with a badge saying how many days are left, amber inside three weeks),
and contact with the multi-address box. Subject and description. Then the
upstream tables and attributes, editable, with a live count. Say plainly
whether the fields were found by matching the catalogue or typed by hand, and
that the scan uses exactly what is on this screen, not the email.

That label has three values, not two: "Entered by you — no AI used" when the
change was typed in, "Read by AI — check it" when the AI read the email, and
"Found by matching the catalogue — check it" when it did not. They are three
different amounts of trust, and printing two of them as one hides which you got.
Say the same thing in the other three places it belongs. On step 1, a line under
the drop zone reading either "AI is on — the email is read by <model>" or "AI is
off — fields are found by matching the repository catalogue". On the summary
screen, either "Written by <model> from the findings — no code was sent to it"
or "Written from the findings without AI". And in the sidebar status block, a
dot and either "AI on" or "AI off — rules only", beside the repository dot and
the dialect dot.

STEP 3 — the repository.
Left: what is connected — the folder, the label, files indexed, statements
understood, and, ONLY when they are not zero, files never opened, files that
would not parse, and files in folders Ripple skips. "Files indexed 1,770" is
the number somebody reads to decide the whole folder was covered, so when it
was not, the rows saying otherwise sit directly underneath it.
Right: what kinds of file are in the index, counted; the file types Ripple does
NOT open with a count each, from unknown_ext, so the next unlisted extension is
visible instead of silent — nothing recorded those before, and a repository whose
pipeline is written in .ipynb or .tf files looked exactly like one with no
pipeline in it; a confirmation note with the branch and the file count; the never-opened note if there is one, saying
the number, why, and the one thing that fixes it; the skipped-folders note if
there is one; and the catalogue counts, which arrive from a separate request —
while waiting, say what it is waiting for rather than leaving a heading with
nothing under it.
A "Run impact analysis" button, disabled when nothing is indexed, and a
"Re-read the repository" button. The hint beside them says what the scan WILL
do, in the future tense — "The scan will search X" — never something that
reads as though it is already happening.
While reading, show the counted progress line: reading takes minutes on a real
repository, and saying "a few seconds" and then taking four minutes is how a
working program gets reported as hung.

Under those counts, when health.repo.runsSqlFrom is not zero, one line: that
many of these files run SQL that is kept in a separate .sql file rather than
written inside them, those .sql files were read on their own account, and any
that name a file which is not in this repository are listed as gaps after a
scan. A DAG that runs a query kept elsewhere holds no SQL of its own, so without
that line "Python · 240" reads as 240 files Ripple learned nothing from.

When the counts arrive, that card has four answers, and three of them are not
"all clear":
  Gaps in the catalogue — "N tables here have no column list written down", and
    then the part that matters: a scan still follows your attribute through
    these, because a SELECT * carries every column, so the trail does not stop
    here. What Ripple cannot do is name the columns inside them, so every step
    past one is marked on the result as worked out rather than read. This is a
    fact about how the code is written, not a gap in the scan. List each table
    with its reason.
  Under the two counts, when the catalogue's derived[] is not empty, one calm
    line: "N of these are built with SELECT * and have their column list read
    from the table they copy", with a chip per table reading "<table> ← <from>
    (N columns)". Without it the count reads as "N tables with a list, and the
    SELECT * ones unknown".
  No tables read at all — "No table definitions were read, so there is no
    catalogue to check." "Every table definition was readable" is technically
    true of nothing at all, and reads as a clean bill of health for a repository
    that was never read.
  Some files never opened — "Every table definition in the files that could be
    opened was readable. The files above were not opened, so nothing is known
    about them." It has to say which repository it means, or it sits in green
    directly under a warning that part of the folder went unread.
  Only when none of those apply — "Every table definition was readable."
````

**Check it worked.** Start it with `python run.py` and click through. You should be
able to walk from step 1 to step 3, and step 3 should show real counts from a real
folder. The "Run impact analysis" button will not do anything yet — that arrives in
the next phase.

---

# PHASE 11 — the screens: findings, map, summary, reply, settings

**Saves to:** the end of `ripple-build/web/app.js` — **append** it to what window
10 gave you, in the same file. Do not replace it and do not make a second script.

**Paste this into the chat.**
````text
[PASTE THE CONTRACT CARD FIRST]

Build the rest of web/app.js. It is appended to the part I already have, which
defines S, render(), el(), x(), api(), run(), and steps 1 to 3. End with the
boot block that fetches /api/health and renders.

STEP 4 — the findings. Order the page by importance, with a small heading
above each section.
  A card with what was read: the repository, and "N files read · M mention the
  names you confirmed". Real counts only.
  Under the heading "What the change reaches", five counted cards:
  production tables at risk, other tables reached, attributes impacted, files
  to change, breaking usages. The attributes card is labelled "Tables and
  attributes impacted" when stats.wholeTables is not zero.
  Under the heading "What this result does not cover", up to three: to check
  by hand, never opened, in folders Ripple skips — the last two only when they
  are not zero. When all are zero, say so positively in the space beside them.
  Then, BEFORE the findings, the never-opened card if there is one. It is the
  card that decides whether every number above it can be believed, and the
  bottom of a long page is where a caveat goes to be missed.
  Then the findings: one expanding card per published table, then the tables
  the chain ends at, then usages that build no table. Each card lists rows —
  table it lands in, attribute impacted, alias used, what the code does,
  value — expanding to a plain-English impact sentence and the real lines of
  code with the matching line marked and the reason on the line itself.
  Where a row's column is no longer what the person asked about, say "from
  MARKET_CODE" underneath it. A row with whole: true shows a navy "whole
  table" chip in the attribute cell, the words "every column" in the alias
  cell and a grey mode badge — never a blank cell, which reads as a value
  that failed to load. The line under the title, the risk badge and the
  "never met" note all have a whole-table wording ("Ripple never met this
  table", "Table not found — nothing was checked", "every statement that
  reads the table, and every table built from those") chosen when
  stats.wholeTables is not zero.

  EVERY LONG LIST FOLDS SHUT BY DEFAULT, AND THE HEADING STAYS. One helper,
  fold(label, head, body, opts) -> a card with a clickable heading row (a
  small-capitals tag, the heading, a count badge, the word "show" or "hide",
  a caret) and the list underneath only while open; foldFrom(label, card,
  opts) turns a card built heading-first into one. The heading IS the caveat
  — what the list is and how many are in it — so somebody who never opens it
  still sees everything Ripple knows it missed; the list is the evidence.
  opts.after is a node that stays visible whether or not the list is open,
  for a button that acts on the list. Open state lives in S.folds by label,
  so a redraw does not shut a list somebody just opened; the heading is
  reached by Tab and opened by Enter or Space. Fold: the never-opened file
  names, every card under FIVE CARDS UNDER THE FINDINGS below, the usages
  that build no table, the "N more tables" chips, the check-by-hand list, the
  mentions-only list, and "Every attribute you asked about" (which opens by
  itself when it holds a correction somebody has to see — a name never met or
  a trail cut short — or when there are three attributes or fewer). Tables
  that stop refreshing and deliveries out of the warehouse fold too, and open
  by themselves when they hold five or fewer. Measured on a real repository:
  the findings screen ran to forty thousand pixels, and every caveat on it
  was a heading over a list nobody could scroll past.
  Draw at most 20 cards. On a real repository a key column reaches over two
  hundred tables, and two hundred collapsed cards is a page nobody scrolls to
  the end of, so the tables at the bottom are in practice hidden. Nothing is
  dropped: they are sorted worst first, and every remaining table is named
  with its count in a scrollable list underneath, saying so.
  When nothing matched the published-table rule at all, say it in a warning
  above the list, quote the rule, and point at the settings screen.
  A green tick is ONLY shown when there is genuinely nothing — no production
  table, no other table, no loose usage anywhere. If no files were read at
  all, show a red note saying nothing was scanned, and never the tick.
  Under "How to check this result": every attribute asked about and what came
  back — used in N files, or named in N files and never read from, or this
  name is not in the repository at all. Then the check-by-hand list, giving
  the file, the reason, the LINE and the line itself, so somebody can open it
  at the right place. Where the same advice applies to more than one file, say
  it once at the top rather than under every entry — printed sixty-eight times
  it stops being advice and becomes wallpaper the eye skips, taking the file
  names with it. Then the files that mention the name but carry it nowhere.

  That panel carries more than three answers, and each one is a different
  answer. For every attribute, one badge, chosen in this order:

    reaches a published table               red,   when reachesProduction
    used in N files                         amber, when found is above zero
    Ripple never saw a column of this name  amber, when lookupFailed
    named in N files, never read from       grey,  when mentionedIn is above zero
    this name is not in the repository at all  grey

  Beside the badge, "ends at <tables>" from endsAt. Keep "still going at
  <tables>" from cutShortAt as a separate red badge: the two read the same and
  mean opposite things — one is where the code ran out, the other is where
  Ripple stopped looking.

  Then underneath, each only when it applies:
    cutShortAt has anything — Ripple follows maxHops renames and then stops,
      this trail had not finished, so whether it reaches a published table is
      not something this scan can tell you, and there is a button above to
      follow it further.
    notVisible has anything — the trail goes through those tables, every column
      carried on and none of them named, and <inferred> of the findings below
      sit past that point and are worked out rather than read.
    nameInTables is 8 or more AND is at least a quarter of tablesRead — say the
      name is a column in nameInTables of the tablesRead tables Ripple could
      read, that the findings follow it out of this one table only, so a long
      list here is the name being common rather than the change being bigger.
      Both conditions matter: "3 of the 3 tables" is a fact about a folder with
      three files in it, and printing it there teaches somebody to skip the line
      in the repository where it is the whole point.
    uncertain is above zero — say how many are on a line where the SQL did not
      say which table the column came from, that more than one table in that
      statement has one, and that they are marked "table not stated" below as
      real usages with the table inferred.

  After those lists, and before "How to check this result", two more sections.
  They are their own kind of impact and they get their own words.

  PUBLISHED TABLES THAT STOP BEING REFRESHED (stopsLoading). Heading: "N
  published tables stop being refreshed". A red-edged card that opens by saying
  it is NOT because a column of these changes — the change stops the statement
  that fills them from running at all, so they go on holding whatever they held
  yesterday. Nothing fails on the screen of whoever reads them; the numbers are
  simply out of date, and stay out of date until somebody fixes the job. Then
  one entry per table: a PRODUCTION TABLE badge and the table name, then
  "Because <because> stops loading. The path: <via, joined by arrows>". When
  stopsLoadingCapped is true, add a warning that the list was cut short after
  400 tables downstream, so there may be more than these — a list cut short
  without a word reads as "there were only these".
  Give it a counted card as well — "Published tables that stop refreshing", from
  stats.productionStopsLoading, sub-line "Their columns do not change — their
  data stops" — in "What the change reaches", second from the left. Never add it
  into "production tables at risk": one number covering two different kinds of
  impact is a number that means neither. Second from the left, not in a row of
  its own underneath: a grid of its own holding one card strands the most
  alarming number on the screen on a line by itself, looking like an
  afterthought. Order that row worst first — production tables at risk,
  published tables that stop refreshing, deliveries out of the warehouse, then
  the rest — so the card that wraps to a second line is the mildest one.

  There is a second green note on this screen and it has a rule of its own. The
  "Every file was opened and read — nothing was skipped, and nothing was left for
  a person to follow by hand" note may print only when EVERY gap is zero: no
  files to check by hand, no unopened file types, nothing else in the row beside
  it, and files actually read. Name each of those in the condition itself, not
  only in the row above it. A clean bill of health printed directly above a card
  saying a notebook was never looked inside is the tool contradicting itself on
  one screen — and the reader believes the green one.

  That row holds up to SIX cards, not three, and every one after the first is
  drawn only when its count is not zero:

    To check by hand           stats.couldNotRead — "Ripple could not follow these"
    Trails cut short           stats.trailsCutShort, in red — "Stopped at N renames deep"
    Tables not fully readable  stats.tablesNotVisible — the sub-line says which
                               kind, read off starTables[].how: "Copied whole, or
                               SELECT * — no column list" when there are both,
                               "Copied or renamed whole — no column list" when they
                               are all copies, "Built with SELECT * — no column
                               list" when they are all stars
    Never opened               stats.neverOpened, in red — "Not on this machine, or
                               path too long"
    In folders Ripple skips    health.repo.inSkippedDirs — the folder names
    Types Ripple does not open the counts in fileTypesUnopened added up — the
                               extensions

  Lay them out in the SAME grid as the row above — five columns, three below
  1500px, two below 900px — so a card is the same size wherever it sits and a
  short row leaves the rest of the row empty. A row with its own column count
  stretches two cards to half the page each while five narrow ones sit directly
  above them. A trail Ripple gave up on is not a trail that ended, and a table it
  cannot see inside is not a table it has read. Leave either off this row and a
  result built on half a picture looks, number for number, exactly like one
  built on the whole picture.

STEP 5 — the dependency map. A tab per attribute. The upstream source as a
dark card on the left, and to its right ONE TREE: branches that share their
first steps are drawn once, as one box with the paths that part from it drawn
underneath, indented and joined by a connector line. treeOf(branches) folds
the branches (a box is the same box when its table, its alias and its markers
are the same) and treeEl(tree) draws nested lists. A box shows the kind, the
table and the alias at that step; published tables are red; a leaf that is
not a published table is dashed and labelled "chain ends here", a published
leaf "published table". Measured before this on the practice pipeline: four
rows of three boxes, with the published table on every row cut off at the
right edge. Draw at most 60 branches into the tree, longest and
production-reaching first, and COUNT
THE REST OUT LOUD — every one of them is already a finding on the previous
step. A legend, and one line saying the alias is the rename a word search
would miss. The line under the title must be true of the picture underneath
it: if no branch reaches a published table, say so there.

Two things a box on this map can hide, and the box itself has to say them,
because a picture of a chain is exactly where somebody reads "and then it
stops". A box whose node carries inferred gets a line reading "<how> of a whole
table — column list not visible", or "built with SELECT * — column list not
visible" when there is no word to name. A box whose node carries cut gets a red
line: "Ripple stopped here — hop limit, not the end of the chain".
The line under the title has a third version. When no branch reaches a published
table but some were cut short, do not claim none of them reach one — say Ripple
stopped following that many branches at maxHops renames deep, so where they end
is not known.
When some branches end at a table that is not on the published list, say so in a
warning under the picture: they are drawn because the change reaches them either
way, and Ripple simply cannot say whether anyone outside your team reads them.
And when there is no lineage at all, the button under the picture writes the
summary itself rather than moving on a step. Sending somebody straight on leaves
the next screen with nothing to draw and two buttons that do nothing — which
only ever happens on a clean result, exactly when somebody most wants to get to
the reply.

FIVE CARDS UNDER THE FINDINGS, each one a thing Ripple could not see and each
one BESIDE the answer it qualifies. Every one of these was, at some point, a
warning that lived on another screen while a scan said "no impact":

There are more than five of these cards. This one comes first, before all the
others:

  Trails cut short by the hop limit (cutShort). Ripple follows a column through
  maxHops renames and then stops, and a trail that was still going when it
  stopped has not ended. Draw a red-edged card saying how many trails stopped
  because of a setting rather than because the code ran out, name each one as a
  chip reading "table · attribute", and say plainly that "does not reach a
  published table" is not something this result can tell you about them.
  Under it, when maxHops is below 25, a button reading "Follow these N renames
  deep instead", where N is maxHops doubled and capped at 25. It runs the same
  scan again by POSTing to /api/scan with an extra maxHops field. Say beside it
  that no files are read a second time and that it changes nothing on the
  settings screen — it applies to this one scan only.
  Without that button the only way past the limit is a setting on another screen
  that the person reading the answer has no reason to visit.

  Tables whose column list is not readable (starTables with known false). Say
  which kind each is — built with SELECT *, a whole table copied or renamed
  with COPY / CLONE / LIKE / RENAME, or a placeholder the job fills in at run
  time. Never describe a statement the file does not contain. Each chip says
  WHY the list is not there — "from <table>, whose own column list is not
  written down here", or "whose written column list has no <column> —
  followed anyway" from listedWithout — so nobody reads the card as Ripple
  having failed to read a file.
  Then, apart from those and calmly, the ones whose list Ripple COULD read
  (starTables with known true): "N tables built with SELECT * have a column
  list Ripple could read", each chip "<table> — every column of <from> (N
  columns, listed in <listedIn>)", and the explanation that the table copied
  has its columns written down, so the list was read from there and nothing
  past these tables is inferred.
  One name standing for more than one table (mergedNames).
  Tables read through a wildcard rather than by name (wildcardNames).
  Tables built from scratch in more than one file (twoDefinitions). Say that
  only one of them can be the one that runs and that nothing in the code says
  which, so the reader checks their scheduler before acting.
  Code files not read because of the folder they are in (skippedInFolders).
  Name the folders, and say that if the pipeline really runs from one of them
  the skip list on the settings screen can be changed.
  Tables named after their file rather than by the SQL (namedByFile). Say which
  tool names them, and that opening the file will show the query and not the
  name.

  Each entry says which of two reasons it is. When reason is "capitals", the
  chip reads "<spelling A>  vs  <spelling B> — same name, different capitals",
  and the card adds a line saying BigQuery treats capitals as significant, so
  two names differing only by case really are two tables there, and Ripple
  cannot tell whether that is what your code means or just how it was typed.
  Otherwise the chip reads "<table> — in <datasets>".
  Say that Ripple followed all of them, because missing a chain is worse than
  showing a row you can dismiss by opening the file, and that findings under
  these names may be about either table, so check before acting on one.

  File types Ripple does not open (fileTypesUnopened). The repository screen
  already counts these; the ANSWER has to as well. Ripple opens SQL and the file
  types that normally hold SQL, and if the chain passes through a notebook or a
  Terraform file the answer stops there and says so nowhere else. Draw an
  amber-edged card: "N files are of a type Ripple does not open", that sentence,
  and a chip per type reading "<extension> — <count>", up to forty of them, with
  "no extension" for files that have none. Notebooks and Terraform files are the
  usual ones to check. A caveat may never live on a different screen from the
  answer it qualifies.

AND ONE SENTENCE UNDER THE FILE COUNT, on every scan, that qualifies every other
sentence on the screen: Ripple read these N files and nothing else, so "no
impact" means "nothing in this repository", not "nothing anywhere" — a job in
another repository, a scheduled query, or a dashboard built straight on the
table is outside what it can see. That is the single commonest way to be wrong
with this tool.

STEP 6 — the summary. The headline with a risk badge, the narrative, the
bullets, and the change details. A right-hand rail with the deadline and days
left, a blast-radius count, and what to do. Then the check-by-hand list again,
because this is the screen people read. A save button, and when saved, say so
with the number it was saved as.

Before any of that: if this screen is ever reached without a summary, say so and
offer the one button that fixes it — the summary is written from the findings
when you leave the dependency map, and it has not been written for this scan. A
screen with nothing on it and two buttons that do nothing is the worst way to
say that.
And where "saved" does not really mean saved, say it in the same breath. When
the health limits report that saved analyses are not kept, the line beside the
save button adds that this host wipes them and anything worth keeping should be
copied out. Keep it to one short line — it sits between two buttons, and the
full explanation belongs on the past-analyses screen.

STEP 7 — the reply. Editable subject and body. The recipients as separate
chips, one per address, so a list of four is not one unreadable string hiding
a typo. Copy takes the recipients with it — copying a reply and then having to
gather the addresses again by hand is half a job. Nothing on this screen sends
anything, and nothing pretends to.

PAST ANALYSES — a table of what was saved, newest first, with an editable
status.

SETTINGS — and the published-tables control is the whole point of it.
Build it as one function used by the whole app:
  a big multi-line box, monospace, resizable, holding the list exactly as it
  was pasted — a single-line input is the wrong control for two hundred names
  as it is checked, with a 600ms pause, by POSTing to /api/production/read.
  Never re-render the page on the answer, or the cursor leaves the box.
  Underneath, in this order:
    how many table names and how many patterns were read, then every entry as
    a chip in a scrollable box, with patterns outlined differently and one
    line saying which is which
    what was left out of the paste and why, with examples
    then the important one, in red: "N of the M tables on this list are not in
    this repository", with the reason it matters — either the name is spelled
    differently here, or the table is built somewhere Ripple could not read,
    and until that is settled a clean result for those tables means nothing.
    Group them: not written anywhere in this repository, and the name is here
    but nothing readable builds it. Two different places to go and look.
    If a name matches nothing but IS the ending of tables that exist, ask
    whether it was meant as a pattern and show how to write it. Do not decide.
    Then, for each pattern, how many tables here it matches — and a warning
    when a pattern matches none, because it is doing nothing at all.
  A save button, and a line saying plainly where the list is kept and whether
  it survives a restart.
The rest of the settings screen: what is connected, and a note explaining that
this one setting decides whether "no production table is impacted" is a result
or an accident.

THE FOLDER BOX, and it is the difference between a demo and a tool. Under the
Repository facts, a single-line box holding the folder Ripple is reading now,
and a button that says "Read this folder". It POSTs to /api/repo/folder and
repaints from the health block that comes back.

  Without it, the only way to point Ripple at real SQL is to set RIPPLE_REPO and
  restart it. On a laptop that is not a way of choosing anything, and until
  somebody does it every answer describes the practice pipeline — confidently,
  correctly, and about nothing anybody cares about.

  Under the button, one plain line: the choice is held only while Ripple is
  running, and RIPPLE_REPO is what keeps it. There is nowhere for this build to
  write it down. Saying nothing lets somebody believe tomorrow's Ripple will
  still be reading their folder.

  On success, CLEAR ANY RESULT ON SCREEN — the scan and the summary both. A
  finding left up after the folder changes looks entirely right and is about a
  repository nobody is reading any more. Say so in the confirmation: how many
  files were read, and that the earlier result was cleared and why.

  On failure, show the reason where the button is and change nothing else. The
  folder in force must still be the one that was working.

  Two more states that box can be in, and both change what a scan means:
    Nothing in the paste was read as a table name — say so in red, and say what
    happens next: Ripple falls back to its own guess, names ending _PROD, _PRD
    or _PUBLISHED, which is almost certainly not how your tables are named.
    Paste the list again, one table per line.
    Nothing has been read from a repository yet — say the list has not been
    checked against one, that Ripple cannot say whether these tables exist, and
    send the reader to choose the repository first. A missing-table count of
    zero because nothing was checked reads exactly like a list that all matched.
  Check the list already in force the moment the screen opens, rather than
  waiting for somebody to touch the box. A rule that matches nothing is worth
  knowing about before it is edited, not after.

THE AI KEY BOX. Three providers — OpenAI, Google Gemini and Groq — and ONE
box, not three. Which company issued a key is worked out from the key itself,
from its first few characters. Asking is one more thing to get wrong, and a key
sent to the wrong company comes back rejected, which reads as "your key is bad"
when it is not.

All three speak the same OpenAI-shaped POST /chat/completions, so there is one
code path and only the address, the key and the model change. Google's own
OpenAI-compatible endpoint is at
https://generativelanguage.googleapis.com/v1beta/openai — confirmed live with a
deliberately wrong key rather than taken from documentation.

Four things this must get right:

* An Anthropic key begins "sk-" exactly as an OpenAI one does. Match the
  LONGEST prefix, and keep a list of keys you recognise but cannot use so the
  screen can say "that is an Anthropic key" instead of "rejected".
* Google answers a bad key with 400 and "Please pass a valid API key", not 401.
  Read as a bad request that sends somebody to check their prompt rather than
  their key.
* DO NOT WRITE A LIST OF MODEL NAMES INTO THE CODE. It is wrong within months
  and then offers a model that no longer exists, discovered at the moment
  somebody is trying to read an email. Ask the provider — GET /models with the
  key — which proves the key and produces the real list in the same call. Keep
  a preference ORDER for choosing a default, filter out the models that cannot
  hold a conversation (embeddings, audio, images), and keep every other one:
  hiding a model somebody is paying for because you have not heard of it is the
  worse mistake.
* Not every provider accepts every optional field of an OpenAI-shaped request.
  If one refuses response_format, send the request again without it rather than
  losing the whole call — the prompt asks for JSON in words as well.

The screen reads the prefixes from the server so there is ONE list of them, and
names the provider as the key is typed, before anything is sent anywhere.

Also on the settings screen: a card saying WHICH BUILD IS RUNNING, from the
`build` block of /api/health — the version, the commit if there is one, and the
date. Underneath it, one line saying where that came from: read from the
repository, recorded when the copy was packaged, reported by the host, or — when
nothing better was found — the date of the newest file in the folder. That last
one must say out loud that it is a guess. A file date moves whenever anything is
touched and proves nothing about what anybody installed, and a guess that looks
like a fact is worse than no line.

Write this card once, as shared code, and call it from every edition's settings
screen. It exists because the copy nobody can check is exactly the one that
turns out to be months old, and putting it only on the screen you happen to be
looking at is how the half-shipped fix happens.

The card is headed "This build" and shows the label exactly as the server sends
it. Do not re-format the date or re-join the parts in the page: one place
decides how honest that line is, and it is the server.

The server sends one of exactly four words in "from", and the small line under
the label is chosen from them:

    build   Recorded when this copy was packaged.
    host    Reported by the host that deployed it.
    git     Read from the repository this copy is running out of.
    files   No build record was found, so that is the date of the newest file
            in this folder. It moves whenever anything is touched, and it does
            not tell you whether this copy was ever installed anywhere.

If /api/health carries no build block at all, draw no card rather than an empty
one.

THE CARDS THAT QUALIFY THE ANSWER

These sit BESIDE the findings, never on another screen. A caveat one click away
from the answer it qualifies is a caveat nobody reads.

* **Where Ripple could not see through** — the coverage counts, at the top of
  "how to check this result", plus a second badge next to the risk word reading
  either "whole trail seen" or "N gaps in what Ripple could see". Put no count
  in that heading: it would be counting KINDS of gap, above lines that count
  files and findings, so "1 place ... 3 files" reads as two numbers for one
  thing. Write every one of those lines twice, for one and for many. Printed
  plural-only they read "1 findings are on a line" and "1 trails were still
  going", which is how a careful tool sounds careless on the one screen where
  care is what it is selling.
* **Column not found** — when lookupFailed, the headline badge reads "Column not
  found — nothing was checked" instead of a risk word, and the attribute panel
  prints back the columns Ripple DID read on that table.
* **Deliveries out of the warehouse** — the feeds, with their own stat card.
  Never folded into "production tables at risk".
* **N places name this, and carry it nowhere** — the referencedHere list, with
  the table, the columns named, and the file and line.
* **N statements are written as text and run** — the builtAsText list, and a
  "run as text" badge on every row that came out of one, because the code shown
  underneath such a row is a quoted string and looks nothing like the statement
  the row describes.
* **The wildcard card** gains a warning when any pattern matched only the family
  name without its separator: BigQuery would match nothing there, so every row
  from it is marked "table not stated".

  That card has two shapes and only two. When coverage.complete: one paragraph
  saying every step of every trail above was read out of the SQL, no file that
  mentions these names went unread, no table on the way was built with a
  SELECT *, no trail was still going when Ripple stopped, and nothing below is
  worked out rather than read — then the sentence that keeps it honest, that
  this is true of these N files and of nothing outside them.
  Otherwise: one line saying the answer above rests on these, that each is a
  place Ripple could not see through, and that they are listed as counts rather
  than as a score because there is no honest way to say what share of the whole
  trail they are. Then print coverage.gaps straight through — the count in bold
  and its words beside it.
  Never a percentage, never a bar, never a score out of ten. There is no honest
  denominator for "how much of a trail exists", and a precise-looking number on
  a guess is the one thing this tool may not do.

  That badge is not drawn at all when no files were read, or when lookupFailed.
  "Whole trail seen" is true, and reads as a reassurance, over a scan that
  followed no trail at all because the column it was given is not in this
  repository — and over a scan of an empty folder. For the same reason the
  coverage card itself is not drawn when lookupFailed: "every step of every
  trail was read" over a trail that does not exist is the same reassuring
  nonsense in longer words.
  The headline badge replaces the risk word twice, for the same reason: "Nothing
  was scanned", in amber, when filesScanned is zero; "Column not found — nothing
  was checked", in amber, when lookupFailed.
  The line under the step 4 title has to be true of the screen under it as well,
  so it has three versions: when lookupFailed, "Ripple never met these column
  names. Check the spelling before reading anything below."; when there are
  production groups, "Every finding grouped under the production table it puts
  at risk."; when there are none but tables were reached, "Nothing matched your
  published-table rule. Every table the change does reach is below."

  Three badges sit inside the same cell as the "what the code does" badge, so a
  row that has them still lines up with the rows that do not:

    table not stated        grey,  when the finding's certain is false
    column list not visible amber, when inferredHops is set and viaStar is true
    inferred                amber, when inferredHops is set without viaStar
    SELECT * — column list known   grey, when starKnown is true
    run as text             amber, when builtAsText is set

  Each opens into its own note when the row is expanded:
    table not stated — the usage is on that line and it is real; what is
      inferred is which table the column came from. Say the statement reads more
      than one table with a column of that name, that the SQL does not say
      which, which one Ripple has counted it as, and that the code below is
      worth a look before acting on it. In a warehouse where the same key
      columns sit in nearly every table, that is worth stating rather than
      glossing.
    column list not visible — the statement takes every column, so the attribute
      is carried into the next table without ever being named. The hop is real;
      what Ripple cannot promise is that the column still carries that name by
      the time it lands.
    run as text — the line below holds the statement as a quoted string, so the
      code shown is the string rather than the statement. Ripple read what is
      inside the quotes and it is complete SQL, which is why the row exists;
      anything added to that text when the job runs is not covered here.

  Give the expanded row's opening note three states, not two: red when
  noLocalFix, reading "No local fix — the upstream team must supply a
  replacement"; amber when breaking, "This breaks"; blue otherwise, "Changes,
  but does not break".

  What that section holds: the heading "N deliveries out of the warehouse", then
  a red-edged card opening with "These are not tables" — the statement writes a
  file to a bucket, whoever reads that file is outside this repository, so
  nothing Ripple can scan will tell you who they are, and they have to be told
  before the change ships. Then one entry per delivery: a DELIVERY BREAKS or
  DELIVERY CHANGES badge, the destination or "destination not written down", and
  a line reading "Carries <attributes> out of <from> · file:line".
  Its counted card sits in the same second row as the stop-refreshing one, from
  stats.feedsBroken, sub-line "Files another team reads — tell them".
  On the "usages that build no table" panel, any row carrying a feed gets a red
  "→ destination" badge, and the paragraph above it says how many of those
  usages deliver a file out of the warehouse instead. Without that, the
  paragraph tells somebody the destination is somewhere Ripple cannot see, two
  paragraphs above the card that names it.
````

**Check the file itself first.** This window and Phase 10 both wrote into
`web/app.js`, so before you look at any screen, check that the file still reads
as one whole program. Go to the black Command Prompt window, and from
`C:\ripple-build`:

**Type this into the black window.**
```
node --check web/app.js
```

**No output at all is the pass.** It is the only check in this kit that catches
a missing bracket before the browser does, and a missing bracket leaves every
single screen blank — which looks exactly like the whole build being broken. If
the window answers that `node` is not recognised, Node is not on this machine:
skip this and use the browser instead. Open the page, press F12, click the
Console tab, and look for one red line on load.

**Check it worked:** run a scan against a real folder and click through all seven
steps. Then paste a deliberately messy list into the settings box — with a typo
in it — and confirm the typo comes back named.

---

# PHASE 12 — starting it up, and the checklist

Nothing to prompt here. This is you, checking.

**Set aside an hour for this part.** The block below comes back as 20-25 small
files and you save every one of them by hand, with the same two commands as
always: `type nul >` the full path, then `notepad` the same path, paste, Ctrl+S,
close. There is no faster way, and this is the last long stretch of saving in the
kit. The SAVE THESE FILES block at the end of the reply is your list — tick them
off as you go, because half a pipeline tests nothing.

**Make a tiny fake pipeline to test against.** Ask any window for it:

**Paste this into the chat.**
````text
[PASTE THE CONTRACT CARD FIRST]

Write me the contents of ripple-build/mockrepo/ : a small fake pipeline, 20-25
files, using only invented table and column names. It must contain, on
purpose:
  a source table definition and a couple of tables built from it
  a column renamed twice down a chain, ending at a table called
    something_prod so the default published rule matches it
  a chain ending at a table that does NOT match the published rule
  a join on a column of the same name in two different tables
  a window ORDER BY on the column, so there is a ranking with no local fix
  a filter comparing the column to a literal
  a Python job holding SQL in a triple-quoted string
  a Python job that names a .sql file which does NOT exist in the folder
  a file with a deliberate syntax error
  a file where the column name appears only as a quoted string in a call
  a BigQuery-shaped file wrapped in BEGIN ... EXCEPTION ... RAISE ... END
  a CREATE TABLE built with SELECT *
Give me every file complete, and end with the SAVE THESE FILES block giving
the full path of each one under ripple-build/mockrepo/.

THEN, LAST OF ALL, under a heading THE NAMES I WILL NEED, list in plain text:
  the exact column name I should scan for, spelled as it is in the source table
  the upstream table that column starts in
  the published table the chain should reach
  the table the chain ends at that is NOT on the published list
  the file with the deliberate syntax error
  the file where the column name is only a quoted string
  the Python job that names a .sql file which is not there
  the full list of published table names, one per line, ready to paste
I am going to type these into a checklist by hand. I cannot read your files and
I have no way of knowing what you called anything.
````

**Then run everything.** First the whole test suite, from `C:\ripple-build`:

**Type this into the black window.**
```
python -m pytest -q
```

Then start it, and this time let it open the browser, because every line of the
checklist is something to look at on screen:

**Type this into the black window.**
```
python run.py
```

**Point Ripple at the practice pipeline first.** Every line below is about the
fake pipeline you just made, and Ripple may well still be reading the real folder
you tried in Phase 10. If it is, every check fails for a reason that has nothing
to do with your build, and you will spend the evening re-prompting windows that
were never wrong. Go to **Settings & checks**, find the folder box under the
repository facts, and put this in it:

**Type this into the black window.**
```
C:\ripple-build\mockrepo
```

Press **Read this folder**. The line underneath tells you how many files it read
and that the old result was cleared. When you have finished the checklist, put
your real folder back the same way.

**And this is how you run a scan**, because most of the lines below start with
one. On step 1 choose *entered by hand*. Put the upstream table in a row and the
column name in the box beside it. Go on to step 3, and press **Run impact
analysis**. The names to type are the ones the chat listed for you under THE
NAMES I WILL NEED — keep that reply open in the other window while you work.

**The checklist. Each line is one thing to look at on screen.**

1. The repository screen shows a real file count, and if any file was never
   opened or would not parse, a row underneath saying so.
2. A scan of the renamed column reaches the published table three hops away.
3. Scroll further down that same findings screen, past the cards for the
   published table. The chain that ends somewhere NOT on the published list has a
   card of its own, with its table named on it and the reason underneath in
   words: "Last table in the chain - not matched by your production naming
   rule". Open that card: it must hold the same rows, files, lines and code as
   the published one. A bare table name with nothing under it is a fail, and so
   is the chain being missing altogether.
4. The file with the syntax error is on the check-by-hand list, with its line
   number and the line itself.
5. The file where the name is only a quoted string is on that list too, and
   says how many lines of it do that.
6. On the findings screen, under the heading **"What this result does not
   cover"**, open the **To check by hand** list. The Python job that names a .sql
   file which is not in the folder must be in that list, with words like "runs
   the SQL in ..., which is not in this repository". A query nobody has ever read
   is not a query with no impact, so if that job is missing from the list, that
   is a fail.
7. Scan for a column name you have invented. On step 1, in the row where you
   typed the upstream table, put `zzz_not_a_column` instead of the real column,
   and run it. Two things to look at, and both must be right. The badge at the
   top of the findings, where the risk word normally sits, must read **"Column
   not found — nothing was checked"**. Then click on to the reply and read it: it
   must ask the other team to confirm the column name, and the words "no impact"
   and "proceed as planned" must not be anywhere in it. A reply may say no impact
   **only** when nothing at all was left unread, and this pipeline has a file
   Ripple cannot parse in it on purpose. A clean, confident answer here is a
   fail.
8. Make yourself an empty folder — in the black window, `mkdir
   C:\ripple-build\emptyfolder` — then put `C:\ripple-build\emptyfolder` in the
   folder box on **Settings & checks** and press **Read this folder**. The line
   underneath should say it read 0 files, and back on the repository screen the
   **Run impact analysis** button should be greyed out and refuse to be clicked.
   That greyed-out button IS the pass: it is the tool declining to answer a
   question about nothing. If your build does let you scan, the badge at the top
   must read **"Nothing was scanned"**. Either way there must be no green tick
   anywhere on the screen. Point Ripple back at `C:\ripple-build\mockrepo`
   afterwards.
9. Paste a list of published tables with one deliberate typo: the typo comes
   back named as not in the repository.
10. Go to **Settings & checks** and paste two columns into the big
    published-tables box: the published table names under a heading `Table name`,
    and anything you like beside them under a heading `Owner`. Under the box, a
    note must come back saying the paste had two columns, naming the one Ripple
    read — the one headed "Table name" — and saying it ignored the other. If
    nothing on screen mentions the second column, that is a fail: which column
    got read is what decides whether "no production table is impacted" is a
    result or an accident.
11. Long table names must not break the layout — and you do not rename anything
    by hand. Do this one last. Go back to the window that wrote the fake
    pipeline and paste: *"Give me three more files for ripple-build/mockrepo: a
    source table and two tables built from it, carrying the same column as the
    rest of the pipeline, where every table name is exactly forty characters
    long. End with the SAVE THESE FILES block."* Save those three the same way,
    press **Read this folder** again, and scan the column. The long names show up
    on the findings screen and on the map, and neither one scrolls sideways.
12. Save an analysis, reopen Past analyses, and change its status.

If 3, 5, 7, 8 or 9 fails, the honesty half has not been built and the tool will
give you a confident wrong answer on your real code. Do not carry on, and do not
try to word the complaint yourself. Go back to the window named under each one,
paste the block, and ask for the file again. If you have closed that window, open
a fresh one, paste the contract card, then the block.

**If 3 fails — window 11, the screens.** If window 11 says it is already drawing
everything it was given, paste the same block into window 5, which is what
produces the list.

**Paste this into the chat.**
````text
On the findings screen, the tables a chain ends at that are NOT on my published
list are missing, or they are shown as bare table names with nothing under them.

reached[] gets the SAME card as groups[]: the full rows, every finding, file,
line, code snippet and impact sentence, each card carrying its own note in words
-- "Last table in the chain - not matched by your production naming rule".

A list of bare names is not keeping them: it tells somebody six tables are hit
and nothing whatever about how. A real breaking impact shown as a clean result
because the tables are not named _PROD is the exact failure this tool exists to
prevent.

Give me the file again.
````

**If 5 fails — window 5, the scan.**

**Paste this into the chat.**
````text
A file that names my column only inside a quoted string is not on the
check-by-hand list, or it is on the list with no count of how many lines do it.

Test in this order and no other: the quoted string FIRST, then the file that
would not parse, and only then mentionsOnly. mentionsOnly is the reassuring case
-- "the name appears but carries nowhere" -- so anything that lands there by
mistake is a warning turned into a comfort.

Count how many LINES of the file name it as text, not merely whether any line
does, and report it even in a file that already has findings, saying so
explicitly: fixing the findings does not fix the text, which still says the old
name.

Give me the file again.
````

**If 7 fails — window 7, the summary and the reply.**

**Paste this into the chat.**
````text
I scanned for a column that is not in this repository at all, and the drafted
reply came back saying no impact.

lookupFailed gets its own branch, before anything else. The question was not
answered, so the letter asks the upstream team to confirm the column name and
reports no impact either way. The words "no impact" and "proceed as planned" may
not appear in it.

Add the tests that catch this: no impact is never claimed over a scan that read
nothing, and never over files that could not be read -- check the headline AND
the reply body.

Give me the file again.
````

**If 8 fails — window 11, the screens.**

**Paste this into the chat.**
````text
I pointed Ripple at an empty folder and scanned. The screen showed a green tick,
or a risk word.

When no files were read, the headline badge reads "Nothing was scanned", in
amber, in place of the risk word, and the green tick is not drawn at all. The
coverage badge is not drawn either: "whole trail seen" over a folder with nothing
in it reads as a reassurance about a trail that was never followed.

Give me the file again.
````

**If 9 fails — window 11, the settings screen.**

**Paste this into the chat.**
````text
I pasted a published-table list with a deliberate typo in it and the settings
screen said nothing about it.

Under the box, in red: "N of the M tables on this list are not in this
repository", with the reason it matters -- either the name is spelled differently
here, or the table is built somewhere Ripple could not read -- and until that is
settled a clean result for those tables means nothing. Group them: not written
anywhere in this repository, and the name is here but nothing readable builds it.
Two different places to go and look.

Give me the file again.
````

---

## Starting it with a double-click

Once it all works you will not want to open a Command Prompt every time. Two
commands, once:

**Type this into the black window.**
```
type nul > C:\ripple-build\start-ripple.bat
```

```
notepad C:\ripple-build\start-ripple.bat
```

Put this in it, save, and close:

**Paste this into Notepad and save it.**
```
@echo off
cd /d "%~dp0"

REM Windows can answer to "python" more than once, and only the one
REM Ripple's packages were installed into can start it. Ask each.
set "PY="
for %%P in ("python" "py -3.12" "py -3" "py") do (
  if not defined PY (
    %%~P -c "import uvicorn, fastapi, sqlglot" >nul 2>nul && set "PY=%%~P"
  )
)

if not defined PY goto nothing_installed

echo Starting Ripple. It prints the address to open, and opens your browser.
echo Leave this window open. Closing it stops Ripple.
echo.
%PY% run.py
if errorlevel 1 pause
exit /b

:nothing_installed
echo.
echo Ripple's building blocks are not installed on this machine yet.
echo Nothing is broken - this is the one step that has to happen first.
echo.
echo Open a Command Prompt, run the line below, then double-click this again:
echo.
echo     python -m pip install --user -r "%~dp0requirements.txt"
echo.
pause
exit /b 1
```

Now double-clicking **start-ripple.bat** starts Ripple and opens the browser. To
have it on your desktop, right-click it and choose *Send to → Desktop (create
shortcut)*. To stop Ripple, close the black window that opened with it.

**Why it is not just two lines.** It nearly was: move to the folder, then
`python run.py`. That trusts the word `python` to mean the Python you installed
the packages into — and on Windows that is not safe. Measured on 27 Aug 2026,
one ordinary laptop answered to `python` three separate times: a real 3.12 with
the packages in it, a shim for a 3.14 that had none, and a zero-byte Microsoft
Store stub that is not Python at all. Which one a double-click reaches depends
on the order of a setting most people have never opened.

It reached a wrong one, and what came up was seven lines of Python traceback
ending in `ModuleNotFoundError: No module named 'uvicorn'`. Nothing was broken
and nothing in that message said so.

So the batch file asks each candidate whether it can actually load Ripple's
packages, and uses the first one that can. It asks each of them quietly, so the
ones that cannot answer never print anything at you. If none can, it says the one
line to run instead of showing a traceback —
because the person reading it may not write code, and "not installed yet" and
"broken" have to look different.

The rest is small. `@echo off` stops the window printing each command back at
you. `cd /d "%~dp0"` moves to the folder the batch file is sitting in, so you
can move or rename the whole folder and it still works, where a written-out
path would break. `if errorlevel 1 pause` keeps the window open when something
did go wrong, so you can read it instead of watching it vanish.

**This is where most people should stop.** The batch file gives you the
double-click, and Ripple is finished. There is one more phase below that turns
the folder into a single program for a machine with no Python on it at all.
Whether to do it is a real decision, and Phase 13 opens by laying out both
sides — on a managed laptop, a program you built yourself that then opens a
network port is the shape endpoint security likes least.

---

# PHASE 13 — packaging it as a program

**This phase is optional, and skipping it is a fair choice.** Ripple is finished
without it. Do this phase only if you have to hand Ripple to somebody whose
machine has no Python on it and who is not allowed to install any. If everyone
who needs it can run `python run.py`, the batch file above is the better answer,
for one reason: on a managed laptop, a program you built yourself that then opens
a network port is the shape endpoint security likes least. It tends to be
quarantined, and explaining it afterwards costs more time than the packaging ever
saved. Nothing later in this kit depends on this phase.

**Saves to:** `C:\ripple-build\build.py` (new). Nothing else changes — Phases 1
and 8 already wrote the three things a packaged program needs.

**What you get.** A folder called `Ripple` holding `Ripple.exe` and one other
folder, about 40 MB in total. Copy that folder anywhere, double-click the program,
and Ripple starts and opens the browser — on a machine with no Python on it and
nothing installed. Packaging takes about a minute and a half each time.

**About the thousands of files in that other folder.** Open it and you will find
roughly 1,770 files. **You do not write any of them, and you never look at them
again.** They are put there by the packaging tool, every time, in about ninety
seconds. Counted on a real build:

| How many | What it is |
|---|---|
| ~923 | Python's own windowing library — it draws the "choose a folder" box and the error box |
| ~605 | a timezone database, dragged in by the Outlook-email reader |
| ~89 | the Outlook `.msg` reader |
| ~72 | the SQL parser |
| ~60 | Python itself, its standard library, and Windows DLLs |
| ~20 | Ripple's own screens |

**Not one of them is a file you typed.** Ripple's own Python — every phase in
this kit — is compiled and tucked inside the `.exe` itself, which is why you
cannot see it in there. The proof, if you want it: delete the whole output
folder and run `build.py` again. The same 1,770 files come back.

So the question "do I really have to write all that?" has a short answer: no.
You write about thirty Python files across the phases below. The packaging tool
supplies the rest, and re-supplies it every time you build.


**First, add the packaging tool.** One more install, and only on the machine that
does the building:

**Type this into the black window.**
```
python -m pip install --user pyinstaller
```

**Why this is one short phase.** A packaged program has no folder of source files
around it, so anything that goes looking for a file has to ask where it is rather
than assume. There are three such places in Ripple and all three fail *silently* —
the program starts, looks healthy, and is wrong. They were dealt with when the
files were first written: `paths.py` in Phase 1 answers where the front end and the
database live, and `run.py` in Phase 8 hands uvicorn the app object rather than its
name. So nothing here goes back and edits anything. If any of that was skipped, go
back and fix it there rather than patching it now, or Phase 13 will appear to work
and the program will not.

**Paste this into the chat.**
````text
[PASTE THE CONTRACT CARD FIRST]

Ripple works when I run it with python run.py. Package it as a Windows program
with PyInstaller so it runs on a machine with no Python installed.

ripple/paths.py already answers where the front end and the database live when
running packaged, and run.py already passes uvicorn the app object rather than
the string "ripple.api:app". Do not change either. Do not change any other
file. I want build.py and nothing else.

--- build.py  (new, at the project root)

Run with: python build.py
It says what it is doing, runs PyInstaller, then checks the result itself.

Use exactly these arguments. Every one is here because leaving it out
produces a program that builds cleanly and then misbehaves:

  sys.executable, "-m", "PyInstaller", "run.py",
  "--name", "Ripple",
  "--noconfirm", "--clean",
  "--onedir",
  "--console",
  "--add-data", f"{WEB}{os.pathsep}web",
  "--collect-all", "sqlglot",
  "--collect-all", "extract_msg",

  --onedir, not --onefile. A one-file build unpacks itself into a temporary
    folder on every single launch, which makes it slow to start, and a
    locked-down Windows machine often refuses to run a program out of a
    temporary folder at all.
  --console for now. It leaves a plain window open beside the app showing the
    address, and showing the error if there is one. Put a line at the end of
    build.py saying that switching it to --noconsole gives a cleaner program
    once everything works, so I can find it again later.
  WEB MUST BE AN ABSOLUTE PATH. Build it as
    Path(__file__).resolve().parent / "web" and pass that. A relative "web"
    gets resolved against PyInstaller's own working folder rather than mine,
    and the build stops with "Unable to find ... web", which reads as a
    missing folder rather than a wrong path.
  --collect-all for both of those two. Each loads parts of itself by name at
    run time, which PyInstaller cannot see by reading the code. Without this
    they are silently left out and the program fails the first time it reads
    any SQL -- long after the build said it succeeded.

And do not commit it. Git keeps every version of every file for ever, which is
the exact opposite of "keep only the latest": forty builds of a 22 MB zip WERE
the whole repository, and a fresh clone paid for all forty. Write it into the
ignored dist/ folder and publish it to the releases page, keeping only the
newest one there. Ripple itself does this in the cloud: a version tag runs
both test suites, builds the zip, starts the built program and drives it
through its own API, and only then publishes it. A build nobody watched is a
download nobody can trust, so "it built" is never the last step — "it ran, and
answered the questions this commit says it answers" is.

NAME WHAT YOU PRODUCE FOR ITS VERSION, AND STAMP IT. Both halves already exist
in ripple/build_info.py from Phase 8. Do not re-invent either here.

  Read VERSION out of ripple/build_info.py. The zip is called
  Ripple-v1.5.0.zip when VERSION is "1.5.0", the release is tagged v1.5.0, and
  the settings screen says Version 1.5.0 -- three things that can never
  disagree because they are one thing. A file called dist.zip is the same name
  for ever, so nobody can tell which build they downloaded.

  Call write_stamp() from that same file, pointing at the packaged folder.
  Nothing inside a packaged folder can work out which build it is on its own:
  a program has no git, and the file dates in there are the dates the files
  were copied -- true, useless, and impossible to tell apart from a real build
  date. The file it writes is called BUILD-STAMP.json and it holds exactly
  three keys: version, commit, built. Write a different name, or a key called
  "date" instead of "built", and the running program finds nothing, says
  nothing about it, and falls back to that file-date guess -- so the copy you
  just packaged shows a date that only records when files were copied, on a
  screen whose whole job is to tell an old copy from a new one.

  Then have build.py confirm the stamp is sitting beside the program and names
  a real date, as one of the checks it makes on its own work.

Then have build.py CHECK ITS OWN WORK rather than trust PyInstaller's exit
code:
  confirm dist/Ripple/Ripple.exe is really there
  confirm the build stamp is beside it and names a real date
  confirm the web folder was bundled, by finding index.html inside
    dist/Ripple/_internal/web
  print the total size of dist/Ripple in MB, and the full path to the .exe
  if PyInstaller failed, print the LAST part of its output, not a bare
    "failed" -- the real reason is usually the last three lines of a very
    long message, and the first three thousand lines are noise

Two things to guard, because both cost an evening:
  Rebuilding deletes the dist folder, and once the program has been run the
  history database is living in it. Before deleting, check for that database
  and if it exists and is not empty, say so and ask me to confirm rather than
  destroying saved analyses without a word.
  Windows will not delete a folder something is sitting in -- the last build
  still running, or a terminal whose current folder is inside it. PyInstaller
  fails there with a wall of traceback ending in WinError 32, which says none
  of that. Catch it and say it in plain words.

Python 3.10. Standard library only in build.py itself.
````

**Check it worked.** From `C:\ripple-build`:

**Type this into the black window.**
```
python build.py
```

It takes a minute or two and ends by naming the folder it made. Then go to that
folder and double-click **Ripple.exe**. The browser should open on the same Ripple
you have been using. Walk one scan through it end to end — that is the only proof
that matters, because everything in this phase fails quietly rather than loudly.

Three things to check specifically, since these are the ones that break silently:

1. **The page is styled**, not blank and not plain text. Blank means the front end
   did not come along.
2. **Run a scan.** If it reports that it could not read any SQL, the parser was
   left out of the package.
3. **Save an analysis, close the program, open it again, and look at Past
   analyses.** Your saved analysis should still be there, and there should be a
   file next to `Ripple.exe` holding it.

**If Windows blocks it or quietly deletes it.** An unsigned program built on the
spot, which then opens a network port, is a shape that endpoint security is
designed to be suspicious of. If it is quarantined, that is not a bug in your
build, and the fix is not a setting you should go hunting for on your own — it is
a conversation with whoever runs security, who can allow it properly. Ripple runs
perfectly well as `python run.py` in the meantime.

---

## When the chat goes wrong

**It gives you a shorter, "simpler" version.** Reply: *"That drops the case where
X. Put it back and keep everything in the contract card."* Chats optimise for a
tidy answer; the messy cases are the product.

**It invents a name that does not match the contract.** Reply with the exact line
from the contract card. Do not accept "this is equivalent" — window 9 will not
know.

**It truncates.** Ask for the file in labelled parts, and ask it to tell you the
total line count first so you know when you have all of it.

**It writes a progress bar, a percentage, or a fake count.** Reply: *"Every number
on screen must be something that was actually counted. Where there is no total,
show the count and no fraction."*

**It quietly drops what it could not parse.** This is the big one, and it will do
it, because dropping things makes the demo look better. Reply: *"Anything the
reader could not follow is listed on screen with the file and the line, never
dropped."*

**It writes code for a newer Python than you have.** The giveaway is an error
mentioning a version, or a line the chat swears is fine. Reply: *"This is Python
3.10. Write it the 3.10 way."*

**It asks you to install something new.** Reply: *"Use only what is already
installed."* Every phase in this kit is buildable with the nine pieces from the
setup step, and an extra one is a habit rather than a need.

### The four replies worth keeping to hand

Most rounds of back-and-forth are one of these four. Paste the reply into the
same window rather than explaining it in your own words each time.

**It stopped mid-file.**
> *Continue from the last complete line. Do not start the file again from the
> top. Tell me the line you are resuming from.*

**It used a name that is not in the contract card.**
> *The card calls that X, not Y. Window 9 will be looking for X and will never
> know you renamed it. Use the card's name everywhere and give me the file
> again.*

**The tests all pass but look too easy.**
> *Would any of those tests fail if the behaviour were missing? Show me the one
> that catches it. If there is not one, add it.*

**Something failed when you ran it.** Paste the whole red block, and nothing
else except this:
> *This is what happened when I ran it. Do not guess at the cause -- tell me
> which line you think produced it and why, then give me the corrected file
> whole.*

---

## When your own machine goes wrong

These are not code problems, they are the four things that actually stop people.
Each looks like broken code and none of them is.

**"python is not recognized" or "pip is not recognized".** Windows was never told
where those live. Use `python -m pip` instead of `pip`, and if `python` itself is
not recognised, use the full path in quotes:
`"C:\Program Files\Python310\python.exe"`

**"No module named ripple", or "no tests ran".** You are standing in the wrong
folder. Every command in this kit runs from the project folder:

**Type this into the black window.**
```
cd /d C:\ripple-build
```

**A file you definitely saved cannot be found.** It is almost certainly named
`config.py.txt` rather than `config.py`, because Notepad added the ending. This
lists what is really there, endings and all:

**Type this into the black window.**
```
dir C:\ripple-build\ripple
```

If you see a `.txt` on the end, delete that file and save it again using the
two-command trick in *Saving a file the chat gives you* above.

**"Port 8000 is already in use".** Two different things look like this, and only
one of them has a window you can close.

At home, usually: a copy of Ripple is still running in another Command Prompt
window from earlier. Find that window and hold Ctrl and press C, or close it.

On a work laptop, usually: nothing is running and there is nothing to close.
Windows itself has reserved that port, and hunting for a window will cost you the
evening. Ripple is built to step past this on its own — it takes the next free
port and prints the address it actually got. Read the address in the black window
and open that one, not 8000. Only if it gives up altogether is there anything for
you to do, and then it says so in words: that the ports are reserved rather than
in use, and the command that lists them.

---

## What to tell your IT team

Somebody will ask, and it is a fair question. Ripple has screens, so something has
to put them in front of your browser. The plain answer is that this is not a server
in the sense the word usually carries: nothing is hosted, nothing is published, and
nothing is reachable by anybody else.

- **It listens only to the laptop it is running on.** The address is 127.0.0.1,
  which is the machine talking to itself, and it is not reachable from the office
  network. A colleague who typed your machine name and the port would find nothing,
  because there is nothing there to find.
- **It runs only while the window is open.** Close the Command Prompt and it is
  gone. Nothing is installed as a Windows service and nothing starts at boot.
- **Nothing leaves the machine.** Ripple reads a folder of code you already have
  access to, works the answer out on your laptop, and shows it in your browser.
  Nothing is sent anywhere.
- **This is the ordinary shape of a desktop tool that has screens.** A Jupyter
  notebook works exactly this way. The browser is being used as the window, and
  that is the whole of it.

Two things worth saying out loud rather than being asked later: it reads the source
code of whatever repository you point it at, and it keeps one small file on your
laptop holding the analyses you chose to save. Both of those stay on the machine.

---

## If the install step will not work at all

The install steps back in **Getting ready** assume `pip` can reach something.
When it cannot — no mirror, no route out, and IT cannot help today — one package
still has to arrive, and only one: **`sqlglot`**, the SQL reader. Without it
Ripple is a word search, and a word search calling itself an impact analysis is
the exact thing Ripple exists to replace.

**Be clear about what these routes do and do not rescue.** They get the SQL
reader on and nothing else. The other eight pieces on that install line are what
put the screens in front of you, and there is no way to carry those across by
hand. If `pip` can reach nothing at all, get the reader on with a route below so
the hard part is proven, and then you still need one of the requests at the end
of this section before Ripple has screens.

**TWO BLACK WINDOWS, AND THIS IS WHERE THE SECOND ONE ARRIVES.** Up to now
everything went into the Command Prompt from Step 1. Some of the boxes below are
marked **powershell** above them, and those will NOT run in that window — they
are a different program with different words. Open it now and keep both:

> Press the Windows key, type `powershell`, press Enter. A blue window opens.

From here on: **a box marked `powershell` goes in the blue window. Every other
box goes in the black Command Prompt.** If a command answers with
`is not recognized as the name of a cmdlet` you are in the blue one and it wanted
the black one. If it answers `is not recognized as an internal or external
command` it is the other way round. Neither means anything is broken.

**STAND IN THE PROJECT FOLDER FIRST.** Every route below copies something into
`C:\ripple-build`. You already made that folder in **Making the folders**, so
there is nothing to create here — this only moves you into it. In the black
window:

**Type this into the black window.**
```
cd /d C:\ripple-build
```

`cd` means change directory, and the `/d` matters if your window opened on a
different drive. Everything below is typed while you are standing in that folder
— that is what "run it from ripple-build" means everywhere in this document.
Routes 1 and 3 leave a `sqlglot` folder in there beside `ripple`; that is
expected, even though the folder picture in **Making the folders** does not show
it.

**Whichever route you take, this is the proof.** Type it in the black window,
standing in `C:\ripple-build`:

**Type this into the black window.**
```
python -c "import sqlglot; print(sqlglot.__version__)"
```

It must print exactly `30.17.0`. Anything else — an error, a blank, a different
number — means that route did not land, and you move to the next one.

**The numbers are the order.** The ordinary install back at Step 4 was the first
thing to try, and it is the one that failed — that is why you are here. Work down
these three in the order they are printed, Route 1 then Route 2 then Route 3, and
stop at the first one where the proof above prints `30.17.0`.

### Route 1 — the source zip, unpacked beside your code

Route 1 comes first because it needs nothing from any other machine and no
permission from anyone. Many companies block the package site but leave GitHub
open, because people need to read code.

**1. Open this in your browser:**

**Open this in your browser.**
```
https://github.com/tobymao/sqlglot/archive/refs/tags/v30.17.0.zip
```

If it downloads, GitHub is reachable and this route works. If it does not, go to
Route 2.

**2. Unblock and unzip it.** Windows marks anything downloaded as coming from the
internet, which can make Python refuse to load it:

**Type this into the blue PowerShell window.**
```powershell
Unblock-File $env:USERPROFILE\Downloads\sqlglot-30.17.0.zip
```

```powershell
Expand-Archive $env:USERPROFILE\Downloads\sqlglot-30.17.0.zip -DestinationPath $env:USERPROFILE\Downloads\sqlglot-src
```

**3. Take ONE folder out of it — the inner one.** The zip contains a folder called
`sqlglot-30.17.0`, and inside that is another called `sqlglot`. **The inner one is
the parser**; the outer one is the project around it — tests, documentation, build
files — and none of that is wanted. Copy the inner one into your project:

**Type this into the blue PowerShell window.**
```powershell
Copy-Item $env:USERPROFILE\Downloads\sqlglot-src\sqlglot-30.17.0\sqlglot -Destination .\ripple-build\sqlglot -Recurse
```

**4. Fix the one thing the zip is missing.** This will catch you out, so do it now
rather than debugging it later. The file that records the version number is not in
the source code — it is created when the package is built, and the zip is the code
before that happens. Without it, `import sqlglot` prints a red error line and
`sqlglot.__version__` does not exist, **even though parsing works perfectly**. The
fix is one small file, and this is the first file in the whole kit you make by
hand. **Do not use Notepad's File then Save As.** It silently adds `.txt` to
whatever you name it, so you get `_version.py.txt`, Python cannot see it, and
the proof below keeps failing for a reason nothing tells you. Make the empty
file from the black window first, then open that file — the name is then already
right and Notepad cannot change it:

**Type this into the black window.**
```
type nul > C:\ripple-build\sqlglot\_version.py
```

```
notepad C:\ripple-build\sqlglot\_version.py
```

Notepad opens, empty. Paste these two lines into it, press Ctrl+S, close it:

**Type this into the black window.**
```python
__version__ = version = '30.17.0'
__version_tuple__ = version_tuple = (30, 17, 0)
```

**Proof:** the command above. Run it from `ripple-build`. If it prints
`Unable to set __version__` you skipped step 4.

---

### Route 2 — a wheel carried across and installed with no network

Route 2 gives the best result of the three — a properly installed package that
works from any folder, not just this project. It is second rather than first only
because it needs a second machine, one that can reach the internet.

**On any machine that can reach the internet** — a home laptop, a phone
tethered to a spare machine, anything outside the corporate network — fetch the
file:

**Type this into the black window.**
```
python -m pip download sqlglot==30.17.0 --no-deps --dest C:\ripple-parts
```

That produces one file, `sqlglot-30.17.0-py3-none-any.whl`, **415 KB**. The
`py3-none-any` in the name means it is not tied to any Python version or any kind
of machine — the same file works on your 3.10 laptop. `--no-deps` is safe here
because sqlglot has no dependencies.

Move that one file to the office laptop by whatever route is allowed to you — USB,
OneDrive, Teams, emailing it to yourself. It is under half a megabyte.

**On the office laptop, put that file in `C:\ripple-parts`.** Make the folder
first, in the black window:

**Type this into the black window.**
```
mkdir C:\ripple-parts
```

The name has to be exactly that, because the next command goes looking for it by
name. Then install from it. There is no network in this command; nothing is
fetched:

**Type this into the black window.**
```
python -m pip install --no-index --find-links=C:\ripple-parts sqlglot==30.17.0
```

If that is refused for permissions, add `--user`:

**Type this into the black window.**
```
python -m pip install --user --no-index --find-links=C:\ripple-parts sqlglot==30.17.0
```

**Proof:** the command above. This route is the one where it also works from
outside `ripple-build`, which is a good sign you got the best outcome available.

---

### Route 3 — the folder copied across as plain files

The last route, and the one that cannot fail for any reason involving pip, because
pip is not involved. Use it if pip refuses to install even from a local file.

**On any machine that can reach the internet**, install it there first, then find
where it landed:

**Type this into the black window.**
```
python -m pip install sqlglot==30.17.0
```

```
python -c "import sqlglot,os;print(os.path.dirname(sqlglot.__file__))"
```

That prints a folder called `sqlglot`. Copy it, then **delete every `__pycache__`
folder inside the copy**. Those hold code compiled for that machine's Python
version, they are useless anywhere else, and they are more than half the size:

**Type this into the blue PowerShell window.**
```powershell
Get-ChildItem <your copy>\sqlglot -Recurse -Directory -Filter __pycache__ | Remove-Item -Recurse -Force
```

`<your copy>` is the pointy-bracket gap again: put the folder you pasted the copy
into in place of it, brackets deleted, so the line reads something like
`Get-ChildItem D:\parts\sqlglot -Recurse -Directory -Filter __pycache__ | Remove-Item -Recurse -Force`.

You should be left with **71 files and 1.8 MB**. Move that folder across, and drop
it into the project so it sits beside `ripple`:

**Read this — there is nothing to type.**
```
ripple-build\sqlglot\
```

Nothing is installed and nothing is configured. Python looks in the folder it was
started from, finds `sqlglot` there, and uses it.

**Proof:** the command above, run from `ripple-build`. This route only works from
`ripple-build`, which is why the contract card tells every window that commands run
from the project root.

---

### When none of them work

Say so early rather than building eleven-twelfths of a tool that cannot read SQL.
The options left are all requests to someone else, in rough order of how often
they are granted: ask IT to install one named pure-Python package for you; ask for
the internal mirror to be enabled; ask for a temporary firewall exception to
`pypi.org` and `files.pythonhosted.org`; or build Ripple somewhere else and use it
against a copy of the repository. There is no version of Ripple worth having that
reads SQL without a parser — a word search that calls itself an impact analysis is
the exact thing this tool exists to replace.

