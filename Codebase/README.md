# Ripple

When an upstream team changes a database column, someone has to work out which
of *our* tables and jobs break. Today that means hours of searching by hand, and
it is easy to miss something.

Ripple does the searching. A human still decides.

**It is a search assistant, not an answer machine.** Everything it finds is
shown with the file and the exact lines, so it can be checked. Everything it
*could not read* is shown too — a clean "no impact" is worthless if it quietly
skipped four hundred files.

---

## Run it on your own machine

You need Python 3.11 or newer. Nothing else.

```bash
python -m venv .venv
```

Then, on Windows:

```bash
.venv\Scripts\pip install -r requirements.txt
```

and start it:

```bash
.venv\Scripts\python run.py
```

Your browser opens at `http://localhost:8000`. That is the whole setup.

On Mac or Linux the two commands are `.venv/bin/pip install -r requirements.txt`
and `.venv/bin/python run.py`.

---

## What to try first

1. Press **Enter manually**, then **Fill with an example**, then **Run impact
   analysis**. No email and no AI needed — this is the shortest path to seeing
   it work.
2. Or drag `samples/01-market-code-value-change.eml` onto the upload box.
3. On the results screen, click a row to see the real code and the exact line.
4. Try `samples/02-timestamp-decommission.eml` — that one comes out **high
   risk**, because the column is the sort order inside a ranking and has no
   local fix.
5. Try `samples/03-no-impact.eml` — nothing in the repository uses it, and
   Ripple says so, while still listing where the name appeared.

---

## What it is scanning

`mockrepo/` is a made-up data pipeline. Nothing in it is real, and no company's
code or data is present anywhere in this project.

It was built to contain the awkward cases on purpose:

| In the mock repo | Why it is there |
|---|---|
| `market_code` → `mc` → `mkt_cd` | A column renamed twice. A word search finds only the first name. |
| `WHERE cp.mc = 'US'` | A filter on a literal. After a value change it matches nothing and the table silently empties. |
| `ROW_NUMBER() ... ORDER BY last_upd` | A ranking. Remove the column and the wrong row wins, with no error raised. |
| `SUBSTR(country_code, 1, 2)` | Assumes a two-character code. Longer values are silently truncated. |
| `legacy_dynamic_build.py` | Builds SQL by gluing strings together. Ripple cannot read it — and says so. |
| `sp_refresh_market.sql` | A stored procedure. Not parsed. |
| `broken_syntax.sql` | Malformed. Reported, not skipped. |
| `vw_everything.sql` | `SELECT *`, which hides which columns flow onward. |
| `prospect_master` | An upstream table nothing consumes, so "no impact" can be demonstrated. |

To point Ripple at different code, set `RIPPLE_REPO` (see Settings below).

---

## How it works

```
  the notification            the repository
        |                           |
        v                           v
  read the fields            index every file
  (AI, or matching                  |
   the catalogue)                   v
        |                    find every mention          <- fast text search
        v                           |
   YOU CONFIRM  ------------------->|
                                    v
                            read the SQL properly        <- sqlglot
                                    |
                                    v
                            follow each rename           <- up to 4 hops
                                    |
                                    v
                    group under the production table it feeds
                                    |
                                    v
                     summary + drafted reply  (AI, or written out)
```

The AI is only ever used at the two ends — reading the email, and writing the
English. **It is never shown your source code.** The scanning is ordinary,
repeatable Python, so it gives the same answer every run.

### Why parsing matters

A word search can tell you `MARKET_CODE` appears in a file. Only parsing can
tell you it appears *inside a WHERE clause comparing it to `'US'`* — which is
the difference between "mentioned here" and "this breaks on the 18th".

Every finding is labelled with what the code actually does with the column:

| Label | Meaning |
|---|---|
| Filter | Used in a `WHERE`. A value change stops it matching. |
| Join key | Joined on. If both sides do not change together, rows vanish silently. |
| Ranking | The sort order picking one row per key. Removing it is silent and awful. |
| Dedup key | A `MAX`/`MIN` deciding which row survives. |
| Transform | Reshaped by a function — length and format assumptions live here. |
| Aggregation | Grouped on, so labels split across old and new values. |
| Select | Carried straight through. Changes, but nothing depends on it. |

Whether a usage actually *breaks* depends on the kind of change, so Ripple asks
you which it is (removal, value format, data type, rename) and applies that.

---

## Settings

All optional. Set them as environment variables before starting.

| Variable | Default | What it does |
|---|---|---|
| `RIPPLE_REPO` | `./mockrepo` | The folder to scan. Point at a real checkout. |
| `RIPPLE_REPO_LABEL` | `mockrepo` | The name shown in the interface. |
| `RIPPLE_SQL_DIALECT` | generic | `bigquery`, `oracle`, `teradata`, `snowflake`, `hive`, `spark`, `postgres`, `mysql`, `tsql`, `redshift`, `databricks`, `presto`, `trino`, `duckdb`, `sqlite`. **Setting this correctly matters more than anything else here** — see below. |
| `RIPPLE_MAX_HOPS` | `4` | How many renames deep to follow a column. |
| `RIPPLE_PROD_TABLES` | `_PROD, _PRD, _PUBLISHED` | Which tables **your team publishes**. Paste the real list, one per line — Ripple reads it as written. A naming pattern still works alongside it: a word starting with an underscore matches the end of a table name, `*` matches anything (`PROD_*`, or `*` for every table). **This is the second setting that can turn a real finding into a calm-looking result** — see below. |
| `RIPPLE_REPO_URL_TEMPLATE` | empty | Link findings to your Git host, when reading a folder. Use `{path}` and `{line}`. On GitHub this is worked out for you. |
| `RIPPLE_AI_KEY` | empty | Turns the AI on. An OpenAI, Google Gemini or Groq key — Ripple works out which from the key itself. Without it everything still works. Can also be entered on the Settings screen. `OPENAI_API_KEY`, `GEMINI_API_KEY` and `GROQ_API_KEY` are read too. |
| `RIPPLE_AI_MODEL` | empty | Which model to use. Left empty, Ripple asks the provider what the key can use and takes the first it would choose. |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | Which model to call. Also choosable on the Settings screen. |
| `RIPPLE_DB` | `./ripple.db` | Where history is kept. On a serverless host this becomes `/tmp/ripple.db`, which does not survive. |
| `RIPPLE_MAX_UPLOAD_BYTES` | `25000000` | Biggest notification file accepted. Drops to `4000000` on a serverless host, which refuses more than that itself. |
| `RIPPLE_AI_TIMEOUT` | `45` | Seconds to wait for the model. Drops to `20` on a serverless host, where the whole request is killed at 60. |

To read a repository from GitHub rather than a folder:

| Variable | Default | What it does |
|---|---|---|
| `RIPPLE_REPO_SOURCE` | `folder` | Set to `github` to connect on start-up instead of reading a folder. |
| `RIPPLE_GITHUB_REPO` | empty | `owner/repository`, or the address copied from GitHub. |
| `RIPPLE_GITHUB_BRANCH` | empty | Blank uses the repository's default branch. |
| `GITHUB_TOKEN` | empty | A personal access token with **read** access. `RIPPLE_GITHUB_TOKEN` works too. |
| `RIPPLE_MAX_REPO_BYTES` | `60000000` | The largest compressed repository Ripple will pull in one go. Drops to `25000000` on a serverless host, where a request is killed after 60 seconds. |

Example, on Windows:

```bash
set RIPPLE_SQL_DIALECT=teradata && set RIPPLE_AI_KEY=your-key-here && .venv\Scripts\python run.py
```

The **Settings & checks** screen inside Ripple shows what it is connected to and
has a *Test the key* button, so a bad key is obvious immediately rather than at
the worst moment. It also shows which dialect is in use, because that one is
easy to leave wrong.

---

## Why the SQL dialect is the setting that matters

Leaving it unset does not degrade the answer politely. It can invert it.

A small BigQuery pipeline is kept in the tests. It uses nothing exotic — a
`QUALIFY`, a `SELECT * EXCEPT`, an `UNNEST`, a `MERGE`, and table names written
the BigQuery way with backticks and a project prefix. Run against it:

| | dialect unset | `RIPPLE_SQL_DIALECT=bigquery` |
|---|---|---|
| Files parsed | 2 of 5 | 5 of 5 |
| Tables learned | 0 | 3 |
| Production tables affected | 0 | 1 |
| Verdict | **No impact** | **Medium risk, 2 breaking usages** |

The unset run is not a smaller answer. It is the opposite answer, and it is
wrong. Ripple does report the files it could not read, so the evidence is on
screen — but a "no impact" headline is what gets remembered.

Set it once, and check the Settings screen agrees.

---

## The other setting that can flatten a real result

`RIPPLE_PROD_TABLES` says which tables *your team publishes*. It decides one
thing: whether a finding counts as **production impact**, which is what the
headline, the risk level and the drafted reply are all built from.

**The best answer is the list itself.** Paste the real table names into the box
on the Settings screen — one per line, or however they arrive from Excel, Slack,
Confluence or a query result. Bullets, numbering, backticks, code fences,
quotes, heading rows, trailing commas, duplicates, mixed capitalisation, and
fully qualified names next to bare ones are all read without being tidied up
first. A paste from Excel with several columns has the column holding the table
names picked out, and the screen says which one it took.

Then it says what it did, because a silently misread list here is worse than no
list at all: how many names it recognised, what it ignored and why, and — the
one that matters — **which of the tables on your list it has never seen anywhere
in the repository**. Paste fifty and have six come back unknown, and those six
are either misspelled or built somewhere Ripple could not read. Either way a
clean result for them means nothing until that is settled.

A naming pattern still works exactly as it did, alongside the list, so nothing
already set breaks. It ships as `_PROD, _PRD, _PUBLISHED`, because that is a
common convention and there is no way to guess. Point Ripple at a repository
whose published tables end `_umdl`, `_gdi`, `_final` or anything else, and every
real finding is still found, still listed and still counted — but nothing is
*called* production impact, so the top of the report reads far calmer than the
truth.

Ripple no longer hides those findings behind that. When a chain ends at a table
the rule does not match, the table is listed under **Chain ends here**, the rule
is quoted beside it, and the summary says the assessment is unfinished rather
than clean. Correcting the rule and scanning again turns them into production
tables — nothing else changes.

How each entry is read, and it is the same rule in all three places the setting
can be given:

| What you write | How it is matched |
|---|---|
| `cust360_customer_demographics` | that table, exactly |
| `foundation.cust360_customer_demographics` | the same table — SQL only ever says the last part of a name, so the qualifier is shown back but not matched on |
| `_PROD` | the **end** of a name: matches `sales_prod` |
| `PROD_*` | the whole name, with `*` standing for anything: matches `prod_sales` |
| `*` | every table is published — the safe setting if you are not sure |

An entry that is a real table name is matched exactly, so a staging copy called
`stg_sales_daily` is *not* counted as the published `sales_daily`. If a name on
your list matches nothing but is the ending of tables that do exist, Ripple says
so and asks whether you meant it as a pattern, rather than quietly deciding for
you.

---

## SQL that is really a template

Very little production SQL is plain SQL. Airflow, dbt and in-house generators
write the project and dataset names as placeholders that are filled in before a
database ever sees the file:

```sql
CREATE OR REPLACE TABLE {{tgt_project_id}}.{{stage_dataset}}.web_activity AS ...
```

A SQL parser refuses that outright, and refuses the whole file with it. On a
repository written this way that meant almost every file landing in "could not
read" — and a scan over a repository that was never read reports no impact,
confidently, on a change that breaks things.

Ripple fills the placeholders in with ordinary names before parsing, on a copy;
the file itself is never touched and every line number still points where it
did. `{{ ... }}`, `{% ... %}`, `{# ... #}`, `${ ... }` and Python's `{name}` are
all handled, and dbt's `ref('orders')` resolves to `orders`, because that is
what it means.

Three more things changed with it:

* **`BEGIN` no longer eats the statement after it.** Real pipeline files are
  wrapped in `DECLARE … BEGIN … END;`. `BEGIN` has no semicolon of its own, so a
  parser that does not know the keyword takes the next statement as part of it
  and hands back one blob it cannot read. Nothing errors, the file "parses", and
  the *first real statement of every file* is gone. Scripting keywords — `BEGIN`,
  `END`, `IF … THEN`, `ELSE`, `EXCEPTION WHEN … THEN`, `FOR … DO`, transaction
  markers — are now dropped before parsing, and a loop keeps the query in its
  header so the table it reads is still seen.
* **One bad statement costs one statement.** A file is retried statement by
  statement, so a `GRANT`, a procedure call or one line in another dialect no
  longer takes the other thirteen statements down with it. The gap then reads
  *"1 of 14 statements in this file could not be read"*.
* **The gap says where.** Every entry in "check by hand" now carries the line
  number and the line itself, so the file can be opened at the right place
  instead of hunted through.

---

## When the name is somewhere no parser can follow

Some references genuinely cannot be traced, however good the parsing is:

```sql
SET tag = `proj`.ds.get_sde_tag('home_phone_no', 'customer_demographics');
EXECUTE IMMEDIATE FORMAT("""INSERT INTO %s SELECT home_phone_no FROM %s""", a, b);
CALL `proj`.ds.refresh('proj.ds.customer_demographics', NULL, out);
```

The column and the table are **quoted strings** handed to a helper, or SQL built
as text and run later. Ripple cannot turn any of that back into lineage — and it
used to file those files under *"mentions the name but carries it nowhere"*,
which reads as a reassurance and is the exact opposite of the truth.

They now go in the **check by hand** list, with the line and the line itself, and
a sentence saying which of the two it is. A file that only mentions the name in a
comment still goes in the quiet list, because a list that flags everything is
ignored within a week.

**`DELETE` and `UPDATE` are read too.** They build nothing, so they look
uninteresting — but `DELETE FROM stage WHERE market_code = 'US'` stops working
the day the column goes, the pruning silently stops, and the table fills up.
Their `WHERE` clauses used to be invisible.

---

## Reading a repository from GitHub

Step 3 can read straight from GitHub instead of from a folder. Choose **GitHub**
on that screen, enter `owner/repository`, and connect.

* A **public** repository needs no token.
* A **private** one needs a personal access token with read access — nothing
  more. Ripple never writes.

Create one on GitHub under *Settings → Developer settings → Personal access
tokens*. A fine-grained token needs **Contents: Read-only**, and must list the
repository you want scanned. A classic token needs the `repo` scope.

**Where the token goes.** Typed into the screen, it is sent to GitHub and held
in the running server's memory. It is never written to disk, never logged, and
never sent back to the browser. Restart the server and you enter it again.

For anything hosted, set `GITHUB_TOKEN` as an environment variable instead, so
it survives restarts and is never typed into a page. On a serverless host such
as Vercel this is the only way that works reliably, because each request can
land on a fresh instance with no memory of the last one.

Ripple downloads the repository as a single archive — one request rather than
one per file — reads it in memory, and keeps only the file types it can scan.
Nothing is written to your repository, and nothing is cloned to disk.

Once connected, each finding gets an **Open in GitHub** link pointing at the
exact commit Ripple read, so the line you are sent to is the line it saw, not
whatever the branch has moved on to since.

---

## Turning the AI on

Ripple works with no AI at all — that is deliberate, not a limitation. With a
key it reads messier emails more reliably and writes better English.

Three providers are supported, and there is **one box**, not three. Which
company issued a key is worked out from the key itself, because asking is one
more thing to get wrong — and a key sent to the wrong company comes back
rejected, which reads as "your key is bad" when it is not.

| Provider | Key looks like | Get one at |
|---|---|---|
| OpenAI | `sk-…`, `sk-proj-…` | <https://platform.openai.com/api-keys> |
| Google Gemini | `AIza…` | <https://aistudio.google.com/apikey> |
| Groq | `gsk_…` | <https://console.groq.com> |

1. Get a key from any of them.
2. Open **Settings & checks** and paste it into *API key*. The screen names the
   provider as you type, before anything is sent anywhere. Press *Turn the AI
   on*. Or set `RIPPLE_AI_KEY` before starting, which survives restarts.
3. A model list appears once the key is accepted. It is **asked of the
   provider**, not written down here — a list in the code is wrong within
   months and then offers a model that no longer exists. Ripple picks the one
   it would choose; change it if you want another.
4. Press *Test the key* whenever you want proof it still works.

A key from a provider Ripple cannot use is named rather than guessed at: an
Anthropic key begins `sk-` exactly as an OpenAI one does, and read as OpenAI it
would be sent to the wrong company and rejected.

The key is treated exactly like the GitHub token: it is held in the running
process, never written to disk, never logged, and never sent back to the page.
There is a test that fails if it ever appears in a response.

Turning it on is not taken on trust. Ripple calls the model there and then, and
refuses a key the provider rejects rather than storing it and failing later —
and it says so in a sentence, not a page of the provider's JSON.

### Which model

| Model | When |
|---|---|
| **GPT-OSS 120B** | Default. Best at pulling names out of a messy forwarded email. |
| Llama 3.3 70B | A solid all-rounder, slightly quicker. |
| GPT-OSS 20B | Lighter and faster. Fine for tidy notifications. |
| Llama 3.1 8B | Fastest. Misses fields in awkward emails — check its answers. |

Only Groq's production models are offered. Preview models get withdrawn without
notice, and a model that disappears mid-demonstration is worse than one that is
merely adequate. Change the default with `GROQ_MODEL`.

**Before using this on anything real, read this.** Turning the AI on sends the
notification text and the findings — table names, system names, colleagues'
names — to Groq's servers. Being *able* to make the call is not the same as
being *allowed* to send that data. If in doubt, leave the key unset and use
manual mode; nothing is lost except some polish in the wording.

**And on a shared copy, read this too.** A key typed into the screen belongs to
that running copy, not to you. If the copy is reachable by other people — as any
hosted one is — they are spending your allowance for as long as it is loaded.
The Settings screen says so on a hosted copy. For anything but a demonstration,
run Ripple on your own machine, or set the key as an environment variable on the
host rather than typing it into a public page.

---

## Putting it online, free

The project is set up for Vercel's free tier, which gives a real HTTPS address
and redeploys every time you push to `main`.

1. At <https://vercel.com> choose *Add New → Project* and pick this repository.
2. Set the **Root Directory** to `Codebase`. This is the only setting that must
   be changed by hand — everything else is detected. Leave the build and output
   settings empty; the install command should read `pip install -r
   requirements.txt` on its own.

   Vercel finds the app on its own because `api/index.py` is one of the
   entrypoints it looks in and exports a variable called `app`. Because that is
   a whole FastAPI application rather than a lone function, Vercel sends **every**
   request to it and lets Ripple's own routing decide — so no redirect or rewrite
   rules are needed, and none are configured.
3. Under *Environment Variables*, add whichever of these you want:
   * `RIPPLE_AI_KEY` — turns the AI on. An OpenAI, Google Gemini or Groq key;
     Ripple works out which from the key. Leave it out and Ripple still works;
     every screen simply says the rules wrote it rather than a model.
   * `GITHUB_TOKEN` — lets Ripple read a **private** repository. Public ones
     need no token. Set it here rather than typing it into the screen: each
     request can land on a fresh machine, so a token typed into the page will
     not last.
   * `RIPPLE_REPO_SOURCE=github` and `RIPPLE_GITHUB_REPO=owner/repository` — to
     connect to that repository on start-up instead of reading the sample folder.
   * `RIPPLE_SQL_DIALECT` — set this to match the repository you point it at
     (`bigquery`, `teradata`, `oracle`…). Leave it out and the answer can be
     wrong rather than merely vaguer; see *Why the SQL dialect is the setting
     that matters* above.
4. Deploy.

### What a hosted copy does differently

A serverless host is not a laptop, and Ripple says so on screen rather than
promising otherwise. It detects the host automatically and changes four things:

| | On your machine | Hosted |
|---|---|---|
| Saved history | Kept in `ripple.db`, permanent | **Does not survive.** The machine behind the site is replaced constantly and takes saved rows with it. Both the save confirmation and the *Past analyses* screen say so. |
| Biggest email upload | 25 MB | **4 MB.** The host refuses a bigger request body before Ripple sees it, so the limit shown is the real one. Pasting the text has no such limit. |
| Biggest repository pulled from GitHub | 60 MB compressed | **25 MB.** A request is killed after 60 seconds, so a clear "too big for this host" beats a blank timeout. |
| Wait for the AI model | 45 seconds | **20 seconds.** Writing a summary calls the model twice in a row; both have to finish inside the 60-second cap, or the page dies with nothing on it. |

Everything else is the same: reading a notification, scanning, the dependency
map, the summary, the drafted reply, and connecting to GitHub.

Two more things worth knowing. The first request after a quiet spell is slow,
because the machine is starting from cold and reading the repository again — a
few seconds for the bundled sample, longer for a real repository. And if you
want history that lasts, or a big repository scanned, run Ripple on a normal
server instead; nothing in the code has to change.

---

## Tests

```bash
.venv\Scripts\python -m pytest tests -q
```

109 tests. Most of them exist to prove Ripple is *honest* rather than that it is
clever — that unreadable files are reported, that a clean result still says
where the name appeared, that a generic word like `STATUS` does not produce a
page of false hits, that an access token never comes back out of the app in any
response, and that a hosted copy admits saved history will not survive instead
of letting the word "Saved" stand on its own, that an AI key never comes back
out of the app any more than a GitHub token does, and that a BigQuery pipeline read
as generic SQL is caught rather than quietly reported as harmless. None of them
touch the network: the GitHub tests build the archive GitHub would send and feed
it in directly.

---

## The files

```
run.py              start it locally
api/index.py        start it on Vercel (same app)
vercel.json         how long the hosted copy may run, and how assets are cached
.vercelignore       what a hosted copy does not need
.python-version     pins Python 3.12, so a host cannot change it underneath us
ripple/
  config.py         every setting, in one place
  api.py            the web routes - deliberately thin
  catalog.py        what tables and columns exist, learned from the code
  notification.py   reading .msg / .eml / pasted text, and pulling out fields
  ai.py             the optional AI calls, with fallbacks
  narrative.py      the summary and reply, written without AI
  store.py          history (SQLite)
  scanner/
    repo.py         walking a folder and searching it
    github.py       reading a repository from GitHub with an access token
    templating.py   filling in {{ ... }} placeholders so real pipeline SQL parses
    sqlread.py      parsing SQL and classifying how a column is used
    lineage.py      following renames, and grouping by production table
web/                the interface - plain HTML, CSS and JavaScript, no build step
mockrepo/           the synthetic pipeline being scanned
samples/            example notification emails
tests/              the test suite (hosting and BigQuery have their own files)
```

There is no build step and no framework anywhere in `web/`. That is on purpose:
it can be opened, read and changed by anyone, including in an environment where
installing tooling is difficult.

---

## Running it where there is no internet

There is a second edition, in `../Ripple Offline`, for a locked-down machine
with no network at all: one folder to copy across, double-click, no Python and
no install. Download it from
**<https://github.com/aucksy/Ripple/releases/latest>** — the version is in the
filename, and only the newest release is kept. The repository folder and the SQL dialect are asked for on screen
instead of being environment variables, and the GitHub source and the AI key
form are not merely switched off — they are deleted from the build, along with
the HTTP client they would need.

It is **not a fork**. It has no copy of `ripple/` and no copy of `web/`: its
build script reads both out of this folder, so it is always built from whatever
this version is today. In `web/app.js`, the blocks between `//<online-only>` and
`//</online-only>` are the ones removed from that build. Deleting those lines has
to leave working JavaScript, which is why each block is written to read
correctly with its marked lines gone.

Moving a marker is safe. Losing one is caught: the offline build searches what it
produced for the words that should be gone and fails with the line it found,
rather than shipping a key box onto a machine where nobody can check it.

---

## Known limits

Worth saying out loud, because a tool like this is dangerous when it looks more
certain than it is.

- **It reads one repository.** Lineage that crosses into another team's code is
  invisible to it. What you get is *your* exposure, not the whole blast radius.
- **SQL built by gluing strings together cannot be followed**, and neither can a
  column or table name handed to a helper as a quoted string. Both are listed
  under *check by hand*, with the line — but they are a real hole, and the list
  is only useful if somebody actually reads those lines.
- **Stored procedure bodies are not parsed.** A `CALL` that passes a table name
  as a string shows up under *check by hand* when that table is being scanned
  for, and is invisible otherwise.
- **A loop is not followed**, only the query in its header. What the body does
  once per row is beyond this.
- **`SELECT *` hides which columns flow onward.**
- **A job writing to several tables** cannot be attributed reliably, so lineage
  stops there — and says so.
- **Which tables count as "production" is a naming rule you set**
  (`RIPPLE_PROD_TABLES`, or the settings screen in Ripple Offline). Ripple ships
  expecting `_PROD`. Point it at a repository that names nothing `_PROD` and no
  finding will be *called* production impact — every table the change reaches is
  still listed, with the rule quoted beside them, but the headline and the risk
  level follow the rule. Check it before you trust a calm answer.
- **Columns are matched by name.** Two different tables using the same column
  name can produce a finding that needs a human to dismiss.
- **The SQL dialect must be set correctly**, and it is the one setting that can
  turn a real finding into a silent "no impact". See below.
