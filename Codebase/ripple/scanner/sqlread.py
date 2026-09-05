"""Reading SQL properly, rather than just matching words.

The whole value of Ripple is in this file. A word search can tell you that
MARKET_CODE appears in a file. Only parsing can tell you that it appears
*inside a WHERE clause comparing it to the literal 'US'* -- which is the
difference between "mentioned here" and "this breaks on the 18th".
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import sqlglot
from sqlglot import exp

from ..config import Settings, settings as default_settings
from .repo import (
    RepoIndex,
    SourceFile,
    looks_like_unread_sql,
    sql_file_refs,
    statements_for,
    written_tables,
)
from . import rescue
from .dialectcompat import (
    RENAME_NODE, SET_OPERATION, from_of, is_temporary, is_unpivot, merge_whens,
    output_names as query_output_names, pivot_columns, pivot_fields,
    set_branches, star_except, star_replace,
)
from .templating import (
    describe as describe_templating,
    fill_placeholders,
    has_blocks,
    has_placeholders,
    placeholder_names,
    renderings,
    unwrap_blocks,
)

# sqlglot narrates its fallbacks to the log; that noise is not useful here
# because we surface every genuinely unreadable file ourselves.
import logging

logging.getLogger("sqlglot").setLevel(logging.ERROR)
log = logging.getLogger(__name__)

# How a usage is shown to the user, in the order we prefer to report it.
LOGIC_LABEL = {
    "filter": "Filter",
    "join_key": "Join key",
    "ranking": "Ranking",
    "dedup_key": "Dedup key",
    "aggregation": "Aggregation",
    "transform": "Transform",
    "excluded": "Named in EXCEPT",
    "pivoted": "Named in PIVOT",
    "layout": "Partition or cluster key",
    "sort": "Sort order",
    "renamed": "Renamed by ALTER TABLE",
    "dropped": "Dropped by ALTER TABLE",
    "retyped": "Changed by ALTER TABLE",
    "select": "Select",
    "star": "Carried by SELECT *",
}
# Most consequential first: if a column is used several ways in one statement,
# this decides which one heads the finding.
KIND_PRIORITY = ["ranking", "dedup_key", "layout", "filter", "join_key", "transform",
                 "aggregation", "sort", "pivoted", "excluded", "renamed", "dropped",
                 "retyped", "select", "star"]

# Words that make a line likely to be the one a given usage lives on.
KIND_MARKERS = {
    "filter": ("WHERE", "AND ", "OR ", "HAVING"),
    "join_key": ("JOIN", " ON "),
    "ranking": ("ORDER BY", "OVER", "ROW_NUMBER", "RANK"),
    "aggregation": ("GROUP BY",),
    "dedup_key": ("MAX(", "MIN(", "GROUP BY"),
    "transform": ("SUBSTR", "CAST", "TRIM", "UPPER", "LOWER", "COALESCE", "CONCAT", "("),
    "excluded": ("EXCEPT", "SELECT"),
    "pivoted": ("UNPIVOT", "PIVOT", " FOR ", " IN ("),
    "layout": ("PARTITION BY", "CLUSTER BY"),
    "sort": ("ORDER BY",),
    "renamed": ("RENAME COLUMN", "RENAME", "ALTER"),
    "dropped": ("DROP COLUMN", "DROP", "ALTER"),
    "retyped": ("ALTER COLUMN", "SET DATA TYPE", "ALTER"),
    "select": ("SELECT", " AS "),
    "star": ("SELECT *", "SELECT"),
}


# ── one table's name, and whether two names are the same table ─────────────
# ``prj.raw_dataset.customer_demographics`` and
# ``prj.archive_dataset.customer_demographics`` are two different tables. Ripple
# used to keep only the last part of a name, so a change to one produced
# findings for the code that reads the other -- and in the warehouse this was
# built for the same table name really does appear in a source dataset and a
# stage dataset.
#
# The project is deliberately left out. It is templated in nearly every file
# ({{tgt_project_id}}, {{src_project_id}}), so including it would split one real
# table into two on the strength of which placeholder somebody happened to type.
# The dataset is the part that says which table this is.
# customer_demographics$20260101 -- a partition decorator. It names ONE DAY of
# one table, not another table, and BigQuery uses it wherever a single
# partition is written or read. Kept as part of the name, it split every
# decorated read off from the table it belongs to and the scan came back clean.
_DECORATOR = re.compile(r"\$[0-9]+$")


def short_name(table: str) -> str:
    """The table's own name, without the dataset in front of it."""
    return _DECORATOR.sub("", (table or "").rsplit(".", 1)[-1])


def dataset_of(table: str) -> str:
    """The dataset a name was qualified with, or '' if the SQL did not say."""
    parts = (table or "").rsplit(".", 1)
    return parts[0] if len(parts) == 2 else ""


def canonical(table: str) -> str:
    """A name cut down to the part that identifies the table: ``dataset.name``.

    Names arrive with a project in front of them -- typed into the notification,
    pasted off a screen, or written that way in the SQL. The project is dropped
    for the reason given above: it is a placeholder in nearly every file here, so
    comparing it would split one real table into two.
    """
    parts = [p for p in (table or "").split(".") if p]
    if parts:
        parts[-1] = _DECORATOR.sub("", parts[-1])
    return ".".join(parts[-2:]) if parts else (table or "")


# ── wildcard tables ────────────────────────────────────────────────────────
# Date-sharded tables are ordinary in BigQuery, and the way every one of them is
# read is a wildcard::
#
#     SELECT cm13 FROM `prj.ds.customer_demographics_*`
#     WHERE _TABLE_SUFFIX BETWEEN '20260101' AND '20260131'
#
# The name in the file is ``customer_demographics_*``, asterisk and all. Nobody
# has a table called that. The tables are ``customer_demographics_20260101`` and
# three hundred siblings, and that is what a person types into a scan -- so the
# name matched nothing, the chain was never followed, and the answer came back
# as a clean "no impact" on a change that breaks a published table.
#
# What a wildcard matches is not a guess: BigQuery only allows the star at the
# end, and it stands for every table in that dataset whose name starts with the
# part in front of it. So a wildcard covers a name when the name starts with
# that prefix.
#
# One deliberate addition to that rule. A person asked what breaks does not type
# the shard, they type the family the way they think of it -- "customer_
# demographics", with no trailing separator, which BigQuery itself would not
# match. Refusing that would print the exact clean "no impact" this exists to
# prevent, so the prefix with its trailing separator taken off matches too. It
# costs a row somebody can dismiss by opening the file. Silence costs an outage.
_STAR = "*"


def is_wildcard(table: str) -> bool:
    """Is this a BigQuery wildcard table name -- ``events_*``?"""
    return short_name(table).endswith(_STAR)


def wildcard_match(pattern: str, name: str) -> str:
    """How ``pattern`` covers ``name``: "shard", "family", "both", or "".

    Two different answers wearing one word, and shipping them as one is how a
    guess got printed as a fact.

    * "shard" -- ``customer_demographics_*`` and ``customer_demographics_20260101``.
      BigQuery itself matches this. It is a fact about the SQL.
    * "family" -- ``customer_demographics_*`` and plain ``customer_demographics``.
      BigQuery does NOT match this; the separator is required. Ripple matches it
      anyway, because somebody typing the family name they say out loud must not
      get a clean "no impact" -- but it is a guess about what they meant, and a
      guess shipped as ``certain`` is the failure this whole reader exists to
      avoid.
    * "both" -- two wildcards whose families overlap.

    Both names are compared on their short names, because the dataset is ruled
    on separately by ``same_table`` for the reason given further up this file.
    """
    prefix = short_name(pattern).upper()
    if not prefix.endswith(_STAR):
        return ""
    prefix = prefix[:-1]
    # A bare "*" -- the whole of a dataset. It genuinely does read every table
    # there, but matching on it here would put every table in the repository on
    # every chain, which is not a spare row somebody can dismiss, it is the
    # whole warehouse. It is ruled on in same_table instead, where the dataset
    # is known and can scope it.
    if not prefix:
        return ""
    other = short_name(name).upper()
    if other.endswith(_STAR):
        # Two wildcards. They are the same family if either prefix contains the
        # other -- ``customer_*`` and ``customer_demographics_*`` overlap, and
        # following both is the safe direction.
        other = other[:-1]
        return "both" if other.startswith(prefix) or prefix.startswith(other) else ""
    if other.startswith(prefix):
        return "shard"                   # customer_demographics_20260101
    # The family named the way a person says it, without the separator the
    # wildcard was written with. Deliberately tight: it matches the whole prefix
    # bar its trailing separator and nothing shorter, so ``ev`` never matches
    # ``events_*``.
    return "family" if prefix.rstrip("_-") == other else ""


def wildcard_covers(pattern: str, name: str) -> bool:
    """Does the wildcard name ``pattern`` cover the table name ``name``?"""
    return bool(wildcard_match(pattern, name))


# ── the warehouse describing itself ────────────────────────────────────────
# INFORMATION_SCHEMA is not data, it is BigQuery's catalogue of its own tables.
# Its views are called COLUMNS, TABLES, JOBS, VIEWS, PARTITIONS -- ordinary
# words, and a warehouse of any size has real tables called some of them.
#
#     CREATE TABLE `p.base.columns` (table_name STRING, column_name STRING);
#     CREATE TABLE `p.pub.report_prod` AS
#     SELECT column_name FROM `p.base`.INFORMATION_SCHEMA.COLUMNS;
#
# Measured before this: `report_prod` was reported as fed by the real table
# `base.columns`, breaking, with a warning that blamed CAPITALISATION -- so the
# one thing on screen pointing at the problem named the wrong cause, and
# following it would not have found anything.
#
# A metadata view carries no column of anybody's table. Nothing that changes in
# `customer_demographics` changes a column of INFORMATION_SCHEMA.COLUMNS -- a
# ROW of it changes, and a row is not lineage. So these are not catalogued, not
# merged with anything, and no edge is drawn from them.
#
# ``region-us`` and its siblings are the same thing at project level: the
# region-wide job history, addressed as if it were a project.
_METADATA_PART = "INFORMATION_SCHEMA"
_REGION_PROJECT = re.compile(r"^region-", re.IGNORECASE)


def is_metadata_read(table: str) -> bool:
    """Is this BigQuery describing itself, rather than a table of anybody's?"""
    parts = [p for p in (table or "").split(".") if p]
    if any(p.upper() == _METADATA_PART for p in parts):
        return True
    return bool(parts) and bool(_REGION_PROJECT.match(parts[0]))


# ── temporary tables ───────────────────────────────────────────────────────
# A TEMP table lives inside one script and is gone when it finishes. Two files
# that both build a ``t`` are not sharing a table; they cannot be, because a
# static scan has no way to know two files ever ran in one session, and BigQuery
# throws the table away at the end of each. Temp names in real repositories are
# ``t``, ``tmp``, ``stg``, ``base``, ``deduped`` -- collisions are the norm, not
# the exception.
#
# Measured before this: two unrelated files, each building its own ``t``, put
# BOTH of their published tables on the chain, marked the second one breaking,
# and printed no warning of any kind. A confident finding about a table nothing
# had touched.
#
# The dataset fix that keeps ``stage.orders`` apart from ``archive.orders``
# cannot help here, because a temp table has no dataset to compare. So one is
# invented: a scope standing for "inside this file", made of the file's own path
# and marked with a character no warehouse allows in a name. It never reaches a
# screen -- ``display`` strips it -- and ``same_table`` treats it as absolute
# rather than as the usual loose match, because "no dataset given" must not go
# on matching a table that exists nowhere outside one file.
_SESSION_DATASET = "_SESSION"
_SCOPE_MARK = "#"
_NOT_A_NAME = re.compile(r"[^A-Za-z0-9]+")


def session_scope(path: str) -> str:
    """A dataset name no warehouse can have, standing for 'inside this file'."""
    return _SCOPE_MARK + _NOT_A_NAME.sub("_", path).strip("_").upper()


def is_session_scoped(table: str) -> bool:
    """Is this name confined to one file -- a TEMP or _SESSION table?"""
    return dataset_of(table).startswith(_SCOPE_MARK)


def same_table(a: str, b: str) -> bool:
    """Are these two names the same table?

    The short name always has to match, or one of the two has to be a wildcard
    covering the other. The dataset can only rule a match OUT, and only when
    BOTH sides carry one -- these files are templated, so a great many names in
    the repository are written with a placeholder where a dataset goes, and
    treating "no dataset given" as "a different table" would cut every one of
    those chains. Two placeholders that fill to the same value produce the same
    word here, so they go on matching.
    """
    if short_name(a).upper() != short_name(b).upper():
        if is_wildcard(a) or is_wildcard(b):
            wide, other = (a, b) if is_wildcard(a) else (b, a)
            if not wildcard_covers(wide, other):
                # A dataset-wide "ds.*" has nothing in front of the star, so it
                # covers every table -- but only inside its own dataset, and
                # only when the other name says which dataset it is in. Without
                # both of those it would match the whole repository.
                if not (short_name(wide) == _STAR and dataset_of(wide)
                        and dataset_of(other)
                        and dataset_of(wide).upper() == dataset_of(other).upper()):
                    return False
        else:
            return False
    left, right = dataset_of(a).upper(), dataset_of(b).upper()
    # A temporary table only exists inside one file, so "the SQL did not say
    # which dataset" cannot mean "it might be that one". Nothing outside that
    # file can be it. This is the one place the loose match is switched off.
    if left.startswith(_SCOPE_MARK) or right.startswith(_SCOPE_MARK):
        return left == right
    return not (left and right and left != right)


# ── table-valued functions ─────────────────────────────────────────────────
# A BigQuery TABLE FUNCTION is a table as far as lineage is concerned. It is
# named, it is read in a FROM clause, and every column of its body travels
# through it::
#
#     CREATE OR REPLACE TABLE FUNCTION ds.recent_customers(d STRING) AS (
#       SELECT cm13, market_code FROM customer_demographics WHERE dt = d)
#
#     CREATE OR REPLACE TABLE published.summary AS
#     SELECT cm13 FROM ds.recent_customers('2026-01-01')
#
# Both halves were invisible. The definition parses as a function rather than a
# table, so it published nothing; and the call parses as a function call in the
# FROM clause, whose table node carries no name at all, so it read nothing. The
# chain broke in the middle and the published table was never mentioned.
#
# Some things written in a FROM clause that look the same really are not tables.
# BigQuery's own built-in table functions wrap a table rather than being one,
# and the table they wrap is parsed as its own node and found anyway -- so
# taking the wrapper's name as well would only invent a table nobody has.
_NOT_A_TABLE = {
    "EXTERNAL_QUERY", "APPENDS", "CHANGES", "GAP_FILL", "RANGE_SESSIONIZE",
    "TABLE_DATE_RANGE", "TABLE_QUERY", "OBJECT_METADATA", "VECTOR_SEARCH",
    "GENERATE_ARRAY", "GENERATE_DATE_ARRAY", "GENERATE_TIMESTAMP_ARRAY",
    "SEARCH_INDEX_STATUS", "SESSIONIZE",
}


def _called_function_name(t: exp.Table) -> str:
    """The table function this FROM clause is calling, or '' if it is not one."""
    inner = t.this
    if not isinstance(inner, exp.Anonymous):
        return ""
    name = inner.name or ""
    if not name or name.upper() in _NOT_A_TABLE:
        return ""
    return name


def _tables_handed_to_a_call(t: exp.Table) -> list[str]:
    """Tables passed INTO a function that sits in a FROM clause.

    BigQuery hands a table to a function with the word TABLE in front of it::

        SELECT cm13 FROM APPENDS(TABLE `prj.ds.customer_demographics`, NULL)
        SELECT ...  FROM `prj.ds.recent`(TABLE `prj.ds.orders`, 'apple')

    The parser refuses that outright, so the pre-pass takes the word out (see
    scanner/rescue.py) -- and what is left arrives as an ordinary column
    reference among the function's arguments, not as a table node. Without this
    the real table is nowhere in the statement, and an incremental load, which
    is exactly how a published table is kept up to date, reads nothing at all.

    Only column-shaped arguments count. A literal, a number or a nested call is
    not a table, and inventing one from a string would put a table nobody has
    on the result.
    """
    inner = t.this
    if not isinstance(inner, exp.Anonymous):
        return []
    out: list[str] = []
    for arg in inner.expressions:
        if not isinstance(arg, exp.Column):
            continue
        name = canonical(_bare(arg.sql()))
        if name and name not in out:
            out.append(name)
    return out


def _qualify(t: exp.Table) -> str:
    """One table node as ``dataset.name``, or just ``name`` when unqualified."""
    name = _DECORATOR.sub("", t.name or "")
    if not name:
        # A table function call. Backticked in full, the whole path arrives as
        # one string -- `prj.ds.recent_customers` -- so it is cut down the same
        # way any other name written in full is.
        called = _called_function_name(t)
        if not called:
            return ""
        if "." in called:
            return canonical(called)
        name = called
    db = t.text("db")
    return f"{db}.{name}" if db else name


def _bare(sql: str) -> str:
    """A name as written, with whatever quoting the dialect put round it taken off."""
    return sql.replace("`", "").replace('"', "").strip()


def reads_metadata(stmt: exp.Expression | None) -> bool:
    """Does this statement read the warehouse's own catalogue?

    Asked of the tree rather than of a Statement's sources, because a metadata
    view is deliberately never recorded as a source -- it carries no column of
    anybody's table. So the statement itself is the only place the fact
    survives, and one screen needs it to name what actually happened rather
    than blaming an in-house helper for a plain INFORMATION_SCHEMA lookup.
    """
    if stmt is None:
        return False
    return any(is_metadata_read(_qualify(t)) for t in stmt.find_all(exp.Table))


def _table_function_target(stmt: exp.Expression) -> str:
    """The name a ``CREATE TABLE FUNCTION`` publishes, or ''.

    A scalar UDF parses identically -- same node, same kind -- and must NOT be
    treated as a table, or every helper function in the repository becomes one.
    The difference is what it returns: a table function's body is a SELECT, and
    a scalar function's is an expression.
    """
    if not isinstance(stmt, exp.Create):
        return ""
    if str(stmt.args.get("kind") or "").upper() != "FUNCTION":
        return ""
    body = stmt.args.get("expression")
    if body is None or body.find(exp.Select) is None:
        return ""
    named = getattr(stmt.this, "this", None)
    if named is None:
        return ""
    return canonical(_bare(named.sql()))


def _forget_templated_datasets(stmt: exp.Expression, holes: set[str]) -> None:
    """Take off any dataset that is really a placeholder.

    Ripple fills placeholders in with an ordinary word so the statement parses,
    which leaves ``{{stage_dataset}}`` looking exactly like a dataset called
    stage_dataset. It is not one -- it is a hole, and the file next door writes
    the very same dataset as a different hole.

    Treating those two words as two datasets would split one real table in two,
    cut the chain between them, and report no impact. So a dataset that came out
    of a placeholder is recorded as what it honestly is: not stated. A name with
    no dataset goes on matching any dataset, which is the safe direction --
    Ripple would rather show a finding somebody can dismiss by opening the file
    than hide one nobody will ever know was missed.
    """
    for t in stmt.find_all(exp.Table):
        db = t.text("db")
        if db and db.upper() in holes:
            t.set("db", None)


# ── a hole where the column list goes ──────────────────────────────────────
# A great many Airflow DAGs build their SQL like this::
#
#     cols = "cm13, cm14"
#     sql = f"CREATE OR REPLACE TABLE ds.final_published AS " \
#           f"SELECT {cols} FROM ds.customer_demographics"
#
# The placeholder is filled in by Python before BigQuery ever sees it, so the
# column list genuinely is "cm13, cm14" -- but it is not in the file, and Ripple
# reads `SELECT cols FROM ...`. Measured before this: Ripple believed the
# published table had exactly one column, called `cols`, and answered
# `reachesProduction False, risk none, unreadable 0, couldNotRead 0` -- a clean,
# confident, complete zero. Identical with ``.format()``.
#
# A hole in the projection list is a SELECT * that has not been filled in yet:
# it carries columns Ripple cannot see and names none of them. That is exactly
# what the star machinery already models -- the trail carries on, the table is
# listed as one whose column list is not visible, and every finding past it is
# marked worked out rather than read. So it is turned into one, and the screen
# is told what the file actually writes.
def _holes_in_the_select_list(stmt: exp.Expression, holes: set[str]) -> str:
    """Turn a placeholder standing where columns go into the star it is.

    Returns the placeholder's name, or "" if there was none.
    """
    if not holes:
        return ""
    found = ""
    for sel in list(stmt.find_all(exp.Select)):
        for e in list(sel.expressions):
            inner = e.this if isinstance(e, exp.Alias) else e
            if not isinstance(inner, exp.Column) or inner.table:
                continue
            if inner.name.upper() not in holes:
                continue
            found = inner.name
            e.replace(exp.Star())
    return found


@dataclass
class Usage:
    kind: str
    column: str            # the source column this usage refers to
    alias: str | None      # the name it is published as, when projected
    detail: str = ""       # e.g. the literal it is compared against
    # Whether the statement actually said which table this column came from.
    # In a warehouse where the same three key columns are in nearly every table,
    # most joins have the name on both sides, and "cm13" on its own does not say
    # whose. False means the usage is real and the table is a guess.
    certain: bool = True
    # Whether this column only leaves the statement because of a SELECT *. The
    # column really is carried through -- that is what a star does -- but the
    # column list is not written down anywhere, so nothing here can be pointed
    # at. Every finding on the far side of one of these is inferred, and says so.
    via_star: bool = False

    @property
    def label(self) -> str:
        return LOGIC_LABEL.get(self.kind, self.kind.title())


@dataclass
class Statement:
    file: str
    lang: str
    line_offset: int
    # The last line of the file this statement occupies. A finding is only ever
    # pointed at a line inside its own statement -- see _with_lines.
    line_end: int
    sql: str
    target: str | None
    sources: set[str]
    select: exp.Select | None
    expr: exp.Expression | None
    # "" for an ordinary statement; otherwise the word the file used to copy a
    # whole table -- COPY, CLONE, LIKE or RENAME. The hop is followed as a
    # SELECT *, because that is what it does, but the screen has to say what is
    # actually written or it is describing a statement that is not there.
    whole_copy: str = ""
    # "" when a SELECT * in this statement really is written as SELECT *.
    # Otherwise what the file writes instead -- a placeholder the job fills in
    # when it runs. It carries whatever columns it is handed and names none of
    # them, which is what a star does, so it is followed the same way; but no
    # screen may tell somebody the file says SELECT * when it does not.
    star_note: str = ""
    # Column names in this statement that Ripple put back by hand because the
    # parser read them as something else -- see _rescue_parenless_functions.
    # Every usage of one is real and every one of them is a guess about which
    # of two things the writer meant, so they are never asserted.
    guessed_columns: set = field(default_factory=set)
    # "" when the target table is written in the statement. Otherwise how the
    # name was worked out instead -- "dbt" or "file". The table name is nowhere
    # in this file, so anybody sent to the line to check would find no such
    # table written there, and a finding that does not say so reads as a fact
    # off the page. See _named_after_its_file.
    named_by: str = ""
    # "" for a statement written as SQL. Otherwise the words the file used to
    # run it as text -- today only EXECUTE IMMEDIATE. The statement is read
    # exactly as it will run, so the hop is real; but the line in the file is a
    # quoted string, and anybody sent to it to check would find a string rather
    # than the CREATE the row describes. See _reparse_run_as_text.
    built_as_text: str = ""
    # "" for an ordinary statement. Otherwise where this EXPORT DATA delivers
    # to -- gs://feed/partner. An export builds no table, so there is nothing
    # for the trail to carry the column on to, and every screen said "no
    # production table is affected", which is true and useless: the delivery
    # that breaks belongs to another team and was named nowhere at all.
    export_uri: str = ""
    # "" for an ordinary statement. Otherwise the script variable this one
    # fills: a DECLARE or a SET whose value is a query, or the row variable of
    # a FOR loop. The variable is not a table, but it behaves exactly like a
    # temporary one -- built here, read further down, and gone at the end of the
    # file -- so it is fenced and followed as one. See _bind_script_variables.
    script_var: str = ""
    # Worked out once and kept. One scan asks the same statement about the same
    # column many times over, and on a 600-line statement each answer means
    # walking the whole expression tree again. Measured on a repository the size
    # of his, this was most of the time a scan took.
    _names: dict = field(default_factory=dict, repr=False, compare=False)
    _projected: list | None = field(default=None, repr=False, compare=False)
    _sources_upper: set | None = field(default=None, repr=False, compare=False)
    _scopes: dict | None = field(default=None, repr=False, compare=False)

    def reads_from(self, table: str) -> bool:
        if self._sources_upper is None:
            self._sources_upper = {s.upper() for s in self.sources}
        return table.upper() in self._sources_upper


@dataclass
class ParsedRepo:
    statements: list[Statement] = field(default_factory=list)
    unreadable: list[dict] = field(default_factory=list)
    parsed_files: set[str] = field(default_factory=set)
    # Statements the reader could take in but not understand the shape of: a
    # procedure call, a loop, an EXECUTE IMMEDIATE, a scripting block. They are
    # kept per file rather than reported, because whether they matter depends
    # entirely on what is being scanned for. A loop over a table list is
    # nothing at all -- until the attribute you are chasing is named inside it.
    opaque: dict[str, list[dict]] = field(default_factory=dict)
    # Programs that run SQL kept in a separate .sql file rather than holding it
    # as text. Two folders of his pipeline are written this way. Where the .sql
    # file is in the repository this is nothing to worry about -- it was read on
    # its own account -- but the program is not empty either, and saying so is
    # the difference between "this DAG does nothing" and "this DAG runs that".
    runs_sql_from: list[dict] = field(default_factory=list)
    # DDL that names a table and its columns and carries no column anywhere: a
    # search index, a vector index, a row access policy, an UNDROP. Never an
    # edge and never a hop -- a dependency somebody has to go and change,
    # reported as one. See referenced_here.
    references: list[dict] = field(default_factory=list)
    # Which file CALLs a procedure defined in which other file. A CALL runs in
    # the SAME BigQuery session as the line above it, so the caller's temporary
    # tables really are visible inside the procedure -- and the per-file fence
    # renamed only the caller's side of that pair, so the chain died on the temp
    # table and the file that actually breaks was reported as "the name appears,
    # but no lineage to a production table". See _follow_procedure_calls.
    procedure_calls: list[dict] = field(default_factory=list)
    # Built on demand by reading(); see the note there.
    _by_source: dict | None = field(default=None, repr=False, compare=False)
    _indexed: int = field(default=-1, repr=False, compare=False)
    _ambiguous: set = field(default_factory=set, repr=False, compare=False)
    _datasets: dict = field(default_factory=dict, repr=False, compare=False)
    _spellings: dict = field(default_factory=dict, repr=False, compare=False)
    # Wildcard source names, e.g. CUSTOMER_DEMOGRAPHICS_*, kept apart from the
    # main index because they can never be found by an exact lookup. Almost
    # always empty, and skipped entirely when it is.
    _wildcards: dict = field(default_factory=dict, repr=False, compare=False)
    # short table name -> the files that build it from scratch. See rebuilt_in.
    _rebuilds: dict = field(default_factory=dict, repr=False, compare=False)

    def reading(self, table: str) -> list[Statement]:
        # Indexed rather than searched. A scan asks this once per table it
        # visits, and on a repository of a few thousand statements walking the
        # whole list each time was a large part of what a scan cost.
        #
        # Indexed on the short name and then filtered on the dataset, so a name
        # the SQL qualified is not merged with a same-named table in another
        # dataset -- and a name it did not qualify still matches everything, as
        # it must, because nothing has been said to tell them apart.
        self._index()
        candidates = self._by_source.get(short_name(table).upper(), [])
        if self._wildcards or is_wildcard(table):
            candidates = self._plus_wildcards(table, candidates)
        if not dataset_of(table):
            # A name with no dataset goes on matching anything -- except a
            # table that exists only inside one file. Nothing outside that file
            # can be reading it, so an unqualified name reaching one puts an
            # unrelated file's whole chain on the answer. See session_scope.
            kept: list[Statement] = []
            for s in candidates:
                matched = [src for src in s.sources if same_table(src, table)]
                if matched and all(is_session_scoped(src) for src in matched):
                    continue
                kept.append(s)
            return kept
        return [s for s in candidates if any(same_table(src, table) for src in s.sources)]

    def _plus_wildcards(self, table: str, candidates: list[Statement]) -> list[Statement]:
        """The same statements, plus any reached only through a wildcard name.

        An exact lookup can never find these: the key in the index is
        ``CUSTOMER_DEMOGRAPHICS_*`` and the table being followed is
        ``customer_demographics_20260101``. Missing them is what produced a
        clean "no impact" on every date-sharded table in the warehouse.
        """
        short = short_name(table).upper()
        extra: list[Statement] = []
        for pattern, stmts in self._wildcards.items():
            if pattern != short and wildcard_covers(pattern, short):
                extra.extend(stmts)
        if is_wildcard(table):
            # The other way round: somebody asked about the family itself, so
            # every shard read by name in the repository is part of the answer.
            for key, stmts in self._by_source.items():
                if key != short and wildcard_covers(short, key):
                    extra.extend(stmts)
        if not extra:
            return candidates
        out = list(candidates)
        seen = {id(s) for s in out}
        for s in extra:
            if id(s) not in seen:
                seen.add(id(s))
                out.append(s)
        return out

    def wildcards_covering(self, table: str) -> list[str]:
        """Wildcard names in this repository that take in ``table``.

        Used to say so on the result. A finding that only exists because a
        wildcard was followed reads as a plain fact about one table otherwise,
        and the person acting on it has no way to know a whole family of shards
        is what the SQL actually named.
        """
        return [p for p, _ in self.wildcards_covering_how(table)]

    def wildcards_covering_how(self, table: str) -> list[tuple[str, str]]:
        """The same, with HOW each one matched -- see wildcard_match.

        A real shard match is a fact about the SQL. The family name typed
        without its separator is a guess about what somebody meant, and the two
        must never leave here wearing the same word.
        """
        self._index()
        short = short_name(table).upper()
        # Given back as the SQL spells it, not as the index keys it. This goes
        # on screen and into the text search, and neither wants shouting.
        out = [(sorted(self._spellings.get(p, {p}))[0], wildcard_match(p, short))
               for p in self._wildcards if p != short]
        return sorted((p, how) for p, how in out if how)

    def _index(self) -> None:
        if self._by_source is not None and self._indexed == len(self.statements):
            return
        by_source: dict[str, list[Statement]] = {}
        wild: dict[str, list[Statement]] = {}
        rebuilds: dict[str, list[str]] = {}
        seen: dict[str, set[str]] = {}
        spelt: dict[str, set[str]] = {}
        bare: set[str] = set()
        for s in self.statements:
            # A CREATE that replaces the whole table. An INSERT or a MERGE adds
            # to one, and several files loading one table that way is ordinary;
            # two files REPLACING it is a fork. See rebuilt_in.
            if s.target and isinstance(s.expr, exp.Create) and not is_temporary(s.expr):
                seen_in = rebuilds.setdefault(short_name(s.target).upper(), [])
                if s.file not in seen_in:
                    seen_in.append(s.file)
            for src in s.sources:
                key = short_name(src).upper()
                by_source.setdefault(key, []).append(s)
                if key.endswith(_STAR):
                    wild.setdefault(key, []).append(s)
            for name in list(s.sources) + ([s.target] if s.target else []):
                short = short_name(name)
                ds = dataset_of(name)
                # A temp table's scope is not a dataset somebody wrote, it is a
                # fence Ripple put round one file. Counting it here would report
                # every ``t`` in the repository as a name standing for more than
                # one table -- a warning on something already told apart.
                if ds.startswith(_SCOPE_MARK):
                    continue
                if ds:
                    seen.setdefault(short.upper(), set()).add(ds.upper())
                else:
                    bare.add(short.upper())
                # How this name is actually spelt, capitals and all. BigQuery
                # treats ccm_Wireless_Enroll and ccm_wireless_enroll as two
                # different tables. Ripple matches them as one, because losing a
                # chain is the worse mistake -- and then says so, rather than
                # letting a finding read as a fact about one of them.
                spelt.setdefault(short.upper(), set()).add(short)
        self._by_source = by_source
        self._wildcards = wild
        self._rebuilds = rebuilds
        self._datasets = seen
        self._spellings = spelt
        # Names Ripple cannot be sure it is following one table under. Two ways:
        # the same name in two different datasets, or one dataset plus somewhere
        # else that names the table with no dataset at all -- the second is a
        # merge just as much as the first, and it is the one that produced a
        # finding about an archive table on a scan of the source table.
        #
        # In a fully templated repository almost no name has a dataset Ripple
        # can read, so almost nothing is flagged. That is the point: this fires
        # where there really is something to tell apart, and a warning printed
        # over every table is one nobody reads.
        self._ambiguous = {k for k, v in seen.items() if len(v) > 1 or k in bare}
        self._indexed = len(self.statements)

    def ambiguous_names(self) -> set[str]:
        """Short table names this repository uses in more than one dataset."""
        self._index()
        return self._ambiguous

    def datasets_for(self, table: str) -> list[str]:
        """Every dataset this repository writes or reads this table name in."""
        self._index()
        return sorted(self._datasets.get(short_name(table).upper(), set()))

    def spellings_for(self, table: str) -> list[str]:
        """Every way this table name is capitalised in the repository."""
        self._index()
        return sorted(self._spellings.get(short_name(table).upper(), set()))

    def display(self, table: str) -> str:
        """The name to put on screen: qualified only where it has to be."""
        if is_session_scoped(table):
            # The scope is Ripple's own fence round one file, not part of any
            # name anybody wrote. Putting it on screen would show a table name
            # that is in no file.
            return short_name(table)
        if short_name(table).upper() in self.ambiguous_names():
            return table
        return short_name(table)

    def rebuilt_in(self, table: str) -> list[str]:
        """Files that build this table from scratch, when more than one does.

        A CREATE OR REPLACE replaces the whole table, so only one of them can be
        the definition that runs. Two of them in two files is a fork -- usually a
        live copy and a stale one under archive/ or dev/ that nothing schedules.

        Measured before this: the ONLY finding reported came from the archive
        copy, presented with `breaking true, certain true` and the same wording
        as any live finding, while the live definition appeared under
        "mentions only". Where the real build is generated at deploy time and
        only the stale copy is committed, that is a confident, clean answer
        about a pipeline that no longer exists.

        Ripple cannot know which one runs -- nothing in the files says -- so it
        keeps following both and says so. Empty when only one file builds it,
        which is nearly always.
        """
        self._index()
        files = self._rebuilds.get(short_name(table).upper(), [])
        return files if len(files) > 1 else []

    def statements_in(self, path: str) -> list[Statement]:
        return [s for s in self.statements if s.file == path]


# ── parsing ────────────────────────────────────────────────────────────────
def _table_name(node: exp.Expression | None) -> str | None:
    if node is None:
        return None
    if isinstance(node, exp.Schema):
        node = node.this
    if isinstance(node, exp.Table):
        return _qualify(node)
    if isinstance(node, exp.Expression):
        t = node.find(exp.Table)
        if t is not None:
            return _qualify(t)
    return None


def _target_of(stmt: exp.Expression) -> str | None:
    # MERGE matters as much as CREATE and INSERT. On BigQuery, Snowflake and
    # Databricks it is the usual way a production table is loaded -- without it
    # the chain stops one step short of the table anyone actually reads, and
    # Ripple reports "no production impact" for a change that plainly has some.
    #
    # DELETE and UPDATE matter for a different reason. They build nothing, so
    # they look uninteresting -- but a DELETE whose WHERE clause filters on the
    # attribute that is being decommissioned stops working on the day it goes,
    # and the table it prunes quietly fills up instead. Naming the table they
    # act on is what lets that be reported at all.
    # A CREATE TABLE FUNCTION publishes a name that other statements read in a
    # FROM clause. Checked first because it is also an exp.Create, and its
    # ``this`` is a function signature that _table_name finds no table in.
    # ALTER TABLE was in none of these, so a repository holding its own rename
    # migration -- ALTER TABLE stage.customers RENAME COLUMN email TO
    # email_address -- came back target None, sources [], and reported no impact
    # for the column it renames. The rename is the plainest alias hop there is,
    # and it was the one hop Ripple could not see.
    tvf = _table_function_target(stmt)
    if tvf:
        return tvf
    if isinstance(stmt, (exp.Create, exp.Insert, exp.Merge, exp.Delete, exp.Update, exp.Alter)):
        name = _table_name(stmt.this)
        # Nothing writes into INFORMATION_SCHEMA. A name that looks like one is
        # the catalogue being read, not a table being built, and cataloguing it
        # merges it with every real table sharing its short name.
        return None if name and is_metadata_read(name) else name
    return None


def _target_node(stmt: exp.Expression) -> exp.Table | None:
    """The table node a statement WRITES, as a node rather than as a name.

    Sources are gathered by walking every table in the statement, which finds
    the write target too, so it has to be left out. That used to be done by
    comparing NAMES with same_table -- and same_table is deliberately loose,
    because a name with no dataset has to go on matching one that has a dataset
    or every templated chain in the repository breaks.

    Loose is right for FOLLOWING a chain and catastrophic for EXCLUDING a
    source. Two real shapes were silently losing every source they had:

        CREATE OR REPLACE TABLE ds.events_rollup AS SELECT ... FROM ds.events_*
        CREATE OR REPLACE TABLE {{target_dataset}}.orders AS SELECT ... FROM stage.orders

    In the first the wildcard covers the target's own name; in the second the
    templated dataset is dropped, leaving a bare "orders" that matches
    "stage.orders". Either way the one source in the statement was thrown away,
    the statement was indexed as reading nothing, and the scan came back clean.

    Comparing the node itself cannot make that mistake, and it costs nothing.
    """
    if not isinstance(stmt, (exp.Create, exp.Insert, exp.Merge, exp.Delete, exp.Update)):
        return None
    node = stmt.this
    if isinstance(node, exp.Schema):
        node = node.this
    return node if isinstance(node, exp.Table) else None


# ── a table built as a whole copy of another ───────────────────────────────
# Four shapes, every one of them ordinary in a BigQuery pipeline, and not one of
# them has a SELECT anywhere in it::
#
#     CREATE OR REPLACE TABLE published.customers COPY  stage.customers
#     CREATE TABLE            published.customers CLONE stage.customers
#     CREATE TABLE            published.customers LIKE  stage.customers
#     ALTER TABLE stage.customers RENAME TO published.customers
#
# The last step of a great many pipelines is exactly this. The table is built in
# a staging dataset, checked, and then promoted into the published one by
# copying or renaming it -- so the promotion is the single line that connects
# everything upstream to the table people actually read.
#
# Ripple recorded no source for any of these, so the trail died at the staging
# table and the screen said "last table in the chain -- not matched by your
# production naming rule". That is the worst thing this tool can print: a calm,
# confident answer over less than the whole picture, on a change that breaks a
# published table one line further down the same folder.
#
# A whole-table copy carries every column and writes none of them down, which is
# precisely what ``SELECT *`` means. So it is turned into the ``SELECT *`` it
# already is, on the parsed copy only, and everything that knows how to follow a
# star -- carrying the column on, marking the hop as worked out rather than
# read, and listing the table as one whose column list cannot be seen -- works
# on it unchanged. What is shown on screen still says COPY, because that is what
# the file says.
_COPY_WORD = {True: "COPY", False: "CLONE"}


def _copy_source(stmt: exp.Expression) -> tuple[exp.Table, str] | None:
    """The table a CREATE ... COPY/CLONE/LIKE reads, and which word was used."""
    if not isinstance(stmt, exp.Create):
        return None
    clone = stmt.args.get("clone")
    if clone is not None and isinstance(clone.this, exp.Table):
        return clone.this, _COPY_WORD[bool(clone.args.get("copy"))]
    props = stmt.args.get("properties")
    for p in (props.expressions if props is not None else []):
        if isinstance(p, exp.LikeProperty) and isinstance(p.this, exp.Table):
            return p.this, "LIKE"
    return None


# CREATE SNAPSHOT TABLE published.customers CLONE stage.customers
#
# A snapshot is a copy like any other, but those two extra words are enough for
# the parser to give up on the whole statement and hand back something with no
# tables in it at all. Retried without them -- and only once the parser has
# already failed, so it costs nothing on any statement that reads normally.
_SNAPSHOT = re.compile(r"^\s*CREATE\s+SNAPSHOT\s+TABLE\b", re.IGNORECASE)


def _reparse_snapshot(raw: str, dialect: str | None) -> exp.Expression | None:
    """A CREATE SNAPSHOT TABLE read as the plain table copy it is."""
    if not _SNAPSHOT.match(raw):
        return None
    try:
        again = sqlglot.parse_one(_SNAPSHOT.sub("CREATE TABLE", raw, count=1),
                                  read=dialect)
    except Exception:
        return None
    return again if isinstance(again, exp.Create) else None


# ── SQL written as text and run later ──────────────────────────────────────
# EXECUTE IMMEDIATE is how a BigQuery script builds a statement at run time. The
# parser gives up on it and hands back a Command, so the CREATE inside it is
# read, understood as nothing, and the scan comes back with the column reaching
# nothing. Measured before this: a whole CREATE OR REPLACE TABLE of the scanned
# column, sitting in the file in plain sight, gave prod [].
#
# Only the plain shape is followed: the whole thing after IMMEDIATE is ONE
# string literal and nothing else. That literal IS the statement, exactly as it
# will run, so reading it is not a guess about anything.
#
# Everything else stays unreadable and says so:
#
#     EXECUTE IMMEDIATE FORMAT('CREATE TABLE %s ...', x)   the name is a value
#     EXECUTE IMMEDIATE 'CREATE TABLE ' || env || '_mid'   built by adding up
#     EXECUTE IMMEDIATE 'INSERT ... VALUES (?)' USING v    holes in the text
#
# In each of those the statement never exists as text anywhere, so there is
# nothing to read -- and inventing the missing piece would be exactly the
# confident-answer-over-less-than-the-picture failure this tool exists to avoid.
_EXECUTE_IMMEDIATE = re.compile(r"^\s*EXECUTE\s+IMMEDIATE\s+", re.IGNORECASE)
# What may legally follow the literal. Anything else means the statement is
# being built rather than quoted.
_AFTER_LITERAL = re.compile(r"^\s*(?:;|INTO\b|USING\b)", re.IGNORECASE)
BUILT_AS_TEXT = "EXECUTE IMMEDIATE"


def _one_string_literal(text: str) -> str | None:
    """The contents of ``text`` when it is exactly one quoted string, else None."""
    body = text.strip()
    for quote in ("'''", '"""', "'", '"'):
        if not body.startswith(quote):
            continue
        end = body.find(quote, len(quote))
        while end != -1 and body[end - 1] == "\\" and quote in ("'", '"'):
            end = body.find(quote, end + 1)
        if end == -1:
            return None
        inner = body[len(quote):end]
        rest = body[end + len(quote):]
        # A literal followed by anything other than the end of the statement,
        # an INTO or a USING is a literal being added to something.
        if rest.strip() and not _AFTER_LITERAL.match(rest):
            return None
        return inner
    return None


def _reparse_run_as_text(raw: str, dialect: str | None) -> list[exp.Expression] | None:
    """The statement inside a plain ``EXECUTE IMMEDIATE '<sql>'``, or None."""
    m = _EXECUTE_IMMEDIATE.match(raw)
    if not m:
        return None
    inner = _one_string_literal(raw[m.end():])
    if inner is None or not inner.strip():
        return None
    # A "?" is a value supplied by USING at run time. The text is complete
    # without it only when it is not there.
    if "?" in inner:
        return None
    try:
        got = [s for s in sqlglot.parse(inner, read=dialect) if s is not None]
    except Exception:
        return None
    # A literal that parses to nothing but another Command has told us nothing.
    return got if got and not all(isinstance(s, exp.Command) for s in got) else None


# ── DDL that names a table and its columns and builds nothing ──────────────
# A search index, a vector index and a row access policy all name a table and
# name columns of it, and none of them carries a column anywhere. The parser
# gives up on every one of them and hands back a Command with no tables in it,
# so the whole statement was invisible: measured `couldNotRead 1`, and nothing
# anywhere saying which table or which column it was about.
#
#     CREATE SEARCH INDEX idx ON `p.d.cust`(market_code, email)
#     CREATE ROW ACCESS POLICY apac ON `p.d.cust`
#       GRANT TO ('group:apac@acme.com') FILTER USING (market_code IN ('IN','SG'))
#     UNDROP TABLE `p.d.cust`
#
# These are read with a regular expression rather than a parser, deliberately.
# Nothing here becomes lineage -- no edge, no hop, no published table. It is a
# dependency somebody has to go and change, reported as exactly that. Reading it
# loosely can add a row to a list; it can never move a chain.
_INDEX_DDL = re.compile(
    r"\b(?P<verb>CREATE|DROP)\s+(?:OR\s+REPLACE\s+)?"
    r"(?P<kind>SEARCH|VECTOR)?\s*INDEX\s+(?:IF\s+(?:NOT\s+)?EXISTS\s+)?"
    r"(?P<name>`[^`]+`|[\w.\-]+)\s+ON\s+(?P<table>`[^`]+`|[\w.\-]+)\s*(?P<cols>\([^)]*\))?",
    re.IGNORECASE,
)
_POLICY_DDL = re.compile(
    r"\b(?P<verb>CREATE|DROP)\s+(?:OR\s+REPLACE\s+)?ROW\s+ACCESS\s+POLICY\s+"
    r"(?:IF\s+(?:NOT\s+)?EXISTS\s+)?(?P<name>`[^`]+`|[\w.\-]+)\s+ON\s+"
    r"(?P<table>`[^`]+`|[\w.\-]+)",
    re.IGNORECASE,
)
_FILTER_USING = re.compile(r"\bFILTER\s+USING\s*\(", re.IGNORECASE)
_UNDROP = re.compile(r"\bUNDROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?(?P<table>`[^`]+`|[\w.\-]+)",
                     re.IGNORECASE)
# A bare word that is not a quoted string, a number or a SQL keyword.
_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_NOT_A_COLUMN = {
    "AND", "OR", "NOT", "IN", "IS", "NULL", "TRUE", "FALSE", "LIKE", "BETWEEN", "CASE",
    "WHEN", "THEN", "ELSE", "END", "SESSION_USER", "CURRENT_TIMESTAMP", "CURRENT_DATE",
    "CAST", "AS", "STRING", "INT64", "FLOAT64", "BOOL", "DATE", "TIMESTAMP", "ANY", "ALL",
    "COLUMNS", "EXISTS", "SELECT", "FROM", "WHERE",
}


def _column_words(text: str) -> list[str]:
    """Every bare word in a fragment that could be a column name."""
    out: list[str] = []
    without_strings = re.sub(r"'[^']*'|\"[^\"]*\"", " ", text)
    for m in _WORD.finditer(without_strings):
        word = m.group(0)
        if word.upper() in _NOT_A_COLUMN or word in out:
            continue
        out.append(word)
    return out


def referenced_here(raw: str) -> dict | None:
    """The table and columns named by index, policy or UNDROP DDL, or None.

    Never lineage. A dependency on a table, reported as one.
    """
    m = _INDEX_DDL.search(raw)
    if m is not None:
        kind = (m.group("kind") or "").lower()
        cols = _column_words(m.group("cols") or "")
        return {
            "refKind": f"{kind} index".strip(),
            "refTable": _bare(m.group("table")),
            "refColumns": cols,
            "refVerb": m.group("verb").upper(),
        }
    m = _POLICY_DDL.search(raw)
    if m is not None:
        cols: list[str] = []
        using = _FILTER_USING.search(raw)
        if using is not None:
            open_at = raw.find("(", using.end() - 1)
            close_at = _balanced_brackets(raw, open_at) if open_at >= 0 else -1
            if close_at > 0:
                cols = _column_words(raw[open_at + 1:close_at - 1])
        return {
            "refKind": "row access policy",
            "refTable": _bare(m.group("table")),
            "refColumns": cols,
            "refVerb": m.group("verb").upper(),
        }
    m = _UNDROP.search(raw)
    if m is not None:
        return {"refKind": "UNDROP", "refTable": _bare(m.group("table")),
                "refColumns": [], "refVerb": "UNDROP"}
    return None


def _balanced_brackets(text: str, open_at: int) -> int:
    """The index just past the ``)`` closing the ``(`` at ``open_at``, or -1."""
    depth = 0
    quote = ""
    i = open_at
    while i < len(text):
        ch = text[i]
        if quote:
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


# ── what an ALTER TABLE does to one column ─────────────────────────────────
# A migration file is where a rename is WRITTEN DOWN, in the plainest words the
# language has:
#
#     ALTER TABLE stage.customers RENAME COLUMN email TO email_address;
#
# Measured before this: target None, sources [], risk none. The one statement in
# the repository that states the rename outright was the one statement Ripple
# could not read, so a repository carrying its own migration reported no impact
# for the column the migration renames.
#
# Three actions matter, and they are three different answers:
#
#   RENAME COLUMN a TO b   the alias hop. The column carries on as b.
#   DROP COLUMN a          the column stops here, in this file, by name.
#   ALTER COLUMN a ...     the column is named, so the statement fails without it.
def _alter_actions(expr: exp.Expression | None) -> dict[str, tuple[str, str]]:
    """``{COLUMN: (kind, new name)}`` for every column an ALTER names."""
    if not isinstance(expr, exp.Alter):
        return {}
    out: dict[str, tuple[str, str]] = {}
    for action in expr.args.get("actions") or []:
        if isinstance(action, exp.RenameColumn):
            old = action.this.name if action.this is not None else ""
            new = action.args.get("to")
            new_name = new.name if new is not None else ""
            if old and new_name:
                out[old.upper()] = ("renamed", new_name)
        elif isinstance(action, exp.Drop) and isinstance(action.this, exp.Column):
            name = action.this.name
            if name:
                out[name.upper()] = ("dropped", "")
        elif isinstance(action, exp.AlterColumn):
            name = action.name or (action.this.name if action.this is not None else "")
            if name:
                out[name.upper()] = ("retyped", name)
    return out


def _renamed_to(stmt: exp.Expression) -> exp.Table | None:
    """The new name in ``ALTER TABLE old RENAME TO new``."""
    if not isinstance(stmt, exp.Alter):
        return None
    for action in stmt.args.get("actions") or []:
        if isinstance(action, RENAME_NODE) and isinstance(action.this, exp.Table):
            return action.this
    return None


def _as_whole_copy(stmt: exp.Expression) -> tuple[exp.Expression, str] | None:
    """This statement rewritten as the ``SELECT *`` it is, and how it was written.

    Returns None for everything that is not a whole-table copy, which is nearly
    every statement, so this costs two attribute lookups on the common path.
    """
    found = _copy_source(stmt)
    if found is not None:
        source, how = found
        target = stmt.this
    else:
        target = _renamed_to(stmt)
        if target is None:
            return None
        source, how = stmt.this, "RENAME"
    if not isinstance(source, exp.Table) or not isinstance(target, exp.Table):
        return None
    return (
        exp.Create(
            this=target.copy(),
            kind="TABLE",
            expression=exp.Select(expressions=[exp.Star()]).from_(source.copy()),
        ),
        how,
    )


def _cte_names(stmt: exp.Expression) -> set[str]:
    """Names defined by WITH in this statement. Not tables -- a CTE is a name
    for a query, and treating one as a table invents a link that is not there."""
    out: set[str] = set()
    for with_ in stmt.find_all(exp.With):
        for cte in with_.expressions:
            if cte.alias:
                out.add(cte.alias.upper())
    return out


# ── splitting a file into separate statements ──────────────────────────────
# Only used once a whole block has already been refused. sqlglot reads a file
# as one piece and gives up at the first statement it cannot follow, taking
# every other statement in the file down with it -- so one GRANT, one procedure
# call, one line written in a dialect the rest of the file is not in, costs the
# reader the entire file. Splitting first means one bad statement costs exactly
# one statement, and the file is reported as "3 of 14" rather than "unreadable".
def split_statements(sql: str) -> list[tuple[str, int]]:
    """(statement, 0-based line it starts on), split on real statement ends.

    Semicolons inside quotes and comments do not end a statement, which is the
    only reason this is not a call to ``str.split``.
    """
    out: list[tuple[str, int]] = []
    start = start_line = line = i = 0
    n = len(sql)
    quote = ""

    def keep(chunk: str, base: int) -> None:
        if not chunk.strip():
            return
        lead = len(chunk) - len(chunk.lstrip())
        out.append((chunk, base + chunk[:lead].count("\n")))

    while i < n:
        ch = sql[i]
        if ch == "\n":
            line += 1
            i += 1
        elif quote:
            if ch == "\\" and quote != "`":
                i += 2
            else:
                if ch == quote:
                    quote = ""
                i += 1
        elif ch in "'\"`":
            quote = ch
            i += 1
        elif sql.startswith("--", i) or ch == "#":
            found = sql.find("\n", i)
            i = n if found < 0 else found
        elif sql.startswith("/*", i):
            found = sql.find("*/", i + 2)
            end = n if found < 0 else found + 2
            line += sql.count("\n", i, end)
            i = end
        elif ch == ";":
            keep(sql[start:i], start_line)
            i += 1
            start, start_line = i, line
        else:
            i += 1
    keep(sql[start:], start_line)
    return out


def _first_code_line(chunk: str) -> str:
    """The first line of a statement worth showing on screen."""
    for raw in chunk.splitlines():
        line = raw.strip()
        if line and not line.startswith("--"):
            return line[:120]
    return chunk.strip()[:120]


def _with_lines(
    statements: list[exp.Expression], text: str, base_line: int
) -> list[tuple[exp.Expression, int, int]]:
    """Give each statement the lines of the file it actually occupies.

    sqlglot reads a whole block in one go and says nothing about where each
    statement started, so every statement in a file used to carry the same
    offset: the top of the block. A finding was then free to point at any line
    in the file that happened to score well -- and in a 600-line generated file
    with sixty statements, that regularly meant a finding about one table
    pointing at a WHERE clause belonging to a different table entirely. The
    finding was right and the line was somebody else's.

    ``split_statements`` already knows where each statement begins, and costs a
    single character scan rather than another parse. Where the two line up one
    for one, each statement gets its real span; where they do not, the block
    offset is used exactly as before rather than a span that might be wrong.
    """
    chunks = split_statements(text)
    if len(chunks) != len(statements):
        last = base_line + text.count("\n")
        return [(s, base_line, last) for s in statements]
    out: list[tuple[exp.Expression, int, int]] = []
    for stmt, (chunk, line) in zip(statements, chunks):
        start = base_line + line
        out.append((stmt, start, start + chunk.strip().count("\n")))
    return out


def _parse_text(
    text: str, dialect: str | None, base_line: int
) -> tuple[list[tuple[exp.Expression, int, int]], list[dict]]:
    """Parse a block; if it is refused, parse it one statement at a time."""
    try:
        got = [s for s in sqlglot.parse(text, read=dialect) if s is not None]
        return _with_lines(got, text, base_line), []
    except Exception:
        pass
    good: list[tuple[exp.Expression, int, int]] = []
    bad: list[dict] = []
    for chunk, line in split_statements(text):
        try:
            got = sqlglot.parse(chunk, read=dialect)
        except Exception:
            bad.append({"line": base_line + line + 1, "text": _first_code_line(chunk)})
            continue
        start = base_line + line
        end = start + chunk.strip().count("\n")
        good.extend((s, start, end) for s in got if s is not None)
    return good, bad


def _best_rendering(
    raw: str, plain: str, bad: list[dict],
    parsed: list, dialect: str | None, base_line: int,
) -> tuple[list, list[dict]]:
    """Re-read a template whose control flow stopped it parsing. See renderings.

    EVERY rendering that parses is kept, not the best one. Nothing in the file
    says which way it runs -- that is decided by a variable set somewhere else
    entirely -- so choosing a branch would be a guess, and a guess that went the
    wrong way loses a source table with nothing on any screen to say a branch
    existed. Measured on a real BigQuery warehouse: of 103 templated files with
    an if/else that read more than one way, 26 name DIFFERENT tables in their
    two branches. Reading one of those files one way and calling it read is the
    quietest version of this tool's worst failure.

    So both are read and both are followed. That is the trade this tool always
    makes: a spare row somebody can dismiss by opening the file, never a chain
    that is silently not there.

    Statements are de-duplicated on the SQL the parser actually saw, so the
    parts of the file OUTSIDE the branches -- which is nearly all of it -- are
    read once, not once per rendering.
    """
    best_bad = bad
    seen: set[str] = set()
    kept: list = []

    def take(rows: list) -> None:
        for row in rows:
            stmt = row[0]
            try:
                key = stmt.sql()
            except Exception:                              # noqa: BLE001
                key = repr(stmt)
            if key in seen:
                continue
            seen.add(key)
            kept.append(row)

    take(parsed)
    for rendered in renderings(raw):
        text = unwrap_blocks(fill_placeholders(rendered))
        text = rescue.rewrite(text)
        try:
            got, worse = _parse_text(text, dialect, base_line)
        except Exception:                                  # noqa: BLE001
            continue
        take(got)
        # The file is only still "could not be read" if EVERY way of reading it
        # refused something. One rendering reading cleanly means the file was
        # read, and saying otherwise sends somebody to look at a file that is
        # already understood.
        if len(worse) < len(best_bad):
            best_bad = worse
    return kept, best_bad


def _why_not(f: SourceFile, cfg: Settings, failures: list[dict], understood: int) -> dict:
    """One entry for the 'could not read' list, saying enough to act on.

    The point of this list is that somebody goes and checks those files by
    hand, so it has to name the line and show it. "ParseError" names nothing.
    """
    first = failures[0]
    total = understood + len(failures)
    if understood:
        reason = (f"{len(failures)} of {total} statements in this file could not be read - "
                  f"the other {understood} {'was' if understood == 1 else 'were'}")
    else:
        reason = "could not be read as SQL"
    hints: list[str] = []
    kind = describe_templating(f.text)
    if kind:
        hints.append(f"It is a template - it uses {kind}. Ripple fills those in before reading, "
                     f"and this part still did not parse.")
    if not cfg.sql_dialect:
        hints.append("This repository is being read as generic SQL. If it is BigQuery, Snowflake "
                     "or anything else in particular, choose that on the settings screen - it is "
                     "the most common reason a file will not parse.")
    return {
        "file": f.path,
        "reason": reason,
        "line": first["line"],
        "snippet": first["text"],
        "hint": " ".join(hints),
    }


# ── a query with no CREATE in front of it ──────────────────────────────────
# A dbt model is a bare SELECT. There is no CREATE, no INSERT and no MERGE, so
# nothing in the file names a table it builds -- dbt names it, after the file.
# ``models/marts/customer_published.sql`` builds ``customer_published``.
#
# Measured before this existed: a three-hop dbt chain gave productionTables 0,
# reachesProduction false, and the finding text "Selected straight through into
# the next table" when there was no next table. Every dbt repository on earth,
# and dbt is the commonest way a BigQuery pipeline is written, produced ZERO
# lineage. That is the loudest possible version of Ripple's worst failure: a
# calm, clean, complete no-impact answer over none of the picture.
#
# The name is not a guess. dbt's model name IS its file stem -- that is the rule
# the tool itself runs on, and ``ref('customer_published')`` elsewhere in the
# repository resolves through exactly the same rule. Dataform and every
# hand-rolled "one query per file" runner work the same way.
#
# Two levels of evidence, and they are labelled differently on screen because
# they are not equally sure:
#
# * "dbt" -- the file is under models/ or snapshots/, or it calls ref(),
#   source() or config(). The tool that runs this file names the table.
# * "file" -- a .sql file holding exactly one query and no CREATE anywhere.
#   Something runs it and puts the rows somewhere; naming that somewhere after
#   the file is the convention every such runner uses. Following it costs a row
#   somebody can dismiss by opening the file. Not following it costs the chain.
#
# Only ever done when the file holds ONE statement and that statement builds
# nothing. Two bare SELECTs in one file cannot both be the table the file is
# named after, and guessing which would merge two unrelated queries into one.
_DBT_FOLDER = re.compile(r"(?:^|/)(?:models|snapshots|definitions)/", re.IGNORECASE)
# Dataform's own header. Its models are named after their files too.
_DATAFORM_CONFIG = re.compile(r"^[ \t]*config\s*\{", re.IGNORECASE | re.MULTILINE)
_DBT_CALL = re.compile(r"\{\{-?\s*(?:config|ref|source|this)\b", re.IGNORECASE)
# A query, rather than something that builds a table. A UNION of two SELECTs and
# a WITH ... SELECT are both queries; sqlglot wraps the second in the Select
# itself, so only these three shapes need naming.
_A_QUERY = (exp.Select, exp.Union, exp.Subquery)

# The file has to say SELECT, in its own words, on its own first line of code.
# Asking the parse tree is not enough: several statements that build nothing and
# are named after nothing are rewritten into a bare SELECT on the way into the
# parser -- EXPORT DATA is the one that caught this -- and by the time the tree
# exists they are indistinguishable from a dbt model. EXPORT DATA delivers a file
# to somebody outside the warehouse; calling its destination "a.sql" would be a
# table that does not exist anywhere.
_LINE_COMMENT = re.compile(r"(--|#)[^\n]*")
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_QUERY_WORD = re.compile(r"^\s*(?:\(\s*)?(SELECT|WITH)\b", re.IGNORECASE)


def _is_one_query(text: str) -> bool:
    """Does this file open with SELECT or WITH once the wrapping is taken off?"""
    body = fill_placeholders(text) if has_placeholders(text) else text
    body = _BLOCK_COMMENT.sub(" ", body)
    body = _LINE_COMMENT.sub("", body)
    return bool(_QUERY_WORD.match(body.lstrip()))


# ── a column named after a function ────────────────────────────────────────
# BigQuery lets four of its built-ins be called with no brackets, so
# ``SELECT current_date FROM customer_demographics`` parses as a call to
# CURRENT_DATE and not as a column at all. A table with a column of that name
# then produces the cleanest possible zero: `risk none, prod [], found 0,
# nameInTables 0` -- Ripple did not miss the column, it never saw one.
# Backticked, the very same scan is `risk medium` and reaches production.
#
# Which of the two the writer meant cannot be known from the file: both are
# valid BigQuery and both are written exactly the same way. So both are
# followed, and the row says the table is a guess -- Ripple's standing rule,
# because a spare row is dismissed by opening the file and a lost chain is
# never seen at all.
#
# Only where the file writes the name with NO brackets. ``CURRENT_DATE()`` is
# unambiguously the function.
_PARENLESS = {
    "CURRENT_DATE": exp.CurrentDate,
    "CURRENT_TIME": getattr(exp, "CurrentTime", None),
    "CURRENT_TIMESTAMP": getattr(exp, "CurrentTimestamp", None),
    "CURRENT_DATETIME": getattr(exp, "CurrentDatetime", None),
}
_PARENLESS_NODES = tuple(n for n in _PARENLESS.values() if n is not None)


def _written_without_brackets(text: str) -> set[str]:
    """Which parenless built-ins this text writes with no brackets after them."""
    out: set[str] = set()
    upper = text.upper()
    for name in _PARENLESS:
        if name not in upper:
            continue
        for m in re.finditer(r"\b" + name + r"\b\s*(\()?", upper):
            if not m.group(1):
                out.add(name)
                break
    return out


def _rescue_parenless_functions(stmt: exp.Expression, bare: set[str]) -> set[str]:
    """Read those names as columns as well. Returns the ones put back."""
    put_back: set[str] = set()
    if not bare or not _PARENLESS_NODES:
        return put_back
    for node in list(stmt.find_all(*_PARENLESS_NODES)):
        name = next((k for k, v in _PARENLESS.items()
                     if v is not None and isinstance(node, v)), "")
        if name not in bare or node.args:
            continue
        replacement = exp.column(name.lower())
        if node.parent is None:
            continue
        node.replace(replacement)
        put_back.add(name)
    return put_back


# FOR <var> IN (...) DO -- the line the loop header was rewritten from. Read off
# the file rather than the rewritten SQL, because the rewrite is what threw the
# variable away and this is the one place the original wording survives.
_LOOP_ROW = re.compile(r"^\s*FOR\s+(\w+)\s+IN\b", re.IGNORECASE)


def _is_loop_row(f: SourceFile, stmt: Statement) -> bool:
    """Was this temporary table a FOR loop's row variable in the file itself?

    The rewrite turns the header into ``CREATE TEMP TABLE rec AS ...`` so that
    the rows the loop walks can be followed like anything else with a name. The
    file says ``FOR rec IN``, and the row on screen points at that line -- so
    the name really is written where the reader is sent, which is the whole test
    for whether Ripple is allowed to use it.
    """
    lines = f.text.splitlines()
    if not 0 <= stmt.line_offset < len(lines):
        return False
    found = _LOOP_ROW.match(lines[stmt.line_offset])
    return bool(found and found.group(1).upper() == short_name(stmt.target or "").upper())


def _declared_variable(stmt: exp.Expression) -> str:
    """The variable a DECLARE or a SET fills FROM A QUERY, or "".

        DECLARE cutoff DATE DEFAULT (SELECT MAX(cm13) FROM customer_demographics);
        CREATE OR REPLACE TABLE final_published AS
        SELECT order_id, amount FROM orders WHERE order_date > cutoff;

    Measured before this: groups [], filed as a dead end two lines above the
    CREATE that uses it. final_published's whole row set is chosen by cutoff,
    which IS MAX(cm13), so removing the column stops that statement compiling
    and stops the published table loading.

    Only a value that holds a query counts. ``DECLARE i INT64 DEFAULT 0`` binds
    nothing anybody can follow, and giving every loop counter a table of its own
    would fill the screen with names that lead nowhere.
    """
    # Everything here is checked for being an expression before it is walked.
    # sqlglot puts plain booleans in some of these slots -- BEGIN TRANSACTION is
    # an exp.Set with no assignment in it at all -- and reaching for .find on one
    # took down the whole file with an AttributeError.
    if isinstance(stmt, exp.Declare):
        for item in stmt.expressions:
            if not isinstance(item, exp.DeclareItem):
                continue
            value = item.args.get("default")
            if not isinstance(value, exp.Expression) or value.find(exp.Select) is None:
                continue
            named = item.args.get("this")
            first = named[0] if isinstance(named, list) and named else named
            if isinstance(first, exp.Expression) and getattr(first, "name", ""):
                return first.name
    if isinstance(stmt, exp.Set):
        for item in stmt.expressions:
            eq = item.args.get("this") if isinstance(item, exp.SetItem) else item
            if not isinstance(eq, exp.EQ):
                continue
            value = eq.expression
            if not isinstance(value, exp.Expression) or value.find(exp.Select) is None:
                continue
            if isinstance(eq.this, exp.Column) and eq.this.name:
                return eq.this.name
    return ""


def _bind_script_variables(f: SourceFile, out: list[Statement]) -> None:
    """Join a statement that FILLS a script variable to the ones that READ it.

    A BigQuery script does not only pass values from table to table. It passes
    them through variables -- a watermark from a DECLARE, a row from a FOR loop
    -- and both halves were being read as separate statements that had nothing
    to do with each other. Measured on both shapes: groups [], no production
    table named, over a change that really does break the published table.

    The variable is already fenced to this file by _scope_session_tables, so
    ``cutoff`` in one file cannot join up with ``cutoff`` in another. This adds
    it to the SOURCES of every statement in the file that names it, which is
    what makes the usage in a WHERE, or ``rec.seg`` in a VALUES list, count.

    Both spellings are counted: the bare name for a scalar, and the qualifier
    for a loop row. Neither is guessed at -- the name has to have been declared
    in this very file for anything to happen at all.
    """
    variables = {short_name(s.target).upper(): s.target
                 for s in out if s.script_var and s.target}
    if not variables:
        return
    for s in out:
        if s.expr is None or (s.target and short_name(s.target).upper() in variables):
            continue
        named: set[str] = set()
        for col in s.expr.find_all(exp.Column):
            for spelling in (col.table, col.name):
                if spelling and spelling.upper() in variables:
                    named.add(variables[spelling.upper()])
        if named:
            s.sources = set(s.sources) | named
            s._sources_upper = None


def _scope_session_tables(f: SourceFile, out: list[Statement]) -> None:
    """Fence this file's temporary tables off from every other file's.

    Done once the whole file is parsed, so a temp table used above the line that
    creates it is still caught. Only names with no dataset, or the ``_SESSION``
    dataset BigQuery uses for them, are moved: ``ds.t`` is a real table that
    happens to share a short name with a temp one, and taking it would cut a
    genuine chain. See the note above session_scope.
    """
    names: set[str] = set()
    for s in out:
        if s.target and (is_temporary(s.expr) or s.script_var
                         or dataset_of(s.target).upper() == _SESSION_DATASET):
            names.add(short_name(s.target).upper())
    if not names:
        return
    scope = session_scope(f.path)

    def scoped(name: str) -> str:
        if short_name(name).upper() not in names:
            return name
        ds = dataset_of(name).upper()
        if ds and ds != _SESSION_DATASET:
            return name
        return scope + "." + short_name(name)

    for s in out:
        if s.target:
            s.target = scoped(s.target)
        s.sources = {scoped(x) for x in s.sources}
        s._sources_upper = None


def _named_after_its_file(f: SourceFile, stmt: Statement, alone: bool) -> str:
    """The tool that names this file's one query, "file", or "".

    "dbt" and "Dataform" are facts: both tools name a model after its file, and
    a ``ref()`` elsewhere in the repository resolves through the same rule.
    "file" is the weaker reading -- one query, no CREATE, and something runs it,
    so it only applies when the whole file is that one query.

    A Dataform model can have ``pre_operations`` beside it, which are real
    statements with real targets. The model is still the one query that builds
    nothing of its own, so ``alone`` is not required there.
    """
    lowered = f.path.lower()
    if not (lowered.endswith(".sql") or lowered.endswith(".sqlx")):
        return ""
    if stmt.target or not isinstance(stmt.expr, _A_QUERY):
        return ""
    if lowered.endswith(".sqlx") or _DATAFORM_CONFIG.search(f.text):
        return "Dataform"
    if not alone or not _is_one_query(f.text):
        return ""
    if _DBT_FOLDER.search(f.path) or _DBT_CALL.search(f.text):
        return "dbt"
    return "file"


def parse_file(f: SourceFile, cfg: Settings) -> tuple[list[Statement], list[dict], list[dict]]:
    """Parse one file into statements, failures, and statements not understood.

    Failures are reported, never swallowed. The third list is the statements the
    reader took in but could not make sense of; they are handed back rather than
    reported, because whether they matter depends on the scan.
    """
    out: list[Statement] = []
    problems: list[dict] = []
    blocks = statements_for(f)
    # More SQL is written in this file than could be taken out of it. Asked
    # whether or not any block came out: an Airflow YAML, an Oozie workflow and
    # a shell job all normally hold several tasks of different kinds, and one
    # recognised block used to buy silence for the one beside it. See
    # looks_like_unread_sql.
    left_behind = looks_like_unread_sql(f, blocks)
    if left_behind:
        # Written as two whole sentences rather than one with a word slotted
        # into it. The slotted version read "Ripple could not take some of out
        # of it", which is not English -- on the one list whose whole job is to
        # persuade somebody to go and open a file.
        reason = ("some of the SQL written in this file could not be taken out of it"
                  if blocks else
                  "there is SQL written in this file that Ripple could not take out of it")
        problems.append({
            "file": f.path,
            "reason": reason,
            "line": 1,
            "snippet": _first_code_line(f.text),
            "hint": (("Some of this file was read and some of it was not - what is below is "
                      "not the whole of it. " if blocks else
                      "The statement is most likely built by adding short pieces of text "
                      "together, so it never exists in the file as one thing to read. ")
                     + "Open it and check by hand."),
        })
    if not blocks:
        return out, problems, []

    # For Spark/Scala jobs the destination is in the program, not the SQL.
    writes = written_tables(f)
    implied_target = writes[0] if len(writes) == 1 else None
    if len(writes) > 1:
        problems.append(
            {
                "file": f.path,
                "reason": (
                    f"writes to {len(writes)} tables ({', '.join(writes)}) - Ripple cannot tell "
                    f"which query feeds which, so lineage past this job is not traced"
                ),
            }
        )

    dialect = cfg.sql_dialect or None
    failures: list[dict] = []
    opaque: list[dict] = []
    for sql_text, offset in blocks:
        # Templating is filled in and scripting keywords are dropped on the way
        # into the parser only. Everything shown on screen still comes from the
        # file exactly as it is written, on the line it is written on.
        templated = has_placeholders(sql_text)
        text = fill_placeholders(sql_text) if templated else sql_text
        holes = placeholder_names(sql_text) if templated else set()
        # Handed straight over rather than asked about first: unwrap_blocks
        # gives the text back unchanged when there is no scripting in it, and
        # asking first meant walking every line of every file twice.
        text = unwrap_blocks(text)
        # Shapes the parser refuses outright, rewritten into ones it reads. Five
        # of them are a hard parse error, which loses the neighbouring
        # statements too; four fall back to a node with no tables in it, which
        # is invisible. See scanner/rescue.py.
        # Where each EXPORT DATA delivers to, read BEFORE the rewrite takes the
        # OPTIONS clause off. Every rewrite keeps the line count, so these line
        # numbers still line up with the statements that come out below.
        exports = rescue.export_targets(text)
        text = rescue.rewrite(text)
        parsed, bad = _parse_text(text, dialect, offset)
        # A template that uses its own control flow -- an if/else, a {% set %}
        # block, a whole block of SQL dropped in on one line -- does not survive
        # having its tags blanked and every body kept. Rendered the ordinary
        # way it is not half a file, it is no file at all: 176 of one real
        # warehouse's .sql files parsed to nothing. Each rendering is tried only
        # because THIS one failed, so a file that reads today cannot start
        # reading differently. See templating.renderings.
        if bad and templated:
            parsed, bad = _best_rendering(sql_text, text, bad, parsed,
                                          dialect, offset)
        failures.extend(bad)
        # CURRENT_DATE and its three siblings can be written with no brackets,
        # so a column of that name parses as a call and is invisible. See
        # _rescue_parenless_functions.
        bare = _written_without_brackets(sql_text)
        # Matched to statements in file order rather than by line number. The
        # rewrite takes the whole ``EXPORT DATA OPTIONS(...) AS`` away, so what
        # is left starts on the line AFTER the export's own -- the export at
        # line 0 belongs to the SELECT the parser reports at line 1.
        pending = sorted(exports)
        for outer, line, line_end in parsed:
            export_uri = ""
            while pending and pending[0][0] <= line_end:
                export_uri = pending.pop(0)[1]
            # A scripting block, a loop, a procedure call, an EXECUTE IMMEDIATE.
            # Kept, not reported: whether it matters depends on whether the name
            # somebody is chasing turns up inside it, which is not known here.
            inside: list[tuple[exp.Expression, str]] = [(outer, "")]
            if isinstance(outer, exp.Command):
                raw = outer.sql()
                again = _reparse_snapshot(raw, dialect)
                run = None if again is not None else _reparse_run_as_text(raw, dialect)
                if again is not None:
                    inside = [(again, "")]
                elif run is not None:
                    # SQL written as text and run later. The literal IS the
                    # statement, exactly as it will run, so it is read -- and
                    # every finding out of it says where it came from.
                    inside = [(s, BUILT_AS_TEXT) for s in run]
                else:
                    entry = {"line": line + 1, "text": _first_code_line(raw),
                             "sql": raw[:8000]}
                    # DDL that names a table and its columns and builds nothing:
                    # a search index, a row access policy, an UNDROP. Read for
                    # what it names, never turned into lineage.
                    ref = referenced_here(raw)
                    if ref is not None:
                        entry.update(ref)
                    opaque.append(entry)
                    continue
            for stmt, built_as_text in inside:
                guessed = _rescue_parenless_functions(stmt, bare)
                star_note = ""
                if holes:
                    _forget_templated_datasets(stmt, holes)
                    # A placeholder standing where the column list goes is a
                    # SELECT * nobody has filled in yet. See _holes_in_the_select_list.
                    filled = _holes_in_the_select_list(stmt, holes)
                    if filled:
                        star_note = ("a placeholder - this statement's column list is "
                                     "filled in when the job runs")
                # A whole-table copy or a rename has no SELECT in it at all, so the
                # chain used to stop dead on the one line that promotes a staging
                # table into the published one. See the note above _copy_source.
                written = stmt.sql()
                whole_copy = ""
                rewritten = _as_whole_copy(stmt)
                if rewritten is not None:
                    stmt, whole_copy = rewritten
                select = stmt.find(exp.Select)
                target = _target_of(stmt) or implied_target
                # A DECLARE or a SET filled from a query builds something the
                # rest of the file reads by name. See _declared_variable.
                script_var = _declared_variable(stmt)
                if script_var and not target:
                    target = script_var
                sources: set[str] = set()
                skip = _cte_names(stmt)
                # A MERGE whose USING names a table directly has no SELECT anywhere
                # in it, so it recorded no sources -- which meant the statement that
                # loads the published table was never indexed as reading anything,
                # and no scan could reach it however hard it looked. The same is
                # true of UPDATE ... FROM, which reads a whole second table and had
                # only ever recorded the table it writes.
                if select is not None or isinstance(stmt, (exp.Merge, exp.Delete, exp.Update)):
                    # Every table the whole statement reads, not just the ones in
                    # its first SELECT. A union is two SELECTs side by side, and
                    # looking only at the first made the second half of every
                    # ..._BCA_UNION table invisible: the statement was never
                    # recorded as reading that table at all, so a change to it
                    # produced no findings anywhere and the scan came back clean.
                    written = _target_node(stmt)
                    written_id = id(written) if written is not None else None
                    for t in stmt.find_all(exp.Table):
                        # The write target, left out by identity rather than by
                        # name. See the note above _target_node for what comparing
                        # names cost.
                        if written_id is not None and id(t) == written_id:
                            continue
                        qualified = _qualify(t)
                        # A metadata view is the warehouse describing itself. It
                        # carries no column of anybody's table, and its names --
                        # COLUMNS, TABLES, JOBS -- collide with real ones. See
                        # is_metadata_read.
                        if (qualified and t.name.upper() not in skip
                                and not is_metadata_read(qualified)):
                            sources.add(qualified)
                        # APPENDS(TABLE t, ...) and a TVF given a table: the table
                        # handed in is a real read and is nowhere else in the tree.
                        for handed in _tables_handed_to_a_call(t):
                            if short_name(handed).upper() not in skip:
                                sources.add(handed)
                # A DELETE or an UPDATE reads the table it changes. Without this the
                # statement has no source, so nothing ever looks at its WHERE clause
                # -- and a filter on a column that is about to disappear is exactly
                # the kind of thing this tool exists to find.
                # An ALTER is the same shape: it names one table and changes it in
                # place, and a RENAME COLUMN on it is an alias hop like any other.
                if isinstance(stmt, (exp.Delete, exp.Update, exp.Alter)) and target:
                    sources.add(target)
                # A DECLARE has no SELECT the loop above would walk into, so the
                # table its value is read from was recorded nowhere.
                if script_var and not sources:
                    for t in stmt.find_all(exp.Table):
                        qualified = _qualify(t)
                        if qualified and not is_metadata_read(qualified):
                            sources.add(qualified)
                out.append(
                    Statement(
                        file=f.path,
                        lang=f.lang,
                        line_offset=line,
                        line_end=line_end,
                        sql=written,
                        target=target,
                        sources=sources,
                        select=select,
                        expr=stmt,
                        whole_copy=whole_copy,
                        star_note=star_note,
                        guessed_columns=guessed,
                        built_as_text=built_as_text,
                        export_uri=export_uri,
                        script_var=script_var,
                    )
                )
    # A FOR loop's row variable is filled by its header, which is rewritten into
    # a temporary table of that name on the way into the parser. See _loop_read.
    for s in out:
        if not s.script_var and s.target and is_temporary(s.expr) and _is_loop_row(f, s):
            s.script_var = short_name(s.target)
    # A temporary table belongs to the file that made it and to nothing else.
    _scope_session_tables(f, out)
    # ... and now the statements that read those variables can be joined to the
    # ones that fill them. After the fence, so the names match.
    _bind_script_variables(f, out)
    # A file that is one query and builds nothing names its table after itself.
    # Done here rather than in the loop above because it is only true when the
    # whole file is that one query -- see _named_after_its_file.
    building_nothing = [s for s in out if s.target is None and isinstance(s.expr, _A_QUERY)]
    if len(building_nothing) == 1:
        one = building_nothing[0]
        how = _named_after_its_file(f, one, alone=len(out) == 1)
        if how:
            one.target = Path(f.path).stem
            one.named_by = how
    # DDL that builds nothing but names a table and its columns -- an index, a
    # row access policy, an UNDROP. Ripple DID learn what it names, and reports
    # it as exactly that rather than as a file nobody could read. Left on the
    # "check by hand" list it was pure noise on the one list that has to stay
    # short enough for somebody to read to the bottom of.
    lost = [o for o in opaque if not o.get("refKind")]
    if failures:
        failures.sort(key=lambda p: p["line"])
        problems.append(_why_not(f, cfg, failures, len(out)))
    elif lost and not out:
        # Nothing in this file was understood. The reader did not fall over, it
        # simply got nothing out -- which is the quietest way to lose a file and
        # the reason the wrong SQL dialect used to look like a clean repository.
        first = lost[0]
        problems.append({
            "file": f.path,
            "reason": f"read, but not one of its {len(lost)} statements was understood",
            "line": first["line"],
            "snippet": first["text"],
            "hint": ("Nothing was learned from this file at all - no table, no column, no "
                     "lineage." + ("" if cfg.sql_dialect else
                     " This repository is being read as generic SQL; if it is BigQuery, "
                     "Snowflake or anything else in particular, choose that on the settings "
                     "screen.")),
        })
    return out, problems, opaque


def parse_repo(index: RepoIndex, cfg: Settings | None = None, on_progress=None) -> ParsedRepo:
    """Read every file as SQL. ``on_progress(done, total, label)`` is called as
    it goes: on a repository of a few thousand files this is minutes of work,
    and it is by far the slowest thing Ripple does."""
    cfg = cfg or default_settings
    pr = ParsedRepo()
    problems: list[dict] = list(index.skipped)
    total = len(index.files)
    for done, f in enumerate(index.files, start=1):
        if on_progress is not None and (done % 10 == 0 or done == total):
            on_progress(done, total, "Understanding the SQL")
        try:
            stmts, file_problems, opaque = parse_file(f, cfg)
        except Exception as exc:
            # Reading a repository takes minutes. Letting one unexpected shape
            # end the whole thing with a traceback loses every file after it,
            # and the person is left with nothing at all rather than with an
            # answer and one file to check by hand.
            log.warning("could not read %s: %s", f.path, exc)
            problems.append({
                "file": f.path,
                "reason": (f"Ripple could not read this file at all "
                           f"({type(exc).__name__}) - check it by hand"),
            })
            continue
        if stmts:
            pr.statements.extend(stmts)
            pr.parsed_files.add(f.path)
        if opaque:
            pr.opaque[f.path] = opaque
            pr.references.extend(
                {"file": f.path, "line": o["line"], "snippet": o["text"],
                 "kind": o["refKind"], "table": o["refTable"],
                 "columns": o["refColumns"], "verb": o["refVerb"]}
                for o in opaque if o.get("refKind")
            )
        problems.extend(file_problems)
    problems.extend(_follow_sql_file_refs(index, pr))
    # Done once every file is parsed, because the two ends of a CALL are in two
    # different files and neither one alone can see the pair.
    _follow_procedure_calls(index, pr)
    pr.unreadable = _one_entry_per_file(problems)
    return pr


def _follow_sql_file_refs(index: RepoIndex, pr: ParsedRepo) -> list[dict]:
    """Match every program that names a .sql file to the file it names.

    Found is the good case and is only recorded. Not found is a real hole: the
    program runs a query that is not in this repository, so nothing in it has
    been read and no scan can cover it.
    """
    by_path = {f.path.lower(): f.path for f in index.files}
    by_name: dict[str, str] = {}
    for f in index.files:
        if f.path.lower().endswith(".sql"):
            by_name.setdefault(f.path.rsplit("/", 1)[-1].lower(), f.path)

    missing: list[dict] = []
    for f in index.files:
        for ref in sql_file_refs(f):
            wanted = ref["ref"].replace("\\", "/").lstrip("./")
            runs = by_path.get(wanted.lower()) or by_name.get(wanted.rsplit("/", 1)[-1].lower(), "")
            pr.runs_sql_from.append(
                {"file": f.path, "ref": ref["ref"], "line": ref["line"], "runs": runs}
            )
            if runs:
                continue
            missing.append({
                "file": f.path,
                "reason": f"runs the SQL in {ref['ref']}, which is not in this repository",
                "line": ref["line"],
                "snippet": ref["ref"],
                "hint": ("Ripple has never read that query, so nothing it does is covered by "
                         "this scan. If the file lives in another repository, scan that one "
                         "too; if it is generated at run time, it has to be checked by hand."),
            })
    return missing


# ── a procedure CALLed from another file ───────────────────────────────────
# CALL ds.publish_it() runs in the SAME session as the statement above it, so a
# TEMP table the caller has just built IS visible inside the procedure. Ripple's
# fence round temporary tables (see session_scope) renamed the CALLER's "stg" to
# "#A_SQL.stg" and left the procedure's "stg" alone, so the two stopped matching
# and the trail died on the temp table -- with the file that really breaks filed
# under "the name appears, but no lineage to a production table", which is the
# one sentence this tool exists to stop anybody printing over a live chain.
#
# Read off the file TEXT rather than the parse tree, because neither end
# survives parsing: the procedure signature is dropped on the way in (that is
# what lets the body be read at all), and the CALL comes out as a statement
# nobody understood.
#
# Short name only, and every file defining that name is taken. This is
# FOLLOWING a chain, which is the side of that rule where a loose match is
# right -- and the dataset in front of a procedure name is usually a
# placeholder in these files anyway.
_PROCEDURE_DEF = re.compile(
    r"^[ \t]*CREATE\s+(?:OR\s+REPLACE\s+)?PROCEDURE\s+(?:IF\s+NOT\s+EXISTS\s+)?"
    r"([`\"\w.${}-]+)", re.IGNORECASE | re.MULTILINE)
_PROCEDURE_CALL = re.compile(r"(?<![\w.])CALL\s+([`\"\w.${}-]+)\s*\(", re.IGNORECASE)


def _reached_through(edges: dict[str, set[str]], start: str) -> set[str]:
    """Every file reachable from this one by following CALL edges."""
    seen: set[str] = set()
    stack = [start]
    while stack:
        for nxt in edges.get(stack.pop(), ()):
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    seen.discard(start)
    return seen


def _follow_procedure_calls(index: RepoIndex, pr: ParsedRepo) -> None:
    """Let a temporary table cross a CALL, and let nothing else cross it.

    The fence stays exactly as it is. A name is only unfenced along an edge
    Ripple can point at: this file CALLs a procedure, that file defines it, so
    the two run in one session and one file's temp table is the other's.
    Everything else -- two files that both build a ``stg`` and never call each
    other -- is untouched, which is the whole reason the fence exists.

    Widened, never replaced: the plain ``stg`` stays in sources beside the
    scoped one. So nothing that matched before stops matching, and where two
    different callers hand their own ``stg`` to the SAME procedure both are
    added and both chains are followed rather than one being guessed at.
    """
    defined: dict[str, list[str]] = {}
    called: dict[str, set[str]] = {}
    for f in index.files:
        for m in _PROCEDURE_DEF.finditer(f.text):
            defined.setdefault(short_name(_bare(m.group(1))).upper(), []).append(f.path)
        for m in _PROCEDURE_CALL.finditer(f.text):
            called.setdefault(f.path, set()).add(short_name(_bare(m.group(1))).upper())
    if not defined or not called:
        return

    runs: dict[str, set[str]] = {}
    run_by: dict[str, set[str]] = {}
    for caller, procs in sorted(called.items()):
        for proc in sorted(procs):
            for callee in defined.get(proc, []):
                if callee == caller:
                    continue                    # one file, already one fence
                pr.procedure_calls.append({"file": caller, "proc": proc, "runs": callee})
                runs.setdefault(caller, set()).add(callee)
                run_by.setdefault(callee, set()).add(caller)

    fenced: dict[str, set[str]] = {}
    by_file: dict[str, list[Statement]] = {}
    for s in pr.statements:
        by_file.setdefault(s.file, []).append(s)
        if s.target and is_session_scoped(s.target):
            fenced.setdefault(s.file, set()).add(short_name(s.target).upper())

    # Both directions, and the whole way down a chain of calls. A procedure a
    # procedure calls is still the first caller's session; and a temp table
    # built INSIDE a procedure is visible to whatever called it, which is the
    # same pair read the other way round.
    for path, names in fenced.items():
        scope = session_scope(path)
        for other in _reached_through(runs, path) | _reached_through(run_by, path):
            for s in by_file.get(other, ()):
                # A name the SQL qualified is a real table that happens to share
                # a short name, and a name already fenced belongs to its own
                # file. Neither one is this session's temporary table.
                extra = {scope + "." + short_name(x) for x in s.sources
                         if not dataset_of(x) and short_name(x).upper() in names}
                if extra:
                    s.sources |= extra
                    s._sources_upper = None


def _one_entry_per_file(problems: list[dict]) -> list[dict]:
    """Collapse repeated failures in the same file down to one entry.

    A program file can hold several blocks of SQL and fail on more than one of
    them. That is still one file for a person to go and check, so counting it
    twice would overstate "could not read" -- the number this whole tool is
    judged on. The repeats are kept as a count so nothing is hidden.
    """
    merged: dict[str, dict] = {}
    for p in problems:
        key = p.get("file", "")
        if key in merged:
            merged[key]["places"] += 1
        else:
            merged[key] = {**p, "places": 1}
    return list(merged.values())


# ── which table a column came from ─────────────────────────────────────────
# In this warehouse cm13, cm11 and pub_guid are columns in nearly every table,
# so nearly every join has the same name on both sides. Matching on the name
# alone meant a filter on the OTHER table's cm13 was reported as a usage of the
# one being changed -- a finding about the wrong table, in a repository where
# that is the ordinary case rather than an edge one.
#
# The statement usually says which is which, and when it does that is a fact
# about the SQL rather than a guess: "a.cm13" belongs to whatever "a" is. Where
# it does not say, nothing is thrown away -- the usage is kept and marked.


def _sources_of(stmt: Statement) -> dict[str, list[str]]:
    """Every alias and table name this statement reads, and what each can mean.

    A list rather than one name, because a bare ``customer_demographics`` in a
    statement that reads it out of two datasets genuinely does not say which.
    Answering that with whichever one happened to be parsed first is how a
    change to the source table produced findings about the archive copy.
    """
    out: dict[str, list[str]] = {}

    def add(key: str, value: str) -> None:
        bucket = out.setdefault(key.upper(), [])
        if value not in bucket:
            bucket.append(value)

    if stmt.expr is None:
        return out
    for t in stmt.expr.find_all(exp.Table):
        for handed in _tables_handed_to_a_call(t):
            add(short_name(handed), handed)
            if t.alias:
                add(t.alias, handed)
        qualified = _qualify(t)
        if not qualified:
            continue
        add(t.name or short_name(qualified), qualified)
        if t.alias:
            add(t.alias, qualified)
    return out


def _binds_here(sel: exp.Expression) -> dict[str, list[str]]:
    """The names THIS one SELECT binds in its own FROM and JOINs.

    Its own, not its subqueries'. A subquery given an alias binds that alias to
    whatever tables the subquery reads, because ``t.cm13`` written outside
    ``(SELECT * FROM customer_demographics) t`` really is that table's column.
    """
    out: dict[str, list[str]] = {}

    def add(key: str, value: str) -> None:
        bucket = out.setdefault(key.upper(), [])
        if value not in bucket:
            bucket.append(value)

    if not isinstance(sel, exp.Select):
        return out
    for part in [from_of(sel)] + list(sel.args.get("joins") or []):
        node = getattr(part, "this", None) if part is not None else None
        if isinstance(node, exp.Table):
            for handed in _tables_handed_to_a_call(node):
                add(short_name(handed), handed)
                if node.alias:
                    add(node.alias, handed)
            qualified = _qualify(node)
            if qualified:
                add(node.name or short_name(qualified), qualified)
                if node.alias:
                    add(node.alias, qualified)
        elif isinstance(node, exp.Subquery) and node.alias:
            # The alias stands for every table the subquery reads. Where it
            # reads more than one, the SQL has not said which -- and a list is
            # how _belongs_to is told to mark it rather than pick one.
            for inner in node.find_all(exp.Table):
                qualified = _qualify(inner)
                if qualified:
                    add(node.alias, qualified)
    return out


def _scopes_of(stmt: Statement) -> dict[int, dict[str, list[str]]]:
    """One binding map per SELECT in the statement, worked out once and kept."""
    if stmt._scopes is not None:
        return stmt._scopes
    out: dict[int, dict[str, list[str]]] = {}
    if stmt.expr is not None:
        for sel in stmt.expr.find_all(exp.Select):
            out[id(sel)] = _binds_here(sel)
    stmt._scopes = out
    return out


def _resolve_qualifier(col: exp.Column, stmt: Statement,
                       sources: dict[str, list[str]]) -> list[str]:
    """What ``t`` means where THIS ``t.cm13`` is written.

    The same alias means two different things in two scopes more often than it
    looks, and a flat map across the whole statement gets the wrong one::

        SELECT t.k, o.amount
        FROM (SELECT * FROM customer_demographics) t
        JOIN orders o ON o.k = t.k
        WHERE t.cm13 = 'A'
          AND EXISTS (SELECT 1 FROM legacy_dim t WHERE t.k = o.k)

    The inner EXISTS re-binds ``t`` to ``legacy_dim``. Flat, that was the only
    binding of ``t`` the map held -- the outer ``t`` is a subquery alias, which
    is not a table at all -- so the breaking ``WHERE t.cm13`` was ruled out as
    some other table's column and the scan said risk low over a change that
    stops this statement compiling.

    This walks OUT from the column to the nearest SELECT that binds the name,
    which is what SQL itself does. The flat map stays as the fallback: it is
    what answers for a qualifier bound somewhere this cannot see.
    """
    scopes = _scopes_of(stmt)
    node = col.parent
    while node is not None:
        binding = scopes.get(id(node))
        if binding:
            options = binding.get(col.table.upper())
            if options:
                return options
        node = node.parent
    return sources.get(col.table.upper()) or []


def _belongs_to(col: exp.Column, stmt: Statement, table: str,
                sources: dict[str, list[str]], ctes: set[str]) -> str:
    """'yes', 'no' or 'unknown' -- is this column reference `table`'s?"""
    qualifier = col.table
    if not qualifier:
        # Unqualified. If the statement only reads one table it can only have
        # come from there. If it reads several, the SQL has not said.
        return "yes" if len(stmt.sources) <= 1 else "unknown"
    options = _resolve_qualifier(col, stmt, sources)
    if not options:
        return "unknown"                 # an alias from somewhere we cannot see
    if any(short_name(o).upper() in ctes for o in options):
        # It came out of a WITH block, which was itself built from something.
        # That is exactly the chain being followed, so it is not a reason to
        # rule the usage out.
        return "unknown"
    verdicts = {"yes" if same_table(o, table) else "no" for o in options}
    if verdicts == {"yes"}:
        return "yes"
    if verdicts == {"no"}:
        return "no"
    # The name stands for two tables at once and one of them is this one. Kept,
    # and marked -- never silently counted as a fact about either.
    return "unknown"


# ── SELECT *, which carries every column and names none of them ────────────
def _direct_tables(sel: exp.Select) -> list[str]:
    """The tables this SELECT reads in its own FROM and JOINs.

    Its own, not a subquery's: a star in an outer SELECT covers whatever the
    subquery below it hands up, and that subquery has a star check of its own.
    """
    out: list[str] = []
    parts = [from_of(sel)] + list(sel.args.get("joins") or [])
    for part in parts:
        node = getattr(part, "this", None) if part is not None else None
        if isinstance(node, exp.Table):
            qualified = _qualify(node)
            if qualified and qualified not in out:
                out.append(qualified)
    return out


def _is_star(e: exp.Expression) -> bool:
    """``*`` or ``a.*`` -- either way, not a column reference."""
    return isinstance(e, exp.Star) or (isinstance(e, exp.Column)
                                       and isinstance(e.this, exp.Star))


def _star_of(e: exp.Expression) -> exp.Star:
    return e if isinstance(e, exp.Star) else e.this


def _whole_row_aliases(stmt: Statement) -> dict[str, list[str]]:
    """Names that stand for a WHOLE ROW of a table, and which table that is.

    BigQuery lets a query carry a whole row around as one value, and the
    standard dbt-utils ``deduplicate`` macro is written exactly that way::

        SELECT unique_row.* FROM (
          SELECT ARRAY_AGG(original ORDER BY loaded_at DESC LIMIT 1)[OFFSET(0)]
                   AS unique_row
          FROM customer_demographics original
          GROUP BY id)

    ``original`` on its own -- a bare name that is the table's alias rather than
    any column of it -- is the entire row. So ``unique_row.*`` publishes every
    column ``customer_demographics`` has, which is precisely what SELECT * means.

    Ripple's whole honesty guarantee rests on admitting when a table's column
    list is not written down, and that admission fired for ``SELECT *`` and for
    ``alias.*`` over a real table, but not for this. A deduplicated staging
    table -- an ordinary thing to find in a dbt repository -- gave a clean "no
    impact" with no warning of any kind.

    Only a BARE reference counts. ``original.loaded_at`` is one column, and
    ``STRUCT(a, b) AS s`` is two named ones; neither is a whole row.
    """
    if stmt.expr is None:
        return {}
    out: dict[str, list[str]] = {}
    for sel in stmt.expr.find_all(exp.Select):
        # What this SELECT's own FROM and JOINs call the tables they read.
        here: dict[str, str] = {}
        parts = [from_of(sel)] + list(sel.args.get("joins") or [])
        for part in parts:
            node = getattr(part, "this", None) if part is not None else None
            if not isinstance(node, exp.Table):
                continue
            qualified = _qualify(node)
            if not qualified:
                continue
            here[(node.alias or node.name or "").upper()] = qualified
        if not here:
            continue
        for e in sel.expressions:
            if not isinstance(e, exp.Alias) or not e.alias:
                continue
            for col in e.find_all(exp.Column):
                if col.table or isinstance(col.this, exp.Star):
                    continue                      # one column, or a star already
                owner = here.get(col.name.upper())
                if owner:
                    bucket = out.setdefault(e.alias.upper(), [])
                    if owner not in bucket:
                        bucket.append(owner)
    return out


def _stars_over(stmt: Statement, table: str, sources: dict[str, list[str]]) -> list[exp.Star]:
    """Every ``SELECT *`` in this statement that covers `table`'s columns."""
    if stmt.expr is None:
        return []
    rows = _whole_row_aliases(stmt)
    found: list[exp.Star] = []
    for sel in stmt.expr.find_all(exp.Select):
        reads = _direct_tables(sel)
        direct = any(same_table(t, table) for t in reads)
        for e in sel.expressions:
            if isinstance(e, exp.Star):
                if direct:
                    found.append(e)                  # SELECT * -- everything
            elif isinstance(e, exp.Column) and isinstance(e.this, exp.Star):
                key = (e.table or "").upper()
                # a.* -- only the table that alias stands for.
                if direct and any(same_table(o, table) for o in sources.get(key, [])):
                    found.append(e.this)
                    continue
                # x.* where x is a whole row of the table, carried as one value.
                # Not gated on this SELECT reading the table: it does not, the
                # subquery under it does, and the scoping is done where the
                # alias is worked out.
                if any(same_table(o, table) for o in rows.get(key, [])):
                    found.append(e.this)
    return found


# ── _TABLE_SUFFIX ──────────────────────────────────────────────────────────
# A wildcard table reads a whole family of date-sharded tables, and the query
# almost always narrows that down on the very next line::
#
#     SELECT cm13 FROM `p.ds.customer_demographics_*`
#     WHERE _TABLE_SUFFIX = '20260101'
#
# Ripple followed the wildcard and never read the line under it, so scanning
# ``customer_demographics_19991231`` -- a shard from 1999 that this query
# provably never touches -- came back `risk medium, prod ['g_published'],
# breaking true, certain true`, with no hedge anywhere. The predicate is on the
# same line as the wildcard, inside the snippet Ripple prints, and the answer
# contradicted it.
#
# Only literals decide anything. A parameter, a date calculation or a variable
# is not something a static reader can evaluate, and guessing at one would trade
# an over-confident finding for a missing one. Those set `certain=False` and the
# finding stays.
#
# Only ANDs. ``_TABLE_SUFFIX = 'x' OR something_else`` reads the other shards
# too, and a NOT turns every comparison below it inside out.
_SUFFIX_COL = "_TABLE_SUFFIX"


def _only_ands_above(node: exp.Expression, stop: exp.Expression) -> bool:
    """Is every branch between here and the WHERE an AND?"""
    cur = node.parent
    while cur is not None and cur is not stop:
        if isinstance(cur, (exp.Or, exp.Not)):
            return False
        cur = cur.parent
    return True


def _shard_suffix(table: str, pattern: str) -> str:
    """The part of a shard's name the wildcard stands for, or ''.

    Empty for the family itself. Somebody who typed ``customer_demographics_*``
    is asking about every shard, so no one suffix can be tested and every
    predicate has to be read as letting some of them through.
    """
    if is_wildcard(table):
        return ""
    prefix = short_name(pattern).upper()
    if not prefix.endswith(_STAR):
        return ""
    prefix = prefix[:-1]
    name = short_name(table)
    if not prefix or not name.upper().startswith(prefix):
        return ""
    suffix = name[len(prefix):]
    return "" if _STAR in suffix else suffix


def suffix_verdict(stmt: Statement, table: str) -> str:
    """"reads", "maybe" or "excluded" -- does this statement touch that shard?

    "reads" also means "nothing here says otherwise", which is the answer for
    every statement that has no _TABLE_SUFFIX in it at all.
    """
    if stmt.expr is None:
        return "reads"
    patterns = [s for s in stmt.sources if is_wildcard(s) and same_table(s, table)]
    if not patterns:
        return "reads"
    suffix = next((s for s in (_shard_suffix(table, p) for p in patterns) if s), "")
    if not suffix:
        return "reads"                      # the family name, not a shard
    verdict = "reads"
    for sel in stmt.expr.find_all(exp.Select):
        where = sel.args.get("where")
        if where is None:
            continue
        for col in where.find_all(exp.Column):
            if col.name.upper() != _SUFFIX_COL:
                continue
            test = col.parent
            if not _only_ands_above(col, where):
                return "maybe"
            hit = _suffix_allows(test, suffix)
            if hit == "excluded":
                return "excluded"
            if hit == "maybe":
                verdict = "maybe"
    return verdict


def _suffix_allows(test: exp.Expression | None, suffix: str) -> str:
    """Does this one comparison let that suffix through?"""
    def literal(node) -> str | None:
        return node.this if isinstance(node, exp.Literal) else None

    if isinstance(test, exp.Between):
        low, high = literal(test.args.get("low")), literal(test.args.get("high"))
        if low is None or high is None:
            return "maybe"
        return "reads" if low <= suffix <= high else "excluded"
    if isinstance(test, exp.In):
        values = [literal(v) for v in test.expressions]
        if not values or any(v is None for v in values):
            return "maybe"
        return "reads" if suffix in values else "excluded"
    if isinstance(test, (exp.EQ, exp.NEQ, exp.GT, exp.GTE, exp.LT, exp.LTE)):
        # Only when the column is on the left; ``'x' = _TABLE_SUFFIX`` is legal
        # and rare, and reading it backwards would exclude the wrong shard.
        if not isinstance(test.this, exp.Column):
            return "maybe"
        value = literal(test.args.get("expression"))
        if value is None:
            return "maybe"
        ok = {
            exp.EQ: suffix == value,
            exp.NEQ: suffix != value,
            exp.GT: suffix > value,
            exp.GTE: suffix >= value,
            exp.LT: suffix < value,
            exp.LTE: suffix <= value,
        }[type(test)]
        return "reads" if ok else "excluded"
    return "maybe"


def _named_in_except(star: exp.Star, column: str) -> bool:
    """``SELECT * EXCEPT(cm13)`` -- the one shape where a star drops a column."""
    for c in star_except(star):
        if getattr(c, "name", "").upper() == column.upper():
            return True
    return False


def star_sources(stmt: Statement) -> list[tuple[exp.Star, list[str]]]:
    """Every star in this statement's own projection, with the tables it covers.

    ``SELECT *`` covers every table the SELECT reads directly; ``a.*`` covers
    only the table the alias stands for. Used to fill in the column list of a
    table built with a star from tables whose columns are written down -- see
    catalog.build_catalog. Stars inside subqueries are not here: it is the
    statement's own projection that names the built table's columns.
    """
    sel = stmt.select
    if sel is None:
        return []
    direct = _direct_tables(sel)
    aliases = _sources_of(stmt)
    out: list[tuple[exp.Star, list[str]]] = []
    for e in sel.expressions:
        if isinstance(e, exp.Star):
            out.append((e, list(direct)))
        elif isinstance(e, exp.Column) and isinstance(e.this, exp.Star):
            out.append((e.this, list(aliases.get((e.table or "").upper(), []))))
    return out


def star_carries(stmt: Statement, column: str, table: str,
                 sources: dict[str, list[str]] | None = None) -> bool:
    """Does a ``SELECT *`` carry this column of this table out of the statement?

    ``SELECT * FROM customer_demographics`` really does publish every column
    that table has, including the one being traced. The column list is simply
    not written down anywhere a parser can read it.

    Refusing to follow that was the largest hole in Ripple. Forty-four tables in
    the repository this was built for are made this way, so the trail died at
    the first one it met -- and a change that breaks a published table one hop
    later came back as a clean, confident "no impact".
    """
    stars = _stars_over(stmt, table, sources if sources is not None else _sources_of(stmt))
    return any(not _named_in_except(s, column) for s in stars)


def star_excludes(stmt: Statement, column: str, table: str,
                  sources: dict[str, list[str]] | None = None) -> bool:
    """Is the column named in a ``SELECT * EXCEPT(...)`` of this statement?

    Two things at once, and both matter. The column does not reach the table
    this statement builds, so the chain genuinely stops -- and the statement
    names the column out loud, so removing or renaming it makes this statement
    fail on the day of the change.
    """
    stars = _stars_over(stmt, table, sources if sources is not None else _sources_of(stmt))
    return any(_named_in_except(s, column) for s in stars)


# ── working out how a column is used ───────────────────────────────────────
def _cols_named(node: exp.Expression | None, name: str) -> list[exp.Column]:
    """Every reference to this column. A dotted name must match dotted.

    A STRUCT field is carried as ``payload.code``, and that name has to be
    matched against the QUALIFIER too. Matching it on the leaf alone would make
    a plain column called ``code`` on an unrelated table look like the struct's
    field -- which is the invented-column mistake the ordinary-struct guard
    exists to stop.
    """
    if node is None:
        return []
    if "." in name:
        qualifier, _, leaf = name.rpartition(".")
        return [c for c in node.find_all(exp.Column)
                if c.name.upper() == leaf.upper()
                and c.table.upper() == qualifier.upper()]
    return [c for c in node.find_all(exp.Column) if c.name.upper() == name.upper()]


def _literal_beside(node: exp.Expression, col: exp.Column) -> str:
    """If the column is compared to a literal, return it -- that is the detail
    that turns 'used in a filter' into 'compared against US'."""
    parent = col.parent
    while parent is not None and not isinstance(parent, exp.Binary):
        parent = parent.parent
    if isinstance(parent, exp.Binary):
        for side in (parent.left, parent.right):
            if isinstance(side, exp.Literal):
                return side.this
    return ""


# How many names one column may be followed under out of a single statement.
# Real SQL publishes a column under one name, occasionally two or three -- the
# value itself and a cleaned-up copy of it. The cap is here so that a generated
# statement with hundreds of derived columns cannot turn one scan into a search
# of the whole warehouse; it is set far above anything hand-written.
MAX_OUTPUT_NAMES = 6


# How many times a rename may be fed straight into another rename inside ONE
# level before this stops looking. Sibling CTEs in a single WITH are all at the
# same SELECT depth, so a chain of them is resolved here rather than by the
# level loop. Set well above anything hand-written; it only has to terminate.
MAX_CHAINED_RENAMES = 12


def _resolve_level(names: list[str], direct_map: dict, derived_map: dict) -> list[str]:
    """Every name these names become at one level, following renames fed by renames.

    The levels handed to ``output_names`` are grouped by how deeply nested each
    SELECT is, and the CTEs of a single WITH are all at the SAME depth even
    though they feed each other::

        WITH src     AS (SELECT k, cm13 FROM customer_demographics),
             renamed AS (SELECT k, cm13 AS customer_code FROM src),
             final   AS (SELECT k, customer_code AS cust_code FROM renamed)
        SELECT * FROM final

    Applying that level in one pass followed ``cm13`` to ``customer_code`` and
    stopped, because ``customer_code -> cust_code`` was in the very same map and
    the map was only ever read once. The table really does publish ``cust_code``,
    so a change to ``cm13`` reached a published table under a name Ripple never
    said, and the scan came back clean.

    Which CTE feeds which is not knowable from depth, so this does not try to
    put them in order: it runs to a fixpoint instead, which gets the same answer
    whatever order they are written in. The set only grows and every name comes
    from the statement, so it terminates; the counter is a backstop.

    Following a rename that happens to share a name with an unrelated sibling
    can add a name the column never really takes. That is the safe direction:
    a spare row is visible on screen and dismissed by opening the file, while a
    lost chain is invisible and reads as "no impact".
    """
    found: list[str] = []
    frontier = list(names)
    seen = {n.upper() for n in names}
    for _ in range(MAX_CHAINED_RENAMES):
        step: list[str] = []
        for name in frontier:
            step.extend(direct_map.get(name.upper(), ()))
        for name in frontier:
            step.extend(derived_map.get(name.upper(), ()))
        step = _dedupe(step)
        if not step:
            break
        found.extend(step)
        frontier = [s for s in step if s.upper() not in seen]
        if not frontier:
            break
        seen.update(s.upper() for s in frontier)
    return _dedupe(found)


def output_names(stmt: Statement, column: str, limit: int = MAX_OUTPUT_NAMES) -> list[str]:
    """Every name this column is published under once the statement is done.

    Renames often happen inside a subquery -- ``c.last_upd AS lut_ts`` buried in
    a ranking, then simply carried out by the enclosing SELECT. Resolving from
    the innermost query outwards is what keeps the chain joined up; without it
    the trail goes cold at exactly the statements that matter most.

    A column also leaves under more than one name more often than it looks::

        SELECT CAST(cm13 AS STRING) AS cm13_str,
               cm13
        FROM customer_demographics

    Following only the first of those was a silent, expensive mistake. The next
    table along reads ``cm13``, not ``cm13_str``, so the chain stopped one step
    short -- and a change that really does reach a published table was reported
    as no production impact, which is the exact answer this tool exists to stop
    anybody giving.

    The name carried through unchanged is always kept first, so it survives the
    cap: it is the one the rest of the warehouse is most likely to be using.
    """
    if stmt.expr is None:
        return [column]
    # An ALTER has no SELECT to walk. What it does to this column is written on
    # the statement itself: a rename carries it on under the new name, a DROP
    # ends it here, and anything else leaves the name alone.
    action = _alter_actions(stmt.expr).get(column.upper())
    if action is not None:
        kind, new_name = action
        return [] if kind == "dropped" else [new_name or column]
    cached = stmt._names.get(column.upper())
    if cached is not None:
        return cached
    names = [column]
    for direct_map, derived_map, passthrough, dropped in _projections(stmt):
        found = _resolve_level(names, direct_map, derived_map)
        # A star carries the name through untouched -- unless the star names it
        # in an EXCEPT, which is the one shape where a star drops a column.
        # Written beside explicit columns -- SELECT *, CAST(cm13 AS STRING) AS
        # cm13_str -- it leaves under BOTH names, and the untouched one is kept
        # first because it is the one the rest of the warehouse is likeliest to
        # be reading.
        if passthrough:
            kept = [n for n in names if n.upper() not in dropped]
            found = _dedupe(kept + found)
            if not found:
                # Every name was dropped by an EXCEPT. The column really does
                # stop here, and saying so is the point of tracking this at all.
                return []
        # Not projected at this level at all. That is normal -- the column may
        # only be in a WHERE or a JOIN here -- so the name it had carries on
        # rather than the trail being dropped.
        names = found[:limit] if found else names
    names = _through_insert_columns(stmt, names)
    names = _through_create_columns(stmt, names)
    names = _through_merge_columns(stmt, names)
    names = _through_declared_variable(stmt, names)
    stmt._names[column.upper()] = names
    return names


def _through_declared_variable(stmt: Statement, names: list[str]) -> list[str]:
    """A DECLARE publishes ONE thing: the variable, whatever fed it.

    ``DECLARE cutoff DATE DEFAULT (SELECT MAX(cm13) ...)`` has no select list
    the projection walk could read -- MAX(cm13) is named nothing at all -- so
    the column came out still called cm13 and the statement below, which reads
    ``cutoff``, matched nothing.

    A loop's row variable is NOT this shape: it carries a whole row, its column
    names survive, and the walk above already gets them right.
    """
    if not stmt.script_var or not isinstance(stmt.expr, (exp.Declare, exp.Set)):
        return names
    return [stmt.script_var]


def _through_insert_columns(stmt: Statement, names: list[str]) -> list[str]:
    """Rename by position, the way ``INSERT INTO t (a, b) SELECT x, y`` does.

    The load statement at the heart of every foundation file in this pipeline is
    a TRUNCATE followed by an INSERT with the target's whole column list written
    out, and the SELECT under it hands over values by position, not by name. So
    the name the column carries downstream is the one in the INSERT's list -- and
    following the SELECT's name instead walked off the end of the chain.

    Only done when the two lists are plainly the same length and no star is in
    the way. Where the arity cannot be checked, the name is left as it was
    rather than guessed at.
    """
    if not isinstance(stmt.expr, exp.Insert) or stmt.select is None:
        return names
    schema = stmt.expr.this
    if not isinstance(schema, exp.Schema):
        return names
    targets = [c.name for c in schema.expressions if getattr(c, "name", "")]
    if not targets:
        return names
    positions: list[str] = []
    for e in stmt.select.expressions:
        if _is_star(e):
            return names                      # arity unknown; nothing to line up
        positions.append(e.alias if isinstance(e, exp.Alias)
                         else e.name if isinstance(e, exp.Column) else "")
    if len(positions) != len(targets):
        return names
    wanted = {n.upper() for n in names}
    mapped = [targets[i] for i, p in enumerate(positions) if p and p.upper() in wanted]
    return _dedupe(mapped) if mapped else names


def _through_create_columns(stmt: Statement, names: list[str]) -> list[str]:
    """Rename by position, the way ``CREATE VIEW v(a, b) AS SELECT x, y`` does.

    BigQuery lets a view, a materialized view or a CTAS pin its own output
    column names in the CREATE line, and it is the ordinary way a team publishes
    friendly names over cryptic warehouse codes. The list was thrown away, which
    went wrong in both directions at once: the chain stopped at the view, and a
    downstream table reading the OLD name was reported as a confident break --
    when after the rename that name is not a column of the view at all.

    Same care as the INSERT version: only when the two lists are plainly the
    same length and no star is in the way. Where the arity cannot be checked the
    name is left alone rather than guessed at.
    """
    if not isinstance(stmt.expr, exp.Create) or stmt.select is None:
        return names
    schema = stmt.expr.this
    if not isinstance(schema, exp.Schema):
        return names
    targets: list[str] = []
    for c in schema.expressions:
        # A CTAS column list may carry types -- (cid STRING, mkt STRING) -- and
        # a view's does not. Both give the name the same way.
        name = getattr(c, "name", "") or (c.this.name if getattr(c, "this", None) is not None
                                          and hasattr(c.this, "name") else "")
        if not name:
            return names
        targets.append(name)
    if not targets:
        return names
    positions: list[str] = []
    for e in stmt.select.expressions:
        if _is_star(e):
            return names                      # arity unknown; nothing to line up
        positions.append(e.alias if isinstance(e, exp.Alias)
                         else e.name if isinstance(e, exp.Column) else "")
    if len(positions) != len(targets):
        return names
    wanted = {n.upper() for n in names}
    mapped = [targets[i] for i, p in enumerate(positions) if p and p.upper() in wanted]
    return _dedupe(mapped) if mapped else names


def _through_merge_columns(stmt: Statement, names: list[str]) -> list[str]:
    """The names a MERGE writes this column into the published table under.

    ``WHEN MATCHED THEN UPDATE SET t.market = s.cm13`` publishes cm13 as market,
    and ``WHEN NOT MATCHED THEN INSERT (pub_id, market) VALUES (s.pub_id, s.cm13)``
    renames by position exactly as a plain INSERT does. Following the source's
    own name instead walked straight off the end of the chain at the one
    statement that loads the table everybody downstream reads.

    Only done where the two lists are plainly the same length. Where the arity
    cannot be checked the name is left as it was rather than guessed at.
    """
    if not isinstance(stmt.expr, exp.Merge):
        return names
    wanted = {n.upper() for n in names}
    mapped: list[str] = []

    def carries(value: exp.Expression | None) -> bool:
        return value is not None and any(c.name.upper() in wanted
                                         for c in value.find_all(exp.Column))

    for when in merge_whens(stmt.expr):
        then = when.args.get("then")
        if isinstance(then, exp.Update):
            for setter in then.args.get("expressions") or []:
                if isinstance(setter, exp.EQ) and isinstance(setter.this, exp.Column)                         and carries(setter.expression):
                    mapped.append(setter.this.name)
        elif isinstance(then, exp.Insert):
            into = then.this
            values = then.args.get("expression")
            if not isinstance(into, exp.Tuple) or not isinstance(values, exp.Tuple):
                continue
            targets = [c.name for c in into.expressions]
            if len(targets) != len(values.expressions):
                continue
            for target, value in zip(targets, values.expressions):
                if target and carries(value):
                    mapped.append(target)
    return _dedupe(mapped) if mapped else names


# ── PIVOT and UNPIVOT ──────────────────────────────────────────────────────
# Both fold a column away and build differently-named ones out of it, and both
# NAME the column while doing it -- so the statement itself fails on the day the
# column goes. Neither was read at all, and each failed in its own direction.
#
# UNPIVOT was the worse of the two, and the only case in the whole suite that
# hedges DOWNWARDS on a statement that hard-fails::
#
#     CREATE OR REPLACE TABLE s1 AS SELECT * FROM customer_demographics
#     UNPIVOT (val FOR metric IN (cm13, other_col));
#
# read as a plain SELECT *, so the answer was `risk: low`, `breaking: false`,
# and the sentence "Nothing here fails on the day of the change" -- printed
# about a statement whose UNPIVOT list stops being valid SQL.
#
# PIVOT failed the other way: the columns it builds are `total_Q1`, `total_Q2`,
# worked out from the aggregate's alias and each IN value. Nothing derived them,
# so the trail was declared finished one hop early with the note "Last table in
# the chain", and the published table reading `total_Q1` was never named.
#
# Both column lists are facts written in the statement, not guesses. sqlglot
# works the PIVOT output names out itself; where it does not, nothing here
# invents them.
def _pivots_over(sel: exp.Select) -> list[exp.Expression]:
    """Every PIVOT or UNPIVOT applied to what this SELECT reads."""
    out: list[exp.Expression] = []
    holders: list[exp.Expression | None] = []
    frm = from_of(sel)
    if frm is not None:
        holders.append(frm.this)
    for j in sel.args.get("joins") or []:
        holders.append(j.args.get("this"))
    for node in holders:
        if node is not None:
            out.extend(node.args.get("pivots") or [])
    return out


def _pivot_consumes(pivot: exp.Expression) -> set[str]:
    """The columns this PIVOT or UNPIVOT names, upper case.

    Named means the statement stops being valid SQL if one of them goes -- an
    UNPIVOT's IN list and a PIVOT's aggregate and FOR column alike.
    """
    named: set[str] = set()
    for field_node in pivot_fields(pivot):
        for c in field_node.find_all(exp.Column):
            named.add(c.name.upper())
    if not is_unpivot(pivot):
        # PIVOT: the aggregates are over real columns of the table underneath.
        # An UNPIVOT's ``expressions`` are the NEW names it invents, not columns
        # it reads, which is why this only applies one way round.
        for e in pivot.expressions:
            for c in e.find_all(exp.Column):
                named.add(c.name.upper())
    return named


def _pivot_outputs(pivot: exp.Expression) -> list[str]:
    """The columns this PIVOT or UNPIVOT builds, or [] if they cannot be known."""
    if not is_unpivot(pivot):
        return pivot_columns(pivot)
    out: list[str] = []
    # UNPIVOT (val FOR metric IN (...)) -- the values land in ``val`` and the
    # column's own NAME lands in ``metric``. Both are followed: renaming the
    # column changes what is written into the name column just as surely.
    for e in pivot.expressions:
        out.extend(i.name for i in e.find_all(exp.Identifier))
        if not list(e.find_all(exp.Identifier)) and getattr(e, "name", ""):
            out.append(e.name)
    for field_node in pivot_fields(pivot):
        this = field_node.args.get("this") if hasattr(field_node, "args") else None
        if this is not None and getattr(this, "name", ""):
            out.append(this.name)
    return _dedupe([n for n in out if n])


# Where a nested SELECT can sit that is NOT a source of rows for the query
# around it: in the select list, or inside a WHERE, HAVING, QUALIFY, GROUP BY or
# ORDER BY. A SELECT in one of those places is a VALUE -- one number, one list to
# test against -- and the names inside it are its own business.
#
#     SELECT o.k,
#            (SELECT MAX(d.cm13) AS c_alias FROM customer_demographics d
#             WHERE d.k = o.k) AS peak_cm
#     FROM other_source o
#
# Measured before this: the statement's output name for cm13 came back as
# ``c_alias`` -- a name that exists only inside the brackets and appears on no
# table anywhere. The real name is ``peak_cm``, which is what the next table
# reads, so the chain went cold one hop early and reported no production impact.
# The mirror is just as bad: ``WHERE k IN (SELECT cm13 AS c_alias FROM ...)``
# INVENTED a column called c_alias on the table being built.
#
# A subquery in FROM or JOIN, or a CTE, really does hand its columns to the query
# around it, and its renames really do survive. Those are untouched.
_VALUE_POSITIONS = {"expressions", "where", "having", "qualify", "group", "order", "limit"}


# SELECT AS VALUE STRUCT(k AS k, cm13 AS code) FROM customer_demographics
#
# BigQuery's way of writing a table whose columns are named in one place. AS
# VALUE dissolves the wrapper, so the table this builds has columns k and code
# -- there is no column called "struct" and no struct on the table at all.
#
# Measured before this: the select list held ONE expression, a Struct with no
# alias, so the statement published nothing under any name. cm13 was carried on
# under its own name, the next table reads "code", and the chain went cold one
# hop early with a clean "no impact".
def _select_list(sel: exp.Select) -> list[exp.Expression]:
    """The expressions this SELECT publishes, with AS VALUE STRUCT unwrapped."""
    items = sel.expressions
    if str(sel.args.get("kind") or "").upper() != "VALUE" or len(items) != 1:
        return items
    struct = items[0]
    if isinstance(struct, exp.Alias):
        struct = struct.this
    if not isinstance(struct, exp.Struct):
        return items
    # PropertyEQ is "name: value" -- sqlglot's shape for STRUCT(x AS name).
    out: list[exp.Expression] = []
    for field in struct.expressions:
        if isinstance(field, exp.PropertyEQ):
            out.append(exp.alias_(field.expression.copy(), field.this.name))
        elif isinstance(field, (exp.Alias, exp.Column)):
            out.append(field)
    return out or items


# How deep a STRUCT inside a STRUCT is followed. One level covers everything
# hand-written; the cap is only here so a generated nest cannot run away.
MAX_STRUCT_DEPTH = 3


def _struct_fields(node: exp.Expression, under: str,
                   depth: int = 0) -> list[tuple[str, str]]:
    """(column it came from, dotted name it becomes) for a STRUCT built here.

    ``SELECT k, STRUCT(cm13 AS code, seg AS segment) AS payload`` builds ONE
    column called payload, and the table really does have only that column --
    ``SELECT code FROM ...`` downstream is an error, and saying otherwise would
    invent columns that are not there. But ``payload.code`` IS how that field is
    read, and following the struct only under "payload" ended the trail at the
    wrapper. Measured before this: the chain stopped at the struct while
    ``payload.code`` was both selected AND filtered on one hop later, and the
    scan came back with no production table at all.

    So the field is published under its DOTTED name, never its bare one. That is
    the name the next statement actually writes, and it cannot collide with a
    real column called ``code`` on some other table.

    ``SELECT AS VALUE STRUCT`` is the other spelling and is unwrapped earlier,
    in _select_list, because AS VALUE dissolves the wrapper outright. This one
    keeps it, so the field name is carried ALONGSIDE the wrapper's own name
    rather than instead of it -- a statement downstream that reads ``payload``
    whole is still followed.
    """
    out: list[tuple[str, str]] = []
    if not isinstance(node, exp.Struct) or depth >= MAX_STRUCT_DEPTH:
        return out
    for item in node.expressions:
        if isinstance(item, exp.PropertyEQ):        # STRUCT(x AS name)
            made, value = item.this.name, item.expression
        elif isinstance(item, exp.Alias):
            made, value = item.alias, item.this
        elif isinstance(item, exp.Column):          # STRUCT(cm13) -- named after itself
            made, value = item.name, item
        else:
            continue
        if not made:
            continue
        path = f"{under}.{made}"
        for c in value.find_all(exp.Column):
            out.append((c.name.upper(), path))
        out.extend(_struct_fields(value, path, depth + 1))
    return out


def _feeds_its_parent(sel: exp.Select) -> bool:
    """Does this SELECT hand its columns to the query around it?"""
    node = sel
    while node.parent is not None and not isinstance(node.parent, exp.Select):
        # A JOIN has two halves and they are opposite. Its SOURCE really does
        # hand its columns over -- that is what a joined subquery is. Its ON
        # condition is a value, exactly like a WHERE, and the arg_key of the
        # whole join is "joins" either way, so walking straight past this
        # counted the condition as a source.
        #
        #     ... LEFT JOIN ref_bands r
        #           ON r.k = c.k
        #          AND c.cm13 IN (SELECT cm13 AS band_code FROM allowed_bands)
        #
        # Measured before this: the statement's output name for cm13 came back
        # as band_code -- a name that exists only inside that condition and is a
        # column of no table anywhere -- so the next table, which reads plain
        # cm13, was never reached and the scan reported no production impact.
        if node.arg_key == "on" and isinstance(node.parent, exp.Join):
            return False
        node = node.parent
    if node.parent is None:
        return True                            # the statement's own SELECT
    return node.arg_key not in _VALUE_POSITIONS


def _select_depth(sel: exp.Select) -> int:
    """How many SELECTs this one is nested inside."""
    depth = 0
    node = sel.parent
    while node is not None:
        if isinstance(node, exp.Select):
            depth += 1
        node = node.parent
    return depth


# ── the names a UNION publishes its branches under ─────────────────────────
# SQL takes a set operation's output column names from the branch written
# FIRST, and applies them to every other branch BY POSITION. The second branch's
# own names are never published at all::
#
#     SELECT id, other_col AS market FROM legacy_demographics
#     UNION ALL
#     SELECT id, cm13          FROM customer_demographics
#
# builds a table whose columns are ``id`` and ``market``. Nothing downstream can
# read ``cm13`` from it, because there is no such column.
#
# The projection walk groups the two branches together -- they sit side by side,
# at the same depth -- and merged their select lists into one map, so ``cm13``
# came out still called ``cm13``. The next statement reads ``market``, matched
# nothing, and the trail ended at the staging table: `prod []`, no production
# table affected, no gap reported anywhere. Which of the two branches the traced
# column happens to be written in decided whether a real break was found -- and
# a current table UNION'd with an archive one, written in whichever order, is
# how a large part of a staging layer is built.
#
# Only done when the branches are plainly the same width and no star is in the
# way, the same care taken over INSERT and CREATE column lists. Where the arity
# cannot be checked nothing is lined up, because a name put on the wrong column
# is worse than a name not put on at all.
def _union_position_names(stmt: Statement) -> dict[int, list[str]]:
    """For each non-first branch of a set operation: its output names, in order.

    Keyed by ``id()`` of the branch's own node, which is what the projection
    walk has in hand. The first branch is left out -- its own names ARE the
    output names, and it is already read correctly.
    """
    if stmt.expr is None:
        return {}
    out: dict[int, list[str]] = {}
    for node in stmt.expr.find_all(SET_OPERATION):
        branches = set_branches(node)
        if len(branches) < 2:
            continue
        names = query_output_names(node)
        if not names:
            continue
        for branch in branches[1:]:
            # A star carries an unknown number of columns, so no position in
            # this branch can be lined up with a position in the first.
            selects = _select_list(branch) if isinstance(branch, exp.Select) else []
            if not selects or any(_is_star(e) for e in selects):
                continue
            if len(selects) != len(names):
                continue
            out[id(branch)] = list(names)
    return out


def _projections(stmt: Statement) -> list[tuple[dict, dict, bool]]:
    """For each level of SELECT, inner to outer: what each column leaves as.

    Built in one pass over the statement instead of once per column asked about.
    ``direct`` is the column carried through or plainly renamed; ``derived`` is
    the column reshaped into something else; the flag says a ``SELECT *`` is
    carrying every remaining name through untouched.

    Grouped by how deeply nested each SELECT is, which is what makes a UNION
    come out right. The two halves of a union are side by side, not one inside
    the other, and treating the second as if it wrapped the first fed the wrong
    map into the next step -- so a column renamed in the first half of
    ``..._BCA_UNION`` was followed under the second half's name and the chain
    went cold. SQL takes a union's output names from its FIRST branch, and so
    does this: the branches are read in the order they are written.
    """
    if stmt._projected is not None:
        return stmt._projected
    selects = list(stmt.expr.find_all(exp.Select)) if stmt.expr is not None else []
    by_depth: dict[int, list[exp.Select]] = {}
    for sel in selects:
        # A SELECT written as a value rather than as a source of rows never
        # names an output of the statement around it. See _feeds_its_parent.
        if not _feeds_its_parent(sel):
            continue
        by_depth.setdefault(_select_depth(sel), []).append(sel)

    # See _union_position_names. Worked out once for the whole statement.
    union_names = _union_position_names(stmt)

    out: list[tuple[dict, dict, bool, set]] = []
    for depth in sorted(by_depth, reverse=True):            # innermost first
        direct: dict[str, list[str]] = {}
        derived: dict[str, list[str]] = {}
        dropped: set[str] = set()
        passthrough = False
        # One vote per star, so that a column is only treated as dropped when
        # EVERY star at this level drops it. See the note below the loop.
        stars = 0
        star_drops: dict[str, int] = {}
        for sel in by_depth[depth]:
            # PIVOT and UNPIVOT happen to what this SELECT reads, before its own
            # select list is applied, and they rename by rule rather than with an
            # AS. Without this the trail ended one hop early on every PIVOT and
            # went on carrying a name that no longer exists on every UNPIVOT.
            for pivot in _pivots_over(sel):
                eaten = _pivot_consumes(pivot)
                built = _pivot_outputs(pivot)
                for name in eaten:
                    dropped.add(name)
                    for made in built:
                        derived.setdefault(name, []).append(made)
            # A branch of a UNION publishes under the FIRST branch's names, by
            # position. See _union_position_names.
            published = union_names.get(id(sel), [])
            for at, e in enumerate(_select_list(sel)):
                if published:
                    # The name this position really leaves under. Its own name
                    # is kept too: it reaches nothing downstream, because no
                    # such column exists on the table -- but keeping it means a
                    # miscounted branch costs a spare row rather than a lost
                    # chain, which is the trade this tool always makes.
                    under = published[at]
                    for c in e.find_all(exp.Column):
                        direct.setdefault(c.name.upper(), []).append(under)
                        if c.table:
                            direct.setdefault(
                                f"{c.table}.{c.name}".upper(), []).append(under)
                if _is_star(e):
                    passthrough = True
                    star = _star_of(e)
                    stars += 1
                    mine: set[str] = set()
                    for c in star_except(star):
                        mine.add(getattr(c, "name", "").upper())
                    # RENAME(cm13 AS cm13_new) and REPLACE(UPPER(cm13) AS cm13)
                    # both change what leaves under which name, so a star is not
                    # always a plain pass-through.
                    for a in star.args.get("rename") or []:
                        if isinstance(a, exp.Alias) and isinstance(a.this, exp.Column):
                            mine.add(a.this.name.upper())
                            direct.setdefault(a.this.name.upper(), []).append(a.alias)
                    for a in star_replace(star):
                        if isinstance(a, exp.Alias):
                            # The output column of that name now holds the
                            # replacement's value, so the ORIGINAL column of
                            # that name reaches nothing past here. Exactly what
                            # EXCEPT does, plus a value put in its place -- and
                            # without this the star went on carrying it.
                            mine.add(a.alias.upper())
                            for c in a.find_all(exp.Column):
                                derived.setdefault(c.name.upper(), []).append(a.alias)
                    for name in mine:
                        star_drops[name] = star_drops.get(name, 0) + 1
                elif isinstance(e, exp.Alias):
                    inner = e.this
                    if isinstance(inner, exp.Column):
                        direct.setdefault(inner.name.upper(), []).append(e.alias)
                        # ``payload.code AS customer_code`` also has to answer
                        # to the dotted name, because that is what a STRUCT
                        # field is carried under. See _struct_fields.
                        if inner.table:
                            direct.setdefault(
                                f"{inner.table}.{inner.name}".upper(), []
                            ).append(e.alias)
                    else:
                        # STRUCT(cm13 AS code) AS payload publishes payload.code,
                        # and the next table reads it as payload.code -- whose
                        # column name is "code". Following only "payload" ended
                        # the trail at the struct. See _struct_fields.
                        for came_from, made in _struct_fields(inner, e.alias):
                            derived.setdefault(came_from, []).append(made)
                        for c in e.find_all(exp.Column):
                            derived.setdefault(c.name.upper(), []).append(e.alias)
                elif isinstance(e, exp.Column):
                    direct.setdefault(e.name.upper(), []).append(e.name)
        # A star only drops a column when EVERY star at this level drops it.
        # The CTEs of one WITH are all at the same depth and usually read
        # DIFFERENT tables::
        #
        #     WITH cust AS (SELECT * FROM customer_demographics),
        #          hits AS (SELECT * EXCEPT (cm13) FROM web_events)
        #     SELECT cust.*, hits.url FROM cust JOIN hits USING (k)
        #
        # That EXCEPT belongs to ``hits``, which never reads the scanned table
        # at all. Applied to the whole level it deleted the column arriving
        # through ``cust.*``, the trail died inside the statement, and a change
        # that really does break the published table came back "no impact".
        # Which star a column flows through is not knowable from the select
        # list alone, so this keeps it whenever any star could still carry it --
        # a spare row rather than a lost chain.
        if stars:
            dropped |= {n for n, votes in star_drops.items() if votes == stars}
        out.append((direct, derived, passthrough, dropped))
    stmt._projected = out
    return out


def _dedupe(names: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for n in names:
        key = n.upper()
        if key not in seen:
            seen.add(key)
            out.append(n)
    return out


def output_name(stmt: Statement, column: str) -> str:
    """The one name to show on screen for this column. See output_names.

    A statement can publish the column under no name at all -- SELECT * EXCEPT
    drops it -- and the row on screen still has to say which column it is about,
    so the name it arrived under is what gets shown.
    """
    names = output_names(stmt, column)
    return names[0] if names else column


def usages_of(stmt: Statement, column: str, table: str = "") -> list[Usage]:
    """Every way `column` is used by this statement, across all its subqueries.

    ``table`` is the table the column is being traced from. Given it, a column
    the statement plainly attributes to some other table is not counted -- which
    matters enormously in a warehouse where the same three key columns are in
    nearly every table and so on both sides of nearly every join. Without a
    table this behaves as it always did and counts every match.
    """
    if stmt.expr is None:
        return []
    # An ALTER names its column outright, in one place, and has no SELECT for
    # the walk below to look in. See _alter_actions.
    action = _alter_actions(stmt.expr).get(column.upper())
    if action is not None:
        kind, new_name = action
        return [Usage(kind=kind, column=column,
                      alias=new_name or column, detail=new_name)]
    found: list[Usage] = []
    alias_for_column = output_name(stmt, column)
    sources = _sources_of(stmt) if table else {}
    ctes = _cte_names(stmt.expr) if table else set()

    # A name Ripple put back by hand because the parser read it as a built-in
    # function. The usage is real; whether the writer meant the column or the
    # function is not knowable from the file, so it is never asserted.
    a_guess = column.upper() in stmt.guessed_columns

    def owned(node: exp.Expression | None) -> tuple[list[exp.Column], bool]:
        """This table's references to the column, and whether the SQL said so."""
        cols = _cols_named(node, column)
        if not table or not cols:
            return cols, not (a_guess and cols)
        keep: list[exp.Column] = []
        certain = True
        for c in cols:
            verdict = _belongs_to(c, stmt, table, sources, ctes)
            if verdict == "no":
                continue                 # plainly another table's column
            if verdict == "unknown":
                certain = False          # kept, and marked rather than asserted
            keep.append(c)
        return keep, certain and not a_guess

    # 0. How the table it builds is laid out: PARTITION BY and CLUSTER BY.
    #
    # These sit on the CREATE line, outside the SELECT, so nothing else in this
    # function could ever see them. Measured before this: a table partitioned by
    # the very column being decommissioned returned NO usages at all, and the
    # whole chain came back `risk low, groups 0, couldNotRead 0`.
    #
    # It is not a column of the table being built -- so no chain follows from it
    # -- but the name is written down on the CREATE line, so the day the column
    # goes this statement stops compiling and the table stops being built. Every
    # published table underneath it then quietly serves data that has stopped
    # being refreshed. That is what "stops being refreshed" exists to report,
    # and this is what feeds it.
    props = stmt.expr.args.get("properties") if isinstance(stmt.expr, exp.Create) else None
    for prop in (props.expressions if props is not None else []):
        which = type(prop).__name__
        if "Partition" not in which and "Cluster" not in which:
            continue
        cols, sure = owned(prop)
        # PARTITION BY cm13 with nothing round it parses as a bare identifier
        # rather than a column, so the search above finds nothing.
        named = bool(cols) or any(i.name.upper() == column.upper()
                                  for i in prop.find_all(exp.Identifier))
        if named:
            found.append(Usage(kind="layout", column=column, alias=alias_for_column,
                               detail="CLUSTER BY" if "Cluster" in which else "PARTITION BY",
                               certain=sure))

    # A DELETE or an UPDATE has a WHERE clause and no SELECT at all. Requiring a
    # SELECT made both invisible, so "DELETE FROM stage WHERE market_code = 'US'"
    # -- which stops working the day market_code goes, and silently stops pruning
    # the table -- was reported as no usage whatsoever.
    if isinstance(stmt.expr, (exp.Delete, exp.Update)):
        cols, sure = owned(stmt.expr.args.get("where"))
        for c in cols:
            found.append(Usage(kind="filter", column=column, alias=alias_for_column,
                               detail=_literal_beside(stmt.expr, c), certain=sure))
        if isinstance(stmt.expr, exp.Update):
            for e in stmt.expr.args.get("expressions") or []:
                cols, sure = owned(e)
                if cols:
                    found.append(Usage(kind="transform", column=column,
                                       alias=alias_for_column, detail="SET", certain=sure))
        if not found:
            cols, sure = owned(stmt.expr)
            if cols:
                found.append(Usage(kind="select", column=column, alias=alias_for_column,
                                   certain=sure))

    # A MERGE is how a published table is normally loaded on BigQuery, Snowflake
    # and Databricks. When USING names a table directly the statement has no
    # SELECT of its own, so every check below was skipped and Ripple answered
    # "the name appears, but no lineage to a production table" -- its single most
    # reassuring sentence, printed about the very statement that loads the table.
    if isinstance(stmt.expr, exp.Merge):
        cols, sure = owned(stmt.expr.args.get("on"))
        if cols:
            found.append(Usage(kind="join_key", column=column, alias=alias_for_column,
                               certain=sure))
        for when in merge_whens(stmt.expr):
            # WHEN MATCHED AND s.cm13 = 'DEAD' THEN DELETE. The condition here
            # decides which rows of a published table get deleted or updated,
            # and it is often the only place in the whole statement the column
            # is named at all.
            cols, sure = owned(when.args.get("condition"))
            for c in cols:
                found.append(Usage(kind="filter", column=column, alias=alias_for_column,
                                   detail=_literal_beside(when, c), certain=sure))
            then = when.args.get("then")
            if isinstance(then, exp.Update):
                # Only the right-hand side. ``SET t.market = s.cm13`` reads
                # s.cm13 and writes t.market, and reading the whole assignment
                # would report the target's own column as a usage of the source.
                for setter in then.args.get("expressions") or []:
                    value = setter.args.get("expression") if isinstance(setter, exp.EQ) else setter
                    cols, sure = owned(value)
                    if cols:
                        found.append(Usage(kind="select", column=column,
                                           alias=alias_for_column, certain=sure))
            elif isinstance(then, exp.Insert):
                cols, sure = owned(then.args.get("expression"))
                if cols:
                    found.append(Usage(kind="select", column=column,
                                       alias=alias_for_column, certain=sure))

    # INSERT ... VALUES has no SELECT anywhere in it, so every check below was
    # skipped and the statement recorded no usage of anything. That is exactly
    # how a FOR loop's body is written -- the values are the loop row's fields --
    # and it is the half of the statement that names the published table::
    #
    #     FOR rec IN (SELECT id, cm13 AS seg FROM customer_demographics) DO
    #       INSERT INTO final_published (id, seg) VALUES (rec.id, rec.seg);
    #
    # Measured before this: groups [], while the finding's own text said the
    # column went "into the next table" and named no next table at all.
    if isinstance(stmt.expr, exp.Insert):
        values = stmt.expr.find(exp.Values)
        if values is not None:
            cols, sure = owned(values)
            if cols:
                found.append(Usage(kind="select", column=column,
                                   alias=alias_for_column, certain=sure))

    if stmt.select is None:
        return _best_of(found)

    for sel in stmt.expr.find_all(exp.Select):
        # 1. the select list
        for e in sel.expressions:
            # A star is not a column reference, and the names hanging off one --
            # EXCEPT(cm13), RENAME(cm13 AS x) -- are not usages of a column in a
            # select list. Reading them as ordinary usages made
            # "SELECT * EXCEPT(cm13)" report cm13 as carried onward, which is
            # the exact opposite of what that statement does with it. The star
            # is handled properly at the bottom of this function.
            if _is_star(e):
                for r in star_replace(_star_of(e)):
                    # REPLACE(UPPER(cm13) AS cm13) genuinely reshapes the value.
                    cols, sure = owned(r)
                    if cols:
                        found.append(Usage(kind="transform", column=column,
                                           alias=alias_for_column, detail="REPLACE",
                                           certain=sure))
                    # SELECT * REPLACE(legacy_code AS cm13) names cm13 out loud.
                    # Remove it and this statement fails, exactly as it does
                    # with EXCEPT -- and the column downstream of that name is
                    # fed by legacy_code from here on, not by this one. Ripple
                    # got the right answer for the wrong reason before: the
                    # rename was followed and nothing said the name was written
                    # down here, so the row read `breaking: false`.
                    if isinstance(r, exp.Alias) and r.alias.upper() == column.upper():
                        found.append(Usage(kind="excluded", column=column,
                                           alias=alias_for_column, detail="REPLACE"))
                continue
            cols, sure = owned(e)
            if not cols:
                continue
            inner = e.this if isinstance(e, exp.Alias) else e
            if isinstance(inner, exp.Column):
                found.append(Usage(kind="select", column=column, alias=alias_for_column,
                                   certain=sure))
            else:
                fn = inner.__class__.__name__.upper() if inner is not None else ""
                found.append(
                    Usage(kind="transform", column=column, alias=alias_for_column,
                          detail=fn, certain=sure)
                )

        # 2. WHERE / HAVING / QUALIFY
        #
        # QUALIFY is BigQuery's and Snowflake's filter on a window result, and
        # it is where nearly every dedup in this kind of pipeline is written:
        # QUALIFY ROW_NUMBER() OVER (PARTITION BY cm13 ORDER BY ts) = 1. Not
        # reading it meant a column that appears nowhere else in the statement
        # was invisible, and the scan came back with no impact at all.
        for clause_key in ("where", "having", "qualify"):
            clause = sel.args.get(clause_key)
            cols, sure = owned(clause)
            for c in cols:
                found.append(
                    Usage(kind="filter", column=column, alias=alias_for_column,
                          detail=_literal_beside(clause, c), certain=sure)
                )

        # 3. JOIN ... ON
        for j in sel.args.get("joins") or []:
            cols, sure = owned(j.args.get("on"))
            if cols:
                found.append(Usage(kind="join_key", column=column, alias=alias_for_column,
                                   certain=sure))

        # 3b. FROM t, UNNEST(cm13) -- an array column opened out into rows.
        # There is no ON clause here, so the join check above sees nothing, and
        # the column is named nowhere else in the statement.
        for j in sel.args.get("joins") or []:
            node = j.args.get("this")
            if isinstance(node, exp.Unnest):
                cols, sure = owned(node)
                if cols:
                    found.append(Usage(kind="transform", column=column,
                                       alias=alias_for_column, detail="UNNEST",
                                       certain=sure))

        # 4. GROUP BY
        cols, sure = owned(sel.args.get("group"))
        if cols:
            found.append(Usage(kind="aggregation", column=column, alias=alias_for_column,
                               certain=sure))

        # 4b. the statement's own ORDER BY. With a LIMIT under it this decides
        # which rows survive, which is the ranking case; without one it decides
        # the order rows are written in. Either way the name is written down, so
        # removing it stops the statement compiling and the table stops loading.
        cols, sure = owned(sel.args.get("order"))
        if cols:
            found.append(Usage(kind="ranking" if sel.args.get("limit") else "sort",
                               column=column, alias=alias_for_column, certain=sure))

        # 4c. PIVOT and UNPIVOT. The column is named in the statement, so the
        # statement stops being valid SQL the day it goes -- and it leaves under
        # names worked out by rule rather than written with an AS. See
        # _pivots_over. Nothing above finds these: an UNPIVOT's IN list is under
        # the FROM clause, not in any select list, WHERE or JOIN.
        for pivot in _pivots_over(sel):
            if column.upper() not in _pivot_consumes(pivot):
                continue
            found.append(Usage(kind="pivoted", column=column, alias=alias_for_column,
                               detail="UNPIVOT" if is_unpivot(pivot) else "PIVOT"))

    # 5. window ORDER BY -- the ranking case, where removal is silent and awful
    for w in stmt.expr.find_all(exp.Window):
        cols, sure = owned(w.args.get("order"))
        if cols:
            found.append(Usage(kind="ranking", column=column, alias=alias_for_column,
                               certain=sure))
        # PARTITION BY is the other half of a dedup and the half that was never
        # read. The ORDER BY picks the winner; the PARTITION BY says what it
        # wins against. Take the column away and every row falls into one group,
        # so one record survives for the whole table instead of one per key --
        # and nothing anywhere is raised to say so.
        for part in w.args.get("partition_by") or []:
            cols, sure = owned(part)
            if cols:
                found.append(Usage(kind="dedup_key", column=column, alias=alias_for_column,
                                   detail="PARTITION BY", certain=sure))
                break

    # 6. aggregates that pick which row survives
    for agg in list(stmt.expr.find_all(exp.Max)) + list(stmt.expr.find_all(exp.Min)):
        cols, sure = owned(agg)
        if cols:
            found.append(
                Usage(kind="dedup_key", column=column, alias=alias_for_column,
                      detail=agg.__class__.__name__.upper(), certain=sure)
            )

    # 7. SELECT * -- last, because anything written down beats anything inferred.
    #
    # Nothing above can see this: there is no column node to find. The column is
    # carried all the same, and refusing to say so is what turned a change that
    # breaks a published table one hop later into a clean result.
    # A column folded away by a PIVOT or an UNPIVOT is not carried on by the
    # star over it. The pivot is definitive about what happens to that one
    # column, and letting the star speak as well would put "carried through
    # untouched" beside "named here, and this statement fails without it".
    pivoted = any(column.upper() in _pivot_consumes(p)
                  for sel in stmt.expr.find_all(exp.Select)
                  for p in _pivots_over(sel))
    # Same for a column the star REPLACEs by name: the output column of that
    # name is fed by the replacement, so this one is not carried through.
    replaced = any(u.kind == "excluded" and u.detail == "REPLACE" for u in found)
    if table and not pivoted and not replaced:
        if star_excludes(stmt, column, table, sources):
            found.append(Usage(kind="excluded", column=column, alias=alias_for_column))
        elif star_carries(stmt, column, table, sources):
            found.append(Usage(kind="star", column=column, alias=alias_for_column,
                               via_star=True))

    return _best_of(found)


def _best_of(found: list[Usage]) -> list[Usage]:
    """The most informative reading of each kind, most consequential first."""
    seen: dict[str, Usage] = {}
    for u in found:
        if u.kind not in seen:
            seen[u.kind] = u
        # One the SQL was explicit about beats one it was not, and after that
        # the one carrying a detail beats the one that does not.
        elif u.certain and not seen[u.kind].certain:
            seen[u.kind] = u
        elif u.certain == seen[u.kind].certain and u.detail and not seen[u.kind].detail:
            seen[u.kind] = u
    return sorted(
        seen.values(),
        key=lambda u: KIND_PRIORITY.index(u.kind) if u.kind in KIND_PRIORITY else 99,
    )


def primary_usage(usages: list[Usage]) -> Usage | None:
    return usages[0] if usages else None


def mode_of(usages: list[Usage]) -> str:
    """How the value itself travels: unchanged, or reshaped on the way."""
    kinds = {u.kind for u in usages}
    if "transform" in kinds or "dedup_key" in kinds or "aggregation" in kinds:
        return "Transformed"
    return "Direct pull"


# ── pointing at the right line of the real file ────────────────────────────
def locate(f: SourceFile, column: str, kind: str, line_offset: int = 0,
           line_end: int | None = None) -> int:
    """Best guess at the 1-based line where this usage lives.

    Bounded to the statement the finding is about. Without the upper bound a
    finding could be sent to any line of the file that scored better -- and in a
    generated file holding sixty statements, the best-scoring WHERE clause is
    very often in somebody else's statement about somebody else's table.
    """
    pat = re.compile(r"\b" + re.escape(column) + r"\b", re.IGNORECASE)
    markers = KIND_MARKERS.get(kind, ())
    last = len(f.lines) if line_end is None else min(line_end + 1, len(f.lines))

    def best_between(low: int, high: int) -> int | None:
        best, best_score = None, -1
        for i in range(max(1, low + 1), min(high, len(f.lines)) + 1):
            line = f.lines[i - 1]
            if not pat.search(line):
                continue
            up = line.upper()
            score = 1 + sum(2 for m in markers if m in up)
            if score > best_score:
                best, best_score = i, score
        return best

    inside = best_between(line_offset, last)
    if inside is not None:
        return inside
    # Nothing inside the statement matched. That happens where the name only
    # exists after a placeholder was filled in, so the statement is widened
    # rather than the finding being dropped -- but only then.
    anywhere = best_between(0, len(f.lines))
    return anywhere or max(1, line_offset + 1)


def snippet(f: SourceFile, hit_line: int, note: str, before: int = 2, after: int = 2) -> list[dict]:
    """A few lines of real code with the important one marked."""
    lines = f.lines
    start = max(1, hit_line - before)
    end = min(len(lines), hit_line + after)
    out = []
    for n in range(start, end + 1):
        row = {"n": n, "t": lines[n - 1].rstrip()}
        if n == hit_line:
            row["hit"] = note
        out.append(row)
    return out
