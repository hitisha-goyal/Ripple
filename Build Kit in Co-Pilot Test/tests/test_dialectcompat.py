"""The only warning anybody gets when the library moves underneath them.

Two tests, neither optional and neither nice to have:
  one fails when the installed parser is not the pinned one
  one fails when any parse-tree key stops resolving

They run against the REAL parser, because the gap being guarded is exactly the
one between what the code expects and what the library returns.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import sqlglot
from sqlglot import exp

from ripple.scanner import dialectcompat as dc

REQUIREMENTS = Path(__file__).resolve().parents[1] / "requirements.txt"
DIALECT = "bigquery"


def _pinned_version() -> str:
    """The version requirements.txt pins the parser to."""
    assert REQUIREMENTS.exists(), (
        "requirements.txt is missing, so nothing pins the parser: "
        + str(REQUIREMENTS)
    )
    for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        match = re.match(r"\s*sqlglot\s*==\s*([0-9][0-9A-Za-z.\-]*)\s*$", line)
        if match:
            return match.group(1)
    raise AssertionError(
        "requirements.txt does not pin sqlglot to one exact version. "
        "An unpinned parser is one that renames a key without anything failing."
    )


def test_the_installed_parser_is_the_pinned_one() -> None:
    pinned = _pinned_version()
    installed = sqlglot.__version__
    assert installed == pinned, (
        "sqlglot " + installed + " is installed but requirements.txt pins "
        + pinned
        + ". The keys this tool reads out of the parse tree are renamed between "
        "versions and the renames are silent, so this is not a warning to work "
        "around: either install the pinned version or check every reader in "
        "ripple/scanner/dialectcompat.py against the new one."
    )


def test_the_rename_node_class_exists() -> None:
    """ALTER TABLE a RENAME TO b: AlterRename on newer parsers, RenameTable on
    older ones. Neither means the whole-table rename hop stops being seen."""
    assert isinstance(dc.RENAME_NODE, type)
    assert issubclass(dc.RENAME_NODE, exp.Expression), (
        "Neither AlterRename nor RenameTable exists in sqlglot "
        + sqlglot.__version__
        + ", so ALTER TABLE a RENAME TO b is no longer recognised as a copy of "
        "a whole table."
    )


def test_every_parse_tree_reader_still_resolves() -> None:
    """Every function in dialectcompat, against a statement of the right shape.

    Each assertion names what stops working when it goes quiet, because a bare
    "assert x" here would be read as pedantry and skipped.
    """
    # from_of - the check that decides which tables a SELECT * covers
    select = sqlglot.parse_one("SELECT a FROM ds.t1", read=DIALECT)
    assert dc.from_of(select) is not None, (
        "Select's FROM key no longer resolves, so nothing can work out which "
        "tables a SELECT * covers"
    )

    # star_except - a column dropped BY NAME
    star = sqlglot.parse_one(
        "SELECT * EXCEPT (cm13) FROM ds.customer_demographics", read=DIALECT
    ).find(exp.Star)
    assert star is not None
    excepted = [item.name for item in dc.star_except(star)]
    assert excepted == ["cm13"], (
        "SELECT * EXCEPT(cm13) is no longer being noticed, so a column dropped "
        "by name is reported as carried through: " + repr(excepted)
    )

    # star_replace
    star = sqlglot.parse_one(
        "SELECT * REPLACE (legacy_code AS cm13) FROM ds.customer_demographics",
        read=DIALECT,
    ).find(exp.Star)
    assert star is not None
    assert dc.star_replace(star), (
        "SELECT * REPLACE no longer resolves, so a statement that names the "
        "column and stops compiling without it reads as breaking: false"
    )

    # star_rename
    star = sqlglot.parse_one(
        "SELECT * RENAME (cm13 AS cm13_new) FROM ds.customer_demographics",
        read=DIALECT,
    ).find(exp.Star)
    assert star is not None
    assert dc.star_rename(star), (
        "SELECT * RENAME no longer resolves, so the star is followed under a "
        "name the table it builds does not have"
    )

    # is_unpivot, pivot_fields - opposite operations
    unpivot_stmt = sqlglot.parse_one(
        "SELECT * FROM ds.customer_demographics "
        "UNPIVOT (val FOR metric IN (cm13, other_col))",
        read=DIALECT,
    )
    unpivot = unpivot_stmt.find(exp.Pivot)
    assert unpivot is not None, "an UNPIVOT no longer parses to a Pivot node"
    assert dc.is_unpivot(unpivot) is True, (
        "an UNPIVOT is being read as a PIVOT, which hedges downwards on a "
        "statement that hard-fails on the day the column goes"
    )
    assert dc.pivot_fields(unpivot), (
        "an UNPIVOT's IN list no longer resolves, and that list IS the column "
        "list being folded away"
    )

    pivot_stmt = sqlglot.parse_one(
        "SELECT * FROM ds.sales "
        "PIVOT (SUM(amount) AS total FOR quarter IN ('Q1', 'Q2'))",
        read=DIALECT,
    )
    pivot = pivot_stmt.find(exp.Pivot)
    assert pivot is not None, "a PIVOT no longer parses to a Pivot node"
    assert dc.is_unpivot(pivot) is False
    assert dc.pivot_fields(pivot), "a PIVOT's FOR x IN (...) no longer resolves"
    assert dc.pivot_columns(pivot), (
        "the parser no longer works out a PIVOT's output column names, so the "
        "trail ends one hop early with 'Last table in the chain' and the "
        "published table reading total_Q1 is never named"
    )

    # is_temporary - two files that each build a "t" are not sharing a table
    temp = sqlglot.parse_one("CREATE TEMP TABLE t AS SELECT 1 AS a", read=DIALECT)
    assert dc.is_temporary(temp) is True, (
        "TEMP is no longer visible on a CREATE, so two unrelated files each "
        "building their own t get merged into one invented chain"
    )
    permanent = sqlglot.parse_one("CREATE TABLE ds.t AS SELECT 1 AS a", read=DIALECT)
    assert dc.is_temporary(permanent) is False

    # merge_whens - every rename a MERGE makes
    merge = sqlglot.parse_one(
        "MERGE INTO ds.final_published t USING ds.stage s ON t.k = s.k "
        "WHEN MATCHED THEN UPDATE SET t.market = s.cm13 "
        "WHEN NOT MATCHED THEN INSERT (k, market) VALUES (s.k, s.cm13)",
        read=DIALECT,
    )
    branches = dc.merge_whens(merge)
    assert len(branches) == 2, (
        "a MERGE's WHEN branches no longer resolve, so every rename a MERGE "
        "makes disappears - and a MERGE is how a published table is loaded: "
        + repr(branches)
    )


def test_the_readers_do_not_raise_on_a_node_that_has_no_such_key() -> None:
    """An unfamiliar version must degrade to finding LESS, never to a crash in
    the middle of a repository that takes minutes to read."""
    plain = sqlglot.parse_one("SELECT 1 AS a", read=DIALECT)
    assert dc.star_except(plain) == []
    assert dc.star_replace(plain) == []
    assert dc.star_rename(plain) == []
    assert dc.pivot_fields(plain) == []
    assert dc.pivot_columns(plain) == []
    assert dc.merge_whens(plain) == []
    assert dc.is_unpivot(plain) is False
    assert dc.is_temporary(plain) is False
    assert dc.from_of(plain) is None


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__]))
