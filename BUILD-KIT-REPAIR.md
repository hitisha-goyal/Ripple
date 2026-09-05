# Repairing Ripple

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

* `ripple/scanner/sqlread.py` — 3,743 lines
* `web/app.js` — 3,592 lines
* `ripple/scanner/lineage.py` — 2,052 lines

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
      the project root holds run.py, and folders ripple\ , web\ and tests\
      example: ripple\scanner\sqlread.py

  The packaged build, also called Ripple Offline:
      the same, plus a folder ripple_offline\ and a copied folder sqlglot\
      example: ripple\scanner\sqlread.py   (the same place)
      but the web service is ripple_offline\app.py, not ripple\api.py

THE CATALOGUE — every file, what it decides, and what it touches
29 Python files and the three screen files, 14,233 lines in all.

### ripple/ai.py   (312 lines, normal build only)
WHAT IT DECIDES: The optional AI layer.
IT NEEDS      : ripple/config.py, ripple/providers.py
NEEDED BY     : ripple/api.py
CALLABLE      : AIUnavailable, list_models(), read_email(), write_summary(), write_reply(), check_key()
WHY IT IS LIKE THIS, in the file's own words:
    Two jobs only: read the notification email at the front, and write the English
    at the back. It is never shown a single line of source code -- the findings it
    summarises are already structured facts produced by the scanner.

    If there is no key, or the call fails, every function here falls back to a
    written-out version. Ripple must work with the AI switched off.
### ripple/api.py   (920 lines, normal build only)
WHAT IT DECIDES: The web service.
IT NEEDS      : ripple/ai.py, ripple/build_info.py, ripple/catalog.py, ripple/config.py, ripple/narrative.py, ripple/notification.py, ripple/production.py, ripple/progress.py, ripple/providers.py, ripple/scanner/github.py, ripple/scanner/lineage.py, ripple/scanner/repo.py, ripple/scanner/sqlread.py, ripple/store.py
NEEDED BY     : nothing else in Ripple
CALLABLE      : repo_state(), reindex(), UpstreamIn, ScanIn, SummaryIn, SaveIn, StatusIn, AIKeyIn, ProductionIn, FolderIn, ConnectIn, health(), progress_now(), catalog() and 19 more
WHY IT IS LIKE THIS, in the file's own words:
    Thin on purpose: every route is a few lines that call the scanner, the reader
    or the writer. All of the thinking lives in those modules, so the same logic
    runs from the command line, from a test, or from this API.
### ripple/build_info.py   (227 lines, both builds)
WHAT IT DECIDES: Which build of Ripple is this one?
IT NEEDS      : nothing else in Ripple
NEEDED BY     : ripple/api.py, ripple_offline/app.py
CALLABLE      : build_info(), write_stamp()
WHY IT IS LIKE THIS, in the file's own words:
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
### ripple/catalog.py   (201 lines, both builds)
WHAT IT DECIDES: What tables and columns exist, learned from the repository itself.
IT NEEDS      : ripple/scanner/dialectcompat.py, ripple/scanner/sqlread.py
NEEDED BY     : ripple/api.py, ripple/notification.py, ripple/scanner/lineage.py, ripple_offline/app.py
CALLABLE      : Catalog, build_catalog()
WHY IT IS LIKE THIS, in the file's own words:
    This is the "mock database" for the demo: rather than being handed a data
    dictionary, Ripple reads every CREATE TABLE it can find and builds one. The
    same code works against a real repository -- and whatever it cannot read shows
    up as a gap rather than silently shrinking the catalogue.
### ripple/config.py   (365 lines, both builds)
WHAT IT DECIDES: Settings for a Ripple installation.
IT NEEDS      : ripple/production.py, ripple/providers.py
NEEDED BY     : ripple/ai.py, ripple/api.py, ripple/scanner/github.py, ripple/scanner/lineage.py, ripple/scanner/repo.py, ripple/scanner/sqlread.py, ripple/store.py, ripple_offline/app.py, ripple_offline/prefs.py, run.py
CALLABLE      : git_branch(), Settings
WHY IT IS LIKE THIS, in the file's own words:
    Everything that would differ between a laptop, a demo host and a real corporate
    network lives here, so nothing has to be hunted for in code.
### ripple/narrative.py   (595 lines, both builds)
WHAT IT DECIDES: Writing the summary and the reply without any AI.
IT NEEDS      : nothing else in Ripple
NEEDED BY     : ripple/api.py, ripple_offline/app.py
CALLABLE      : days_until(), summarise(), draft_reply()
WHY IT IS LIKE THIS, in the file's own words:
    This is what runs when there is no key, when the key stops working, or when
    someone decides no data may leave the network. It is plainer than the AI
    version, but it says exactly the same things -- the facts come from the scan
    either way.
### ripple/notification.py   (545 lines, both builds)
WHAT IT DECIDES: Reading the impact notification.
IT NEEDS      : ripple/catalog.py
NEEDED BY     : ripple/api.py, ripple_offline/app.py
CALLABLE      : names_the_whole_table(), Notification, read_eml(), read_msg(), strip_html(), split_pasted_headers(), parse_sender(), signature(), source_system(), enrich(), read_pasted(), read_upload(), parse_date(), classify_change() and 2 more
WHY IT IS LIKE THIS, in the file's own words:
    Two ways in, and both end at the same editable form:

    * upload a saved Outlook message, or paste the text
    * type the tables and attributes yourself (manual mode)

    Extraction never has the last word. Whatever comes out of here is shown to a
    human to correct before a single file is scanned.
### ripple/production.py   (688 lines, both builds)
WHAT IT DECIDES: Which tables are the ones this team publishes.
IT NEEDS      : nothing else in Ripple
NEEDED BY     : ripple/api.py, ripple/config.py, ripple_offline/app.py
CALLABLE      : Entry, parse(), parse_production_rule(), family_of(), ProductionRule, check_against_repo()
WHY IT IS LIKE THIS, in the file's own words:
    This is the single most expensive setting in Ripple. A finding only counts as
    production impact if the table it ends at is on this list, so getting it wrong
    turns a change that really breaks three published tables into a calm "no
    production impact" -- the exact answer this tool exists to stop anybody giving.

    It used to take patterns only: a word like ``_PROD`` matching the end of a table
    name, or ``PROD_*`` with a wildcard. That is a guess about a naming convention
    dressed up as a rule. So this module also takes the answer directly: paste the
    real list of published tables and Ripple uses it as written.

    The paste arrives from wherever the list happens to live -- an Excel column, a
    Slack message, a Confluence page, the output of a query -- so it is read
    tolerantly. Nothing is thrown away quietly: everything the reader declined to
    use comes back as a note saying what it was and why, because a silently misread
    list here is worse than no list at all.
### ripple/progress.py   (64 lines, both builds)
WHAT IT DECIDES: What Ripple is doing right now, so a screen can say so while it waits.
IT NEEDS      : nothing else in Ripple
NEEDED BY     : ripple/api.py, ripple_offline/app.py
CALLABLE      : start(), step(), finish(), snapshot(), reader()
WHY IT IS LIKE THIS, in the file's own words:
    On a repository the size of the one this was built for -- a couple of thousand
    files, single statements six hundred lines long -- reading takes minutes and a
    scan takes about a minute. A screen that says nothing for that long looks
    broken, and the honest answer to "is it still going?" is a number that is
    actually going up.

    Two rules this file keeps, and they are the whole reason it is this small:

    * Every number here is counted, never estimated. ``done`` is files that have
      really been read. Nothing is smoothed, nothing is extrapolated, and nothing
      moves on a timer.
    * ``total`` is zero when there genuinely is no total. Following a chain looks at
      as many statements as it turns out to need, so there is no denominator, and
      inventing one to fill a progress bar would be inventing the one number on the
      screen nobody could check.
### ripple/providers.py   (142 lines, normal build only)
WHAT IT DECIDES: Which AI provider a key belongs to, worked out from the key itself.
IT NEEDS      : nothing else in Ripple
NEEDED BY     : ripple/ai.py, ripple/api.py, ripple/config.py
CALLABLE      : detect(), name_of_unsupported(), by_id(), is_chat_model(), rank_models()
WHY IT IS LIKE THIS, in the file's own words:
    One box on the screen, not three. Somebody pasting a key should not have to
    tell Ripple which company issued it: the key says so in its first few
    characters, and asking is one more thing to get wrong on a screen whose whole
    job is to be checkable.

    All three providers speak the same OpenAI-shaped ``/chat/completions``, so
    there is one code path and only the address, the key and the model change.
    Google's is its own OpenAI-compatible endpoint, which was confirmed live rather
    than taken from documentation.

    The model list is NOT written down here. A hand-typed list of model names is
    wrong within months and then tells somebody a model exists that does not. It is
    fetched from the provider with the key they just pasted, which proves the key
    and produces the real list in the same call. The names below are only an
    ORDER OF PREFERENCE applied to whatever comes back -- if none of them is in the
    list, the first usable model is used and the screen says which.
### ripple/scanner/dialectcompat.py   (138 lines, both builds)
WHAT IT DECIDES: Reading the parse tree the same way whichever sqlglot is installed.
IT NEEDS      : nothing else in Ripple
NEEDED BY     : ripple/catalog.py, ripple/scanner/lineage.py, ripple/scanner/sqlread.py
CALLABLE      : from_of(), star_except(), star_replace(), is_unpivot(), pivot_fields(), pivot_columns(), is_temporary(), merge_whens(), set_branches(), output_names()
WHY IT IS LIKE THIS, in the file's own words:
    sqlglot renames the keys inside its own nodes between major versions, and three
    of the renames that matter here are SILENT: the old key simply returns None, so
    the code carries on and finds nothing. Two of the three switch off things this
    tool exists to do --

    * ``Star.args["except"]`` became ``except_``. Read the old key and
      ``SELECT * EXCEPT(col)`` stops being noticed, so a column that is dropped by
      name is reported as carried through.
    * ``Merge.args["expressions"]`` became ``whens`` (wrapped in a ``Whens`` node).
      Read the old key and every rename a MERGE makes disappears -- and a MERGE is
      how a published table is normally loaded.

    -- and the third, ``Select.args["from"]`` becoming ``from_``, quietly empties
    the check that decides which tables a ``SELECT *`` covers.

    None of that raises. The tests would go on passing on the version that is
    installed today and the answers would go quietly wrong on any newer one. So
    every one of those keys is read through a function here, and there is a test
    that fails loudly if a key stops resolving at all.
### ripple/scanner/github.py   (284 lines, normal build only)
WHAT IT DECIDES: Reading a repository straight from GitHub, with an access token.
IT NEEDS      : ripple/config.py, ripple/scanner/repo.py
NEEDED BY     : ripple/api.py
CALLABLE      : GitHubError, RepoRef, Connection, parse_repo_ref(), describe(), download_archive(), index_from_archive(), connect()
WHY IT IS LIKE THIS, in the file's own words:
    Ripple's scanner works on a folder of files. This module gets that folder from
    GitHub instead of from disk: it asks GitHub for the repository as a single
    compressed archive, unpacks it in memory, and hands back the same RepoIndex the
    local reader produces. Everything downstream -- the SQL reader, the lineage
    tracer, the catalogue -- is unchanged and does not know where the files came
    from.

    One archive is a single request. Asking for each file separately would be
    hundreds of requests and would exhaust the hourly limit on a real repository.

    The access token is only ever used as an Authorization header. It is never
    written to disk, never logged, and never returned by any route.
### ripple/scanner/lineage.py   (2,052 lines, both builds)
WHAT IT DECIDES: Following a column through the pipeline, and saying what it means.
IT NEEDS      : ripple/catalog.py, ripple/config.py, ripple/scanner/dialectcompat.py, ripple/scanner/repo.py, ripple/scanner/sqlread.py
NEEDED BY     : ripple/api.py, ripple_offline/app.py
CALLABLE      : Finding, ScanResult, trace()
WHY IT IS LIKE THIS, in the file's own words:
    A column rarely keeps its name. MARKET_CODE becomes mc, then mkt_cd, and the
    thing that finally breaks is three files away from the one the notification
    named. This module walks that chain and groups what it finds under the
    production table each chain ends at -- because that is the thing an engineer
    actually has to defend.
### ripple/scanner/repo.py   (964 lines, both builds)
WHAT IT DECIDES: Reading the repository and finding candidate files.
IT NEEDS      : ripple/config.py
NEEDED BY     : ripple/api.py, ripple/scanner/github.py, ripple/scanner/lineage.py, ripple/scanner/sqlread.py, ripple_offline/app.py
CALLABLE      : effective_ext(), unopened_code_types(), online_only(), SourceFile, Match, RepoIndex, welded_blocks(), extract_sql_blocks(), extract_markup_sql(), statements_for(), sql_file_refs(), looks_like_unread_sql(), written_tables()
WHY IT IS LIKE THIS, in the file's own words:
    Step one of a scan is deliberately dumb and fast: find every file that so much
    as mentions the name. Understanding what the mention *means* happens later.
### ripple/scanner/rescue.py   (345 lines, both builds)
WHAT IT DECIDES: BigQuery shapes the SQL parser refuses, rewritten into ones it accepts.
IT NEEDS      : nothing else in Ripple
NEEDED BY     : ripple/scanner/sqlread.py
CALLABLE      : export_targets(), needed(), rewrite()
WHY IT IS LIKE THIS, in the file's own words:
    Same idea as ``templating.fill_placeholders`` and ``templating.unwrap_blocks``,
    and the same two rules: this is done to a COPY on the way into the parser, and
    every replacement puts back the number of line breaks it swallowed, so a finding
    still points at the real line of the real file.

    Why it has to exist. sqlglot fails these two ways, and both are quiet:

    * a hard parse error, which loses the whole statement -- and in a file of a few
      statements, sqlglot's error recovery loses its neighbours with it;
    * a fall back to a generic Command node, which holds the raw text and contains
      no tables at all, so the statement is read, understood as nothing, and is
      invisible unless it is the only statement in its file.

    Either way the answer that comes back is a clean "no impact". Every shape below
    was measured against the installed parser rather than taken from documentation,
    and every one of them appears in an ordinary BigQuery pipeline:

        CREATE MATERIALIZED VIEW p.d.mv AS REPLICA OF p.d.cust        a whole copy
        CREATE TABLE a CLONE b FOR SYSTEM_TIME AS OF TIMESTAMP(...)   a restore
        CREATE EXTERNAL TABLE t ... WITH CONNECTION `p.us.c`          every BigLake
        CREATE EXTERNAL TABLE t WITH PARTITION COLUMNS (dt DATE)      hive layout
        SELECT ... FROM APPENDS(TABLE `p.d.cust`, NULL)               incremental
        SELECT ... FROM `p.d.f`(TABLE `p.d.orders`, 'apple')          a TVF argument
        LOAD DATA INTO t (a STRING) FROM FILES (...)                  ingestion
        EXPORT DATA OPTIONS(...) AS SELECT ...                        a partner feed

    The last one is worth a word. An export builds no table, so there is nothing to
    carry the column onwards to -- but it is a real read, and after this it is
    reported as one rather than as a file that could not be read.
### ripple/scanner/sqlread.py   (3,743 lines, both builds)
WHAT IT DECIDES: Reading SQL properly, rather than just matching words.
IT NEEDS      : ripple/config.py, ripple/scanner/dialectcompat.py, ripple/scanner/repo.py, ripple/scanner/rescue.py, ripple/scanner/templating.py
NEEDED BY     : ripple/api.py, ripple/catalog.py, ripple/scanner/lineage.py, ripple_offline/app.py
CALLABLE      : short_name(), dataset_of(), canonical(), is_wildcard(), wildcard_match(), wildcard_covers(), is_metadata_read(), session_scope(), is_session_scoped(), same_table(), reads_metadata(), Usage, Statement, ParsedRepo and 15 more
WHY IT IS LIKE THIS, in the file's own words:
    The whole value of Ripple is in this file. A word search can tell you that
    MARKET_CODE appears in a file. Only parsing can tell you that it appears
    *inside a WHERE clause comparing it to the literal 'US'* -- which is the
    difference between "mentioned here" and "this breaks on the 18th".
### ripple/scanner/templating.py   (681 lines, both builds)
WHAT IT DECIDES: Filling in the placeholders that pipeline SQL is written with.
IT NEEDS      : nothing else in Ripple
NEEDED BY     : ripple/scanner/sqlread.py
CALLABLE      : has_placeholders(), describe(), placeholder_names(), fill_placeholders(), unwrap_blocks(), has_blocks(), has_control_flow(), renderings()
WHY IT IS LIKE THIS, in the file's own words:
    Almost no production SQL is plain SQL. Airflow, dbt and every in-house
    generator wrap the parts that change -- the project, the dataset, the run date
    -- in ``{{ ... }}`` and push the file through a templating engine before a
    database ever sees it. A SQL parser has never met a ``{`` in that position, so
    it refuses the file outright, and a repository that is almost entirely readable
    is reported as almost entirely unreadable::

        CREATE OR REPLACE TABLE {{tgt_project_id}}.{{stage_dataset}}.web_activity AS
        SELECT ...

    Ripple is not the templating engine and cannot know what those values are at
    run time. It does not need to. It needs the shape of the statement and the
    names in it -- and the table name, ``web_activity``, is sitting right there.

    So every placeholder is replaced by an ordinary identifier made out of its own
    text. ``{{tgt_project_id}}.{{stage_dataset}}.web_activity`` becomes
    ``tgt_project_id.stage_dataset.web_activity``, which parses as the three-part
    name it always was, and the table still comes out as ``web_activity``.

    Two rules this file keeps:

    * Line numbers do not move. Every replacement puts back the same number of
      line breaks it swallowed, so a finding still points at the real line of the
      real file, which is the only line anybody can go and look at.
    * The original text is never changed. This is done to a copy on the way into
      the parser; everything shown on screen still comes from the file itself.
### ripple/store.py   (144 lines, both builds)
WHAT IT DECIDES: History of past notifications, so nothing gets lost between people.
IT NEEDS      : ripple/config.py
NEEDED BY     : ripple/api.py, ripple_offline/app.py
CALLABLE      : save(), listing(), get(), set_status()
WHY IT IS LIKE THIS, in the file's own words:
    A single SQLite file. On a serverless host the filesystem is read-only apart
    from /tmp, so the path is configurable and a failure to write is reported
    rather than crashing the request.
### run.py   (148 lines, normal build only)
WHAT IT DECIDES: Start Ripple on this machine.
IT NEEDS      : ripple/config.py
NEEDED BY     : nothing else in Ripple
CALLABLE      : take_a_port(), chosen_port(), main()
WHY IT IS LIKE THIS, in the file's own words:
    python run.py

    It finds a port it can actually use, prints the address, and opens your browser.
    Nothing else to install or set up.

    WHY THERE IS A PORT SEARCH HERE AT ALL. This used to be one line: listen on 8000.
    It printed "open http://localhost:8000", opened the browser, and only then asked
    Windows for the port. On a managed work laptop, 27 Aug 2026, Windows refused it
    -- WinError 10013, a port reserved by the machine rather than used by a program
    -- so the browser was already sitting on a dead address before anything knew the
    start had failed. Announce nothing until the door is actually open.
### ripple_offline/__init__.py   (14 lines, packaged build only)
WHAT IT DECIDES: Ripple Offline — the same Ripple, packaged for a machine with no internet.
IT NEEDS      : ripple_offline/engine.py
NEEDED BY     : nothing else in Ripple
CALLABLE      : none
WHY IT IS LIKE THIS, in the file's own words:
    This package is a wrapper, not a copy. The analysis engine lives in
    ``D:\Apps\Ripple\Codebase\ripple`` and stays there: importing anything from
    here puts that folder on the import path first, so there is exactly one copy of
    the scanner, the SQL reader, the lineage tracer and the writer. What lives here
    is only what genuinely differs offline — settings chosen on screen instead of
    in environment variables, and a front end with nothing on it that reaches out.
### ripple_offline/app.py   (641 lines, packaged build only)
WHAT IT DECIDES: The offline web service.
IT NEEDS      : ripple/build_info.py, ripple/catalog.py, ripple/config.py, ripple/narrative.py, ripple/notification.py, ripple/production.py, ripple/progress.py, ripple/scanner/lineage.py, ripple/scanner/repo.py, ripple/scanner/sqlread.py, ripple/store.py, ripple_offline/folderpick.py, ripple_offline/lifecycle.py, ripple_offline/nonet.py, ripple_offline/paths.py, ripple_offline/prefs.py, ripple_offline/synced.py
NEEDED BY     : nothing else in Ripple
CALLABLE      : start_reading(), repo_state(), reindex(), UpstreamIn, ScanIn, SummaryIn, SaveIn, StatusIn, PathIn, ProductionIn, SettingsIn, health(), alive(), going() and 21 more
WHY IT IS LIKE THIS, in the file's own words:
    The same shape as the online one, minus everything that reaches out. There is
    no GitHub route and no AI route — not disabled, not behind a flag, absent — so
    there is no key to leak, no address to type, and nothing that can quietly start
    working because the machine turned out to have internet after all.

    What is here instead: the two settings that were environment variables online,
    asked for on screen and remembered in a file beside the executable.

    Every route below calls the shared engine in ``Codebase/ripple``. Nothing about
    scanning, reading SQL, tracing lineage or writing the summary is reimplemented
    here — this is a thin layer, exactly as the online service is.
### ripple_offline/engine.py   (56 lines, packaged build only)
WHAT IT DECIDES: Finding the one copy of the analysis engine.
IT NEEDS      : nothing else in Ripple
NEEDED BY     : ripple_offline/__init__.py, ripple_offline/paths.py, ripple_offline/webbuild.py
CALLABLE      : frozen(), ensure_engine_importable()
WHY IT IS LIKE THIS, in the file's own words:
    Ripple Offline deliberately has no ``ripple`` package of its own. Two copies
    would drift: the online one has already grown BigQuery support, MERGE lineage
    and honesty notices that a fork would quietly miss, and the fork would be the
    one running on the locked-down machine where nobody can check it.

    So there is one copy, in ``Codebase/ripple``, and two ways of reaching it:

    * running from source, this adds ``Codebase`` to the import path;
    * running as a built executable, the build script has already collected that
      same folder into the bundle, so ``import ripple`` simply works.

    If the shared engine is not where it should be, this says so and stops. It
    never falls back to a copy — a stale copy is the exact failure it exists to
    prevent.
### ripple_offline/folderpick.py   (51 lines, packaged build only)
WHAT IT DECIDES: This machine's own "choose a folder" window.
IT NEEDS      : nothing else in Ripple
NEEDED BY     : ripple_offline/app.py
CALLABLE      : available(), choose_folder()
WHY IT IS LIKE THIS, in the file's own words:
    A browser cannot hand a web page the real path of a folder — that is a security
    rule, not an oversight — and a real path is exactly what the scanner needs. But
    Ripple Offline is not really a website: it is a program running on the same
    machine as the browser looking at it. So the window it opens is this machine's
    own folder picker, and the path comes back the normal way.

    Typing or pasting a path always works and is never taken away. This only saves
    the typing, and when there is no picker to open the screen does not offer the
    button at all — a button that does nothing is worse than no button.
### ripple_offline/lifecycle.py   (167 lines, packaged build only)
WHAT IT DECIDES: Stopping the program when nobody is looking at it any more.
IT NEEDS      : nothing else in Ripple
NEEDED BY     : ripple_offline/app.py
CALLABLE      : reset(), attach(), beat(), leaving(), verdict(), stop(), stopping(), watch(), facts()
WHY IT IS LIKE THIS, in the file's own words:
    The built program opens without a console window, on purpose: a black box
    sitting beside the browser looks like something went wrong. The cost of that is
    there is no Ctrl-C and no window to close. Closing the browser tab does nothing
    at all -- the server goes on running, invisible, holding its own folder open. So
    the folder cannot be deleted, the port stays taken, a second copy starts on a
    different port, and the only way out is Task Manager, which nobody should need
    to know about to close a program.

    This module is the way out. The page says "still here" every few seconds; when
    it stops saying so, Ripple stops. There is also a button that stops it now.

    Two things this has to get right, because both are ways to lose somebody's work:

    * A refresh, or moving between screens, briefly has no page. That is why a page
      saying goodbye only shortens the deadline rather than stopping immediately --
      the new page arrives well inside that window and cancels it.
    * A tab left open in the background is still somebody using Ripple. Browsers
      throttle timers in hidden tabs to about one a minute, so the quiet limit is
      minutes rather than seconds.

    Everything here is decided by ``verdict()``, which is given the time rather than
    reading the clock, so the whole of it can be tested without waiting.
### ripple_offline/nonet.py   (122 lines, packaged build only)
WHAT IT DECIDES: The guard that makes "offline" a fact rather than a claim.
IT NEEDS      : nothing else in Ripple
NEEDED BY     : ripple_offline/app.py
CALLABLE      : OutboundBlocked, install(), uninstall(), installed()
WHY IT IS LIKE THIS, in the file's own words:
    A build machine has internet. That is exactly how an offline build ships with
    something in it that quietly reaches out: on the machine where it was tested
    the call succeeded, so nothing looked wrong, and the first time anyone finds
    out is on the locked-down machine where it hangs instead.

    So outbound connections are blocked outright, in the running application and in
    the tests. Loopback is allowed, because Ripple talks to itself: the web server
    listens on 127.0.0.1 and the browser connects to it. Anything else raises, and
    the message says what was attempted, so a reach-out is a loud failure with an
    address in it rather than a silent success.
### ripple_offline/paths.py   (52 lines, packaged build only)
WHAT IT DECIDES: Where things are written on the machine Ripple is copied onto.
IT NEEDS      : ripple_offline/engine.py
NEEDED BY     : ripple_offline/app.py, ripple_offline/prefs.py
CALLABLE      : app_dir(), settings_file(), history_file(), web_dir()
WHY IT IS LIKE THIS, in the file's own words:
    Everything Ripple keeps — the chosen folder, the SQL dialect, the saved history
    — sits next to the executable, in the folder the user copied across. Nothing
    goes into a hidden application-data folder, so deleting the folder really does
    remove Ripple, and copying the folder to another machine takes the settings and
    the history with it.
### ripple_offline/prefs.py   (284 lines, packaged build only)
WHAT IT DECIDES: The two settings a person has to choose, kept in a file beside the app.
IT NEEDS      : ripple/config.py, ripple_offline/paths.py
NEEDED BY     : ripple_offline/app.py
CALLABLE      : default_hops(), max_hops_ceiling(), clamp_hops(), default_production(), dialects(), valid_dialect(), load(), save(), configured(), folder_label(), apply(), folder_state(), check_folder()
WHY IT IS LIKE THIS, in the file's own words:
    Online, the repository folder and the SQL dialect are environment variables.
    That is fine for someone who deploys things and hopeless for everybody else: a
    colleague who has been handed a folder to double-click will never set one, so
    they would silently scan the wrong folder, reading BigQuery as generic SQL.

    So both are asked for on screen and written to ``ripple-settings.json`` next to
    the executable. Nothing else is stored, and the file is plain text so it can be
    read, edited or deleted by hand.
### ripple_offline/synced.py   (89 lines, packaged build only)
WHAT IT DECIDES: Is Ripple itself sitting in a folder something is syncing to the cloud?
IT NEEDS      : nothing else in Ripple
NEEDED BY     : ripple_offline/app.py
CALLABLE      : detect()
WHY IT IS LIKE THIS, in the file's own words:
    Ripple Offline keeps everything beside the executable -- the chosen folder, the
    SQL dialect, the saved history, the log. That is deliberate: deleting the folder
    really does remove Ripple, and copying the folder to another machine takes the
    settings and the history with it.

    It has one consequence worth saying out loud. Everyone in this office has
    OneDrive sync switched on, so the folder Ripple is copied into is very likely a
    folder OneDrive uploads. Two things follow, and neither is obvious:

    * The saved history is a database file. A sync client holds a file open while it
      uploads it, and it copies files whenever it likes. A save can fail because of
      that, and a database copied mid-write can come back damaged.
    * Everything in the folder goes up to the company's cloud -- the whole program,
      not just the settings. That is a decision somebody should make on purpose
      rather than discover afterwards.

    Neither is a reason to stop. Both are a reason to say so.
### ripple_offline/webbuild.py   (199 lines, packaged build only)
WHAT IT DECIDES: Building the offline front end out of the online one.
IT NEEDS      : ripple_offline/engine.py
NEEDED BY     : nothing else in Ripple
CALLABLE      : BuildError, strip_blocks(), check_clean(), build()
WHY IT IS LIKE THIS, in the file's own words:
    The same argument as the engine: two copies of a 60 KB screen would drift, and
    the drifting one would be the copy running where nobody can check it. So there
    is one front end, in ``Codebase/web``, and this makes the offline version of it.

    Two things happen here.

    *Lines are deleted.* The shared files mark the parts that reach out — the
    GitHub source and the AI key form — between ``//<online-only>`` and
    ``//</online-only>``. Those lines are removed, so they are not merely unused in
    the offline build, they are not in it. Then the result is checked for the words
    that should no longer be there. That check is the real safeguard: if somebody
    edits the online front end and loses a marker, the offline build fails with the
    word it found rather than quietly shipping a key box onto a locked-down machine.

    *One file is added.* ``web/offline.js`` holds the screens that only exist
    offline — choosing the repository folder and the SQL dialect. It is appended to
    the stripped script rather than loaded separately, because JavaScript hoists
    every function declaration in a file before running any of it, which is what
    lets it replace the online settings screen cleanly.
### web/app.js   (3,592 lines, both builds)
WHAT IT DECIDES: Every screen. All seven steps, every card, every table and every word on them. No Python file draws anything.
IT NEEDS      : reads the JSON that ripple/api.py (or ripple_offline/app.py) returns
NEEDED BY     : nothing imports it — the page loads it
CALLABLE      : not Python
### web/styles.css   (438 lines, both builds)
WHAT IT DECIDES: Every colour, size and spacing rule.
IT NEEDS      : nothing
NEEDED BY     : web/index.html loads it
CALLABLE      : not Python
### web/index.html   (215 lines, both builds)
WHAT IT DECIDES: The empty page the screens are drawn into, and the seven <template> blocks each step is cloned from.
IT NEEDS      : loads styles.css, app.js and the fonts
NEEDED BY     : nothing
CALLABLE      : not Python
### ripple/paths.py   (built from the kit only)
WHAT IT DECIDES: Where things are, whether Ripple is running from source or packaged.
IT NEEDS      : nothing else in Ripple
NEEDED BY     : ripple/api.py, ripple/store.py, run.py
CALLABLE      : web_dir(), data_dir()
### getfonts.py   (built from the kit only)
WHAT IT DECIDES: Fetches the two typefaces, once. Run it and never again.
IT NEEDS      : nothing else in Ripple
NEEDED BY     : nothing - it is run by hand, once
CALLABLE      : run as a program, not imported
### requirements.txt   (built from the kit only)
WHAT IT DECIDES: The pinned versions, so a second machine gets the same Ripple.
IT NEEDS      : nothing else in Ripple
NEEDED BY     : start-ripple.bat names it when nothing is installed yet
CALLABLE      : not Python
### start-ripple.bat   (built from the kit only)
WHAT IT DECIDES: Starting Ripple with a double-click, and finding the right Python.
IT NEEDS      : run.py
NEEDED BY     : nothing - it is the way in
CALLABLE      : not Python
### build.py   (built from the kit only)
WHAT IT DECIDES: Packaging the folder into a program you can hand to somebody.
IT NEEDS      : the whole project folder
NEEDED BY     : nothing - it is run by hand, last
CALLABLE      : run as a program, not imported

WHAT PEOPLE USUALLY WANT CHANGED, AND WHERE IT LIVES
Use this to check your answer, not instead of the catalogue -- a complaint that
is not on this list is ordinary, and the catalogue is what you reason from.

| Which folder is scanned, which SQL dialect, how many renames deep it follows, which folders are skipped, the biggest file it will open | `ripple/config.py` |
| Which table names count as the ones your team publishes | `ripple/production.py` |
| A file type Ripple should open and does not — .ipynb, .tf, .j2 | `ripple/scanner/repo.py` |
| SQL kept inside YAML, XML, a shell script or a Python file that is being missed | `ripple/scanner/repo.py` |
| A file held in OneDrive, or a path too long to open | `ripple/scanner/repo.py` |
| A {{ placeholder }} shape that is not being filled in | `ripple/scanner/templating.py` |
| A scripting block — BEGIN, FOR, IF, DECLARE — hiding the SQL underneath | `ripple/scanner/templating.py` |
| A statement the parser refuses, reported as unreadable | `ripple/scanner/rescue.py` |
| A rename that is not being followed | `ripple/scanner/sqlread.py` |
| A chain that stops one hop early, or never starts | `ripple/scanner/sqlread.py` |
| A usage that should count as breaking and does not | `ripple/scanner/sqlread.py` |
| A column usage Ripple does not notice at all — QUALIFY, PIVOT, a window clause | `ripple/scanner/sqlread.py` |
| The risk badge being wrong | `ripple/scanner/lineage.py` |
| Something missing from "what this result does not cover" | `ripple/scanner/lineage.py` |
| A published table that should have been found, or should not have been | `ripple/scanner/lineage.py` |
| "No impact" appearing where it should not | `ripple/scanner/lineage.py` |
| Wording in the summary or the reply letter | `ripple/narrative.py` |
| The email upload getting the tables, the date or the contact wrong | `ripple/notification.py` |
| Wording, layout, or any card on any screen | `web/app.js` |
| Colours, spacing, fonts, anything visual | `web/styles.css` |
| The version line on the settings screen | `ripple/build_info.py` |
| The progress line while you wait | `ripple/progress.py` |
| Saved analyses — what is kept, what the table shows | `ripple/store.py` |
| A new web address, or the shape of what one returns | `ripple/api.py` |
| The AI reader, or which model it uses | `ripple/ai.py` |
| Every screen is blank, the sidebar draws, and there is nothing in the browser console | `web/app.js` |
| Ripple will not start: ModuleNotFoundError naming one of its own files | `ripple/api.py` |
| A button that does nothing at all, with no error anywhere | `ripple/api.py` |
| The first screen is empty and /api/health answers 500 | `ripple/progress.py` |
| The typefaces never arrived, or the screens are in the wrong font | `web/styles.css` |
| It says nothing can be scanned until the published list is set | `ripple/production.py` |
| The trail stops after a few renames and says the chain ended | `ripple/config.py` |
| A file it could not read is not on the check-by-hand list | `ripple/scanner/lineage.py` |

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
it — `C:\ripple-build` if you followed BUILD-KIT.md. That folder is what "the
project root" means, here and everywhere else in the kit. TYPE THIS INTO THE
BLACK WINDOW, then press Enter:

```
cd /d C:\ripple-build
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
