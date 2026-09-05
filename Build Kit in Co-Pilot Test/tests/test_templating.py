"""Tests for the templating and rescue rewrites.

The rescue file was given no test file of its own by the brief, and the brief's
own check line runs this one, so the rescue tests live here too, at the bottom.

Every table and column name below is invented.
"""

from __future__ import annotations

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

from ripple.scanner import rescue
from ripple.scanner.templating import (
    describe,
    fill_placeholders,
    loop_read,
    placeholder_names,
    unwrap_blocks,
)


def _parses(sql: str) -> bool:
    """Whether the real parser accepts this text.

    Against the real parser on purpose: the gap being guarded is exactly the one
    between what this code expects and what the library returns.
    """
    try:
        sqlglot.parse(sql, dialect="bigquery")
    except SqlglotError:
        return False
    return True


def _statements(sql: str) -> list[exp.Expression]:
    """The statements the parser found, with the empty ones left out."""
    return [
        statement
        for statement in sqlglot.parse(sql, dialect="bigquery")
        if statement is not None
    ]


# ---------------------------------------------------------------------------
# PART ONE - placeholders
# ---------------------------------------------------------------------------

DBT_MODEL = """{{ config(
    materialized='table'
) }}
SELECT id FROM {{ ref('customer_demographics') }}
"""


def test_a_placeholder_becomes_the_name_it_always_was() -> None:
    text = (
        "CREATE OR REPLACE TABLE "
        "{{tgt_project_id}}.{{stage_dataset}}.web_activity AS SELECT 1"
    )
    filled = fill_placeholders(text)
    assert "tgt_project_id.stage_dataset.web_activity" in filled
    assert "{" not in filled
    assert "}" not in filled
    assert _parses(filled)


def test_a_dbt_config_header_resolves_to_nothing_at_all() -> None:
    # Turned into a bare identifier, a word lands where SQL expects a keyword
    # and the whole file stops parsing.
    filled = fill_placeholders(DBT_MODEL)
    assert "config" not in filled
    assert "SELECT id FROM customer_demographics" in filled
    assert filled.count("\n") == DBT_MODEL.count("\n")
    assert _parses(filled)


def test_ref_and_source_resolve_to_the_last_quoted_name() -> None:
    assert (
        fill_placeholders("SELECT 1 FROM {{ source('raw', 'orders_daily') }}")
        == "SELECT 1 FROM orders_daily"
    )
    assert (
        fill_placeholders("SELECT 1 FROM {{ ref('orders_daily') }}")
        == "SELECT 1 FROM orders_daily"
    )


def test_the_order_of_the_five_leaves_no_stray_brace() -> None:
    # Take the narrow { name } pattern first and it matches the inner half of
    # {{ name }}, leaving a stray brace and an unreadable file.
    assert fill_placeholders("SELECT 1 FROM {{ a }}.{{ b }}.c") == "SELECT 1 FROM a.b.c"


def test_the_narrow_pattern_leaves_a_regex_quantifier_alone() -> None:
    text = (
        "SELECT * FROM ${src_dataset}.orders_daily "
        "WHERE dt = '{run_date}' AND code LIKE '[0-9]{3}'"
    )
    filled = fill_placeholders(text)
    assert "src_dataset.orders_daily" in filled
    assert "'run_date'" in filled
    assert "{3}" in filled


def test_the_three_fallbacks_in_the_identifier_rule() -> None:
    # An empty one leaves FROM .orders_daily behind, a parse error that costs
    # the whole file.
    assert (
        fill_placeholders("SELECT 1 FROM {{ }}.orders_daily")
        == "SELECT 1 FROM placeholder.orders_daily"
    )
    assert (
        fill_placeholders("SELECT 1 FROM {{ 2024_totals }}") == "SELECT 1 FROM p_2024_totals"
    )
    assert len(fill_placeholders("{{ " + "z" * 90 + " }}")) == 60


def test_a_jinja_filter_still_gives_back_one_identifier() -> None:
    assert fill_placeholders("SELECT {{ x | upper }} AS c") == "SELECT x___upper AS c"


def test_line_numbers_do_not_move_when_a_placeholder_spans_lines() -> None:
    text = (
        "SELECT 1\n"
        "FROM {{\n"
        "  params.src\n"
        "}}.orders_daily\n"
        "WHERE dt = '2024-01-01'\n"
    )
    filled = fill_placeholders(text)
    assert filled.count("\n") == text.count("\n")
    assert filled.splitlines()[3].startswith(".orders_daily")


def test_placeholder_names_are_upper_case_and_skip_the_directives() -> None:
    assert placeholder_names(DBT_MODEL) == {"CUSTOMER_DEMOGRAPHICS"}


def test_placeholder_names_walks_the_three_patterns_that_stand_for_a_value() -> None:
    text = (
        "{# a comment #}{% if run %}\n"
        "SELECT * FROM ${src_dataset}.orders_daily\n"
        "WHERE dt = '{run_date}' AND code LIKE '[0-9]{3}'\n"
        "{% endif %}\n"
    )
    assert placeholder_names(text) == {"SRC_DATASET", "RUN_DATE"}


def test_describe_says_what_kind_of_templating_is_in_the_file() -> None:
    assert describe("SELECT 1 FROM {{ a }}") == (
        "{{ ... }} templating (Airflow, dbt or similar)"
    )
    assert describe("SELECT 1") == ""


# ---------------------------------------------------------------------------
# PART TWO - scripting blocks
# ---------------------------------------------------------------------------

CASE_DOWN_THE_PAGE = """BEGIN
CREATE OR REPLACE TABLE ds.customer_status AS
SELECT
  id,
  CASE WHEN status = 'A' THEN 'Active'
  ELSE
    'Unknown'
  END AS status_desc
FROM customer_demographics;
END;
"""


def test_a_case_written_down_the_page_survives_intact() -> None:
    # The test to insist on. Cut the ELSE and the END and a 600-line CREATE
    # TABLE is thrown away whole, with every table and column in it.
    out = unwrap_blocks(CASE_DOWN_THE_PAGE)
    assert "ELSE" in out
    assert "END AS status_desc" in out
    assert out.count("\n") == CASE_DOWN_THE_PAGE.count("\n")
    creates = [s for s in _statements(out) if isinstance(s, exp.Create)]
    assert len(creates) == 1
    written = creates[0].sql(dialect="bigquery").lower()
    assert "customer_status" in written
    assert "customer_demographics" in written
    assert "status_desc" in written


def test_a_scripting_end_is_dropped() -> None:
    text = "BEGIN\nSELECT id FROM customer_demographics;\nEND;\n"
    assert unwrap_blocks(text) == ";\nSELECT id FROM customer_demographics;\n;\n"


def test_a_keyword_inside_a_string_is_not_scripting() -> None:
    text = (
        "CREATE OR REPLACE TABLE ds.notes_daily AS\n"
        "SELECT '''\n"
        "END\n"
        "''' AS note\n"
        "FROM customer_demographics;\n"
    )
    # Nothing matched, so the same object comes back untouched.
    assert unwrap_blocks(text) is text


def test_a_stray_end_in_a_string_does_not_close_a_real_case() -> None:
    text = (
        "CREATE OR REPLACE TABLE ds.customer_status AS\n"
        "SELECT CASE WHEN note = 'the END of it' THEN 'a'\n"
        "ELSE\n"
        "'b'\n"
        "END AS flag\n"
        "FROM customer_demographics;\n"
    )
    out = unwrap_blocks(text)
    assert out is text
    assert _parses(out)


def test_begin_does_not_eat_the_statement_after_it() -> None:
    text = (
        "BEGIN CREATE OR REPLACE TABLE ds.web_activity AS "
        "SELECT id FROM customer_demographics;\nEND;\n"
    )
    out = unwrap_blocks(text)
    assert out.split("\n")[0] == (
        "; CREATE OR REPLACE TABLE ds.web_activity AS "
        "SELECT id FROM customer_demographics;"
    )
    creates = [s for s in _statements(out) if isinstance(s, exp.Create)]
    assert len(creates) == 1
    assert "web_activity" in creates[0].sql(dialect="bigquery")


def test_a_procedure_body_is_kept() -> None:
    text = (
        "CREATE OR REPLACE PROCEDURE `proj.ds.load_web_activity`(\n"
        "    IN tbl STRING,\n"
        "    IN run_date DATE\n"
        ")\n"
        "BEGIN\n"
        "CREATE OR REPLACE TABLE ds.web_activity AS SELECT id FROM customer_demographics;\n"
        "END;\n"
    )
    out = unwrap_blocks(text)
    assert out.count("\n") == text.count("\n")
    assert "PROCEDURE" not in out
    # The body is ordinary SQL worth reading, and the first semicolon sits
    # inside it, which is why the signature is found by counting brackets.
    creates = [s for s in _statements(out) if isinstance(s, exp.Create)]
    assert len(creates) == 1
    assert "web_activity" in creates[0].sql(dialect="bigquery")


def test_a_loop_header_keeps_its_table_and_its_row_variable() -> None:
    text = (
        "FOR rec IN (SELECT id, cm13 AS seg FROM customer_demographics) DO\n"
        "INSERT INTO final_published (id, seg) VALUES (rec.id, rec.seg);\n"
        "END FOR;\n"
    )
    out = unwrap_blocks(text)
    assert out.split("\n")[0] == (
        "CREATE TEMP TABLE rec AS SELECT * FROM "
        "(SELECT id, cm13 AS seg FROM customer_demographics);"
    )
    assert "INSERT INTO final_published" in out
    assert out.count("\n") == text.count("\n")


def test_a_loop_header_written_across_lines_is_gathered() -> None:
    text = (
        "FOR rec IN (\n"
        "  SELECT id, cm13 AS seg FROM customer_demographics\n"
        ") DO\n"
        "INSERT INTO final_published (id, seg) VALUES (rec.id, rec.seg);\n"
        "END FOR;\n"
    )
    out = unwrap_blocks(text)
    lines = out.split("\n")
    assert lines[0] == (
        "CREATE TEMP TABLE rec AS SELECT * FROM "
        "( SELECT id, cm13 AS seg FROM customer_demographics );"
    )
    assert lines[1] == ";"
    assert lines[2] == ";"
    assert out.count("\n") == text.count("\n")


def test_a_while_header_stays_the_plain_read_it_always_was() -> None:
    text = "WHILE (SELECT COUNT(*) FROM customer_demographics) > 0 DO\nSELECT 1;\nEND WHILE;\n"
    out = unwrap_blocks(text)
    assert out.split("\n")[0] == (
        "SELECT * FROM (SELECT COUNT(*) FROM customer_demographics);"
    )


def test_a_whole_loop_on_one_line_does_not_eat_the_rest_of_the_file() -> None:
    text = (
        "FOR rec IN (SELECT tbl FROM cfg_tables) DO SELECT 1; END FOR;\n"
        "CREATE OR REPLACE TABLE ds.web_activity AS SELECT id FROM customer_demographics;\n"
    )
    out = unwrap_blocks(text)
    lines = out.split("\n")
    assert lines[0].startswith(
        "CREATE TEMP TABLE rec AS SELECT * FROM (SELECT tbl FROM cfg_tables);"
    )
    assert "SELECT 1;" in lines[0]
    assert "END FOR" not in out
    # The line after it must still be there: the trail stopping one table short
    # is reported as where the chain ends, with nothing on any screen.
    assert lines[1] == (
        "CREATE OR REPLACE TABLE ds.web_activity AS "
        "SELECT id FROM customer_demographics;"
    )


def test_a_multi_line_raise_is_consumed_whole() -> None:
    text = (
        "EXCEPTION WHEN ERROR THEN\n"
        "RAISE USING MESSAGE = FORMAT(\n"
        '  "load failed for %s",\n'
        "  tbl);\n"
        "END;\n"
    )
    out = unwrap_blocks(text)
    assert "RAISE" not in out
    assert out.count("\n") == text.count("\n")
    assert [line for line in out.split("\n") if line.strip()] == [";", ";", ";", ";", ";"]


def test_a_bare_raise_is_matched_too() -> None:
    # A pattern written around USING MESSAGE misses this one, which is enough
    # on its own to put a readable file on the check-by-hand list.
    text = "SELECT id FROM customer_demographics;\nRAISE;\n"
    out = unwrap_blocks(text)
    assert out == "SELECT id FROM customer_demographics;\n;\n"


def test_an_if_holding_a_query_keeps_the_read() -> None:
    guard = (
        "IF (SELECT MAX(cm13) FROM customer_demographics) IS NOT NULL THEN\n"
        "SELECT 1;\n"
        "END IF;\n"
    )
    out = unwrap_blocks(guard)
    assert out.split("\n")[0] == (
        "SELECT * FROM (SELECT MAX(cm13) FROM customer_demographics);"
    )
    # The identical guard written as ASSERT reads correctly, and where two
    # spellings of one guard give opposite answers the difference is a bug.
    assertion = "ASSERT (SELECT MAX(cm13) FROM customer_demographics) IS NOT NULL;\n"
    assert "customer_demographics" in unwrap_blocks(assertion)


def test_an_if_with_no_query_in_it_is_dropped() -> None:
    text = "IF row_count > 0 THEN\nSELECT 1;\nEND IF;\n"
    assert unwrap_blocks(text) == ";\nSELECT 1;\n;\n"


def test_unwrap_returns_the_same_object_when_there_is_no_scripting() -> None:
    text = "SELECT id FROM customer_demographics;\n"
    assert unwrap_blocks(text) is text


def test_every_line_in_is_a_line_out() -> None:
    text = (
        "DECLARE tbl STRING;\n"
        "BEGIN\n"
        "FOR rec IN (SELECT id FROM cfg_tables) DO\n"
        "  INSERT INTO final_published (id) VALUES (rec.id);\n"
        "END FOR;\n"
        "EXCEPTION WHEN ERROR THEN\n"
        "RAISE USING MESSAGE = @@error.message;\n"
        "END;\n"
    )
    out = unwrap_blocks(text)
    assert out.count("\n") == text.count("\n")
    assert len(out.split("\n")) == len(text.split("\n"))


def test_loop_read_is_the_one_helper_every_loop_goes_through() -> None:
    assert loop_read("rec", "(SELECT id FROM customer_demographics)") == (
        "CREATE TEMP TABLE rec AS SELECT * FROM (SELECT id FROM customer_demographics);"
    )
    assert loop_read(None, "(SELECT id FROM customer_demographics)") == (
        "SELECT * FROM (SELECT id FROM customer_demographics);"
    )


# ---------------------------------------------------------------------------
# PART THREE - the shapes the parser simply refuses
# ---------------------------------------------------------------------------


def test_a_bare_table_argument_stops_the_parser_and_the_rewrite_fixes_it() -> None:
    # A hard parse error takes the neighbouring statements down with it. If the
    # first assertion here fails, sqlglot has started accepting this shape and
    # the rewrite is no longer needed rather than being wrong.
    sql = "SELECT id FROM APPENDS(TABLE `proj.ds.customer_demographics`, NULL);"
    assert not _parses(sql)
    out = rescue.rescue_text(sql)
    assert out == "SELECT id FROM APPENDS( `proj.ds.customer_demographics`, NULL);"
    assert _parses(out)


def test_a_backticked_function_name_is_not_skipped() -> None:
    sql = "SELECT id FROM `proj.ds.f`(TABLE `proj.ds.orders_daily`, 'apple');"
    out = rescue.rescue_text(sql)
    assert "TABLE" not in out
    assert "`proj.ds.orders_daily`" in out


def test_undrop_lands_as_a_generic_command() -> None:
    sql = "UNDROP TABLE `proj.ds.customer_demographics`;"
    out = rescue.rescue_text(sql)
    assert out == "EXECUTE UNDROP TABLE `proj.ds.customer_demographics`;"
    assert _parses(out)


def test_a_snapshot_and_a_replica_become_plain_creates() -> None:
    snapshot = "CREATE SNAPSHOT TABLE ds.orders_snap CLONE ds.orders_daily;"
    assert rescue.rescue_text(snapshot) == (
        "CREATE TABLE ds.orders_snap CLONE ds.orders_daily;"
    )
    assert _parses(rescue.rescue_text(snapshot))

    replica = "CREATE MATERIALIZED VIEW ds.orders_mv AS REPLICA OF ds.orders_daily;"
    assert rescue.rescue_text(replica) == (
        "CREATE TABLE ds.orders_mv COPY ds.orders_daily;"
    )
    assert _parses(rescue.rescue_text(replica))


def test_system_time_is_dropped_only_beside_a_copy() -> None:
    copied = (
        "CREATE TABLE ds.orders_snap CLONE ds.orders_daily "
        "FOR SYSTEM_TIME AS OF TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 DAY);"
    )
    assert rescue.rescue_text(copied) == (
        "CREATE TABLE ds.orders_snap CLONE ds.orders_daily ;"
    )
    # The same words are legal on an ordinary FROM and the parser reads those.
    ordinary = (
        "SELECT id FROM ds.orders_daily FOR SYSTEM_TIME AS OF TIMESTAMP('2024-01-01');"
    )
    assert rescue.rescue_text(ordinary) == ordinary


def test_external_table_clauses_go_with_their_brackets() -> None:
    sql = (
        "CREATE EXTERNAL TABLE ds.landing_zone (id STRING)\n"
        "WITH CONNECTION `proj.us.conn_one`\n"
        "WITH PARTITION COLUMNS (dt DATE)\n"
        "OPTIONS (format = 'CSV', uris = ['gs://bucket/one)two.csv']);\n"
    )
    out = rescue.rescue_text(sql)
    assert "WITH CONNECTION" not in out
    assert "PARTITION COLUMNS" not in out
    assert "(dt DATE)" not in out
    # The bracket inside the quoted uri closes nothing, so the OPTIONS clause
    # is still whole.
    assert "'gs://bucket/one)two.csv'" in out
    assert out.count("\n") == sql.count("\n")
    assert _parses(out)


def test_load_data_becomes_a_create_table() -> None:
    sql = (
        "LOAD DATA INTO ds.landing_zone (id STRING, dt DATE) "
        "FROM FILES (format='CSV', uris=['gs://bucket/a.csv']);"
    )
    out = rescue.rescue_text(sql)
    assert out.startswith("CREATE TABLE ds.landing_zone (id STRING, dt DATE)")
    assert "FROM FILES" not in out
    assert _parses(out)


def test_export_data_leaves_the_select_and_names_its_feed() -> None:
    sql = (
        "EXPORT DATA OPTIONS(\n"
        "  uri='gs://feed/partner/*.csv', format='CSV')\n"
        "AS SELECT id FROM customer_demographics;\n"
    )
    # Read BEFORE the rewrite, because the rewrite takes the OPTIONS with it.
    assert rescue.export_targets(sql) == [(0, "gs://feed/partner/*.csv")]
    out = rescue.rescue_text(sql)
    assert out.count("\n") == sql.count("\n")
    assert out.strip().startswith("SELECT id FROM customer_demographics")
    assert _parses(out)


def test_export_targets_finds_nothing_where_there_is_nothing() -> None:
    assert rescue.export_targets("SELECT id FROM customer_demographics;") == []


def test_sqlx_blocks_keep_the_sql_that_really_runs() -> None:
    text = (
        "config {\n"
        '  type: "table",\n'
        "}\n"
        "pre_operations {\n"
        "  CREATE OR REPLACE TABLE ds.staging_orders AS "
        "SELECT id FROM customer_demographics\n"
        "}\n"
        "SELECT id FROM ds.staging_orders\n"
    )
    out = rescue.rescue_text(text)
    assert "config" not in out
    assert "pre_operations" not in out
    assert "CREATE OR REPLACE TABLE ds.staging_orders" in out
    assert out.count("\n") == text.count("\n")
    assert _parses(out)


def test_the_copy_is_not_the_text_that_ends_up_on_screen() -> None:
    sql = (
        "LOAD DATA INTO ds.landing_zone (id STRING) "
        "FROM FILES (uris=['gs://bucket/a.csv']);"
    )
    out = rescue.rescue_text(sql)
    assert out != sql
    # Somebody sent to this line must find what they were told they would find.
    assert sql.startswith("LOAD DATA INTO ds.landing_zone")


def test_text_with_none_of_these_words_comes_straight_back() -> None:
    sql = "SELECT id FROM customer_demographics;"
    assert rescue.rescue_text(sql) is sql
