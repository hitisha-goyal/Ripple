"""A SELECT * from a table whose columns are written down is read, not guessed.

CREATE TABLE x AS SELECT * FROM y publishes every column y has. When y's
columns are written down -- a CREATE TABLE with the list, a query that names
them, or a star filled in the same way one step earlier -- x's column list is
known too. Ripple used to report x as a table it could not see inside, and
people read that as Ripple failing to read a file.

The reproduction, from a real repository on 2 Sep 2026:

    CREATE OR REPLACE TABLE stage.cam_r42_loyalty_active_customer AS
    select distinct a.*
    from stage.cam_r42_loyalty_customer a
    inner join stage.card_triumph_demographics_ccm b on b.cm13 = a.cm13
    where b.cif_in = 'Y';

cam_r42_loyalty_customer is built two files earlier with every column named.
Every table name below is invented except those.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_confident_over_less import build, scan                 # noqa: E402

from ripple import narrative, notification                       # noqa: E402
from ripple.catalog import build_catalog                          # noqa: E402
from ripple.scanner.lineage import trace                          # noqa: E402

DDL = "CREATE TABLE customer_demographics (cm13 STRING, market_code STRING);"
STAR = {
    "a.sql": "CREATE OR REPLACE TABLE stage_star AS SELECT * FROM customer_demographics;",
    "b.sql": "CREATE OR REPLACE TABLE final_published AS "
             "SELECT cm13 FROM stage_star WHERE cm13 IS NOT NULL;",
}


# ── the scan ───────────────────────────────────────────────────────────────
def test_a_star_over_a_table_with_a_written_list_is_read_not_inferred(tmp_path):
    out = scan(tmp_path, {**STAR, "ddl.sql": DDL})
    assert [g["prod"] for g in out["groups"]] == ["final_published"], "the answer itself is unchanged"
    assert out["stats"]["tablesNotVisible"] == 0
    assert out["stats"]["inferredFindings"] == 0
    star = out["starTables"][0]
    assert star["known"] is True and star["columns"] == 2 and star["listedIn"] == "ddl.sql"
    assert out["attributes"][0]["notVisible"] == []
    rows = out["groups"][0]["rows"]
    star_row = next(r for r in rows if r["viaStar"])
    assert star_row["starKnown"] is True and star_row["inferredHops"] == 0
    assert all(r["inferredHops"] == 0 for r in rows)
    assert out["coverage"]["complete"] is True


def test_without_the_written_list_nothing_changes(tmp_path):
    """The old answer, exactly, for the old situation."""
    out = scan(tmp_path, STAR)
    assert out["stats"]["tablesNotVisible"] == 1
    assert out["stats"]["inferredFindings"] == 2
    star = out["starTables"][0]
    assert star["known"] is False and star["columns"] == 0 and star["listedWithout"] == []
    assert out["coverage"]["complete"] is False


def test_a_written_list_without_the_column_is_followed_and_said(tmp_path):
    """Excluding on a written list would be the catastrophic direction: the
    DDL may be stale. So the star is followed as before, and the result says
    the list has no such column rather than staying quiet."""
    out = scan(tmp_path, {**STAR, "ddl.sql": "CREATE TABLE customer_demographics (market_code STRING);"})
    assert [g["prod"] for g in out["groups"]] == ["final_published"], "followed anyway"
    star = out["starTables"][0]
    assert star["known"] is False and star["listedWithout"] == ["cm13"]
    assert out["stats"]["tablesNotVisible"] == 1


def test_the_reproduction_a_qualified_star_takes_only_its_own_table(tmp_path):
    files = {
        "ddl.sql": "CREATE TABLE card_triumph_demographics_ccm (cm13 STRING, cif_in STRING);",
        "stage.sql": "CREATE OR REPLACE TABLE cam_r42_loyalty_customer AS "
                     "SELECT cm13, loyalty_tier FROM raw_loyalty;",
        "active.sql": "CREATE OR REPLACE TABLE cam_r42_loyalty_active_customer AS\n"
                      "select distinct a.*\n"
                      "from cam_r42_loyalty_customer a\n"
                      "inner join card_triumph_demographics_ccm b on b.cm13 = a.cm13\n"
                      "where b.cif_in = 'Y';",
        "pub.sql": "CREATE OR REPLACE TABLE loyalty_published AS "
                   "SELECT loyalty_tier FROM cam_r42_loyalty_active_customer;",
    }
    cfg, idx, parsed = build(tmp_path, files)
    cat = build_catalog(parsed)
    # a.* is a's columns and none of b's.
    assert cat.columns("cam_r42_loyalty_active_customer") == ["cm13", "loyalty_tier"]
    d = cat.derived["CAM_R42_LOYALTY_ACTIVE_CUSTOMER"]
    assert d["from"] == ["cam_r42_loyalty_customer"] and d["listedIn"] == ["stage.sql"]
    assert not any(g["table"] == "cam_r42_loyalty_active_customer" for g in cat.gaps)
    out = trace(idx, parsed, [{"table": "cam_r42_loyalty_customer", "attrs": ["loyalty_tier"]}],
                change_type="removal", cfg=cfg, catalog=cat).to_dict()
    assert [g["prod"] for g in out["groups"]] == ["loyalty_published"]
    assert out["stats"]["tablesNotVisible"] == 0
    star = out["starTables"][0]
    assert star["known"] is True and star["listedIn"] == "stage.sql" and star["columns"] == 2
    # And a column of b does NOT ride through a.*
    other = trace(idx, parsed, [{"table": "card_triumph_demographics_ccm", "attrs": ["cif_in"]}],
                  change_type="removal", cfg=cfg, catalog=cat).to_dict()
    assert other["groups"] == []


# ── the catalogue ──────────────────────────────────────────────────────────
def test_the_catalogue_fills_in_a_chain_of_stars_and_honours_except(tmp_path):
    files = {
        "0.sql": "CREATE TABLE root (a INT, b INT, c INT);",
        "1.sql": "CREATE TABLE s1 AS SELECT * EXCEPT(c) FROM root;",
        "2.sql": "CREATE TABLE s2 AS SELECT r.*, 1 AS extra FROM s1 r;",
        "3.sql": "CREATE VIEW s3 AS SELECT * FROM s2;",
        "9.sql": "CREATE TABLE lost AS SELECT * FROM nowhere_known;",
    }
    _, _, parsed = build(tmp_path, files)
    cat = build_catalog(parsed)
    assert cat.columns("s1") == ["a", "b"]
    assert cat.columns("s2") == ["a", "b", "extra"]
    assert cat.columns("s3") == ["a", "b", "extra"]
    assert sorted(cat.derived) == ["S1", "S2", "S3"]
    assert cat.derived["S3"]["listedIn"] == ["0.sql"], "the list a person can open is the root's"
    gap = next(g for g in cat.gaps if g["table"] == "lost")
    assert gap["from"] == ["nowhere_known"] and "not written down" in gap["reason"]
    assert not cat.has_table("lost")
    assert cat.to_dict()["derivedCount"] == 3


def test_a_star_over_two_tables_needs_both_lists(tmp_path):
    files = {
        "x.sql": "CREATE TABLE x (a INT);",
        "y.sql": "CREATE TABLE y (b INT);",
        "j.sql": "CREATE TABLE j AS SELECT * FROM x JOIN y ON x.a = y.b;",
        "k.sql": "CREATE TABLE k AS SELECT * FROM x JOIN unknown_z ON x.a = unknown_z.b;",
    }
    _, _, parsed = build(tmp_path, files)
    cat = build_catalog(parsed)
    assert cat.columns("j") == ["a", "b"]
    assert not cat.has_table("k")
    assert any(g["table"] == "k" for g in cat.gaps)


def test_the_notice_reader_now_knows_the_columns_of_a_star_built_table(tmp_path):
    _, _, parsed = build(tmp_path, {**STAR, "ddl.sql": DDL})
    cat = build_catalog(parsed)
    n = notification.read_pasted("We are removing cm13 from stage_star on 18 September 2026.")
    out = notification.extract_by_rules(n, cat)
    up = {u["table"]: u for u in out["upstream"]}
    assert up["stage_star"]["attrs"] == ["cm13"]


# ── the words ──────────────────────────────────────────────────────────────
def test_the_summary_no_longer_says_the_list_could_not_be_read(tmp_path):
    """The sentence about SELECT * is written on the branch where nothing
    matched the published list, so that branch is the one exercised here."""
    vals = {"upstream": [{"table": "customer_demographics", "attrs": ["cm13"]}],
            "effectiveLabel": "18 Sep 2026", "pocName": "Priya"}
    out = scan(tmp_path, {**STAR, "ddl.sql": DDL}, production="_nothing_here")
    s = narrative.summarise(out, vals)
    assert "could not be read" not in s["narrative"]
    before = narrative.summarise(scan(tmp_path / "old", STAR, production="_nothing_here"), vals)
    assert "could not be read" in before["narrative"], "the old situation still says so"


# ── the practice pipeline, through the route ───────────────────────────────
def test_the_practice_view_is_filled_in_from_its_ddl():
    from fastapi.testclient import TestClient
    from ripple.api import app
    c = TestClient(app)
    cat = c.get("/api/catalog").json()
    assert cat["derivedCount"] == 1 and cat["derived"][0]["table"] == "vw_everything"
    assert cat["gaps"] == []
    sc = c.post("/api/scan", json={"upstream": [{"table": "CUSTOMER_DEMOGRAPHICS",
                                                 "attrs": ["MARKET_CODE"]}],
                                   "changeKind": "removal"}).json()
    star = next(s for s in sc["starTables"] if s["table"] == "vw_everything")
    assert star["known"] is True and star["listedIn"] == "ddl/customer_demographics.sql"
    assert sc["stats"]["tablesNotVisible"] == 0
