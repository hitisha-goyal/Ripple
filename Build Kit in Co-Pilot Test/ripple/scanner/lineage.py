"""Following a column out of the table it was reported on, and admitting what
could not be followed.

The walk itself is small. Most of this file is the honest half: a trail the hop
limit cut is not a trail that ended, a table that stops being rebuilt is a
second kind of impact and not the same number as the first, a file that could
not be read is not a file with nothing in it, and a name Ripple never met as a
column is the opposite answer to a name that goes nowhere.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from typing import Any, Callable

from sqlglot import expressions as exp

from ripple.catalog import Catalog, build_catalog
from ripple.production import ProductionRule, matches, parse_production
from ripple.scanner.dialectcompat import merge_whens
from ripple.scanner.sqlread import display_table, same_table, usages_of

# The settings screen owns max_hops; these two are the only bounds a single
# deeper scan may ask for.
HOP_FLOOR = 1
HOP_CEILING = 25

# A list cut short without a word reads as "there were only these", so the cap
# is a number that gets reported rather than a silent stop.
STOPS_LOADING_CAP = 400

QUERY_EXTENSIONS = frozenset({".sql", ".sqlx", ".ddl", ".hql"})

SQL_WORDS = (
    "select",
    "insert into",
    "create table",
    "create or replace",
    "merge into",
    "update",
    "execute immediate",
)

# Written this way round on purpose. A file type nobody thought of counts as a
# gap by default, because that is how a middle hop written in a notebook goes
# missing while the answer reads "the name appears but carries nowhere".
NOT_CODE_EXTENSIONS = frozenset(
    {
        ".md", ".markdown", ".rst", ".txt", ".pdf", ".doc", ".docx", ".rtf",
        ".csv", ".tsv", ".xls", ".xlsx", ".ppt", ".pptx",
        ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg", ".ico", ".webp",
        ".zip", ".gz", ".tar", ".tgz", ".bz2", ".7z", ".rar", ".jar", ".whl",
        ".parquet", ".avro", ".orc", ".pb", ".bin", ".dat", ".db", ".sqlite",
        ".exe", ".dll", ".so", ".dylib", ".class", ".pyc", ".o", ".a",
        ".mp3", ".mp4", ".wav", ".mov", ".avi", ".mkv", ".ogg", ".webm",
        ".lock", ".sum", ".ttf", ".otf", ".woff", ".woff2", ".eot",
    }
)

KIND_LABELS: dict[str, str] = {
    "filter": "used as a filter",
    "join_key": "used as a join key",
    "ranking": "the sort order inside a ranking",
    "dedup_key": "part of the key rows are de-duplicated on",
    "transform": "read inside a calculation",
    "aggregation": "aggregated",
    "sort": "used as the sort order",
    "layout": "part of how the table is laid out",
    "pivoted": "pivoted into column names",
    "excluded": "excluded by name",
    "renamed": "renamed on the way out",
    "dropped": "dropped by name",
    "retyped": "cast to another type",
    "select": "selected straight through",
    "star": "carried by a SELECT *",
}

# Which changes break which usages. A kind missing from this table is silently
# harmless, and it takes the "stops being refreshed" answer down with it,
# because that walk starts from the tables built by breaking statements.
_REMOVAL_OR_RENAME = frozenset(
    {
        "filter", "join_key", "ranking", "dedup_key", "transform",
        "aggregation", "sort", "excluded", "pivoted", "layout", "select",
        "renamed", "retyped",
    }
)

BREAKS: dict[str, frozenset[str]] = {
    "removal": _REMOVAL_OR_RENAME,
    "rename": _REMOVAL_OR_RENAME,
    "value_change": frozenset({"filter", "join_key", "transform"}),
    "type_change": frozenset(
        {"filter", "join_key", "transform", "pivoted", "layout", "retyped"}
    ),
    "unknown": frozenset(
        {
            "filter", "join_key", "ranking", "dedup_key", "transform", "sort",
            "pivoted", "layout", "renamed", "retyped",
        }
    ),
}

# star and dropped are in none of the sets above, both deliberately. A SELECT *
# goes on working when a column disappears - it quietly builds a narrower
# table - and an ALTER TABLE DROP COLUMN of the very column being
# decommissioned is not broken by the change, it is the change.

NO_LOCAL_FIX_KINDS = frozenset({"ranking", "dedup_key"})

# The kinds that actually carry the column into the table the statement builds.
# A filter, a join key or a sort reads the column and leaves it behind.
CARRYING_KINDS = frozenset(
    {"select", "star", "renamed", "transform", "aggregation", "pivoted", "retyped"}
)

_IMPACT_BY_KIND: dict[str, str] = {
    "filter": (
        "This column decides which rows are kept. On the day it goes the "
        "statement stops running, so {target} stops being rebuilt."
    ),
    "join_key": (
        "Rows are matched on this column. Unless both sides change on the same "
        "day, matching rows are dropped silently - no error, just fewer rows."
    ),
    "ranking": (
        "This column is the sort order inside a ranking that picks one row per "
        "key. Without it the choice becomes arbitrary; the wrong record can "
        "win, and nothing is raised to tell you."
    ),
    "dedup_key": (
        "Rows are collapsed to one on this column. Change it and rows that used "
        "to fold together stop doing so, or rows that were kept apart start "
        "folding - and the row counts move with no error."
    ),
    "transform": (
        "The value is read inside a calculation here, so whatever that "
        "calculation produces for {target} changes with it."
    ),
    "aggregation": (
        "This column is aggregated here, so every total {target} carries moves "
        "with it."
    ),
    "sort": (
        "This column sets the order rows come out in, so the order in {target} "
        "changes with it."
    ),
    "layout": (
        "{target} is laid out on this column - partitioned or clustered on it. "
        "Without the column the CREATE stops compiling, the table stops being "
        "built at all, and everything below it goes on serving yesterday."
    ),
    "pivoted": (
        "The values in this column become column names further down, so a "
        "change here renames columns inside {target}."
    ),
    "excluded": (
        "This statement takes a whole table and excludes this column by name. "
        "Remove the column and the exclusion has nothing to exclude, and the "
        "statement stops running."
    ),
    "renamed": (
        "The column leaves this statement under another name, so everything "
        "below this point calls it something else."
    ),
    "dropped": (
        "This statement is the change rather than a casualty of it: it drops "
        "the column itself. Worth knowing about for exactly that reason."
    ),
    "retyped": (
        "The column is cast to another type here, so a change of type either "
        "fails outright or quietly changes what the cast produces."
    ),
    "select": (
        "The column is selected straight through, so {target} carries it and "
        "loses it on the same day."
    ),
    "star": (
        "A SELECT * carries this column onwards without naming it. Nothing "
        "fails here - {target} simply becomes one column narrower - and what "
        "breaks is whatever reads the missing column below."
    ),
}

_IMPACT_FALLBACK = (
    "The column is read here. Ripple could not work out what the statement "
    "does with it, so somebody has to look at this one."
)

_IMPACT_BY_CHANGE: dict[tuple[str, str], str] = {
    ("value_change", "filter"): (
        "This column decides which rows are kept. The values change, so the "
        "rows kept change with them - the statement goes on running and "
        "{target} quietly holds a different set of rows."
    ),
    ("value_change", "join_key"): (
        "Rows are matched on this column. New values match nothing on the "
        "other side, so rows are dropped silently - no error, just fewer rows."
    ),
    ("value_change", "transform"): (
        "The value is read inside a calculation here, so the calculation goes "
        "on running and returns something different for {target}."
    ),
    ("type_change", "filter"): (
        "This column decides which rows are kept, and the comparison here is "
        "written for the old type. Expect either an error or a filter that "
        "quietly stops matching."
    ),
    ("type_change", "join_key"): (
        "Rows are matched on this column. A join across two types either fails "
        "outright or matches nothing, and matching nothing is silent."
    ),
    ("type_change", "retyped"): (
        "The column is already cast here, and the cast is written for the old "
        "type. It fails, or it produces something different, with no error."
    ),
}


@dataclass
class SnippetLine:
    n: int
    t: str
    hit: bool

    def to_json(self) -> dict[str, Any]:
        return {"n": self.n, "t": self.t, "hit": self.hit}


@dataclass
class Finding:
    """One usage of one column, on one statement."""

    from_table: str
    column: str
    to_table: str
    keyed_table: str
    alias: str
    kind: str
    label: str
    mode: str
    impact: str
    breaking: bool
    no_local_fix: bool
    file: str
    lang: str
    lines: list[SnippetLine]
    hop: int
    certain: bool
    stmt_line: int
    roots: list[str] = field(default_factory=list)
    via_star: bool = False
    copied_by: str = ""
    built_as_text: str = ""
    feed: str = ""
    inferred_hops: int = 0

    def identity(self) -> tuple[str, str, str, str, str, int]:
        """What makes two findings the same finding.

        The statement's own first line is in here on purpose. One file very
        often builds several tables and filters on the same source column in
        each of them; keyed on file, table, column and kind alone, the second
        and third statements were folded into the first, so the row shown under
        a published table pointed at another statement's lines and the count of
        usages was quietly short. roots is deliberately NOT part of it: one
        usage can sit on the path of more than one attribute.
        """
        return (
            self.file,
            self.from_table,
            self.column,
            self.to_table,
            self.kind,
            self.stmt_line,
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "inter": self.to_table,
            "from": self.from_table,
            "attr": self.column,
            "roots": list(self.roots),
            "alias": self.alias,
            "logic": self.label,
            "mode": self.mode,
            "impact": self.impact,
            "breaking": self.breaking,
            "noLocalFix": self.no_local_fix,
            "file": self.file,
            "lang": self.lang,
            "lines": [line.to_json() for line in self.lines],
            "certain": self.certain,
            "viaStar": self.via_star,
            "copiedBy": self.copied_by,
            "builtAsText": self.built_as_text,
            "feed": self.feed,
            "inferredHops": self.inferred_hops,
        }


@dataclass
class CheckByHand:
    """One line somebody has to look at themselves, and why."""

    file: str
    line: int
    text: str
    why: str
    hint: str = ""
    mention_lines: int = 0
    score: int = 0

    def to_json(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "line": self.line,
            "text": self.text,
            "why": self.why,
            "hint": self.hint,
            "mentionLines": self.mention_lines,
            "score": self.score,
        }


@dataclass
class AttributeReport:
    table: str
    attr: str
    found: int = 0
    files: int = 0
    mentioned_in: int = 0
    reaches_production: bool = False
    ends_at: set[str] = field(default_factory=set)
    uncertain: int = 0
    name_in_tables: int = 0
    tables_read: int = 0
    cut_short_at: set[str] = field(default_factory=set)
    not_visible: set[str] = field(default_factory=set)
    inferred: int = 0
    lookup_failed: bool = False
    table_columns: list[str] = field(default_factory=list)
    reaching: list[list[dict[str, Any]]] = field(default_factory=list)
    ending: list[list[dict[str, Any]]] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return {
            "table": self.table,
            "attr": self.attr,
            "found": self.found,
            "files": self.files,
            "mentionedIn": self.mentioned_in,
            "reachesProduction": self.reaches_production,
            "endsAt": sorted(self.ends_at),
            "uncertain": self.uncertain,
            "nameInTables": self.name_in_tables,
            "tablesRead": self.tables_read,
            "cutShortAt": sorted(self.cut_short_at),
            "notVisible": sorted(self.not_visible),
            "inferred": self.inferred,
            "lookupFailed": self.lookup_failed,
            "tableColumns": list(self.table_columns),
        }

    def graph_json(self) -> dict[str, Any]:
        return {
            "table": self.table,
            "attr": self.attr,
            "reaching": _drop_prefixes(self.reaching),
            "ending": _drop_prefixes(self.ending),
        }


@dataclass
class Coverage:
    complete: bool
    gaps: list[dict[str, Any]]
    files_matched: int
    files_unread: int

    def to_json(self) -> dict[str, Any]:
        return {
            "complete": self.complete,
            "gaps": list(self.gaps),
            "filesMatched": self.files_matched,
            "filesUnread": self.files_unread,
        }


@dataclass
class Stats:
    production_tables: int = 0
    tables_reached: int = 0
    intermediate_tables: int = 0
    attributes_impacted: int = 0
    files_with_impact: int = 0
    breaking_usages: int = 0
    could_not_read: int = 0
    never_opened: int = 0
    tables_not_visible: int = 0
    inferred_findings: int = 0
    trails_cut_short: int = 0
    production_stops_loading: int = 0
    feeds_broken: int = 0

    def to_json(self) -> dict[str, Any]:
        return {
            "productionTables": self.production_tables,
            "tablesReached": self.tables_reached,
            "intermediateTables": self.intermediate_tables,
            "attributesImpacted": self.attributes_impacted,
            "filesWithImpact": self.files_with_impact,
            "breakingUsages": self.breaking_usages,
            "couldNotRead": self.could_not_read,
            "neverOpened": self.never_opened,
            "tablesNotVisible": self.tables_not_visible,
            "inferredFindings": self.inferred_findings,
            "trailsCutShort": self.trails_cut_short,
            "productionStopsLoading": self.production_stops_loading,
            "feedsBroken": self.feeds_broken,
        }


@dataclass
class ScanResult:
    attributes: list[AttributeReport] = field(default_factory=list)
    groups: list[dict[str, Any]] = field(default_factory=list)
    reached: list[dict[str, Any]] = field(default_factory=list)
    other: list[Finding] = field(default_factory=list)
    unreadable: list[CheckByHand] = field(default_factory=list)
    mentions_only: list[dict[str, Any]] = field(default_factory=list)
    held_online: list[str] = field(default_factory=list)
    path_too_long: list[str] = field(default_factory=list)
    star_tables: list[dict[str, Any]] = field(default_factory=list)
    cut_short: list[dict[str, Any]] = field(default_factory=list)
    merged_names: list[dict[str, Any]] = field(default_factory=list)
    wildcard_names: list[dict[str, Any]] = field(default_factory=list)
    named_by_file: list[dict[str, Any]] = field(default_factory=list)
    built_as_text: list[dict[str, Any]] = field(default_factory=list)
    two_definitions: list[dict[str, Any]] = field(default_factory=list)
    skipped_in_folders: int = 0
    skipped_folder_names: list[str] = field(default_factory=list)
    file_types_unopened: list[dict[str, Any]] = field(default_factory=list)
    stops_loading: list[dict[str, Any]] = field(default_factory=list)
    referenced_here: list[dict[str, Any]] = field(default_factory=list)
    feeds: list[dict[str, Any]] = field(default_factory=list)
    stops_loading_capped: bool = False
    max_hops: int = 0
    files_scanned: int = 0
    files_matched: int = 0
    risk: str = "none"
    lookup_failed: bool = False
    coverage: Coverage | None = None
    stats: Stats = field(default_factory=Stats)

    def findings(self) -> list[Finding]:
        """Every finding on the result, wherever it was filed."""
        seen: dict[tuple[str, str, str, str, str, int], Finding] = {}
        for group in self.groups + self.reached:
            for row in group.get("_findings", ()):
                seen[row.identity()] = row
        for row in self.other:
            seen[row.identity()] = row
        return list(seen.values())

    def to_json(self) -> dict[str, Any]:
        coverage = self.coverage or Coverage(True, [], 0, 0)
        return {
            "attributes": [a.to_json() for a in self.attributes],
            "groups": [_group_json(g) for g in self.groups],
            "reached": [_group_json(g) for g in self.reached],
            "other": [f.to_json() for f in self.other],
            "graphs": [a.graph_json() for a in self.attributes],
            "unreadable": [u.to_json() for u in self.unreadable],
            "mentionsOnly": list(self.mentions_only),
            "heldOnline": list(self.held_online),
            "pathTooLong": list(self.path_too_long),
            "starTables": list(self.star_tables),
            "cutShort": list(self.cut_short),
            "mergedNames": list(self.merged_names),
            "wildcardNames": list(self.wildcard_names),
            "namedByFile": list(self.named_by_file),
            "builtAsText": list(self.built_as_text),
            "twoDefinitions": list(self.two_definitions),
            "skippedInFolders": self.skipped_in_folders,
            "skippedFolderNames": list(self.skipped_folder_names),
            "fileTypesUnopened": list(self.file_types_unopened),
            "stopsLoading": list(self.stops_loading),
            "referencedHere": list(self.referenced_here),
            "feeds": list(self.feeds),
            "stopsLoadingCapped": self.stops_loading_capped,
            "maxHops": self.max_hops,
            "filesScanned": self.files_scanned,
            "filesMatched": self.files_matched,
            "risk": self.risk,
            "lookupFailed": self.lookup_failed,
            "coverage": coverage.to_json(),
            "stats": self.stats.to_json(),
        }


def settings_with_max_hops(cfg: Any, requested: int | None) -> Any:
    """A deeper scan is one scan, not a new setting.

    The settings screen keeps its number. This hands back a copy carrying the
    clamped one, so running a trail deeper does not quietly change every later
    scan.
    """
    if requested is None:
        return cfg
    wanted = max(HOP_FLOOR, min(HOP_CEILING, int(requested)))
    if wanted == int(cfg.max_hops):
        return cfg
    once = copy.copy(cfg)
    once.max_hops = wanted
    return once


def trace(
    index: Any,
    parsed: Any,
    upstream: list[dict[str, Any]],
    change_type: str,
    cfg: Any,
    on_progress: Callable[[str], None] | None = None,
) -> ScanResult:
    """Follow every attribute out of its table and say what could not be followed."""
    catalog = build_catalog(parsed)
    max_hops = max(HOP_FLOOR, int(cfg.max_hops))
    texts = {source.path: source.text for source in index.files}

    walk = _Walk(
        parsed=parsed,
        catalog=catalog,
        cfg=cfg,
        change_type=change_type,
        max_hops=max_hops,
        texts=texts,
        on_progress=on_progress,
        # Worked out once. Every table on every hop asks whether it is
        # published, and turning a pasted list back into a rule each time would
        # be the most expensive thing in the walk.
        prod_rule=_production_rule(cfg),
    )

    names: list[str] = []
    for entry in upstream:
        for attr in entry.get("attrs", ()):
            attr = str(attr).strip()
            if attr and attr not in names:
                names.append(attr)

    reports: list[AttributeReport] = []
    for entry in upstream:
        table = str(entry.get("table", "")).strip()
        for attr in entry.get("attrs", ()):
            attr = str(attr).strip()
            if not table or not attr:
                continue
            _say(on_progress, "Following " + attr + " out of " + table)
            report = AttributeReport(table=table, attr=attr)
            walk.seed(table, attr, report)
            reports.append(report)

    result = ScanResult()
    result.attributes = reports
    result.max_hops = max_hops
    result.files_scanned = _files_scanned(index)
    result.held_online = [str(name) for name in _index_field(index, "held_online") or ()]
    result.path_too_long = [
        str(name) for name in _index_field(index, "path_too_long", "too_long") or ()
    ]
    result.skipped_in_folders = _count_of(
        _index_field(index, "skipped_in_folders", "in_skipped_dirs")
    )
    result.skipped_folder_names = sorted(
        str(name)
        for name in _index_field(index, "skipped_folder_names", "skipped_dir_names")
        or ()
    )
    result.file_types_unopened = _file_types_unopened(index)
    result.cut_short = list(walk.cut_short)
    result.star_tables = list(walk.star_tables)
    result.feeds = list(walk.feeds)
    result.built_as_text = list(walk.built_as_text)
    result.named_by_file = sorted(
        walk.named_by_file.values(), key=lambda row: (row["table"], row["file"])
    )
    result.merged_names = sorted(walk.merged.values(), key=lambda row: row["table"])
    result.wildcard_names = sorted(
        walk.wildcards.values(), key=lambda row: (row["table"], row["pattern"])
    )
    result.other = list(walk.other.values())
    result.two_definitions = _two_definitions(parsed)
    all_findings = walk.all_findings()

    _say(on_progress, "Sorting what was found")
    groups, reached = walk.destinations()
    result.groups = groups
    result.reached = reached

    # The tables already named above, so the staleness walk does not report
    # anything twice: saying it twice under two headings reads as two problems.
    reported = {str(g["prod"]) for g in groups} | {str(r["table"]) for r in reached}

    _say(on_progress, "Checking which tables stop being refreshed")
    stops, capped = walk.stops_loading(reported)
    result.stops_loading = stops
    result.stops_loading_capped = capped

    # Worked out BEFORE the honesty lists: a file accounted for here belongs on
    # this card and on no other, or one statement reads as two problems.
    result.referenced_here = walk.referenced_here(names)
    accounted = {str(row["file"]) for row in result.referenced_here}

    _say(on_progress, "Checking the files that only mention the name")
    check_by_hand, mentions_only, matched_paths = walk.honest_half(
        names, accounted, {f.file for f in all_findings}
    )
    result.mentions_only = mentions_only
    result.files_matched = len(matched_paths)

    check_by_hand.extend(walk.chain_may_carry_on(check_by_hand, accounted))

    # Sorted last, after everything has been added to it, because it is only
    # worth something for as long as somebody reads to the bottom of it.
    for item in check_by_hand:
        item.score = walk.score(item, matched_paths)
    check_by_hand.sort(key=lambda item: (-item.score, item.file, item.line))
    result.unreadable = check_by_hand

    _finish_reports(walk, reports, all_findings)

    unread_paths = walk.unreadable_paths()
    never_opened = {path for path in unread_paths if path not in texts}
    result.stats = _stats(
        walk,
        groups,
        reached,
        reports,
        all_findings,
        stops,
        unread_paths,
        never_opened,
    )
    result.coverage = _coverage(result, unread_paths, never_opened, matched_paths)
    subject_gap = _subject_gap(
        result, unread_paths, never_opened, matched_paths, all_findings
    )
    result.risk = _risk(all_findings, result, subject_gap)
    result.lookup_failed = _scan_lookup_failed(
        reports, all_findings, result, subject_gap
    )
    _say(on_progress, "Done")
    return result


@dataclass
class _Walk:
    """The state one scan builds up while it walks."""

    parsed: Any
    catalog: Catalog
    cfg: Any
    change_type: str
    max_hops: int
    texts: dict[str, str]
    on_progress: Callable[[str], None] | None
    prod_rule: ProductionRule = field(default_factory=ProductionRule)
    kept: dict[tuple, Finding] = field(default_factory=dict)
    other: dict[tuple, Finding] = field(default_factory=dict)
    dest_rows: dict[str, dict[tuple, Finding]] = field(default_factory=dict)
    dest_prod: dict[str, bool] = field(default_factory=dict)
    dest_cut: dict[str, bool] = field(default_factory=dict)
    cut_short: list[dict[str, Any]] = field(default_factory=list)
    star_tables: list[dict[str, Any]] = field(default_factory=list)
    feeds: list[dict[str, Any]] = field(default_factory=list)
    built_as_text: list[dict[str, Any]] = field(default_factory=list)
    named_by_file: dict[str, dict[str, Any]] = field(default_factory=dict)
    merged: dict[str, dict[str, Any]] = field(default_factory=dict)
    wildcards: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)
    broken_targets: dict[str, str] = field(default_factory=dict)
    stood_on: set[str] = field(default_factory=set)
    stood_on_shown: set[str] = field(default_factory=set)
    table_columns_cache: dict[str, list[str]] = field(default_factory=dict)

    # ---- the walk -------------------------------------------------------

    def is_production(self, table: str) -> bool:
        """Is this one of the tables the team publishes.

        production.py answers this against a parsed rule rather than against
        the settings object, so the rule is read once when the walk is built
        and asked here.
        """
        if not table:
            return False
        return bool(matches(self.prod_rule, table))

    def seed(self, table: str, attr: str, report: AttributeReport) -> None:
        """Start one attribute off from the table the reader typed."""
        self.note_merged_seed(table)
        node = {
            "name": table,
            "kind": "source",
            "alias": "",
            "prod": self.is_production(table),
        }
        self.follow(
            keyed=table,
            shown=table,
            column=attr,
            roots=[attr],
            hop=0,
            seen=frozenset(),
            route=[],
            nodes=[node],
            report=report,
            inferred_hops=0,
        )

    def follow(
        self,
        keyed: str,
        shown: str,
        column: str,
        roots: list[str],
        hop: int,
        seen: frozenset,
        route: list[Finding],
        nodes: list[dict[str, Any]],
        report: AttributeReport,
        inferred_hops: int,
    ) -> tuple[bool, bool]:
        """Returns (anything recorded, the hop limit is what stopped it).

        Every caller passes the second one up. Without it the screen reads "the
        chain ends at t4, it does not reach production", which is a setting
        reported as a fact about somebody's pipeline.
        """
        step = (keyed.lower(), column.lower())
        if step in seen:
            return False, False
        seen = seen | {step}
        self.stood_on.add(keyed)
        self.stood_on_shown.add(shown)

        recorded = False
        cut = False
        for stmt, certain_source, wildcard in self.readers_of(keyed, shown):
            # The KEYED name, not the one shown. usages_of asks which table a
            # bare column belongs to, and in a real warehouse the same two or
            # three key columns are on nearly every table - answering with the
            # display name would hand it a temporary table's stripped name and
            # match another file's table of that name.
            usages = usages_of(stmt, column, keyed)
            if not usages:
                continue
            if wildcard is not None:
                # Only the wildcards that actually produced a finding: the card
                # says "the usages below are real", and it was being printed
                # over an empty list.
                self.note_wildcard(shown, wildcard[0], wildcard[1])

            target_keyed = (stmt.target or "").strip()
            target_shown = display_table(target_keyed) if target_keyed else ""
            rows: list[Finding] = []
            breaking_here = False
            for usage in usages:
                finding = self.make_finding(
                    stmt=stmt,
                    source=shown,
                    column=column,
                    target_shown=target_shown,
                    target_keyed=target_keyed,
                    usage=usage,
                    roots=roots,
                    hop=hop,
                    certain_source=certain_source,
                    inferred_hops=inferred_hops,
                )
                rows.append(self.remember(finding, roots))
                recorded = True
                if finding.breaking:
                    breaking_here = True
                if usage.via_star or usage.kind == "star":
                    self.note_star(stmt, shown, target_shown, column, roots)

            if breaking_here and target_keyed:
                self.broken_targets[target_keyed] = target_shown
            if stmt.export_uri:
                self.note_feed(stmt, shown, roots, rows)
            if stmt.built_as_text:
                self.note_built_as_text(stmt)
            if stmt.named_by and target_shown:
                self.note_named_by_file(stmt, target_shown)

            if not target_keyed:
                # Real usages in code that builds no table Ripple can name.
                for row in rows:
                    self.other[row.identity()] = row
                continue

            star_here = any(u.via_star or u.kind == "star" for u in usages)
            deeper_inferred = inferred_hops + (1 if star_here else 0)
            route2 = route + rows
            prod = self.is_production(target_shown)
            node = {
                "name": target_shown,
                "kind": rows[0].kind if rows else "select",
                "alias": rows[0].alias if rows else "",
                "prod": prod,
            }
            if star_here:
                node["inferred"] = True
                node["how"] = stmt.whole_copy or ""
            nodes2 = nodes + [node]

            if prod:
                # Record it AND keep going: one published table feeding another
                # is exactly how a change spreads.
                report.reaches_production = True
                self.destination(target_shown, prod=True, cut=False, route=route2)
                report.reaching.append(nodes2)

            went_on = False
            for out_name in self.outgoing(stmt, column, usages):
                if hop + 1 > self.max_hops:
                    self.cut_short.append(
                        {
                            "table": target_shown,
                            "attr": out_name,
                            "hop": hop + 1,
                            "roots": list(roots),
                        }
                    )
                    report.cut_short_at.add(target_shown)
                    cut = True
                    went_on = True
                    cut_node = dict(node)
                    cut_node["cut"] = True
                    self.destination(target_shown, prod=prod, cut=True, route=route2)
                    if not prod:
                        report.ending.append(nodes + [cut_node])
                    continue
                sub_recorded, sub_cut = self.follow(
                    keyed=target_keyed,
                    shown=target_shown,
                    column=out_name,
                    roots=roots,
                    hop=hop + 1,
                    seen=seen,
                    route=route2,
                    nodes=nodes2,
                    report=report,
                    inferred_hops=deeper_inferred,
                )
                cut = cut or sub_cut
                if sub_recorded:
                    went_on = True

            if not went_on and not prod:
                # Nothing further is built from this table, so the chain really
                # ends here. Record it - dropping these was how a real breaking
                # impact got shown as a clean result.
                self.destination(target_shown, prod=False, cut=False, route=route2)
                report.ends_at.add(target_shown)
                report.ending.append(nodes2)

        return recorded, cut

    def readers_of(
        self, keyed: str, shown: str
    ) -> list[tuple[Any, bool, tuple[str, str] | None]]:
        """Every statement that reads this table, keyed name only.

        Looking the table up by the name shown on screen would match every
        other file's temporary table of the same name, and an unrelated
        published table would reappear here worded as certainly as anywhere
        else.
        """
        out: list[tuple[Any, bool, tuple[str, str] | None]] = []
        for stmt in self.parsed.statements:
            certain = True
            hit = False
            wildcard: tuple[str, str] | None = None
            for source in stmt.sources:
                source = str(source)
                # The wildcard is asked FIRST. same_table already answers yes
                # for a wildcard that covers the name, so asking it first
                # swallows every wildcard read: the card listing them prints
                # over an empty list, and a family match - a guess about what
                # somebody meant - ships worded as certainly as a read of the
                # SQL.
                how = _wildcard_match(source, keyed)
                if how:
                    hit = True
                    # A shard match is a fact about the SQL and stays certain.
                    # A family match is a guess about what somebody meant.
                    certain = how not in ("family", "both")
                    wildcard = (source, how)
                    break
                if same_table(source, keyed):
                    hit = True
                    if source != keyed:
                        self.note_merged(shown, source, keyed)
                    break
            if hit:
                out.append((stmt, certain, wildcard))
        return out

    def outgoing(self, stmt: Any, column: str, usages: list[Any]) -> list[str]:
        """Every name the column leaves this statement under."""
        names: list[str] = []
        for name in _merge_outputs(stmt, column):
            if name and name not in names:
                names.append(name)
        for usage in usages:
            if usage.kind not in CARRYING_KINDS:
                continue
            name = usage.alias or usage.column or column
            if name and name not in names:
                names.append(name)
        return names

    def remember(self, finding: Finding, roots: list[str]) -> Finding:
        key = finding.identity()
        kept = self.kept.get(key)
        if kept is None:
            self.kept[key] = finding
            return finding
        # One usage can be on the path of more than one attribute, so the roots
        # accumulate on the finding that is already there.
        for root in roots:
            if root not in kept.roots:
                kept.roots.append(root)
        return kept

    def destination(
        self, shown: str, prod: bool, cut: bool, route: list[Finding]
    ) -> None:
        if not shown:
            return
        rows = self.dest_rows.setdefault(shown, {})
        for row in route:
            rows[row.identity()] = row
        self.dest_prod[shown] = self.dest_prod.get(shown, False) or prod
        self.dest_cut[shown] = self.dest_cut.get(shown, False) or cut

    def destinations(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Published tables and the tables the chain ends at, worst first."""
        groups: list[dict[str, Any]] = []
        reached: list[dict[str, Any]] = []
        for name, rows in self.dest_rows.items():
            findings = list(rows.values())
            inferred = [f for f in findings if f.inferred_hops or f.via_star]
            if self.dest_prod.get(name):
                note = ""
                if inferred and len(inferred) == len(findings):
                    note = (
                        "Every row here was worked out through a SELECT *, so "
                        "the column list was not read"
                    )
                groups.append(
                    {
                        "prod": name,
                        "note": note,
                        "rows": [f.to_json() for f in findings],
                        "_findings": findings,
                    }
                )
                continue
            if self.dest_cut.get(name):
                note = (
                    "Ripple stopped following here, the hop limit was reached, "
                    "so this is not where the chain ends"
                )
            else:
                note = "The chain ends here - nothing else read reads this table"
            reached.append(
                {
                    "table": name,
                    "note": note,
                    "cut": bool(self.dest_cut.get(name)),
                    "rows": [f.to_json() for f in findings],
                    "_findings": findings,
                }
            )
        # Worst first, then by name: on a real repository this list is hundreds
        # of tables long and the alphabet is no way to decide what is read first.
        groups.sort(key=lambda g: (-len(g["rows"]), str(g["prod"])))
        reached.sort(key=lambda r: (-len(r["rows"]), str(r["table"])))
        return groups, reached

    def all_findings(self) -> list[Finding]:
        rows = dict(self.kept)
        rows.update(self.other)
        return list(rows.values())

    # ---- the notes the walk leaves behind --------------------------------

    def make_finding(
        self,
        stmt: Any,
        source: str,
        column: str,
        target_shown: str,
        target_keyed: str,
        usage: Any,
        roots: list[str],
        hop: int,
        certain_source: bool,
        inferred_hops: int,
    ) -> Finding:
        kind = str(usage.kind)
        breaking = kind in BREAKS.get(self.change_type, BREAKS["unknown"])
        no_local_fix = breaking and kind in NO_LOCAL_FIX_KINDS and self.change_type in (
            "removal",
            "rename",
        )
        feed = stmt.export_uri or ""
        text = self.texts.get(stmt.file, "")
        return Finding(
            from_table=source,
            column=column,
            to_table=target_shown,
            keyed_table=target_keyed,
            alias=usage.alias or "",
            kind=kind,
            label=KIND_LABELS.get(kind, kind),
            mode=self.change_type,
            impact=_impact(kind, self.change_type, target_shown, feed),
            breaking=breaking,
            no_local_fix=no_local_fix,
            file=stmt.file,
            lang=stmt.lang,
            lines=_snippet(text, stmt, column),
            hop=hop,
            certain=bool(usage.certain) and certain_source and not usage.via_star,
            stmt_line=int(stmt.line_offset),
            roots=list(roots),
            via_star=bool(usage.via_star) or kind == "star",
            copied_by=stmt.whole_copy or "",
            built_as_text=stmt.built_as_text or "",
            feed=feed,
            inferred_hops=inferred_hops + (1 if usage.via_star or kind == "star" else 0),
        )

    def note_star(
        self, stmt: Any, source: str, target_shown: str, column: str, roots: list[str]
    ) -> None:
        entry = {
            "table": target_shown,
            "file": stmt.file,
            "from": source,
            "attr": column,
            "roots": list(roots),
            "how": stmt.whole_copy or "",
            "filledIn": bool(stmt.star_note),
        }
        for seen in self.star_tables:
            if seen["table"] == entry["table"] and seen["file"] == entry["file"]:
                return
        self.star_tables.append(entry)

    def note_feed(
        self, stmt: Any, source: str, roots: list[str], rows: list[Finding]
    ) -> None:
        breaking = any(row.breaking for row in rows)
        for seen in self.feeds:
            if seen["uri"] == stmt.export_uri and seen["file"] == stmt.file:
                for root in roots:
                    if root not in seen["attrs"]:
                        seen["attrs"].append(root)
                seen["breaking"] = seen["breaking"] or breaking
                return
        self.feeds.append(
            {
                "uri": stmt.export_uri,
                "file": stmt.file,
                "line": int(stmt.line_offset),
                "from": source,
                "attrs": list(roots),
                "breaking": breaking,
            }
        )

    def note_built_as_text(self, stmt: Any) -> None:
        entry = {
            "file": stmt.file,
            "line": int(stmt.line_offset),
            "how": stmt.built_as_text,
            "table": display_table(stmt.target) if stmt.target else "",
        }
        for seen in self.built_as_text:
            if seen["file"] == entry["file"] and seen["line"] == entry["line"]:
                return
        self.built_as_text.append(entry)

    def note_named_by_file(self, stmt: Any, table: str) -> None:
        self.named_by_file.setdefault(
            table, {"table": table, "file": stmt.file, "how": stmt.named_by}
        )

    def note_wildcard(self, table: str, pattern: str, how: str) -> None:
        entry = self.wildcards.setdefault(
            (table, pattern),
            {
                "table": table,
                "pattern": pattern,
                "how": how,
                # Only the patterns that matched because the family name was
                # typed without the separator BigQuery wants.
                "shorthand": [pattern] if how in ("family", "both") else [],
            },
        )
        entry["how"] = how

    def note_merged(self, shown: str, source: str, keyed: str) -> None:
        """Two spellings this repository uses for what may be two tables."""
        reason = _merge_reason(source, keyed)
        if not reason:
            return
        entry = self.merged.setdefault(
            shown,
            {"table": shown, "reason": reason, "spellings": [], "datasets": []},
        )
        for name in (source, keyed):
            if name not in entry["spellings"]:
                entry["spellings"].append(name)
            dataset = _dataset(name)
            if dataset and dataset not in entry["datasets"]:
                entry["datasets"].append(dataset)

    def note_merged_seed(self, table: str) -> None:
        """Say nothing about the name a person typed unless the repository
        really does hold it in more than one dataset.

        Somebody typing a table name without its dataset is not an ambiguity in
        the warehouse, and flagging it would put a warning on every scan.
        """
        if _dataset(table):
            return
        short = _short(table).lower()
        datasets: list[str] = []
        for name in self.every_table_name():
            if _short(name).lower() != short:
                continue
            dataset = _dataset(name)
            if dataset and dataset not in datasets:
                datasets.append(dataset)
        if len(datasets) > 1:
            self.merged[table] = {
                "table": table,
                "reason": "dataset",
                "spellings": [table],
                "datasets": sorted(datasets),
            }

    def every_table_name(self) -> set[str]:
        names: set[str] = set()
        for stmt in self.parsed.statements:
            if stmt.target:
                names.add(str(stmt.target))
            for source in stmt.sources:
                names.add(str(source))
        return names

    # ---- the second kind of impact --------------------------------------

    def stops_loading(self, reported: set[str]) -> tuple[list[dict[str, Any]], bool]:
        """Published tables that stop being refreshed rather than breaking.

        A column used only in a WHERE never reaches the table the statement
        builds, so the trail for the column ends there and saying so is right.
        The statement still stops working, so the table stops being rebuilt and
        every published table under it serves yesterday's numbers with no error.
        """
        edges: dict[str, set[str]] = {}
        for stmt in self.parsed.statements:
            target = (stmt.target or "").strip()
            if not target:
                continue
            for source in stmt.sources:
                edges.setdefault(str(source).lower(), set()).add(target)

        out: list[dict[str, Any]] = []
        named: set[str] = set()
        visited_total = 0
        capped = False
        for because_keyed in sorted(self.broken_targets):
            because = self.broken_targets[because_keyed] or display_table(because_keyed)
            frontier: list[tuple[str, list[str]]] = [(because_keyed, [because])]
            seen: set[str] = {because_keyed.lower()}
            depth = 0
            while frontier and depth < self.max_hops and not capped:
                depth += 1
                nxt: list[tuple[str, list[str]]] = []
                for table, path in frontier:
                    for child in sorted(edges.get(table.lower(), ())):
                        if child.lower() in seen:
                            continue
                        seen.add(child.lower())
                        visited_total += 1
                        if visited_total > STOPS_LOADING_CAP:
                            capped = True
                            break
                        child_shown = display_table(child)
                        route = path + [child_shown]
                        if (
                            self.is_production(child_shown)
                            and child_shown not in reported
                            and child_shown not in named
                        ):
                            named.add(child_shown)
                            out.append(
                                {
                                    "prod": child_shown,
                                    "because": because,
                                    "via": route,
                                }
                            )
                        nxt.append((child, route))
                    if capped:
                        break
                frontier = nxt
        out.sort(key=lambda row: (str(row["prod"]), str(row["because"])))
        return out, capped

    # ---- the honest half -------------------------------------------------

    def referenced_here(self, names: list[str]) -> list[dict[str, Any]]:
        """Index, policy and UNDROP DDL naming a table the chain stood on, or a
        column being followed.

        Narrow on purpose: every warehouse is full of indexes on tables this
        scan never heard of, and listing those buries the ones that matter.
        None of this is lineage - it may add a row, it must never move a chain.
        """
        wanted_tables = {t.lower() for t in self.stood_on_shown}
        wanted_tables |= {display_table(t).lower() for t in self.stood_on}
        wanted_columns = {n.lower() for n in names}
        out: list[dict[str, Any]] = []
        for ref in self.parsed.references:
            table = str(ref.table or "")
            columns = [str(c) for c in (ref.columns or ())]
            names_columns = [c for c in columns if c.lower() in wanted_columns]
            if display_table(table).lower() not in wanted_tables and not names_columns:
                continue
            # The reader records one line of the statement and the kind in the
            # SQL's own capitals. The screen prints plain words and the line
            # itself, so both are made here rather than asked of a field the
            # reader does not keep.
            line_text = str(getattr(ref, "text", "") or "")
            out.append(
                {
                    "kind": _reference_words(str(ref.kind or "")),
                    "table": display_table(table) if table else "",
                    "file": ref.file,
                    "line": int(ref.line),
                    "snippet": line_text,
                    "verb": _leading_verb(line_text),
                    "columns": columns,
                    "namesColumns": names_columns,
                }
            )
        out.sort(key=lambda row: (str(row["file"]), int(row["line"])))
        return out

    def honest_half(
        self, names: list[str], accounted: set[str], with_findings: set[str]
    ) -> tuple[list[CheckByHand], list[dict[str, Any]], set[str]]:
        """Every file the word search matched, told apart three ways."""
        check: list[CheckByHand] = []
        mentions_only: list[dict[str, Any]] = []
        matched: set[str] = set()

        by_file: dict[str, list[Any]] = {}
        for stmt in self.parsed.statements:
            by_file.setdefault(stmt.file, []).append(stmt)

        unread = self.unreadable_paths()
        for path in sorted(set(self.texts) | unread):
            text = self.texts.get(path, "")
            hits = [name for name in names if text and _mentions(text, name)]
            if not hits and path not in unread:
                continue
            if hits:
                matched.add(path)
            if path in accounted:
                # Already on the referenced-here card. One statement counted
                # twice reads as two separate problems.
                continue

            line, snippet, count = self.text_mentions(path, by_file.get(path, ()), hits)
            if count:
                check.append(
                    CheckByHand(
                        file=path,
                        line=line,
                        text=snippet,
                        why=(
                            "The name is written here as text, on "
                            + str(count)
                            + (" line" if count == 1 else " lines")
                            + ". Fixing the findings does not fix this - the "
                            "text still says the old name"
                        ),
                        hint=self.metadata_hint(by_file.get(path, ()), hits),
                        mention_lines=count,
                    )
                )
                continue
            if path in unread:
                first_line, first_text = self.unreadable_line(path)
                if hits:
                    why = (
                        "This file mentions the name, but Ripple could not read "
                        "it as SQL - check by hand"
                    )
                elif path not in self.texts:
                    why = (
                        "Ripple never opened this file, so nothing can say "
                        "whether it mentions the name - check by hand"
                    )
                else:
                    why = "Ripple could not read this file as SQL - check by hand"
                check.append(
                    CheckByHand(file=path, line=first_line, text=first_text, why=why)
                )
                continue
            if hits and path not in with_findings:
                # mentionsOnly is the reassuring case - the name appears and
                # carries nowhere - so a file that produced a finding is not
                # one of them.
                mentions_only.append(
                    {"file": path, "lines": self.mention_count(path, hits)}
                )
        mentions_only.sort(key=lambda row: str(row["file"]))
        return check, mentions_only, matched

    def text_mentions(
        self, path: str, statements: Any, hits: list[str]
    ) -> tuple[int, str, int]:
        """How many LINES of this file name the column as text, and the first.

        A real file sets one tag per column and runs to sixty of them, so a
        report naming one line sends somebody to fix one line out of sixty.
        """
        if not hits:
            return 0, "", 0
        quoted = self.quoted_in_tree(statements, hits) or self.named_in_opaque(path, hits)
        if not quoted:
            return 0, "", 0
        text = self.texts.get(path, "")
        first_line = 0
        first_text = ""
        count = 0
        for number, line in enumerate(text.splitlines(), start=1):
            if any(_quoted_mention(line, name) for name in hits):
                count += 1
                if not first_line:
                    first_line = number
                    first_text = line.strip()
        if not count:
            # The parser saw it as a string but the text is spread over lines;
            # report the statement rather than pretending to a line count.
            return 0, "", 0
        return first_line, first_text, count

    def quoted_in_tree(self, statements: Any, hits: list[str]) -> bool:
        for stmt in statements:
            if stmt.expr is None:
                continue
            for literal in stmt.expr.find_all(exp.Literal):
                if not literal.is_string:
                    continue
                value = str(literal.this)
                if any(_mentions(value, name) for name in hits):
                    return True
        return False

    def named_in_opaque(self, path: str, hits: list[str]) -> bool:
        for chunk in self.parsed.opaque.get(path, ()):
            body = str(chunk.get("sql", "")) + "\n" + str(chunk.get("text", ""))
            if any(_mentions(body, name) for name in hits):
                return True
        return False

    def metadata_hint(self, statements: Any, hits: list[str]) -> str:
        """The INFORMATION_SCHEMA hint, asked of the parse tree.

        A metadata view is deliberately never recorded as a source, so the
        Statement's sources cannot answer this, and the old hint - "which is
        how in-house helpers take a column or table name" - named a cause
        nobody could find.
        """
        for stmt in statements:
            if stmt.expr is None:
                continue
            for table in stmt.expr.find_all(exp.Table):
                whole = ".".join(
                    part for part in (table.catalog, table.db, table.name) if part
                )
                if "information_schema" in whole.lower():
                    return (
                        "This statement looks the name up in the warehouse's own "
                        "catalogue, which is correct code doing what it should"
                    )
        return ""

    def mention_count(self, path: str, hits: list[str]) -> int:
        text = self.texts.get(path, "")
        count = 0
        for line in text.splitlines():
            if any(_mentions(line, name) for name in hits):
                count += 1
        return count

    def chain_may_carry_on(
        self, already: list[CheckByHand], accounted: set[str]
    ) -> list[CheckByHand]:
        """Statements Ripple could not understand that name a table the chain
        actually stood on.

        The file parses, the readable statements in it produce findings, and
        the one statement that carries the chain onwards is simply absent.
        Deliberately narrow: every pipeline is full of DECLAREs and CALLs that
        carry no lineage, and reporting those buries this list.
        """
        listed = {item.file for item in already} | set(accounted)
        wanted = {display_table(t).lower() for t in self.stood_on}
        wanted |= {t.lower() for t in self.stood_on_shown}
        out: list[CheckByHand] = []
        for path in sorted(self.parsed.opaque):
            if path in listed:
                continue
            for chunk in self.parsed.opaque.get(path, ()):
                body = str(chunk.get("sql", "")) + "\n" + str(chunk.get("text", ""))
                named = [name for name in wanted if name and _mentions(body, name)]
                if not named:
                    continue
                out.append(
                    CheckByHand(
                        file=path,
                        line=int(chunk.get("line", 0)),
                        text=str(chunk.get("text", "")).strip(),
                        why=(
                            "Ripple could not read this statement, and it names "
                            + sorted(named)[0]
                            + " - a table on this trail"
                        ),
                        hint="The chain may carry on inside this statement",
                    )
                )
                listed.add(path)
                break
        return out

    def score(self, item: CheckByHand, matched: set[str]) -> int:
        """Worst first. Left alphabetical, what somebody reads first is decided
        by the first letter of a filename: twelve config files above the one
        genuinely broken query, because that query's file started with a z."""
        score = 0
        if item.file in matched:
            score += 4
        lower = item.file.lower()
        if any(lower.endswith(ext) for ext in QUERY_EXTENSIONS):
            score += 2
        text = self.texts.get(item.file)
        if text is None:
            # Never opened, so nothing can say what is in it, which is the
            # whole problem with it.
            score += 1
        elif any(word in text.lower() for word in SQL_WORDS):
            score += 1
        return score

    def unreadable_paths(self) -> set[str]:
        paths = {_unreadable_file(entry) for entry in self.parsed.unreadable}
        paths.discard("")
        return paths

    def unreadable_line(self, path: str) -> tuple[int, str]:
        for entry in self.parsed.unreadable:
            if _unreadable_file(entry) == path:
                return int(getattr(entry, "line", 0) or 0), str(
                    getattr(entry, "text", "") or ""
                ).strip()
        return 0, ""

    def columns_seen_on(self, table: str) -> list[str]:
        """Every column Ripple saw written down against this table.

        Taken from the statements that build it and from the statements that
        read only it, because nothing in a repository ever builds a source
        table - its columns are only written down by the queries that read it.
        Worked out only when a lookup has actually failed, and once per table:
        it walks every statement.
        """
        cached = self.table_columns_cache.get(table)
        if cached is not None:
            return cached
        columns: list[str] = list(self.catalog.columns_of(table))
        for stmt in self.parsed.statements:
            sources = {str(s) for s in stmt.sources}
            if len(sources) != 1:
                continue
            only = sources.pop()
            if not same_table(only, table):
                continue
            if stmt.expr is None:
                continue
            for column in stmt.expr.find_all(exp.Column):
                name = column.name
                if name and name not in columns:
                    columns.append(name)
        columns.sort(key=lambda name: name.lower())
        self.table_columns_cache[table] = columns
        return columns


def _finish_reports(
    walk: _Walk,
    reports: list[AttributeReport],
    all_findings: list[Finding],
) -> None:
    tables_read = len(walk.catalog.tables)
    not_visible_tables = walk.catalog.gap_tables() | {
        str(entry["table"]) for entry in walk.star_tables
    }
    for report in reports:
        mine = [f for f in all_findings if report.attr in f.roots]
        report.found = len(mine)
        report.files = len({f.file for f in mine})
        report.uncertain = len([f for f in mine if not f.certain])
        report.inferred = len([f for f in mine if f.inferred_hops])
        report.name_in_tables = len(walk.catalog.tables_naming(report.attr))
        report.tables_read = tables_read
        report.mentioned_in = len(
            [path for path, text in walk.texts.items() if _mentions(text, report.attr)]
        )
        touched = {f.to_table for f in mine} | {f.from_table for f in mine}
        touched |= report.ends_at | report.cut_short_at
        report.not_visible = {t for t in touched if t and t in not_visible_tables}
        # endsAt must never hold a table the limit stopped at: a branch Ripple
        # gave up on has not ended.
        report.ends_at -= report.cut_short_at
        report.lookup_failed = not mine and report.name_in_tables == 0
        if report.lookup_failed:
            report.table_columns = walk.columns_seen_on(report.table)


def _stats(
    walk: _Walk,
    groups: list[dict[str, Any]],
    reached: list[dict[str, Any]],
    reports: list[AttributeReport],
    all_findings: list[Finding],
    stops: list[dict[str, Any]],
    unread_paths: set[str],
    never_opened: set[str],
) -> Stats:
    ends = {str(g["prod"]) for g in groups} | {str(r["table"]) for r in reached}
    passed_through = {f.to_table for f in all_findings if f.to_table} - ends
    not_visible: set[str] = set()
    for report in reports:
        not_visible |= report.not_visible
    return Stats(
        production_tables=len(groups),
        tables_reached=len(reached),
        intermediate_tables=len(passed_through),
        # Confirmed attributes, not every column name a finding touches: a
        # column renamed twice on the way down is one attribute.
        attributes_impacted=len([r for r in reports if r.found]),
        files_with_impact=len({f.file for f in all_findings}),
        breaking_usages=len([f for f in all_findings if f.breaking]),
        could_not_read=len(unread_paths),
        never_opened=len(never_opened),
        tables_not_visible=len(not_visible),
        inferred_findings=len([f for f in all_findings if f.inferred_hops]),
        trails_cut_short=len(walk.cut_short),
        # Three different kinds of impact, kept apart: one number covering more
        # than one of them is a number that means none of them.
        production_stops_loading=len(stops),
        feeds_broken=len([f for f in walk.feeds if f["breaking"]]),
    )


def _coverage(
    result: ScanResult,
    unread_paths: set[str],
    never_opened: set[str],
    matched: set[str],
) -> Coverage:
    """Counts of what Ripple already worked out and must not throw away.

    Not a percentage: there is no honest denominator for how much of a trail
    exists, and a made-up one puts a precise number on a guess.
    """
    counted: list[tuple[int, str]] = [
        (len(unread_paths), "files Ripple could not read"),
        (len(never_opened), "files Ripple never opened at all"),
        (
            len(result.star_tables),
            "tables whose column list is written down nowhere",
        ),
        (len(result.cut_short), "trails Ripple stopped following at the hop limit"),
        (
            result.stats.inferred_findings,
            "findings that sit past a table Ripple could not see inside",
        ),
        (
            len(result.merged_names),
            "names this repository uses for more than one table",
        ),
        (
            len(result.named_by_file),
            "tables named after the file that builds them rather than in it",
        ),
        (
            result.skipped_in_folders,
            "code files Ripple walked past because of the folder they sit in",
        ),
        (
            sum(int(row["count"]) for row in result.file_types_unopened),
            "files of a type Ripple does not open at all",
        ),
    ]
    gaps = [{"count": count, "what": what} for count, what in counted if count]
    return Coverage(
        complete=not gaps,
        gaps=gaps,
        files_matched=len(matched),
        files_unread=len(matched & unread_paths) + len(never_opened),
    )


def _subject_gap(
    result: ScanResult,
    unread_paths: set[str],
    never_opened: set[str],
    matched: set[str],
    all_findings: list[Finding],
) -> bool:
    """Something on the subject of this scan went unread.

    Narrow on purpose: every real pipeline has some file the reader cannot make
    sense of, and a badge that says "not sure" on every scan ever run is one
    nobody reads.
    """
    if matched & unread_paths:
        return True
    if never_opened:
        return True
    if result.held_online or result.path_too_long:
        return True
    if result.file_types_unopened:
        return True
    if result.skipped_in_folders and not all_findings:
        # A folder Ripple was told to skip is exactly as unread as a file it
        # could not open. Only when nothing was found: skipping build, dist and
        # target is ordinary.
        return True
    return False


def _risk(all_findings: list[Finding], result: ScanResult, subject_gap: bool) -> str:
    if any(f.no_local_fix for f in all_findings):
        return "high"
    if any(f.breaking for f in all_findings):
        return "medium"
    if all_findings:
        return "low"
    if subject_gap:
        # "I found nothing" and "I could not look" are not the same answer.
        return "unknown"
    if any(row["namesColumns"] for row in result.referenced_here):
        # It carries the column nowhere, so it produces no finding, and "No
        # impact" printed over it is the one sentence this tool may not print.
        return "low"
    return "none"


def _scan_lookup_failed(
    reports: list[AttributeReport],
    all_findings: list[Finding],
    result: ScanResult,
    subject_gap: bool,
) -> bool:
    """"I never saw that column" is a confident claim.

    Measured, all three of these printed a green "check your spelling" over a
    real gap: a file naming the column that could not be read, a whole chain in
    a folder Ripple was told to skip, and a row access policy naming that very
    column on the same screen.
    """
    if not reports or all_findings:
        return False
    if not all(report.lookup_failed for report in reports):
        return False
    if subject_gap:
        return False
    coverage = result.coverage
    if coverage is not None and not coverage.complete:
        return False
    if any(row["namesColumns"] for row in result.referenced_here):
        return False
    return True


def _two_definitions(parsed: Any) -> list[dict[str, Any]]:
    """Tables more than one file builds from scratch.

    Only one of those can be the definition that runs, and nothing in the code
    says which.
    """
    builders: dict[str, list[str]] = {}
    for stmt in parsed.statements:
        target = (stmt.target or "").strip()
        if not target:
            continue
        if not isinstance(stmt.expr, exp.Create) and not stmt.whole_copy:
            # INSERT and MERGE load a table someone else defined.
            continue
        files = builders.setdefault(display_table(target), [])
        if stmt.file not in files:
            files.append(stmt.file)
    out = [
        {"table": table, "files": sorted(files)}
        for table, files in builders.items()
        if len(files) > 1
    ]
    out.sort(key=lambda row: str(row["table"]))
    return out


def _file_types_unopened(index: Any) -> list[dict[str, Any]]:
    """The file types this answer had to pass over, most first.

    Every repository has a README, and a warning printed over every scan is one
    nobody reads - it would take "no impact" down with it. So the types known
    NOT to be code are left out here. The repository screen still lists every
    skipped extension, this one included, so nothing is hidden from anybody.
    """
    tally = _index_field(index, "unopened_extensions", "unknown_ext") or {}
    out = [
        {"ext": ext, "count": int(count)}
        for ext, count in tally.items()
        if str(ext).lower() not in NOT_CODE_EXTENSIONS
    ]
    out.sort(key=lambda row: (-int(row["count"]), str(row["ext"])))
    return out


def _group_json(group: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in group.items() if key != "_findings"}


def _drop_prefixes(
    branches: list[list[dict[str, Any]]]
) -> list[list[dict[str, Any]]]:
    """Drop any branch that is only the start of a longer one already listed."""
    routes = [[dict(node) for node in branch] for branch in branches]
    keys = [tuple(str(node["name"]) for node in branch) for branch in routes]
    out: list[list[dict[str, Any]]] = []
    for index, key in enumerate(keys):
        longer = False
        for other_index, other in enumerate(keys):
            if other_index == index:
                continue
            if len(other) > len(key) and other[: len(key)] == key:
                longer = True
                break
            if other == key and other_index < index:
                longer = True
                break
        if not longer:
            out.append(routes[index])
    return out


def _impact(kind: str, change_type: str, target: str, feed_uri: str) -> str:
    if feed_uri and kind not in ("filter", "join_key"):
        # An EXPORT DATA writes a file to a bucket. There is no published table
        # to gain or lose a column, which is exactly why the ordinary wording is
        # no use here.
        return (
            "This column is written into the file delivered to "
            + feed_uri
            + ". No table in this warehouse gains or loses anything, the "
            "delivery does, and whoever reads it is outside this repository. "
            "Tell them before the change ships."
        )
    sentence = _IMPACT_BY_CHANGE.get((change_type, kind))
    if sentence is None:
        sentence = _IMPACT_BY_KIND.get(kind, _IMPACT_FALLBACK)
    return sentence.format(target=_target_words(target))


def _target_words(target: str) -> str:
    return target if target else "the table this statement builds"


def _production_rule(cfg: Any) -> ProductionRule:
    """The published-table rule every table on this walk is judged against.

    The settings object keeps the pasted list already parsed, so ask it for
    that rule. A settings object built by hand carries only the patterns, and
    those are turned into a rule the same way a paste is, so a pattern like
    _PROD goes on meaning "any name ending _PROD" rather than a table called
    exactly that.
    """
    ask = getattr(cfg, "production", None)
    if callable(ask):
        rule = ask()
        if isinstance(rule, ProductionRule):
            return rule
    patterns = [
        str(name).strip()
        for name in (getattr(cfg, "production_patterns", ()) or ())
        if str(name).strip()
    ]
    if not patterns:
        # An empty list means nothing is published. Handing that to
        # parse_production would hand back production.py's own shipped
        # fallback instead, and a table called anything_published would be
        # reported as production on a scan that never asked for it.
        return ProductionRule()
    return parse_production("\n".join(patterns))


def _wildcard_match(source: str, keyed: str) -> str:
    """How a BigQuery wildcard table name covers another name.

    "shard", "family", "both", or "" for no match at all - not a yes or no,
    because the two readings are not worth the same. BigQuery's own rule is
    that events_* stands for every table in that dataset whose name starts
    with "events_", and a match on that rule is a fact about the SQL. Ripple
    matches one more thing on purpose: somebody asking what breaks types the
    family the way they say it out loud, "events" with no trailing separator,
    which BigQuery would not match. Matching it is right, because typing the
    name you say out loud must not produce a clean "no impact". Shipping it as
    certain is not, which is why the caller lowers certainty on "family" and
    "both".

    The reader keeps its own copy of this test to itself, and reaching into
    another file's private name is how a rename over there becomes a silent
    nothing over here, so the test is done in full in this file.
    """
    if not source or not keyed:
        return ""
    if "*" not in source and "*" not in keyed:
        return ""
    if not same_table(source, keyed):
        # This is what rules out a wildcard in one dataset covering a shard in
        # another, and it must go on ruling that out.
        return ""
    left = _short(source).lower()
    right = _short(keyed).lower()
    if left.endswith("*") and right.endswith("*"):
        # The same family written twice over. Nothing was guessed.
        return "shard"
    pattern, name = (left, right) if left.endswith("*") else (right, left)
    prefix = pattern[:-1]
    if not prefix:
        # A bare star is every table in the dataset, which says nothing about
        # this one.
        return ""
    starts = name.startswith(prefix)
    family = name == prefix.rstrip("_-")
    if starts and family:
        return "both"
    if starts:
        return "shard"
    if family:
        return "family"
    return ""


_REFERENCE_WORDS: dict[str, str] = {
    "SEARCH INDEX": "search index",
    "VECTOR INDEX": "vector index",
    "ROW ACCESS POLICY": "row access policy",
    "UNDROP TABLE": "UNDROP",
}


def _reference_words(kind: str) -> str:
    """The plain words the screen prints for one of these statements.

    The reader records the kind in the SQL's own capitals. The person reading
    this screen does not write SQL, so it says "row access policy".
    """
    return _REFERENCE_WORDS.get(kind.strip().upper(), kind.strip().lower())


def _leading_verb(text: str) -> str:
    """The word the statement starts with - CREATE, UNDROP.

    Read off the line itself rather than assumed from the kind, because the
    line is what somebody sees when they open the file to check the row.
    """
    for word in str(text or "").split():
        cleaned = re.sub(r"[^A-Za-z]", "", word)
        if cleaned:
            return cleaned.upper()
    return ""


def _unreadable_file(entry: Any) -> str:
    """The file one unreadable record is about.

    The reader calls that field `file`. This walk was written against a record
    that called it `path` and the tests still hand one of those over, so both
    spellings are read: an empty name here would quietly drop the file off the
    check-by-hand list, which is the one list that exists to admit what was
    missed.
    """
    name = getattr(entry, "file", "") or getattr(entry, "path", "")
    return str(name or "")


def _index_field(index: Any, *names: str) -> Any:
    """The first of these names the repository index actually carries.

    The index is built elsewhere in Ripple and several of its fields are spelt
    differently there - too_long rather than path_too_long, unknown_ext rather
    than unopened_extensions. Reading one spelling only kills the whole scan
    with an AttributeError at the very end, after every file has been read.
    """
    for name in names:
        if hasattr(index, name):
            return getattr(index, name)
    return None


def _count_of(value: Any) -> int:
    """A count, whether the index keeps the number or the list itself."""
    if isinstance(value, int):
        return value
    return len(value or ())


def _files_scanned(index: Any) -> int:
    """How many files this scan read.

    Where the index does not keep a number for it, the files it is holding are
    counted. Both are things that were actually counted; neither is a guess.
    """
    scanned = _index_field(index, "files_scanned")
    if isinstance(scanned, int):
        return scanned
    return len(getattr(index, "files", ()) or ())


def _snippet(text: str, stmt: Any, column: str) -> list[SnippetLine]:
    """Lines around the usage, never outside the statement's own lines.

    A finding pointed at a line in the next statement is a finding somebody
    opens the file to check, fails to find, and then dismisses.
    """
    if not text:
        return []
    lines = text.splitlines()
    start = max(1, int(stmt.line_offset or 1))
    end = int(stmt.line_end or start)
    if end < start:
        end = start
    end = min(end, len(lines))
    if start > len(lines):
        return []
    hit = start
    for number in range(start, end + 1):
        if _mentions(lines[number - 1], column):
            hit = number
            break
    first = max(start, hit - 2)
    last = min(end, hit + 2)
    return [
        SnippetLine(n=number, t=lines[number - 1].rstrip(), hit=number == hit)
        for number in range(first, last + 1)
    ]


def _merge_outputs(stmt: Any, column: str) -> list[str]:
    """The names a column lands under inside a MERGE.

    The whens are read through the dialect-compatibility module rather than off
    the node, because that key was renamed and the old one just returns None -
    every rename a MERGE makes would disappear, and a MERGE is how a published
    table is loaded.
    """
    expr = stmt.expr
    if not isinstance(expr, exp.Merge):
        return []
    out: list[str] = []
    for when in merge_whens(expr):
        for update in when.find_all(exp.EQ):
            left = update.this
            if not isinstance(left, exp.Column):
                continue
            if _tree_names(update.expression, column):
                if left.name and left.name not in out:
                    out.append(left.name)
        for insert in when.find_all(exp.Insert):
            targets = _tuple_columns(insert.this)
            values = _tuple_items(insert.expression)
            for position, value in enumerate(values):
                if position >= len(targets):
                    break
                if _tree_names(value, column) and targets[position] not in out:
                    out.append(targets[position])
    return out


def _tuple_columns(node: Any) -> list[str]:
    if node is None:
        return []
    if isinstance(node, exp.Tuple):
        return [item.name for item in node.expressions if isinstance(item, exp.Column)]
    if isinstance(node, exp.Schema):
        return [item.name for item in node.expressions if isinstance(item, exp.Column)]
    if isinstance(node, exp.Column):
        return [node.name]
    return []


def _tuple_items(node: Any) -> list[Any]:
    if node is None:
        return []
    if isinstance(node, exp.Tuple):
        return list(node.expressions)
    if isinstance(node, exp.Values) and node.expressions:
        first = node.expressions[0]
        if isinstance(first, exp.Tuple):
            return list(first.expressions)
    return [node]


def _tree_names(node: Any, column: str) -> bool:
    if node is None:
        return False
    if isinstance(node, exp.Column):
        return node.name.lower() == column.lower()
    for found in node.find_all(exp.Column):
        if found.name.lower() == column.lower():
            return True
    return False


def _merge_reason(one: str, two: str) -> str:
    """Why two spellings were followed as one table, or nothing at all."""
    if one == two:
        return ""
    if one.lower() == two.lower():
        # BigQuery treats two capitalisations as two different tables.
        return "capitals"
    if _short(one).lower() == _short(two).lower():
        left, right = _dataset(one), _dataset(two)
        if not left or not right:
            # A bare name has said nothing to rule anything out.
            return "dataset"
        # Two tables of the same name in two NAMED datasets are kept apart, and
        # nothing is said about them.
        return ""
    return ""


def _short(name: str) -> str:
    return name.split(".")[-1] if name else ""


def _dataset(name: str) -> str:
    parts = name.split(".") if name else []
    return parts[-2] if len(parts) > 1 else ""


def _word_pattern(name: str) -> str:
    # Explicit character classes rather than \b, so a name ending in an
    # underscore or a digit is still matched on its own boundaries.
    return r"(?<![0-9A-Za-z_])" + re.escape(name) + r"(?![0-9A-Za-z_])"


def _mentions(text: str, name: str) -> bool:
    if not text or not name:
        return False
    return re.search(_word_pattern(name), text, re.IGNORECASE) is not None


def _quoted_mention(line: str, name: str) -> bool:
    """The name written inside a quoted string on this line."""
    if not line or not name:
        return False
    inner = _word_pattern(name)
    single = r"'[^']*" + inner + r"[^']*'"
    double = r'"[^"]*' + inner + r'[^"]*"'
    return re.search(single + "|" + double, line, re.IGNORECASE) is not None


def _say(on_progress: Callable[[str], None] | None, message: str) -> None:
    if on_progress is not None:
        on_progress(message)
