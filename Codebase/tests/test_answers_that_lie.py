"""Answers that were right in the engine and wrong on the page it was written to.

Found by nine agents measuring the real engine, after the reader fixes above
landed. None of these is a lineage bug. Every one of them is a screen or a
letter saying a different thing from what Ripple actually worked out -- and the
letter is the thing somebody sends to another team:

* A guard written as ``IF (SELECT ...) THEN`` had its condition deleted before
  the reader ever saw it. The identical guard written as ``ASSERT`` was read
  correctly, which is how this was found.
* A whole loop on ONE line looked like a header that had not finished, so every
  line after it in the file was silently replaced with an empty statement.
* One SQL block Ripple could mine bought silence for the unmineable block beside
  it -- the ordinary shape of an Airflow, Oozie or shell job.
* A quoted YAML value running over two lines was cut at the first, and the half
  statement was counted as read.
* "I never saw that column" was printed over a file that could not be read, over
  a folder that was never opened, and over a row access policy naming that very
  column one line further down the same screen.
* The letter said "Please proceed as planned" over all of the above.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from test_confident_over_less import scan                        # noqa: E402
from ripple import narrative                                     # noqa: E402

VALS = {
    "upstream": [{"table": "customer_demographics", "attrs": ["cm13"]}],
    "pocName": "Priya R", "subject": "cm13 change", "effectiveLabel": "15 September",
}


def letter(out: dict) -> str:
    return narrative.draft_reply(out, VALS, narrative.summarise(out, VALS))["body"]


def headline(out: dict) -> str:
    return narrative.summarise(out, VALS)["headline"]


# ── a guard whose condition reads the column ───────────────────────────────
def test_an_if_condition_that_reads_the_column_is_not_deleted(tmp_path):
    """Measured before this: risk none, every count zero, nothing on the check
    list. The whole header line was replaced with an empty statement, and the
    SELECT inside the condition went with it."""
    out = scan(tmp_path, {
        "a.sql": "IF (SELECT MAX(cm13) FROM customer_demographics) IS NOT NULL THEN\n"
                 "  CREATE OR REPLACE TABLE final_published AS SELECT id FROM orders;\n"
                 "END IF;\n"})
    assert out["risk"] != "none", out["risk"]
    assert out["stats"]["breakingUsages"] >= 1, out["stats"]


def test_a_while_condition_that_reads_the_column_is_not_deleted(tmp_path):
    out = scan(tmp_path, {
        "a.sql": "WHILE (SELECT COUNT(*) FROM customer_demographics WHERE cm13 IS NULL) > 0 DO\n"
                 "  SELECT 1;\n"
                 "END WHILE;\n"
                 "CREATE OR REPLACE TABLE final_published AS SELECT id FROM orders;\n"})
    assert out["risk"] != "none", out["risk"]
    assert out["stats"]["breakingUsages"] >= 1, out["stats"]


def test_a_guard_reads_the_same_whichever_way_it_is_spelt(tmp_path):
    """ASSERT already worked. Two spellings of one guard must not give opposite
    answers -- that difference is what found the bug."""
    body = "(SELECT COUNT(*) FROM customer_demographics WHERE cm13 IS NULL)"
    as_assert = scan(tmp_path / "a", {"a.sql": f"ASSERT {body} = 0;\n"})
    as_if = scan(tmp_path / "b", {"a.sql": f"IF {body} > 0 THEN\n  SELECT 1;\nEND IF;\n"})
    assert as_if["stats"]["breakingUsages"] == as_assert["stats"]["breakingUsages"]


def test_an_if_with_no_query_in_it_is_still_dropped(tmp_path):
    """The guard. Only a condition holding a SELECT is worth keeping; keeping
    every IF would hand the parser scripting it cannot read."""
    out = scan(tmp_path, {
        "a.sql": "IF row_count > 0 THEN\n"
                 "  CREATE OR REPLACE TABLE final_published AS "
                 "SELECT cm13 FROM customer_demographics;\n"
                 "END IF;\n"})
    assert [g["prod"] for g in out["groups"]] == ["final_published"], out["groups"]
    assert out["stats"]["couldNotRead"] == 0, out["unreadable"]


# ── a whole loop on one line ───────────────────────────────────────────────
LOOP_FILES = {
    "a.sql": "CREATE OR REPLACE TABLE stage_x AS SELECT cm13 FROM customer_demographics;",
    "b.sql": "CREATE OR REPLACE TABLE final_published AS SELECT cm13 FROM mid_x;",
}


def test_a_one_line_loop_does_not_swallow_the_rest_of_the_file(tmp_path):
    """Measured before this: every line after the loop became an empty
    statement. No parse error, no unreadable entry, nothing on any screen -- the
    trail simply stopped one table short and that was reported as the end."""
    out = scan(tmp_path, {
        **LOOP_FILES,
        "m.sql": "FOR rec IN (SELECT tbl FROM cfg_tables) DO SELECT 1; END FOR;\n"
                 "CREATE OR REPLACE TABLE mid_x AS SELECT * FROM stage_x;\n"})
    assert [g["prod"] for g in out["groups"]] == ["final_published"], out["groups"]


def test_the_same_loop_over_two_lines_gives_the_same_answer(tmp_path):
    """The control that found it. Where a file is broken by a line break, the
    line break is the bug."""
    out = scan(tmp_path, {
        **LOOP_FILES,
        "m.sql": "FOR rec IN (SELECT tbl FROM cfg_tables) DO\n  SELECT 1;\nEND FOR;\n"
                 "CREATE OR REPLACE TABLE mid_x AS SELECT * FROM stage_x;\n"})
    assert [g["prod"] for g in out["groups"]] == ["final_published"], out["groups"]


def test_a_loop_header_that_never_finishes_costs_one_line(tmp_path):
    """It used to cost every line to the end of the file."""
    out = scan(tmp_path, {
        **LOOP_FILES,
        "m.sql": "FOR rec IN (SELECT tbl FROM cfg_tables\n"
                 "CREATE OR REPLACE TABLE mid_x AS SELECT * FROM stage_x;\n"})
    assert [g["prod"] for g in out["groups"]] == ["final_published"], out["groups"]


# ── one mined block silencing the block beside it ──────────────────────────
def test_a_second_sql_block_ripple_cannot_mine_is_still_reported(tmp_path):
    """An Airflow, Oozie or shell job normally holds several tasks of different
    kinds. Finding one used to buy silence for the rest of the file."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE stage_x AS SELECT cm13 FROM customer_demographics;",
        "dags/nightly.yaml":
            "tasks:\n"
            "  - task_id: mid\n"
            "    sql: |\n"
            "      CREATE OR REPLACE TABLE mid_x AS SELECT cm13 FROM stage_x;\n"
            "  - task_id: publish\n"
            "    bash_command: |\n"
            "      bq query 'CREATE OR REPLACE TABLE final_published "
            "AS SELECT cm13 FROM mid_x'\n"})
    assert out["stats"]["couldNotRead"] == 1, out["unreadable"]
    assert out["coverage"]["complete"] is False, out["coverage"]


def test_a_file_whose_sql_was_all_mined_says_nothing(tmp_path):
    """The guard. Reporting every file Ripple read perfectly well would bury the
    list this is trying to protect."""
    out = scan(tmp_path, {
        "dags/load.yaml": "task:\n"
                          "  sql: |\n"
                          "    CREATE OR REPLACE TABLE final_published AS\n"
                          "    SELECT cm13 FROM customer_demographics;\n"})
    assert out["unreadable"] == [], out["unreadable"]


# ── a quoted YAML value over two lines ─────────────────────────────────────
def test_a_quoted_yaml_value_running_over_two_lines_is_read_whole(tmp_path):
    """Measured before this: repo._yaml_blocks gave back
    "CREATE OR REPLACE TABLE final_published AS" with no SELECT -- half a
    statement, which parses, and was therefore counted as read."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE stage_x AS SELECT cm13 FROM customer_demographics;",
        "m.sql": "CREATE OR REPLACE TABLE mid_x AS SELECT cm13 FROM stage_x;",
        "dags/pub.yaml": 'tasks:\n  - task_id: publish\n'
                         '    sql: "CREATE OR REPLACE TABLE final_published AS\n'
                         '      SELECT cm13 FROM mid_x"\n'})
    assert [g["prod"] for g in out["groups"]] == ["final_published"], out["groups"]


# ── "I never saw that column" is a confident claim ─────────────────────────
def test_a_failed_lookup_is_not_claimed_over_a_file_that_could_not_be_read(tmp_path):
    out = scan(tmp_path, {
        "ok.sql": "CREATE OR REPLACE TABLE stage_x AS SELECT customer_id FROM other_table;",
        "proc.sql": "CALL build_the_thing(\n"
                    "  'CREATE OR REPLACE TABLE final_published AS SELECT ' || col_list ||\n"
                    "  ' FROM customer_demographics WHERE cm13 IS NOT NULL'\n"
                    ");\n"})
    assert out["lookupFailed"] is False, out
    assert out["risk"] == "unknown", out["risk"]


def test_a_failed_lookup_is_not_claimed_over_a_folder_that_was_skipped(tmp_path):
    """The whole chain sat in build/, and the answer was a green "no impact"
    with a letter saying "please proceed as planned"."""
    out = scan(tmp_path, {
        "readme.sql": "CREATE OR REPLACE TABLE stage_unrelated AS SELECT 1 AS x;",
        "build/a.sql": "CREATE OR REPLACE TABLE stage_star AS "
                       "SELECT cm13 FROM customer_demographics;",
        "build/b.sql": "CREATE OR REPLACE TABLE final_published AS "
                       "SELECT cm13 FROM stage_star;"})
    assert out["lookupFailed"] is False, out
    assert out["risk"] == "unknown", out["risk"]
    assert out["coverage"]["complete"] is False, out["coverage"]
    assert "proceed as planned" not in letter(out), letter(out)


def test_a_failed_lookup_is_not_claimed_while_a_policy_names_the_column(tmp_path):
    """Ripple demonstrably met cm13 -- it printed the policy that names it one
    card further down the same screen."""
    out = scan(tmp_path, {
        "policy.sql": "CREATE ROW ACCESS POLICY apac_only ON customer_demographics\n"
                      "GRANT TO ('group:apac@example.com')\n"
                      "FILTER USING (cm13 = 'APAC');\n"})
    assert out["lookupFailed"] is False, out
    assert "proceed as planned" not in letter(out), letter(out)
    assert "row access policy" in letter(out), letter(out)


def test_a_genuinely_missing_column_is_still_a_failed_lookup(tmp_path):
    """The guard on all three above."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE stage_a AS SELECT market_code "
                 "FROM customer_demographics;",
        "b.sql": "CREATE OR REPLACE TABLE final_published AS SELECT market_code FROM stage_a;"})
    assert out["lookupFailed"] is True, out
    assert "proceed as planned" not in letter(out), letter(out)
    assert "not found" in headline(out), headline(out)


# ── the letter has to say what the screen says ─────────────────────────────
def test_the_letter_names_the_delivery_out_of_the_warehouse(tmp_path):
    """It used to say the data feeds "tables in our own pipeline"."""
    out = scan(tmp_path, {
        "a.sql": "EXPORT DATA OPTIONS(uri='gs://partner-drop/daily/*.csv', format='CSV') AS\n"
                 "SELECT customer_id, cm13 FROM customer_demographics;\n"})
    assert "gs://partner-drop/daily" in letter(out), letter(out)
    assert "delivery" in headline(out).lower(), headline(out)


def test_the_letter_says_the_published_table_stops_refreshing(tmp_path):
    """The production rule matched final_published perfectly, and the headline
    said "none of them reaching a table on your published list" while telling
    the reader to go and fix the rule that had worked."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE stage_active AS\n"
                 "SELECT customer_id, name FROM customer_demographics WHERE cm13 = 'Y';\n",
        "b.sql": "CREATE OR REPLACE TABLE final_published AS\n"
                 "SELECT customer_id, name FROM stage_active;\n"})
    assert "final_published" in letter(out), letter(out)
    assert "stops being refreshed" in headline(out), headline(out)
    assert "Check the rule" not in narrative.summarise(out, VALS)["narrative"]


def test_a_genuinely_clean_repository_still_says_proceed_as_planned(tmp_path):
    """The guard on every change in this file. A letter that never confirms
    anything is a letter nobody uses."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE final_published AS "
                 "SELECT cm13, other FROM some_other_source;"})
    assert out["risk"] == "none", out["risk"]
    assert out["lookupFailed"] is False, out
    assert "proceed as planned" in letter(out), letter(out)


# ── two more names that exist in one place only ────────────────────────────
def test_a_subquery_in_a_join_condition_does_not_invent_the_output_name(tmp_path):
    """A JOIN has two halves and they are opposite. Its SOURCE hands its columns
    over; its ON condition is a value, exactly like a WHERE. Measured: the
    statement published cm13 under "band_code" -- a name written inside the join
    condition and belonging to no table anywhere -- so the next table, which
    reads plain cm13, was never reached."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE stage_l AS\n"
                 "SELECT c.k, c.cm13\n"
                 "FROM customer_demographics c\n"
                 "LEFT JOIN ref_bands r\n"
                 "  ON r.k = c.k\n"
                 "  AND c.cm13 IN (SELECT cm13 AS band_code FROM allowed_bands);",
        "b.sql": "CREATE OR REPLACE TABLE final_published AS SELECT k, cm13 FROM stage_l;"})
    assert [g["prod"] for g in out["groups"]] == ["final_published"], out["groups"]


def test_a_subquery_joined_as_a_source_still_renames(tmp_path):
    """The guard on the half above. A joined subquery really does hand its
    columns to the query around it, and its renames really do survive."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE stage_j AS\n"
                 "SELECT o.k, d.band_code\n"
                 "FROM orders o\n"
                 "JOIN (SELECT k, cm13 AS band_code FROM customer_demographics) d\n"
                 "  ON d.k = o.k;",
        "b.sql": "CREATE OR REPLACE TABLE final_published AS SELECT k, band_code FROM stage_j;"})
    assert [g["prod"] for g in out["groups"]] == ["final_published"], out["groups"]


def test_select_as_value_struct_publishes_the_fields_as_columns(tmp_path):
    """AS VALUE dissolves the wrapper, so this table's columns are k and code.
    Measured: the select list held one expression with no alias, the statement
    published nothing under any name, and the chain went cold one hop early."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE stage_n AS\n"
                 "SELECT AS VALUE STRUCT(k AS k, cm13 AS code)\n"
                 "FROM customer_demographics;",
        "b.sql": "CREATE OR REPLACE TABLE final_published AS SELECT k, code FROM stage_n;"})
    assert [g["prod"] for g in out["groups"]] == ["final_published"], out["groups"]
    rows = [r for g in out["groups"] for r in g["rows"]]
    assert any(r["alias"] == "code" for r in rows), rows


def test_an_ordinary_struct_column_is_left_alone(tmp_path):
    """The guard. Without AS VALUE the struct really is one column of the
    table, and unwrapping it would invent two columns that are not there."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE stage_s AS\n"
                 "SELECT k, STRUCT(cm13 AS code) AS payload\n"
                 "FROM customer_demographics;",
        "b.sql": "CREATE OR REPLACE TABLE final_published AS SELECT k, code FROM stage_s;"})
    assert [g["prod"] for g in out["groups"]] == [], out["groups"]
