"""The table itself is what changes, not one column of it.

Sometimes the notice says the upstream table is being dropped, renamed, moved
or rebuilt. The question is then "what reads it" -- every statement, every
column, and everything built from what those statements build.

Measured before any of this existed, 2 Sep 2026: a table sent in with no
attribute went through the column walk with nothing to walk, and came back
"No usage found" with a blank where the name should have been, in a letter
ready to send. Every shape below is pinned so that answer cannot come back.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ripple import narrative, notification                       # noqa: E402
from ripple.catalog import build_catalog                          # noqa: E402
from ripple.config import Settings, parse_production_rule        # noqa: E402
from ripple.scanner.lineage import WHOLE_TABLE, trace            # noqa: E402
from ripple.scanner.repo import RepoIndex                        # noqa: E402
from ripple.scanner.sqlread import parse_repo                    # noqa: E402


def build(tmp_path: Path, files: dict, production: str = "_published",
          max_hops: int = 4) -> tuple:
    for name, text in files.items():
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    cfg = Settings()
    cfg.sql_dialect = "bigquery"
    cfg.repo_path = tmp_path
    cfg.max_hops = max_hops
    cfg.production_patterns = parse_production_rule(production)
    idx = RepoIndex.build(tmp_path, cfg)
    return cfg, idx, parse_repo(idx, cfg)


def scan_whole(tmp_path: Path, files: dict, table: str = "customer_demographics",
               production: str = "_published", change: str = "removal",
               max_hops: int = 4) -> dict:
    cfg, idx, parsed = build(tmp_path, files, production=production, max_hops=max_hops)
    return trace(idx, parsed, [{"table": table, "attrs": [], "whole": True}],
                 change_type=change, cfg=cfg).to_dict()


CHAIN = {
    "ddl.sql": "CREATE TABLE customer_demographics (cm13 STRING, market_code STRING);",
    "a.sql": """
        CREATE OR REPLACE TABLE stage_cust AS
        SELECT cm13, market_code FROM customer_demographics WHERE cm13 IS NOT NULL;
    """,
    "b.sql": """
        CREATE OR REPLACE TABLE final_published AS
        SELECT s.cm13, r.name FROM stage_cust s JOIN region_ref r ON s.market_code = r.code;
    """,
    # Names no column at all. The column walk can never see this statement;
    # the table walk must.
    "c.sql": """
        CREATE OR REPLACE TABLE counts_only AS
        SELECT COUNT(*) AS n FROM customer_demographics;
    """,
    "d.sql": "CREATE OR REPLACE TABLE other_published AS SELECT n FROM counts_only;",
    # The changed table on the JOIN side, not the FROM side.
    "j.sql": """
        CREATE OR REPLACE TABLE joined_published AS
        SELECT a.x FROM other_src a JOIN customer_demographics d ON a.k = d.cm13;
    """,
}


# ── the walk ───────────────────────────────────────────────────────────────
def test_a_whole_table_change_reaches_every_published_table_built_from_it(tmp_path):
    out = scan_whole(tmp_path, CHAIN)
    assert sorted(g["prod"] for g in out["groups"]) == \
        ["final_published", "joined_published", "other_published"]
    assert out["risk"] == "medium"
    assert out["stats"]["wholeTables"] == 1
    a = out["attributes"][0]
    assert a["whole"] is True and a["attr"] == WHOLE_TABLE
    assert a["readers"] == 3, "a.sql, c.sql and j.sql read the table directly"
    assert a["reachesProduction"] is True
    assert a["lookupFailed"] is False


def test_a_statement_that_names_no_column_is_still_a_reader(tmp_path):
    """COUNT(*) names no column, so no column walk could ever see c.sql."""
    out = scan_whole(tmp_path, CHAIN)
    rows = [r for g in out["groups"] for r in g["rows"]]
    row = next(r for r in rows if r["file"] == "c.sql")
    assert row["whole"] is True and row["attr"] == WHOLE_TABLE and row["alias"] == ""
    assert row["breaking"] is True and "fails outright" in row["impact"]
    assert row["mode"] == "Whole table"


def test_the_row_says_how_the_table_is_read(tmp_path):
    out = scan_whole(tmp_path, CHAIN)
    rows = {r["file"]: r for g in out["groups"] for r in g["rows"]}
    assert rows["a.sql"]["logic"] == "Reads this table"
    assert rows["j.sql"]["logic"] == "Joined to this table"
    assert "joins to customer_demographics" in rows["j.sql"]["impact"]
    # The marked line is the one that names the table, inside the statement.
    hit = next(ln for ln in rows["a.sql"]["lines"] if ln.get("hit"))
    assert "customer_demographics" in hit["t"]


def test_one_step_further_down_says_so(tmp_path):
    """The row in b.sql is about stage_cust, which is built from the table that
    changes. That is the same change one hop on, and the sentence has to say
    so or the row reads as a second, unrelated change."""
    out = scan_whole(tmp_path, CHAIN)
    rows = {r["file"]: r for g in out["groups"] for r in g["rows"]}
    assert rows["b.sql"]["from"] == "stage_cust"
    assert "one step further down" in rows["b.sql"]["impact"]


def test_a_value_change_to_a_whole_table_does_not_break_but_is_reported(tmp_path):
    out = scan_whole(tmp_path, CHAIN, change="value_change")
    rows = [r for g in out["groups"] for r in g["rows"]]
    assert rows and all(r["breaking"] is False for r in rows)
    assert out["risk"] == "low"
    assert "the data changes" in rows[0]["impact"]


def test_an_unspecified_change_is_treated_as_the_worse_case_and_says_so(tmp_path):
    out = scan_whole(tmp_path, CHAIN, change="unknown")
    rows = [r for g in out["groups"] for r in g["rows"]]
    assert all(r["breaking"] for r in rows)
    assert "did not say what changes" in rows[0]["impact"]


def test_a_table_ripple_never_met_is_not_called_safe(tmp_path):
    out = scan_whole(tmp_path, CHAIN, table="no_such_table")
    assert out["lookupFailed"] is True
    assert out["attributes"][0]["lookupFailed"] is True
    assert out["attributes"][0]["builtHere"] is False
    assert out["groups"] == [] and out["findings"] == [] if "findings" in out else True


def test_a_table_nothing_reads_is_an_answer_not_a_failed_lookup(tmp_path):
    files = {"a.sql": "CREATE TABLE lonely AS SELECT 1 AS x FROM src;"}
    out = scan_whole(tmp_path, files, table="lonely")
    assert out["lookupFailed"] is False
    assert out["attributes"][0]["builtHere"] is True
    assert out["attributes"][0]["found"] == 0


def test_the_hop_limit_is_reported_on_a_table_walk_too(tmp_path):
    files = {f"{i}.sql": f"CREATE TABLE t{i + 1} AS SELECT * FROM t{i};" for i in range(6)}
    out = scan_whole(tmp_path, files, table="t0", max_hops=2)
    assert out["cutShort"] and out["cutShort"][0]["attr"] == WHOLE_TABLE
    assert out["attributes"][0]["cutShortAt"]
    assert out["stats"]["trailsCutShort"] >= 1
    # And the last box on the picture says Ripple stopped, not that it ended.
    g = out["graphs"][0]
    assert any(b[-1].get("cut") for b in g["endBranches"])


def test_an_export_of_the_whole_table_is_named_as_a_delivery(tmp_path):
    files = {"e.sql": "EXPORT DATA OPTIONS(uri='gs://feed/partner/*.csv', format='CSV') AS\n"
                      "SELECT * FROM customer_demographics;"}
    out = scan_whole(tmp_path, files)
    assert out["feeds"] and out["feeds"][0]["attrs"] == [WHOLE_TABLE]
    assert out["feeds"][0]["breaking"] is True
    row = out["other"][0]
    assert row["logic"] == "Exported from this table"
    assert "delivered to gs://feed/partner" in row["impact"]
    assert "file stops arriving" in row["impact"]


def test_the_map_has_a_branch_per_published_table_with_no_alias(tmp_path):
    out = scan_whole(tmp_path, CHAIN)
    g = out["graphs"][0]
    assert g["whole"] is True and g["attr"] == WHOLE_TABLE
    assert sorted(b[-1]["name"] for b in g["branches"]) == \
        ["final_published", "joined_published", "other_published"]
    assert all(n["alias"] == "" and n.get("whole") for b in g["branches"] for n in b)


def test_a_column_scan_is_exactly_what_it_was(tmp_path):
    """The table walk sits beside the column walk and must not change it."""
    cfg, idx, parsed = build(tmp_path, CHAIN)
    out = trace(idx, parsed, [{"table": "customer_demographics", "attrs": ["cm13"]}],
                change_type="removal", cfg=cfg).to_dict()
    assert sorted(g["prod"] for g in out["groups"]) == ["final_published", "joined_published"]
    assert out["stats"]["wholeTables"] == 0
    assert all(not r["whole"] for g in out["groups"] for r in g["rows"])


def test_a_whole_table_and_a_column_can_be_asked_about_in_one_scan(tmp_path):
    cfg, idx, parsed = build(tmp_path, CHAIN)
    out = trace(idx, parsed, [{"table": "customer_demographics", "attrs": [], "whole": True},
                              {"table": "region_ref", "attrs": ["code"]}],
                change_type="removal", cfg=cfg).to_dict()
    assert [a["attr"] for a in out["attributes"]] == [WHOLE_TABLE, "code"]
    assert out["stats"]["wholeTables"] == 1


# ── the words ──────────────────────────────────────────────────────────────
VALS = {"upstream": [{"table": "customer_demographics", "attrs": [], "whole": True}],
        "effectiveLabel": "18 Sep 2026", "pocName": "Priya Raman",
        "subject": "CUSTOMER_DEMOGRAPHICS decommission"}


def test_the_summary_and_the_letter_say_the_whole_table_never_a_blank(tmp_path):
    out = scan_whole(tmp_path, CHAIN)
    s = narrative.summarise(out, VALS)
    r = narrative.draft_reply(out, VALS, s)
    assert "the whole of customer_demographics" in s["narrative"]
    assert "the whole of customer_demographics" in r["body"]
    assert "of  " not in r["body"], "the blank that used to be printed where the name goes"
    assert s["headline"].startswith("3 production tables at risk")
    assert not any("on whole table" in b for b in s["bullets"])
    assert not any("on whole table" in a for a in s["actions"])
    assert any(a.startswith("Change the statement that") for a in s["actions"])


def test_a_letter_about_a_table_never_met_asks_for_the_table_name(tmp_path):
    out = scan_whole(tmp_path, CHAIN, table="no_such_table")
    vals = {**VALS, "upstream": [{"table": "no_such_table", "attrs": [], "whole": True}]}
    s = narrative.summarise(out, vals)
    r = narrative.draft_reply(out, vals, s)
    assert s["headline"] == "no_such_table was not found - nothing has been checked"
    assert "table called no_such_table" in r["body"]
    assert "column called" not in r["body"]
    assert "check the table name" in r["subject"]


# ── the notice ─────────────────────────────────────────────────────────────
def _catalogue(tmp_path):
    _, _, parsed = build(tmp_path, CHAIN)
    return build_catalog(parsed)


@pytest.mark.parametrize("text", [
    "The table CUSTOMER_DEMOGRAPHICS will be decommissioned on 18 September 2026.",
    "We are dropping CUSTOMER_DEMOGRAPHICS on 18 September 2026.",
    "Decommission of CUSTOMER_DEMOGRAPHICS - effective 18 September 2026.",
    "customer_demographics is being retired. All downstream consumers must move.",
    "The whole table is going: CUSTOMER_DEMOGRAPHICS will not be refreshed after 18 Sep.",
])
def test_a_notice_about_the_table_itself_is_read_as_a_whole_table_change(tmp_path, text):
    cat = _catalogue(tmp_path)
    n = notification.read_pasted(f"Hi team,\n\n{text}\n\nRegards,\nPriya Raman\nC360 Data Governance")
    out = notification.extract_by_rules(n, cat)
    up = {u["table"].lower(): u for u in out["upstream"]}
    assert up["customer_demographics"]["whole"] is True
    assert up["customer_demographics"]["attrs"] == []
    assert any("whole-table change" in w for w in out["warnings"])


def test_a_named_attribute_wins_even_when_the_notice_says_table(tmp_path):
    cat = _catalogue(tmp_path)
    n = notification.read_pasted(
        "The column MARKET_CODE on table CUSTOMER_DEMOGRAPHICS will be dropped on 18 September 2026.")
    out = notification.extract_by_rules(n, cat)
    up = {u["table"].lower(): u for u in out["upstream"]}
    assert up["customer_demographics"]["attrs"] == ["MARKET_CODE"]
    assert up["customer_demographics"]["whole"] is False
    assert out["changeKind"] == "removal" and out["changeType"] == "Decommission"


def test_a_notice_with_no_attribute_and_no_table_words_asks_rather_than_guesses(tmp_path):
    cat = _catalogue(tmp_path)
    n = notification.read_pasted("FYI the CUSTOMER_DEMOGRAPHICS refresh timing changes next month.")
    out = notification.extract_by_rules(n, cat)
    up = {u["table"].lower(): u for u in out["upstream"]}
    assert up["customer_demographics"]["whole"] is False
    assert up["customer_demographics"]["attrs"] == []
    assert any("tick 'Whole table'" in w for w in out["warnings"])


def test_the_change_labels_no_longer_say_attribute_over_a_table_change():
    assert notification.classify_change("the table will be dropped") == ("removal", "Decommission")
    assert notification.classify_change("the table is renamed") == ("rename", "Rename")


# ── the route, in the build this file belongs to ───────────────────────────
@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from ripple.api import app
    return TestClient(app)


def test_the_route_refuses_a_table_with_no_attribute_that_is_not_marked_whole(client):
    r = client.post("/api/scan", json={"upstream": [{"table": "CUSTOMER_DEMOGRAPHICS", "attrs": []}],
                                       "changeKind": "removal"})
    assert r.status_code == 400
    assert "Whole table" in r.json()["detail"]


def test_the_route_scans_the_whole_table_when_asked(client):
    r = client.post("/api/scan", json={"upstream": [{"table": "CUSTOMER_DEMOGRAPHICS", "attrs": [],
                                                     "whole": True}],
                                       "changeKind": "removal"})
    assert r.status_code == 200
    sc = r.json()
    assert sc["stats"]["wholeTables"] == 1
    assert sc["groups"], "the practice pipeline builds published tables from it"
    assert sc["risk"] == "medium"
    assert sc["attributes"][0]["readers"] >= 1
    # A column scan of the same table reaches no MORE than the whole table does.
    col = client.post("/api/scan", json={"upstream": [{"table": "CUSTOMER_DEMOGRAPHICS",
                                                       "attrs": ["MARKET_CODE"]}],
                                         "changeKind": "removal"}).json()
    assert {g["prod"] for g in col["groups"]} <= {g["prod"] for g in sc["groups"]}
