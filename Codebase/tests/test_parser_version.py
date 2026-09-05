"""The parse tree must be read the same way whichever sqlglot is installed.

sqlglot renames the keys inside its own nodes between major versions, and three
of the renames that matter here are SILENT: the old key simply returns None, so
the code carries on and finds nothing. Two of them switch off things this tool
exists to do -- ``SELECT * EXCEPT(col)`` stops being noticed, and every rename a
MERGE makes disappears.

Nothing raises. Every test would go on passing on the version installed today
and the answers would go quietly wrong on the next one. So the keys are read
through ripple/scanner/dialectcompat.py, and these tests fail LOUDLY the moment
one of them stops resolving.

They are written against the real parser rather than against a mock, because
the thing being guarded is exactly the gap between what the code expects and
what the library actually returns.
"""
from __future__ import annotations

import sys
from pathlib import Path

import sqlglot
from sqlglot import exp

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ripple.scanner import dialectcompat as compat          # noqa: E402


def parse(sql: str):
    return sqlglot.parse_one(sql, dialect="bigquery")


def test_the_from_clause_still_resolves():
    """Empty, the check that decides which tables a SELECT * covers finds
    nothing, and every star hop stops being followed."""
    sel = parse("SELECT * FROM customer_demographics").find(exp.Select)
    found = compat.from_of(sel)
    assert found is not None
    assert isinstance(found.this, exp.Table)


def test_select_star_except_still_resolves():
    """Empty, a column dropped BY NAME is reported as carried through -- which
    is the opposite of the truth, on the one shape that stops a chain."""
    star = parse("SELECT * EXCEPT(cm13) FROM customer_demographics").find(exp.Star)
    assert [c.name for c in compat.star_except(star)] == ["cm13"]


def test_select_star_replace_still_resolves():
    star = parse("SELECT * REPLACE(legacy AS cm13) FROM customer_demographics").find(exp.Star)
    assert compat.star_replace(star), "REPLACE swaps a column and must be visible"


def test_every_merge_branch_still_resolves():
    """Empty, every rename a MERGE makes disappears -- and a MERGE is how a
    published table is normally loaded on BigQuery."""
    merged = parse(
        "MERGE INTO tgt t USING src s ON t.k = s.k "
        "WHEN MATCHED THEN UPDATE SET market = s.cm13 "
        "WHEN NOT MATCHED THEN INSERT (k, market) VALUES (s.k, s.cm13)")
    whens = compat.merge_whens(merged)
    assert len(whens) == 2, whens


def test_the_rename_node_still_exists():
    """The one rename that is loud: the class stops existing altogether."""
    renamed = parse("ALTER TABLE old_name RENAME TO new_name")
    actions = renamed.args.get("actions") or []
    assert any(isinstance(a, compat.RENAME_NODE) for a in actions), actions


def test_the_pinned_version_is_the_one_installed():
    """A build made against a different parser is a different tool. The pin is
    in requirements.txt; this fails if the environment has drifted from it."""
    pinned = ""
    for line in (Path(__file__).resolve().parent.parent / "requirements.txt") \
            .read_text(encoding="utf-8").splitlines():
        if line.strip().lower().startswith("sqlglot=="):
            pinned = line.split("==", 1)[1].split()[0].strip()
            break
    assert pinned, "sqlglot must be pinned in requirements.txt"
    assert sqlglot.__version__ == pinned, (
        f"requirements.txt pins {pinned} but {sqlglot.__version__} is installed")


def test_a_temporary_table_is_still_recognisable():
    """Empty, every file's temp table merges with every other file's -- which
    invents a chain to a published table nobody touched."""
    assert compat.is_temporary(parse("CREATE TEMP TABLE t AS SELECT 1 AS a"))
    assert compat.is_temporary(parse("CREATE TEMPORARY TABLE t AS SELECT 1 AS a"))
    assert not compat.is_temporary(parse("CREATE TABLE t AS SELECT 1 AS a"))


def test_the_unpivot_column_list_still_resolves():
    """Empty, an UNPIVOT that names the column reads as a plain SELECT * -- so a
    statement that fails outright on the day of the change is reported as
    'nothing here fails on the day of the change'."""
    pivot = parse("SELECT * FROM cd UNPIVOT (val FOR metric IN (cm13, other_col))") \
        .find(exp.Pivot)
    assert compat.is_unpivot(pivot)
    fields = compat.pivot_fields(pivot)
    assert fields, "the IN list is where the column names are"
    named = {c.name.upper() for f in fields for c in f.find_all(exp.Column)}
    assert "CM13" in named, named


def test_the_pivot_output_names_still_resolve():
    """Empty, the trail is declared finished one hop early: the table PIVOT
    builds has columns total_Q1 and total_Q2 and nothing knows their names."""
    pivot = parse("SELECT * FROM (SELECT k, quarter, cm13 FROM cd) "
                  "PIVOT (SUM(cm13) AS total FOR quarter IN ('Q1', 'Q2'))").find(exp.Pivot)
    assert not compat.is_unpivot(pivot)
    assert compat.pivot_columns(pivot) == ["total_Q1", "total_Q2"]
