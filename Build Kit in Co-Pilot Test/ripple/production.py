from __future__ import annotations

"""Which tables the team publishes.

This file decides which tables count as published by our team, which decides
whether a finding counts as production impact - which is what the headline, the
risk level and the drafted reply are all built from. Getting it wrong turns a
change that really breaks three published tables into a calm "no impact".

The list arrives as a paste out of Excel, Slack, Confluence or a query result,
so the parsing is deliberately forgiving. What it is never allowed to be is
quiet: everything left out comes back as a note, already written as a sentence
somebody can read on screen.
"""

import fnmatch
import re
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

# The shipped fallback. An empty rule would mean "no table is ever production",
# which would report every repository on earth as clean.
DEFAULT_PRODUCTION: tuple[str, ...] = ("_PROD", "_PRD", "_PUBLISHED")

# A heading that is not recognised becomes a published table name, and a
# published-table list with a word like "Status" on it matches nothing,
# quietly, on the one setting that decides whether "no production table is
# impacted" is a result or an accident. The last dozen are here because a real
# list is copied out of a spreadsheet that had other columns beside the table
# names, and every one of those column headings arrives with it.
HEADING_WORDS: frozenset[str] = frozenset(
    {
        "#",
        "no",
        "s no",
        "sr no",
        "sl no",
        "row",
        "id",
        "index",
        "name",
        "names",
        "table",
        "tables",
        "tablename",
        "table name",
        "table names",
        "full name",
        "full table name",
        "qualified name",
        "fully qualified name",
        "fully qualified table name",
        "target table",
        "output table",
        "published table",
        "prod table",
        "production table",
        "downstream table",
        "dataset",
        "datasets",
        "schema",
        "project",
        "database",
        "db",
        "owner",
        "team",
        "layer",
        "domain",
        "env",
        "environment",
        "source",
        "type",
        "status",
        "sla",
        "frequency",
        "comment",
        "comments",
        "notes",
        "description",
    }
)

# Decoration that arrives with a paste. A bullet is stripped; a pattern is not.
# "*" and "-" only count as bullets when a space follows, because "*_PROD" and
# "-odd-name" are things somebody may genuinely have typed.
_HARD_BULLETS = "•‣·–—▪◦"
_QUOTES = "`\"'‘’“”"

_FENCE_RE = re.compile(r"^\s*`{3,}")
_RULED_RE = re.compile(r"^[\s\-=|:]+$")
_NUMBER_RE = re.compile(r"^\(?\d+[.)]\s+")

# A name is dot-separated parts. BigQuery project ids carry hyphens, datasets
# and tables carry underscores and digits, and a pattern carries * or ?.
_PART = r"[A-Za-z0-9_$*?\-]+"
_NAME_RE = re.compile(rf"^{_PART}(\.{_PART})*$")


@dataclass(frozen=True)
class ProductionEntry:
    """One recognised entry from the pasted list.

    raw   - exactly what was pasted, kept for showing back on screen
    match - what is actually matched against
    kind  - "exact", "glob" or "suffix"
    """

    raw: str
    match: str
    kind: str


@dataclass(frozen=True)
class ProductionRule:
    """The parsed list, plus an honest account of what was left out."""

    entries: tuple[ProductionEntry, ...] = ()
    notes: tuple[str, ...] = ()
    column_used: str = ""
    from_default: bool = False


def _clean_cell(raw: str) -> str:
    """Strip paste decoration from one cell, leaving the name as typed."""
    text = raw.strip()
    changed = True
    while changed and text:
        changed = False
        if text[0] in _HARD_BULLETS:
            text = text[1:].strip()
            changed = True
            continue
        if text[0] in "-*" and len(text) > 1 and text[1] in " \t":
            text = text[1:].strip()
            changed = True
            continue
        found = _NUMBER_RE.match(text)
        if found:
            text = text[found.end() :].strip()
            changed = True
            continue
        if len(text) >= 2 and text[0] in _QUOTES and text[-1] in _QUOTES:
            text = text[1:-1].strip()
            changed = True
            continue
        if text[0] in _QUOTES:
            text = text[1:].strip()
            changed = True
            continue
        if text[-1] in _QUOTES or text[-1] in ",;":
            text = text[:-1].strip()
            changed = True
            continue
    return text


def _looks_like_name(text: str) -> bool:
    """Could this be a table name at all."""
    if not text or len(text) > 200:
        return False
    if not _NAME_RE.match(text):
        return False
    # A cell of pure digits is a row number from a spreadsheet, not a table.
    return any(char.isalpha() for char in text)


def _strong(text: str) -> bool:
    """Does this look like a REAL table name.

    "real" means it also contains an underscore, a dot or a digit. This is what
    separates a column of table names from a column of words, and it is what
    stops a sentence being chopped into invented published tables.
    """
    if not _looks_like_name(text):
        return False
    return any(char == "_" or char == "." or char.isdigit() for char in text)


def _looks_like_prose(text: str) -> bool:
    """A sentence somebody typed under their list, not a row of names."""
    words = text.split()
    if len(words) < 4:
        return False
    strong = sum(1 for word in words if _strong(_clean_cell(word)))
    return strong * 2 < len(words)


def _usable_lines(text: str) -> list[str]:
    """Lines with fences, rules and blanks taken out."""
    lines: list[str] = []
    for line in text.splitlines():
        if _FENCE_RE.match(line):
            continue
        if not line.strip():
            continue
        if _RULED_RE.match(line):
            continue
        lines.append(line)
    return lines


def _looks_like_columns(rows: list[list[str]]) -> bool:
    """Is this comma-separated paste a grid of columns, or a list of names.

    A list of names scores well in every field; a spreadsheet exported as CSV
    has one column of names and others of owners and dates. Requiring a column
    that scores nothing is what keeps "alpha_daily, beta_weekly" on one line
    from being read as two columns.
    """
    if len(rows) < 2:
        return False
    widths = {len(row) for row in rows}
    if len(widths) != 1:
        return False
    width = widths.pop()
    if width < 2:
        return False
    scores = [
        sum(1 for row in rows if _strong(_clean_cell(row[index])))
        for index in range(width)
    ]
    return max(scores) > 0 and min(scores) == 0


def _as_grid(lines: list[str]) -> list[list[str]] | None:
    """Split a paste into columns, or return None if it is a plain list."""
    if any("\t" in line for line in lines):
        return [line.split("\t") for line in lines]
    if any("|" in line for line in lines):
        rows: list[list[str]] = []
        for line in lines:
            cells = line.split("|")
            # A markdown row is written | a | b |, so the split leaves an empty
            # cell at each end that is not a column.
            if cells and not cells[0].strip():
                cells = cells[1:]
            if cells and not cells[-1].strip():
                cells = cells[:-1]
            rows.append(cells)
        return rows
    trimmed = [line.rstrip().rstrip(",;").rstrip() for line in lines]
    rows = [line.split(",") for line in trimmed]
    if _looks_like_columns(rows):
        return rows
    return None


def _is_heading_row(cells: list[str]) -> bool:
    """A row of column headings rather than a row of data.

    Requiring that no cell is a real table name is what stops a data row being
    thrown away because one of its columns happens to read "source".
    """
    cleaned = [_clean_cell(cell) for cell in cells]
    filled = [cell for cell in cleaned if cell]
    if not filled:
        return False
    if any(_strong(cell) for cell in filled):
        return False
    return any(cell.lower() in HEADING_WORDS for cell in filled)


def _column_with_table_heading(cells: list[str]) -> int:
    """The column whose heading contains the word "table", or -1."""
    for index, cell in enumerate(cells):
        words = _clean_cell(cell).lower().replace("_", " ").split()
        if any(word.startswith("table") or word == "tablename" for word in words):
            return index
    return -1


def _best_column(rows: list[list[str]]) -> int:
    """The column holding the most things that look like real table names."""
    if not rows:
        return 0
    width = max(len(row) for row in rows)
    best_index = 0
    best_score = -1
    for index in range(width):
        score = sum(
            1
            for row in rows
            if index < len(row) and _strong(_clean_cell(row[index]))
        )
        if score > best_score:
            best_score = score
            best_index = index
    return best_index


def _split_pieces(cell: str) -> list[str]:
    """One cell into candidate names.

    Commas and semicolons are explicit separators. Spaces are only treated as a
    separator when every piece is a real table name, because "please confirm by
    friday" must come back as one ignored line and not as four published tables
    Ripple would then never find.
    """
    pieces: list[str] = []
    for chunk in re.split(r"[,;]", cell):
        text = chunk.strip()
        if not text:
            continue
        tokens = text.split()
        if len(tokens) > 1 and all(_strong(_clean_cell(token)) for token in tokens):
            pieces.extend(tokens)
        else:
            pieces.append(text)
    return pieces


def _classify(name: str) -> tuple[str, str]:
    """Decide what kind of entry this is, and what it is matched against.

    Rules somebody set months ago must go on meaning exactly what they meant,
    so this order does not change: a wildcard first, then a leading underscore,
    then an ordinary name. SQL only ever gives us the last part of a name, so
    an exact name is matched on its last dot-separated part.
    """
    if "*" in name or "?" in name:
        return "glob", name.lower()
    if name.startswith("_"):
        return "suffix", name.lower()
    return "exact", name.rsplit(".", 1)[-1].lower()


def _plural(count: int, one: str, many: str) -> str:
    return one if count == 1 else many


def parse_production(text: str) -> ProductionRule:
    """Read a pasted list of published tables, in whatever shape it arrived."""
    notes: list[str] = []
    heading_lines = 0
    ignored_lines = 0
    column_used = ""

    lines = _usable_lines(text or "")
    rows = _as_grid(lines)
    cells: list[str]
    if rows is None:
        cells = list(lines)
    else:
        width = max(len(row) for row in rows) if rows else 0
        padded = [row + [""] * (width - len(row)) for row in rows]
        heading: list[str] = []
        if padded and _is_heading_row(padded[0]):
            heading = padded[0]
            body = padded[1:]
            heading_lines += 1
        else:
            body = padded
        chosen = -1
        if heading:
            chosen = _column_with_table_heading(heading)
        if chosen < 0:
            chosen = _best_column(body)
        if width > 1:
            other = width - 1
            label = _clean_cell(heading[chosen]) if heading else ""
            if label:
                column_used = label
                notes.append(
                    f"The paste had {width} columns. Ripple read the column "
                    f'headed "{label}" and ignored the other {other}.'
                )
            else:
                column_used = f"column {chosen + 1}"
                notes.append(
                    f"The paste had {width} columns. Ripple read column "
                    f"{chosen + 1} and ignored the other {other}."
                )
        cells = [row[chosen] if chosen < len(row) else "" for row in body]

    candidates: list[str] = []
    for cell in cells:
        cleaned = _clean_cell(cell)
        if not cleaned:
            continue
        if cleaned.lower() in HEADING_WORDS:
            heading_lines += 1
            continue
        if _looks_like_prose(cleaned):
            ignored_lines += 1
            continue
        for piece in _split_pieces(cleaned):
            name = _clean_cell(piece)
            if not name:
                continue
            if name.lower() in HEADING_WORDS:
                heading_lines += 1
                continue
            if _looks_like_name(name):
                candidates.append(name)
            else:
                ignored_lines += 1

    entries: list[ProductionEntry] = []
    seen_text: set[str] = set()
    seen_match: set[tuple[str, str]] = set()
    duplicates = 0
    ambiguous = 0
    for candidate in candidates:
        lowered = candidate.lower()
        if lowered in seen_text:
            duplicates += 1
            continue
        kind, key = _classify(candidate)
        if (kind, key) in seen_match:
            if kind == "exact":
                # Two different pastes of the same table, in different
                # datasets. Ripple cannot tell them apart, and saying so is the
                # whole point: silently keeping one would hide the other.
                ambiguous += 1
            else:
                duplicates += 1
            continue
        seen_text.add(lowered)
        seen_match.add((kind, key))
        entries.append(ProductionEntry(raw=candidate, match=key, kind=kind))

    if heading_lines:
        notes.append(
            f"{heading_lines} "
            f"{_plural(heading_lines, 'line', 'lines')} looked like a heading "
            f"row and {_plural(heading_lines, 'was', 'were')} ignored."
        )
    if ignored_lines:
        notes.append(
            f"{ignored_lines} "
            f"{_plural(ignored_lines, 'line', 'lines')} did not look like a "
            f"table name and {_plural(ignored_lines, 'was', 'were')} ignored."
        )
    if duplicates:
        notes.append(
            f"{duplicates} {_plural(duplicates, 'duplicate', 'duplicates')} "
            f"removed."
        )
    if ambiguous:
        if ambiguous == 1:
            notes.append(
                "1 pair of names is the same table to Ripple, so only the "
                "first was kept: SQL only ever says the last part of a table "
                "name."
            )
        else:
            notes.append(
                f"{ambiguous} pairs of names are the same table to Ripple, so "
                "only the first of each was kept: SQL only ever says the last "
                "part of a table name."
            )

    if not entries:
        for name in DEFAULT_PRODUCTION:
            kind, key = _classify(name)
            entries.append(ProductionEntry(raw=name, match=key, kind=kind))
        notes.append(
            "The list was empty, so Ripple used its own default: "
            + ", ".join(DEFAULT_PRODUCTION[:-1])
            + " and "
            + DEFAULT_PRODUCTION[-1]
            + "."
        )
        return ProductionRule(tuple(entries), tuple(notes), column_used, True)

    return ProductionRule(tuple(entries), tuple(notes), column_used, False)


def _entry_matches(entry: ProductionEntry, whole: str, last: str) -> bool:
    if entry.kind == "exact":
        return last == entry.match
    if entry.kind == "suffix":
        return last.endswith(entry.match)
    # fnmatchcase, not fnmatch: fnmatch folds case using the rules of whatever
    # operating system this runs on, so the same list would match differently
    # on Windows and on the demo host. Both sides are lower-cased here instead.
    return fnmatch.fnmatchcase(whole, entry.match) or fnmatch.fnmatchcase(
        last, entry.match
    )


def _split_name(table_name: str) -> tuple[str, str]:
    whole = table_name.strip().strip("`").lower()
    return whole, whole.rsplit(".", 1)[-1]


def matches(rule: ProductionRule, table_name: str) -> bool:
    """Is this table one the team publishes."""
    if not table_name:
        return False
    whole, last = _split_name(table_name)
    if not whole:
        return False
    return any(_entry_matches(entry, whole, last) for entry in rule.entries)


def _iter_file_texts(index: Any) -> Iterator[str]:
    """Every file's text, once.

    The repository index is built in a later phase, so this reads it by the
    attribute names the file map implies rather than by importing it. If the
    index turns out to expose its files under another name, this yields nothing
    and every unfound name is reported as "nowhere" - which is wrong in the
    cautious direction, but it is still a guess and it is written down.
    """
    if index is None:
        return
    files = getattr(index, "files", None)
    if files is None:
        files = getattr(index, "sources", None)
    if files is None and isinstance(index, (list, tuple)):
        files = index
    if files is None:
        return
    for item in files:
        text = getattr(item, "text", None)
        if isinstance(text, str):
            yield text


def check_against_repo(rule: ProductionRule, index: Any, parsed: Any) -> dict[str, Any]:
    """Which of the pasted tables has Ripple never seen.

    found   the table is in the SQL that was read
    written the name is in the repository, but nothing readable builds it
    nowhere the name is not in this repository at all

    The difference sends a person to two completely different places: a name
    that is written down but never built is a parsing gap on our side, and a
    name that is nowhere at all is a list that is out of date.
    """
    known: set[str] = set()
    for statement in getattr(parsed, "statements", ()) or ():
        seen_names = [getattr(statement, "target", "") or ""]
        seen_names.extend(getattr(statement, "sources", ()) or ())
        for name in seen_names:
            if not isinstance(name, str) or not name.strip():
                continue
            _, last = _split_name(name)
            if last:
                known.add(last)

    pattern_matches: dict[str, int] = {}
    missing: dict[str, str] = {}
    verdicts: dict[str, str] = {}
    for entry in rule.entries:
        if entry.kind == "exact":
            if entry.match in known:
                verdicts[entry.raw] = "found"
            else:
                missing[entry.match] = entry.raw
        else:
            # A pattern matching zero tables is doing nothing at all, and that
            # is worth knowing before a result from it is believed.
            count = sum(
                1 for table in known if _entry_matches(entry, table, table)
            )
            pattern_matches[entry.raw] = count
            verdicts[entry.raw] = "found" if count else "nowhere"

    if missing:
        # One pass over the files, not one pass per name: a real repository is
        # tens of megabytes and there may be two hundred pasted names.
        hit: set[str] = set()
        for text in _iter_file_texts(index):
            lowered = text.lower()
            for key in missing:
                if key not in hit and key in lowered:
                    hit.add(key)
            if len(hit) == len(missing):
                break
        for key, raw in missing.items():
            verdicts[raw] = "written" if key in hit else "nowhere"

    ending_matches: dict[str, int] = {}
    for key, raw in missing.items():
        # A name that matches nothing but IS the ending of tables that do exist
        # was probably meant as a pattern. Report how many, so the screen can
        # ask instead of quietly deciding.
        count = sum(1 for table in known if table != key and table.endswith(key))
        if count:
            ending_matches[raw] = count

    found: list[str] = []
    written: list[str] = []
    nowhere: list[str] = []
    for entry in rule.entries:
        verdict = verdicts.get(entry.raw, "nowhere")
        if verdict == "found":
            found.append(entry.raw)
        elif verdict == "written":
            written.append(entry.raw)
        else:
            nowhere.append(entry.raw)

    return {
        "found": found,
        "written": written,
        "nowhere": nowhere,
        "endingMatches": ending_matches,
        "patternMatches": pattern_matches,
        "tablesSeen": len(known),
    }
