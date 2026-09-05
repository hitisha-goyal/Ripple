"""The data dictionary Ripple builds for itself, out of the CREATEs it can read.

Nobody hands this tool a column list. It reads every CREATE in the repository
and writes down what it finds. The important half is what it CANNOT write
down: a table built with SELECT *, or copied whole, has no column list in the
file, and recording a guess there would make every finding below it read as
something that was read rather than worked out.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlglot import expressions as exp


@dataclass
class CatalogGap:
    """A table Ripple met whose real column list is not written down anywhere."""

    table: str
    file: str
    reason: str

    def to_json(self) -> dict[str, Any]:
        return {"table": self.table, "file": self.file, "reason": self.reason}


@dataclass
class Catalog:
    """Tables and columns learned from CREATE, plus the ones that could not be."""

    tables: dict[str, list[str]] = field(default_factory=dict)
    defined_in: dict[str, str] = field(default_factory=dict)
    gaps: list[CatalogGap] = field(default_factory=list)

    def columns_of(self, table: str) -> list[str]:
        return list(self.tables.get(table, ()))

    def has_columns(self, table: str) -> bool:
        return bool(self.tables.get(table))

    def gap_tables(self) -> set[str]:
        return {gap.table for gap in self.gaps}

    def tables_naming(self, column: str) -> list[str]:
        """Which tables write this column name down.

        A scan for a column half the warehouse shares and a scan for one only
        this table has look identical on screen without this number.
        """
        wanted = column.strip().lower()
        found = [
            table
            for table, columns in self.tables.items()
            if any(str(col).lower() == wanted for col in columns)
        ]
        return sorted(found)

    def knows_column(self, column: str) -> bool:
        return bool(self.tables_naming(column))


def build_catalog(parsed: Any) -> Catalog:
    """Read every CREATE in a parsed repository into one catalogue.

    `parsed` is the ParsedRepo the SQL reader produced. It is typed loosely on
    purpose: this module only ever reads the fields the shared contract names,
    and importing the class would tie the catalogue to the reader's import
    order for nothing.
    """
    catalog = Catalog()
    for stmt in parsed.statements:
        table = (stmt.target or "").strip()
        if not table:
            # A statement that builds nothing Ripple can name is not a table
            # definition. It is still a real usage, and lineage reports it.
            continue

        file = stmt.file
        catalog.defined_in.setdefault(table, file)

        if stmt.whole_copy:
            _record_gap(
                catalog,
                table,
                file,
                "this table is copied whole with "
                + str(stmt.whole_copy)
                + ", so no column list is written down here",
            )
            continue

        if stmt.star_note:
            _record_gap(
                catalog,
                table,
                file,
                "the column list here is filled in when the job runs ("
                + str(stmt.star_note)
                + "), so Ripple cannot read it",
            )
            continue

        if not isinstance(stmt.expr, exp.Create):
            # INSERT and MERGE load a table; they do not define one. Reading
            # columns off them would put a partial list under a table name and
            # make it look complete.
            continue

        columns, unnamed, starred = _create_columns(stmt)
        if columns:
            _record_columns(catalog, table, columns)
        if starred:
            _record_gap(
                catalog,
                table,
                file,
                "built with SELECT *, so the real column list is not visible here",
            )
        elif unnamed:
            _record_gap(
                catalog,
                table,
                file,
                str(unnamed)
                + " of the columns here are written without a name, so the "
                "column list Ripple read is shorter than the real one",
            )
        elif not columns:
            _record_gap(
                catalog,
                table,
                file,
                "this CREATE has neither a column list nor a SELECT Ripple could read",
            )
    return catalog


def _record_columns(catalog: Catalog, table: str, columns: list[str]) -> None:
    """First definition wins.

    Two files building the same table from scratch is reported on its own, as
    twoDefinitions. Merging the two column lists here would invent a table
    that no file builds.
    """
    catalog.tables.setdefault(table, columns)


def _record_gap(catalog: Catalog, table: str, file: str, reason: str) -> None:
    for gap in catalog.gaps:
        if gap.table == table and gap.file == file:
            return
    catalog.gaps.append(CatalogGap(table=table, file=file, reason=reason))


def _create_columns(stmt: Any) -> tuple[list[str], int, bool]:
    """Columns from one CREATE: the list, how many were unnamed, and whether a
    star made the list unreadable."""
    create = stmt.expr
    schema = create.this
    if isinstance(schema, exp.Schema):
        declared = [
            col.name
            for col in schema.expressions
            if isinstance(col, exp.ColumnDef) and col.name
        ]
        if declared:
            return declared, 0, False

    select = stmt.select if stmt.select is not None else _select_of(create)
    if select is None:
        return [], 0, False
    return _projection(select)


def _select_of(create: exp.Create) -> exp.Select | None:
    """The SELECT of a CREATE ... AS SELECT.

    `.this` and `.expression` are properties on sqlglot's Expression rather
    than raw args-key reads, which is why they are safe to use outside the
    dialect-compatibility module.
    """
    inner = create.expression
    if isinstance(inner, exp.Subquery):
        inner = inner.this
    if isinstance(inner, exp.Union):
        # The two sides of a UNION have to agree on their columns, so the left
        # side is enough, and it is the only one written down first.
        inner = inner.this
    if isinstance(inner, exp.Select):
        return inner
    return None


def _projection(select: exp.Select) -> tuple[list[str], int, bool]:
    columns: list[str] = []
    unnamed = 0
    starred = False
    for item in select.expressions:
        if isinstance(item, exp.Star):
            starred = True
            continue
        if isinstance(item, exp.Column) and isinstance(item.this, exp.Star):
            starred = True
            continue
        name = item.alias_or_name
        if name:
            columns.append(name)
        else:
            unnamed += 1
    return columns, unnamed, starred
