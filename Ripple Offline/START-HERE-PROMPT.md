# Prompt: build Ripple Offline

Paste everything below the line into a new Claude Code session started in
`D:\Apps\Ripple`.

---

Build **Ripple Offline** — a version that runs on a locked-down machine with no
internet at all, scanning a repository already downloaded to that machine.

## WHERE THINGS ARE

- Build it in: `D:\Apps\Ripple\Ripple Offline`
- The working app to reuse: `D:\Apps\Ripple\Codebase` — FastAPI plus plain
  HTML/CSS/JavaScript, no build step, no framework.
- Prototype (design source of truth, READ ONLY — never edit):
  `D:\Apps\Ripple\Prototype\Ripple Prototype.html`
- Git: repo root `D:\Apps\Ripple` → github.com/aucksy/Ripple, branch `main`.
  Commit and push straight to `main` yourself. No branches, no PRs.
- `D:\Apps\CLAUDE.md` loads automatically — follow it. Above all: write to me in
  plain English (I'm a product manager, not a coder), and end every session with
  the Done / Needs you / Next block.

## WHAT ALREADY WORKS — DO NOT REBUILD IT

Ripple already scans a folder on disk and needs no internet. This was proved,
not assumed: with every outbound socket blocked, the page loaded, the bundled
fonts loaded, a full scan ran, the summary and the drafted reply were written,
an `.eml` was read, and history saved. Fonts are bundled in the app, so there is
no font CDN.

**So this job is not about the analysis engine.** It is about packaging, and
about removing every way a user could accidentally need the internet.

## WHAT I WANT

A folder a colleague can copy onto a locked-down machine, double-click, and use
— with no Python installed, no `pip install`, and no network.

1. **A double-click build for Windows.** PyInstaller or equivalent. It starts,
   the browser opens, it works. No terminal, no install step.
2. **Choose the repository folder on screen.** Today it is an environment
   variable, which a non-technical user will never set. Ask on first run and
   remember it in a small config file beside the executable. A folder that has
   moved or been deleted must say so plainly, not crash.
3. **Choose the SQL dialect on screen too**, defaulted to `bigquery` — that is
   our stack. This matters more than it looks: read as generic SQL, a BigQuery
   pipeline parsed 2 of 5 files and reported "no impact" on a change that really
   broke two things. See the README section "Why the SQL dialect is the setting
   that matters".
4. **Hard offline.** The GitHub source option and the AI card must be *gone*,
   not merely unused — nothing on screen that reaches out, and no key boxes to
   tempt anyone. Add a guard so that any outbound call fails loudly in the tests
   rather than quietly succeeding because the build machine happens to be
   online.
5. **Everything else identical** to the online version, screen for screen.

## THE DESIGN CONSTRAINT THAT MATTERS MOST

**Do not copy the `ripple` package into the new folder.** Two copies will drift
apart and the offline one will quietly rot — the online one has already gained
BigQuery support, MERGE lineage and hosted-copy honesty notices that a fork
would miss. Reuse `D:\Apps\Ripple\Codebase\ripple` as the single source of
truth and have the build script pull it in. If that turns out to be impossible,
stop and tell me why *before* copying anything.

## RULES THAT STILL APPLY

- No fake behaviour: no invented counts, no progress bars that animate while
  nothing is happening, no links that go nowhere.
- Don't weaken the honesty features: the confirm-before-scanning step, the
  "could not read" list and its stat card, the "mentions only" list, and the
  labels saying whether AI or rules produced something.
- Manual mode must keep working end to end.
- Never commit `Ripple - Overview.pdf` or `ripple-overview.html` — they name
  internal hostnames and the repo is public. `.gitignore` already excludes them.

## HOW TO RUN AND CHECK

- Tests: from `D:\Apps\Ripple\Codebase` run
  `.venv\Scripts\python -m pytest tests -q` → 109 pass. Keep them passing.
- Prove it is offline the way it was proved before: block outbound sockets while
  allowing loopback (Python's own event loop needs loopback, so blocking
  everything breaks the test harness rather than the app), then run the whole
  flow. If anything reaches out, the test must fail.
- Then **actually run the built executable on this machine** and scan a real
  folder before telling me it works. A build that compiles is not a screen that
  opens.
- If the Browser pane cannot screenshot ("not compositing frames"), drive
  headless Chrome over the DevTools protocol instead. Chrome is at
  `C:\Program Files (x86)\Google\Chrome\Application\chrome.exe`. The app scrolls
  an inner container, not the page, so full-page capture returns one screenful —
  use a tall viewport instead.

## WHAT GETS BETTER OFFLINE, AND WHAT GETS WORSE

Better: saved history actually lasts, because there is a real disk. There is no
4 MB limit on the notification file, because there is no serverless host
refusing large uploads. Nothing leaves the machine, so there is no question
about sending table names to a third party.

Worse: there is no AI, so the rules-only reader is the *only* path rather than a
fallback. Which brings me to the one known problem.

## KNOWN, NOT YET FIXED — and it matters more offline

With no AI key, **pasting** email text into step 1 finds the tables and
attributes correctly but leaves "Source system" and the contact blank. Uploading
the `.eml` or `.msg` file works better than pasting.

Online this is a minor annoyance because the AI covers it. Offline it is the
normal path, so please fix it as part of this work: the rules-based reader
should pull the source system and the contact out of pasted text as well as it
does out of an uploaded file.
