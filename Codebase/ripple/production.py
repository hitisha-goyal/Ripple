"""Which tables are the ones this team publishes.

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
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from fnmatch import fnmatch

# What Ripple assumes when nobody has said. Every one of these begins with an
# underscore, which is what marks it as a pattern rather than a table name.
DEFAULT_PRODUCTION = ("_PROD", "_PRD", "_PUBLISHED")
DEFAULT_TEXT = ", ".join(DEFAULT_PRODUCTION)

# ── how a line is tidied before anything is read out of it ─────────────────
# A bullet only counts as a bullet when a space follows it. Without that rule
# "*_PROD" would lose its wildcard and "PROD_*" would be fine while "*" alone
# -- which means "treat every table as published" -- would vanish entirely.
_BULLET = re.compile(r"^(?:[-–—•‣·◦*+>]\s+|\(?\d+[.)]\s+|\[\d+\]\s+)")
_FENCE = re.compile(r"^`{3,}|^~{3,}")
_SEPARATOR = re.compile(r"^[\s|:+-]*-[\s|:+-]*$")
_QUOTES = "\"'`‘’“”"
# Characters that arrive invisibly inside a pasted name: a zero-width space
# from Confluence, a no-break space from Excel, a byte-order mark from a saved
# file. Each one made a real table name fail to look like one, and the paste
# then reported it as "did not look like a table name" -- which sends a person
# to check a spelling that is right.
_INVISIBLE = re.compile("[\u200b\u200c\u200d\u2060\ufeff]")
_NBSP = "\u00a0"

# A table name, as written anywhere it might be written: bare, dataset-qualified,
# or fully qualified with a project id (which on BigQuery may contain hyphens).
_PART = r"[A-Za-z_][A-Za-z0-9_$#-]*"
_TABLE_NAME = re.compile(rf"^{_PART}(?:\.{_PART}){{0,3}}$")
# The older BigQuery spelling, project:dataset.table, as the bq command line
# and older documents write it. The colon is a separator there, not part of a
# name, and a list copied out of an old page is full of them.
_LEGACY_COLON = re.compile(rf"^({_PART}):({_PART}(?:\.{_PART}){{0,2}})$")
# A note in brackets after a name -- "sales_daily (partitioned by day)".
_BRACKET_NOTE = re.compile(r"^(.*?\S)\s*[\(\[\{][^\)\]\}]*[\)\]\}]\s*$")
# A description after the name: "sales_daily - daily sales", "sales_daily: the
# daily sales". The name has to look like a table on its own before either is
# used at all, because "please - confirm by friday" is exactly this shape.
_TAILS = (re.compile(r"^(\S+)\s+(?:[-–—|]|->)\s+\S.*$"),
          re.compile(r"^(\S+?):\s+\S.*$"))

# Column headings a list of tables tends to arrive under. Matched only against
# the first row, so a table genuinely called "source" is only ever at risk if it
# is the very first line -- and even then the note says it was dropped.
_HEADINGS = {
    "table", "tables", "table name", "table names", "tablename", "name", "names",
    "full name", "full table name", "fully qualified name", "fully qualified table name",
    "qualified name", "target table", "output table", "published table", "prod table",
    "production table", "downstream table", "dataset", "datasets", "schema", "project",
    "database", "db", "owner", "team", "layer", "type", "description", "comment",
    "comments", "status", "notes", "id", "index", "no", "s no", "sr no", "sl no",
    "row", "environment", "env", "frequency", "sla", "domain", "source", "#",
}


@dataclass(frozen=True)
class Entry:
    """One thing read out of the paste, and what Ripple will do with it."""

    given: str          # as written, once decoration was stripped
    kind: str           # "name" | "endswith" | "glob"
    key: str            # what is actually matched, upper case

    @property
    def is_pattern(self) -> bool:
        return self.kind != "name"

    def to_dict(self) -> dict:
        return {"given": self.given, "kind": self.kind, "key": self.key,
                "isPattern": self.is_pattern}


def _classify(text: str) -> Entry | None:
    """A tidied cell, as an entry -- or None if it is not one.

    Three shapes, and the order matters. Both pattern shapes are exactly what
    they were before this module existed, so a rule somebody set months ago goes
    on meaning what it meant: a wildcard is matched against the whole name, and
    a word beginning with an underscore matches the end of one.
    """
    if "*" in text or "?" in text:
        # Matched against the table's own name, like everything else here,
        # because SQL only ever says the last part. Keyed whole, a pattern
        # pasted as "mart.snap_daily_*" matched nothing at all: no bare name
        # has a dot in it. The dataset is dropped unless the wildcard is in it.
        head, _, last = text.rpartition(".")
        key = last if head and "*" not in head and "?" not in head else text
        return Entry(given=text, kind="glob", key=key.upper())
    if text.startswith("_"):
        return Entry(given=text, kind="endswith", key=text.upper())
    if _TABLE_NAME.match(text):
        # Ripple only ever learns the last part of a table name from SQL, so
        # that is what an exact name is compared against. The whole thing is
        # kept for showing back, because that is what was pasted.
        return Entry(given=text, kind="name", key=text.rsplit(".", 1)[-1].upper())
    return None


# ── reading the paste ──────────────────────────────────────────────────────
def _strip_decoration(line: str) -> str:
    """A line with Slack, Confluence and Markdown ornament taken off it."""
    out = line.strip()
    for _ in range(3):                     # "- - foo" happens; "- - - foo" does not
        stripped = _BULLET.sub("", out).strip()
        if stripped == out:
            break
        out = stripped
    return out


def _strip_cell(cell: str) -> str:
    """One value, with quotes, backticks and trailing punctuation taken off.

    Stripping never empties a value. A line of nothing but punctuation is left
    as it was so it comes back as something that was ignored, with a reason,
    rather than disappearing as if it had been a blank line.
    """
    out = original = _INVISIBLE.sub("", cell).replace(_NBSP, " ").strip()
    for _ in range(4):
        before = out
        out = re.sub(r"[,;.]+$", "", out).strip()
        if len(out) >= 2 and out[0] in _QUOTES and out[-1] in _QUOTES:
            out = out[1:-1].strip()
        out = out.strip(_QUOTES).strip()
        if out == before:
            break
    return out or original


def _is_heading(cell: str) -> bool:
    norm = re.sub(r"[\s_\-]+", " ", cell.strip().strip(":.").lower()).strip()
    return norm in _HEADINGS


def _looks_like_a_name(cell: str) -> bool:
    return bool(_TABLE_NAME.match(cell)) or "*" in cell or "?" in cell


def _looks_like_a_table(cell: str) -> bool:
    """The stricter test: a name that could only be a table, not a word.

    Used where guessing wrong invents an entry rather than declining one --
    splitting a line on spaces, and choosing which column of a grid to read.
    "please confirm by friday" is four words that all pass the loose test, and
    reading them as four published tables would be the worst kind of quiet
    mistake: four tables Ripple would then never find anywhere.
    """
    if not _looks_like_a_name(cell):
        return False
    return "_" in cell or "." in cell or any(ch.isdigit() for ch in cell)


def _tidy(cell: str) -> tuple[str, str]:
    """A cell made readable as a name, and one word saying what was done to it.

    "" when nothing was. Every other answer goes back as a note, because a
    name Ripple quietly rewrote is a name nobody can check -- and each of these
    shapes was measured as a real published table reported "not a table name".
    """
    if _looks_like_a_name(cell):
        return cell, ""
    m = _LEGACY_COLON.match(cell)
    if m:
        return f"{m.group(1)}.{m.group(2)}", "colon"
    m = _BRACKET_NOTE.match(cell)
    if m and _looks_like_a_table(_strip_cell(m.group(1))):
        return _strip_cell(m.group(1)), "bracket"
    for pattern in _TAILS:
        m = pattern.match(cell)
        if m and _looks_like_a_table(_strip_cell(m.group(1))):
            return _strip_cell(m.group(1)), "tail"
    return cell, ""


def _split_cells(line: str, delimiter: str | None) -> list[str]:
    if delimiter == "\t":
        return line.split("\t")
    if delimiter == "|":
        return line.split("|")
    parts = re.split(r"[,;]", line)
    out: list[str] = []
    for p in parts:
        p = p.strip()
        # A list pasted out of Slack can be space separated. Only split on
        # spaces when every piece is a name on its own -- otherwise "Table name"
        # would arrive as two entries instead of being spotted as a heading.
        pieces = p.split()
        if len(pieces) > 1 and all(_looks_like_a_table(_strip_cell(x)) for x in pieces):
            out.extend(pieces)
        else:
            out.append(p)
    return out


def _delimiter_of(lines: list[str]) -> str | None:
    """Tab or pipe means columns. Commas are a list unless a heading says otherwise."""
    if any("\t" in ln for ln in lines):
        return "\t"
    if any(len([c for c in ln.split("|") if c.strip()]) >= 2 for ln in lines):
        return "|"
    return None


def _pick_column(rows: list[list[str]], heading: list[str] | None) -> tuple[int, dict | None]:
    """Which column of a pasted grid holds the table names, and how it was decided.

    A heading with the word "table" in it settles the question outright. Failing
    that the column with the most values that look like table names wins. Either
    way the answer is handed back so the screen can say which column it took --
    a grid read down the wrong column is a silent, total misread.
    """
    width = max((len(r) for r in rows), default=0)
    if width <= 1:
        return 0, None
    # Columns that are empty everywhere are an artefact of splitting a Markdown
    # row on its pipes, not columns anybody pasted. Counting them would say
    # "the paste had 4 columns" about a two-column table.
    filled = [i for i in range(width)
              if any(i < len(r) and r[i].strip() for r in rows)]
    used = len(filled)

    def place(i: int) -> int:
        return (filled.index(i) + 1) if i in filled else i + 1

    if heading:
        for i, h in enumerate(heading[:width]):
            norm = re.sub(r"[\s_\-]+", " ", h.strip().strip(":.").lower()).strip()
            if "table" in norm and "count" not in norm:
                return i, {"index": i, "position": place(i), "heading": h.strip(),
                           "by": "heading", "columns": used}
    scores: list[tuple[int, int]] = []
    for i in range(width):
        score = 0
        for r in rows:
            cell = _strip_cell(r[i]) if i < len(r) else ""
            if not cell:
                continue
            if _looks_like_a_table(cell):
                score += 3
            elif _looks_like_a_name(cell):
                score += 1
        scores.append((score, -i))
    best = max(range(width), key=lambda i: scores[i])
    head = heading[best].strip() if heading and best < len(heading) else ""
    return best, {"index": best, "position": place(best), "heading": head,
                  "by": "content", "columns": used}


def parse(text: str) -> "ProductionRule":
    """Read a pasted list, however it arrived, and say what was made of it."""
    raw = str(text or "")
    notes: list[dict] = []
    # Counted on the raw lines, before anything is tidied: the characters are
    # taken out on the way in, and this note is the only trace they leave.
    invisible = sum(1 for ln in raw.splitlines()
                    if ln.strip() and (_INVISIBLE.search(ln) or _NBSP in ln))
    if invisible:
        notes.append({"kind": "tidied", "how": "invisible", "count": invisible, "examples": [],
                      "text": f"{invisible} line{'' if invisible == 1 else 's'} had invisible "
                              f"characters in {'it' if invisible == 1 else 'them'} - a zero-width "
                              f"space or a no-break space, the kind a copy out of Confluence or "
                              f"Excel brings along. Ripple removed them."})
    fenced = 0
    lines: list[str] = []
    for line in raw.splitlines():
        if _FENCE.match(line.strip()):
            fenced += 1
            continue
        lines.append(line)
    if fenced:
        notes.append({"kind": "fence", "count": fenced, "examples": [],
                      "text": f"{fenced} code-fence line{'' if fenced == 1 else 's'} "
                              f"(```) ignored."})

    tidied = [_strip_decoration(ln) for ln in lines]
    kept: list[str] = []
    separators = 0
    for ln in tidied:
        if not ln:
            continue
        if _SEPARATOR.match(ln):
            separators += 1
            continue
        kept.append(ln)
    if separators:
        notes.append({"kind": "separator", "count": separators, "examples": [],
                      "text": f"{separators} ruled line{'' if separators == 1 else 's'} "
                              f"from a table border ignored."})

    delimiter = _delimiter_of(kept)
    rows = [_split_cells(ln, delimiter) for ln in kept]
    rows = [[c for c in r] for r in rows if any(c.strip() for c in r)]

    # A heading row, if the first row is one. Checked before anything is read as
    # a name so that "TABLE_NAME" at the top of an Excel paste is not offered as
    # a table called TABLE_NAME.
    heading: list[str] | None = None
    if rows:
        first = [_strip_cell(c) for c in rows[0] if c.strip()]
        if first and any(_is_heading(c) for c in first) and not all(
            _looks_like_a_name(c) and not _is_heading(c) for c in first
        ):
            heading = [_strip_cell(c) for c in rows[0]]
            notes.append({"kind": "heading", "count": 1,
                          "examples": [" · ".join(first)[:120]],
                          "text": "1 line looked like a heading row and was ignored."})
            rows = rows[1:]

    column: dict | None = None
    cells: list[str] = []
    if delimiter and rows:
        index, column = _pick_column(rows, heading)
        for r in rows:
            cells.append(_strip_cell(r[index]) if index < len(r) else "")
        if column and column["columns"] > 1:
            dropped = column["columns"] - 1
            where = (f'the column headed "{column["heading"]}"' if column.get("heading")
                     else f"column {column.get('position', column['index'] + 1)}")
            notes.append({
                "kind": "column", "count": dropped, "examples": [],
                "text": f"The paste had {column['columns']} columns. Ripple read {where} "
                        f"and ignored the other {dropped}.",
            })
    else:
        for r in rows:
            cells.extend(_strip_cell(c) for c in r)

    entries: list[Entry] = []
    seen: dict[str, Entry] = {}
    duplicates: list[str] = []
    same_table: list[str] = []
    rejected: list[str] = []
    headings_inline = 0
    tidied: dict[str, list[str]] = {}
    for cell in cells:
        if not cell:
            continue
        if _is_heading(cell) and not _TABLE_NAME.match(cell):
            headings_inline += 1
            continue
        cell, how = _tidy(cell)
        if how:
            tidied.setdefault(how, []).append(cell[:60])
        entry = _classify(cell)
        if entry is None:
            rejected.append(cell[:80])
            continue
        marker = f"{entry.kind}:{entry.key}"
        if marker in seen:
            kept = seen[marker]
            # The same name twice is a duplicate. Two *different* names that
            # Ripple cannot tell apart is a different thing entirely, and it has
            # to be said rather than quietly counted as a duplicate: SQL only
            # ever tells Ripple the last part of a table name.
            if cell.upper() == kept.given.upper():
                duplicates.append(cell)
            else:
                same_table.append(f"{kept.given} and {cell}")
            continue
        seen[marker] = entry
        entries.append(entry)

    if headings_inline:
        notes.append({"kind": "heading", "count": headings_inline, "examples": [],
                      "text": f"{headings_inline} more line{'' if headings_inline == 1 else 's'} "
                              f"looked like a heading and {'was' if headings_inline == 1 else 'were'} ignored."})
    # Names that were read only after something was taken off them. Said out
    # loud, one line per kind, because a rewrite nobody can see is a rewrite
    # nobody can correct.
    for how, kept in tidied.items():
        n, one = len(kept), len(kept) == 1
        text_for = {
            "colon": (f"{n} name{'' if one else 's'} used the older project:dataset.table "
                      f"form. Ripple read {'it' if one else 'them'} as project.dataset.table."),
            "bracket": (f"{n} name{'' if one else 's'} had a note in brackets after "
                        f"{'it' if one else 'them'}. Ripple kept the name and dropped the note."),
            "tail": (f"{n} line{'' if one else 's'} had a description after the name. "
                     f"Ripple kept the name and dropped the rest."),
        }
        notes.append({"kind": "tidied", "how": how, "count": n, "examples": kept[:6],
                      "text": text_for[how]})
    if duplicates:
        notes.append({"kind": "duplicate", "count": len(duplicates),
                      "examples": duplicates[:6],
                      "text": f"{len(duplicates)} duplicate"
                              f"{'' if len(duplicates) == 1 else 's'} removed."})
    if rejected:
        notes.append({"kind": "rejected", "count": len(rejected), "examples": rejected[:6],
                      "text": f"{len(rejected)} line{'' if len(rejected) == 1 else 's'} did not "
                              f"look like a table name and {'was' if len(rejected) == 1 else 'were'} "
                              f"ignored."})

    if same_table:
        notes.append({
            "kind": "sameTable", "count": len(same_table), "examples": same_table[:6],
            "text": f"{len(same_table)} pair{'' if len(same_table) == 1 else 's'} of names "
                    f"{'is' if len(same_table) == 1 else 'are'} the same table to Ripple, so "
                    f"only the first of each was kept. SQL only "
                    f"ever says the last part of a table name, which means two datasets holding "
                    f"a table of the same name cannot be told apart.",
        })

    return ProductionRule(text=raw, entries=tuple(entries), notes=tuple(notes), column=column)


# Kept under its old name: the old rule was "a comma separated list of patterns",
# and everything that called it still gets exactly that.
def parse_production_rule(text: str) -> tuple[str, ...]:
    return tuple(e.given for e in parse(text).entries)


# A date-sharded table is written with its day on the end -- events_20260101 --
# and pasted without it, because the family is what the team publishes. A
# run-time placeholder glued onto a name is the same shape one step removed:
# fact_returns_${RUN_DATE} reaches the parser as fact_returns_RUN_DATE. Neither
# is a different table from the one on the list. Measured before this: both
# came back "not written anywhere in this repository", one screen away from a
# scan that then called the same tables safe.
#
# Loose on purpose, and in the safe direction. A name matched this way is
# COUNTED AS PUBLISHED, which can only add a finding, never hide one -- and
# every such match is reported as the family match it is, never as an exact
# one. Nothing here ever excludes a table.
_SHARD = re.compile(r"_(?:\d{8}|\d{6}|\d{4}_\d{2}_\d{2}|\d{8}_\d{2,6}|\d{8}T\d{6})$")
_DECORATOR = re.compile(r"\$\d+$")
_RUN_WORDS = frozenset({
    "DATE", "DT", "DS", "DS_NODASH", "RUN_DATE", "RUNDATE", "RUN_DT", "LOAD_DATE", "LOADDATE",
    "LOAD_DT", "EXECUTION_DATE", "EXEC_DATE", "NEXT_DS", "PREV_DS", "PARTITION_DATE",
    "PARTITION_DT", "PARTITIONDATE", "TABLE_SUFFIX", "SUFFIX", "SHARD", "YYYYMMDD", "YYYYMM",
    "YYYY_MM_DD", "RUN_ID", "RUNID", "BATCH_ID", "BATCHID", "RUN_TS", "SNAPSHOT_DATE",
    "SNAPSHOT_DT", "AS_OF", "ASOF", "AS_OF_DATE", "TIMESTAMP", "TS", "ENV", "ENVIRONMENT",
})


def family_of(name: str) -> tuple[str, str]:
    """The family a sharded or placeholder-suffixed name belongs to, and why.

    ("", "") when the name is not one of those. Compared in upper case, on
    the table's own name: the dataset in front is taken off first.
    """
    bare = _DECORATOR.sub("", (name or "").strip().rsplit(".", 1)[-1]).upper()
    m = _SHARD.search(bare)
    if m and m.start():
        return bare[:m.start()], "shard"
    parts = bare.split("_")
    # The longer tail first: fact_returns_RUN_DATE belongs to fact_returns,
    # not to fact_returns_run.
    for take in (2, 1):
        if len(parts) > take and "_".join(parts[-take:]) in _RUN_WORDS:
            return "_".join(parts[:-take]), "placeholder"
    return "", ""


@dataclass
class ProductionRule:
    """A pasted list, read. Immutable in practice -- rebuilt when the text changes."""

    text: str = ""
    entries: tuple[Entry, ...] = ()
    notes: tuple[dict, ...] = ()
    column: dict | None = None
    _names: frozenset = field(default=frozenset(), repr=False, compare=False)
    _globs: tuple = field(default=(), repr=False, compare=False)
    _suffixes: tuple = field(default=(), repr=False, compare=False)

    def __post_init__(self) -> None:
        # Exact names are a set lookup, because a real list is hundreds long and
        # this is asked once per table visited on every hop of every scan.
        object.__setattr__(self, "_names",
                           frozenset(e.key for e in self.entries if e.kind == "name"))
        object.__setattr__(self, "_globs",
                           tuple(e.key for e in self.entries if e.kind == "glob"))
        object.__setattr__(self, "_suffixes",
                           tuple(e.key for e in self.entries if e.kind == "endswith"))

    # ── matching ───────────────────────────────────────────────────────────
    def matches(self, table: str) -> bool:
        return bool(self.match_how(table))

    def match_how(self, table: str) -> str:
        """Why this table counts as published -- or "" when it does not.

        "name", "glob" and "suffix" are exact readings of the list. "shard"
        and "placeholder" are family matches (see family_of): real, in the
        safe direction, and reported as what they are wherever the answer goes
        on screen.
        """
        name = (table or "").strip()
        if not name:
            return ""
        bare = _DECORATOR.sub("", name.rsplit(".", 1)[-1]).upper()
        if bare in self._names:
            return "name"
        for pattern in self._globs:
            if fnmatch(bare, pattern):
                return "glob"
        for pattern in self._suffixes:
            if bare.endswith(pattern):
                return "suffix"
        family, how = family_of(bare)
        if family and family in self._names:
            return how
        return ""

    # ── what it is made of ─────────────────────────────────────────────────
    @property
    def names(self) -> tuple[Entry, ...]:
        return tuple(e for e in self.entries if e.kind == "name")

    @property
    def patterns(self) -> tuple[Entry, ...]:
        return tuple(e for e in self.entries if e.is_pattern)

    def is_empty(self) -> bool:
        return not self.entries

    def one_line(self) -> str:
        """The rule as one short line, for a status row rather than a screen.

        A list of two hundred table names does not fit on a line and pretending
        otherwise produces a row of dots. So a long list is counted instead.
        """
        names, patterns = self.names, self.patterns
        if not self.entries:
            return "not set"
        if len(self.entries) <= 4:
            return ", ".join(e.given for e in self.entries)
        bits = []
        if names:
            bits.append(f"{len(names)} table name{'' if len(names) == 1 else 's'}")
        if patterns:
            bits.append(f"{len(patterns)} pattern{'' if len(patterns) == 1 else 's'} "
                        f"({', '.join(e.given for e in patterns[:3])}"
                        f"{'…' if len(patterns) > 3 else ''})")
        return " and ".join(bits)

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "entries": [e.to_dict() for e in self.entries],
            "names": [e.given for e in self.names],
            "patterns": [e.given for e in self.patterns],
            "nameCount": len(self.names),
            "patternCount": len(self.patterns),
            "notes": [dict(n) for n in self.notes],
            "column": self.column,
            "oneLine": self.one_line(),
        }


EMPTY = ProductionRule()


# ── checking the list against the repository that was actually read ────────
def check_against_repo(rule: ProductionRule, index, parsed) -> dict:
    """Which of these tables Ripple has actually seen, and which it has not.

    This is the point of taking a pasted list at all. If fifty tables are pasted
    and Ripple only ever sees forty-four of them, the other six are either
    misspelled or built somewhere it could not read -- and both of those have to
    be known *before* a result from this list is believed, not after.

    Three answers, and the difference between them matters:

    * **found** -- the table is in the SQL Ripple read.
    * **written down** -- the name is in the repository, but not in any statement
      Ripple could turn into a table. Something builds it out of reach.
    * **nowhere** -- the name is not in this repository at all. A typo, a table
      from another repository, or one that is created by a tool.
    """
    known = _table_names(parsed)
    names = rule.names
    found: list[dict] = []
    unseen: list[Entry] = []
    # Every sharded or placeholder-suffixed name in the code, by the family it
    # belongs to. Worked out once here rather than once per pasted name: a
    # real list is hundreds long and a real repository has thousands of names.
    families: dict[str, dict[str, list[str]]] = {}
    for t in known:
        family, how = family_of(t)
        if family:
            families.setdefault(family, {}).setdefault(how, []).append(t)
    for e in names:
        if e.key in known:
            found.append({"given": e.given, "key": e.key, "state": "found", "how": "exact",
                          "as": [], "asCount": 0})
        elif e.key in families:
            # The list says order_lines; the code writes order_lines_20260101.
            # Found -- and said to be found THIS way, because "the table you
            # pasted is here" and "dated copies of it are here" are different
            # sentences to the person checking the list.
            hows = families[e.key]
            how = "shard" if "shard" in hows else "placeholder"
            spellings = sorted({t for ts in hows.values() for t in ts})
            found.append({"given": e.given, "key": e.key, "state": "found", "how": how,
                          "as": spellings[:6], "asCount": len(spellings)})
        else:
            unseen.append(e)

    # One pass over the files for everything that was not in the parsed SQL,
    # rather than one pass per name: a real repository is tens of megabytes.
    mentions: dict[str, int] = {}
    if unseen and index is not None and getattr(index, "files", None):
        wanted = {e.key: 0 for e in unseen}
        pattern = index._pattern([e.key for e in unseen])
        for f in index.files:
            hits = {m.upper() for m in pattern.findall(f.text)}
            for hit in hits:
                if hit in wanted:
                    wanted[hit] += 1
        mentions = wanted

    missing: list[dict] = []
    for e in unseen:
        seen_in = mentions.get(e.key, 0)
        # A name nobody uses as a table may still be a naming convention that
        # was meant as a pattern. Said out loud rather than guessed at, because
        # silently re-reading it as a pattern is how a rule stops meaning what
        # it says.
        ends_with = sum(1 for t in known if t.endswith(e.key) and t != e.key)
        missing.append({
            "given": e.given, "key": e.key,
            "state": "written" if seen_in else "nowhere",
            "files": seen_in,
            "endsWith": ends_with,
        })

    pattern_hits: list[dict] = []
    for e in rule.patterns:
        hit = sorted(t for t in known
                     if (fnmatch(t, e.key) if e.kind == "glob" else t.endswith(e.key)))
        pattern_hits.append({"given": e.given, "kind": e.kind, "matches": len(hit),
                             "examples": hit[:6]})

    return {
        "checked": bool(known),
        "tablesKnown": len(known),
        "found": found,
        "missing": missing,
        "patterns": pattern_hits,
        "foundCount": len(found),
        # How many of those were found as a family rather than by their exact
        # name. The screen says so beside the count, because a list that reads
        # "all 50 found" over 12 family matches is telling half the truth.
        "familyCount": len([f for f in found if f["how"] != "exact"]),
        "missingCount": len(missing),
    }


def _table_names(parsed) -> set[str]:
    """Every table name in the SQL Ripple understood: written or read."""
    if parsed is None:
        return set()
    cached = getattr(parsed, "_table_names_cache", None)
    if cached is not None and cached[0] == len(parsed.statements):
        return cached[1]
    names: set[str] = set()
    for s in parsed.statements:
        if s.target:
            names.add(_DECORATOR.sub("", s.target.rsplit(".", 1)[-1]).upper())
        for src in s.sources:
            if src:
                names.add(_DECORATOR.sub("", src.rsplit(".", 1)[-1]).upper())
    try:
        parsed._table_names_cache = (len(parsed.statements), names)
    except Exception:      # pragma: no cover - a stand-in object in a test
        pass
    return names
