"""BigQuery shapes the SQL parser refuses, rewritten into ones it accepts.

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
"""
from __future__ import annotations

import re

# One cheap scan decides whether any of the work below is needed. Almost every
# file in a repository contains none of these words, and walking every file
# twice is minutes rather than seconds on a repository of a few thousand.
#
# The bracket half is deliberately NOT inside the \b group. A word boundary in
# front of "(" needs a word character there, and a backticked function name
# ends in a backtick -- so `p.d.f`(TABLE x) was skipped while APPENDS(TABLE x)
# was caught, which is the sort of difference nobody would ever guess at.
_WORTH_LOOKING = re.compile(
    r"(?:\b(?:SNAPSHOT|REPLICA\s+OF|SYSTEM_TIME|WITH\s+CONNECTION"
    r"|PARTITION\s+COLUMNS|LOAD\s+DATA|EXPORT\s+DATA|UNDROP)\b|[(,]\s*TABLE\s)",
    re.IGNORECASE,
)


def _keep_lines(text: str) -> str:
    return "\n" * text.count("\n")


def _same_lines(m: "re.Match[str]") -> str:
    """Drop what matched, keeping the file the same length."""
    return _keep_lines(m.group(0))


def _balanced(text: str, open_at: int) -> int:
    """The index just past the ``)`` that closes the ``(`` at ``open_at``.

    Written out rather than done with a regular expression because an OPTIONS
    clause holds quoted strings, and a bracket inside one of those closes
    nothing. Returns -1 if the bracket never closes.
    """
    depth = 0
    quote = ""
    i = open_at
    while i < len(text):
        ch = text[i]
        if quote:
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                quote = ""
        elif ch in "'\"`":
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return -1


def _strip_clause(text: str, head: "re.Pattern[str]") -> str:
    """Remove ``<head>(...)`` wherever it appears, brackets balanced properly."""
    while True:
        m = head.search(text)
        if not m:
            return text
        open_at = text.find("(", m.end() - 1)
        if open_at < 0:
            return text
        close_at = _balanced(text, open_at)
        if close_at < 0:
            return text
        chunk = text[m.start():close_at]
        text = text[:m.start()] + _keep_lines(chunk) + text[close_at:]


# ── one shape at a time ────────────────────────────────────────────────────

# CREATE SNAPSHOT TABLE a CLONE b -- a copy, with two extra words the parser
# gives up on. Handled here rather than as a retry so it shares one code path
# with the rest.
_SNAPSHOT = re.compile(r"\bCREATE\s+SNAPSHOT\s+TABLE\b", re.IGNORECASE)

# CREATE MATERIALIZED VIEW x AS REPLICA OF y -- a full copy of a table into
# another region or cloud. Every column carries through under the same name,
# which is exactly what COPY already means to Ripple.
_REPLICA = re.compile(
    r"\bCREATE\s+(?:OR\s+REPLACE\s+)?MATERIALIZED\s+VIEW\s+(?P<t>[^\s]+)\s+"
    r"AS\s+REPLICA\s+OF\s+(?P<s>[^\s;]+)",
    re.IGNORECASE,
)

# ... CLONE b FOR SYSTEM_TIME AS OF <expr> -- the restore-from-backup form, and
# the one teams actually write. Only stripped after a CLONE or a COPY, because
# the same words are legal on an ordinary FROM and the parser reads those.
_TIME_TRAVEL = re.compile(
    r"(?<=\s)(FOR\s+SYSTEM_TIME\s+AS\s+OF\s+)(?P<e>[^;]*)",
    re.IGNORECASE,
)
_HAS_COPY = re.compile(r"\b(CLONE|COPY)\b", re.IGNORECASE)

# WITH CONNECTION `p.us.conn` -- on every BigLake, object and Iceberg table.
_CONNECTION = re.compile(
    r"\bWITH\s+CONNECTION\s+(?:`[^`]*`|\"[^\"]*\"|[\w.\-]+)", re.IGNORECASE)

# WITH PARTITION COLUMNS (dt DATE) -- hive-partitioned external tables.
_PARTITION_COLUMNS = re.compile(r"\bWITH\s+PARTITION\s+COLUMNS\s*(?=\()", re.IGNORECASE)

# APPENDS(TABLE t, ...), CHANGES(TABLE t, ...), my_tvf(TABLE t, 'x'),
# VECTOR_SEARCH(TABLE t, ...). A bare TABLE in argument position is a hard
# parse error, and it takes the neighbouring statements down with it.
_TABLE_ARG = re.compile(r"(?<=[(,])(\s*)TABLE\s+(?=[`\"\w])", re.IGNORECASE)

# LOAD DATA [OVERWRITE] INTO t (cols) FROM FILES (...) -- often the only place a
# landing table's columns are written down anywhere in the repository.
_LOAD_DATA = re.compile(
    r"\bLOAD\s+DATA\s+(?:OVERWRITE\s+|INTO\s+)+(?P<t>`[^`]*`|[\w.\-]+)\s*(?=\()",
    re.IGNORECASE,
)
_FROM_FILES = re.compile(r"\bFROM\s+FILES\s*(?=\()", re.IGNORECASE)

# EXPORT DATA [WITH CONNECTION x] OPTIONS(...) AS SELECT ... -- a delivery to
# somebody outside the warehouse. It builds no table, so what is left is the
# SELECT, and the read is reported as a real usage instead of an unreadable file.
_EXPORT = re.compile(r"\bEXPORT\s+DATA\s+(?=.*?\bOPTIONS\s*\()", re.IGNORECASE | re.DOTALL)
_OPTIONS_AS = re.compile(r"\bOPTIONS\s*(?=\()", re.IGNORECASE)


# Where an EXPORT DATA delivers to. The whole point of an export is that the
# file lands somewhere outside the warehouse and somebody else's job reads it,
# so "no production table is affected" is true and useless: the delivery that
# breaks belongs to another team, and nothing on any screen named it.
#
#     OPTIONS(uri='gs://feed/partner/*.csv', format='CSV')  ->  gs://feed/partner
#
# The last part of the path is a filename pattern, not a place. Dropping it is
# what turns a wildcard nobody recognises into the name of a feed somebody does.
_URI_OPTION = re.compile(r"\buri\s*=\s*(?:\[\s*)?(['\"])(?P<uri>[^'\"]+)\1", re.IGNORECASE)


def _feed_name(uri: str) -> str:
    """The delivery an export URI names, without its filename pattern."""
    head, sep, tail = uri.rstrip("/").rpartition("/")
    if sep and ("*" in tail or "." in tail):
        return head or uri
    return uri.rstrip("/")


def export_targets(text: str) -> list[tuple[int, str]]:
    """``(0-based line of the EXPORT, feed name)`` for every EXPORT DATA here."""
    out: list[tuple[int, str]] = []
    at = 0
    while True:
        m = _EXPORT.search(text, at)
        if not m:
            return out
        at = m.end()
        opt = _OPTIONS_AS.search(text, m.end())
        if not opt:
            return out
        open_at = text.find("(", opt.end() - 1)
        close_at = _balanced(text, open_at) if open_at >= 0 else -1
        if close_at < 0:
            return out
        found = _URI_OPTION.search(text[open_at:close_at])
        out.append((text[: m.start()].count("\n"),
                    _feed_name(found.group("uri")) if found else ""))


def _rewrite_export(text: str) -> str:
    """Leave the SELECT of an EXPORT DATA, and nothing else."""
    while True:
        m = _EXPORT.search(text)
        if not m:
            return text
        opt = _OPTIONS_AS.search(text, m.end())
        if not opt:
            return text
        open_at = text.find("(", opt.end() - 1)
        close_at = _balanced(text, open_at) if open_at >= 0 else -1
        if close_at < 0:
            return text
        after = text[close_at:]
        as_at = re.match(r"\s*AS\b", after, re.IGNORECASE)
        end = close_at + (as_at.end() if as_at else 0)
        chunk = text[m.start():end]
        text = text[:m.start()] + _keep_lines(chunk) + text[end:]


def _rewrite_load_data(text: str) -> str:
    """A LOAD DATA read as the table declaration it is."""
    while True:
        m = _LOAD_DATA.search(text)
        if not m:
            return text
        open_at = text.find("(", m.end() - 1)
        close_at = _balanced(text, open_at) if open_at >= 0 else -1
        if close_at < 0:
            return text
        columns = text[open_at:close_at]
        # Whatever follows -- FROM FILES (...) -- names no table, only a bucket.
        rest = text[close_at:]
        files = _FROM_FILES.search(rest)
        end = close_at
        if files:
            f_open = rest.find("(", files.end() - 1)
            f_close = _balanced(rest, f_open) if f_open >= 0 else -1
            if f_close >= 0:
                end = close_at + f_close
        chunk = text[m.start():end]
        replacement = f"CREATE TABLE {m.group('t')} {columns}"
        text = text[:m.start()] + replacement + _keep_lines(chunk) + text[end:]


# UNDROP TABLE t -- restoring a table somebody deleted. A HARD parse error, and
# a hard parse error costs the neighbouring statements too, so one line of a
# recovery script used to take the rest of its file with it. One extra word puts
# it in the same generic-command shape every other unreadable statement lands
# in, where sqlread.referenced_here reads the table name out of it and reports
# it as the dependency it is. Nothing is added to any line, so no line moves.
_UNDROP = re.compile(r"\bUNDROP\s+TABLE\b", re.IGNORECASE)


# ── Dataform ───────────────────────────────────────────────────────────────
# A .sqlx file is Google's own way of writing a BigQuery pipeline: an ordinary
# SELECT with a block on top that is JavaScript, not SQL.
#
#     config { type: "table", schema: "reporting" }
#     js { const x = 1 }
#     pre_operations { DELETE FROM ... }
#
#     SELECT cm13 FROM ${ref("customer_demographics")}
#
# The parser refuses the whole file on the first line, so nothing at all is
# learned from it. The blocks carry no lineage -- the config names a schema, and
# the SELECT under it is the thing that builds the table -- so they are dropped
# on the way in, keeping every line where it was.
#
# ``pre_operations`` and ``post_operations`` DO hold real SQL, so their brackets
# are dropped and their contents kept, as one more statement in the file.
_DATAFORM_BLOCK = re.compile(r"^[ \t]*(config|js)\s*\{", re.IGNORECASE | re.MULTILINE)
_DATAFORM_OPS = re.compile(r"^[ \t]*(pre_operations|post_operations)\s*\{",
                           re.IGNORECASE | re.MULTILINE)


def _balanced_braces(text: str, open_at: int) -> int:
    """The index just past the ``}`` closing the ``{`` at ``open_at``, or -1."""
    depth = 0
    quote = ""
    i = open_at
    while i < len(text):
        ch = text[i]
        if quote:
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                quote = ""
        elif ch in "'\"`":
            quote = ch
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return -1


def _strip_dataform(text: str) -> str:
    """Drop the JavaScript blocks a Dataform file opens with."""
    for pattern, keep_inside in ((_DATAFORM_BLOCK, False), (_DATAFORM_OPS, True)):
        while True:
            m = pattern.search(text)
            if m is None:
                break
            brace = text.find("{", m.start())
            end = _balanced_braces(text, brace) if brace >= 0 else -1
            if end < 0:
                break
            if keep_inside:
                # Real SQL, run before or after the model builds. Keep it, as
                # one more statement in the file.
                head = _keep_lines(text[m.start():brace])
                text = text[:m.start()] + head + text[brace + 1:end - 1] + ";" + text[end:]
            else:
                text = text[:m.start()] + _keep_lines(text[m.start():end]) + text[end:]
    return text


def needed(text: str) -> bool:
    return bool(_WORTH_LOOKING.search(text) or _DATAFORM_BLOCK.search(text)
                or _DATAFORM_OPS.search(text))


def rewrite(text: str) -> str:
    """The same SQL, in a shape the parser will read. Line numbers do not move."""
    if not needed(text):
        return text
    text = _strip_dataform(text)
    out = _SNAPSHOT.sub(lambda m: "CREATE TABLE", text)
    out = _REPLICA.sub(
        lambda m: (f"CREATE TABLE {m.group('t')} COPY {m.group('s')}"
                   + _keep_lines(m.group(0))),
        out)
    if _HAS_COPY.search(out):
        out = _TIME_TRAVEL.sub(_same_lines, out)
    out = _CONNECTION.sub(_same_lines, out)
    out = _strip_clause(out, _PARTITION_COLUMNS)
    out = _TABLE_ARG.sub(lambda m: m.group(1), out)
    out = _rewrite_load_data(out)
    out = _rewrite_export(out)
    out = _UNDROP.sub(lambda m: "CREATE " + m.group(0), out)
    return out
