"""Filling in the placeholders that pipeline SQL is written with.

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
"""
from __future__ import annotations

import re

# {# a comment #} -- carries nothing, and never should reach the parser.
_COMMENT = re.compile(r"\{#.*?#\}", re.DOTALL)

# {% if ... %} ... {% endif %} -- control flow, not values. The tags go and the
# SQL between them stays. That is right for the common "optional WHERE clause"
# shape; where a file uses if/else to pick between two different statements the
# result will still not parse, and it is reported like any other file that did
# not parse rather than guessed at.
_TAG = re.compile(r"\{%-?.*?-?%\}", re.DOTALL)

# {{ project }} and {{ params.run_date | upper }} -- the usual case by far.
_VAR = re.compile(r"\{\{-?\s*(?P<body>.*?)\s*-?\}\}", re.DOTALL)

# ${project} -- shell, Databricks and older Airflow jobs. sqlglot does not
# refuse these outright; it quietly gives up on the statement and hands back
# something with no tables in it, which is worse, because nothing says so.
_DOLLAR = re.compile(r"\$\{\s*(?P<body>[^{}\n]*?)\s*\}")

# {dataset} -- Python's own .format() and f-strings, which is how a great many
# Airflow DAGs build their SQL. Deliberately narrow: the body has to look like
# a name, so a regular expression's {3} or {2,4} inside a string literal is
# left alone.
_BRACE = re.compile(r"\{(?P<body>[A-Za-z_][A-Za-z0-9_.\[\]'\"]{0,60})\}")

# dbt names a real table inside the placeholder: ref('orders') is the orders
# model. Taking that name is not a guess -- it is the whole point of ref().
_DBT = re.compile(r"^\s*(?:ref|source)\s*\(", re.IGNORECASE)
_QUOTED = re.compile(r"""['"]([A-Za-z_][A-Za-z0-9_]*)['"]""")

# {{ config(materialized='table') }} -- and its siblings. These are instructions
# to dbt, not values. Every dbt model in the world opens with one, and turning it
# into a bare identifier puts a word where SQL expects a keyword, so the WHOLE
# FILE stops parsing: not one table, not one column, nothing. Measured: adding a
# config header to a readable dbt model took it from a full chain to 100%
# unreadable. They carry nothing, so they leave nothing behind.
_DBT_DIRECTIVE = re.compile(
    r"^\s*(?:config|set|test|macro|endmacro|snapshot|endsnapshot|do|print|log)\s*\(",
    re.IGNORECASE,
)

_ANY = (_COMMENT, _TAG, _VAR, _DOLLAR, _BRACE)


def has_placeholders(text: str) -> bool:
    """Is there any templating in here at all?"""
    return any(p.search(text) for p in _ANY)


def describe(text: str) -> str:
    """What kind of templating this is, in words, or '' if there is none.

    Used to explain a file that still could not be read, so the answer on
    screen is "this file is a template" rather than a parser's exception name.
    """
    found: list[str] = []
    if _COMMENT.search(text) or _TAG.search(text) or _VAR.search(text):
        found.append("{{ ... }} templating (Airflow, dbt or similar)")
    if _DOLLAR.search(text):
        found.append("${ ... } placeholders")
    if _BRACE.search(text):
        found.append("{ ... } placeholders filled in by Python")
    return " and ".join(found)


def _identifier(body: str) -> str:
    """A plain SQL identifier standing in for one placeholder."""
    body = body.strip()
    if _DBT_DIRECTIVE.match(body):
        return ""                     # {{ config(...) }} -- an instruction, not a name
    if _DBT.match(body):
        names = _QUOTED.findall(body)
        if names:
            return names[-1]          # source('raw', 'orders') -> orders
    body = body.split("|")[0]         # drop Jinja filters: {{ x | upper }}
    name = re.sub(r"[^A-Za-z0-9_]+", "_", body).strip("_")
    if not name:
        name = "placeholder"
    if name[0].isdigit():
        name = "p_" + name
    return name[:60]


def _keep_lines(text: str) -> str:
    return "\n" * text.count("\n")


def _blank(m: "re.Match[str]") -> str:
    return _keep_lines(m.group(0))


def _named(m: "re.Match[str]") -> str:
    return _identifier(m.group("body")) + _keep_lines(m.group(0))


def placeholder_names(text: str) -> set[str]:
    """The identifiers ``fill_placeholders`` would put in, upper case.

    A placeholder is not a name. It is a hole where a name goes, and nothing in
    the file says what fills it. One file writes a table as
    ``{{tgt_project_id}}.{{stage_dataset}}.card_guid_umdl`` and the DAG that
    reads it writes ``{{ params.src }}.raw.card_guid_umdl`` -- "stage_dataset"
    and "raw" are not two datasets, one of them is a hole.

    Knowing which words came out of a hole is what stops Ripple deciding that
    two names are two different tables on the strength of the placeholder
    somebody happened to type. Getting that wrong cuts a real chain in half and
    reports no impact, which is the one answer this tool exists to prevent.
    """
    out: set[str] = set()
    for pattern in (_VAR, _DOLLAR, _BRACE):
        for m in pattern.finditer(text):
            name = _identifier(m.group("body"))
            if name:
                out.add(name.upper())
    return out


def fill_placeholders(text: str) -> str:
    """The same SQL with every placeholder replaced by a name that parses."""
    out = _COMMENT.sub(_blank, text)
    out = _TAG.sub(_blank, out)
    out = _VAR.sub(_named, out)
    out = _DOLLAR.sub(_named, out)
    return _BRACE.sub(_named, out)


# ── scripting blocks ───────────────────────────────────────────────────────
# Every file in a real BigQuery pipeline is wrapped in DECLARE ... BEGIN ...
# END, often with a FOR loop or an IF inside it. A SQL parser does not know
# those keywords, hands back "BEGIN" as something it cannot read -- and, because
# BEGIN has no semicolon of its own, swallows the statement that follows it.
#
# That is the quietest possible failure: the file parses, the reader reports no
# problem, and the FIRST REAL STATEMENT OF EVERY FILE has vanished. In a
# repository where every file opens with BEGIN, that is most of the lineage.
#
# These keywords carry no lineage themselves, so they are replaced with an empty
# statement, on the copy going into the parser, keeping every line where it was.
#
# Two of them are only scripting some of the time, which is why this is a scan
# and not a line-by-line regular expression. ``ELSE`` and a bare ``END`` are also
# how an ordinary CASE expression is written across several lines::
#
#     CASE WHEN status = 'A' THEN 'Active'
#     ELSE
#       'Unknown'
#     END AS status_desc
#
# Cutting those two lines out puts a semicolon in the middle of a CASE, which
# breaks the statement they sit in -- a 600-line CREATE TABLE thrown away whole,
# with every table and column in it. So CASE is counted as the file is walked,
# and those two words are only treated as scripting when no CASE is open.
_ALWAYS_SCRIPTING = re.compile(
    r"""^\s*(?:
          BEGIN(?:\s+TRANSACTION)?
        | END\s+(?:IF|FOR|WHILE|LOOP)
        | (?:COMMIT|ROLLBACK)(?:\s+TRANSACTION)?
        | EXCEPTION\s+WHEN\s+.+?\s+THEN
        | LOOP
        | (?:LEAVE|ITERATE|BREAK|CONTINUE)\b.*
      )\s*;?\s*$""",
    re.IGNORECASE | re.VERBOSE,
)
# Scripting only while no CASE is open. See the note above.
_SCRIPTING_UNLESS_CASE = re.compile(
    r"""^\s*(?:
          END
        | ELSE
        | (?:ELSE\s*)?IF\b.*?\bTHEN
      )\s*;?\s*$""",
    re.IGNORECASE | re.VERBOSE,
)

# RAISE USING MESSAGE = @@error.message
#
# The last line of the exception handler every generated file in a BigQuery
# pipeline ends with, and by a distance the commonest thing a parser refuses. It
# re-throws an error; it reads no table and touches no column, so it is nothing
# to a scan -- but one of them is enough to put the file on the "check by hand"
# list, and a list padded with hundreds of files nobody needs to check is a list
# nobody reads. It can run past the end of its line, so it is consumed up to its
# semicolon rather than matched a line at a time.
_RAISE = re.compile(r"^\s*RAISE\b", re.IGNORECASE)

# CREATE OR REPLACE PROCEDURE `prj.foundation.refresh`(IN tbl STRING, ...)
#
# The signature, which no SQL parser reads, wrapped around a BEGIN ... END body
# that is ordinary SQL. Dropping the signature is what lets the body be read.
_PROCEDURE = re.compile(
    r"^\s*CREATE\s+(?:OR\s+REPLACE\s+)?PROCEDURE\b", re.IGNORECASE
)

# BEGIN followed by the body on the SAME line, which _ALWAYS_SCRIPTING cannot
# match because it wants BEGIN alone. TRANSACTION is left to that one -- it
# opens a transaction rather than a block, and has no body to keep.
_INLINE_BEGIN = re.compile(r"^\s*BEGIN[ \t]+(?!TRANSACTION\b)(?=\S)", re.IGNORECASE)

# A loop header names a real table. Keeping the query inside it costs one line
# and is the difference between seeing that table read and not. The header is
# often written across several lines, with the DO on its own, so it is gathered
# rather than matched.
_LOOP_HEADER = re.compile(
    r"^\s*(?:FOR\s+(?P<var>\w+)\s+IN|WHILE)\s*(?P<q>\(.*\))\s*(?:DO|LOOP)\s*$",
    re.IGNORECASE)
_LOOP_START = re.compile(r"^\s*(?:FOR\s+\w+\s+IN|WHILE)\b", re.IGNORECASE)
_LOOP_PLAIN = re.compile(r"^\s*(?:FOR|WHILE)\b.*\b(?:DO|LOOP)\s*$", re.IGNORECASE)
_LOOP_END = re.compile(r"\b(?:DO|LOOP)\s*$", re.IGNORECASE)

# A whole loop written on ONE line:
#     FOR rec IN (SELECT tbl FROM cfg_tables) DO SELECT 1; END FOR;
# _LOOP_START matches it and _LOOP_END does not (the line ends with END FOR, not
# with DO), so it used to go to _gather_loop -- which then looked for a line
# ending in DO, never found one, and gave back "everything to the end of the
# file". Measured: every line after it became an empty statement, silently. No
# parse error, no unreadable entry, nothing on any screen: the trail simply
# stopped one table short and reported that as where the chain ends.
_ONE_LINE_LOOP = re.compile(
    r"^(?P<lead>\s*)(?:FOR\s+(?P<var>\w+)\s+IN|WHILE)\s*(?P<q>\(.*\))\s*(?:DO|LOOP)\b"
    r"(?P<body>.*?)(?:\bEND\s+(?:FOR|WHILE|LOOP)\s*;?\s*)?$",
    re.IGNORECASE,
)


# FOR rec IN (SELECT id, cm13 AS seg FROM customer_demographics) DO
#   INSERT INTO final_published (id, seg) VALUES (rec.id, rec.seg);
# END FOR;
#
# The header was rewritten to a read with no target, and the INSERT in the body
# has no source of its own, so the two halves of ONE statement never joined up.
# Measured: groups [], over a loop that really does load the published table --
# and the finding's own text said "into the next table" while naming no next
# table at all.
#
# The loop variable is what joins them, so the header keeps it: the rows the
# loop walks are a thing with a name, exactly like a temporary table, and the
# name is written on the very line the row points at. Fenced to this file by
# _scope_session_tables, the same as any other temporary. WHILE has no variable
# and is left as the plain read it always was.
def _loop_read(var: str | None, query: str) -> str:
    if not var:
        return f"SELECT * FROM {query};"
    return f"CREATE TEMP TABLE {var} AS SELECT * FROM {query};"

# The condition of an IF or a WHILE, when it is a query.
#
#     IF (SELECT MAX(cm13) FROM customer_demographics) IS NOT NULL THEN
#
# That line READS the table, and the whole header was being replaced with an
# empty statement -- so the read went with it and the file came back with
# nothing at all: risk none, no findings, no gap reported. Written as an ASSERT
# instead, the identical guard is read correctly, which is how this was found.
# The condition is a scalar expression rather than a table, but a subquery in a
# FROM is exactly what it is: one read of one table, building nothing.
_HAS_SELECT = re.compile(r"\bSELECT\b", re.IGNORECASE)


def _condition_query(line: str) -> str:
    """The first bracketed group in this line that holds a SELECT, or ""."""
    if not _HAS_SELECT.search(line):
        return ""
    depth = 0
    start = -1
    quote = ""
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = ""
            continue
        if ch in "'\"`":
            quote = ch
        elif ch == "(":
            if depth == 0:
                start = i
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0 and start >= 0:
                group = line[start:i + 1]
                if _HAS_SELECT.search(group):
                    return group
                start = -1
            depth = max(0, depth)
    return ""


def _kept_read(line: str) -> str:
    """A scripting line replaced by the read it contains, or by nothing."""
    group = _condition_query(line)
    return f"SELECT * FROM {group};" if group else ";"


_CASE_OR_END = re.compile(r"\b(CASE|END)\b", re.IGNORECASE)
# Nothing to hide a keyword behind, so the line can be read as it stands.
_NEEDS_STRIPPING = re.compile(r"""['"`]|--|/\*|\#""")


def _code_only(line: str, state: dict) -> str:
    """The line with string literals and comments blanked out.

    A keyword inside a quoted string is not scripting, and a 600-line statement
    is exactly where a stray ``'... END ...'`` turns up. ``state`` carries what
    is still open when the line ends, because both can run across lines.
    """
    if not state["quote"] and not state["comment"] and not _NEEDS_STRIPPING.search(line):
        return line
    out: list[str] = []
    i, n = 0, len(line)
    while i < n:
        ch = line[i]
        if state["comment"]:
            if line.startswith("*/", i):
                state["comment"] = False
                out.append("  ")
                i += 2
            else:
                out.append(" ")
                i += 1
        elif state["quote"]:
            q = state["quote"]
            if ch == "\\" and q != "`":
                out.append("  ")
                i += 2
            elif line.startswith(q, i):
                state["quote"] = ""
                out.append(" " * len(q))
                i += len(q)
            else:
                out.append(" ")
                i += 1
        elif line.startswith("/*", i):
            state["comment"] = True
            out.append("  ")
            i += 2
        elif line.startswith("--", i) or ch == "#":
            out.append(" " * (n - i))
            i = n
        elif line.startswith('"""', i) or line.startswith("'''", i):
            state["quote"] = line[i : i + 3]
            out.append("   ")
            i += 3
        elif ch in "'\"`":
            state["quote"] = ch
            out.append(" ")
            i += 1
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def _case_depth_after(code: str, depth: int) -> int:
    """How many CASE expressions are still open once this line has been read."""
    for m in _CASE_OR_END.finditer(code):
        if m.group(1).upper() == "CASE":
            depth += 1
        elif depth > 0:
            depth -= 1
    return depth


def unwrap_blocks(text: str) -> str:
    """The same SQL with scripting keywords replaced by empty statements.

    Returns the text unchanged when there is no scripting in it, so callers can
    hand everything to this rather than asking ``has_blocks`` first. Asking
    first meant walking every line of every file twice, which on a repository of
    a few thousand files is minutes rather than seconds.
    """
    lines = text.splitlines()
    state = {"quote": "", "comment": False}
    out: list[str] = []
    depth = 0          # CASE expressions currently open
    skip_until = -1    # index of the last line of a multi-line thing being dropped
    changed = False

    for n, line in enumerate(lines):
        code = _code_only(line, state)
        if n <= skip_until:
            out.append(";")
            changed = True
            continue

        # A RAISE, or a procedure signature: neither is readable, both can run
        # past the end of their line, and neither carries a table or a column.
        if depth == 0 and (_RAISE.match(code) or _PROCEDURE.match(code)):
            skip_until = _end_of_run(lines, n, state.copy(),
                                     signature=bool(_PROCEDURE.match(code)))
            out.append(";")
            changed = True
            continue

        if _LOOP_HEADER.match(code):
            # Detected on the blanked copy so a keyword in a string cannot
            # trigger it, but read back off the line as written -- the table
            # being looped over is normally a quoted name, and the blanked copy
            # no longer has it.
            loop = _LOOP_HEADER.match(line) or _LOOP_HEADER.match(code)
            out.append(_loop_read(loop.group("var"), loop.group("q")))
            changed = True
            continue
        if _LOOP_START.match(code) and not _LOOP_END.search(code):
            # A whole loop on one line first: it looks like a header that has
            # not finished, and treating it as one swallowed the rest of the
            # file. See _ONE_LINE_LOOP.
            whole = _ONE_LINE_LOOP.match(line) or _ONE_LINE_LOOP.match(code)
            if whole is not None:
                out.append(f"{whole.group('lead')}"
                           f"{_loop_read(whole.group('var'), whole.group('q'))} "
                           f"{whole.group('body').strip()}")
                changed = True
                continue
            body, skip_until = _gather_loop(lines, n, state.copy())
            out.append(body)
            changed = True
            continue
        if _ALWAYS_SCRIPTING.match(code):
            out.append(";")
            changed = True
            continue
        # BEGIN with the first statement of the body on the SAME line. The
        # check above wants BEGIN alone on its line, which is how a procedure
        # is normally written -- but written on one line the whole body went to
        # the parser as part of the BEGIN and came back as a single Command
        # nobody could read. Measured: a procedure whose body loads a published
        # table produced NO statement at all, so the table it builds was known
        # to Ripple nowhere, and the scan reported no lineage to production.
        # The keyword is swapped for a statement end, so the body behind it is
        # read and the line numbers stay exactly as they are in the file.
        inline = _INLINE_BEGIN.match(code)
        if inline:
            out.append(";" + line[inline.end():])
            depth = _case_depth_after(code[inline.end():], depth)
            changed = True
            continue
        # A WHILE or an IF header. Whatever it tests is a READ, and replacing
        # the line outright threw it away -- see _condition_query.
        if _LOOP_PLAIN.match(code):
            out.append(_kept_read(line))
            changed = True
            continue
        if _SCRIPTING_UNLESS_CASE.match(code) and depth == 0:
            out.append(_kept_read(line))
            changed = True
            continue

        out.append(line)
        depth = _case_depth_after(code, depth)

    if not changed:
        return text
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")


def _end_of_run(lines: list[str], start: int, state: dict, signature: bool) -> int:
    """The last line of a statement that has to be dropped whole.

    A RAISE ends at its semicolon. A procedure signature ends when its brackets
    close, or at the BEGIN that starts its body -- and the body is left alone,
    because the body is the SQL worth reading.
    """
    brackets = 0
    opened = False
    for n in range(start, len(lines)):
        code = _code_only(lines[n], state)
        if signature:
            if opened and brackets == 0 and n > start:
                return n - 1
            for ch in code:
                if ch == "(":
                    brackets += 1
                    opened = True
                elif ch == ")":
                    brackets = max(0, brackets - 1)
            if _ALWAYS_SCRIPTING.match(code):
                return n - 1
            if opened and brackets == 0:
                return n
        elif ";" in code:
            return n
    return len(lines) - 1


def _gather_loop(lines: list[str], start: int, state: dict) -> tuple[str, int]:
    """A loop header written across lines, as one statement naming its table.

    Built from the lines as written, not from the copy with the strings blanked
    out -- the table being looped over is usually a quoted name, and blanking it
    would leave a query with nothing in it.
    """
    parts: list[str] = []
    for n in range(start, len(lines)):
        code = _code_only(lines[n], state)
        parts.append(lines[n])
        if _LOOP_END.search(code):
            joined = " ".join(parts)
            open_at = joined.find("(")
            close_at = joined.rfind(")")
            if open_at >= 0 and close_at > open_at:
                return "SELECT * FROM " + joined[open_at : close_at + 1] + ";", n
            return ";", n
    # No line finished the header. Give up on THIS LINE ONLY. Returning the end
    # of the file blanked every statement after it -- silently, with no parse
    # error and nothing on any screen, so a trail stopped one table short and
    # that was reported as where the chain ends.
    return _kept_read(lines[start]), start


def has_blocks(text: str) -> bool:
    state = {"quote": "", "comment": False}
    for line in text.splitlines():
        code = _code_only(line, state)
        if (_ALWAYS_SCRIPTING.match(code) or _SCRIPTING_UNLESS_CASE.match(code)
                or _LOOP_PLAIN.match(code) or _LOOP_START.match(code)
                or _RAISE.match(code) or _PROCEDURE.match(code)):
            return True
    return False


# ── templates that are more than holes ─────────────────────────────────────
# Everything above treats templating as holes with names in them. Real pipeline
# SQL uses it as a small programming language as well, and those shapes do not
# survive having their tags blanked and their bodies kept:
#
#     {% if backfill %} ... {% else %} ... {% endif %}   both branches, run on
#     {% set clause %} ... {% endset %}                  a value, left inside
#                                                         the statement
#     {{ header }} on a line of its own                  a whole block of SQL,
#                                                         turned into a bare word
#                                                         welded to the line below
#
# Measured on a real BigQuery warehouse of 7,304 files: 329 of its 2,320 .sql
# files are templated, and 176 of those did not parse at all. Every one landed
# on the "check by hand" list -- which is honest, but it is 176 files of a real
# warehouse whose tables and columns are in NO answer Ripple gives. Rendering
# them the way below reads 119 of the 176.
#
# These renderings are only ever tried on a file that did NOT parse as it
# stands. They cannot take a file that reads today and make it read differently,
# which matters more than the extra files: the first rule of this tool is that
# it does not quietly change an answer that was right.
_JINJA_TAG = re.compile(r"\{%-?\s*(?P<kw>\w+)\b(?P<args>.*?)-?%\}", re.DOTALL)

# A placeholder with nothing else on its line. In a generated warehouse this is
# how a whole block of SQL is dropped in -- a header, a shared set of CTEs, a
# UDF. Replaced by a bare identifier it becomes a word sitting on its own line
# in front of the next statement, which no parser will take. Blanking it loses
# nothing a name lookup would have found, because it never was one name.
#
# NOT done on the first pass. A table name written on its own line under a FROM
# is exactly this shape too, and blanking that would lose a real source table
# without a word said. Only a file that has already failed to parse gets this.
#
# The trailing class has to allow \r. A repository cloned on Windows has CRLF
# line endings, Python's ``$`` in MULTILINE matches before the \n and the \r is
# still sitting there -- so this matched on a Linux checkout of a file and not
# on a Windows one. The same file, the same SQL, a different answer depending on
# which machine ran the scan, and nothing anywhere saying so.
_STANDALONE_VAR = re.compile(r"^[ \t]*\{\{-?[^}]*?-?\}\}[ \t\r]*$", re.MULTILINE)

# Blocks whose body is a value or a definition, never part of the statement
# around them. A {% set x %}...{% endset %} holds a clause that is used
# somewhere else through {{ x }}; leaving its body where it is written puts a
# WHERE in the middle of a WITH.
_VALUE_BLOCKS = {"set", "macro", "raw", "filter"}
_TRANSPARENT_BLOCKS = {"call", "block"}


def _emitting(stack: list) -> bool:
    return all(on for _, on in stack)


def _render_branches(text: str, take: bool) -> str:
    """One rendering of a template's control flow. Line numbers do not move.

    ``take`` decides which side of every ``{% if %}`` is kept: True keeps the
    if-branch and drops the else, False the other way round. Both are rendered
    and both are tried, because nothing in the file says which way it runs and
    guessing one would be a chain lost on the files that guessed wrong.
    """
    out: list[str] = []
    at = 0
    stack: list[tuple[str, bool]] = []
    for m in _JINJA_TAG.finditer(text):
        kw = m.group("kw").lower()
        chunk = text[at:m.start()]
        out.append(chunk if _emitting(stack) else _keep_lines(chunk))
        at = m.end()
        out.append(_keep_lines(m.group(0)))       # the tag itself carries nothing
        if kw == "if":
            stack.append(("if", take))
        elif kw == "elif":
            if stack and stack[-1][0] == "if":
                stack[-1] = ("if", take)
        elif kw == "else":
            if stack and stack[-1][0] == "if":
                stack[-1] = ("if", not take)
        elif kw == "endif":
            if stack and stack[-1][0] == "if":
                stack.pop()
        elif kw in _VALUE_BLOCKS:
            # "{% set x = 1 %}" assigns and opens nothing; only the block form,
            # which has no "=", has a body to leave out.
            if kw != "set" or "=" not in m.group("args"):
                stack.append((kw, False))
        elif kw in _TRANSPARENT_BLOCKS:
            stack.append((kw, True))
        elif kw.startswith("end") and stack and stack[-1][0] == kw[3:]:
            stack.pop()
        # for / endfor: the body is kept once, which is what it was before.
    tail = text[at:]
    out.append(tail if _emitting(stack) else _keep_lines(tail))
    return "".join(out)


def has_control_flow(text: str) -> bool:
    """Is there templating here that is more than a hole with a name in it?"""
    for m in _JINJA_TAG.finditer(text):
        kw = m.group("kw").lower()
        if kw in ("if", "elif", "else", "endif", "for", "endfor") or kw in _VALUE_BLOCKS:
            return True
    return bool(_STANDALONE_VAR.search(text))


def renderings(text: str) -> list[str]:
    """Ways to read a template that did not parse as it stands, best first.

    Given back as raw template text with the control flow resolved -- the caller
    still puts it through ``fill_placeholders`` and ``unwrap_blocks``, exactly
    as it does the original, so a rendering can never take a path the ordinary
    one does not.

    Every one keeps the file's line count, so a finding still points at the real
    line of the real file. That is not a nicety: the whole use of this list is
    that somebody opens the file and looks.
    """
    if not has_control_flow(text):
        return []
    out: list[str] = []
    for take in (True, False):
        rendered = _render_branches(text, take)
        if rendered != text:
            out.append(rendered)
        # A placeholder standing alone on its line is a block of SQL, not a
        # name. Tried last, because on a file that parses without it this would
        # throw a real table name away. See _STANDALONE_VAR.
        out.append(_STANDALONE_VAR.sub(lambda m: "", rendered))
    seen: set[str] = set()
    return [r for r in out if not (r in seen or seen.add(r)) and r != text]
