"""Tests for the parts that would fail quietly.

The point of most of these is not that Ripple finds things -- it is that when
Ripple cannot find something, it says so.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ripple import narrative                                    # noqa: E402
from ripple.api import app                                      # noqa: E402
from ripple.catalog import build_catalog                        # noqa: E402
from ripple.config import settings                              # noqa: E402
from ripple.notification import (                               # noqa: E402
    classify_change, extract_by_rules, parse_date, read_upload, strip_html,
)
from ripple.scanner.lineage import trace                        # noqa: E402
from ripple.scanner.repo import RepoIndex, written_tables       # noqa: E402
from ripple.scanner.sqlread import output_name, parse_repo, usages_of  # noqa: E402

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


@pytest.fixture(scope="module")
def repo():
    idx = RepoIndex.build(settings.repo_path, settings)
    parsed = parse_repo(idx, settings)
    return idx, parsed, build_catalog(parsed)


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def scan(repo, table, attrs, kind):
    idx, parsed, _ = repo
    return trace(idx, parsed, [{"table": table, "attrs": attrs}], change_type=kind, cfg=settings)


# ── indexing and search ────────────────────────────────────────────────────
def test_index_finds_code_files(repo):
    idx, _, _ = repo
    assert len(idx.files) > 15
    assert any(f.path.endswith(".spark.py") for f in idx.files)


def test_search_is_whole_word_only(repo):
    idx, _, _ = repo
    hits = idx.search(["market_code"])
    assert hits
    # MARKET_CODE must not match inside MARKET_CODE_V2-style longer names
    assert all("market_code" in h.line.lower() for h in hits)


def test_search_is_case_insensitive(repo):
    idx, _, _ = repo
    assert idx.search(["MARKET_CODE"]) and idx.search(["market_code"])


# ── reading SQL ────────────────────────────────────────────────────────────
def test_unparseable_files_are_reported_not_swallowed(repo):
    _, parsed, _ = repo
    bad = {u["file"] for u in parsed.unreadable}
    assert "etl/broken_syntax.sql" in bad


def test_spark_write_target_is_inferred(repo):
    idx, _, _ = repo
    f = idx.get("etl/marketing_base.spark.py")
    assert written_tables(f) == ["marketing_base"]


def test_alias_is_resolved_through_a_subquery(repo):
    """last_upd is renamed to lut_ts inside a ranking subquery. If this stops
    working the trail goes cold at exactly the statement that matters most."""
    _, parsed, _ = repo
    stmt = next(s for s in parsed.statements if s.file == "etl/global_tagging_main.sql")
    assert output_name(stmt, "last_upd") == "lut_ts"


def test_usage_kinds_are_classified(repo):
    _, parsed, _ = repo
    marketing = next(s for s in parsed.statements if s.file == "etl/marketing_base.spark.py")
    kinds = {u.kind for u in usages_of(marketing, "mc")}
    assert "filter" in kinds
    ranking = next(s for s in parsed.statements if s.file == "etl/global_tagging_main.sql")
    assert "ranking" in {u.kind for u in usages_of(ranking, "last_upd")}


def test_filter_literal_is_captured(repo):
    _, parsed, _ = repo
    stmt = next(s for s in parsed.statements if s.file == "etl/marketing_base.spark.py")
    filt = next(u for u in usages_of(stmt, "mc") if u.kind == "filter")
    assert filt.detail == "US"


# ── lineage ────────────────────────────────────────────────────────────────
def test_two_hop_rename_reaches_production(repo):
    res = scan(repo, "customer_demographics", ["market_code"], "value_change")
    chains = [
        [n["name"] for n in b]
        for g in res.graphs for b in g["branches"]
    ]
    assert ["customer_profile_odl", "marketing_base", "final_targeting_prod"] in chains


def test_aliases_are_shown_at_each_hop(repo):
    res = scan(repo, "customer_demographics", ["market_code"], "value_change")
    branch = next(b for g in res.graphs for b in g["branches"]
                  if [n["name"] for n in b][-1] == "final_targeting_prod")
    assert [n["alias"] for n in branch] == ["mc", "mkt_cd", "mkt_cd"]


def test_ranking_removal_is_high_risk_with_no_local_fix(repo):
    res = scan(repo, "customer_demographics", ["last_update_timestamp"], "removal")
    assert res.risk == "high"
    rows = [r for g in res.groups for r in g["rows"]]
    assert any(r["noLocalFix"] for r in rows)


def test_value_change_does_not_break_a_plain_select(repo):
    res = scan(repo, "customer_demographics", ["market_name"], "value_change")
    rows = [r for g in res.groups for r in g["rows"]]
    agg = [r for r in rows if r["logic"] == "Aggregation"]
    assert agg and not agg[0]["breaking"]


def test_unused_attribute_reports_no_impact(repo):
    res = scan(repo, "prospect_master", ["legacy_segment_code"], "removal")
    assert res.groups == [] and res.graphs == [] and res.risk == "none"


def test_no_impact_still_lists_where_the_name_appeared(repo):
    res = scan(repo, "prospect_master", ["legacy_segment_code"], "removal")
    assert res.mentions_only, "a clean result must still show where the name was seen"


def test_dynamic_sql_is_flagged_as_unreadable(repo):
    """The file mentions the column but builds its SQL by gluing strings. It must
    surface as a gap, not vanish into a confident clean result."""
    res = scan(repo, "customer_demographics", ["market_code"], "value_change")
    assert any("legacy_dynamic_build" in (u.get("file") or "") for u in res.unreadable)


def test_unknown_table_is_not_a_crash(repo):
    res = scan(repo, "table_that_does_not_exist", ["nope"], "removal")
    assert res.risk == "none" and res.groups == []


# ── catalogue ──────────────────────────────────────────────────────────────
def test_catalog_reads_column_definitions(repo):
    _, _, cat = repo
    assert cat.has_table("customer_demographics")
    assert cat.has_column("customer_demographics", "market_code")


def test_select_star_over_a_listed_table_is_filled_in_not_a_gap(repo):
    """vw_everything is SELECT * FROM customer_demographics, and the DDL lists
    every column of customer_demographics. So the view's column list is known,
    read from that DDL -- it used to be reported as a gap, which read as Ripple
    having failed to read a file."""
    _, _, cat = repo
    assert not any("vw_everything" in g["table"] for g in cat.gaps)
    assert cat.columns("vw_everything") == cat.columns("customer_demographics")
    assert cat.derived["VW_EVERYTHING"]["listedIn"] == ["ddl/customer_demographics.sql"]
    assert cat.listed_in("vw_everything") == "ddl/customer_demographics.sql"


# ── the notification ───────────────────────────────────────────────────────
def test_eml_is_read(repo):
    raw = (SAMPLES / "01-market-code-value-change.eml").read_bytes()
    n = read_upload("01.eml", raw)
    assert n.from_name == "Priya Raman"
    assert "MARKET_CODE" in n.text()


def test_html_only_body_becomes_text():
    n = read_upload("x.eml", (SAMPLES / "04-html-table-forwarded.eml").read_bytes())
    assert "CUSTOMER_ADDRESS" in n.body and "<td>" not in n.body


def test_dates_are_understood_in_several_shapes():
    assert parse_date("effective 2026-09-18") == "2026-09-18"
    assert parse_date("effective September 18, 2026") == "2026-09-18"
    assert parse_date("effective 18 September 2026") == "2026-09-18"
    assert parse_date("no date here") == ""


def test_change_type_is_guessed_from_wording():
    assert classify_change("will be decommissioned")[0] == "removal"
    assert classify_change("value format change")[0] == "value_change"


def test_columns_only_match_once_their_table_has(repo):
    """Without this rule, generic words produce a page of false hits."""
    _, _, cat = repo
    from ripple.notification import Notification
    n = Notification(body="STATUS and AMOUNT and MARKET_CODE are changing")
    out = extract_by_rules(n, cat)
    assert out["upstream"] == []  # no table named, so no columns are claimed


def test_unrecognised_names_are_warned_about(repo):
    _, _, cat = repo
    from ripple.notification import Notification
    n = Notification(body="SOME_UNKNOWN_TABLE.SOME_COL is changing")
    out = extract_by_rules(n, cat)
    assert any("not in the connected repository" in w for w in out["warnings"])


def test_strip_html_keeps_table_cells_apart():
    assert "A\tB" in strip_html("<tr><td>A</td><td>B</td></tr>")


# ── writing it up without AI ───────────────────────────────────────────────
def test_summary_works_with_no_ai(repo):
    res = scan(repo, "customer_demographics", ["market_code"], "value_change")
    s = narrative.summarise(res.to_dict(), {"upstream": [{"table": "CUSTOMER_DEMOGRAPHICS",
                                                         "attrs": ["MARKET_CODE"]}]})
    assert s["headline"] and s["bullets"] and s["actions"]
    assert s["writtenBy"] == "rules"


def test_actions_are_not_repeated(repo):
    res = scan(repo, "customer_demographics", ["market_code"], "value_change")
    s = narrative.summarise(res.to_dict(), {"upstream": []})
    assert len(s["actions"]) == len(set(s["actions"]))


def test_summary_mentions_what_could_not_be_read(repo):
    res = scan(repo, "customer_demographics", ["market_code"], "value_change")
    s = narrative.summarise(res.to_dict(), {"upstream": []})
    assert any("checked by hand" in b for b in s["bullets"])


def test_reply_asks_upstream_when_there_is_no_local_fix(repo):
    res = scan(repo, "customer_demographics", ["last_update_timestamp"], "removal")
    d = res.to_dict()
    s = narrative.summarise(d, {"upstream": []})
    r = narrative.draft_reply(d, {"pocName": "Marcus Hale", "upstream": []}, s)
    assert "replacement" in r["body"].lower()


# ── the API ────────────────────────────────────────────────────────────────
def test_health_reports_the_repo(client):
    h = client.get("/api/health").json()
    assert h["ok"] and h["repo"]["files"] > 0


def test_scan_endpoint(client):
    r = client.post("/api/scan", json={
        "upstream": [{"table": "customer_demographics", "attrs": ["market_code"]}],
        "changeKind": "value_change"}).json()
    assert r["groups"] and r["stats"]["productionTables"] >= 1


def test_scan_with_no_tables_is_rejected(client):
    assert client.post("/api/scan", json={"upstream": [], "changeKind": "removal"}).status_code == 400


def test_summary_endpoint_without_ai(client):
    sc = client.post("/api/scan", json={
        "upstream": [{"table": "customer_demographics", "attrs": ["market_code"]}],
        "changeKind": "value_change"}).json()
    out = client.post("/api/summary", json={"scan": sc, "vals": {"upstream": []},
                                            "useAI": False}).json()
    assert out["summary"]["headline"] and out["reply"]["body"]


def test_upload_endpoint_reads_an_eml(client):
    raw = (SAMPLES / "02-timestamp-decommission.eml").read_bytes()
    out = client.post("/api/read-email?useAI=false",
                      files={"file": ("02.eml", raw, "message/rfc822")}).json()
    assert out["changeKind"] == "removal"
    assert out["upstream"][0]["table"].upper() == "CUSTOMER_DEMOGRAPHICS"


def test_garbage_upload_does_not_crash(client):
    out = client.post("/api/read-email?useAI=false",
                      files={"file": ("x.msg", b"\x00\x01not really a msg", "application/octet-stream")}).json()
    assert out["warnings"]


def test_file_endpoint_returns_real_lines(client):
    out = client.get("/api/file", params={"path": "odl/customer_profile_odl.sql"}).json()
    assert any("market_code" in ln.lower() for ln in out["lines"])


def test_file_endpoint_rejects_unknown_path(client):
    assert client.get("/api/file", params={"path": "../../secrets.txt"}).status_code == 404


# ── where the repository happens to live ───────────────────────────────────
def test_a_repository_under_a_folder_called_build_is_still_read(tmp_path):
    """The skipped-folder names apply inside the repository, not to the whole
    path. Matched against the whole path, a repository that merely sits under a
    folder called build, dist, target or venv has every file skipped -- and the
    scan comes back clean because it read nothing at all."""
    root = tmp_path / "build" / "our-pipelines"
    (root / "etl").mkdir(parents=True)
    (root / "etl" / "load.sql").write_text("CREATE TABLE A_PROD AS SELECT 1 AS X;", encoding="utf-8")
    idx = RepoIndex.build(root, settings)
    assert [f.path for f in idx.files] == ["etl/load.sql"]


def test_skipped_folders_inside_the_repository_are_still_skipped(tmp_path):
    root = tmp_path / "repo"
    (root / "node_modules").mkdir(parents=True)
    (root / "src").mkdir(parents=True)
    (root / "node_modules" / "junk.sql").write_text("SELECT 1;", encoding="utf-8")
    (root / "src" / "real.sql").write_text("SELECT 1;", encoding="utf-8")
    idx = RepoIndex.build(root, settings)
    assert [f.path for f in idx.files] == ["src/real.sql"]
