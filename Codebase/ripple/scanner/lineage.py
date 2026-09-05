"""Following a column through the pipeline, and saying what it means.

A column rarely keeps its name. MARKET_CODE becomes mc, then mkt_cd, and the
thing that finally breaks is three files away from the one the notification
named. This module walks that chain and groups what it finds under the
production table each chain ends at -- because that is the thing an engineer
actually has to defend.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, replace

from sqlglot import exp

from ..catalog import Catalog, build_catalog
from ..config import Settings, settings as default_settings
from .dialectcompat import merge_whens
from .repo import RepoIndex, unopened_code_types
from .sqlread import (
    ParsedRepo,
    Usage,
    canonical,
    dataset_of,
    is_wildcard,
    reads_metadata,
    same_table,
    wildcard_match,
    mode_of,
    locate,
    output_names,
    short_name,
    snippet,
    suffix_verdict,
    usages_of,
)

# What a given kind of change does to a given kind of usage.
#
# "star" is in none of them, and that is deliberate. A SELECT * does not fail
# when a column disappears -- it quietly builds a narrower table, and the thing
# that breaks is whatever reads the missing column further down. Calling the
# star hop itself breaking would put a red badge on the one row in the chain
# that carries on working.
#
# "pivoted" is in every set but value_change, for the same reason "excluded" is:
# the column is NAMED in the statement, so removing or renaming it stops the SQL
# compiling. A change to its VALUES does not -- an UNPIVOT folds whatever is
# there into rows either way. Reading the type wrong can still break it, because
# every column an UNPIVOT folds together has to share one.
#
# "renamed" and "retyped" are an ALTER TABLE naming the column outright, so they
# fail the same way "select" does. "dropped" is in none of them: an ALTER TABLE
# ... DROP COLUMN of the very column being decommissioned is not broken by the
# change, it IS the change -- and it is worth reporting for exactly that reason.
BREAKS = {
    "removal":      {"filter", "join_key", "ranking", "dedup_key", "transform", "aggregation",
                     "sort", "excluded", "pivoted", "layout", "select", "renamed", "retyped"},
    "rename":       {"filter", "join_key", "ranking", "dedup_key", "transform", "aggregation",
                     "sort", "excluded", "pivoted", "layout", "select", "renamed", "retyped"},
    "value_change": {"filter", "join_key", "transform"},
    "type_change":  {"filter", "join_key", "transform", "pivoted", "layout", "retyped"},
    "unknown":      {"filter", "join_key", "ranking", "dedup_key", "transform", "sort",
                     "pivoted", "layout", "renamed", "retyped"},
}
# Usages with no local fix: the replacement has to come from the upstream team.
NO_LOCAL_FIX = {"ranking", "dedup_key"}

# ── the whole table, not one column of it ──────────────────────────────────
# Sometimes the notice is not about a column at all. The table itself is being
# dropped, renamed, moved or rebuilt, and the question is "what reads it" --
# every statement, every column, and everything built from what they build.
# Followed at the level of tables: which column carries onwards does not matter
# when the table underneath every column is what changes.
#
# Measured before this: a table with no attribute went through the column walk
# with nothing to walk, and came back "no usage found" with a blank where the
# name should have been, in a letter ready to send.
WHOLE_TABLE = "whole table"
# What a given kind of change does to a statement that reads the table.
# Removing or renaming it stops the statement running at all. A change of
# values or types runs; what it produces changes. "unknown" is treated as the
# worse case, and the sentence says the notice did not say.
TABLE_BREAKS = {"removal", "rename", "unknown"}


def _how_table_is_read(stmt, table: str) -> str:
    """"copied", "exported", "joined" or "read": how this statement takes the table."""
    if stmt.whole_copy:
        return "copied"
    if stmt.export_uri:
        return "exported"
    if stmt.expr is not None:
        wanted = short_name(table).upper()
        for join in stmt.expr.find_all(exp.Join):
            t = join.this
            if isinstance(t, exp.Table) and short_name(t.name).upper() == wanted:
                return "joined"
    return "read"


def _table_logic(stmt, role: str, change_type: str) -> tuple[str, str]:
    """The badge on the row, and the note on the marked line, for a whole-table hop."""
    stops = change_type in TABLE_BREAKS
    if role == "copied":
        return (f"Copied whole by {stmt.whole_copy}",
                f"{stmt.whole_copy} of the whole table - every column carried on")
    if role == "exported":
        return ("Exported from this table",
                "Reads this table and writes a file out of the warehouse")
    if role == "joined":
        return ("Joined to this table",
                "Joined here - the statement stops running without this table" if stops
                else "Joined here - whatever changes in the table flows on from this line")
    return ("Reads this table",
            "Reads this table - the statement stops running without it" if stops
            else "Reads this table - whatever changes in it flows on from this line")


def _table_impact_sentence(change_type: str, src: str, tgt: str | None, role: str,
                           copied_by: str = "", feed: str = "", hop: int = 0) -> str:
    """One plain sentence about what this statement does the day the table changes."""
    where = tgt or "the next table"
    reads = (f"copies the whole of {src} with {copied_by}" if role == "copied"
             else f"joins to {src}" if role == "joined"
             else f"reads {src}")
    further = ("" if hop == 0 else
               f" {src} is itself built from the table that is changing, so this is the "
               f"same change one step further down.")
    if feed:
        what = ("Once the table is gone this export fails and the file stops arriving."
                if change_type == "removal" else
                "Once the table is renamed this export fails until the name is changed here."
                if change_type == "rename" else
                "The file changes shape on the next run, with no error anywhere.")
        return (f"This statement {reads} and writes the result to the file delivered to {feed}. "
                f"{what} Whoever reads that file is outside this repository - tell them before "
                f"the change ships.{further}")
    if change_type == "removal":
        return (f"This statement {reads} directly. Once the table is gone it fails outright, so "
                f"{where} stops being built, and everything built from {where} goes stale from "
                f"that day.{further}")
    if change_type == "rename":
        return (f"This statement {reads} by its current name. Once the table is renamed it "
                f"fails outright until the name is changed here, and {where} stops being built "
                f"in the meantime.{further}")
    if change_type == "type_change":
        return (f"This statement {reads} directly, so the changed types arrive here first. "
                f"Anything it filters, joins or casts on those columns can fail, and the rest "
                f"flows into {where} changed.{further}")
    if change_type == "value_change":
        return (f"This statement {reads} directly, so the new values flow straight into {where} "
                f"on the next run. Nothing fails on the day - the data changes.{further}")
    return (f"The notice did not say what changes about the table. This statement {reads} "
            f"directly, so any change to it reaches {where} on the next run - and if the table "
            f"goes, this statement fails outright.{further}")


def _impact_sentence(u: Usage, change_type: str, target: str | None,
                     copied_by: str = "", feed: str = "") -> str:
    tgt = feed and f"the delivery at {feed}" or target or "the next table"
    # An EXPORT DATA writes a file to a bucket. There is no published table to
    # gain or lose a column, which is exactly why the answer used to read "no
    # production table is affected" -- true, and no use to anybody: the file
    # somebody else's job reads every morning changes shape or stops arriving.
    if feed and u.kind not in ("filter", "join_key"):
        return (f"This column is written into the file delivered to {feed}. No table in this "
                f"warehouse gains or loses anything - the delivery does, and whoever reads it "
                f"is outside this repository. Tell them before the change ships.")
    lit = f" '{u.detail}'" if u.kind == "filter" and u.detail else ""
    if u.kind == "star":
        # A whole-table COPY does exactly what a SELECT * does, and is followed
        # the same way -- but saying "SELECT *" about a file that says COPY
        # sends somebody to the line to look for a statement that is not there.
        how = (f"This statement copies the whole table with {copied_by}" if copied_by
               else "This statement takes every column with SELECT *")
        return (f"{how}, so the column is carried into "
                f"{tgt} without ever being named. Nothing here fails on the day of the change - "
                f"{tgt} is simply built without the column, and whatever reads it further down is "
                f"what breaks. Ripple cannot see {tgt}'s column list, so everything past this "
                f"point is worked out rather than read.")
    if u.kind == "excluded":
        if u.detail == "REPLACE":
            return (f"This statement puts another value in this column's place by name - "
                    f"SELECT * REPLACE. The column of that name in {tgt} is fed by the "
                    f"replacement from here on, not by this one, so the trail stops here - and "
                    f"the name is written down, so removing or renaming it makes this statement "
                    f"itself fail.")
        return (f"This statement takes every column EXCEPT this one by name. The column never "
                f"reaches {tgt}, so the trail stops here - but the name is written down, so "
                f"removing or renaming it makes this statement itself fail.")
    if u.kind == "renamed":
        return (f"This file renames the column, in {tgt} itself, to "
                f"{u.detail or u.alias}. Everything downstream of {tgt} reads the new name "
                f"from here on, which is why the trail carries on under it - and the old name "
                f"is written on this line, so the migration has to change with it.")
    if u.kind == "dropped":
        return (f"This file already drops the column from {tgt}, by name. The trail stops here: "
                f"nothing built from {tgt} after this statement runs has the column at all. "
                f"Check whether this migration has already run.")
    if u.kind == "retyped":
        return (f"This file changes the column on {tgt} itself. The name is written on this "
                f"line, so removing or renaming it stops the migration running - and a change "
                f"of type here meets whatever type change you are making.")
    if u.kind == "layout":
        how = u.detail or "PARTITION BY"
        return (f"{tgt} is laid out by this column ({how}). Nothing published gains or loses a "
                f"column when it goes -- but the name is written on the CREATE line, so the "
                f"statement stops compiling, {tgt} stops being built, and everything below it "
                f"quietly serves data that has stopped being refreshed.")
    if u.kind == "pivoted":
        if u.detail == "UNPIVOT":
            return (f"This column is named in an UNPIVOT list. Its values are folded into rows "
                    f"under a new column name, so the column itself does not reach {tgt} - but "
                    f"the name is written down here, so removing or renaming it makes this "
                    f"statement fail outright and {tgt} stops loading.")
        return (f"This column is fed into a PIVOT, which turns its values into columns of "
                f"{tgt} under names worked out from each value. The name is written down here, "
                f"so removing or renaming it makes this statement fail outright.")
    if u.kind == "filter":
        if change_type in ("removal", "rename"):
            return (f"Used in a filter here. Once the column is gone this query fails outright, "
                    f"and {tgt} stops loading.")
        return (f"The code filters on a literal value{lit}. After the change that comparison "
                f"stops matching, so {tgt} quietly loads no rows.")
    if u.kind == "join_key":
        if change_type in ("removal", "rename"):
            return f"Joined on this column. Removing it breaks the join and {tgt} fails to build."
        return ("Joined on the raw value. Unless both sides change on the same day, matching rows "
                "are dropped silently - no error, just fewer rows.")
    if u.kind == "ranking":
        return ("This column is the sort order inside a ranking that picks one row per key. "
                "Without it the choice becomes arbitrary - the wrong record can win, and nothing "
                "is raised to tell you.")
    if u.kind == "dedup_key":
        if u.detail == "PARTITION BY":
            return ("This column is the key the ranking is worked out within - one row is kept "
                    "for each value of it. Take the column away and every row falls into a "
                    f"single group, so {tgt} keeps one record for the whole table instead of "
                    "one per key. Nothing fails on the day; the table is simply wrong.")
        return (f"{u.detail or 'An aggregate'} on this column decides which row survives. "
                f"Without it {tgt} can publish stale records with no error.")
    if u.kind == "sort":
        return (f"The rows are sorted by this column on the way into {tgt}. The name is "
                f"written down here, so removing or renaming it stops this statement running "
                f"at all, and {tgt} stops loading.")
    if u.kind == "transform":
        fn = f" ({u.detail})" if u.detail else ""
        return (f"The value is reshaped here{fn}. A change in its format or length produces wrong "
                f"output that flows straight into {tgt}.")
    if u.kind == "aggregation":
        return ("Grouped on this column, so the group labels move with it. Old and new values will "
                "split the history in two unless the table is rebuilt.")
    return (f"Selected straight through into {tgt}. Nothing here depends on the value, but the "
            f"published column changes with it.")


@dataclass
class Finding:
    source_table: str
    source_column: str
    target_table: str | None
    alias: str | None
    logic: str
    kind: str
    mode: str
    impact: str
    breaking: bool
    no_local_fix: bool
    file: str
    lang: str
    lines: list[dict]
    hop: int
    # The attribute the person actually asked about, which two hops down the
    # chain is no longer the column name on this row. A row saying "mc" is
    # unattributable on a scan of three attributes -- and it is the row somebody
    # has to act on. Not part of what makes two findings the same finding: one
    # usage can be on the path of more than one attribute.
    roots: list[str] = field(default_factory=list, compare=False)
    # Whether the statement said which table this column came from. False means
    # the usage is real and on that line, but the same column name is in more
    # than one table the statement reads and the SQL did not say whose it is.
    # Shown, never dropped -- and never asserted either.
    certain: bool = True
    # This hop is carried by a SELECT *, so the table it builds has no column
    # list Ripple can read. The hop is real; everything past it is inferred.
    via_star: bool = False
    # "" when the file really does say SELECT *; otherwise the word it used to
    # copy a whole table instead - COPY, CLONE, LIKE or RENAME. Carried this far
    # so no screen ever tells somebody the file says SELECT * when it does not.
    copied_by: str = ""
    # "" for a statement written as SQL in the file. Otherwise the words the
    # file used to run it as text -- EXECUTE IMMEDIATE. The statement is read
    # exactly as it will run, so this finding is real; but the line it points at
    # holds a quoted string, and a row that does not say so sends somebody to
    # look for a CREATE that is not written there.
    built_as_text: str = ""
    # "" for an ordinary statement. Otherwise where this EXPORT DATA delivers
    # to. The row sits under "builds no table", which is true of it and does not
    # tell the whole story: Ripple knows exactly where this one goes.
    feed_uri: str = ""
    # How many SELECT * hops are behind this finding, counting this one. Zero
    # means every step to here was written down in the SQL.
    inferred_hops: int = 0
    # The line the statement this finding lives in starts on. Part of what makes
    # two findings the same finding, and the reason is worth writing down: one
    # file very often builds several tables, and the same column of the same
    # source table is filtered on in each of them. Without this the second and
    # third statements were folded into the first, so the row shown under a
    # published table pointed at another statement's lines and named another
    # statement's target -- and the count of usages was quietly short.
    at: int = 0
    # The target table as the reader keyed it, which is not always what goes on
    # screen: a temporary table is fenced to the file that built it, and the
    # fence is stripped for display. Anything that walks ONWARDS from a finding
    # has to use this, or it looks the table up by a name that matches every
    # other file's temporary table of the same name -- which is the merge this
    # fence exists to stop, leaking back in one screen further along.
    target_key: str = field(default="", compare=False)
    # This hop is a SELECT *, and the column list it publishes is written down
    # after all: the table it copies has its columns listed, so the built
    # table's list was filled in from there (catalog.derived), or the built
    # table has a CREATE TABLE of its own. Read, not inferred.
    star_known: bool = False

    def key(self) -> tuple:
        return (self.file, self.at, self.source_table, self.source_column, self.kind)


@dataclass
class ScanResult:
    attributes: list[dict] = field(default_factory=list)
    groups: list[dict] = field(default_factory=list)
    # Chains that end somewhere Ripple has not been told is a table this team
    # publishes. These used to be thrown away, which meant a real, breaking
    # impact could be shown as a clean result purely because the tables are not
    # named _PROD. They are reported, and labelled for what they are.
    reached: list[dict] = field(default_factory=list)
    # Usages in code that builds no table Ripple can name -- a bare SELECT, a
    # view it could not follow. Still real usages of the attribute.
    other: list[dict] = field(default_factory=list)
    graphs: list[dict] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    unreadable: list[dict] = field(default_factory=list)
    # How many of those unreadable files actually mention one of the names being
    # followed. The coverage line used to say "N files mention these names and
    # could not be read" about every file in the repository the parser choked
    # on, which on a clean scan printed "3 files mention these names" directly
    # above a row saying the attribute was named in one file and nowhere else.
    # Those two cannot both be true.
    unreadable_on_topic: int = 0
    mentions_only: list[dict] = field(default_factory=list)
    # Files that were never opened at all, which is a different and worse thing
    # than a file that was read and not understood. A scan over a repository
    # half of which was never opened produces a short finding list and a green
    # tick, and that green tick is the only thing this tool sells.
    held_online: list[str] = field(default_factory=list)
    too_long: list[str] = field(default_factory=list)
    # Tables the chain went through that are built with SELECT *. Their column
    # list is nowhere in the SQL, so every hop past one of them is worked out
    # rather than read. This belongs on the scan result and nowhere else: the
    # repository screen has listed these tables for months, and nothing joined
    # it up to the answer, so a scan said "no impact" while the warning sat on
    # a screen nobody was looking at.
    star_tables: list[dict] = field(default_factory=list)
    # Trails Ripple stopped following because the hop limit was reached, not
    # because the code ran out. Without this the setting gets reported as a fact
    # about the warehouse: "the chain ends at t4, it does not reach production".
    cut_short: list[dict] = field(default_factory=list)
    # Table names this repository uses in more than one dataset, where the SQL
    # being followed did not say which one it meant. Ripple treats them as one
    # table -- losing the chain is the worse mistake -- and says so here, so a
    # finding under one of these names is read as being about either.
    merged_names: list[dict] = field(default_factory=list)
    # Wildcard table names the chain was followed through -- ``events_*``. The
    # SQL never named the table being scanned; it named a whole family of
    # date-sharded tables, and this one falls inside it. The finding is real and
    # the statement really does read this table, but "which shard" is a question
    # the file does not answer, and the person acting on it has to know that.
    wildcard_names: list[dict] = field(default_factory=list)
    # Tables on the trail whose name is nowhere in the file that builds them. A
    # dbt model is a bare SELECT with no CREATE: the table it loads is named
    # after the file, by dbt, at run time. Ripple follows that rule -- without it
    # a dbt repository produced no lineage at all -- and then says so here,
    # because somebody sent to that line to check will not find the table
    # written on it, and a finding they cannot verify is one they will dismiss.
    named_by_file: list[dict] = field(default_factory=list)
    # Statements on the trail that the file runs as text -- EXECUTE IMMEDIATE
    # holding a whole CREATE in a quoted string. Ripple reads the string, so the
    # hop is followed rather than lost; the line it points at is a string, and
    # this card is what says so beside the answer instead of on another screen.
    built_as_text: list[dict] = field(default_factory=list)
    # Files Ripple would have read but did not, because they sit in a folder it
    # is told to skip -- build, dist, target, venv. The count reached the
    # repository screen and nothing else, so a scan of a dbt project (whose
    # target/ folder holds the SQL that actually runs) came back `risk none,
    # prod []` with the reason on a screen nobody was looking at.
    # Tables on the trail that more than one file builds from scratch. Only one
    # of those definitions can be the one that runs, and nothing in the files
    # says which -- so both are followed and both are named. See rebuilt_in.
    two_definitions: list[dict] = field(default_factory=list)
    skipped_in_folders: list[str] = field(default_factory=list)
    skipped_folder_names: list[str] = field(default_factory=list)
    # File types Ripple does not open at all, and how many of each are in the
    # repository: {".ipynb": 12, ".tf": 3}. The repository screen has always
    # listed these. The ANSWER never did -- so a middle hop written in a
    # notebook, or in Terraform, or in a file with no extension at all, produced
    # "the name appears, but no lineage to a production table" with nothing
    # anywhere beside it saying a file had been passed over. Measured on a
    # notebook holding the one statement that built the published table.
    # A caveat may never live on a different screen from the answer it
    # qualifies, so it is carried here and counted as a gap in coverage.
    file_types_unopened: dict = field(default_factory=dict)
    # Published tables that are not built FROM this column, but that stop being
    # refreshed because the statement feeding them stops running on the day of
    # the change. A different kind of impact from the findings above, and it
    # must never be presented as the same one.
    stops_loading: list[dict] = field(default_factory=list)
    # DDL that names a table on the trail, or one of the columns being followed,
    # and carries no column anywhere: a search index, a vector index, a row
    # access policy, an UNDROP. Never lineage -- a dependency somebody has to go
    # and change. Before this the whole statement was invisible: the parser gave
    # up on it, the file landed on the "check by hand" list, and nothing said
    # which table or which column it was about.
    referenced_here: list[dict] = field(default_factory=list)
    # Deliveries out of the warehouse -- EXPORT DATA writing a file to a bucket
    # somebody else's job picks up. An export builds no table, so the trail had
    # nothing to carry the column on to, and the answer read "no production
    # table is affected": true, and useless. The delivery that breaks belongs to
    # another team, and until now it was named on no screen at all.
    feeds: list[dict] = field(default_factory=list)
    # True when the walk that found them hit its own ceiling. A cap nobody is
    # told about reads as "there were only these".
    stops_loading_capped: bool = False
    # Every attribute asked about turned out to be a name Ripple never saw as a
    # column anywhere, and nothing was found. That is not "no impact" -- it is
    # the question not having been answered, and printed as a green tick it is
    # the most convincing wrong answer this tool can give.
    lookup_failed: bool = False
    max_hops: int = 0
    files_scanned: int = 0
    files_matched: int = 0
    risk: str = "none"

    def to_dict(self) -> dict:
        return {
            "attributes": self.attributes,
            "groups": self.groups,
            "reached": self.reached,
            "other": self.other,
            "graphs": self.graphs,
            "unreadable": self.unreadable,
            "mentionsOnly": self.mentions_only,
            "heldOnline": self.held_online,
            "pathTooLong": self.too_long,
            "starTables": self.star_tables,
            "cutShort": self.cut_short,
            "mergedNames": self.merged_names,
            "wildcardNames": self.wildcard_names,
            "namedByFile": self.named_by_file,
            "builtAsText": self.built_as_text,
            "twoDefinitions": self.two_definitions,
            "skippedInFolders": self.skipped_in_folders,
            "skippedFolderNames": self.skipped_folder_names,
            "fileTypesUnopened": [{"ext": k, "count": n} for k, n
                                  in sorted(self.file_types_unopened.items(),
                                            key=lambda kv: (-kv[1], kv[0]))],
            "stopsLoading": self.stops_loading,
            "referencedHere": self.referenced_here,
            "feeds": self.feeds,
            "stopsLoadingCapped": self.stops_loading_capped,
            "maxHops": self.max_hops,
            "filesScanned": self.files_scanned,
            "filesMatched": self.files_matched,
            "risk": self.risk,
            "lookupFailed": self.lookup_failed,
            "coverage": self.coverage(),
            "stats": self.stats(),
        }

    def coverage(self) -> dict:
        """How much of this trail Ripple could actually see.

        "No impact, and I could follow every step of it" and "no impact, and
        three tables on the way were invisible to me" printed identically: one
        three-word badge, computed from nothing but whether a finding was
        breaking. Everything below was already counted and then thrown away.

        Deliberately counts, not a percentage. There is no honest denominator
        for "how much of a trail exists" -- a made-up one would put a precise
        number on a guess, which is the one thing this tool may not do. The
        files ratio IS real, because both halves are files Ripple listed.
        """
        # Each line is written twice, for one and for more than one. Printed
        # plural-only these read "1 findings are on a line" and "1 trails were
        # still going", which is the sort of thing that makes a careful tool
        # look careless on the exact screen where care is what it is selling.
        on_topic = min(self.unreadable_on_topic, len(self.unreadable))
        gaps = [
            (len(self.unreadable),
             "file could not be read" + (
                 f", and it mentions these names" if on_topic else ""),
             "files could not be read" + (
                 f", and {on_topic} of them mention these names" if on_topic else "")),
            (len(self.held_online) + len(self.too_long),
             "file was never opened at all",
             "files were never opened at all"),
            # Written for somebody reading a scan for the first time. "On the
            # trail", "hop limit" and "worked out rather than read" are Ripple's
            # own vocabulary, and this is the list a person reads to decide
            # whether to believe the answer above it.
            # Only the stars whose column list really is nowhere. One filled
            # in from the table it copies was read, and is not a gap.
            (len([s for s in self.star_tables if not s.get("known")]),
             "table the column passes through takes every column at once, so your "
             "code never lists what its columns are called",
             "tables the column passes through take every column at once, so your "
             "code never lists what their columns are called"),
            (len(self.cut_short),
             "trail was still going when Ripple stopped following it",
             "trails were still going when Ripple stopped following them"),
            (len([f for f in self.findings if f.inferred_hops]),
             "finding comes after one of those tables, so Ripple worked the column "
             "name out rather than reading it",
             "findings come after one of those tables, so Ripple worked the column "
             "names out rather than reading them"),
            (len(self.merged_names),
             "name here stands for more than one table, and the SQL does not say which",
             "names here stand for more than one table, and the SQL does not say which"),
            (len([f for f in self.findings if not f.certain]),
             "finding is on a line that did not say which table the column came from",
             "findings are on a line that did not say which table the column came from"),
            (len(self.skipped_in_folders),
             "code file was walked past because of the folder it sits in",
             "code files were walked past because of the folder they sit in"),
            (sum(self.file_types_unopened.values()),
             "file is of a type Ripple does not open, so anything written in "
             "it was never read",
             "files are of a type Ripple does not open, so anything written in "
             "them was never read"),
        ]
        found = [{"count": n, "what": one if n == 1 else many}
                 for n, one, many in gaps if n]
        return {
            "complete": not found,
            "gaps": found,
            # Both halves are files Ripple listed, so this ratio is a fact.
            "filesMatched": self.files_matched,
            "filesUnread": len(self.unreadable),
        }

    def stats(self) -> dict:
        inter = {f.source_table for f in self.findings if f.hop > 0}
        inter |= {f.target_table for f in self.findings if f.target_table}
        prod = {g["prod"] for g in self.groups}
        inter = {t for t in inter if t and t not in prod}
        return {
            "productionTables": len(self.groups),
            "tablesReached": len(self.reached),
            "intermediateTables": len(inter),
            # Counted over the attributes that were actually confirmed, not over
            # every column name a finding touches -- a column renamed twice on
            # the way down is one attribute, and the card says "of those you
            # confirmed", so it has to be true of that number.
            "attributesImpacted": len([a for a in self.attributes if a.get("found")]),
            # How many of the things asked about were whole tables rather than
            # columns. The screen names the count differently when this is set.
            "wholeTables": len([a for a in self.attributes if a.get("whole")]),
            "filesWithImpact": len({f.file for f in self.findings}),
            "breakingUsages": len([f for f in self.findings if f.breaking]),
            "couldNotRead": len(self.unreadable),
            "neverOpened": len(self.held_online) + len(self.too_long),
            # Tables on the trail whose column list is not written down, and
            # findings that sit on the far side of one. Both counts, because
            # "3 tables Ripple could not see inside" and "40 findings that
            # depend on them" are different sizes of the same problem.
            "tablesNotVisible": len([s for s in self.star_tables if not s.get("known")]),
            "inferredFindings": len([f for f in self.findings if f.inferred_hops]),
            "trailsCutShort": len(self.cut_short),
            # Not added to productionTables: nothing about these tables'
            # columns changes, and one number covering two different kinds of
            # impact is a number that means neither.
            "productionStopsLoading": len(self.stops_loading),
            # Kept out of productionTables for the same reason: a file delivered
            # to a bucket is not a published table, and one number covering two
            # different kinds of impact is a number that means neither.
            "feedsBroken": len([f for f in self.feeds if f["breaking"]]),
        }


def _kind_of_node(name: str, cfg: Settings) -> str:
    if cfg.is_production_table(name):
        return "Prod"
    up = name.upper()
    if up.startswith("TEMP") or "_TEMP" in up:
        return "Temp"
    if up.endswith("_ODL") or "_ODL" in up:
        return "ODL"
    return "ETL"


def trace(
    index: RepoIndex,
    parsed: ParsedRepo,
    upstream: list[dict],
    change_type: str = "unknown",
    cfg: Settings | None = None,
    on_progress=None,
    catalog: Catalog | None = None,
) -> ScanResult:
    """upstream is [{"table": "CUSTOMER_DEMOGRAPHICS", "attrs": ["MARKET_CODE"]}].

    ``catalog`` is the one built from this repository, handed in by the
    service so it is not built again per scan. Built here when it is not: it
    is what says whether a SELECT * hop has a column list Ripple can read.

    ``on_progress(done, total, label)`` is called as the chain is followed. It
    is deliberately given no total: how many statements a scan will look at
    depends on what it finds as it goes, and a fraction of a number nobody knows
    is a made-up fraction. The count of what has actually been looked at is a
    real thing to show.
    """
    cfg = cfg or default_settings
    cat = catalog if catalog is not None else build_catalog(parsed)
    res = ScanResult()
    res.max_hops = cfg.max_hops
    res.files_scanned = len(index.files)
    res.unreadable = list(parsed.unreadable)
    res.held_online = list(index.held_online)
    res.too_long = list(index.too_long)
    # Beside the answer, not on another screen. See ScanResult.skipped_in_folders.
    res.skipped_in_folders = list(index.in_skipped_dirs)
    res.skipped_folder_names = list(index.skipped_dir_names)
    # Already counted while the repository was indexed. Carried onto the ANSWER
    # rather than left on the repository screen. See file_types_unopened.
    res.file_types_unopened = unopened_code_types(index.unknown_ext)
    breaks = BREAKS.get(change_type, BREAKS["unknown"])

    # Searched on the table's own name, not on the whole thing somebody typed.
    # "prj.raw_dataset.customer_demographics" appears in the files as a name with
    # placeholders where the project and dataset are, so looking for it in full
    # matches nothing at all -- and "0 files mention this" is the most convincing
    # possible way to say "no impact".
    all_names: list[str] = []
    for u in upstream:
        all_names.append(short_name(u["table"]))
        all_names.extend(u.get("attrs") or [])
        # A date-sharded table is never written by its own name. The file says
        # ``customer_demographics_*``, so searching the text for the shard finds
        # nothing -- and then every honesty list built off that search is empty
        # too, including the one that says "the name is in this file as text".
        all_names.extend(parsed.wildcards_covering(u["table"]))
    matched_files = {m.file for m in index.search(all_names)}
    res.files_matched = len(matched_files)
    attr_names = [a for u in upstream for a in (u.get("attrs") or [])]
    shared, table_count = _tables_carrying(parsed, attr_names)

    graphs: list[dict] = []
    findings_by_key: dict[tuple, Finding] = {}
    looked = [0]                       # statements examined, for the progress line
    # production table -> ordered findings that lead to it
    prod_groups: dict[str, list[Finding]] = {}
    # the same, for chains that end at a table nothing further is built from
    end_groups: dict[str, list[Finding]] = {}
    # tables whose column list is not written down, and where that was found
    star_seen: dict[str, dict] = {}
    cut_seen: dict[tuple, dict] = {}
    merged_seen: dict[str, dict] = {}
    wild_seen: dict[str, dict] = {}
    # Tables a wildcard genuinely produced a finding for. The card says "the
    # usages below are real"; without this it was printed over an empty list.
    wild_confirmed: set[str] = set()
    # tables whose name came from the file path, not from the statement
    file_named_seen: dict[str, dict] = {}
    # tables more than one file builds from scratch
    forked_seen: dict[str, dict] = {}
    # statements the file runs as text -- EXECUTE IMMEDIATE
    text_sql_seen: dict[tuple, dict] = {}
    # deliveries out of the warehouse -- EXPORT DATA
    feed_seen: dict[tuple, dict] = {}
    # Every table the chain actually stood on. Used at the end to look through
    # the statements Ripple could not understand for one that names any of
    # them -- see _opaque_on_the_trail.
    visited: set[str] = set()

    def note_if_wildcard(name: str) -> None:
        """Say when this table was only reached through a wildcard name.

        The SQL did not name this table. It named ``customer_demographics_*``,
        a whole family of date-sharded tables, and the one being scanned falls
        inside it. The usage is real -- that query reads this table on any day
        its suffix is in range -- but the file cannot say which shard, and a
        finding that does not admit that reads as more precise than it is.

        Nothing is said when the person typed the wildcard themselves. They
        already know; a warning on every scan is a warning nobody reads.

        Recorded here, and only PUT ON THE SCREEN if a finding actually came out
        of one of these patterns. The card says "the usages below are real", and
        it was being printed over an empty list: a wildcard in one dataset and a
        shard in another are not the same table -- ``same_table`` rules on the
        dataset and this does not -- so the pattern covered the name, produced
        nothing, and the card contradicted the answer it sat under.
        """
        if is_wildcard(name):
            return
        key = short_name(name).upper()
        if key in wild_seen:
            return
        found = parsed.wildcards_covering_how(name)
        if found:
            wild_seen[key] = {
                "table": short_name(name),
                "patterns": [p for p, _ in found],
                # The family name typed without the separator BigQuery requires.
                # A guess about what somebody meant, and it gets its own line.
                "shorthand": [p for p, how in found if how == "family"],
            }

    def note_if_merged(name: str, matched: list, hop: int) -> None:
        """Say when following this name really did pull in more than one table.

        Reported because it happened, not because it might have. Two tables of
        the same name in two named datasets are kept apart, and nothing is said;
        what gets reported is a match that only held because one side said
        nothing -- ``archive_dataset.cust_stage`` matched by a bare
        ``cust_stage`` somewhere else.

        Ripple always follows those, because missing a chain is far worse than
        showing a row somebody can dismiss by opening the file. What it must not
        do is stay quiet, or the finding reads as a fact about one table when it
        may be about the other.

        Capitals are the same problem wearing a different hat: BigQuery treats
        ccm_Wireless_Enroll and ccm_wireless_enroll as two different tables, and
        Ripple matches them as one.
        """
        key = short_name(name).upper()
        if key in merged_seen:
            return
        spellings = parsed.spellings_for(name)
        if len(spellings) > 1:
            merged_seen[key] = {
                "table": short_name(name), "reason": "capitals",
                "spellings": spellings, "datasets": parsed.datasets_for(name),
            }
            return
        def record() -> None:
            merged_seen[key] = {
                "table": short_name(name), "reason": "dataset",
                "spellings": spellings, "datasets": parsed.datasets_for(name),
            }

        if hop == 0:
            # The first name came from a person, not from the code. Somebody
            # typing "customer_demographics" without its dataset is not an
            # ambiguity in the warehouse, and flagging it would put a warning on
            # every scan ever run. It only matters if the repository really does
            # have that name in more than one dataset.
            if len(parsed.datasets_for(name)) > 1:
                record()
            return
        here = dataset_of(name).upper()
        for stmt in matched:
            for src in stmt.sources:
                if same_table(src, name) and dataset_of(src).upper() != here:
                    record()
                    return

    def show(name: str) -> str:
        """A table name as it should appear on screen. Dataset-qualified only
        where this repository uses the same short name in two datasets."""
        return parsed.display(name)

    for up in upstream:
        # What was typed is what gets shown; what gets followed is the table it
        # names. A project id in front of it is dropped, so a name typed in full
        # still finds the same table the SQL writes with a placeholder there.
        typed = up["table"]
        table = canonical(typed)
        # Only worked out when a lookup actually fails, and then only once for
        # the whole table. It walks every statement in the repository and opens
        # every column of the ones that read this table -- cheap on a scan that
        # needs it, minutes across a repository the size of his on every scan
        # that does not.
        columns_cache: list[list[str]] = []

        def columns_here() -> list[str]:
            if not columns_cache:
                columns_cache.append(_columns_on(parsed, table)[:MAX_COLUMNS_SHOWN])
            return columns_cache[0]

        if up.get("whole"):
            # The table itself is changing. Every statement that reads it is a
            # finding, and every table those statements build is followed the
            # same way, as far as the code goes -- see WHOLE_TABLE.
            branches: list[list[dict]] = []
            end_branches: list[list[dict]] = []
            attr_findings: list[Finding] = []
            attr_cut: list[dict] = []
            readers = [0]

            def walk_table(cur_table: str, hop: int, path: list[dict],
                           chain: list[Finding], seen: set) -> tuple[bool, bool]:
                """Follow the table onwards. Same two answers as walk()."""
                if cfg.max_hops and hop >= cfg.max_hops:
                    entry = cut_seen.setdefault(
                        (cur_table.upper(), WHOLE_TABLE.upper()),
                        {"table": show(cur_table), "attr": WHOLE_TABLE, "hop": hop, "roots": []},
                    )
                    if WHOLE_TABLE not in entry["roots"]:
                        entry["roots"].append(WHOLE_TABLE)
                    if entry not in attr_cut:
                        attr_cut.append(entry)
                    return False, True
                key = cur_table.upper()
                if key in seen:
                    return False, False
                seen = seen | {key}
                recorded = False
                truncated = False
                matched = parsed.reading(cur_table)
                visited.add(short_name(cur_table).upper())
                note_if_merged(cur_table, matched, hop)
                note_if_wildcard(cur_table)

                for stmt in matched:
                    looked[0] += 1
                    if on_progress is not None and looked[0] % 200 == 0:
                        on_progress(looked[0], 0,
                                    f"Following the whole of {short_name(typed)} — "
                                    f"{len(findings_by_key)} usages so far")
                    reads = suffix_verdict(stmt, cur_table)
                    if reads == "excluded":
                        continue
                    how = _how_this_statement_reads(stmt, cur_table)
                    if how:
                        wild_confirmed.add(short_name(cur_table).upper())
                    src = index.get(stmt.file)
                    if src is None:
                        continue
                    if hop == 0:
                        readers[0] += 1
                    role = _how_table_is_read(stmt, cur_table)
                    logic, note = _table_logic(stmt, role, change_type)
                    hit = locate(src, short_name(cur_table), "table", stmt.line_offset, stmt.line_end)
                    tgt_shown = show(stmt.target) if stmt.target else None
                    f = Finding(
                        source_table=show(cur_table),
                        source_column=WHOLE_TABLE,
                        target_table=tgt_shown,
                        alias="",
                        logic=logic,
                        kind="table",
                        mode="Whole table",
                        impact=_table_impact_sentence(change_type, show(cur_table), tgt_shown,
                                                      role, stmt.whole_copy, stmt.export_uri, hop),
                        breaking=change_type in TABLE_BREAKS,
                        no_local_fix=False,
                        file=stmt.file,
                        lang=src.lang,
                        lines=snippet(src, hit, note),
                        hop=hop,
                        certain=reads != "maybe" and how != "family",
                        via_star=False,
                        copied_by=stmt.whole_copy,
                        built_as_text=stmt.built_as_text,
                        feed_uri=stmt.export_uri,
                        inferred_hops=0,
                        at=stmt.line_offset,
                        target_key=stmt.target or "",
                    )
                    findings_by_key.setdefault(f.key(), f)
                    f = findings_by_key[f.key()]
                    if WHOLE_TABLE not in f.roots:
                        f.roots.append(WHOLE_TABLE)
                    if f not in attr_findings:
                        attr_findings.append(f)
                    new_chain = chain + [f]

                    tgt = stmt.target
                    if stmt.export_uri:
                        entry = feed_seen.setdefault(stmt.export_uri, {
                            "uri": stmt.export_uri, "file": stmt.file,
                            "line": stmt.line_offset + 1, "from": show(cur_table),
                            "attrs": [], "breaking": False})
                        if WHOLE_TABLE not in entry["attrs"]:
                            entry["attrs"].append(WHOLE_TABLE)
                        entry["breaking"] = entry["breaking"] or f.breaking
                        recorded = True
                    if not tgt:
                        continue
                    shown = show(tgt)
                    node = {"name": shown, "kind": _kind_of_node(short_name(tgt), cfg),
                            "alias": "", "whole": True}
                    forks = parsed.rebuilt_in(tgt)
                    if forks:
                        node["twoDefinitions"] = True
                        forked_seen.setdefault(shown, {"table": shown, "files": forks})
                    if stmt.built_as_text:
                        node["builtAsText"] = True
                        text_sql_seen.setdefault(
                            (stmt.file, stmt.line_offset),
                            {"table": shown, "file": stmt.file,
                             "line": stmt.line_offset + 1, "how": stmt.built_as_text})
                    if stmt.named_by:
                        node["namedByFile"] = True
                        file_named_seen.setdefault(shown, {
                            "table": shown, "file": stmt.file, "how": stmt.named_by})
                    if cfg.is_production_table(short_name(tgt)):
                        node["prod"] = True
                        branch = path + [node]
                        if branch not in branches:
                            branches.append(branch)
                        _collect(prod_groups, shown, new_chain)
                        recorded = True
                        _, hit_cap = walk_table(tgt, hop + 1, path + [node], new_chain, seen)
                        truncated = truncated or hit_cap
                        continue
                    done, hit_cap = walk_table(tgt, hop + 1, path + [node], new_chain, seen)
                    truncated = truncated or hit_cap
                    if done:
                        recorded = True
                    else:
                        if hit_cap:
                            node["cut"] = True
                        branch = path + [node]
                        if branch not in end_branches:
                            end_branches.append(branch)
                        _collect(end_groups, shown, new_chain)
                        recorded = True
                return recorded, truncated

            walk_table(table, 0, [], [], set())
            branches = _longest_only(branches)
            end_branches = _longest_only(end_branches)
            res.findings.extend([f for f in attr_findings if f not in res.findings])
            # "Nothing reads it" is an answer. "Ripple never met it" is the
            # question not having been asked -- split on whether anything in
            # the repository builds the table, since nothing reads it either.
            wanted = short_name(table).upper()
            built_here = any(s.target and short_name(s.target).upper() == wanted
                             for s in parsed.statements)
            lookup_failed = not attr_findings and not built_here
            if branches or end_branches:
                graphs.append({"attr": WHOLE_TABLE, "table": typed, "whole": True,
                               "branches": branches, "endBranches": end_branches})
            res.attributes.append(
                {
                    "table": typed,
                    "attr": WHOLE_TABLE,
                    "whole": True,
                    "found": len(attr_findings),
                    "files": len({f.file for f in attr_findings}),
                    "mentionedIn": len({m.file for m in index.search([short_name(typed)])}),
                    # Statements that read the table itself, before any hop.
                    "readers": readers[0],
                    "builtHere": built_here,
                    "reachesProduction": bool(branches),
                    "endsAt": sorted({b[-1]["name"] for b in end_branches
                                      if not b[-1].get("cut")}),
                    "cutShortAt": sorted({c["table"] for c in attr_cut}),
                    "notVisible": [],
                    "inferred": 0,
                    "nameInTables": 0,
                    "tablesRead": table_count,
                    "lookupFailed": lookup_failed,
                    "tableColumns": [],
                    "uncertain": len([f for f in attr_findings if not f.certain]),
                }
            )
            continue

        for attr in up.get("attrs") or []:
            branches: list[list[dict]] = []
            end_branches: list[list[dict]] = []
            attr_findings: list[Finding] = []
            attr_cut: list[dict] = []

            def walk(cur_table: str, cur_col: str, hop: int, path: list[dict],
                     chain: list[Finding], seen: set, inferred: int) -> tuple[bool, bool]:
                """Follow the column onwards.

                Returns (anything recorded, the hop limit stopped us). The second
                half is the whole point: without it a trail Ripple gave up on
                looks exactly like a trail that genuinely ended, and the screen
                where somebody decides whether to worry reports a setting as a
                fact about their warehouse.
                """
                # Zero means "until the code runs out" -- see Settings.max_hops.
                # The `seen` set below is what actually guarantees this ends.
                if cfg.max_hops and hop >= cfg.max_hops:
                    entry = cut_seen.setdefault(
                        (cur_table.upper(), cur_col.upper()),
                        {"table": show(cur_table), "attr": cur_col, "hop": hop, "roots": []},
                    )
                    if attr not in entry["roots"]:
                        entry["roots"].append(attr)
                    if entry not in attr_cut:
                        attr_cut.append(entry)
                    return False, True
                key = (cur_table.upper(), cur_col.upper())
                if key in seen:
                    return False, False
                seen = seen | {key}
                recorded = False
                truncated = False
                matched = parsed.reading(cur_table)
                visited.add(short_name(cur_table).upper())
                note_if_merged(cur_table, matched, hop)
                note_if_wildcard(cur_table)

                for stmt in matched:
                    looked[0] += 1
                    if on_progress is not None and looked[0] % 200 == 0:
                        on_progress(looked[0], 0,
                                    f"Following {cur_col} — {len(findings_by_key)} usages so far")
                    us = usages_of(stmt, cur_col, cur_table)
                    if not us:
                        continue
                    # This statement reads a whole family of date-sharded
                    # tables, and the line under the wildcard says which. See
                    # suffix_verdict: a shard the query provably never touches
                    # used to come back breaking and certain.
                    reads = suffix_verdict(stmt, cur_table)
                    if reads == "excluded":
                        continue
                    if reads == "maybe":
                        us = [replace(u, certain=False) for u in us]
                    # How this statement got here. A statement that names the
                    # table outright is a fact; one reached only through
                    # ``customer_demographics_*`` matching plain
                    # ``customer_demographics`` is a guess about what somebody
                    # meant -- BigQuery requires the separator and would match
                    # nothing. Ripple follows it anyway, because a clean "no
                    # impact" for somebody typing the family name they say out
                    # loud is the worse mistake; shipping it as certain is the
                    # part that was wrong.
                    how = _how_this_statement_reads(stmt, cur_table)
                    if how == "family":
                        us = [replace(u, certain=False) for u in us]
                    if how:
                        wild_confirmed.add(short_name(cur_table).upper())
                    primary = us[0]
                    src = index.get(stmt.file)
                    if src is None:
                        continue
                    hit = locate(src, cur_col, primary.kind, stmt.line_offset, stmt.line_end)
                    note = {
                        "filter": "Filter - stops matching after the change",
                        "join_key": "Join key - verify both sides change together",
                        "ranking": "Ranking order - breaks silently if removed",
                        "dedup_key": "Decides which row survives",
                        "transform": "Value is reshaped here",
                        "aggregation": "Group label changes with the value",
                        "sort": "Sort order - the statement stops running if this goes",
                        "excluded": ("Named in REPLACE - swapped here, and breaks here"
                                     if primary.detail == "REPLACE"
                                     else "Named in EXCEPT - dropped here, and breaks here"),
                        "pivoted": f"Named in {primary.detail or 'PIVOT'} - reshaped here, "
                                   "and breaks here",
                        "layout": f"{primary.detail or 'PARTITION BY'} - this table stops "
                                  "being built without it",
                        "renamed": f"Renamed here to {primary.detail or primary.alias}",
                        "dropped": "Dropped from the table here, by name",
                        "retyped": "Changed on the table itself here",
                        "star": "SELECT * - carried on without being named",
                        "select": f"Carried forward as {primary.alias or cur_col}",
                    }.get(primary.kind, "Used here")

                    carried_by_star = any(u.via_star for u in us)
                    # A SELECT * from a table whose columns are written down
                    # publishes a column list Ripple can READ: the catalogue
                    # filled it in from the table it copies, or the built
                    # table has a CREATE TABLE of its own. Then this hop is
                    # read, not inferred. A list that is written down WITHOUT
                    # this column is said out loud, and followed anyway --
                    # excluding on it would be the catastrophic direction.
                    star_known = False
                    listed_without = ""
                    listed: list[str] = []
                    if carried_by_star and stmt.target:
                        listed = cat.columns(short_name(stmt.target))
                        if listed:
                            if cur_col.upper() in {c.upper() for c in listed}:
                                star_known = True
                            else:
                                listed_without = cur_col
                    # A whole-table COPY, CLONE, LIKE or RENAME is followed as
                    # the SELECT * it is, but those two words are nowhere in the
                    # file. A row that says "Carried by SELECT *" sends somebody
                    # to the line to look for a statement that is not there --
                    # and then to doubt the finding rather than the label.
                    logic = primary.label
                    # The file does not say SELECT * -- it says {cols}, and the
                    # column list arrives when the job runs. A row that claims
                    # the file says SELECT * sends somebody to a line where no
                    # such statement is written.
                    if stmt.star_note and primary.kind == "star":
                        logic = "Carried by a placeholder"
                        note = stmt.star_note
                    # PIVOT and UNPIVOT are opposite operations, and the file
                    # says which one. A row labelled PIVOT beside a line reading
                    # UNPIVOT is describing a statement that is not there.
                    if primary.kind == "pivoted" and primary.detail:
                        logic = f"Named in {primary.detail}"
                    # EXCEPT drops the column; REPLACE puts another value in its
                    # place. Both name it and both break here, but they are not
                    # the same statement and the file says which.
                    if primary.kind == "excluded" and primary.detail == "REPLACE":
                        logic = "Named in REPLACE"
                    if stmt.whole_copy and primary.kind == "star":
                        logic = f"Carried by {stmt.whole_copy}"
                        note = (f"{stmt.whole_copy} of the whole table - every column "
                                "carried on, none of them named")
                    f = Finding(
                        source_table=show(cur_table),
                        source_column=cur_col,
                        target_table=show(stmt.target) if stmt.target else None,
                        alias=primary.alias or cur_col,
                        logic=logic,
                        kind=primary.kind,
                        mode=mode_of(us),
                        impact=_impact_sentence(primary, change_type,
                                                show(stmt.target) if stmt.target else None,
                                                stmt.whole_copy, stmt.export_uri),
                        breaking=primary.kind in breaks,
                        no_local_fix=primary.kind in NO_LOCAL_FIX
                        and change_type in ("removal", "rename"),
                        file=stmt.file,
                        lang=src.lang,
                        lines=snippet(src, hit, note),
                        hop=hop,
                        certain=primary.certain,
                        via_star=carried_by_star,
                        copied_by=stmt.whole_copy,
                        built_as_text=stmt.built_as_text,
                        feed_uri=stmt.export_uri,
                        inferred_hops=inferred + (1 if carried_by_star and not star_known else 0),
                        at=stmt.line_offset,
                        target_key=stmt.target or "",
                        star_known=star_known,
                    )
                    findings_by_key.setdefault(f.key(), f)
                    f = findings_by_key[f.key()]
                    if attr not in f.roots:
                        f.roots.append(attr)
                    if f not in attr_findings:
                        attr_findings.append(f)
                    new_chain = chain + [f]

                    tgt = stmt.target
                    # An EXPORT DATA delivers a file to somebody outside the
                    # warehouse. It builds no table, so the trail has nothing to
                    # carry the column on to -- and every screen therefore said
                    # "no production table is affected", which is true and
                    # useless. The delivery breaks; it is named here.
                    if stmt.export_uri:
                        entry = feed_seen.setdefault(stmt.export_uri, {
                            "uri": stmt.export_uri, "file": stmt.file,
                            "line": stmt.line_offset + 1, "from": show(cur_table),
                            "attrs": [], "breaking": False})
                        if attr not in entry["attrs"]:
                            entry["attrs"].append(attr)
                        entry["breaking"] = entry["breaking"] or f.breaking
                        recorded = True
                    if not tgt:
                        continue
                    shown = show(tgt)
                    node = {
                        "name": shown,
                        "kind": _kind_of_node(short_name(tgt), cfg),
                        "alias": primary.alias or cur_col,
                    }
                    # The statement builds a table it never names -- a dbt model
                    # or any other one-query file. The hop is real and the name
                    # is the tool's own rule, not a guess, but it is not written
                    # on the line, so it is said out loud beside the answer.
                    # More than one file builds this table from scratch, and
                    # only one of them can be the definition that runs. See
                    # ParsedRepo.rebuilt_in.
                    forks = parsed.rebuilt_in(tgt)
                    if forks:
                        node["twoDefinitions"] = True
                        forked_seen.setdefault(shown, {"table": shown, "files": forks})
                    # The file does not hold this statement as SQL. It holds a
                    # quoted string, and runs it. Ripple reads the string, so
                    # the hop is real -- but nobody sent to that line will find
                    # the CREATE this row describes written there.
                    if stmt.built_as_text:
                        node["builtAsText"] = True
                        text_sql_seen.setdefault(
                            (stmt.file, stmt.line_offset),
                            {"table": shown, "file": stmt.file,
                             "line": stmt.line_offset + 1, "how": stmt.built_as_text})
                    if stmt.named_by:
                        node["namedByFile"] = True
                        file_named_seen.setdefault(shown, {
                            "table": shown, "file": stmt.file, "how": stmt.named_by})
                    if carried_by_star:
                        # This table is built with SELECT *. Either its column
                        # list was filled in from the table it copies (see
                        # star_known) and the hop was read -- or the list is
                        # nowhere in the repository, the hop is real and the
                        # ones past it are worked out. Both facts travel with
                        # the result rather than living on another screen.
                        node["how"] = stmt.whole_copy
                        if star_known:
                            node["starKnown"] = True
                        else:
                            node["inferred"] = True
                        entry = star_seen.setdefault(shown, {
                            "table": shown, "file": stmt.file, "from": show(cur_table),
                            "attr": cur_col, "roots": [],
                            # A whole-table COPY, CLONE, LIKE or RENAME is
                            # followed as the SELECT * it is, but the file does
                            # not say SELECT * -- and a card describing a
                            # statement that is not in the file is worse than
                            # no card. Which word was written travels with it.
                            "how": stmt.whole_copy,
                            # Not a star in the file at all, but a hole where
                            # the column list goes. See Statement.star_note.
                            "filledIn": stmt.star_note,
                            # The list IS written down, and where. See star_known.
                            "known": star_known,
                            "columns": len(listed),
                            "listedIn": cat.listed_in(short_name(stmt.target)) if listed else "",
                            # Columns asked about that the written list lacks.
                            "listedWithout": [],
                        })
                        if attr not in entry["roots"]:
                            entry["roots"].append(attr)
                        # One attribute on the written list and another off it
                        # is one table, known only for the ones on the list.
                        entry["known"] = bool(entry["known"] and star_known)
                        if listed_without and listed_without not in entry["listedWithout"]:
                            entry["listedWithout"].append(listed_without)
                    # SELECT * EXCEPT(col) drops the column by name. It does not
                    # reach this table, so there is nothing to follow onwards --
                    # but the statement is still broken by the change, which is
                    # why the finding above was kept.
                    if primary.kind == "excluded":
                        branch = path + [node]
                        if branch not in end_branches:
                            end_branches.append(branch)
                        _collect(end_groups, shown, new_chain)
                        recorded = True
                        continue
                    # A column can leave a statement under more than one name --
                    # reshaped into one column and passed through unchanged as
                    # another, in the same SELECT. Following only one of them
                    # stopped the chain one table short of the published table
                    # that reads the other, and reported no production impact.
                    onwards = output_names(stmt, cur_col)
                    onward_inferred = inferred + (1 if carried_by_star and not star_known else 0)
                    if cfg.is_production_table(short_name(tgt)):
                        node["prod"] = True
                        branch = path + [node]
                        if branch not in branches:
                            branches.append(branch)
                        _collect(prod_groups, shown, new_chain)
                        recorded = True
                        # And keep going. One published table feeding another is
                        # exactly how a change spreads, and stopping at the first
                        # one under-counts the number this whole tool is judged
                        # on -- while showing a shorter chain than the real one.
                        for onward in onwards:
                            _, hit_cap = walk(tgt, onward, hop + 1, path + [node],
                                              new_chain, seen, onward_inferred)
                            truncated = truncated or hit_cap
                        continue
                    # Every onward name is followed. This used to be an any(),
                    # which stops at the first one that finds something -- so a
                    # column leaving under two names had its second name dropped
                    # exactly when the first name found something, which is most
                    # of the time.
                    results = [walk(tgt, onward, hop + 1, path + [node], new_chain,
                                    seen, onward_inferred)
                               for onward in onwards]
                    truncated = truncated or any(cap for _, cap in results)
                    if any(done for done, _ in results):
                        recorded = True
                    else:
                        # Nothing further is built from this table, so the trail
                        # ends here -- unless the hop limit is what stopped us,
                        # in which case the trail does not end here at all and
                        # the node says so.
                        if any(cap for _, cap in results):
                            node["cut"] = True
                        branch = path + [node]
                        if branch not in end_branches:
                            end_branches.append(branch)
                        _collect(end_groups, shown, new_chain)
                        recorded = True
                return recorded, truncated

            walk(table, attr, 0, [], [], set(), 0)

            # A chain that carries on past a published table is drawn once, at
            # its full length. The shorter version of it is the same chain with
            # the end cut off, and drawing both reads as two findings.
            branches = _longest_only(branches)
            end_branches = _longest_only(end_branches)

            res.findings.extend([f for f in attr_findings if f not in res.findings])
            # "I never saw that column" and "that column goes nowhere" were the
            # same answer, byte for byte: found 0, no findings, a green tick.
            # They are opposite answers -- one answers the question, the other
            # is the question never having been asked. Split on whether the name
            # ever turned up as a column on any table in the repository.
            lookup_failed = not attr_findings and not shared.get(attr.upper(), 0)
            if branches or end_branches:
                graphs.append({"attr": attr, "table": typed,
                               "branches": branches, "endBranches": end_branches})
            res.attributes.append(
                {
                    "table": typed,
                    "attr": attr,
                    "found": len(attr_findings),
                    "files": len({f.file for f in attr_findings}),
                    # How many files so much as write the name down. Zero here
                    # is the answer to "why did it find nothing?" -- the name is
                    # not in this repository at all.
                    "mentionedIn": len({m.file for m in index.search([attr])}),
                    "reachesProduction": bool(branches),
                    # Only the branches that genuinely ran out of code. A branch
                    # Ripple stopped following has not ended, and putting it here
                    # is what turned a setting into a claim about the warehouse.
                    "endsAt": sorted({b[-1]["name"] for b in end_branches
                                      if not b[-1].get("cut")}),
                    "cutShortAt": sorted({c["table"] for c in attr_cut}),
                    # Hops on this attribute's trail where the column list was
                    # not written down, and findings that sit past one of them.
                    "notVisible": sorted({f.target_table for f in attr_findings
                                          if f.via_star and not f.star_known and f.target_table}),
                    "inferred": len([f for f in attr_findings if f.inferred_hops]),
                    # How widely this column name is used as a name. A scan for
                    # a name half the warehouse shares is a different kind of
                    # answer from a scan for a name only one table has, and the
                    # screen has no way to say so without these two numbers.
                    "nameInTables": shared.get(attr.upper(), 0),
                    "tablesRead": table_count,
                    # "I never saw that column" and "that column goes nowhere"
                    # were byte-for-byte the same answer: found 0, no findings,
                    # a green tick. They are opposite answers. The first is a
                    # question Ripple did not manage to ask; the second is an
                    # answer to it. Split on whether the name turned up as a
                    # column on ANY table in the repository.
                    "lookupFailed": lookup_failed,
                    # The columns Ripple did read on the table asked about, so a
                    # typo corrects itself on the spot rather than shipping as
                    # "no impact". Empty means Ripple has no column list for
                    # this table at all, which is a different answer again.
                    "tableColumns": columns_here() if lookup_failed else [],
                    # Findings on lines where the SQL did not say which table
                    # the column came from. Real usages; the table is inferred.
                    "uncertain": len([f for f in attr_findings if not f.certain]),
                }
            )

    res.graphs = graphs
    # Most impacts first, then by name. On a real repository this is hundreds of
    # tables long, and alphabetical order puts whichever table happens to start
    # with an "a" at the top of the page -- so the one thing somebody reads
    # first is decided by the alphabet rather than by how much of it is broken.
    def _worst_first(groups: dict[str, list[Finding]]) -> list[tuple[str, list[Finding]]]:
        return sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0].upper()))

    res.groups = [
        {
            "prod": prod,
            "note": f"Published by this team - {_kind_of_node(prod, cfg).lower()} table",
            "rows": [_finding_row(f) for f in fs],
        }
        for prod, fs in _worst_first(prod_groups)
    ]
    placed = {f.key() for fs in prod_groups.values() for f in fs}
    cut_tables = {c["table"] for c in cut_seen.values()}
    res.reached = [
        {
            "prod": table,
            "note": ("Ripple stopped following here - the hop limit was reached, so this is "
                     f"not where the chain ends" if table in cut_tables else
                     "Last table in the chain - not matched by your production naming rule"),
            "cut": table in cut_tables,
            "rows": [_finding_row(f) for f in fs],
        }
        for table, fs in _worst_first(end_groups)
    ]
    res.star_tables = sorted(star_seen.values(), key=lambda s: s["table"].upper())
    res.cut_short = sorted(cut_seen.values(), key=lambda c: c["table"].upper())
    res.merged_names = sorted(merged_seen.values(), key=lambda m: m["table"].upper())
    # Only the wildcards that actually produced a finding. See note_if_wildcard:
    # this card says "the usages below are real", and a wildcard in one dataset
    # covering a shard in another produces none, so the card was contradicting
    # the empty answer it sat under.
    res.wildcard_names = sorted(
        (w for k, w in wild_seen.items() if k in wild_confirmed),
        key=lambda w: w["table"].upper())
    res.named_by_file = sorted(file_named_seen.values(), key=lambda m: m["table"].upper())
    res.two_definitions = sorted(forked_seen.values(), key=lambda m: m["table"].upper())
    res.built_as_text = sorted(text_sql_seen.values(),
                               key=lambda m: (m["file"], m["line"]))
    res.feeds = sorted(feed_seen.values(), key=lambda m: m["uri"])
    placed |= {f.key() for fs in end_groups.values() for f in fs}
    res.other = [_finding_row(f) for f in res.findings if f.key() not in placed]

    # Honesty: anything the search matched but the reader could not turn into a
    # finding is surfaced, never quietly dropped. Which of the three things it
    # is matters enormously -- "the name is written down here and nothing reads
    # it" is reassuring, and "the name is inside a call I cannot follow" is the
    # opposite, and they used to be told apart by nothing at all.
    # DDL that names a table the chain stood on, or one of the columns being
    # followed, and carries no column anywhere. A row access policy filtering on
    # market_code stops working on the day market_code goes, and no lineage
    # anywhere would ever have said so. Worked out here, before the honesty
    # lists below, because a file already accounted for by this belongs on this
    # card and on no other -- counted twice it is the same statement reported as
    # two separate problems.
    res.referenced_here = _references_on_topic(parsed, visited, all_names)
    accounted_for = {r["file"] for r in res.referenced_here}

    impacted_files = {f.file for f in res.findings}
    already = {u.get("file"): u for u in res.unreadable}

    # A file that produced findings used to be skipped entirely here, on the
    # reasonable-sounding grounds that it is already covered. It is not.
    #
    # Real code in this pipeline reads:
    #
    #     substr(decrypt_sde(get_sde_tag('cm13', 'triumph_demographics'), cm13), 1, 11)
    #
    # Both cm13s on that line break when cm13 is renamed. Ripple reports the
    # second one, because it is a column. The first is a quoted string, so no
    # parser can see it as anything but text -- and because the file was
    # "already covered", nothing was said about it at all. Somebody fixes the
    # column, ships, and the helper carries on asking for a name that has gone.
    for path in sorted(matched_files & impacted_files):
        hidden = _named_out_of_reach(index, parsed, path, all_names)
        if not hidden:
            continue
        hidden["reason"] = ("this file has findings above, and the name is ALSO written as "
                            "text in it - " + hidden["reason"])
        hidden["hint"] = (hidden.get("hint", "") + " Fixing the findings above does not fix "
                          "this one: the text still says the old name.").strip()
        res.unreadable.append(hidden)

    for path in sorted(matched_files - impacted_files):
        hidden = _named_out_of_reach(index, parsed, path, all_names)
        if hidden and path in already:
            # Already known to be unreadable, but now there is something better
            # to say about it: not just "this file was a problem" but "the name
            # you are chasing is on line 212 of it".
            entry = already[path]
            entry["hint"] = (entry.get("hint", "") + " " + hidden["hint"]).strip()
            entry.update({k: hidden[k] for k in ("reason", "line", "snippet")})
        elif hidden:
            res.unreadable.append(hidden)
        elif path in already:
            continue
        elif path in accounted_for:
            # An index, a policy or an UNDROP naming this very column. It is on
            # the "named here, but nothing is carried" card with the table and
            # the columns spelled out -- which is more than either of the two
            # lines below could say about it.
            continue
        elif path not in parsed.parsed_files:
            res.unreadable.append(
                {
                    "file": path,
                    "reason": "mentions the name, but Ripple could not read it as SQL - check by hand",
                }
            )
        else:
            res.mentions_only.append(
                {"file": path, "reason": "name appears, but no lineage to a production table"}
            )

    # A published table that stops being REFRESHED, rather than one whose
    # column changes. See _stops_loading -- a column used only to filter or
    # join never reaches the table the statement builds, so the trail for it
    # ends there, but the statement stops running and the table stops loading.
    broken: dict[str, str] = {}
    for f in res.findings:
        if f.breaking and f.target_table:
            # Keyed on what goes on screen, walked on from what the reader
            # keyed. For a temporary table those are two different names -- see
            # Finding.target_key.
            broken.setdefault(short_name(f.target_table).upper(),
                              f.target_key or f.target_table)
    res.stops_loading, res.stops_loading_capped = _stops_loading(
        parsed, cfg, broken,
        {short_name(g["prod"]).upper() for g in res.groups}, show)

    # A statement Ripple could not understand that names a table the chain
    # actually stood on. This is the quietest hole left in the reader: the file
    # parses, the readable statements produce findings, and the one statement
    # that carries the chain onwards -- a procedure call, SQL built as text,
    # a shape the parser gave up on -- is simply absent. The result reads as
    # complete because nothing on it says otherwise.
    #
    # Deliberately narrow. Every real pipeline is full of DECLAREs and CALLs
    # that carry no lineage at all, and reporting those would bury the list this
    # is trying to protect. Only a statement naming a table on THIS trail counts.
    for entry in _opaque_on_the_trail(index, parsed, visited,
                                      {u.get("file") for u in res.unreadable}):
        res.unreadable.append(entry)

    # Worst first. This list is the one place Ripple admits what it missed, and
    # it is only useful for as long as somebody reads to the bottom of it.
    # Alphabetical order decides what they read first by the first letter of a
    # filename -- measured: twelve config files above the one genuinely broken
    # query, because the query's file happened to start with a z.
    res.unreadable.sort(key=lambda u: (-_sql_likeness(u, index, matched_files),
                                       u.get("file", "")))

    # A gap Ripple knows about, on the subject of this scan. See _risk_of.
    # Restricted to files that mention one of the names being followed, because
    # every real pipeline has some file the reader cannot make sense of, and a
    # badge that says "not sure" on every scan ever run is one nobody reads. A
    # file that was never OPENED is not restricted that way -- nothing can say
    # whether it mentions the name, which is exactly the problem with it.
    opened = {f.path for f in index.files}
    res.unreadable_on_topic = len([u for u in res.unreadable
                                   if u.get("file") in matched_files])
    unread_on_topic = (any(u.get("file") in matched_files for u in res.unreadable)
                       or any(u.get("file") not in opened for u in res.unreadable)
                       or bool(res.held_online) or bool(res.too_long)
                       # Code files walked past because of the folder they sit
                       # in, on a scan that found NOTHING. Measured: the whole
                       # chain from the source table to the published one sat
                       # in build/, and the answer was a green "no impact" with
                       # a letter saying "please proceed as planned".
                       # Only when nothing was found: skipping build, dist and
                       # target is ordinary, and a badge that reads "not sure"
                       # on every scan of every dbt project is one nobody reads.
                       # Where the chain WAS found, the card naming the skipped
                       # folder is the right size of warning.
                       or (not res.findings and bool(res.skipped_in_folders)))
    # Every attribute asked about is a name Ripple never met as a column. The
    # scan did not come back clean -- it came back without having asked the
    # question, and those two have to look different on screen. See
    # ScanResult.lookup_failed.
    #
    # "I never saw that column" is a CONFIDENT claim, and it may only be made
    # where Ripple could look everywhere. Measured, all three as a green
    # "check your spelling" over a real gap: a file naming the column that could
    # not be read; the whole chain sitting in a skipped build/ folder; and a row
    # access policy that names the column outright, on the very screen saying
    # the name was never met.
    res.lookup_failed = (
        bool(res.attributes)
        and all(a["lookupFailed"] for a in res.attributes)
        and res.coverage()["complete"]
        and not unread_on_topic
        and not _names_a_scanned_column(res)
    )
    res.risk = _risk_of(res, unread_on_topic)
    return res


def _names_a_scanned_column(res: ScanResult) -> bool:
    """Does any index or policy name one of the columns being followed?

    Nothing here is lineage, so it produces no finding -- but a row access
    policy filtering on the column stops working on the day the column goes,
    and "No impact" over that is the one sentence this tool may not print.
    """
    return any(r.get("namesColumns") for r in res.referenced_here)


# How many tables the downstream walk will look at before it stops. Reached
# only by a table half the warehouse is built from; the number exists so a
# pathological repository cannot turn one scan into a very long one.
MAX_DOWNSTREAM = 400


def _stops_loading(parsed: ParsedRepo, cfg: Settings, broken: dict[str, str],
                   already: set[str], show) -> tuple[list[dict], bool]:
    """Published tables that stop being refreshed because a job stops running.

    A column used only in a WHERE, a JOIN or a GROUP BY never reaches the table
    the statement builds, so the trail for that COLUMN genuinely ends there --
    and Ripple said so, and stopped. But the statement itself stops working on
    the day the column goes, so the table it builds stops being rebuilt, and
    everything below it is served from data that is no longer being updated.

    That is a real impact on a published table, and it was invisible. It is
    also a DIFFERENT KIND of impact from the findings above -- nothing about
    those tables' columns changes -- so it is reported separately and in its
    own words. Folding the two together would be worse than not reporting it.

    Followed at the level of tables, not columns: which column carries onwards
    does not matter once the job feeding them has stopped.
    """
    if not broken:
        return [], False
    out: dict[str, dict] = {}
    seen = set(broken)
    frontier = [(table, [show(table)]) for table in broken.values()]
    capped = False
    # Zero means "until the code runs out". `seen` grows every round and is
    # never cleared, so this walk ends when the frontier does -- or at
    # MAX_DOWNSTREAM below, which IS reported.
    rounds = cfg.max_hops if cfg.max_hops else len(parsed.statements) + 1
    for _ in range(max(1, rounds)):
        if not frontier:
            break
        nxt: list[tuple[str, list[str]]] = []
        for table, path in frontier:
            for stmt in parsed.reading(table):
                target = stmt.target
                if not target:
                    continue
                key = short_name(target).upper()
                if key in seen:
                    continue
                if len(seen) >= MAX_DOWNSTREAM:
                    capped = True
                    continue
                seen.add(key)
                step = path + [show(target)]
                if cfg.is_production_table(short_name(target)) and key not in already:
                    out[key] = {"prod": show(target), "because": path[0], "via": step}
                nxt.append((target, step))
        frontier = nxt
    return sorted(out.values(), key=lambda r: r["prod"].upper()), capped


def _how_this_statement_reads(stmt, table: str) -> str:
    """"" if the statement names this table outright, else how it reached it.

    "shard" or "family" -- see wildcard_match. Only asked of statements that
    already produced a usage, so the cost is per finding rather than per file.
    """
    if stmt.reads_from(short_name(table)):
        return ""
    best = ""
    for src in stmt.sources:
        how = wildcard_match(src, table)
        if how == "family":
            best = "family"
        elif how and not best:
            best = "shard"
    return best


def _references_on_topic(parsed: ParsedRepo, visited: set[str],
                         all_names: list[str]) -> list[dict]:
    """Index, policy and UNDROP DDL that names something this scan is about.

    Deliberately narrow, for the same reason _opaque_on_the_trail is. A real
    warehouse has indexes on tables nobody in this scan has heard of, and
    listing those would bury the ones that matter. A statement counts when it
    names a table the chain actually stood on, or one of the columns being
    followed.
    """
    wanted = {n.upper() for n in all_names if n}
    out: list[dict] = []
    for ref in parsed.references:
        table = short_name(ref["table"]).upper()
        columns = [c for c in ref["columns"] if c.upper() in wanted]
        if table not in visited and table not in wanted and not columns:
            continue
        out.append({**ref, "namesColumns": columns})
    return sorted(out, key=lambda r: (r["file"], r["line"]))


def _opaque_on_the_trail(index: RepoIndex, parsed: ParsedRepo, visited: set[str],
                         already: set) -> list[dict]:
    """Statements Ripple could not read that name a table the chain reached."""
    if not visited or not parsed.opaque:
        return []
    out: list[dict] = []
    pattern = index._pattern(sorted(visited))
    for path, records in sorted(parsed.opaque.items()):
        if path in already:
            continue
        for record in records:
            # An index, a policy or an UNDROP. The parser gave up on it, but
            # Ripple read the table and the columns out of it and reports them
            # under "named here, but nothing is carried". Listing it as a
            # statement nobody could understand as well would count one thing
            # twice, on the list that has to stay short enough to read.
            if record.get("refKind"):
                continue
            text = record.get("sql") or record.get("text") or ""
            match = pattern.search(text)
            if not match:
                continue
            out.append({
                "file": path,
                "reason": (f"a statement here names {match.group(1)}, which is on this "
                           "trail, and Ripple could not understand it"),
                "line": record.get("line", 0),
                "snippet": record.get("text", "")[:200],
                "hint": ("The chain may carry on inside that statement. Everything above "
                         "is what Ripple could follow; this one has to be read by a "
                         "person."),
            })
            break                                  # one entry per file, not per line
    return out


def _named_out_of_reach(
    index: RepoIndex, parsed: ParsedRepo, path: str, names: list[str]
) -> dict | None:
    """Is the name here in a place structural reading cannot follow?

    Two shapes, both everywhere in real pipeline code, and both invisible to a
    parser however good it is:

    * The name is inside a statement the reader could take in but not make sense
      of -- a procedure call, a loop, an EXECUTE IMMEDIATE, SQL assembled as
      text and run later.
    * The name is a quoted string rather than a column: an in-house helper like
      ``get_tag('home_phone_no', 'customer_demographics')`` names the column and
      the table as text, and no amount of parsing turns that back into lineage.

    Either way the attribute really is referenced in this file. Filing it under
    "mentions the name but carries it nowhere" reads as a reassurance, and it is
    the one place a person genuinely has to go and look.
    """
    pattern = index._pattern(names)
    src = index.get(path)

    for record in parsed.opaque.get(path, []):
        # Read after all -- see the note in _opaque_on_the_trail.
        if record.get("refKind"):
            continue
        match = pattern.search(record.get("sql") or record.get("text") or "")
        if match:
            line, text, places = _line_naming(src, match.group(1))
            return {
                "file": path,
                "reason": "the name is used in a statement Ripple cannot follow",
                "line": line,
                "snippet": text,
                "places": places,
                "hint": "A procedure call, a loop, or SQL built as text and run later. "
                        "Ripple can see the name in it but not what it does with it, so "
                        "this one has to be read by a person.",
            }

    for stmt in parsed.statements_in(path):
        if stmt.expr is None:
            continue
        for literal in stmt.expr.find_all(exp.Literal):
            if not literal.is_string:
                continue
            match = pattern.search(str(literal.this))
            if not match:
                continue
            line, text, places = _line_naming(src, match.group(1))
            # How many lines of the file do this, not merely whether any does.
            # A real file sets one tag per column and runs to sixty of them; a
            # report naming one line reads as one thing to check, and sends
            # somebody to fix one line out of sixty.
            where = f" - on {places} lines of this file" if places > 1 else ""
            # Name what actually happened. This statement reads BigQuery's own
            # catalogue and looks the table up by its name as text -- which is
            # correct code, doing exactly what it should. Told instead that the
            # name is "how in-house helpers take a column or table name", the
            # one line on screen pointing at the problem named the wrong cause,
            # and following it would have found no such helper anywhere.
            # Asked of the tree, not of stmt.sources: a metadata view is
            # deliberately never recorded as a source -- it carries no column of
            # anybody's table -- so the one place the fact survives is the
            # statement itself.
            if reads_metadata(stmt.expr):
                return {
                    "file": path,
                    "reason": (f'this statement looks "{match.group(1)}" up in BigQuery\'s own '
                               f"catalogue, by name{where}"),
                    "line": line,
                    "snippet": text,
                    "places": places,
                    "hint": ("INFORMATION_SCHEMA describes the warehouse, so the table name is "
                             "a value here rather than a table being read. Nothing about the "
                             "lineage of the table changes -- but this query stops finding it "
                             "the day the name changes, and no rename of a column or table "
                             "updates a string. Change it by hand."),
                }
            return {
                "file": path,
                "reason": f'the name appears as text inside a call - "{match.group(1)}"{where}',
                "line": line,
                "snippet": text,
                "places": places,
                "hint": "Written as a quoted string rather than used as a column, which is "
                        "how in-house helpers take a column or table name. Ripple cannot "
                        "follow what the helper does with it.",
            }
    return None


def _line_naming(src, name: str) -> tuple[int, str, int]:
    """Where this name is written as text, that line, and how many such lines.

    Quoted occurrences win: that is the one being reported, and it is the line
    somebody has to open the file at. The count matters as much as the line --
    one file can name the same column on sixty lines in a row.
    """
    if src is None:
        return 1, "", 0
    quoted = re.compile(r"['\"]" + re.escape(name) + r"['\"]", re.IGNORECASE)
    plain = re.compile(r"\b" + re.escape(name) + r"\b", re.IGNORECASE)
    first = fallback = None
    places = 0
    for number, line in enumerate(src.lines, start=1):
        if quoted.search(line):
            places += 1
            if first is None:
                first = (number, line.strip()[:140])
        elif fallback is None and plain.search(line):
            fallback = (number, line.strip()[:140])
    if first is not None:
        return first[0], first[1], places
    if fallback is not None:
        return fallback[0], fallback[1], 1
    return 1, "", 0


def _longest_only(branches: list[list[dict]]) -> list[list[dict]]:
    """Drop any branch that is just the start of a longer one already listed."""
    return [b for b in branches
            if not any(other is not b and len(other) > len(b) and other[:len(b)] == b
                       for other in branches)]


def _collect(groups: dict[str, list[Finding]], table: str, chain: list[Finding]) -> None:
    bucket = groups.setdefault(table, [])
    for f in chain:
        if f not in bucket:
            bucket.append(f)


# How many of a table's own column names to print back when a lookup fails.
# Enough to spot a typo in, short enough to read on one line of a card.
MAX_COLUMNS_SHOWN = 40


def _columns_on(parsed: ParsedRepo, table: str) -> list[str]:
    """Every column name Ripple has seen on this table, in the order it met them.

    Two ways of seeing one, and both count. A statement that BUILDS the table
    writes its column list down. A statement that READS ONLY this table
    attributes every column in it to this table and nothing else -- which is
    where a source table's columns are written down, because nothing in the
    repository builds a source table at all.

    Empty means one of two very different things, and the card that prints this
    has to say which: nothing here builds or reads the table under that name, or
    everything that touches it does so with a SELECT *.
    """
    wanted = short_name(table).upper()
    out: list[str] = []
    seen: set[str] = set()

    def add(name: str) -> None:
        key = (name or "").upper()
        if name and key not in seen:
            seen.add(key)
            out.append(name)

    for stmt in parsed.statements:
        if stmt.target and short_name(stmt.target).upper() == wanted:
            for name in _stated_columns(stmt):
                add(name)
            continue
        # Only when this table is the one thing the statement reads. With two
        # tables in the FROM, a bare column name genuinely does not say whose it
        # is -- and putting a guess on this card is how somebody comes to scan
        # for a column that is on the other table.
        if len(stmt.sources) == 1 and stmt.reads_from(wanted) and stmt.expr is not None:
            for col in stmt.expr.find_all(exp.Column):
                add(col.name)
    return out


def _stated_columns(stmt) -> list[str]:
    """The column names this statement writes down for the table it builds."""
    schema = stmt.expr.this if isinstance(stmt.expr, exp.Create) else None
    if isinstance(schema, exp.Schema):
        return [d.this.name for d in schema.expressions if isinstance(d, exp.ColumnDef)]
    columns: list[str] = []
    if isinstance(stmt.expr, exp.Merge):
        for when in merge_whens(stmt.expr):
            then = when.args.get("then")
            if isinstance(then, exp.Update):
                columns += [e.this.name for e in then.args.get("expressions") or []
                            if isinstance(e, exp.EQ) and isinstance(e.this, exp.Column)]
            elif isinstance(then, exp.Insert) and isinstance(then.this, exp.Tuple):
                columns += [c.name for c in then.this.expressions if getattr(c, "name", "")]
        return columns
    if stmt.select is not None:
        for e in stmt.select.expressions:
            if isinstance(e, exp.Alias):
                columns.append(e.alias)
            elif isinstance(e, exp.Column):
                columns.append(e.name)
    return columns


def _tables_carrying(parsed: ParsedRepo, names: list[str]) -> tuple[dict[str, int], int]:
    """How many tables have a column of each of these names, and how many tables
    there are altogether.

    In this warehouse cm13, cm11 and pub_guid are columns in nearly every table,
    and market_code is in a handful. Those two scans look identical on screen and
    are not remotely the same thing: one of them is following a name that half
    the repository happens to share. Counting it is what lets the screen say so
    instead of leaving somebody to work it out from the length of the list.
    """
    wanted = {n.upper() for n in names if n}
    carrying: dict[str, set[str]] = {n: set() for n in wanted}
    all_tables: set[str] = set()
    for stmt in parsed.statements:
        if not stmt.target:
            continue
        target = stmt.target.upper()
        all_tables.add(target)
        columns: list[str] = []
        schema = stmt.expr.this if isinstance(stmt.expr, exp.Create) else None
        if isinstance(stmt.expr, exp.Merge):
            # A MERGE writes the published table's own column names on the left
            # of every SET and in every INSERT list. Without reading them a
            # MERGE-loaded table looked like a table with no columns at all, so
            # a column name half the warehouse shares was counted as rare -- and
            # "only one table has this name" is read as a reason to relax.
            for when in merge_whens(stmt.expr):
                then = when.args.get("then")
                if isinstance(then, exp.Update):
                    columns += [e.this.name for e in then.args.get("expressions") or []
                                if isinstance(e, exp.EQ) and isinstance(e.this, exp.Column)]
                elif isinstance(then, exp.Insert) and isinstance(then.this, exp.Tuple):
                    columns += [c.name for c in then.this.expressions if getattr(c, "name", "")]
        elif isinstance(schema, exp.Schema):
            columns = [d.this.name for d in schema.expressions if isinstance(d, exp.ColumnDef)]
        elif stmt.select is not None:
            for e in stmt.select.expressions:
                if isinstance(e, exp.Alias):
                    columns.append(e.alias)
                elif isinstance(e, exp.Column):
                    columns.append(e.name)
        for c in columns:
            key = (c or "").upper()
            if key in carrying:
                carrying[key].add(target)
    return {k: len(v) for k, v in carrying.items()}, len(all_tables)


def _finding_row(f: Finding) -> dict:
    return {
        "inter": f.target_table or f.source_table,
        "from": f.source_table,
        "attr": f.source_column,
        # Which of the attributes on the notification this row belongs to. Two
        # renames down, the column on this row is not called what the person
        # typed, and without this the row cannot be traced back to the question.
        "roots": list(f.roots),
        "alias": f.alias,
        "logic": f.logic,
        "mode": f.mode,
        "impact": f.impact,
        "breaking": f.breaking,
        "noLocalFix": f.no_local_fix,
        "file": f.file,
        "lang": f.lang,
        "lines": f.lines,
        "certain": f.certain,
        "viaStar": f.via_star,
        "copiedBy": f.copied_by,
        "builtAsText": f.built_as_text,
        "feed": f.feed_uri,
        "inferredHops": f.inferred_hops,
        # The row is about the table itself, not a column of it. See WHOLE_TABLE.
        "whole": f.kind == "table",
        # A SELECT * whose column list is written down after all. See star_known.
        "starKnown": f.star_known,
    }


# Files whose whole job is to hold SQL. One of these on the "check by hand"
# list is a query nobody read; a .yaml on the same list is usually a config
# file that happens to have the word SELECT in a comment.
_SQL_FIRST_EXTS = (".sql", ".sqlx", ".ddl", ".hql")
_SQL_WORDS = re.compile(
    r"\b(SELECT|INSERT\s+INTO|CREATE\s+TABLE|CREATE\s+OR\s+REPLACE|MERGE\s+INTO"
    r"|UPDATE|EXECUTE\s+IMMEDIATE)\b",
    re.IGNORECASE,
)


def _sql_likeness(entry: dict, index: RepoIndex, matched_files: set[str]) -> int:
    """How much a file on the 'check by hand' list is worth checking.

    Three things, in order. Whether it mentions the name being scanned settles
    it on its own -- that is a hole in THIS answer rather than in the reader.
    Then whether the file is a SQL file at all. Then whether SQL is written in
    it anywhere.
    """
    path = entry.get("file", "")
    score = 0
    if path in matched_files:
        score += 4
    if path.lower().endswith(_SQL_FIRST_EXTS):
        score += 2
    src = index.get(path)
    if src is not None and _SQL_WORDS.search(src.text):
        score += 1
    elif src is None:
        # Never opened at all -- nothing can say what is in it, which is the
        # whole problem with it.
        score += 1
    return score


def _risk_of(res: ScanResult, unread_on_topic: bool = False) -> str:
    """The badge at the top of the answer.

    "No impact" is the only thing this tool sells, so it is the one word that
    must never be printed over a gap. A file that mentions the very name being
    scanned and could not be read, or a file that was never opened at all, is a
    gap -- Ripple does not know what is in it, and "I found nothing" and "I could
    not look" are not the same answer however similar they look on screen.

    Measured before this: an EXECUTE IMMEDIATE holding a whole CREATE ... SELECT
    of the scanned column printed a green "No impact" with couldNotRead 1 sitting
    underneath it, and a file whose first statement was eaten by a byte-order
    mark did the same.
    """
    if not res.findings:
        if unread_on_topic:
            return "unknown"
        # No lineage anywhere, but something in the repository names this very
        # column and stops working without it -- a row access policy filtering
        # on it, a search index built over it. See _names_a_scanned_column.
        if _names_a_scanned_column(res):
            return "low"
        # Nothing found, and a whole file type in this repository was never
        # opened. The middle hop of a chain lives in a notebook often enough
        # that "no impact" here is a claim Ripple has not earned. It did not
        # look everywhere, so it says so. See file_types_unopened.
        if res.file_types_unopened:
            return "unknown"
        return "none"
    if any(f.no_local_fix for f in res.findings):
        return "high"
    if any(f.breaking for f in res.findings):
        return "medium"
    return "low"
