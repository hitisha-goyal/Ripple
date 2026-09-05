"""ALTER TABLE, and the DDL that names a table and builds nothing.

``_target_of`` covered CREATE, INSERT, MERGE, DELETE and UPDATE, and not ALTER.
So a repository holding its own rename migration --

    ALTER TABLE stage.customers RENAME COLUMN email TO email_address;

-- came back ``target=None, sources=[]`` and reported no impact at all for the
column the migration renames. That is the plainest statement of a rename the
language has, and it was the one hop Ripple could not see.

A search index, a vector index, a row access policy and an UNDROP have the
opposite problem. They name a table and its columns and carry nothing anywhere,
the parser gives up on all of them, and the whole statement was invisible: the
file went on the "check by hand" list with nothing saying which table or which
column it was about. They are read for what they name, and never turned into
lineage.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from test_confident_over_less import scan, build                # noqa: E402


# ── ALTER TABLE ... RENAME COLUMN ──────────────────────────────────────────
RENAME = {
    "01_migrate.sql": "ALTER TABLE customer_demographics RENAME COLUMN cm13 TO cm13_new;",
    "02_load.sql": "CREATE OR REPLACE TABLE final_published AS "
                   "SELECT cm13_new FROM customer_demographics;",
}


def test_a_rename_migration_is_followed_as_the_alias_hop_it_is(tmp_path):
    out = scan(tmp_path, RENAME)
    assert [g["prod"] for g in out["groups"]] == ["final_published"], out["groups"]
    assert out["risk"] == "medium", out["risk"]


def test_the_rename_itself_is_reported_on_the_line_it_is_written(tmp_path):
    out = scan(tmp_path, RENAME)
    rows = [r for g in out["groups"] for r in g["rows"]]
    renamed = [r for r in rows if r["file"] == "01_migrate.sql"]
    assert renamed, rows
    assert renamed[0]["logic"] == "Renamed by ALTER TABLE", renamed[0]
    assert renamed[0]["alias"] == "cm13_new", renamed[0]
    assert renamed[0]["breaking"] is True


def test_an_alter_names_the_table_it_changes(tmp_path):
    _, _, parsed = build(tmp_path, RENAME)
    alter = [s for s in parsed.statements if s.file == "01_migrate.sql"][0]
    assert alter.target == "customer_demographics"
    assert alter.sources == {"customer_demographics"}


def test_a_drop_column_migration_stops_the_trail_and_says_so(tmp_path):
    """A file that already drops the column is the most useful thing a scan can
    find, and it produced nothing at all."""
    out = scan(tmp_path, {
        "01_migrate.sql": "ALTER TABLE customer_demographics DROP COLUMN cm13;",
        "02_load.sql": "CREATE OR REPLACE TABLE final_published AS "
                       "SELECT cm13 FROM customer_demographics;"})
    rows = [r for g in out["groups"] + out["reached"] for r in g["rows"]] + out["other"]
    dropped = [r for r in rows if r["file"] == "01_migrate.sql"]
    assert dropped and dropped[0]["logic"] == "Dropped by ALTER TABLE", rows
    assert "already drops the column" in dropped[0]["impact"]
    # The column stops at this statement. It does not carry on out of it.
    assert dropped[0]["alias"] == "cm13", dropped[0]


def test_altering_a_column_type_names_the_column(tmp_path):
    out = scan(tmp_path, {
        "a.sql": "ALTER TABLE customer_demographics ALTER COLUMN cm13 SET DATA TYPE STRING;"})
    rows = [r for g in out["groups"] for r in g["rows"]] + \
           [r for g in out["reached"] for r in g["rows"]]
    assert out["risk"] != "none", out["risk"]
    assert any(r["logic"] == "Changed by ALTER TABLE" for r in rows), rows


def test_a_rename_to_a_new_table_still_works(tmp_path):
    """The guard. ALTER TABLE ... RENAME TO is a whole-table copy and was
    already handled; adding ALTER to _target_of must not disturb it."""
    out = scan(tmp_path, {
        "a.sql": "ALTER TABLE customer_demographics RENAME TO cd_v2;",
        "b.sql": "CREATE OR REPLACE TABLE final_published AS SELECT cm13 FROM cd_v2;"})
    assert [g["prod"] for g in out["groups"]] == ["final_published"], out["groups"]


# ── DDL that names a table and carries nothing ─────────────────────────────
def test_a_row_access_policy_naming_the_column_is_reported(tmp_path):
    out = scan(tmp_path, {
        "a.sql": "CREATE ROW ACCESS POLICY apac ON `p.d.customer_demographics` "
                 "GRANT TO ('group:apac@acme.com') FILTER USING (cm13 IN ('IN','SG'));"})
    ref = out["referencedHere"]
    assert [r["kind"] for r in ref] == ["row access policy"], ref
    assert ref[0]["namesColumns"] == ["cm13"], ref
    assert ref[0]["table"] == "p.d.customer_demographics", ref


def test_a_policy_naming_the_column_stops_risk_reading_no_impact(tmp_path):
    """It carries the column nowhere, so there is no lineage and no finding --
    and it stops working on the day the column goes."""
    out = scan(tmp_path, {
        "a.sql": "CREATE ROW ACCESS POLICY apac ON `p.d.customer_demographics` "
                 "GRANT TO ('group:apac@acme.com') FILTER USING (cm13 IN ('IN','SG'));"})
    assert out["risk"] == "low", out["risk"]
    assert out["groups"] == []


def test_a_search_index_over_the_column_is_reported(tmp_path):
    out = scan(tmp_path, {
        "a.sql": "CREATE SEARCH INDEX my_idx ON customer_demographics(cm13, other_col);"})
    ref = out["referencedHere"]
    assert [r["kind"] for r in ref] == ["search index"], ref
    assert ref[0]["namesColumns"] == ["cm13"], ref


def test_an_undrop_no_longer_takes_its_neighbours_down_with_it(tmp_path):
    """UNDROP TABLE was a hard parse error, and a hard parse error in sqlglot
    loses the statements either side of it."""
    out = scan(tmp_path, {
        "a.sql": "UNDROP TABLE customer_demographics;\n"
                 "CREATE OR REPLACE TABLE final_published AS "
                 "SELECT cm13 FROM customer_demographics;\n"})
    assert [g["prod"] for g in out["groups"]] == ["final_published"], out["groups"]
    assert [r["kind"] for r in out["referencedHere"]] == ["UNDROP"], out["referencedHere"]


def test_ddl_that_was_read_is_not_also_listed_as_unreadable(tmp_path):
    """It is one statement. Counted twice it is two problems where there is
    one, on the list that has to stay short enough to read."""
    out = scan(tmp_path, {
        "a.sql": "CREATE SEARCH INDEX my_idx ON customer_demographics(cm13);"})
    assert out["unreadable"] == [], out["unreadable"]
    assert out["mentionsOnly"] == [], out["mentionsOnly"]


def test_an_index_on_a_table_nobody_asked_about_is_not_listed(tmp_path):
    """The guard. Every warehouse is full of indexes on tables this scan has
    never heard of, and listing those buries the ones that matter."""
    out = scan(tmp_path, {
        "a.sql": "CREATE SEARCH INDEX other_idx ON some_other_table(some_other_col);",
        "b.sql": "CREATE OR REPLACE TABLE final_published AS "
                 "SELECT cm13 FROM customer_demographics;"})
    assert out["referencedHere"] == [], out["referencedHere"]


def test_an_index_is_never_drawn_as_a_hop(tmp_path):
    """It carries no column anywhere. Reading it loosely may add a row to a
    list; it must never move a chain."""
    out = scan(tmp_path, {
        "a.sql": "CREATE SEARCH INDEX my_idx ON customer_demographics(cm13);"})
    assert out["groups"] == []
    assert out["reached"] == []
    assert out["stats"]["tablesReached"] == 0
