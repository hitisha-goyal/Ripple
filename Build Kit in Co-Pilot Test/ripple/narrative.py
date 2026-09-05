from __future__ import annotations

"""Writing the summary and the drafted reply, with no AI anywhere near it.

This module runs when there is no AI key, when a key stops working, or when
somebody decides no data may leave the network.  The headline it writes gets
quoted in meetings and the body it writes gets forwarded to another team, so
every sentence in here is held to the same rule as the findings screen:
never claim more than was actually read.

The two public functions deliberately share every private helper below.  A
screen and a letter that disagree about how much of the repository was read
are worse than either one alone, so the branch, the uncovered count and the
capped table lists are all worked out in exactly one place.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

# Both public functions stamp this so a reader can tell a rules-written
# answer from an AI-written one without guessing from the prose.
WRITTEN_BY = "rules"

# The five branch names.  They are module-level constants rather than bare
# strings because both summarise() and draft_reply() switch on them, and a
# typo in one of the two would silently send the letter down a different
# branch from the screen.
BRANCH_NOTHING_PUBLISHED = "nothing-published"
BRANCH_NOTHING_SCANNED = "nothing-scanned"
BRANCH_LOOKUP_FAILED = "lookup-failed"
BRANCH_NO_FINDINGS = "no-findings"
BRANCH_IMPACT = "impact"

# Caps on lists of names.  A real repository puts hundreds of tables behind
# one key column, and joining them all into a sentence produces a paragraph
# nobody reads, in the one place on the screen written to be read.
CAP_TABLES_NARRATIVE = 6
CAP_TABLES_LETTER = 10
CAP_COLUMNS = 12
CAP_ACTIONS_IN_LETTER = 4


# ---------------------------------------------------------------------------
# small readers
#
# scan and vals arrive as the JSON-shaped mappings the rest of Ripple passes
# around.  These readers tolerate a plain object as well, because one missing
# key must not raise in the middle of writing a letter -- a letter that fails
# to render is a letter somebody writes by hand instead, without the caveats.
# ---------------------------------------------------------------------------


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _int(value: Any) -> int:
    # A count that arrives as None or as a string must not become a crash and
    # must not become a made-up number either, so it becomes zero and the
    # sentence that would have used it drops out.
    if value is None:
        return 0
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return 0


# ---------------------------------------------------------------------------
# plain English helpers
# ---------------------------------------------------------------------------


def _count(number: int, one: str, many: str) -> str:
    return f"{number} {one}" if number == 1 else f"{number} {many}"


def _join(parts: Sequence[str], final_word: str = "and") -> str:
    kept = [p for p in parts if p]
    if not kept:
        return ""
    if len(kept) == 1:
        return kept[0]
    return ", ".join(kept[:-1]) + f" {final_word} " + kept[-1]


def _join_capped(names: Sequence[str], cap: int) -> str:
    kept = [n for n in names if n]
    shown = kept[:cap]
    extra = len(kept) - len(shown)
    if not shown:
        return ""
    if extra > 0:
        return ", ".join(shown) + f" and {extra} more"
    return _join(shown)


def _capitalise(text: str) -> str:
    if not text:
        return text
    return text[0].upper() + text[1:]


def _paragraph(sentences: Sequence[str]) -> str:
    return " ".join(s for s in sentences if s)


def _body(paragraphs: Sequence[str]) -> str:
    return "\n\n".join(p for p in paragraphs if p)


# ---------------------------------------------------------------------------
# what the answer does NOT cover
#
# Five things count, and the total is the sum of all five.  Leave any of them
# out and a chain whose middle hop sits in a notebook, or in build/, or four
# renames further down, is a chain nobody looked at while the headline reads
# "No impact" over it.
# ---------------------------------------------------------------------------


@dataclass
class Unread:
    never_opened: int = 0
    not_followed: int = 0
    cut_short: int = 0
    cut_short_tables: list[str] = field(default_factory=list)
    skipped_files: int = 0
    skipped_folders: list[str] = field(default_factory=list)
    unopened_types: list[str] = field(default_factory=list)
    unopened_type_files: int = 0
    max_hops: int = 0

    @property
    def total(self) -> int:
        return (
            self.never_opened
            + self.not_followed
            + self.cut_short
            + self.skipped_files
            + self.unopened_type_files
        )

    @property
    def anything(self) -> bool:
        return self.total > 0

    def phrases(self) -> list[str]:
        """The kinds, not only the total.  A caveat somebody cannot act on is
        a caveat they skip, so the folders and the extensions are named."""
        out: list[str] = []
        if self.never_opened:
            out.append(
                _count(self.never_opened, "file", "files")
                + " could not be opened at all"
            )
        if self.not_followed:
            out.append(
                _count(self.not_followed, "file", "files")
                + " could not be followed"
            )
        if self.skipped_files:
            folders = _join_capped(self.skipped_folders, CAP_TABLES_NARRATIVE)
            named = f" ({folders})" if folders else ""
            if self.skipped_files == 1:
                out.append(
                    "1 code file sits in a folder Ripple is told to skip"
                    + named
                    + " and was never read"
                )
            else:
                out.append(
                    f"{self.skipped_files} code files sit in a folder Ripple "
                    "is told to skip" + named + " and were never read"
                )
        if self.unopened_type_files:
            exts = _join_capped(self.unopened_types, CAP_TABLES_NARRATIVE)
            named = f" ({exts})" if exts else ""
            if self.unopened_type_files == 1:
                out.append(
                    "1 file is of a type Ripple does not open" + named
                )
            else:
                out.append(
                    f"{self.unopened_type_files} files are of a type Ripple "
                    "does not open" + named
                )
        if self.cut_short:
            if self.cut_short == 1:
                out.append(
                    f"1 trail was stopped at {self.max_hops} renames deep and "
                    "was still going"
                )
            else:
                out.append(
                    f"{self.cut_short} trails were stopped at {self.max_hops} "
                    "renames deep and were still going"
                )
        return out


def _unread(scan: Any) -> Unread:
    stats = _get(scan, "stats") or {}
    cut = _as_list(_get(scan, "cutShort"))
    cut_tables: list[str] = []
    for item in cut:
        name = _text(_get(item, "table")) or (
            _text(item) if isinstance(item, str) else ""
        )
        if name:
            cut_tables.append(name)

    types: list[str] = []
    type_files = 0
    for item in _as_list(_get(scan, "fileTypesUnopened")):
        ext = _text(_get(item, "ext"))
        if ext:
            types.append(ext)
        type_files += _int(_get(item, "count"))

    return Unread(
        never_opened=_int(_get(stats, "neverOpened")),
        not_followed=len(_as_list(_get(scan, "unreadable"))),
        cut_short=len(cut),
        cut_short_tables=cut_tables,
        skipped_files=len(_as_list(_get(scan, "skippedInFolders"))),
        skipped_folders=[
            _text(f) for f in _as_list(_get(scan, "skippedFolderNames")) if _text(f)
        ],
        unopened_types=types,
        unopened_type_files=type_files,
        max_hops=_int(_get(scan, "maxHops")),
    )


# ---------------------------------------------------------------------------
# the findings
# ---------------------------------------------------------------------------


@dataclass
class Rows:
    production: list[Any] = field(default_factory=list)
    production_tables: list[str] = field(default_factory=list)
    reached_tables: list[str] = field(default_factory=list)
    other: list[Any] = field(default_factory=list)
    findings: list[Any] = field(default_factory=list)
    breaking: int = 0
    no_local_fix: list[Any] = field(default_factory=list)
    inferred: int = 0

    @property
    def no_fix_logic(self) -> str:
        for finding in self.no_local_fix:
            logic = _text(_get(finding, "logic"))
            if logic:
                return logic
        return "Ranking logic"


def _row_key(finding: Any) -> tuple[Any, ...]:
    """One finding upstream of two published tables appears under both.

    Counting the rows raw makes the letter say 9 one click after the summary
    said 8 -- two numbers for one thing, and the wrong one is the one that
    leaves the building.  So a finding is identified by where it is and what
    it does, not by which group it was printed under.
    """
    lines = _as_list(_get(finding, "lines"))
    first_line = _int(_get(lines[0], "n")) if lines else 0
    return (
        _text(_get(finding, "file")),
        _text(_get(finding, "from")),
        _text(_get(finding, "inter")),
        _text(_get(finding, "attr")),
        _text(_get(finding, "alias")),
        _text(_get(finding, "logic")),
        _text(_get(finding, "mode")),
        first_line,
    )


def _group_name(group: Any) -> str:
    for key in ("prod", "table", "name"):
        name = _text(_get(group, key))
        if name:
            return name
    return ""


def _rows(scan: Any) -> Rows:
    result = Rows()
    seen_production: set[tuple[Any, ...]] = set()
    seen_all: set[tuple[Any, ...]] = set()

    for group in _as_list(_get(scan, "groups")):
        rows = _as_list(_get(group, "rows"))
        if not rows:
            # A published table with no rows under it is not a table at risk,
            # and counting it would put a number on the screen that nothing
            # was counted for.
            continue
        name = _group_name(group)
        if name and name not in result.production_tables:
            result.production_tables.append(name)
        for row in rows:
            key = _row_key(row)
            if key in seen_production:
                continue
            seen_production.add(key)
            result.production.append(row)

    for group in _as_list(_get(scan, "reached")):
        name = _group_name(group)
        if name and name not in result.reached_tables:
            result.reached_tables.append(name)

    reached_rows: list[Any] = []
    for group in _as_list(_get(scan, "reached")):
        reached_rows.extend(_as_list(_get(group, "rows")))

    result.other = _as_list(_get(scan, "other"))

    for finding in list(result.production) + reached_rows + list(result.other):
        key = _row_key(finding)
        if key in seen_all:
            continue
        seen_all.add(key)
        result.findings.append(finding)
        if _get(finding, "breaking"):
            result.breaking += 1
        if _get(finding, "noLocalFix"):
            result.no_local_fix.append(finding)
        if _int(_get(finding, "inferredHops")) > 0:
            result.inferred += 1

    return result


# ---------------------------------------------------------------------------
# the other facts the letter has to read
# ---------------------------------------------------------------------------


@dataclass
class NamedDirectly:
    kind: str
    table: str

    def describe(self) -> str:
        # Print the kind Ripple recorded, not a word of our own: somebody
        # reading the letter has to be able to go and find the thing.
        if self.kind and self.table:
            return f"{self.kind} on {self.table}"
        return self.kind or self.table or "a statement Ripple could not name"


def _stops_loading(scan: Any) -> list[str]:
    out: list[str] = []
    for item in _as_list(_get(scan, "stopsLoading")):
        name = ""
        for key in ("table", "prod", "name"):
            name = _text(_get(item, key))
            if name:
                break
        if not name and isinstance(item, str):
            name = _text(item)
        out.append(name or "a published table Ripple could not name")
    return out


def _feeds(scan: Any) -> list[str]:
    out: list[str] = []
    for item in _as_list(_get(scan, "feeds")):
        dest = ""
        for key in ("uri", "feed", "to", "destination"):
            dest = _text(_get(item, key))
            if dest:
                break
        if not dest and isinstance(item, str):
            dest = _text(item)
        out.append(dest or "a destination Ripple could not read")
    return out


def _named_directly(scan: Any) -> list[NamedDirectly]:
    out: list[NamedDirectly] = []
    for item in _as_list(_get(scan, "referencedHere")):
        # An index on a table the chain happened to stand on is not a reason
        # to warn anybody; a statement that names the column being followed
        # is.  Everything without namesColumns is dropped here, once.
        if not _get(item, "namesColumns"):
            continue
        out.append(
            NamedDirectly(
                kind=_text(_get(item, "kind")),
                table=_text(_get(item, "table")),
            )
        )
    return out


def _star_sentence(scan: Any) -> str:
    tables = _as_list(_get(scan, "starTables"))
    if not tables:
        return ""
    if len(tables) == 1:
        return (
            "1 table on the way is built with SELECT *, so the column list "
            "could not be read and the steps past it are worked out rather "
            "than read."
        )
    return (
        f"{len(tables)} tables on the way are built with SELECT *, so the "
        "column list could not be read and the steps past them are worked "
        "out rather than read."
    )


def _table_columns(scan: Any) -> list[str]:
    out: list[str] = []
    for attribute in _as_list(_get(scan, "attributes")):
        for column in _as_list(_get(attribute, "tableColumns")):
            name = _text(column)
            if name and name not in out:
                out.append(name)
    return out


def _stops_prefix(scan: Any) -> str:
    # A capped list is a floor, not a total, and a floor printed as a total
    # is an invented number.
    return "at least " if _get(scan, "stopsLoadingCapped") else ""


def _stops_clause(scan: Any, stops: Sequence[str]) -> str:
    """One place builds this clause, so the headline, the bullet and the
    letter cannot end up disagreeing about how many tables stop loading."""
    prefix = _stops_prefix(scan)
    counted = prefix + _count(
        len(stops), "published table", "published tables"
    )
    verb = "stops" if (len(stops) == 1 and not prefix) else "stop"
    return f"{counted} {verb} being refreshed"


# ---------------------------------------------------------------------------
# what the upstream team told us
#
# INVENTED SHAPE: the contract card names notification.py but does not write
# down what it hands over.  This module reads vals for "attributes" (a list
# of column names, or one name), "table" and "date", and falls back to the
# scan and to plain wording when any of them is missing.
# ---------------------------------------------------------------------------


def _attribute_names(vals: Any, scan: Any) -> list[str]:
    for key in ("attributes", "attribute", "columns", "column"):
        raw = _get(vals, key)
        if raw:
            names = [_text(v) for v in _as_list(raw)]
            names = [n for n in names if n]
            if names:
                return names
    names = []
    for attribute in _as_list(_get(scan, "attributes")):
        name = ""
        for key in ("name", "attribute", "column"):
            name = _text(_get(attribute, key))
            if name:
                break
        if not name and isinstance(attribute, str):
            name = _text(attribute)
        if name and name not in names:
            names.append(name)
    return names


def _attribute_text(vals: Any, scan: Any) -> str:
    names = _attribute_names(vals, scan)
    return _join_capped(names, CAP_TABLES_NARRATIVE) or "the attribute"


def _table_text(vals: Any) -> str:
    for key in ("table", "tableName", "target"):
        name = _text(_get(vals, key))
        if name:
            return name
    return "the upstream table"


def _date_text(vals: Any) -> str:
    for key in ("date", "effectiveDate", "effective_date", "when"):
        when = _text(_get(vals, key))
        if when:
            return when
    return "the effective date"


# ---------------------------------------------------------------------------
# the branch
#
# Taken in this order and no other.  lookupFailed comes AFTER "nothing was
# scanned": a scan that read no files also meets every condition for a failed
# lookup, and "check the spelling" printed over an empty folder sends
# somebody hunting for a typo that is not there.
# ---------------------------------------------------------------------------


def _branch(scan: Any) -> str:
    rows = _rows(scan)
    stops = _stops_loading(scan)
    feeds = _feeds(scan)
    if (rows.findings or stops or feeds) and not rows.production_tables:
        return BRANCH_NOTHING_PUBLISHED
    if _int(_get(scan, "filesScanned")) == 0:
        return BRANCH_NOTHING_SCANNED
    if _get(scan, "lookupFailed"):
        return BRANCH_LOOKUP_FAILED
    if not rows.findings:
        return BRANCH_NO_FINDINGS
    return BRANCH_IMPACT


# ---------------------------------------------------------------------------
# caveat bullets and actions
#
# Files that could not be opened go first and worded hardest, because every
# other number on the page is a number about the files that WERE opened.
# ---------------------------------------------------------------------------


def _caveat_bullets(unread: Unread) -> list[str]:
    out: list[str] = []
    if unread.never_opened:
        out.append(
            _capitalise(_count(unread.never_opened, "file", "files"))
            + " could not be opened at all. Every other number here is a "
            "number about the files that were opened."
        )
    if unread.not_followed:
        out.append(
            _capitalise(_count(unread.not_followed, "file", "files"))
            + " could not be followed, so anything they use is missing from "
            "this answer."
        )
    if unread.skipped_files:
        folders = _join_capped(unread.skipped_folders, CAP_TABLES_NARRATIVE)
        named = f" ({folders})" if folders else ""
        out.append(
            _capitalise(_count(unread.skipped_files, "code file", "code files"))
            + " sits in a folder Ripple is told to skip"
            + named
            + " and was never read."
            if unread.skipped_files == 1
            else f"{unread.skipped_files} code files sit in a folder Ripple is "
            "told to skip" + named + " and were never read."
        )
    if unread.unopened_type_files:
        exts = _join_capped(unread.unopened_types, CAP_TABLES_NARRATIVE)
        named = f" ({exts})" if exts else ""
        out.append(
            _capitalise(_count(unread.unopened_type_files, "file", "files"))
            + " is of a type Ripple does not open"
            + named
            + "."
            if unread.unopened_type_files == 1
            else f"{unread.unopened_type_files} files are of a type Ripple "
            "does not open" + named + "."
        )
    if unread.cut_short:
        out.append(
            _capitalise(_count(unread.cut_short, "trail", "trails"))
            + " were cut short by the hop limit rather than by the code."
            if unread.cut_short != 1
            else "1 trail was cut short by the hop limit rather than by the "
            "code."
        )
    return out


def _caveat_actions(unread: Unread) -> list[str]:
    out: list[str] = []
    if unread.never_opened:
        out.append(
            "Open the "
            + _count(unread.never_opened, "file", "files")
            + " Ripple could not read on this machine, then run the scan "
            "again."
        )
    if unread.not_followed:
        out.append(
            "Read the "
            + _count(unread.not_followed, "file", "files")
            + " Ripple could not follow by hand."
        )
    if unread.skipped_files:
        folders = _join_capped(unread.skipped_folders, CAP_TABLES_NARRATIVE)
        if folders:
            out.append(
                f"Take {folders} off the skip list and run the scan again, or "
                "confirm nothing in there touches the pipeline."
            )
        else:
            out.append(
                "Take the skipped folders off the skip list and run the scan "
                "again."
            )
    if unread.unopened_type_files:
        exts = _join_capped(unread.unopened_types, CAP_TABLES_NARRATIVE)
        if exts:
            out.append(f"Read the {exts} files by hand. Ripple does not open them.")
        else:
            out.append(
                "Read the files of a type Ripple does not open by hand."
            )
    if unread.cut_short:
        out.append(
            "Run the scan again, deeper, before treating this as the whole "
            "answer."
        )
    return out


def _chain_sentences(scan: Any, rows: Rows, unread: Unread) -> list[str]:
    """A chain Ripple stopped following has not ended, so it is never
    described with the word "end"."""
    out: list[str] = []
    if rows.reached_tables:
        names = _join_capped(rows.reached_tables, CAP_TABLES_NARRATIVE)
        out.append(f"Those chains end at {names}.")
    if unread.cut_short_tables:
        names = _join_capped(unread.cut_short_tables, CAP_TABLES_NARRATIVE)
        out.append(
            f"Ripple stopped following {names} at {unread.max_hops} renames "
            "deep - those trails were still going, so nothing past that point "
            "has been looked at."
        )
    elif unread.cut_short:
        out.append(
            f"Ripple stopped following {_count(unread.cut_short, 'trail', 'trails')} "
            f"at {unread.max_hops} renames deep - those trails were still "
            "going, so nothing past that point has been looked at."
        )
    return out


def _stops_sentences(scan: Any, stops: Sequence[str]) -> list[str]:
    if not stops:
        return []
    names = _join_capped(list(stops), CAP_TABLES_NARRATIVE)
    return [
        _capitalise(_stops_clause(scan, stops)) + f": {names}.",
        "No column of them changes. The job that fills them stops running, so "
        "they quietly serve stale data.",
    ]


def _feed_sentences(feeds: Sequence[str]) -> list[str]:
    if not feeds:
        return []
    names = _join_capped(list(feeds), CAP_TABLES_NARRATIVE)
    head = _capitalise(_count(len(feeds), "delivery", "deliveries"))
    verb = "breaks" if len(feeds) == 1 else "break"
    return [
        f"{head} out of the warehouse {verb}, going to {names}.",
        "Whoever reads that sits outside this repository, so no scan of our "
        "code will ever find them.",
    ]


def _named_sentences(named: Sequence[NamedDirectly], attrs: str) -> list[str]:
    if not named:
        return []
    described = _join_capped([n.describe() for n in named], CAP_TABLES_NARRATIVE)
    head = _capitalise(_count(len(named), "statement", "statements"))
    verb = "names" if len(named) == 1 else "name"
    return [
        f"{head} {verb} {attrs} without carrying it anywhere: {described}.",
        "They stop working on the day the column changes.",
    ]


# ---------------------------------------------------------------------------
# summarise
# ---------------------------------------------------------------------------


def summarise(scan: Any, vals: Any) -> dict[str, Any]:
    attrs = _attribute_text(vals, scan)
    table = _table_text(vals)
    unread = _unread(scan)
    rows = _rows(scan)
    stops = _stops_loading(scan)
    feeds = _feeds(scan)
    named = _named_directly(scan)
    star = _star_sentence(scan)
    files_scanned = _int(_get(scan, "filesScanned"))
    stats = _get(scan, "stats") or {}
    branch = _branch(scan)

    sentences: list[str] = []
    bullets: list[str] = []
    actions: list[str] = []

    if branch == BRANCH_NOTHING_PUBLISHED:
        if stops:
            headline = _capitalise(_stops_clause(scan, stops))
        elif feeds:
            headline = _capitalise(
                _count(len(feeds), "delivery", "deliveries")
                + " out of the warehouse "
                + ("breaks" if len(feeds) == 1 else "break")
            )
        else:
            headline = (
                _count(len(rows.findings), "usage", "usages")
                + " found - none of them reaching a table on your published "
                "list"
            )

        sentences.extend(_stops_sentences(scan, stops))
        sentences.extend(_feed_sentences(feeds))
        sentences.extend(_named_sentences(named, attrs))
        if stops or feeds:
            sentences.append(
                f"Ripple is holding {_count(len(rows.findings), 'usage', 'usages')} "
                f"of {attrs} in this repository. That is not a clean result, "
                "an unfinished one, and the work above stands whatever the "
                "rest of the chain turns out to be."
            )
        else:
            sentences.append(
                f"Ripple found {_count(len(rows.findings), 'usage', 'usages')} "
                f"of {attrs} in this repository and none of them reach a table "
                "on your published list."
            )
            sentences.append(
                "That is not a clean result, an unfinished one: either this "
                "chain really is internal, or the rule that decides which "
                "tables count as published does not match this repository. "
                "Only a person can tell which, so check that rule on the "
                "settings screen before treating this as an answer."
            )
        sentences.extend(_chain_sentences(scan, rows, unread))
        if unread.phrases():
            sentences.append(
                _capitalise(_join(unread.phrases())) + "."
            )
        if star:
            sentences.append(star)

        bullets.extend(_caveat_bullets(unread))
        if stops:
            bullets.append(
                _capitalise(_stops_clause(scan, stops))
                + ": "
                + _join_capped(list(stops), CAP_TABLES_NARRATIVE)
                + "."
            )
        if feeds:
            bullets.append(
                _capitalise(_count(len(feeds), "delivery", "deliveries"))
                + " out of the warehouse "
                + ("breaks" if len(feeds) == 1 else "break")
                + ", going to "
                + _join_capped(list(feeds), CAP_TABLES_NARRATIVE)
                + "."
            )
        if named:
            bullets.append(
                _capitalise(_count(len(named), "statement", "statements"))
                + (" names " if len(named) == 1 else " name ")
                + attrs
                + " directly: "
                + _join_capped(
                    [n.describe() for n in named], CAP_TABLES_NARRATIVE
                )
                + "."
            )
        bullets.append(
            _capitalise(_count(len(rows.findings), "usage", "usages"))
            + " found, and no chain reaches a table on the published list."
        )

        actions.extend(_caveat_actions(unread))
        if stops:
            actions.append(
                "Find out why the load into "
                + _join_capped(list(stops), CAP_TABLES_NARRATIVE)
                + " stopped running, and fix it."
            )
        if feeds:
            actions.append(
                "Tell whoever reads "
                + _join_capped(list(feeds), CAP_TABLES_NARRATIVE)
                + " that the delivery changes."
            )
        for entry in named:
            actions.append(f"Update the {entry.describe()} that names {attrs}.")
        if not stops and not feeds:
            actions.append(
                "Check the published-table rule on the settings screen, then "
                "run the scan again."
            )
        actions.append(
            "Do not treat this as a clean result. It is an unfinished one."
        )

    elif branch == BRANCH_NOTHING_SCANNED:
        headline = "Nothing was scanned — there was no code to search"
        sentences.append(
            "No files were read, so nothing has been checked."
        )
        sentences.append(
            "This is not a statement about the pipeline. It is a statement "
            "about an empty folder."
        )
        sentences.append(
            f"Point Ripple at the repository that builds our tables and run "
            f"the scan again before answering anything about {attrs} on "
            f"{table}."
        )
        if unread.phrases():
            sentences.append(_capitalise(_join(unread.phrases())) + ".")

        bullets.extend(_caveat_bullets(unread))
        bullets.append(
            f"Nothing was scanned, so there is no answer either way about "
            f"{attrs}."
        )
        actions.append(
            "Point Ripple at the pipeline repository and run the scan again."
        )
        actions.append(
            "Do not reply to the upstream team on the strength of this scan."
        )
        actions.extend(_caveat_actions(unread))

    elif branch == BRANCH_LOOKUP_FAILED:
        headline = f"{attrs} was not found - nothing has been checked"
        sentences.append(
            _capitalise(_count(files_scanned, "file", "files"))
            + " were read." if files_scanned != 1 else "1 file was read."
        )
        sentences.append(
            f"{attrs} was never met as a column on {table}, or on anything "
            "else in this repository."
        )
        sentences.append(
            "That is not the same as the change being safe. The question has "
            "not been answered."
        )
        sentences.append("Check the spelling before replying.")
        columns = _table_columns(scan)
        if columns:
            sentences.append(
                f"The columns Ripple did read on {table} are: "
                + _join_capped(columns, CAP_COLUMNS)
                + "."
            )
        else:
            sentences.append(
                "Nothing in this repository writes down the columns of that "
                "table."
            )
        if unread.phrases():
            sentences.append(_capitalise(_join(unread.phrases())) + ".")
        if star:
            sentences.append(star)

        bullets.extend(_caveat_bullets(unread))
        bullets.append(
            f"No answer either way about {attrs}: the name was never met as a "
            "column."
        )
        if columns:
            bullets.append(
                f"What Ripple did read on {table}: "
                + _join_capped(columns, CAP_COLUMNS)
                + "."
            )
        else:
            bullets.append(
                f"Nothing in this repository writes down the columns of "
                f"{table}."
            )
        actions.append(
            f"Check the spelling of {attrs} against the list above, then run "
            "the scan again."
        )
        actions.append(
            "Do not reply to the upstream team on the strength of this scan."
        )
        actions.extend(_caveat_actions(unread))

    elif branch == BRANCH_NO_FINDINGS:
        if named:
            headline = (
                "No lineage, but "
                + _count(len(named), "statement", "statements")
                + (" names " if len(named) == 1 else " name ")
                + attrs
                + " directly"
            )
            sentences.append(
                f"Nothing in this repository carries {attrs} into another "
                "table."
            )
            sentences.extend(_named_sentences(named, attrs))
        elif unread.anything:
            headline = (
                "No usage found in the "
                + _count(files_scanned, "file", "files")
                + " that could be read — "
                + _count(unread.total, "other", "others")
                + " could not be"
            )
            sentences.append(
                f"Nothing in the files Ripple could read consumes {attrs} "
                f"from {table}."
            )
            sentences.append(
                "The assessment is still being confirmed, because part of the "
                "repository was not covered."
            )
        else:
            headline = (
                "No impact — nothing in this repository consumes the attribute"
            )
            sentences.append(
                f"Every file in this repository was read, and nothing in it "
                f"consumes {attrs} from {table}."
            )
        if unread.phrases():
            sentences.append(_capitalise(_join(unread.phrases())) + ".")
        sentences.extend(_chain_sentences(scan, rows, unread))
        if star:
            sentences.append(star)

        bullets.extend(_caveat_bullets(unread))
        if named:
            bullets.append(
                _capitalise(_count(len(named), "statement", "statements"))
                + (" names " if len(named) == 1 else " name ")
                + attrs
                + " directly: "
                + _join_capped(
                    [n.describe() for n in named], CAP_TABLES_NARRATIVE
                )
                + "."
            )
        bullets.append(
            f"No statement in the files that were read carries {attrs} into "
            "another table."
        )
        # Files that could not be opened come first, because every other
        # number on this page is a number about the files that were opened.
        actions.extend(_caveat_actions(unread))
        for entry in named:
            actions.append(f"Update the {entry.describe()} that names {attrs}.")
        if not named and not unread.anything:
            actions.append(
                "Reply to the upstream team confirming the change is clear "
                "from our side."
            )

    else:
        production_count = len(rows.production_tables)
        if rows.no_local_fix:
            headline = (
                f"{rows.no_fix_logic} has no replacement — escalate before "
                "the date"
            )
        elif rows.breaking and unread.anything:
            headline = (
                _count(
                    production_count, "production table", "production tables"
                )
                + " at risk, and "
                + _count(unread.total, "file", "files")
                + " Ripple could not follow"
            )
        elif rows.breaking:
            headline = (
                _count(
                    production_count, "production table", "production tables"
                )
                + " at risk, all fixable in code"
            )
        else:
            headline = "Labels change, but nothing breaks"
        if stops:
            # Three different kinds of impact, and a headline that mentions
            # only the tables at risk hides the ones that quietly stop being
            # refreshed.
            headline = headline + ", and " + _stops_clause(scan, stops)

        sentences.append(
            f"{attrs} is read by "
            + _count(len(rows.production), "pipeline object", "pipeline objects")
            + " feeding "
            + _count(
                production_count, "production table", "production tables"
            )
            + ": "
            + _join_capped(rows.production_tables, CAP_TABLES_NARRATIVE)
            + "."
        )
        if rows.breaking:
            sentences.append(
                _capitalise(_count(rows.breaking, "usage", "usages"))
                + (" breaks" if rows.breaking == 1 else " break")
                + " on the day the column changes."
            )
        else:
            sentences.append(
                "None of them break. The labels change and the numbers do not."
            )
        if rows.no_local_fix:
            sentences.append(
                _capitalise(
                    _count(len(rows.no_local_fix), "usage", "usages")
                )
                + " orders or deduplicates on "
                + attrs
                + " and has no local substitute, so it cannot be fixed in our "
                "own code."
            )
        if rows.reached_tables:
            sentences.append(
                "The chain also reaches "
                + _join_capped(rows.reached_tables, CAP_TABLES_NARRATIVE)
                + ", which are not on your published list."
            )
        sentences.extend(_stops_sentences(scan, stops))
        sentences.extend(_feed_sentences(feeds))
        sentences.extend(_named_sentences(named, attrs))
        chain_notes = _chain_sentences(scan, rows, unread)
        # The "chains end at" half is already said above for this branch, so
        # only the cut-short half is repeated here.
        sentences.extend(chain_notes[1:] if rows.reached_tables else chain_notes)
        if unread.phrases():
            sentences.append(_capitalise(_join(unread.phrases())) + ".")
        if star:
            sentences.append(star)

        bullets.extend(_caveat_bullets(unread))
        bullets.append(
            _capitalise(
                _count(production_count, "production table", "production tables")
            )
            + " at risk: "
            + _join_capped(rows.production_tables, CAP_TABLES_NARRATIVE)
            + "."
        )
        bullets.append(
            _capitalise(_count(len(rows.production), "pipeline object", "pipeline objects"))
            + " read the attribute, "
            + _count(rows.breaking, "of which breaks", "of which break")
            + "."
        )
        impacted = _int(_get(stats, "attributesImpacted"))
        if impacted:
            bullets.append(
                _capitalise(_count(impacted, "attribute", "attributes"))
                + " of those you confirmed "
                + ("is" if impacted == 1 else "are")
                + " used downstream."
            )
        if rows.no_local_fix:
            bullets.append(
                _capitalise(_count(len(rows.no_local_fix), "usage", "usages"))
                + " has no local replacement and needs the upstream team."
            )
        if stops:
            bullets.append(
                _capitalise(_stops_clause(scan, stops))
                + ": "
                + _join_capped(list(stops), CAP_TABLES_NARRATIVE)
                + "."
            )
        if feeds:
            bullets.append(
                _capitalise(_count(len(feeds), "delivery", "deliveries"))
                + " out of the warehouse "
                + ("breaks" if len(feeds) == 1 else "break")
                + ", going to "
                + _join_capped(list(feeds), CAP_TABLES_NARRATIVE)
                + "."
            )
        if named:
            bullets.append(
                _capitalise(_count(len(named), "statement", "statements"))
                + (" names " if len(named) == 1 else " name ")
                + attrs
                + " directly: "
                + _join_capped(
                    [n.describe() for n in named], CAP_TABLES_NARRATIVE
                )
                + "."
            )

        actions.extend(_caveat_actions(unread))
        for name in rows.production_tables[:CAP_TABLES_NARRATIVE]:
            actions.append(f"Update the statements feeding {name}.")
        if rows.no_local_fix:
            actions.append(
                f"Escalate the {rows.no_fix_logic.lower()} that has no local "
                "replacement before the date."
            )
        if stops:
            actions.append(
                "Find out why the load into "
                + _join_capped(list(stops), CAP_TABLES_NARRATIVE)
                + " stopped running, and fix it."
            )
        if feeds:
            actions.append(
                "Tell whoever reads "
                + _join_capped(list(feeds), CAP_TABLES_NARRATIVE)
                + " that the delivery changes."
            )
        for entry in named:
            actions.append(f"Update the {entry.describe()} that names {attrs}.")

    return {
        "headline": headline,
        "narrative": _paragraph(sentences),
        "bullets": bullets,
        "actions": actions,
        "writtenBy": WRITTEN_BY,
    }


# ---------------------------------------------------------------------------
# draft_reply
#
# Assembled from what the summary already worked out, not written a second
# time.  Every count in here comes from the same helper the summary used.
# ---------------------------------------------------------------------------


def draft_reply(scan: Any, vals: Any, summary: Any) -> dict[str, Any]:
    attrs = _attribute_text(vals, scan)
    table = _table_text(vals)
    when = _date_text(vals)
    unread = _unread(scan)
    rows = _rows(scan)
    stops = _stops_loading(scan)
    feeds = _feeds(scan)
    named = _named_directly(scan)
    star = _star_sentence(scan)
    files_scanned = _int(_get(scan, "filesScanned"))
    branch = _branch(scan)
    actions = [_text(a) for a in _as_list(_get(summary, "actions")) if _text(a)]

    paragraphs: list[str] = []

    if branch == BRANCH_NOTHING_PUBLISHED:
        subject = f"Assessment in progress: {attrs} on {table}"
        paragraphs.append(
            "Thank you for the notice. Our assessment is in progress and is "
            "not finished."
        )
        if stops:
            paragraphs.append(
                _paragraph(_stops_sentences(scan, stops))
            )
        if feeds:
            paragraphs.append(_paragraph(_feed_sentences(feeds)))
        if named:
            paragraphs.append(_paragraph(_named_sentences(named, attrs)))
        paragraphs.append(
            "We are holding "
            + _count(len(rows.findings), "usage", "usages")
            + f" of {attrs} in our pipeline, and none of them reach a table on "
            "our published list. That is not a clean result, an unfinished "
            "one, and we are still working through it."
        )
        chains = _chain_sentences(scan, rows, unread)
        if chains:
            paragraphs.append(_paragraph(chains))
        paragraphs.extend(_letter_caveats(unread, star))
        paragraphs.append(
            f"We will come back to you with a firm answer before {when}."
        )

    elif branch == BRANCH_NOTHING_SCANNED:
        subject = f"Cannot assess yet: {attrs} on {table}"
        paragraphs.append(
            "Thank you for the notice. No answer is possible yet."
        )
        paragraphs.append(
            "Nothing was scanned - there was no code to search, so we have "
            f"checked nothing and can say nothing about {attrs} on {table}."
        )
        paragraphs.append(
            "We will point our scan at the pipeline repository, run it again "
            f"and come back to you before {when}."
        )

    elif branch == BRANCH_LOOKUP_FAILED:
        subject = f"Please confirm the column name: {attrs} on {table}"
        paragraphs.append(
            "Thank you for the notice. We cannot confirm anything either way "
            "yet."
        )
        paragraphs.append(
            "We read "
            + _count(files_scanned, "file", "files")
            + f", and {attrs} was never met as a column on {table} or "
            "anywhere else in our repository. That is not the same as the "
            "change being safe: the question has not been answered."
        )
        columns = _table_columns(scan)
        if columns:
            paragraphs.append(
                f"Could you confirm the exact column name. The columns we did "
                f"read on {table} are: "
                + _join_capped(columns, CAP_COLUMNS)
                + "."
            )
        else:
            paragraphs.append(
                "Could you confirm the exact column name. Nothing in our "
                "repository writes down the columns of that table, so we have "
                "no list to check it against."
            )
        paragraphs.extend(_letter_caveats(unread, star))

    elif branch == BRANCH_NO_FINDINGS:
        if named:
            subject = f"Assessment in progress: {attrs} on {table}"
            paragraphs.append(
                "Thank you for the notice. Nothing in our pipeline carries "
                f"{attrs} into another table."
            )
            paragraphs.append(_paragraph(_named_sentences(named, attrs)))
            paragraphs.append(
                "We will update those statements before the effective date."
            )
            paragraphs.extend(_letter_caveats(unread, star))
        elif unread.anything:
            subject = f"Assessment being confirmed: {attrs} on {table}"
            paragraphs.append(
                "Thank you for the notice. Our assessment is still being "
                "confirmed."
            )
            paragraphs.append(
                "We found no usage of "
                + attrs
                + " in the "
                + _count(files_scanned, "file", "files")
                + " we could read, but "
                + _count(unread.total, "other", "others")
                + " could not be: "
                + _join(unread.phrases())
                + "."
            )
            paragraphs.extend(_letter_caveats(unread, star))
            paragraphs.append(
                f"We will confirm before {when}."
            )
        else:
            subject = f"No impact: {attrs} on {table}"
            paragraphs.append(
                "Thank you for the notice. No impact."
            )
            paragraphs.append(
                "We have read every file in our pipeline repository and "
                f"nothing in it consumes {attrs} from {table}."
            )
            if star:
                paragraphs.append(star)
            paragraphs.append("Please proceed as planned.")

    else:
        subject = f"Impact confirmed: {attrs} on {table}"
        paragraphs.append(
            "Impact confirmed. "
            + attrs
            + " is consumed by "
            + _count(len(rows.production), "pipeline object", "pipeline objects")
            + " feeding "
            + _count(
                len(rows.production_tables),
                "production table",
                "production tables",
            )
            + ": "
            + _join_capped(rows.production_tables, CAP_TABLES_LETTER)
            + "."
        )
        if stops:
            paragraphs.append(_paragraph(_stops_sentences(scan, stops)))
        if feeds:
            paragraphs.append(_paragraph(_feed_sentences(feeds)))
        if named:
            paragraphs.append(_paragraph(_named_sentences(named, attrs)))
        if actions:
            lines = ["What we will do before the effective date:"]
            for action in actions[:CAP_ACTIONS_IN_LETTER]:
                lines.append(f"  - {action}")
            paragraphs.append("\n".join(lines))
        if rows.no_local_fix:
            paragraphs.append(
                "One ask of your team: at least one usage orders or "
                f"deduplicates on {attrs} and has no local substitute. Could "
                "you confirm a replacement attribute, or retain this one, "
                f"before {when}."
            )
        paragraphs.extend(_letter_caveats(unread, star))

    return {
        "subject": subject,
        "body": _body(paragraphs),
        "writtenBy": WRITTEN_BY,
    }


def _letter_caveats(unread: Unread, star: str) -> list[str]:
    """The difference between a letter another team can rely on and a letter
    that quietly claims more than was read."""
    out: list[str] = []
    if unread.not_followed:
        out.append(
            _capitalise(_count(unread.not_followed, "file", "files"))
            + " could not be followed, so this assessment may still grow."
        )
    if unread.never_opened:
        out.append(
            _capitalise(_count(unread.never_opened, "file", "files"))
            + " could not be opened at all on this machine. This assessment "
            "does not cover them."
        )
    other: list[str] = []
    if unread.skipped_files:
        folders = _join_capped(unread.skipped_folders, CAP_TABLES_NARRATIVE)
        named = f" ({folders})" if folders else ""
        other.append(
            _count(unread.skipped_files, "code file", "code files")
            + " sits in a folder our scan is told to skip"
            + named
            + " and was never read"
            if unread.skipped_files == 1
            else _count(unread.skipped_files, "code file", "code files")
            + " sit in a folder our scan is told to skip"
            + named
            + " and were never read"
        )
    if unread.unopened_type_files:
        exts = _join_capped(unread.unopened_types, CAP_TABLES_NARRATIVE)
        named = f" ({exts})" if exts else ""
        other.append(
            _count(unread.unopened_type_files, "file", "files")
            + " is of a type our scan does not open"
            + named
            if unread.unopened_type_files == 1
            else _count(unread.unopened_type_files, "file", "files")
            + " are of a type our scan does not open"
            + named
        )
    if unread.cut_short:
        other.append(
            _count(unread.cut_short, "trail", "trails")
            + f" was stopped at {unread.max_hops} renames deep and was still "
            "going"
            if unread.cut_short == 1
            else _count(unread.cut_short, "trail", "trails")
            + f" were stopped at {unread.max_hops} renames deep and were "
            "still going"
        )
    if other:
        out.append(
            _capitalise(_join(other))
            + ". This assessment does not cover them either."
        )
    if star:
        out.append(star)
    return out
