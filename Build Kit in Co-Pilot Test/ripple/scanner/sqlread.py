"""Parsing SQL into statements and usages.

A word search can tell you that MARKET_CODE appears in a file. Only parsing can
tell you it appears inside a WHERE clause compared against the literal 'US' -
which is the difference between "mentioned here" and "this breaks on the 18th".

NAMES THIS FILE NEEDED THAT THE CONTRACT CARD DOES NOT GIVE. Every one of them
is written out again in _NOTES.md so it can be carried to the other windows:

  TAKEN FROM PHASE 3 (ripple/scanner/templating.py), spelled as that file
  spells them rather than as this one first guessed
      placeholder_names(text) -> set[str]
      fill_placeholders(text) -> str                (line count unchanged)
      unwrap_blocks(text) -> str                    (line count unchanged)
          It takes the scripting out of ONE piece of text and hands the whole
          piece back. It does NOT cut a file into blocks and it is not told the
          language. It is also the file that rewrites a loop header,
          FOR x IN (q) DO, into CREATE TEMP TABLE x AS q, which is what lets a
          loop row be followed: this file reads the loop row back off the
          file's own line, but it cannot do the rewrite itself.
  TAKEN FROM PHASE 3 (ripple/scanner/rescue.py)
      rescue_text(text) -> str                      (line count unchanged)
  TAKEN FROM PHASE 2 (ripple/scanner/repo.py)
      statements_for(f) -> list[(sql, 0-based line offset)]
          Where the blocks parse_file walks come from. A .sql file yields one
          block, its whole text; an Airflow DAG, a shell script or a YAML file
          yields one block per query mined out of it, each with the line it
          starts on. Without this every SQL string inside a Python DAG would go
          unread, and a DAG is how most of these pipelines are written.
      the index passed to parse_repo exposes .files, an iterable of SourceFile

  offered BY THIS FILE to the windows downstream
      Statement, Usage, ParsedRepo, Unreadable, Reference, ProcedureCall,
      ExternalSql, TableFork
      parse_file, parse_repo, parse_block, split_statements
      output_names, usages_of, mode_of, locate, snippet
      same_table, reads_from, forget_source_cache, display_table, is_scoped
      shard_verdict, two_definitions
      KIND_ORDER, KIND_WORDS, label_for

NOTHING IN HERE READS A PARSE-TREE KEY THAT DRIFTS BETWEEN PARSER VERSIONS.
Every one of those goes through ripple/scanner/dialectcompat.py.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Iterator, Optional

import sqlglot
from sqlglot import exp

from ripple.scanner.dialectcompat import (
    RENAME_NODE,
    from_of,
    is_temporary,
    is_unpivot,
    merge_whens,
    pivot_columns,
    pivot_fields,
    star_except,
    star_rename,
    star_replace,
)
from ripple.scanner.repo import statements_for
from ripple.scanner.rescue import rescue_text
from ripple.scanner.templating import (
    fill_placeholders,
    placeholder_names,
    unwrap_blocks,
)

# ALTER is exp.Alter on current sqlglot and exp.AlterTable on older ones. This
# is a class lookup rather than one of the drifting arg keys, so it stays here
# rather than in dialectcompat, but it drifts for the same reason.
# An empty tuple when this parser has neither spelling: isinstance against ()
# is simply False, so the tool finds less rather than treating every statement
# as an ALTER.
_ALTER_NODES = tuple(
    node
    for node in (getattr(exp, "Alter", None), getattr(exp, "AlterTable", None))
    if node is not None
)
_DECLARE_NODE = getattr(exp, "Declare", None)
_SET_NODE = getattr(exp, "Set", None)

# BigQuery's own built-in table functions WRAP a table rather than being one.
# The table they wrap is parsed separately and found anyway, so taking the
# wrapper's name as well only invents a table nobody has. The last three catch
# people out: a generated range of dates is written in a FROM clause exactly
# like a table and is not one.
SKIP_TABLE_FUNCTIONS = {
    "EXTERNAL_QUERY",
    "APPENDS",
    "CHANGES",
    "GAP_FILL",
    "VECTOR_SEARCH",
    "RANGE_SESSIONIZE",
    "SESSIONIZE",
    "OBJECT_METADATA",
    "SEARCH_INDEX_STATUS",
    "TABLE_DATE_RANGE",
    "TABLE_QUERY",
    "GENERATE_ARRAY",
    "GENERATE_DATE_ARRAY",
    "GENERATE_TIMESTAMP_ARRAY",
}

# Most consequential first. The first kind left after the sort is the finding's
# headline: it picks the words on the row, the impact sentence, and whether the
# finding counts as breaking at all. Get this order wrong and a table
# partitioned by the column being decommissioned heads its row with "Select".
KIND_ORDER = [
    "ranking",
    "dedup_key",
    "layout",
    "filter",
    "join_key",
    "transform",
    "aggregation",
    "sort",
    "pivoted",
    "excluded",
    "renamed",
    "dropped",
    "retyped",
    "select",
    "star",
]

KIND_WORDS = {
    "ranking": "Ranking",
    "dedup_key": "Dedup key",
    "layout": "Partition or cluster key",
    "filter": "Filter",
    "join_key": "Join key",
    "transform": "Transform",
    "aggregation": "Aggregation",
    "sort": "Sort order",
    "pivoted": "Named in PIVOT",
    "excluded": "Named in EXCEPT",
    "renamed": "Renamed by ALTER TABLE",
    "dropped": "Dropped by ALTER TABLE",
    "retyped": "Changed by ALTER TABLE",
    "select": "Select",
    "star": "Carried by SELECT *",
}

# BigQuery lets these be written with no brackets, so "SELECT current_date FROM
# t" parses as a call and not as a column at all. Which the writer meant cannot
# be known from the file, so both readings are followed and every usage of the
# name in that statement is marked not certain.
PARENLESS_FUNCTIONS = {
    "CURRENT_DATE",
    "CURRENT_TIME",
    "CURRENT_TIMESTAMP",
    "CURRENT_DATETIME",
}

# The words each kind of usage lives near, used only to score which line a
# finding should point at.
_KIND_KEYWORDS = {
    "filter": ("where", "and", "or", "having", "qualify", "="),
    "join_key": ("join", " on ", "using"),
    "ranking": ("over", "order by", "row_number", "rank(", "dense_rank", "limit"),
    "dedup_key": ("partition by", "max(", "min(", "qualify", "distinct"),
    "aggregation": ("group by", "sum(", "count(", "avg("),
    "sort": ("order by",),
    "layout": ("partition by", "cluster by"),
    "transform": ("cast(", "set ", "unnest", "struct("),
    "select": ("select", ","),
    "star": ("select", "*"),
    "pivoted": ("pivot", "unpivot", " for "),
    "excluded": ("except", "replace", "rename"),
    "renamed": ("rename", "alter"),
    "dropped": ("drop", "alter"),
    "retyped": ("alter", "type"),
}

_WHOLE_COPY_RE = re.compile(
    r"""^\s*CREATE\s+(?:OR\s+REPLACE\s+)?
        (?:TEMP\s+|TEMPORARY\s+)?(?:SNAPSHOT\s+)?TABLE\s+
        (?:IF\s+NOT\s+EXISTS\s+)?
        (?P<target>[^\s;()]+)\s+
        (?P<word>COPY|CLONE|LIKE)\s+
        (?P<source>[^\s;()]+)\s*;?\s*$""",
    re.IGNORECASE | re.VERBOSE,
)

_RENAME_TO_RE = re.compile(
    r"^\s*ALTER\s+TABLE\s+(?:IF\s+EXISTS\s+)?(?P<source>[^\s;]+)\s+"
    r"RENAME\s+TO\s+(?P<target>[^\s;]+)\s*;?\s*$",
    re.IGNORECASE,
)

_EXECUTE_IMMEDIATE_RE = re.compile(r"^\s*EXECUTE\s+IMMEDIATE\s+", re.IGNORECASE)
_CALL_RE = re.compile(r"^\s*CALL\s+([A-Za-z0-9_.`$\-]+)\s*\(", re.IGNORECASE)
_PROCEDURE_RE = re.compile(
    r"CREATE\s+(?:OR\s+REPLACE\s+)?PROCEDURE\s+([A-Za-z0-9_.`$\-]+)\s*\(",
    re.IGNORECASE,
)
_SEARCH_INDEX_RE = re.compile(
    r"^\s*CREATE\s+(?:OR\s+REPLACE\s+)?(?P<kind>SEARCH|VECTOR)\s+INDEX\s+"
    r"(?:IF\s+NOT\s+EXISTS\s+)?(?P<name>[^\s]+)\s+ON\s+(?P<table>[^\s(]+)\s*"
    r"\((?P<columns>[^)]*)\)",
    re.IGNORECASE | re.MULTILINE,
)
_POLICY_RE = re.compile(
    r"^\s*CREATE\s+(?:OR\s+REPLACE\s+)?ROW\s+ACCESS\s+POLICY\s+"
    r"(?:IF\s+NOT\s+EXISTS\s+)?(?P<name>[^\s]+)\s+ON\s+(?P<table>[^\s(]+)",
    re.IGNORECASE | re.MULTILINE,
)
_UNDROP_RE = re.compile(
    r"^\s*UNDROP\s+TABLE\s+(?P<table>[^\s;]+)", re.IGNORECASE | re.MULTILINE
)
_FILTER_USING_RE = re.compile(
    r"FILTER\s+USING\s*\((?P<body>.*?)\)\s*;?\s*$", re.IGNORECASE | re.DOTALL
)
_FOR_ROW_RE = r"^\s*FOR\s+{name}\s+IN\b"
_SQL_FILE_RE = re.compile(r"""['"]([^'"\s]+\.sql)['"]""", re.IGNORECASE)
_WORD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_DECORATOR_RE = re.compile(r"\$\d+$")

_SQL_KEYWORDS_IN_POLICY = {
    "and",
    "or",
    "not",
    "in",
    "is",
    "null",
    "true",
    "false",
    "session_user",
    "current_timestamp",
    "between",
    "like",
}


# --------------------------------------------------------------------------
# Data shapes that cross file boundaries
# --------------------------------------------------------------------------


@dataclass
class Usage:
    """How a column is used in one statement."""

    kind: str
    column: str
    alias: str = ""
    detail: str = ""
    certain: bool = True
    # True when the column only leaves the statement because of a SELECT *. It
    # really is carried, but the column list is written down nowhere.
    via_star: bool = False


@dataclass
class Statement:
    """One statement, with everything the file said about it.

    line_offset and line_end are 0-BASED lines of the file. locate() hands back
    a 1-based line because that is what a person reads.
    """

    file: str
    lang: str
    line_offset: int
    line_end: int
    sql: str
    target: str = ""
    sources: set[str] = field(default_factory=set)
    select: Any = None
    expr: Any = None
    # the word the file used to copy a whole table - COPY, CLONE, LIKE, RENAME
    whole_copy: str = ""
    # what the file writes where the column list should be, when a SELECT * is
    # really a placeholder filled in at run time
    star_note: str = ""
    # names read back as columns by hand, so a usage of one is never certain
    guessed_columns: set[str] = field(default_factory=set)
    # how the target was worked out - "dbt", "Dataform" or "file"
    named_by: str = ""
    # the words the file used to run this statement as text
    built_as_text: str = ""
    # where an EXPORT DATA delivers to
    export_uri: str = ""
    # the script variable this statement fills
    script_var: str = ""
    _sources_upper: Optional[frozenset] = field(
        default=None, repr=False, compare=False
    )
    _levels: Optional[list] = field(default=None, repr=False, compare=False)


@dataclass
class Unreadable:
    """One thing the reader could not follow, in plain English.

    Never dropped: a tidier screen that says less is a worse screen.
    """

    file: str
    message: str
    line: int = 0
    text: str = ""
    count: int = 1
    hint: str = ""


@dataclass
class Reference:
    """A statement that NAMES a table and a column but carries nothing.

    Read loosely, with a regular expression: it may add a row to a list, and it
    must never move a chain.
    """

    file: str
    line: int
    kind: str
    table: str
    columns: list[str] = field(default_factory=list)
    text: str = ""


@dataclass
class ProcedureCall:
    """One CALL, read off the file text because it does not survive parsing."""

    file: str
    line: int
    name: str


@dataclass
class ExternalSql:
    """A program that runs a .sql file which is not in this repository."""

    file: str
    line: int
    path: str


@dataclass
class TableFork:
    """One table fully REPLACED by more than one file."""

    table: str
    files: list[str] = field(default_factory=list)


@dataclass
class ParsedRepo:
    statements: list[Statement] = field(default_factory=list)
    unreadable: list[Unreadable] = field(default_factory=list)
    parsed_files: set[str] = field(default_factory=set)
    # {path: [{line, text, sql}]} - kept, not reported
    opaque: dict[str, list[dict]] = field(default_factory=dict)
    runs_sql_from: list[ExternalSql] = field(default_factory=list)
    references: list[Reference] = field(default_factory=list)
    procedure_calls: list[ProcedureCall] = field(default_factory=list)


@dataclass
class _Level:
    """One nesting depth of a statement, read into four things."""

    depth: int = 0
    # a column name -> the names it is carried through or plainly renamed as
    direct: dict[str, list[str]] = field(default_factory=dict)
    # a column name -> the names it is reshaped into
    derived: dict[str, list[str]] = field(default_factory=dict)
    # true when any SELECT * at this level carries the rest through untouched
    passthrough: bool = False
    # the names no star at this level carries on
    dropped: set[str] = field(default_factory=set)


# --------------------------------------------------------------------------
# Names
# --------------------------------------------------------------------------


def _clean_part(part: str) -> str:
    """One dot-separated part of a name, with the warehouse's quoting off.

    A trailing $20260101 is a DAY of a table, not a different table. Keep it and
    every decorated read splits off from the table it belongs to, nothing
    matches, and the answer comes back as a clean "no impact" on a pipeline that
    writes that table every morning.
    """
    part = part.strip().strip("`").strip('"').strip("[").strip("]").strip()
    return _DECORATOR_RE.sub("", part)


def _split_name(name: str) -> tuple[str, str]:
    """(dataset, short name), both lower-cased and cleaned."""
    if not name:
        return "", ""
    parts = [_clean_part(part) for part in str(name).split(".")]
    parts = [part for part in parts if part != ""]
    if not parts:
        return "", ""
    short = parts[-1].lower()
    dataset = parts[-2].lower() if len(parts) > 1 else ""
    return dataset, short


def short_name(name: str) -> str:
    """The last part of a name, decorator taken off."""
    return _split_name(name)[1]


def dataset_of(name: str) -> str:
    """The dataset part of a name, or "" when the name does not state one."""
    return _split_name(name)[0]


def is_scoped(name: str) -> bool:
    """True for a name fenced to one file - a temp table or a script variable.

    The mark is "#", a character no warehouse allows in a name, so it can never
    collide with something somebody wrote.
    """
    return "#" in str(name or "")


def scope_for(path: str) -> str:
    """The fence standing for "inside this file".

    A TEMP table has no dataset, so the dataset rule that keeps stage.orders
    apart from archive.orders cannot help. Invent one out of the file's path.
    """
    return "#" + re.sub(r"[^A-Za-z0-9]", "_", str(path or ""))


def fence(path: str, name: str) -> str:
    """A short name moved inside one file's fence."""
    return scope_for(path) + "." + short_name(name)


def display_table(name: str) -> str:
    """The name as somebody would find it in a file.

    STRIP THE MARK: it is Ripple's fence, not something anybody wrote, and a
    name on screen that is in no file sends somebody looking for a table that
    does not exist.
    """
    dataset, short = _split_name(name)
    if not name:
        return ""
    if is_scoped(dataset) or is_scoped(str(name)):
        return short
    parts = [part for part in str(name).split(".") if part.strip()]
    return ".".join(_clean_part(part) for part in parts)


def is_metadata(name: str) -> bool:
    """INFORMATION_SCHEMA is not data - it is the warehouse describing itself.

    Its views are called COLUMNS, TABLES, JOBS, VIEWS - ordinary words, and a
    warehouse of any size has real tables called some of them. Nothing that
    changes in a real table changes a COLUMN of INFORMATION_SCHEMA.COLUMNS: a
    ROW of it changes, and a row is not lineage.
    """
    if not name:
        return False
    parts = [_clean_part(part) for part in str(name).split(".")]
    for part in parts:
        if part.upper() == "INFORMATION_SCHEMA":
            return True
    if parts and parts[0].lower().startswith("region-"):
        return True
    return False


def _wildcard_covers(wildcard: str, name: str) -> bool:
    """Does a BigQuery wildcard table cover this name?

    BigQuery only allows the star at the end, and it stands for every table in
    that dataset whose name starts with the part in front of it. One deliberate
    addition to that rule: a person asked what breaks types the family the way
    they think of it - "customer_demographics" with no trailing separator -
    which BigQuery would not match. Match that too. Do not go further: "ev" must
    never match "events_*".
    """
    prefix = wildcard[:-1]
    if not prefix:
        return False
    if name.endswith("*"):
        return name[:-1] == prefix
    if name.startswith(prefix):
        return True
    return name == prefix.rstrip("_-")


def _names_match(left: str, right: str) -> bool:
    if left == right:
        return True
    if left.endswith("*"):
        return _wildcard_covers(left, right)
    if right.endswith("*"):
        return _wildcard_covers(right, left)
    return False


def same_table(left: str, right: str) -> bool:
    """Are these two written names the same table?

    Deliberately loose in one direction only: a name with no dataset goes on
    matching one that has a dataset, because otherwise every templated chain in
    the repository breaks. Loose is right for FOLLOWING a chain and catastrophic
    for EXCLUDING a source, which is why the source walk skips its target by
    node identity and never comes through here.
    """
    if not left or not right:
        return False
    left_dataset, left_short = _split_name(left)
    right_dataset, right_short = _split_name(right)
    if not left_short or not right_short:
        return False
    if is_scoped(left_dataset) or is_scoped(right_dataset):
        # The one place the loose rule is switched off. Nothing outside that
        # file can be reading a table that exists only inside it.
        return left_dataset == right_dataset and _names_match(left_short, right_short)
    if left_dataset and right_dataset and left_dataset != right_dataset:
        return False
    return _names_match(left_short, right_short)


def forget_source_cache(stmt: Statement) -> None:
    """Throw away a statement's cached sources.

    THREE things widen a statement's sources after it is built - fencing a
    file's temporary tables, binding its script variables, and unfencing a temp
    name along a CALL edge - and every one of them has to call this. Leave it
    stale and all three look as though they were never applied, while every test
    written against those functions on their own goes on passing.
    """
    stmt._sources_upper = None


def _sources_upper(stmt: Statement) -> frozenset:
    if stmt._sources_upper is None:
        stmt._sources_upper = frozenset(
            str(source).upper() for source in stmt.sources if source
        )
    return stmt._sources_upper


def reads_from(stmt: Statement, name: str) -> bool:
    """Does this statement read that table?

    When asked for a name with no dataset, a source fenced to one file is not an
    answer: nothing outside that file can be reading it.
    """
    if not name:
        return False
    wants_dataset = bool(dataset_of(name))
    for source in _sources_upper(stmt):
        if not wants_dataset and is_scoped(dataset_of(source)):
            continue
        if same_table(source, name):
            return True
    return False


# --------------------------------------------------------------------------
# Splitting
# --------------------------------------------------------------------------


def split_statements(text: str) -> list[tuple[str, int]]:
    """Split on semicolons that are NOT inside quotes or comments.

    Returns (statement text, 0-based start line). sqlglot reads a file as one
    piece and gives up at the first statement it cannot follow, taking every
    other statement down with it - so one GRANT, one procedure call, one line in
    another dialect costs the entire file. Splitting first means one bad
    statement costs one statement.
    """
    out: list[tuple[str, int]] = []
    length = len(text)
    index = 0
    line = 0
    start = 0
    start_line = 0
    seen_code = False
    quote = ""
    in_line_comment = False
    in_block_comment = False

    while index < length:
        char = text[index]

        if in_line_comment:
            if char == "\n":
                in_line_comment = False
                line += 1
            index += 1
            continue

        if in_block_comment:
            if text.startswith("*/", index):
                in_block_comment = False
                index += 2
                continue
            if char == "\n":
                line += 1
            index += 1
            continue

        if quote:
            if char == "\n":
                line += 1
                index += 1
                continue
            if text.startswith(quote, index):
                # A doubled quote inside a string is an escaped quote, not the
                # end of the string.
                if len(quote) == 1 and text.startswith(quote * 2, index):
                    index += 2
                    continue
                index += len(quote)
                quote = ""
                continue
            if char == "\\" and index + 1 < length:
                if text[index + 1] == "\n":
                    line += 1
                index += 2
                continue
            index += 1
            continue

        if char == "\n":
            line += 1
            index += 1
            continue
        if char.isspace():
            index += 1
            continue
        if text.startswith("--", index):
            in_line_comment = True
            index += 2
            continue
        if char == "#":
            in_line_comment = True
            index += 1
            continue
        if text.startswith("/*", index):
            in_block_comment = True
            index += 2
            continue
        if char == ";":
            if seen_code:
                out.append((text[start:index], start_line))
            seen_code = False
            index += 1
            continue

        if not seen_code:
            seen_code = True
            start = index
            start_line = line

        if char in "'\"`":
            if text.startswith(char * 3, index):
                quote = char * 3
                index += 3
            else:
                quote = char
                index += 1
            continue

        index += 1

    if seen_code:
        out.append((text[start:], start_line))
    return out


def _line_span(sql: str, start_line: int) -> tuple[int, int]:
    """(first line, last line) of a chunk, both 0-based."""
    return start_line, start_line + sql.count("\n")


# --------------------------------------------------------------------------
# Pointing at a line
# --------------------------------------------------------------------------


def _lines_of(file: Any) -> list[str]:
    """The file's lines. Takes a SourceFile or the plain text of one."""
    text = getattr(file, "text", file)
    if not isinstance(text, str):
        return []
    return text.splitlines()


def _score_line(line: str, column: str, kind: str) -> int:
    lowered = line.lower()
    wanted = column.lower()
    if not wanted:
        return 0
    if not re.search(r"(?<![A-Za-z0-9_])" + re.escape(wanted) + r"(?![A-Za-z0-9_])", lowered):
        return 0
    score = 2
    for keyword in _KIND_KEYWORDS.get(kind, ()):
        if keyword in lowered:
            score += 1
    return score


def _best_line(
    lines: list[str], column: str, kind: str, low: int, high: int
) -> Optional[int]:
    best: Optional[int] = None
    best_score = 0
    for index in range(max(0, low), min(high, len(lines) - 1) + 1):
        score = _score_line(lines[index], column, kind)
        if score > best_score:
            best_score = score
            best = index
    return best


def locate(
    file: Any,
    column: str,
    kind: str,
    line_offset: int,
    line_end: Optional[int] = None,
) -> int:
    """The best guess at the real 1-based line, BOUNDED to the statement.

    Score only the lines inside the statement first. Only when nothing inside it
    matches - which happens where the name exists only after a placeholder is
    filled in - widen the search to the whole file, rather than dropping the
    finding.

    In a 600-line generated file holding sixty statements, an unbounded search
    regularly picks the best-scoring WHERE clause in somebody else's statement
    about somebody else's table: the finding right, the line wrong, and the whole
    finding wasted.
    """
    lines = _lines_of(file)
    if not lines:
        return max(1, line_offset + 1)
    low = max(0, line_offset)
    high = len(lines) - 1 if line_end is None else min(line_end, len(lines) - 1)
    if high < low:
        high = len(lines) - 1
    best = _best_line(lines, column, kind, low, high)
    if best is None:
        best = _best_line(lines, column, kind, 0, len(lines) - 1)
    if best is None:
        return min(low + 1, len(lines))
    return best + 1


def snippet(file: Any, line: int, note: str = "") -> list[dict]:
    """A few lines of real code with the important one marked.

    Shaped as the finding's lines[{n, t, hit}]. A note, when there is one, is
    added as one last entry with n = 0: it is not a line of the file, and
    putting it on one would print words nobody wrote as though they were code.
    """
    lines = _lines_of(file)
    out: list[dict] = []
    if lines:
        wanted = max(1, min(int(line or 1), len(lines)))
        low = max(1, wanted - 2)
        high = min(len(lines), wanted + 2)
        for number in range(low, high + 1):
            out.append(
                {"n": number, "t": lines[number - 1].rstrip(), "hit": number == wanted}
            )
    if note:
        out.append({"n": 0, "t": note, "hit": False})
    return out


# --------------------------------------------------------------------------
# Small parse-tree helpers
# --------------------------------------------------------------------------


def _is_expression(node: Any) -> bool:
    """sqlglot puts plain booleans in some slots, and reaching for .find on one
    takes the whole file down with an AttributeError."""
    return isinstance(node, exp.Expression)


def _unalias(node: Any) -> Any:
    while isinstance(node, (exp.Alias, exp.Paren)):
        node = node.this
    return node


def _alias_of(node: Any) -> str:
    if isinstance(node, exp.Alias):
        return node.alias or ""
    return ""


def _key(name: Any) -> str:
    if isinstance(name, str):
        return _clean_part(name).lower()
    if isinstance(name, exp.Column):
        return (name.name or "").lower()
    if _is_expression(name):
        return (getattr(name, "alias_or_name", "") or getattr(name, "name", "") or "").lower()
    return ""


def _dotted_key(node: Any) -> str:
    """payload.code for a qualified reference, "" for a bare one."""
    if isinstance(node, exp.Column):
        qualifier = node.table or ""
        if qualifier and node.name:
            return (qualifier + "." + node.name).lower()
    if isinstance(node, exp.Dot):
        text = node.sql().replace("`", "").replace('"', "")
        return text.lower()
    return ""


def _add_name(mapping: dict[str, list[str]], key: str, value: str) -> None:
    if not key or not value:
        return
    bucket = mapping.setdefault(key, [])
    if value not in bucket:
        bucket.append(value)


def _columns_in(node: Any) -> list[exp.Column]:
    if not _is_expression(node):
        return []
    if isinstance(node, exp.Column):
        return [node]
    return list(node.find_all(exp.Column))


def _table_name(node: Any) -> str:
    """The written name of a table node, catalog and dataset kept."""
    if not isinstance(node, exp.Table):
        return ""
    parts = []
    for part in (node.catalog, node.db, node.name):
        if part:
            parts.append(_clean_part(str(part)))
    return ".".join(parts)


def _function_name(node: Any) -> str:
    """The name of a call, in CAPITALS, so the spelling in the file does not
    matter."""
    if not _is_expression(node):
        return ""
    if isinstance(node, exp.Anonymous):
        this = node.this
        name = this if isinstance(this, str) else _key(this)
        return str(name or "").replace("`", "").upper()
    if isinstance(node, exp.Dot):
        return node.sql().replace("`", "").upper()
    if isinstance(node, exp.Func):
        name = getattr(node, "sql_name", None)
        if callable(name):
            try:
                return str(name()).upper()
            except Exception:
                pass
        return type(node).__name__.upper()
    return ""


def _selects_of(expr: Any) -> list[Any]:
    if not _is_expression(expr):
        return []
    return list(expr.find_all(exp.Select))


def _select_depth(select: Any) -> int:
    depth = 0
    node = select.parent
    while node is not None:
        if isinstance(node, exp.Select):
            depth += 1
        node = node.parent
    return depth


_VALUE_HOLDERS = (exp.Where, exp.Having, exp.Group, exp.Order, exp.Limit)
_QUALIFY = getattr(exp, "Qualify", None)
if _QUALIFY is not None:
    _VALUE_HOLDERS = _VALUE_HOLDERS + (_QUALIFY,)


def _is_value_position(select: Any) -> bool:
    """A SELECT written as a VALUE is not a source of rows.

    A scalar subquery in the select list, or in a WHERE, HAVING, QUALIFY, GROUP
    BY, ORDER BY or LIMIT, is one number or one list to test against, and the
    names inside it are its own business. Read them as the statement's output
    names and the chain follows a name that exists only inside the brackets.

    A JOIN has two halves and they are opposite: its SOURCE hands its columns to
    the query around it, its ON CONDITION is a value exactly like a WHERE.
    """
    child = select
    node = select.parent
    while node is not None:
        if isinstance(node, _VALUE_HOLDERS):
            return True
        if isinstance(node, exp.Join):
            return child is node.args.get("on")
        if isinstance(node, exp.Select):
            return any(item is child for item in node.expressions)
        child = node
        node = node.parent
    return False


def _pivots_on(node: Any) -> list[Any]:
    if not _is_expression(node):
        return []
    pivots = node.args.get("pivots")
    if not pivots:
        return []
    return [pivot for pivot in pivots if _is_expression(pivot)]


def _pivots_of(select: Any) -> list[Any]:
    """A PIVOT hangs off the FROM clause, not off any select list, so nothing
    that walks projections, WHERE clauses or joins can ever see it."""
    out: list[Any] = []
    from_clause = from_of(select)
    if _is_expression(from_clause):
        out.extend(_pivots_on(from_clause.this))
        out.extend(_pivots_on(from_clause))
    for join in select.args.get("joins") or []:
        if _is_expression(join):
            out.extend(_pivots_on(join.this))
    return out


def _star_of(item: Any) -> Any:
    """The star inside a select-list item, or None.

    A star is not a column reference. The names hanging off one - EXCEPT(cm13),
    REPLACE(x AS cm13) - sit inside it as ordinary column references, and a
    plain search for the column finds them there and reports the column as
    reshaped and carried onward, which is the opposite of what the statement
    does with it.
    """
    if isinstance(item, exp.Star):
        return item
    if isinstance(item, exp.Column) and isinstance(item.this, exp.Star):
        return item.this
    return None


# --------------------------------------------------------------------------
# Which table a column came from
# --------------------------------------------------------------------------


def _cte_names(expr: Any) -> set[str]:
    if not _is_expression(expr):
        return set()
    return {
        (cte.alias_or_name or "").lower()
        for cte in expr.find_all(exp.CTE)
        if cte.alias_or_name
    }


def _tables_read_by(node: Any, cte_names: set[str]) -> list[str]:
    out: list[str] = []
    if not _is_expression(node):
        return out
    for table in node.find_all(exp.Table):
        name = _table_name(table)
        if not name or is_metadata(name):
            continue
        if not table.db and short_name(name) in cte_names:
            continue
        if name not in out:
            out.append(name)
    return out


def _scope_bindings(select: Any, cte_names: set[str]) -> dict[str, list[str]]:
    """What each alias means INSIDE this one SELECT.

    One alias can mean two things in one statement: an inner EXISTS re-binds t
    to another table. Built flat across the whole statement, the inner binding
    was the only one held and a breaking WHERE was ruled out as some other
    table's column.

    A SUBQUERY's alias binds to every table that subquery reads - a list,
    because where it reads more than one the SQL has not said which.
    """
    bindings: dict[str, list[str]] = {}
    items: list[Any] = []
    from_clause = from_of(select)
    if _is_expression(from_clause):
        items.append(from_clause.this)
    for join in select.args.get("joins") or []:
        if _is_expression(join):
            items.append(join.this)
    for item in items:
        if not _is_expression(item):
            continue
        alias = (item.alias_or_name or "").lower()
        if isinstance(item, exp.Table):
            name = _table_name(item)
            if name and short_name(name) not in cte_names:
                bindings.setdefault(alias, [])
                if name not in bindings[alias]:
                    bindings[alias].append(name)
            elif name:
                # A CTE reference: that IS the chain being followed, so it is
                # not a reason to rule a usage out.
                bindings.setdefault(alias, [])
        elif isinstance(item, exp.Subquery):
            read = _tables_read_by(item, cte_names)
            bindings[alias] = list(read)
        else:
            bindings.setdefault(alias, [])
    return bindings


def _flat_bindings(expr: Any, cte_names: set[str]) -> dict[str, list[str]]:
    """The fallback map: what answers for a qualifier bound somewhere the walk
    cannot see. It must still answer "unknown" there rather than ruling a usage
    out."""
    bindings: dict[str, list[str]] = {}
    for select in _selects_of(expr):
        for alias, tables in _scope_bindings(select, cte_names).items():
            if not alias:
                continue
            bucket = bindings.setdefault(alias, [])
            for table in tables:
                if table not in bucket:
                    bucket.append(table)
    if _is_expression(expr):
        # A MERGE, an UPDATE ... FROM and a DELETE have no SELECT anywhere, so
        # without this every usage in the statement that loads a published
        # table comes back inferred rather than read.
        for table in expr.find_all(exp.Table):
            alias = (table.alias_or_name or "").lower()
            name = _table_name(table)
            if not alias or not name or short_name(name) in cte_names:
                continue
            bucket = bindings.setdefault(alias, [])
            if name not in bucket:
                bucket.append(name)
    return bindings


def _bindings_for(node: Any, qualifier: str, expr: Any, cte_names: set[str]):
    """Resolve a qualifier by walking OUT from the column to the nearest SELECT
    that binds that name, which is what SQL itself does."""
    wanted = qualifier.lower()
    walker = node.parent if _is_expression(node) else None
    while walker is not None:
        if isinstance(walker, exp.Select):
            bindings = _scope_bindings(walker, cte_names)
            if wanted in bindings:
                return bindings[wanted]
        walker = walker.parent
    flat = _flat_bindings(expr, cte_names)
    if wanted in flat:
        return flat[wanted]
    return None


def _belongs_to(stmt: Statement, node: Any, table: str) -> str:
    """"yes", "no" or "unknown" - does this reference belong to that table?

    In a real warehouse the same two or three key columns are in nearly every
    table, so nearly every join has the same name on both sides. Matching on the
    name alone reports a filter on the OTHER table's column as a usage of the
    one being changed.

    Where it says "no", the usage is dropped. Where it says "unknown" the usage
    is KEPT with certain=False: nothing is thrown away, the table is marked as
    inferred rather than asserted.
    """
    expr = stmt.expr
    cte_names = _cte_names(expr)
    qualifier = ""
    if isinstance(node, exp.Column):
        qualifier = node.table or ""
    if not qualifier:
        real = [
            source
            for source in stmt.sources
            if short_name(source) not in cte_names
        ]
        if len(real) == 1:
            return "yes"
        return "unknown"
    if qualifier.lower() in cte_names:
        # That IS the chain being followed, so not a reason to rule it out.
        return "unknown"
    bound = _bindings_for(node, qualifier, expr, cte_names)
    if not bound:
        return "unknown"
    matches = [name for name in bound if not table or same_table(name, table)]
    if not matches:
        return "no"
    if len(bound) > 1:
        # A subquery alias over several tables: the SQL has not said which.
        return "unknown"
    return "yes"


# --------------------------------------------------------------------------
# What name a column leaves under
# --------------------------------------------------------------------------


def _struct_fields(struct: Any) -> list[tuple[str, Any]]:
    """(field name, field value) for every field of a STRUCT.

    Two ways a field is written and one of them has no AS:
        STRUCT(cm13 AS code) AS payload   the field is code
        STRUCT(cm13)         AS payload   named after itself
    Read past the bare one and a struct built out of plain column names
    publishes nothing at all, so the trail ends at the wrapper.
    """
    out: list[tuple[str, Any]] = []
    for item in getattr(struct, "expressions", None) or []:
        if not _is_expression(item):
            continue
        name = _alias_of(item)
        value = _unalias(item)
        if not name:
            name = _key(value)
        if name:
            out.append((name, value))
    return out


def _read_struct(
    struct: Any,
    prefix: str,
    direct: dict[str, list[str]],
    derived: dict[str, list[str]],
    depth: int,
    bare: bool,
) -> None:
    """Publish each field under its DOTTED name and never its bare one.

    The table really does have one column, payload, so publishing "code" as a
    column of it would invent a column that is not there. But payload.code IS
    how the field is read. SELECT AS VALUE STRUCT is the other spelling and is
    different: AS VALUE dissolves the wrapper outright, so there the fields ARE
    the columns and are published bare.

    Three deep and stop: that covers everything hand-written, and the cap is
    only there so a generated nest cannot run away.
    """
    if depth > 3:
        return
    for name, value in _struct_fields(struct):
        published = name if bare else (prefix + "." + name if prefix else name)
        inner = _unalias(value)
        if isinstance(inner, exp.Struct):
            _read_struct(inner, published, direct, derived, depth + 1, False)
            # The wrapper is published too, so a statement that reads it whole
            # is still followed.
            for column in _columns_in(inner):
                _add_name(derived, _key(column), published)
            continue
        for column in _columns_in(value):
            mapping = direct if isinstance(inner, exp.Column) else derived
            _add_name(mapping, _key(column), published)
            if prefix and not bare:
                # Alongside the wrapper's own name, not instead of it, so a
                # statement that reads payload whole is still followed.
                _add_name(mapping, _key(column), prefix)
            dotted = _dotted_key(column)
            if dotted:
                _add_name(mapping, dotted, published)


def _read_star(
    star: Any, direct: dict[str, list[str]], derived: dict[str, list[str]]
) -> set[str]:
    """What this ONE star does not carry on.

    Every star gets one vote: a sibling's EXCEPT must not delete a column
    another star is carrying, because which star a column flows through cannot
    be told from the select list.
    """
    dropped: set[str] = set()
    for column in star_except(star):
        key = _key(column)
        if key:
            dropped.add(key)
    for item in star_replace(star):
        # SELECT * REPLACE(x AS a): the output column a is fed by the
        # replacement from here on, not by the star.
        out_name = _alias_of(item) or _key(item)
        value = _unalias(item)
        if out_name:
            dropped.add(out_name.lower())
        for column in _columns_in(value):
            mapping = direct if isinstance(value, exp.Column) else derived
            _add_name(mapping, _key(column), out_name)
    for item in star_rename(star):
        # SELECT * RENAME(a AS b) does two things at once: the star stops
        # carrying a on under its own name, and carries it on as b.
        old = _key(_unalias(item))
        new = _alias_of(item) or _key(item)
        if old:
            dropped.add(old)
            _add_name(direct, old, new)
    return dropped


def _pivot_named_and_built(pivot: Any) -> tuple[list[str], list[str]]:
    """(the columns a pivot NAMES, the columns it BUILDS).

    An UNPIVOT's IN list is the column list being folded away; a PIVOT's IN list
    plus the columns inside its aggregates are what it names. A PIVOT's built
    names come from the parser - and where it did not work them out, the list is
    empty and nothing here pretends to know them.
    """
    named: list[str] = []
    built: list[str] = []
    unpivot = is_unpivot(pivot)

    for item in pivot_fields(pivot):
        if not _is_expression(item):
            continue
        # exp.In(this=<the FOR column>, expressions=[the IN list])
        for_column = _key(getattr(item, "this", None))
        for value in getattr(item, "expressions", None) or []:
            if isinstance(value, exp.Column):
                key = _key(value)
                if key and key not in named:
                    named.append(key)
        if for_column:
            if unpivot:
                # Renaming the source column changes what is written into the
                # name column just as surely, so follow both.
                if for_column not in built:
                    built.append(for_column)
            elif for_column not in named:
                named.append(for_column)

    for item in getattr(pivot, "expressions", None) or []:
        if not _is_expression(item):
            continue
        if unpivot:
            name = _alias_of(item) or _key(item)
            if name and name not in built:
                built.append(name)
        else:
            for column in _columns_in(item):
                key = _key(column)
                if key and key not in named:
                    named.append(key)

    if not unpivot:
        for name in pivot_columns(pivot):
            lowered = name.lower()
            if lowered not in built:
                built.append(lowered)
    return named, built


def _read_pivot(
    pivot: Any, direct: dict[str, list[str]], derived: dict[str, list[str]]
) -> set[str]:
    named, built = _pivot_named_and_built(pivot)
    for name in named:
        for out in built:
            _add_name(derived, name, out)
    return set(named)


def _whole_row_aliases(select: Any, cte_names: set[str]) -> bool:
    """Is a whole row being carried as one value?

    BigQuery lets a query pass an entire row around as a single value, and the
    standard dbt-utils deduplicate macro is written exactly that way: a bare
    name that is the table's ALIAS rather than any column of it is the whole
    row, so the star over it publishes every column the table has.

    Only a BARE reference counts. original.loaded_at is one column and
    STRUCT(a, b) AS s is two named ones.
    """
    bindings = _scope_bindings(select, cte_names)
    if not bindings:
        return False
    for item in select.expressions:
        value = _unalias(item)
        for column in _columns_in(value):
            if column.table:
                continue
            name = (column.name or "").lower()
            if name and name in bindings and bindings[name]:
                return True
    return False


def _read_item(
    item: Any, direct: dict[str, list[str]], derived: dict[str, list[str]], as_value: bool
) -> None:
    alias = _alias_of(item)
    value = _unalias(item)

    if isinstance(value, exp.Struct):
        _read_struct(value, alias, direct, derived, 1, as_value)
        return

    if isinstance(value, exp.Column):
        out = alias or (value.name or "")
        _add_name(direct, _key(value), out)
        dotted = _dotted_key(value)
        if dotted:
            # Register an aliased qualified reference under its dotted name as
            # well as its bare one.
            _add_name(direct, dotted, out)
        return

    out = alias or (getattr(item, "output_name", "") or "")
    for column in _columns_in(value):
        _add_name(derived, _key(column), out)
        dotted = _dotted_key(column)
        if dotted:
            _add_name(derived, dotted, out)


def _read_selects(selects: list[Any], cte_names: set[str], depth: int) -> _Level:
    """Every SELECT at one depth read into ONE set of maps."""
    direct: dict[str, list[str]] = {}
    derived: dict[str, list[str]] = {}
    star_votes: list[set[str]] = []
    other_dropped: set[str] = set()
    passthrough = False

    for select in selects:
        kind = str(select.args.get("kind") or "").upper()
        items = list(select.expressions)
        as_value = kind == "VALUE" and len(items) == 1 and isinstance(
            _unalias(items[0]), exp.Struct
        )
        for item in items:
            star = _star_of(item)
            if star is not None:
                passthrough = True
                star_votes.append(_read_star(star, direct, derived))
                continue
            _read_item(item, direct, derived, as_value)
        for pivot in _pivots_of(select):
            other_dropped |= _read_pivot(pivot, direct, derived)
        if _whole_row_aliases(select, cte_names):
            passthrough = True
            star_votes.append(set())

    dropped: set[str] = set()
    if star_votes:
        dropped = set(star_votes[0])
        for vote in star_votes[1:]:
            dropped &= vote
    dropped |= other_dropped
    return _Level(
        depth=depth,
        direct=direct,
        derived=derived,
        passthrough=passthrough,
        dropped=dropped,
    )


def _levels_of(stmt: Statement) -> list[_Level]:
    """The statement's levels, innermost first, cached on the statement.

    One scan asks the same statement about the same column many times, and on a
    600-line statement each answer means walking the whole tree again. Measured
    on a real repository, that was most of the time a scan took.
    """
    if stmt._levels is not None:
        return stmt._levels
    expr = stmt.expr
    levels: list[_Level] = []
    if _is_expression(expr):
        cte_names = _cte_names(expr)
        by_depth: dict[int, list[Any]] = {}
        for select in _selects_of(expr):
            if _is_value_position(select):
                continue
            by_depth.setdefault(_select_depth(select), []).append(select)
        for depth in sorted(by_depth, reverse=True):
            levels.append(_read_selects(by_depth[depth], cte_names, depth))
    stmt._levels = levels
    return levels


def _outputs_for(level: _Level, name: str) -> list[str]:
    """Every name this level publishes the held name under."""
    key = name.lower()
    out: list[str] = []
    for mapping in (level.direct, level.derived):
        for produced in mapping.get(key, []):
            if produced and produced not in out:
                out.append(produced)
    if "." in key:
        # Match a dotted name against the QUALIFIER too: matching on the leaf
        # alone invents a column that is not on the table.
        qualifier, _, rest = key.partition(".")
        for mapping in (level.direct, level.derived):
            for produced in mapping.get(qualifier, []):
                candidate = produced + "." + rest
                if candidate not in out:
                    out.append(candidate)
    return out


def _touches(level: _Level, names: list[str]) -> bool:
    for name in names:
        key = name.lower()
        if key in level.direct or key in level.derived or key in level.dropped:
            return True
        if "." in key:
            qualifier = key.split(".", 1)[0]
            if qualifier in level.direct or qualifier in level.derived:
                return True
    return False


def _through_level(level: _Level, names: list[str]) -> list[str]:
    """Resolve the names held through one level, to a FIXPOINT.

    The CTEs of one WITH are all at the same depth and they feed each other, so
    reading the level once applies only the first rename and the trail stops at
    a name the published table does not use. Which CTE feeds which is not
    knowable from depth, so run the level to a fixpoint instead: it gets the
    same answer whatever order they are written in. The set only grows and every
    name comes out of the statement, so it terminates; the counter is a
    backstop.
    """
    if not names:
        return []
    if not _touches(level, names) and not level.passthrough:
        # A level that is silent about the column is the ordinary case, not a
        # dead end. One unrelated CTE must not empty the list.
        return list(names)

    # `seen` starts EMPTY so that a level which carries the name through
    # unchanged - SELECT CAST(cm13 AS STRING) AS cm13_str, cm13 - still
    # publishes the unchanged name. Seeding it with the names held drops
    # exactly that one, and the next table reads it.
    seen: set[str] = set()
    produced: list[str] = []
    frontier = list(names)
    guard = 0
    while frontier and guard < 64:
        guard += 1
        nxt: list[str] = []
        for name in frontier:
            for out in _outputs_for(level, name):
                if out.lower() in seen:
                    continue
                seen.add(out.lower())
                produced.append(out)
                nxt.append(out)
        frontier = nxt

    kept: list[str] = []
    if level.passthrough:
        # Keep every name the level did NOT drop and put those FIRST: the
        # untouched name is the one the rest of the warehouse is likeliest to be
        # reading, and it has to survive the six-name cap.
        kept = [name for name in names if name.lower() not in level.dropped]

    out_names: list[str] = []
    for name in kept + produced:
        if name and name not in out_names:
            out_names.append(name)

    if not out_names:
        surviving = [name for name in names if name.lower() not in level.dropped]
        if not surviving:
            # Every name held is dropped here: the column really does stop
            # inside the statement, and saying so is the point of tracking it.
            return []
        if not produced and not level.passthrough:
            return surviving
        return surviving
    return out_names[:6]


def _outside_column_list(expr: Any) -> list[str]:
    """A column list written OUTSIDE the select renames by position.

        INSERT INTO stage_tbl (member_id) SELECT cm13 FROM ...
        CREATE OR REPLACE VIEW  v1(a, b)  AS SELECT cm13, region FROM ...
        CREATE OR REPLACE TABLE s1(a STRING, b STRING) AS SELECT ...

    The SELECT hands its values over by POSITION, not by name, so the name the
    column carries downstream is the one in the list on the left.
    """
    if not _is_expression(expr):
        return []
    this = getattr(expr, "this", None)
    if not isinstance(this, exp.Schema):
        return []
    names: list[str] = []
    for item in this.expressions:
        name = ""
        if isinstance(item, exp.ColumnDef):
            name = _key(item.this)
        else:
            name = _key(item)
        if not name:
            return []
        names.append(name)
    return names


def _top_projections(stmt: Statement) -> list[Any]:
    select = stmt.select
    if not _is_expression(select):
        return []
    return list(select.expressions)


def _rename_by_position(stmt: Statement, names: list[str]) -> list[str]:
    """Line the two lists up ONLY when they are plainly the same length and
    there is no star in the select list. Where the arity cannot be checked,
    leave the name exactly as it arrived rather than inventing a position."""
    columns = _outside_column_list(stmt.expr)
    if not columns:
        return names
    projections = _top_projections(stmt)
    if not projections or len(projections) != len(columns):
        return names
    for item in projections:
        if _star_of(item) is not None:
            return names
    out: list[str] = []
    for name in names:
        replaced = name
        for index, item in enumerate(projections):
            published = _alias_of(item) or (getattr(item, "output_name", "") or "")
            if published and published.lower() == name.lower():
                replaced = columns[index]
                break
        if replaced not in out:
            out.append(replaced)
    return out


def _alter_actions(expr: Any) -> list[Any]:
    if not _is_expression(expr):
        return []
    return [action for action in (expr.args.get("actions") or []) if _is_expression(action)]


def _alter_output_names(stmt: Statement, column: str) -> Optional[list[str]]:
    """ALTER TABLE t RENAME COLUMN a TO b is the plainest statement of a rename
    the language has. A DROP COLUMN stops the column here, in this file, by
    name."""
    expr = stmt.expr
    if not isinstance(expr, _ALTER_NODES):
        return None
    wanted = column.lower()
    for action in _alter_actions(expr):
        rename = getattr(exp, "RenameColumn", None)
        if rename is not None and isinstance(action, rename):
            old = _key(action.this)
            new = _key(action.args.get("to"))
            if old == wanted and new:
                return [new]
        if isinstance(action, exp.Drop):
            kind = str(action.args.get("kind") or "").upper()
            if kind == "COLUMN" and _key(action.this) == wanted:
                return []
        alter_column = getattr(exp, "AlterColumn", None)
        if alter_column is not None and isinstance(action, alter_column):
            if _key(action.this) == wanted:
                return [column]
    return None


def _insert_pairs(insert: Any) -> list[tuple[str, Any]]:
    """(target column, value) for an INSERT, which renames by position."""
    targets: list[str] = []
    this = getattr(insert, "this", None)
    if isinstance(this, (exp.Tuple, exp.Schema)):
        targets = [_key(item) for item in this.expressions]
    values = insert.args.get("expression") if _is_expression(insert) else None
    items: list[Any] = []
    if isinstance(values, exp.Values):
        for row in values.expressions:
            if isinstance(row, exp.Tuple):
                items.extend(row.expressions)
    elif isinstance(values, exp.Tuple):
        items = list(values.expressions)
    pairs: list[tuple[str, Any]] = []
    for index, item in enumerate(items):
        pairs.append((targets[index] if index < len(targets) else "", item))
    return pairs


def _merge_publications(stmt: Statement, names: list[str]) -> list[str]:
    """What a MERGE publishes the held names as.

    THEN UPDATE SET t.market = s.col and THEN INSERT (a, b) VALUES (x, y) are
    both renames. Follow the source's own name past them and the chain walks off
    the end at the one statement that loads the table.
    """
    expr = stmt.expr
    if not isinstance(expr, exp.Merge):
        return names
    held = {name.lower() for name in names}
    published: list[str] = []

    def publish(target: str) -> None:
        if target and target not in published:
            published.append(target)

    for branch in merge_whens(expr):
        if not _is_expression(branch):
            continue
        then = branch.args.get("then")
        if isinstance(then, exp.Update):
            for assignment in then.args.get("expressions") or []:
                if not isinstance(assignment, exp.EQ):
                    continue
                # Only the right-hand side reads the source table.
                for column in _columns_in(assignment.args.get("expression")):
                    if _key(column) in held or _dotted_key(column) in held:
                        publish(_key(assignment.this))
        elif isinstance(then, exp.Insert):
            for target, value in _insert_pairs(then):
                for column in _columns_in(value):
                    if _key(column) in held or _dotted_key(column) in held:
                        publish(target)
    return published or names


def output_names(stmt: Statement, column: str) -> list[str]:
    """What name (or names) a column leaves this statement under.

    Renames often happen inside a subquery - c.last_upd AS lut_ts buried in a
    ranking, then carried out unchanged by the enclosing SELECT - so resolve
    from the INNERMOST query outwards. A column also leaves under more than one
    name more often than it looks, so return every name, capped at 6, with the
    name carried through UNCHANGED always first so it survives the cap.
    """
    if not column:
        return []
    altered = _alter_output_names(stmt, column)
    if altered is not None:
        return altered

    names = [column]
    for level in _levels_of(stmt):
        names = _through_level(level, names)
        if not names:
            return []
    names = _merge_publications(stmt, names)
    names = _rename_by_position(stmt, names)

    out: list[str] = []
    unchanged = [name for name in names if name.lower() == column.lower()]
    for name in unchanged + names:
        if name and name not in out:
            out.append(name)
    return out[:6]


def first_output_name(stmt: Statement, column: str) -> str:
    """The one name a screen shows for a row.

    Falls back to the name the column arrived under when nothing is published at
    all: a row still has to say which column it is about.
    """
    names = output_names(stmt, column)
    return names[0] if names else column


# --------------------------------------------------------------------------
# How a column is used
# --------------------------------------------------------------------------


def label_for(usage: Usage) -> str:
    """The words a usage wears on screen.

    Swapped when the file says something more exact, so that the row matches the
    line it points at. A row that says "Carried by SELECT *" about a file that
    says COPY sends somebody to look for a statement that is not there, and then
    to doubt the finding rather than the label.
    """
    detail = (usage.detail or "").upper()
    if usage.kind == "pivoted" and detail == "UNPIVOT":
        return "Named in UNPIVOT"
    if usage.kind == "excluded" and detail == "REPLACE":
        return "Named in REPLACE"
    if usage.kind == "excluded" and detail == "RENAME":
        return "Named in RENAME"
    if usage.kind == "star" and detail in {"COPY", "CLONE", "LIKE", "RENAME"}:
        return "Carried by " + detail
    if usage.kind == "star" and usage.detail and detail not in {"COPY", "CLONE", "LIKE"}:
        return "Carried by a placeholder"
    return KIND_WORDS.get(usage.kind, usage.kind)


def mode_of(usages: Iterable[Usage]) -> str:
    for usage in usages:
        if usage.kind in {"transform", "dedup_key", "aggregation"}:
            return "Transformed"
    return "Direct pull"


def _literal_beside(node: Any) -> str:
    """The literal a filter compares the column against."""
    walker = node.parent if _is_expression(node) else None
    hops = 0
    while walker is not None and hops < 4:
        hops += 1
        if isinstance(walker, (exp.EQ, exp.NEQ, exp.GT, exp.GTE, exp.LT, exp.LTE, exp.Like)):
            for side in (walker.this, walker.args.get("expression")):
                if isinstance(side, exp.Literal):
                    return str(side.this)
            return ""
        if isinstance(walker, exp.In):
            values = [
                str(value.this)
                for value in (walker.args.get("expressions") or [])
                if isinstance(value, exp.Literal)
            ]
            if values:
                return ", ".join(values)
            return ""
        if isinstance(walker, exp.Between):
            low = walker.args.get("low")
            high = walker.args.get("high")
            if isinstance(low, exp.Literal) and isinstance(high, exp.Literal):
                return str(low.this) + " to " + str(high.this)
            return ""
        walker = walker.parent
    return ""


def _matches_column(node: Any, column: str) -> bool:
    if not isinstance(node, exp.Column):
        return False
    wanted = column.lower()
    if (node.name or "").lower() == wanted:
        return True
    dotted = _dotted_key(node)
    return bool(dotted) and dotted == wanted


def _columns_named(node: Any, column: str) -> list[Any]:
    if not _is_expression(node):
        return []
    return [found for found in node.find_all(exp.Column) if _matches_column(found, column)]


class _Collector:
    """Gathers candidate usages, then keeps the most informative of each kind."""

    def __init__(self, stmt: Statement, column: str, table: str) -> None:
        self.stmt = stmt
        self.column = column
        self.table = table
        self.found: list[Usage] = []

    def add(
        self,
        kind: str,
        node: Any = None,
        detail: str = "",
        alias: str = "",
        certain: bool = True,
        via_star: bool = False,
    ) -> None:
        if node is not None:
            verdict = _belongs_to(self.stmt, node, self.table)
            if verdict == "no":
                return
            if verdict == "unknown":
                certain = False
        if self.column.lower() in {name.lower() for name in self.stmt.guessed_columns}:
            # Read back as a column by hand, so never asserted as certain.
            certain = False
        self.found.append(
            Usage(
                kind=kind,
                column=self.column,
                alias=alias,
                detail=detail,
                certain=certain,
                via_star=via_star,
            )
        )

    def best(self) -> list[Usage]:
        by_kind: dict[str, Usage] = {}
        for usage in self.found:
            current = by_kind.get(usage.kind)
            if current is None:
                by_kind[usage.kind] = usage
                continue
            # One the SQL was explicit about beats one it was not; after that,
            # one carrying a detail beats one that does not.
            if usage.certain and not current.certain:
                by_kind[usage.kind] = usage
            elif usage.certain == current.certain and usage.detail and not current.detail:
                by_kind[usage.kind] = usage
        order = {kind: index for index, kind in enumerate(KIND_ORDER)}
        return sorted(by_kind.values(), key=lambda item: order.get(item.kind, 99))


def _read_select_list(collector: _Collector, select: Any, column: str) -> set[str]:
    """The select list, with stars handled on their own terms.

    Returns the names this select's stars stop carrying, so the star usage at
    the bottom can be suppressed for them.
    """
    suppressed: set[str] = set()
    for item in select.expressions:
        star = _star_of(item)
        if star is not None:
            for named in star_except(star):
                if _key(named) == column.lower():
                    # The star machinery reports this one, as excluded.
                    collector.add("excluded", None, detail="EXCEPT")
                    suppressed.add(column.lower())
            for replaced in star_replace(star):
                out_name = (_alias_of(replaced) or _key(replaced)).lower()
                value = _unalias(replaced)
                if out_name == column.lower():
                    # The column's own NAME is written down here. The output
                    # column of that name is fed by the replacement from here
                    # on, not by this one.
                    collector.add("excluded", None, detail="REPLACE")
                    suppressed.add(column.lower())
                for found in _columns_named(value, column):
                    collector.add("transform", found, detail="REPLACE")
            for renamed in star_rename(star):
                old = _key(_unalias(renamed))
                if old == column.lower():
                    collector.add("excluded", None, detail="RENAME")
                    suppressed.add(column.lower())
            continue

        value = _unalias(item)
        alias = _alias_of(item)
        if isinstance(value, exp.Column):
            if _matches_column(value, column):
                collector.add("select", value, alias=alias)
            continue
        for found in _columns_named(value, column):
            detail = ""
            if isinstance(value, exp.Struct):
                detail = "STRUCT"
            elif isinstance(value, exp.Cast):
                detail = "CAST"
            else:
                detail = _function_name(value) or ""
            collector.add("transform", found, detail=detail, alias=alias)
    return suppressed


def _read_predicates(collector: _Collector, select: Any, column: str) -> None:
    # QUALIFY is where nearly every dedup in a real pipeline is written, and the
    # column often appears NOWHERE else in the statement.
    for key in ("where", "having", "qualify"):
        clause = select.args.get(key)
        if not _is_expression(clause):
            continue
        for found in _columns_named(clause, column):
            collector.add("filter", found, detail=_literal_beside(found))

    for join in select.args.get("joins") or []:
        if not _is_expression(join):
            continue
        on = join.args.get("on")
        for found in _columns_named(on, column):
            collector.add("join_key", found)
        using = join.args.get("using") or []
        for item in using:
            if _key(item) == column.lower():
                collector.add("join_key", None)
        source = join.this
        if isinstance(source, exp.Unnest):
            for found in _columns_named(source, column):
                collector.add("transform", found, detail="UNNEST")

    from_clause = from_of(select)
    if _is_expression(from_clause) and isinstance(from_clause.this, exp.Unnest):
        for found in _columns_named(from_clause.this, column):
            collector.add("transform", found, detail="UNNEST")

    group = select.args.get("group")
    for found in _columns_named(group, column):
        collector.add("aggregation", found)

    order = select.args.get("order")
    if _is_expression(order):
        # ORDER BY writes the name down, so removing the column stops the
        # statement compiling and the table stops loading.
        order_kind = "ranking" if select.args.get("limit") is not None else "sort"
        for found in _columns_named(order, column):
            collector.add(order_kind, found)


def _read_windows(collector: _Collector, expr: Any, column: str) -> None:
    """A window ORDER BY is where removal is silent and awful, and a window
    PARTITION BY is the other half of a dedup. WINDOW w AS (...) is the same
    thing written as a named clause, and writing it the other way round is not a
    reason to miss it."""
    if not _is_expression(expr):
        return
    for window in expr.find_all(exp.Window):
        for found in _columns_named(window.args.get("order"), column):
            collector.add("ranking", found, detail="OVER")
        for item in window.args.get("partition_by") or []:
            for found in _columns_named(item, column):
                collector.add("dedup_key", found, detail="PARTITION BY")
    for select in _selects_of(expr):
        for window in select.args.get("windows") or []:
            for found in _columns_named(window.args.get("order"), column):
                collector.add("ranking", found, detail="WINDOW")
            for item in window.args.get("partition_by") or []:
                for found in _columns_named(item, column):
                    collector.add("dedup_key", found, detail="PARTITION BY")


def _read_extremes(collector: _Collector, expr: Any, column: str) -> None:
    """MAX and MIN decide which row survives."""
    if not _is_expression(expr):
        return
    for node in expr.find_all(exp.Max, exp.Min):
        for found in _columns_named(node, column):
            collector.add("dedup_key", found, detail=type(node).__name__.upper())


def _read_layout(collector: _Collector, expr: Any, column: str) -> None:
    """PARTITION BY and CLUSTER BY on the CREATE line sit outside the SELECT, so
    nothing that walks a query can see them. It is not a column of the table
    being built, so no chain follows from it - but the day the column goes the
    statement stops compiling, the table stops being built, and every published
    table underneath it quietly serves data that has stopped being refreshed.

    PARTITION BY cm13 with nothing round it parses as a bare IDENTIFIER, not a
    column, so searching for columns alone finds nothing.
    """
    if not isinstance(expr, exp.Create):
        return
    properties = expr.args.get("properties")
    if not _is_expression(properties):
        return
    wanted = column.lower()
    for prop in properties.expressions:
        if not _is_expression(prop):
            continue
        name = type(prop).__name__
        if "Partition" not in name and "Cluster" not in name:
            continue
        detail = "PARTITION BY" if "Partition" in name else "CLUSTER BY"
        hit = False
        for found in _columns_named(prop, column):
            collector.add("layout", found, detail=detail)
            hit = True
        if hit:
            continue
        for identifier in prop.find_all(exp.Identifier):
            if (identifier.name or "").lower() == wanted:
                collector.add("layout", None, detail=detail)
                break


def _read_pivots(collector: _Collector, expr: Any, column: str) -> set[str]:
    """Both fold a column away and build differently-named ones out of it, and
    both NAME the column while doing it, so the statement itself fails on the
    day the column goes. Label the row with the word the FILE uses - PIVOT and
    UNPIVOT are opposite operations."""
    suppressed: set[str] = set()
    if not _is_expression(expr):
        return suppressed
    for select in _selects_of(expr):
        for pivot in _pivots_of(select):
            named, _built = _pivot_named_and_built(pivot)
            if column.lower() in named:
                detail = "UNPIVOT" if is_unpivot(pivot) else "PIVOT"
                collector.add("pivoted", None, detail=detail)
                # The pivot is definitive about that one column; letting the
                # star speak as well puts "carried through untouched" beside
                # "named here, and this statement fails without it".
                suppressed.add(column.lower())
    return suppressed


def _read_merge(collector: _Collector, expr: Any, column: str) -> None:
    """A MERGE is how a published table is normally loaded, and all four parts
    of one have to be read."""
    if not isinstance(expr, exp.Merge):
        return
    for found in _columns_named(expr.args.get("on"), column):
        collector.add("join_key", found)
    for branch in merge_whens(expr):
        if not _is_expression(branch):
            continue
        condition = branch.args.get("condition")
        for found in _columns_named(condition, column):
            collector.add("filter", found, detail=_literal_beside(found))
        then = branch.args.get("then")
        if not _is_expression(then):
            continue
        if isinstance(then, exp.Update):
            for assignment in then.args.get("expressions") or []:
                if isinstance(assignment, exp.EQ):
                    # Read ONLY the right-hand side. It reads s.col and writes
                    # t.market; reading the whole assignment reports the target
                    # table's own column as a usage of the source.
                    value = assignment.args.get("expression")
                    alias = _key(assignment.this)
                    for found in _columns_named(value, column):
                        collector.add("select", found, alias=alias)
                else:
                    for found in _columns_named(assignment, column):
                        collector.add("select", found)
        elif isinstance(then, exp.Insert):
            # An INSERT renames by position, like a plain one.
            for target, value in _insert_pairs(then):
                for found in _columns_named(value, column):
                    collector.add("select", found, alias=target)


def _read_write_statement(collector: _Collector, expr: Any, column: str) -> bool:
    """A DELETE or UPDATE has a WHERE clause and no SELECT at all.

    Requiring a SELECT made both invisible, so "DELETE FROM stage WHERE
    market_code = 'US'" was reported as no usage whatsoever. An UPDATE's SET
    list is a usage in its own right, and the column is often named nowhere else
    in the statement.
    """
    if not isinstance(expr, (exp.Delete, exp.Update)):
        return False
    before = len(collector.found)
    where = expr.args.get("where")
    for found in _columns_named(where, column):
        collector.add("filter", found, detail=_literal_beside(found))
    if isinstance(expr, exp.Update):
        for assignment in expr.args.get("expressions") or []:
            if isinstance(assignment, exp.EQ):
                value = assignment.args.get("expression")
                alias = _key(assignment.this)
                for found in _columns_named(value, column):
                    collector.add("transform", found, detail="SET", alias=alias)
            else:
                for found in _columns_named(assignment, column):
                    collector.add("transform", found, detail="SET")
    if len(collector.found) == before:
        # Half a reading is worse than none here: the statement stops running on
        # the day of the change either way.
        for found in _columns_named(expr, column):
            collector.add("select", found)
    return True


def _read_values(collector: _Collector, expr: Any, column: str) -> None:
    """INSERT ... VALUES has no SELECT anywhere in it, so every usage check
    keyed on a SELECT was skipped and the statement recorded no usage of
    anything. That is exactly how a loop body is written."""
    if not _is_expression(expr):
        return
    for values in expr.find_all(exp.Values):
        for found in _columns_named(values, column):
            collector.add("select", found)


def _read_alter(collector: _Collector, expr: Any, column: str) -> None:
    if not isinstance(expr, _ALTER_NODES):
        return
    wanted = column.lower()
    for action in _alter_actions(expr):
        rename = getattr(exp, "RenameColumn", None)
        if rename is not None and isinstance(action, rename):
            if _key(action.this) == wanted:
                collector.add("renamed", None, detail=_key(action.args.get("to")))
            continue
        if isinstance(action, exp.Drop):
            kind = str(action.args.get("kind") or "").upper()
            if kind == "COLUMN" and _key(action.this) == wanted:
                # Not broken BY the change - it IS the change, and worth
                # reporting for exactly that reason.
                collector.add("dropped", None)
            continue
        alter_column = getattr(exp, "AlterColumn", None)
        if alter_column is not None and isinstance(action, alter_column):
            if _key(action.this) == wanted:
                collector.add("retyped", None)


def usages_of(stmt: Statement, column: str, table: str) -> list[Usage]:
    """How this statement uses that column, most consequential first.

    A clause not read is a column that cannot be seen, and the answer that comes
    back is not "unreadable" - it is "the name appears, but no lineage to a
    production table", which reads as a reassurance.
    """
    collector = _Collector(stmt, column, table)
    expr = stmt.expr
    suppressed: set[str] = set()

    if _is_expression(expr):
        for select in _selects_of(expr):
            if _is_value_position(select):
                continue
            suppressed |= _read_select_list(collector, select, column)
            _read_predicates(collector, select, column)
        _read_windows(collector, expr, column)
        _read_extremes(collector, expr, column)
        _read_layout(collector, expr, column)
        suppressed |= _read_pivots(collector, expr, column)
        _read_merge(collector, expr, column)
        _read_write_statement(collector, expr, column)
        _read_values(collector, expr, column)
        _read_alter(collector, expr, column)

    if column.lower() not in suppressed:
        levels = _levels_of(stmt)
        carried = any(level.passthrough for level in levels)
        dropped = any(column.lower() in level.dropped for level in levels)
        if carried and not dropped:
            detail = stmt.whole_copy or stmt.star_note
            collector.add(
                "star",
                None,
                detail=detail,
                certain=not bool(stmt.star_note),
                via_star=True,
            )
    return collector.best()


# --------------------------------------------------------------------------
# Shards
# --------------------------------------------------------------------------


def _suffix_comparisons(node: Any) -> Iterator[tuple[Any, bool]]:
    """Every comparison naming _TABLE_SUFFIX, with whether an OR or a NOT sits
    above it. Only ANDs are safe: an OR or a NOT above the comparison means
    other shards are read too."""
    if not _is_expression(node):
        return
    for found in node.find_all(exp.Column):
        if (found.name or "").upper() != "_TABLE_SUFFIX":
            continue
        loose = False
        walker = found.parent
        comparison = None
        while walker is not None:
            if comparison is None and isinstance(
                walker,
                (exp.EQ, exp.NEQ, exp.GT, exp.GTE, exp.LT, exp.LTE, exp.In, exp.Between),
            ):
                comparison = walker
            if isinstance(walker, (exp.Or, exp.Not)):
                loose = True
            walker = walker.parent
        yield comparison, loose


def _literal_text(node: Any) -> Optional[str]:
    if isinstance(node, exp.Literal) and node.is_string:
        return str(node.this)
    return None


def shard_verdict(stmt: Statement, wildcard: str, wanted: str) -> str:
    """"reads", "maybe" or "excluded" for one wildcard read of one shard.

    A wildcard table reads a whole family of date-sharded tables and the query
    almost always narrows that down on the very next line. Following the
    wildcard and never reading the line under it made a shard from 1999 the
    query provably never touches come back breaking and CERTAIN.

    Only judge a comparison when _TABLE_SUFFIX is on the LEFT of it, and treat
    an IN list or a BETWEEN as one that cannot be evaluated the moment ANY of
    its values is something other than a plain string literal.
    """
    if not wildcard.endswith("*"):
        return "reads"
    if wanted.endswith("*"):
        # Never narrow when the person typed the family name with the asterisk
        # in it: no one suffix can be tested.
        return "reads"
    prefix = short_name(wildcard)[:-1]
    short = short_name(wanted)
    if not short.startswith(prefix):
        return "reads"
    suffix = short[len(prefix):]

    verdict = "reads"
    for comparison, loose in _suffix_comparisons(stmt.expr):
        if comparison is None:
            verdict = "maybe"
            continue
        if loose:
            verdict = "maybe"
            continue
        left = comparison.this
        if not (isinstance(left, exp.Column) and (left.name or "").upper() == "_TABLE_SUFFIX"):
            # '20260101' = _TABLE_SUFFIX is legal, rare, and reading it
            # backwards excludes the wrong shard.
            verdict = "maybe"
            continue
        if isinstance(comparison, exp.Between):
            low = _literal_text(comparison.args.get("low"))
            high = _literal_text(comparison.args.get("high"))
            if low is None or high is None:
                verdict = "maybe"
                continue
            if not (low <= suffix <= high):
                return "excluded"
            continue
        if isinstance(comparison, exp.In):
            values = comparison.args.get("expressions") or []
            texts = [_literal_text(value) for value in values]
            if not texts or any(text is None for text in texts):
                verdict = "maybe"
                continue
            if suffix not in texts:
                return "excluded"
            continue
        right = _literal_text(comparison.args.get("expression"))
        if right is None:
            verdict = "maybe"
            continue
        if isinstance(comparison, exp.EQ) and suffix != right:
            return "excluded"
        if isinstance(comparison, exp.NEQ) and suffix == right:
            return "excluded"
        if isinstance(comparison, exp.GT) and not suffix > right:
            return "excluded"
        if isinstance(comparison, exp.GTE) and not suffix >= right:
            return "excluded"
        if isinstance(comparison, exp.LT) and not suffix < right:
            return "excluded"
        if isinstance(comparison, exp.LTE) and not suffix <= right:
            return "excluded"
    return verdict


# --------------------------------------------------------------------------
# Building one statement
# --------------------------------------------------------------------------


def _strip_templated_datasets(expr: Any, holes: set[str]) -> None:
    """A TEMPLATED DATASET IS NOT A DATASET.

    A filled-in {{stage_dataset}} looks exactly like a dataset called
    stage_dataset, and the file next door writes the very same dataset as a
    different hole. Record it as what it honestly is - the table, dataset not
    stated. A name with no dataset goes on matching any dataset, which is the
    safe direction.
    """
    if not holes or not _is_expression(expr):
        return
    lowered = {hole.lower() for hole in holes}
    for table in expr.find_all(exp.Table):
        database = table.db
        if database and str(database).lower() in lowered:
            table.set("db", None)
            table.set("catalog", None)


def _fill_projection_holes(expr: Any, holes: set[str]) -> str:
    """A hole standing where a projection goes is a SELECT * not yet filled in.

    Ripple reads "SELECT cols FROM ..." and believes the published table has
    exactly one column called cols. Replace it with a star, which makes the
    whole existing star machinery work, and record that the star came from a
    placeholder: the file does not say SELECT *, and a row that claims it does
    sends somebody to a line where no such statement is written.
    """
    if not holes or not _is_expression(expr):
        return ""
    lowered = {hole.lower() for hole in holes}
    note = ""
    for select in _selects_of(expr):
        kept: list[Any] = []
        changed = False
        for item in select.expressions:
            value = _unalias(item)
            if isinstance(value, exp.Column) and not value.table:
                name = (value.name or "").lower()
                if name in lowered:
                    kept.append(exp.Star())
                    changed = True
                    note = note or "{{" + (value.name or "") + "}}"
                    continue
            kept.append(item)
        if changed:
            select.set("expressions", kept)
    return note


def _read_back_parenless(expr: Any, sql: str) -> set[str]:
    """A column named after a parenless function.

    "SELECT current_date FROM customer_demographics" parses as a call and not as
    a column at all, so a table with a column of that name produces the cleanest
    possible zero. Which the writer meant cannot be known from the file, so
    follow BOTH - read the node back as a column - and mark every usage of that
    name in that statement as not certain. Only where the file writes the name
    with NO brackets after it.
    """
    guessed: set[str] = set()
    if not _is_expression(expr):
        return guessed
    for name in PARENLESS_FUNCTIONS:
        # CURRENT_DATE() with brackets is unambiguously the function, and the
        # lookahead has to allow for the space in "CURRENT_DATE ()".
        if not re.search(
            r"(?<![A-Za-z0-9_])" + name + r"(?![A-Za-z0-9_])(?!\s*\()", sql, re.IGNORECASE
        ):
            continue
        node_class = getattr(exp, "".join(part.capitalize() for part in name.split("_")), None)
        if node_class is None:
            continue
        for node in list(expr.find_all(node_class)):
            if node.args.get("this") is not None:
                continue
            try:
                node.replace(exp.column(name.lower()))
            except Exception:
                continue
            guessed.add(name.lower())
    return guessed


def _whole_copy_rewrite(sql: str) -> Optional[tuple[str, str]]:
    """(rewritten SQL, the word the file used) for a whole-table copy.

    A whole-table copy carries every column and writes none of them down, which
    is exactly what SELECT * means - so rewrite it into CREATE TABLE t AS SELECT
    * FROM s and every piece that already follows a star works on it unchanged.
    That single line is what connects everything upstream to the table people
    actually read; with no source recorded the trail died at the staging table
    and the screen said "last table in the chain", which reads as an answer.
    """
    match = _WHOLE_COPY_RE.match(sql)
    if match:
        word = match.group("word").upper()
        rewritten = "CREATE TABLE {target} AS SELECT * FROM {source}".format(
            target=match.group("target"), source=match.group("source")
        )
        return rewritten, word
    match = _RENAME_TO_RE.match(sql)
    if match:
        rewritten = "CREATE TABLE {target} AS SELECT * FROM {source}".format(
            target=match.group("target"), source=match.group("source")
        )
        return rewritten, "RENAME"
    return None


def _parse_one(sql: str, dialect: str) -> Any:
    """One statement, or None. CREATE SNAPSHOT TABLE is retried only after the
    parser has already failed, so it costs nothing on the statements that read
    normally."""
    try:
        return sqlglot.parse_one(sql, read=dialect or None)
    except Exception:
        pass
    if re.search(r"CREATE\s+SNAPSHOT\s+TABLE", sql, re.IGNORECASE):
        retried = re.sub(
            r"CREATE\s+SNAPSHOT\s+TABLE", "CREATE TABLE", sql, flags=re.IGNORECASE
        )
        try:
            return sqlglot.parse_one(retried, read=dialect or None)
        except Exception:
            return None
    return None


def _target_of(expr: Any) -> Any:
    """The table node this statement WRITES, or None.

    Handed back as the NODE and never as a name: the source walk skips its
    target by identity, and comparing names instead loses every source of
    INSERT INTO t SELECT ... FROM t.
    """
    if isinstance(expr, (exp.Create, exp.Insert, exp.Delete, exp.Update, exp.Merge)):
        this = getattr(expr, "this", None)
        if isinstance(this, exp.Schema):
            this = this.this
        if isinstance(this, exp.Table):
            return this
        return None
    if isinstance(expr, _ALTER_NODES):
        for action in _alter_actions(expr):
            if isinstance(action, RENAME_NODE):
                new = getattr(action, "this", None)
                if isinstance(new, exp.Table):
                    return new
        this = getattr(expr, "this", None)
        if isinstance(this, exp.Table):
            return this
    return None


def _table_function_target(expr: Any) -> str:
    """A BigQuery TABLE FUNCTION is a table as far as lineage is concerned.

    A scalar UDF parses as the very same node with the very same kind, so tell
    them apart by their BODY - a table function's is a SELECT, a scalar one's is
    an expression. Getting this wrong turns every helper in the repository into
    a table.
    """
    if not isinstance(expr, exp.Create):
        return ""
    kind = str(expr.args.get("kind") or "").upper()
    if "FUNCTION" not in kind:
        return ""
    body = expr.args.get("expression")
    inner = _unalias(body)
    if isinstance(inner, exp.Subquery):
        inner = inner.this
    if not isinstance(inner, exp.Select):
        return ""
    this = getattr(expr, "this", None)
    signature = getattr(this, "this", None)
    if signature is None:
        return ""
    if isinstance(signature, exp.Table):
        return _table_name(signature)
    text = signature.sql() if _is_expression(signature) else str(signature)
    return ".".join(_clean_part(part) for part in text.split(".") if part.strip())


def _function_calls_in_from(expr: Any) -> Iterator[tuple[Any, str]]:
    """Every call sitting in a FROM clause, with its alias."""
    if not _is_expression(expr):
        return
    for select in _selects_of(expr):
        items: list[Any] = []
        from_clause = from_of(select)
        if _is_expression(from_clause):
            items.append(from_clause.this)
        for join in select.args.get("joins") or []:
            if _is_expression(join):
                items.append(join.this)
        for item in items:
            if not _is_expression(item):
                continue
            alias = item.alias_or_name or ""
            inner = item.this if isinstance(item, exp.Table) else item
            if isinstance(inner, (exp.Unnest, exp.Values, exp.Subquery, exp.Select)):
                continue
            if isinstance(inner, (exp.Func, exp.Dot)) and not isinstance(
                inner, exp.Identifier
            ):
                yield inner, alias


def _sources_of(expr: Any, target_node: Any, cte_names: set[str]) -> list[str]:
    """Every table the statement reads.

    Walk EVERY table node in the WHOLE statement, not the tables of its first
    SELECT: a union is two SELECTs side by side, and reading only the first
    leaves the second half's table recorded nowhere.

    The walk finds the table the statement WRITES as well, so it is left out BY
    NODE IDENTITY, never by comparing names - comparing names goes through
    same_table, which is deliberately loose, and three ordinary shapes lose
    everything they read that way.
    """
    sources: list[str] = []

    def keep(name: str) -> None:
        if not name or is_metadata(name):
            return
        if name not in sources:
            sources.append(name)

    if not _is_expression(expr):
        return sources

    for table in expr.find_all(exp.Table):
        if target_node is not None and table is target_node:
            continue
        inner = table.this
        if isinstance(inner, (exp.Func, exp.Dot)) and not isinstance(inner, exp.Identifier):
            # Handled with the calls below, where the skip list applies.
            continue
        name = _table_name(table)
        if not name:
            continue
        if not table.db and short_name(name) in cte_names:
            # A CTE is a name for a query; treating one as a table invents a
            # link that is not there.
            continue
        keep(name)

    for call, _alias in _function_calls_in_from(expr):
        name = _function_name(call)
        short = name.split(".")[-1]
        if short not in SKIP_TABLE_FUNCTIONS and name not in SKIP_TABLE_FUNCTIONS:
            keep(".".join(_clean_part(part) for part in name.split(".")).lower())
        # A TABLE handed into a function is a real read, and it is not a table
        # node: the rescue pass takes the word TABLE out so the statement parses
        # at all, and what is left arrives among the arguments as an ordinary
        # column reference. Only column-shaped ones count - a literal, a number
        # or a nested call is not a table.
        for argument in getattr(call, "expressions", None) or []:
            if isinstance(argument, exp.Column):
                parts = [
                    part
                    for part in (argument.catalog, argument.db, argument.table, argument.name)
                    if part
                ]
                keep(".".join(_clean_part(str(part)) for part in parts))
            elif isinstance(argument, exp.Dot):
                keep(
                    ".".join(
                        _clean_part(part)
                        for part in argument.sql().replace("`", "").split(".")
                    )
                )
    return sources


def _statement_from(
    expr: Any,
    *,
    file: str,
    lang: str,
    sql: str,
    line_offset: int,
    line_end: int,
    holes: set[str],
    whole_copy: str = "",
    built_as_text: str = "",
) -> Statement:
    _strip_templated_datasets(expr, holes)
    star_note = _fill_projection_holes(expr, holes)
    guessed = _read_back_parenless(expr, sql)

    target_node = _target_of(expr)
    target = _table_name(target_node) if target_node is not None else ""
    if not target:
        target = _table_function_target(expr)
    if is_metadata(target):
        # Never record the warehouse describing itself as a target.
        target = ""

    cte_names = _cte_names(expr)
    sources = _sources_of(expr, target_node, cte_names)

    if isinstance(expr, (exp.Delete, exp.Update) + tuple(_ALTER_NODES)):
        # A DELETE or UPDATE also reads its own target, or nothing ever looks at
        # its WHERE clause.
        if target and target not in sources:
            sources.append(target)

    select = expr if isinstance(expr, exp.Select) else None
    if select is None and _is_expression(expr):
        for candidate in _selects_of(expr):
            if not _is_value_position(candidate):
                select = candidate
                break

    return Statement(
        file=file,
        lang=lang,
        line_offset=line_offset,
        line_end=line_end,
        sql=sql,
        target=target,
        sources=set(sources),
        select=select,
        expr=expr,
        whole_copy=whole_copy,
        star_note=star_note,
        guessed_columns=guessed,
        built_as_text=built_as_text,
    )


# --------------------------------------------------------------------------
# The shapes that name a table and were invisible
# --------------------------------------------------------------------------


def _execute_immediate_text(sql: str) -> Optional[str]:
    """The SQL inside EXECUTE IMMEDIATE, when the WHOLE thing after IMMEDIATE is
    one quoted string and nothing else.

    REFUSE when the name is built rather than quoted: FORMAT(...), a
    concatenation, or a literal holding a "?" placeholder. In each of those the
    statement never exists as text anywhere, so there is nothing to read, and
    inventing the missing piece is the exact failure this reader exists to
    avoid.
    """
    match = _EXECUTE_IMMEDIATE_RE.match(sql)
    if not match:
        return None
    rest = sql[match.end():].strip()
    if not rest:
        return None
    if "||" in rest or re.match(r"FORMAT\s*\(", rest, re.IGNORECASE):
        return None
    # Try the TRIPLE quotes first: a whole CREATE written inside an EXECUTE
    # IMMEDIATE is nearly always triple-quoted, and checking ' first reads the
    # opening ''' as an empty string and loses the chain.
    for opener in ("'''", '"""', "'", '"'):
        if not rest.startswith(opener):
            continue
        end = rest.find(opener, len(opener))
        if end == -1:
            return None
        body = rest[len(opener):end]
        tail = rest[end + len(opener):].strip().rstrip(";").strip()
        if tail and not re.match(r"(INTO|USING)\b", tail, re.IGNORECASE):
            return None
        if "?" in body:
            return None
        return body
    return None


def _reference_from(sql: str) -> Optional[tuple[str, str, list[str]]]:
    """(kind, table, columns) for a statement that names a table and carries
    nothing anywhere. Read with a regular expression rather than a parser:
    reading it loosely can add a row to a list, and it must never move a
    chain."""
    match = _SEARCH_INDEX_RE.match(sql)
    if match:
        kind = match.group("kind").upper() + " INDEX"
        columns = [
            _clean_part(part) for part in match.group("columns").split(",") if part.strip()
        ]
        return kind, _clean_part(match.group("table")), columns
    match = _POLICY_RE.match(sql)
    if match:
        return (
            "ROW ACCESS POLICY",
            _clean_part(match.group("table")),
            _policy_columns(sql),
        )
    match = _UNDROP_RE.match(sql)
    if match:
        return "UNDROP TABLE", _clean_part(match.group("table")), []
    return None


def _policy_columns(sql: str) -> list[str]:
    """The names a row access policy filters on, read loosely.

    A row access policy filtering on the scanned column stops working the day
    the column goes, so risk may not read "none" while one of these names it.
    """
    columns: list[str] = []
    filter_match = _FILTER_USING_RE.search(sql)
    if filter_match is None:
        return columns
    for word in _WORD_RE.findall(filter_match.group("body")):
        if word.lower() in _SQL_KEYWORDS_IN_POLICY:
            continue
        if word not in columns:
            columns.append(word)
    return columns


def _references_in(path: str, text: str) -> list[Reference]:
    """Every CREATE SEARCH INDEX, VECTOR INDEX, ROW ACCESS POLICY and UNDROP
    TABLE in a file.

    All name a table, most name columns of it, and none carries a column
    anywhere. The parser gives up on every one, so the whole statement was
    invisible and the file landed on the check-by-hand list with nothing saying
    which table or which column it was about. Recorded as "referenced here" -
    never as lineage, never as an edge, never as a hop.
    """
    out: list[Reference] = []

    def line_at(position: int) -> int:
        return text.count("\n", 0, position) + 1

    for match in _SEARCH_INDEX_RE.finditer(text):
        columns = [
            _clean_part(part) for part in match.group("columns").split(",") if part.strip()
        ]
        out.append(
            Reference(
                file=path,
                line=line_at(match.start()),
                kind=match.group("kind").upper() + " INDEX",
                table=_clean_part(match.group("table")),
                columns=columns,
                text=match.group(0).splitlines()[0].strip(),
            )
        )
    for match in _POLICY_RE.finditer(text):
        tail = text[match.start():]
        out.append(
            Reference(
                file=path,
                line=line_at(match.start()),
                kind="ROW ACCESS POLICY",
                table=_clean_part(match.group("table")),
                columns=_policy_columns(tail.split(";")[0]),
                text=match.group(0).splitlines()[0].strip(),
            )
        )
    for match in _UNDROP_RE.finditer(text):
        out.append(
            Reference(
                file=path,
                line=line_at(match.start()),
                kind="UNDROP TABLE",
                table=_clean_part(match.group("table")),
                columns=[],
                text=match.group(0).strip(),
            )
        )
    return out


def _export_place(uri: str) -> str:
    """Where an EXPORT DATA delivers to.

    Drop the last path segment when it holds a "*" or a "." - that is a filename
    pattern, not a place.
    """
    parts = uri.split("/")
    if len(parts) > 1 and ("*" in parts[-1] or "." in parts[-1]):
        parts = parts[:-1]
    return "/".join(parts)


def _export_uris(chunks: list[tuple[str, int]]) -> dict[int, str]:
    """Match exports to statements in FILE ORDER, not by line number: the
    rewrite removes the whole "EXPORT DATA OPTIONS(...) AS", so what is left
    starts on the line after the export's own."""
    out: dict[int, str] = {}
    for index, (sql, _line) in enumerate(chunks):
        if not re.match(r"\s*EXPORT\s+DATA\b", sql, re.IGNORECASE):
            continue
        match = re.search(r"\buri\s*=\s*'([^']*)'", sql, re.IGNORECASE)
        if match is None:
            match = re.search(r'\buri\s*=\s*"([^"]*)"', sql, re.IGNORECASE)
        if match is None:
            continue
        out[index] = _export_place(match.group(1))
    return out


# --------------------------------------------------------------------------
# Parsing a block, a file, a repository
# --------------------------------------------------------------------------


def _dialect_of(cfg: Any) -> str:
    return str(getattr(cfg, "sql_dialect", "") or "")


def _first_code_line(text: str) -> str:
    """The file's own first line of code, comments and placeholders taken off.

    THE TRAP behind the dbt reading: several statements that build nothing and
    are named after nothing are rewritten into a bare SELECT on the way into the
    parser - EXPORT DATA is the one that caught this - and by the time the tree
    exists they are indistinguishable from a dbt model.
    """
    cleaned = re.sub(r"/\*.*?\*/", " ", text, flags=re.DOTALL)
    for raw in cleaned.splitlines():
        line = re.sub(r"\{\{.*?\}\}", " ", raw)
        line = re.sub(r"--.*$", "", line)
        line = re.sub(r"^\s*#.*$", "", line)
        line = line.strip()
        if line:
            return line
    return ""


def _first_code_line_number(text: str) -> int:
    """1-based line of the first code in a chunk, for the opaque list."""
    for index, raw in enumerate(text.splitlines()):
        if raw.strip():
            return index + 1
    return 1


def parse_block(
    sql: str,
    cfg: Any,
    *,
    file: str = "",
    lang: str = "sql",
    line_offset: int = 0,
    holes: Optional[set[str]] = None,
    exports: Optional[dict[int, str]] = None,
) -> tuple[list[Statement], list[Unreadable], list[dict]]:
    """One block of SQL, already filled in and already through the rescue pass.

    Kept as its own seam so a test can hand it plain SQL: everything above it -
    placeholders, unwrapping, the shapes the parser refuses - belongs to Phase 3
    and is applied in parse_file.
    """
    holes = holes or set()
    exports = exports or {}
    dialect = _dialect_of(cfg)
    statements: list[Statement] = []
    problems: list[Unreadable] = []
    opaque: list[dict] = []

    chunks = split_statements(sql)
    if not chunks:
        return statements, problems, opaque

    parsed: list[Any] = []
    aligned = False
    try:
        parsed = [item for item in sqlglot.parse(sql, read=dialect or None)]
        parsed = [item for item in parsed if item is not None]
        aligned = len(parsed) == len(chunks)
    except Exception:
        parsed = []
        aligned = False

    if not parsed or not aligned:
        # One bad statement must cost one statement, not the file.
        parsed = []
        aligned = True
        for chunk_sql, _start in chunks:
            parsed.append(_parse_chunk_expression(chunk_sql, dialect))

    block_start = line_offset + chunks[0][1]
    block_end = line_offset + chunks[-1][1] + chunks[-1][0].count("\n")

    for index, (chunk_sql, start) in enumerate(chunks):
        expr = parsed[index] if index < len(parsed) else None
        if aligned:
            first = line_offset + start
            last = first + chunk_sql.count("\n")
        else:
            # Where the two counts do not match, give every statement the
            # block's offset and the block's last line rather than a span that
            # might be wrong.
            first, last = block_start, block_end

        made = _read_chunk(
            chunk_sql,
            expr,
            cfg=cfg,
            file=file,
            lang=lang,
            first=first,
            last=last,
            holes=holes,
            statements=statements,
            problems=problems,
            opaque=opaque,
        )
        if made is not None and index in exports:
            made.export_uri = exports[index]
    return statements, problems, opaque


def _parse_chunk_expression(chunk_sql: str, dialect: str) -> Any:
    rewritten = _whole_copy_rewrite(chunk_sql)
    if rewritten is not None:
        return _parse_one(rewritten[0], dialect)
    return _parse_one(chunk_sql, dialect)


def _read_chunk(
    chunk_sql: str,
    expr: Any,
    *,
    cfg: Any,
    file: str,
    lang: str,
    first: int,
    last: int,
    holes: set[str],
    statements: list[Statement],
    problems: list[Unreadable],
    opaque: list[dict],
) -> Optional[Statement]:
    """One chunk, all four of the shapes that used to be invisible included."""
    dialect = _dialect_of(cfg)
    code_line = first + _first_code_line_number(chunk_sql)
    first_line = _first_code_line(chunk_sql)

    reference = _reference_from(chunk_sql)
    if reference is not None:
        kind, table, columns = reference
        problems.append(
            Unreadable(
                file=file,
                message=(
                    "This statement names " + display_table(table)
                    + " but carries no column anywhere - " + kind
                ),
                line=code_line,
                text=first_line,
                hint="referenced",
            )
        )
        return None

    call = _CALL_RE.match(chunk_sql)
    if call is not None:
        opaque.append({"line": code_line, "text": first_line, "sql": chunk_sql})
        return None

    if _EXECUTE_IMMEDIATE_RE.match(chunk_sql):
        inner_sql = _execute_immediate_text(chunk_sql)
        made: list[Statement] = []
        inner_problems: list[Unreadable] = []
        if inner_sql is not None:
            made, inner_problems, _inner_opaque = parse_block(
                inner_sql, cfg, file=file, lang=lang, line_offset=first, holes=holes
            )
        if not made:
            # REFUSE and stay unreadable where the name is built rather than
            # quoted: the statement never exists as text anywhere, so there is
            # nothing to read, and inventing the missing piece is the exact
            # failure this reader exists to avoid. The same answer when the
            # text inside the quotes parses to nothing but another statement
            # the parser could not understand: nothing was learned from it, so
            # say so rather than recording an empty statement.
            problems.append(
                Unreadable(
                    file=file,
                    message=(
                        "This statement builds its SQL as text and Ripple could not "
                        "read what it builds"
                    ),
                    line=code_line,
                    text=first_line,
                )
            )
            for problem in inner_problems:
                problems.append(problem)
            return None
        last_made: Optional[Statement] = None
        for statement in made:
            statement.built_as_text = "EXECUTE IMMEDIATE"
            statement.line_offset = first
            statement.line_end = last
            statements.append(statement)
            last_made = statement
        return last_made

    whole_copy = ""
    rewritten = _whole_copy_rewrite(chunk_sql)
    if rewritten is not None:
        whole_copy = rewritten[1]
        # Whatever the parser made of the copy, the rewritten CREATE ... AS
        # SELECT * is the shape every star rule already works on unchanged.
        expr = _parse_one(rewritten[0], dialect) or expr

    if expr is None:
        problems.append(
            Unreadable(
                file=file,
                message="Ripple could not read this statement",
                line=code_line,
                text=first_line,
            )
        )
        return None

    if isinstance(expr, exp.Command):
        # A procedure call, a loop, a scripting block. Kept, not reported:
        # whether they matter depends entirely on whether the name somebody is
        # chasing turns up inside one, which is not known here.
        opaque.append({"line": code_line, "text": first_line, "sql": chunk_sql})
        return None

    statement = _statement_from(
        expr,
        file=file,
        lang=lang,
        sql=chunk_sql,
        line_offset=first,
        line_end=last,
        holes=holes,
        whole_copy=whole_copy,
    )
    statements.append(statement)
    return statement


def parse_file(
    f: Any, cfg: Any
) -> tuple[list[Statement], list[Unreadable], dict[str, list[dict]]]:
    """Everything one file says, in statements, problems and opaque blocks."""
    path = str(getattr(f, "path", "") or "")
    lang = str(getattr(f, "lang", "") or "")
    text = str(getattr(f, "text", "") or "")
    statements: list[Statement] = []
    problems: list[Unreadable] = []
    opaque: dict[str, list[dict]] = {}

    # Phase 2 is the file that knows how to get SQL out of a .py, a .sh or a
    # .yaml as well as out of a .sql, and it hands back the line each block
    # starts on. Phase 3's unwrap_blocks does something different - it takes
    # the scripting out of one piece of text - so it is applied to each block
    # below rather than used to find them.
    blocks = statements_for(f) or []
    holds_sql = bool(
        re.search(r"\b(SELECT|INSERT|MERGE|CREATE|UPDATE|DELETE)\b", text, re.IGNORECASE)
    )
    templated = bool(placeholder_names(text))

    for block_text, block_offset in blocks:
        holes = set(placeholder_names(block_text) or set())
        filled = fill_placeholders(block_text) if holes else block_text
        # The scripting comes out before the parser sees any of it. This hands
        # back the whole block with its line count unchanged, so block_offset
        # still points at the line the reader will be sent to.
        unwrapped = unwrap_blocks(filled)
        # Read the uri BEFORE the rescue pass strips the OPTIONS clause, and
        # read it off the SAME text parse_block will split: an export is matched
        # to its statement by position, and unwrapping turns a scripting line
        # into a statement end, so counting on the text before that would hand
        # the uri to the wrong statement.
        exports = _export_uris(split_statements(unwrapped))
        rescued = rescue_text(unwrapped)
        made, block_problems, block_opaque = parse_block(
            rescued,
            cfg,
            file=path,
            lang=lang,
            line_offset=block_offset,
            holes=holes,
            exports=exports,
        )
        statements.extend(made)
        problems.extend(block_problems)
        if block_opaque:
            opaque.setdefault(path, []).extend(block_opaque)

    _name_after_the_file(statements, path, text)

    total = len(statements) + len([p for p in problems if p.hint != "referenced"])
    failures = [p for p in problems if p.hint != "referenced"]
    collapsed: list[Unreadable] = [p for p in problems if p.hint == "referenced"]

    if failures:
        # Collapse repeated failures in one file to a single entry with a count:
        # it is still one file for a person to go and check.
        first = failures[0]
        if statements:
            message = (
                "{bad} of {total} statements in this file could not be read - "
                "the other {good} were".format(
                    bad=len(failures), total=total, good=len(statements)
                )
            )
        else:
            message = (
                "This file was read but not one statement in it was understood - "
                "check the SQL dialect setting"
            )
        collapsed.append(
            Unreadable(
                file=path,
                message=message,
                line=first.line,
                text=first.text,
                count=len(failures),
                hint=_hint_for(templated, cfg),
            )
        )
    elif not statements and holds_sql:
        collapsed.append(
            Unreadable(
                file=path,
                message=(
                    "This file plainly contains SQL and none of it could be taken out"
                ),
                line=1,
                text=_first_code_line(text),
                hint=_hint_for(templated, cfg),
            )
        )

    return statements, collapsed, opaque


def _hint_for(templated: bool, cfg: Any) -> str:
    dialect = _dialect_of(cfg)
    hints: list[str] = []
    if templated:
        hints.append("this file is a template, so the SQL is only complete once it is filled in")
    if not dialect or dialect.lower() in {"sql", "generic", "none"}:
        hints.append("the repository is being read as generic SQL, not as one warehouse's")
    return "; ".join(hints)


def _name_after_the_file(statements: list[Statement], path: str, text: str) -> None:
    """A file that is one query and builds nothing.

    A dbt model is a bare SELECT: there is no CREATE, no INSERT and no MERGE, so
    nothing in the file names the table it builds - dbt does, after the file.
    models/marts/customer_published.sql builds customer_published. Get this
    wrong and EVERY dbt repository produces zero lineage, which is the loudest
    possible version of this tool's worst failure.

    Three levels of evidence, labelled differently because they are not equally
    sure, and recorded on the statement as named_by.
    """
    bare = [
        statement
        for statement in statements
        if not statement.target and statement.select is not None
    ]
    if len(bare) != 1:
        # Two bare SELECTs in one file cannot both be the table the file is
        # named after.
        return
    statement = bare[0]
    lowered = path.lower()
    stem = lowered.rsplit("/", 1)[-1]
    for suffix in (".sqlx", ".sql"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    if not stem:
        return

    first_line = _first_code_line(text)
    starts_query = first_line.upper().startswith(("SELECT", "WITH"))
    parts = lowered.split("/")

    if lowered.endswith(".sqlx") or first_line.lower().startswith("config"):
        statement.named_by = "Dataform"
        statement.target = stem
        return
    only_query = len(statements) == 1
    if not only_query or not starts_query:
        return
    under_models = any(part in {"models", "snapshots", "definitions"} for part in parts)
    calls_dbt = bool(re.search(r"\b(ref|source|config|this)\s*\(", text))
    if under_models or calls_dbt:
        statement.named_by = "dbt"
        statement.target = stem
        return
    if lowered.endswith(".sql") and not re.search(r"\bCREATE\b", text, re.IGNORECASE):
        statement.named_by = "file"
        statement.target = stem


# --------------------------------------------------------------------------
# Everything that can only be done once the whole file is parsed
# --------------------------------------------------------------------------


def _temp_names_of(statements: list[Statement], text: str) -> set[str]:
    names: set[str] = set()
    lines = text.splitlines()
    for statement in statements:
        if not statement.target:
            continue
        temp = is_temporary(statement.expr)
        if not temp:
            index = statement.line_offset
            if 0 <= index < len(lines):
                temp = bool(
                    re.search(
                        r"CREATE\s+(?:OR\s+REPLACE\s+)?(TEMP|TEMPORARY)\s+TABLE",
                        lines[index],
                        re.IGNORECASE,
                    )
                )
        if temp:
            names.add(short_name(statement.target))
    return names


def _move_name(name: str, temp_names: set[str], scope: str) -> str:
    """Move a name only when it has no dataset, or the _SESSION dataset BigQuery
    uses for temp tables. ds.t is a real table that happens to share a short
    name with a temp one, and taking it would cut a genuine chain."""
    dataset, short = _split_name(name)
    if short not in temp_names:
        return name
    if dataset and dataset != "_session":
        return name
    return scope + "." + short


def _fence_temp_tables(statements: list[Statement], path: str, text: str) -> set[str]:
    """A TEMPORARY TABLE BELONGS TO ONE FILE.

    Temp names in real repositories are t, tmp, stg, base, deduped, so
    collisions are the norm. Two unrelated files each building their own "t" put
    BOTH of their published tables on the chain, marked the second one breaking,
    and printed no warning of any kind. Applied once the whole file is parsed, so
    a temp table used above the line that creates it is still caught.
    """
    temp_names = _temp_names_of(statements, text)
    if not temp_names:
        return temp_names
    scope = scope_for(path)
    for statement in statements:
        if statement.target:
            statement.target = _move_name(statement.target, temp_names, scope)
        moved = {_move_name(source, temp_names, scope) for source in statement.sources}
        if moved != statement.sources:
            statement.sources = moved
        forget_source_cache(statement)
    return temp_names


def _query_variables(statements: list[Statement], path: str, text: str) -> dict[str, str]:
    """The script variables of this file, fenced exactly as a temp table is.

    Only a variable filled FROM A QUERY counts - DECLARE i INT64 DEFAULT 0 binds
    nothing anybody can follow, and giving every loop counter a name on screen
    fills it with dead ends.
    """
    variables: dict[str, str] = {}
    scope = scope_for(path)
    lines = text.splitlines()
    for statement in statements:
        expr = statement.expr
        name = ""
        holds_query = False
        binders = tuple(node for node in (_DECLARE_NODE, _SET_NODE) if node is not None)
        if binders and isinstance(expr, binders):
            for item in expr.expressions:
                # Guard the shapes you walk: BEGIN TRANSACTION is an exp.Set
                # with a plain BOOLEAN in it, and reaching for .find on one
                # takes down the whole file with an AttributeError.
                if not _is_expression(item):
                    continue
                candidate = _key(getattr(item, "this", None)) or _key(item)
                if not candidate:
                    continue
                if item.find(exp.Select) is None:
                    continue
                name = candidate
                holds_query = True
                break
        if name and holds_query:
            variables[name.lower()] = scope + "." + name.lower()
            statement.script_var = scope + "." + name.lower()
            statement.target = statement.target or scope + "." + name.lower()
            continue

        # A LOOP ROW IS A SCRIPT VARIABLE TOO, and the file is the only place
        # that says so: the rewrite is what took the word FOR away, so the file
        # is where the original wording still is - and the name really is
        # written on the line the reader is sent to.
        if statement.target:
            index = statement.line_offset
            short = short_name(statement.target)
            if 0 <= index < len(lines) and short:
                pattern = _FOR_ROW_RE.format(name=re.escape(short))
                if re.search(pattern, lines[index], re.IGNORECASE):
                    variables[short] = statement.target
                    statement.script_var = statement.target
    return variables


def _bind_script_variables(statements: list[Statement], variables: dict[str, str]) -> None:
    """Add each variable to the sources of every statement in the file that
    names it. Count BOTH spellings: the bare name for a scalar, and the
    qualifier for a loop row (rec.seg)."""
    if not variables:
        return
    for statement in statements:
        added = False
        for name, fenced in variables.items():
            if statement.script_var == fenced:
                # A statement that FILLS a variable must never be given that
                # variable as one of its own sources, or the chain reads itself
                # and walks in a circle.
                continue
            pattern = r"(?<![A-Za-z0-9_.])" + re.escape(name) + r"(?![A-Za-z0-9_])"
            if re.search(pattern, statement.sql, re.IGNORECASE) and fenced not in statement.sources:
                statement.sources.add(fenced)
                added = True
        if added:
            forget_source_cache(statement)

    for statement in statements:
        if not statement.script_var or statement.sources:
            continue
        # Where a variable's own statement comes out of the source walk with
        # nothing, take every table named anywhere in it: a DECLARE holds its
        # query in a place the ordinary walk does not reach.
        found = {
            _table_name(table)
            for table in (statement.expr.find_all(exp.Table) if _is_expression(statement.expr) else [])
        }
        found = {name for name in found if name and not is_metadata(name)}
        if found:
            statement.sources |= found
            forget_source_cache(statement)


def _procedure_definitions(text: str) -> set[str]:
    return {
        short_name(match.group(1))
        for match in _PROCEDURE_RE.finditer(text)
        if match.group(1)
    }


def _calls_in(text: str) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    for index, line in enumerate(text.splitlines()):
        match = _CALL_RE.match(line)
        if match:
            out.append((index + 1, short_name(match.group(1))))
    return out


def _unfence_along_calls(
    repo: ParsedRepo,
    temp_by_file: dict[str, set[str]],
    defines: dict[str, set[str]],
    calls: dict[str, set[str]],
) -> None:
    """A TEMP TABLE CROSSES A CALL, because the procedure runs in the same
    session.

    The fence is not weakened and same_table is not changed. The CALL EDGE is
    recorded instead, read off the file TEXT because neither end survives
    parsing, and a temp name is unfenced only along an edge that can be pointed
    at - WIDENING sources rather than replacing them, in BOTH directions and the
    whole way down a chain of calls.
    """
    edges: dict[str, set[str]] = {}
    for caller, names in calls.items():
        for name in names:
            for callee, defined in defines.items():
                if name in defined and callee != caller:
                    edges.setdefault(caller, set()).add(callee)
                    edges.setdefault(callee, set()).add(caller)

    def connected(start: str) -> set[str]:
        seen = {start}
        frontier = [start]
        while frontier:
            current = frontier.pop()
            for neighbour in edges.get(current, set()):
                if neighbour not in seen:
                    seen.add(neighbour)
                    frontier.append(neighbour)
        seen.discard(start)
        return seen

    reachable = {path: connected(path) for path in edges}
    if not reachable:
        return

    for statement in repo.statements:
        others = reachable.get(statement.file)
        if not others:
            continue
        widened = set(statement.sources)
        for source in statement.sources:
            dataset, short = _split_name(source)
            if not is_scoped(dataset):
                continue
            for other in others:
                if short in temp_by_file.get(other, set()):
                    widened.add(scope_for(other) + "." + short)
        if widened != statement.sources:
            statement.sources = widened
            forget_source_cache(statement)


def two_definitions(repo: ParsedRepo) -> list[TableFork]:
    """One table, two files that build it.

    A CREATE OR REPLACE replaces the whole table, so only one of them can be the
    definition that runs. Two of them in two files is a fork - usually a live
    copy and a stale one under archive/ or dev/ that nothing schedules. An
    INSERT or a MERGE adds to a table and several files loading one that way is
    ordinary; only a CREATE forks it.
    """
    by_table: dict[str, list[str]] = {}
    for statement in repo.statements:
        if not isinstance(statement.expr, exp.Create) or not statement.target:
            continue
        if is_scoped(statement.target):
            continue
        name = short_name(statement.target)
        if not name:
            continue
        files = by_table.setdefault(name, [])
        if statement.file not in files:
            files.append(statement.file)
    return [
        TableFork(table=name, files=files)
        for name, files in sorted(by_table.items())
        if len(files) > 1
    ]


def _external_sql(f: Any, known: set[str]) -> list[ExternalSql]:
    """A program that runs a .sql file which is not in this repository: Ripple
    has never read that query, so nothing it does is covered by any scan."""
    out: list[ExternalSql] = []
    path = str(getattr(f, "path", "") or "")
    lang = str(getattr(f, "lang", "") or "").lower()
    text = str(getattr(f, "text", "") or "")
    if lang in {"sql", "sqlx"} or path.lower().endswith((".sql", ".sqlx")):
        return out
    seen: set[str] = set()
    for index, line in enumerate(text.splitlines()):
        for match in _SQL_FILE_RE.finditer(line):
            named = match.group(1).replace("\\", "/")
            if named in seen:
                continue
            seen.add(named)
            tail = named.split("/")[-1].lower()
            if any(known_path.lower().endswith(tail) for known_path in known):
                continue
            out.append(ExternalSql(file=path, line=index + 1, path=named))
    return out


def parse_repo(
    index: Any,
    cfg: Any,
    on_progress: Optional[Callable[[int, int, str], None]] = None,
) -> ParsedRepo:
    """Read a whole repository.

    Reading one takes minutes, so one unexpected shape must never end it: the
    reading of EACH FILE is wrapped in its own guard, and a file that throws
    costs one line on the unreadable list rather than every file after it.
    """
    repo = ParsedRepo()
    files = list(getattr(index, "files", index) or [])
    total = len(files)
    known = {str(getattr(f, "path", "") or "") for f in files}
    temp_by_file: dict[str, set[str]] = {}
    defines: dict[str, set[str]] = {}
    calls: dict[str, set[str]] = {}

    for done, f in enumerate(files, 1):
        path = str(getattr(f, "path", "") or "")
        if on_progress is not None:
            on_progress(done, total, path)
        try:
            statements, problems, opaque = parse_file(f, cfg)
        except Exception as error:
            repo.unreadable.append(
                Unreadable(
                    file=path,
                    message=(
                        "Ripple could not read this file at all ("
                        + type(error).__name__
                        + ") - check it by hand"
                    ),
                )
            )
            continue

        text = str(getattr(f, "text", "") or "")
        for problem in problems:
            # Report a statement read by regular expression ONCE: on the "named
            # here, but nothing is carried" card, and NOT also as a file nobody
            # could understand.
            if problem.hint != "referenced":
                repo.unreadable.append(problem)
        repo.references.extend(_references_in(path, text))

        temp_by_file[path] = _fence_temp_tables(statements, path, text)
        variables = _query_variables(statements, path, text)
        _bind_script_variables(statements, variables)

        defines[path] = _procedure_definitions(text)
        called = _calls_in(text)
        if called:
            calls[path] = {name for _line, name in called}
            for line, name in called:
                repo.procedure_calls.append(ProcedureCall(file=path, line=line, name=name))

        repo.statements.extend(statements)
        for key, entries in opaque.items():
            repo.opaque.setdefault(key, []).extend(entries)
        if statements:
            repo.parsed_files.add(path)
        repo.runs_sql_from.extend(_external_sql(f, known))

    _unfence_along_calls(repo, temp_by_file, defines, calls)
    return repo
