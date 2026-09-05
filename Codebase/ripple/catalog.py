"""What tables and columns exist, learned from the repository itself.

This is the "mock database" for the demo: rather than being handed a data
dictionary, Ripple reads every CREATE TABLE it can find and builds one. The
same code works against a real repository -- and whatever it cannot read shows
up as a gap rather than silently shrinking the catalogue.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlglot import exp

from .scanner.dialectcompat import star_except
from .scanner.sqlread import ParsedRepo, short_name, star_sources


@dataclass
class Catalog:
    tables: dict[str, list[str]] = field(default_factory=dict)   # TABLE -> [COLUMN, ...]
    defined_in: dict[str, str] = field(default_factory=dict)     # TABLE -> file
    gaps: list[dict] = field(default_factory=list)
    # Tables built with SELECT * whose column list was filled in from the table
    # they copy, because that table's columns ARE written down. TABLE -> {table,
    # from[], columns, file, listedIn[]}. See build_catalog.
    derived: dict[str, dict] = field(default_factory=dict)

    def has_table(self, name: str) -> bool:
        return (name or "").upper() in self.tables

    def columns(self, table: str) -> list[str]:
        return self.tables.get((table or "").upper(), [])

    def has_column(self, table: str, column: str) -> bool:
        return (column or "").upper() in {c.upper() for c in self.columns(table)}

    def listed_in(self, table: str) -> str:
        """The file that writes this table's columns down.

        For a table filled in through a star, that is the file listing the
        columns of the table it copies -- the place a person can open and read
        the list, which is not the file with the star in it.
        """
        key = (table or "").upper()
        d = self.derived.get(key)
        if d and d.get("listedIn"):
            return d["listedIn"][0]
        return self.defined_in.get(key, "")

    def to_dict(self) -> dict:
        return {
            "tables": self.tables,
            "definedIn": self.defined_in,
            "gaps": self.gaps,
            "derived": list(self.derived.values()),
            "derivedCount": len(self.derived),
            "tableCount": len(self.tables),
            "columnCount": sum(len(v) for v in self.tables.values()),
        }


def _columns_through_stars(stmt, cat: Catalog) -> list[str] | None:
    """The column list this star-built statement publishes, or None if any
    table a star covers has no written-down list yet."""
    stars = {id(star): tables for star, tables in star_sources(stmt)}
    out: list[str] = []

    def add(name: str) -> None:
        if name and name.upper() not in {o.upper() for o in out}:
            out.append(name)

    for e in stmt.select.expressions:
        star = e if isinstance(e, exp.Star) else (
            e.this if isinstance(e, exp.Column) and isinstance(e.this, exp.Star) else None)
        if star is not None:
            tables = stars.get(id(star), [])
            if not tables:
                return None
            dropped = {getattr(c, "name", "").upper() for c in star_except(star)}
            for t in tables:
                known = cat.tables.get(short_name(t).upper())
                if not known:
                    return None
                for c in known:
                    if c.upper() not in dropped:
                        add(c)
        elif isinstance(e, exp.Alias):
            add(e.alias)
        elif isinstance(e, exp.Column):
            add(e.name)
    return out


def build_catalog(parsed: ParsedRepo) -> Catalog:
    cat = Catalog()
    # Statements that build a table with a star in the projection. Filled in
    # after every written-down list has been read, because the list they need
    # may be three files further on.
    pending: list = []
    for stmt in parsed.statements:
        expr = stmt.expr
        if not isinstance(expr, exp.Create):
            continue
        schema = expr.this
        # CREATE TABLE x (col type, ...) -- an explicit column list
        if isinstance(schema, exp.Schema):
            table = schema.this.name if isinstance(schema.this, exp.Table) else None
            cols: list[str] = []
            for d in schema.expressions:
                if isinstance(d, exp.ColumnDef):
                    cols.append(d.this.name)
            if table and cols:
                cat.tables[table.upper()] = cols
                cat.defined_in[table.upper()] = stmt.file
                continue
            if table:
                cat.gaps.append(
                    {"table": table, "file": stmt.file,
                     "reason": "created without a readable column list"}
                )
                continue
        # CREATE TABLE x AS SELECT ... -- columns come from the query
        #
        # Keyed on the table's own name, without the dataset. What asks this
        # catalogue anything is the notification, and a notification names a
        # table the way a person writes one down.
        target = short_name(stmt.target) if stmt.target else None
        if target and stmt.select is not None:
            cols = []
            starred = False
            for e in stmt.select.expressions:
                if isinstance(e, exp.Star) or (isinstance(e, exp.Column)
                                               and isinstance(e.this, exp.Star)):
                    # Filled in below, from the table the star copies, when
                    # that table's columns are written down. Otherwise a gap.
                    starred = True
                    break
                if isinstance(e, exp.Alias):
                    cols.append(e.alias)
                elif isinstance(e, exp.Column):
                    cols.append(e.name)
            if starred:
                pending.append(stmt)
            elif cols:
                cat.tables.setdefault(target.upper(), cols)
                cat.defined_in.setdefault(target.upper(), stmt.file)

    # ── stars filled in from tables whose columns are written down ─────────
    # CREATE TABLE x AS SELECT * FROM y publishes every column y has. When y's
    # columns are written down -- a CREATE TABLE with the list, a query that
    # names them, or a star filled in the same way one step earlier -- x's
    # column list is known too. Reporting x as "no column list to read"
    # alarmed people about a gap that was not there. Measured on a real file:
    # `select distinct a.*` from a stage table built with a full projection
    # two files earlier was listed as a table Ripple could not see inside.
    # Passed over more than once, so a chain of stars fills in from its root.
    progress = True
    while pending and progress:
        progress = False
        for stmt in list(pending):
            key = short_name(stmt.target).upper()
            if key in cat.tables:
                pending.remove(stmt)
                continue
            cols = _columns_through_stars(stmt, cat)
            if cols is None:
                continue
            sources: list[str] = []
            for _, tables in star_sources(stmt):
                for t in tables:
                    if short_name(t) not in sources:
                        sources.append(short_name(t))
            cat.tables[key] = cols
            cat.defined_in.setdefault(key, stmt.file)
            cat.derived[key] = {
                "table": short_name(stmt.target), "from": sources, "columns": len(cols),
                "file": stmt.file,
                # Where a person can READ the list: the files that write down
                # the columns of the tables the star copies.
                "listedIn": [cat.listed_in(s) for s in sources if cat.listed_in(s)],
            }
            pending.remove(stmt)
            progress = True

    # Whatever is left copies a table whose own columns are not written down
    # anywhere Ripple read. Not a dead end: a scan follows the column straight
    # through a star and marks the steps past it as inferred. The note says
    # what the catalogue is missing, and WHY, so nobody reads it as Ripple
    # having failed to read a file.
    for stmt in pending:
        target = short_name(stmt.target)
        sources = sorted({short_name(t) for _, tables in star_sources(stmt) for t in tables})
        named = ", ".join(sources) if sources else "a table"
        cat.gaps.append(
            {"table": target, "file": stmt.file, "from": sources,
             "reason": (f"built with SELECT * from {named}, whose own column list is not "
                        f"written down anywhere Ripple read - so this table's is not either. "
                        f"A scan still follows your column through it; the column names it "
                        f"publishes are worked out rather than read")}
        )
    return cat
