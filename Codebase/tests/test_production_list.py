"""Pasting the real list of published tables, instead of guessing at a pattern.

The published-table list decides whether "no production table is impacted" is a
result or an accident, so these tests are about two things only: that a list
survives however it was copied, and that Ripple says out loud what it did with
it -- including which of the pasted tables it has never seen.

Every table name below is invented.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ripple import production                                  # noqa: E402
from ripple.config import Settings, parse_production_rule      # noqa: E402
from ripple.scanner.repo import RepoIndex                      # noqa: E402
from ripple.scanner.sqlread import parse_repo                  # noqa: E402


def names(text: str) -> list[str]:
    return [e.given for e in production.parse(text).names]


def patterns(text: str) -> list[str]:
    return [e.given for e in production.parse(text).patterns]


# ── however the list arrives ───────────────────────────────────────────────
THREE = ["sales_daily", "cust_profile", "order_lines"]


@pytest.mark.parametrize("label,text", [
    ("one per line", "sales_daily\ncust_profile\norder_lines\n"),
    ("commas, one line", "sales_daily, cust_profile, order_lines"),
    ("commas across lines", "sales_daily, cust_profile,\norder_lines\n"),
    ("semicolons", "sales_daily; cust_profile; order_lines"),
    ("blank lines and spaces", "\n  sales_daily  \n\n\tcust_profile\n\n  order_lines\n\n"),
    ("slack bullets", "• sales_daily\n- cust_profile\n* order_lines"),
    ("numbered", "1. sales_daily\n2) cust_profile\n3. order_lines"),
    ("backticks", "`sales_daily`\n`cust_profile`\n`order_lines`"),
    ("code fence", "```\nsales_daily\ncust_profile\norder_lines\n```"),
    ("quoted and trailing commas", "'sales_daily',\n\"cust_profile\",\nsales_daily.\norder_lines;"),
    ("space separated on one line", "sales_daily cust_profile order_lines"),
])
def test_a_list_survives_however_it_was_copied(label, text):
    assert names(text) == THREE, label


def test_a_column_pasted_out_of_excel_keeps_its_heading_out_of_the_list():
    rule = production.parse("Table name\nsales_daily\ncust_profile\n")
    assert [e.given for e in rule.names] == ["sales_daily", "cust_profile"]
    assert any(n["kind"] == "heading" for n in rule.notes)


def test_several_columns_out_of_excel_pick_the_one_with_the_tables_in_it():
    rule = production.parse(
        "Owner\tTable name\tRefreshed\n"
        "Priya\tsales_daily\t2026-01-04\n"
        "Marcus\tcust_profile\t2026-01-05\n")
    assert [e.given for e in rule.names] == ["sales_daily", "cust_profile"]
    # And it has to say which column it took, or a grid read down the wrong
    # column is a total misread with nothing on screen to show for it.
    assert rule.column["heading"] == "Table name"
    assert any("Table name" in n["text"] for n in rule.notes)


def test_several_columns_with_no_heading_still_pick_the_table_column():
    rule = production.parse("Priya\tsales_daily\ndeepa\tcust_profile\n")
    assert [e.given for e in rule.names] == ["sales_daily", "cust_profile"]
    assert rule.column["by"] == "content"


def test_a_markdown_table_from_confluence_reads_as_a_list():
    rule = production.parse(
        "| Table name | Owner |\n|---|---|\n| sales_daily | Priya |\n| cust_profile | Marcus |\n")
    assert [e.given for e in rule.names] == ["sales_daily", "cust_profile"]


def test_qualified_bare_and_two_part_names_can_be_mixed_in_one_paste():
    rule = production.parse(
        "prj-p-demo.foundation.sales_daily\nfoundation.cust_profile\norder_lines\n")
    assert len(rule.names) == 3
    # Kept as pasted for showing back, matched on the part SQL actually says.
    assert [e.key for e in rule.names] == ["SALES_DAILY", "CUST_PROFILE", "ORDER_LINES"]


def test_duplicates_and_capitalisation_are_reduced_and_reported():
    rule = production.parse("SALES_DAILY\nsales_daily\n  Sales_Daily\ncust_profile\n")
    assert [e.given for e in rule.names] == ["SALES_DAILY", "cust_profile"]
    note = next(n for n in rule.notes if n["kind"] == "duplicate")
    assert note["count"] == 2


def test_two_names_ripple_cannot_tell_apart_are_said_rather_than_counted_as_duplicates():
    """SQL only ever says the last part of a name, so dev.x and prod.x are one
    table here. Quietly dropping one would be a lie by arithmetic."""
    rule = production.parse("dev.sales_daily\nprod.sales_daily\n")
    assert len(rule.names) == 1
    note = next(n for n in rule.notes if n["kind"] == "sameTable")
    assert "dev.sales_daily and prod.sales_daily" in note["examples"][0]


def test_a_line_that_is_not_a_table_name_is_reported_never_dropped_silently():
    rule = production.parse("Here are the tables:\nsales_daily\nplease confirm by friday\n")
    assert [e.given for e in rule.names] == ["sales_daily"]
    note = next(n for n in rule.notes if n["kind"] == "rejected")
    assert note["count"] == 2
    assert "Here are the tables:" in note["examples"]


def test_prose_is_never_split_into_invented_table_names():
    """Four English words that all look like names would become four published
    tables Ripple then never finds -- the worst kind of quiet mistake."""
    assert names("please confirm by friday") == []


# ── the patterns that were there before, unchanged ─────────────────────────
@pytest.mark.parametrize("rule,table,expected", [
    ("_PROD", "sales_prod", True),
    ("_PROD", "sales_umdl", False),
    ("_UMDL, _GDI", "card_pub_guid_umdl", True),
    ("PROD_*", "prod_sales", True),
    ("PROD_*", "sales_prod", False),
    ("*", "anything_at_all", True),
])
def test_a_pattern_still_does_exactly_what_it_did_before(rule, table, expected):
    cfg = Settings()
    cfg.set_production(rule)
    assert cfg.is_production_table(table) is expected


def test_an_exact_name_matches_only_that_table():
    cfg = Settings()
    cfg.set_production("sales_daily\ncust_profile")
    assert cfg.is_production_table("SALES_DAILY") is True
    assert cfg.is_production_table("sales_daily") is True
    assert cfg.is_production_table("stg_sales_daily") is False
    assert cfg.is_production_table("sales_daily_v2") is False


def test_a_pasted_name_matches_whether_or_not_the_sql_qualifies_it():
    cfg = Settings()
    cfg.set_production("prj-p-demo.foundation.sales_daily")
    assert cfg.is_production_table("sales_daily") is True


def test_names_and_patterns_work_side_by_side():
    cfg = Settings()
    cfg.set_production("sales_daily\n_UMDL\nPROD_*")
    assert cfg.is_production_table("sales_daily") is True
    assert cfg.is_production_table("card_guid_umdl") is True
    assert cfg.is_production_table("prod_sales") is True
    assert cfg.is_production_table("something_else") is False
    rule = cfg.production()
    assert len(rule.names) == 1 and len(rule.patterns) == 2


def test_an_empty_box_means_not_given_and_nothing_is_scanned():
    """An empty list used to fall back to what Ripple shipped with. On a
    warehouse that names its published tables anything else, that default
    matched NOTHING -- and matching nothing did not read as "I do not know which
    tables are yours". It read as "no production table is affected", in green,
    over a change that broke all of them.

    Empty now means NOT GIVEN, which is a different thing from "nothing is
    published", and every entry point refuses to scan until it has been."""
    cfg = Settings()
    cfg.set_production("   \n  \n")
    assert cfg.production_patterns == ()
    assert cfg.production_text == ""
    assert cfg.has_production() is False
    # And the older helper still answers the way its callers expect.
    assert parse_production_rule("  ,  , ") == ()


def test_the_one_line_form_counts_a_long_list_rather_than_printing_it():
    cfg = Settings()
    cfg.set_production("\n".join(f"table_{n}" for n in range(120)) + "\n_PROD")
    line = cfg.production_rule()
    assert "120 table names" in line and "_PROD" in line
    assert len(line) < 90


# ── the important one: which of these tables is not in the repository ──────
REPO = {
    "sql/sales.sql": """
        CREATE TABLE sales_daily AS
        SELECT order_id, market_code FROM orders_raw;
    """,
    "sql/profile.sql": """
        CREATE TABLE cust_profile AS
        SELECT cm_id, market_code FROM sales_daily;
    """,
    "notes/readme.md": "order_lines is built by the other team\n",
    "jobs/loader.py": "TARGET = 'order_lines'\n",
}


def _repo(tmp_path: Path):
    for rel, text in REPO.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    cfg = Settings()
    cfg.sql_dialect = "bigquery"
    idx = RepoIndex.build(tmp_path, cfg)
    return idx, parse_repo(idx, cfg)


def test_a_pasted_table_ripple_has_never_seen_is_named(tmp_path):
    idx, parsed = _repo(tmp_path)
    rule = production.parse("sales_daily\ncust_profile\nnowhere_at_all\n")
    check = production.check_against_repo(rule, idx, parsed)
    assert check["foundCount"] == 2
    missing = {m["given"]: m for m in check["missing"]}
    assert set(missing) == {"nowhere_at_all"}
    assert missing["nowhere_at_all"]["state"] == "nowhere"


def test_a_name_written_in_the_repository_but_never_built_is_told_apart(tmp_path):
    """"The name is nowhere" and "something builds it out of reach" send a
    person to two completely different places."""
    idx, parsed = _repo(tmp_path)
    rule = production.parse("order_lines")
    check = production.check_against_repo(rule, idx, parsed)
    found = check["missing"][0]
    assert found["state"] == "written"
    assert found["files"] == 1        # only the .py is indexed; .md is not read


def test_a_name_that_was_meant_as_a_pattern_is_asked_about_not_guessed(tmp_path):
    idx, parsed = _repo(tmp_path)
    rule = production.parse("daily")
    check = production.check_against_repo(rule, idx, parsed)
    only = check["missing"][0]
    assert only["state"] in ("nowhere", "written")
    assert only["endsWith"] == 1, "sales_daily ends with it, so say so"


def test_a_pattern_that_matches_nothing_here_is_reported(tmp_path):
    idx, parsed = _repo(tmp_path)
    rule = production.parse("_PROD, _daily")
    check = production.check_against_repo(rule, idx, parsed)
    by = {p["given"]: p for p in check["patterns"]}
    assert by["_PROD"]["matches"] == 0
    assert by["_daily"]["matches"] == 1
    assert by["_daily"]["examples"] == ["SALES_DAILY"]


def test_the_check_says_when_there_is_no_repository_to_check_against():
    rule = production.parse("sales_daily")
    check = production.check_against_repo(rule, RepoIndex(), parse_repo(RepoIndex(), Settings()))
    assert check["checked"] is False


# ── the environment variable ───────────────────────────────────────────────
def test_the_environment_variable_takes_a_whole_pasted_list(monkeypatch):
    monkeypatch.setenv("RIPPLE_PROD_TABLES", "sales_daily\ncust_profile\n_PROD")
    cfg = Settings()
    assert cfg.is_production_table("sales_daily") is True
    assert cfg.is_production_table("cust_profile") is True
    assert cfg.is_production_table("anything_prod") is True
    assert cfg.is_production_table("orders_raw") is False
    # And what was set is kept exactly, so the box can show it back for editing.
    assert cfg.production_text == "sales_daily\ncust_profile\n_PROD"


def test_the_list_a_person_pasted_is_kept_exactly_as_they_pasted_it():
    cfg = Settings()
    pasted = "Table name\n• sales_daily\n• cust_profile\n"
    cfg.set_production(pasted)
    assert cfg.production_text == pasted, "handing back a tidied version loses their list"
    assert cfg.production().names[0].given == "sales_daily"


# ── the shapes that failed in the field ────────────────────────────────────
# Users reported the list finding about three tables in four. Measured on
# 2 Sep 2026 against twenty realistic pairs of "what the SQL writes" and "what
# a person pastes": thirteen found, seven missed. Every miss is pinned below,
# and the twenty are run together at the end so the count cannot slip back.


@pytest.mark.parametrize("pasted,expect,how", [
    ("prj-p-demo:mart.dim_store", "DIM_STORE", "colon"),
    ("mart.dim_channel (partitioned by day)", "DIM_CHANNEL", "bracket"),
    ("mart.dim_channel [view]", "DIM_CHANNEL", "bracket"),
    ("mart.dim_region - region lookup", "DIM_REGION", "tail"),
    ("mart.dim_region — region lookup", "DIM_REGION", "tail"),
    ("mart.dim_region: the region lookup", "DIM_REGION", "tail"),
])
def test_a_name_with_something_after_it_is_still_read_and_the_rewrite_is_said(pasted, expect, how):
    rule = production.parse(pasted)
    assert [e.key for e in rule.names] == [expect], pasted
    note = next(n for n in rule.notes if n["kind"] == "tidied" and n["how"] == how)
    assert note["count"] == 1
    assert note["examples"], "the kept name is shown back, so the rewrite can be checked"


def test_an_invisible_character_pasted_out_of_confluence_does_not_hide_a_table():
    rule = production.parse("mart.dim_product​\nsales_daily \n")
    assert [e.key for e in rule.names] == ["DIM_PRODUCT", "SALES_DAILY"]
    note = next(n for n in rule.notes if n["kind"] == "tidied" and n["how"] == "invisible")
    assert note["count"] == 2


def test_prose_after_a_plain_word_is_still_not_a_table():
    """The tidy-up only ever keeps a name that could not be a word. "sales - the
    daily sales" is a sentence, and reading a table out of it would invent one."""
    assert names("sales - the daily sales") == []
    assert names("please: confirm by friday") == []


def test_a_wildcard_pasted_with_its_dataset_matches_the_bare_shard():
    """Keyed whole, mart.snap_daily_* matched nothing: no table name the SQL
    says has a dot in it, so the glob compared a dotted pattern to bare names
    for ever and came back empty -- on the check screen and on every scan."""
    cfg = Settings()
    cfg.set_production("mart.snap_daily_*")
    assert cfg.is_production_table("snap_daily_20260101") is True
    assert cfg.is_production_table("mart.snap_daily_20260101") is True
    assert cfg.is_production_table("other_20260101") is False
    # A wildcard in the dataset itself is left alone: it can only ever be
    # compared whole, and it was never matched before either.
    rule = production.parse("prod_*.sales")
    assert rule.patterns[0].key == "PROD_*.SALES"


def test_a_date_sharded_table_matches_the_family_name_on_the_list_and_says_how():
    cfg = Settings()
    cfg.set_production("mart.order_lines")
    rule = cfg.production()
    assert rule.match_how("order_lines_20260101") == "shard"
    assert rule.match_how("mart.order_lines_2026_01_01") == "shard"
    # A partition decorator names one day of the SAME table, so that is the
    # table itself, matched by name.
    assert rule.match_how("order_lines$20260101") == "name"
    assert rule.match_how("order_lines") == "name"
    # Loose only in the one direction that is safe. A version, a backup or a
    # suffix that is not a date is a different table, exactly as before.
    assert rule.match_how("order_lines_v2") == ""
    assert rule.match_how("order_lines_backup") == ""
    assert rule.match_how("stg_order_lines") == ""


def test_a_placeholder_glued_to_the_name_matches_the_family_and_says_how():
    """CREATE TABLE mart.fact_returns_${RUN_DATE} reaches the parser as
    fact_returns_RUN_DATE. The list says fact_returns, and that is the table."""
    cfg = Settings()
    cfg.set_production("fact_returns")
    rule = cfg.production()
    assert rule.match_how("fact_returns_RUN_DATE") == "placeholder"
    assert rule.match_how("fact_returns_ds_nodash") == "placeholder"
    assert rule.match_how("fact_returns_ds") == "placeholder"
    assert rule.match_how("fact_returns_summary") == ""


def test_the_check_reports_a_family_match_instead_of_calling_the_table_missing(tmp_path):
    files = {
        "a.sql": "CREATE TABLE mart.order_lines_20260101 AS SELECT 1 AS a FROM src.orders;",
        "b.sql": "CREATE TABLE mart.order_lines_20260102 AS SELECT 1 AS a FROM src.orders;",
        "c.sql": "CREATE TABLE mart.fact_returns_${RUN_DATE} AS SELECT 1 AS a FROM src.orders;",
    }
    for rel, text in files.items():
        (tmp_path / rel).write_text(text, encoding="utf-8")
    cfg = Settings()
    cfg.sql_dialect = "bigquery"
    idx = RepoIndex.build(tmp_path, cfg)
    parsed = parse_repo(idx, cfg)
    rule = production.parse("mart.order_lines\nmart.fact_returns\nmart.nowhere_at_all\n")
    check = production.check_against_repo(rule, idx, parsed)
    by = {f["given"]: f for f in check["found"]}
    assert by["mart.order_lines"]["how"] == "shard"
    assert by["mart.order_lines"]["as"] == ["ORDER_LINES_20260101", "ORDER_LINES_20260102"]
    assert by["mart.fact_returns"]["how"] == "placeholder"
    assert check["familyCount"] == 2, "the screen says how many were found as a family"
    assert [m["given"] for m in check["missing"]] == ["mart.nowhere_at_all"]


# The twenty pairs measured on 2 Sep 2026. Every one is what a BigQuery shop
# really writes and what a person really pastes.
FIELD_SHAPES = [
    ("CREATE OR REPLACE TABLE `prj-p-demo.mart.sales_daily` AS SELECT 1 AS a FROM src.orders;",
     "prj-p-demo.mart.sales_daily", "SALES_DAILY"),
    ("CREATE TABLE mart.cust_profile AS SELECT 1 AS a FROM src.orders;", "cust_profile", "CUST_PROFILE"),
    ("CREATE TABLE mart.order_lines_20260101 AS SELECT 1 AS a FROM src.orders;", "mart.order_lines", "ORDER_LINES_20260101"),
    ("INSERT INTO mart.events$20260101 SELECT 1 AS a FROM src.orders;", "mart.events", "EVENTS"),
    ("CREATE TABLE ${PROJECT}.${DATASET}.fact_orders AS SELECT 1 AS a FROM src.orders;",
     "prj-p-demo.mart.fact_orders", "FACT_ORDERS"),
    ("CREATE TABLE mart.fact_returns_${RUN_DATE} AS SELECT 1 AS a FROM src.orders;", "mart.fact_returns", "FACT_RETURNS_RUN_DATE"),
    ("CREATE TABLE mart.dim_store AS SELECT 1 AS a FROM src.orders;", "prj-p-demo:mart.dim_store", "DIM_STORE"),
    ("CREATE TABLE mart.dim_product AS SELECT 1 AS a FROM src.orders;", "mart.dim_product​", "DIM_PRODUCT"),
    ("CREATE TABLE mart.dim_channel AS SELECT 1 AS a FROM src.orders;", "mart.dim_channel (partitioned by day)", "DIM_CHANNEL"),
    ("CREATE TABLE mart.dim_region AS SELECT 1 AS a FROM src.orders;", "mart.dim_region - region lookup", "DIM_REGION"),
    ("CREATE TABLE mart.agg_weekly AS SELECT 1 AS a FROM src.orders;", "MART.AGG_WEEKLY", "AGG_WEEKLY"),
    ("CREATE TABLE mart.agg_monthly AS SELECT 1 AS a FROM src.orders;", "`mart.agg_monthly`", "AGG_MONTHLY"),
    ("CREATE VIEW mart.vw_summary AS SELECT 1 AS a FROM src.orders;", "mart.vw_summary", "VW_SUMMARY"),
    ("CREATE MATERIALIZED VIEW mart.mv_summary AS SELECT 1 AS a FROM src.orders;", "mart.mv_summary", "MV_SUMMARY"),
    ("CREATE TABLE mart.snap_daily_20260101 AS SELECT 1 AS a FROM src.orders;", "mart.snap_daily_*", "SNAP_DAILY_20260101"),
    ("CREATE TABLE IF NOT EXISTS mart.ref_codes (code STRING, label STRING);", "mart.ref_codes", "REF_CODES"),
    ("MERGE INTO mart.cust_master t USING src.orders s ON t.a = s.a WHEN MATCHED THEN UPDATE SET a = s.a;",
     "mart.cust_master", "CUST_MASTER"),
    ("CREATE TABLE `prj-p-demo`.`mart`.`dim_geo` AS SELECT 1 AS a FROM src.orders;", "prj-p-demo.mart.dim_geo", "DIM_GEO"),
    ("EXECUTE IMMEDIATE 'CREATE TABLE mart.dyn_table AS SELECT 1 AS a FROM src.orders';", "mart.dyn_table", "DYN_TABLE"),
    ("CREATE TABLE mart.dim_date AS SELECT 1 AS a FROM src.orders;", "dim_date\t2026-01-04\tPriya", "DIM_DATE"),
]


def test_every_one_of_the_twenty_field_shapes_is_found(tmp_path):
    """Thirteen of these twenty were found before. All twenty are found now, and
    the number is asserted so it cannot slip back one shape at a time."""
    for i, (sql, _, _) in enumerate(FIELD_SHAPES):
        (tmp_path / f"file_{i:02}.sql").write_text(sql + "\n", encoding="utf-8")
    cfg = Settings()
    cfg.sql_dialect = "bigquery"
    idx = RepoIndex.build(tmp_path, cfg)
    parsed = parse_repo(idx, cfg)
    rule = production.parse("\n".join(p for _, p, _ in FIELD_SHAPES))
    matched = {s.target.rsplit(".", 1)[-1].upper()
               for s in parsed.statements if s.target and rule.matches(s.target)}
    wanted = {t for _, _, t in FIELD_SHAPES}
    assert wanted <= matched, f"not matched: {sorted(wanted - matched)}"
    check = production.check_against_repo(rule, idx, parsed)
    assert check["missingCount"] == 0, [m["given"] for m in check["missing"]]
    assert check["foundCount"] == 19 and len(check["patterns"]) == 1
    assert check["patterns"][0]["matches"] == 1, "the pasted wildcard finds its shard"
