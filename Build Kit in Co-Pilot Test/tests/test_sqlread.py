"""Tests for ripple/scanner/sqlread.py.

Every table and column name in here is invented.

Most of these go through parse_block rather than parse_file, so that they test
this file and not Phase 3: parse_block takes SQL that has already been filled in
and already been through the rescue pass, which is exactly what parse_file hands
it. Where a rule only makes sense against rescued text - the word TABLE taken
out of APPENDS(TABLE t) - the test writes the rescued form and says so.

Each test names, in its own assertion, what goes wrong when the behaviour is
missing, because the failure this file guards against is never a crash: it is a
calm, clean, complete no-impact answer over none of the picture.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from ripple.scanner import sqlread
from ripple.scanner.sqlread import (
    Statement,
    display_table,
    label_for,
    locate,
    mode_of,
    output_names,
    parse_block,
    reads_from,
    same_table,
    shard_verdict,
    snippet,
    split_statements,
    usages_of,
)


@dataclass
class _Cfg:
    """Stands in for ripple/config.py, which is another window's file."""

    sql_dialect: str = "bigquery"


@dataclass
class _File:
    """Stands in for repo.py's SourceFile: only these four fields are read."""

    path: str
    abs_path: str
    text: str
    lang: str


CFG = _Cfg()
CUSTOMERS = "ds.customer_demographics"


def _read(sql: str, **kwargs):
    return parse_block(sql, CFG, file="jobs/a.sql", lang="sql", **kwargs)


def _one(sql: str, **kwargs) -> Statement:
    statements, problems, _opaque = _read(sql, **kwargs)
    assert not problems, "unexpected problems: " + repr([p.message for p in problems])
    assert len(statements) == 1, "expected one statement, got " + str(len(statements))
    return statements[0]


def _kinds(usages) -> list[str]:
    return [usage.kind for usage in usages]


# --------------------------------------------------------------------------
# Splitting
# --------------------------------------------------------------------------


def test_the_splitter_ignores_semicolons_inside_quotes_and_comments() -> None:
    text = (
        "SELECT 'a;b' AS a FROM ds.t1;\n"
        "-- a comment; with a semicolon\n"
        "/* another; one */\n"
        "SELECT `odd;name` AS b FROM ds.t2\n"
    )
    chunks = split_statements(text)
    assert len(chunks) == 2, (
        "a semicolon inside a string or a comment split a statement in half, so "
        "both halves stop parsing: " + repr([chunk for chunk, _ in chunks])
    )


def test_each_chunk_carries_its_own_zero_based_start_line() -> None:
    text = "SELECT 1 AS a FROM ds.t1;\n\nSELECT 2 AS b FROM ds.t2;\n"
    starts = [start for _sql, start in split_statements(text)]
    assert starts == [0, 2], (
        "the second statement's own start line was lost, so every finding in "
        "it points at the top of the block: " + repr(starts)
    )


def test_one_bad_statement_does_not_take_the_good_ones_with_it() -> None:
    sql = "SELECT 1 AS a FROM ds.t1;\nSELECT cm13 FROM;\nSELECT 2 AS b FROM ds.t2"
    statements, problems, _opaque = _read(sql)
    assert len(statements) == 2, (
        "sqlglot gave up at the first statement it could not follow and took "
        "the other two down with it, so the whole file reads as unreadable"
    )
    assert len(problems) == 1
    assert problems[0].line == 2, (
        "the unreadable statement is reported at the wrong line: " + str(problems[0].line)
    )
    assert "could not" in problems[0].message.lower()


def test_a_statement_gets_its_own_span_not_the_blocks() -> None:
    sql = "SELECT 1 AS a FROM ds.t1;\nSELECT 2 AS b FROM ds.t2;\n"
    statements, _problems, _opaque = _read(sql)
    assert [statement.line_offset for statement in statements] == [0, 1], (
        "every statement was given the block's offset, so a finding points at "
        "somebody else's statement about somebody else's table"
    )
    assert statements[1].line_end == 1


# --------------------------------------------------------------------------
# Targets and sources
# --------------------------------------------------------------------------


def test_merge_delete_and_update_are_seen() -> None:
    merge = _one(
        "MERGE INTO ds.final_published t USING ds.stage_customers s ON t.k = s.k "
        "WHEN MATCHED THEN UPDATE SET t.market = s.cm13"
    )
    assert same_table(merge.target, "ds.final_published"), (
        "a MERGE recorded no target, so the chain stops one step short of the "
        "table anyone actually reads: " + repr(merge.target)
    )
    assert any(same_table(source, "ds.stage_customers") for source in merge.sources), (
        "a MERGE whose USING names a table recorded no sources at all, so no "
        "scan could ever reach it: " + repr(merge.sources)
    )
    assert not any(
        same_table(source, "ds.final_published") for source in merge.sources
    ), "the MERGE's own target was recorded as one of its sources"

    deleted = _one("DELETE FROM ds.stage_customers WHERE cm13 = 'AA'")
    assert same_table(deleted.target, "ds.stage_customers")
    assert any(
        same_table(source, "ds.stage_customers") for source in deleted.sources
    ), "a DELETE does not read its own target, so nothing looks at its WHERE"

    updated = _one(
        "UPDATE ds.final_published t SET t.market = s.cm13 "
        "FROM ds.customer_demographics s WHERE t.pub_id = s.pub_id"
    )
    assert same_table(updated.target, "ds.final_published")
    assert any(same_table(source, CUSTOMERS) for source in updated.sources), (
        "an UPDATE ... FROM reads a whole second table and has no SELECT, and "
        "gating the source walk on one loses it: " + repr(updated.sources)
    )


def test_a_cte_name_is_not_a_table() -> None:
    statement = _one(
        "CREATE OR REPLACE TABLE ds.stage AS "
        "WITH recent AS (SELECT cm13 FROM ds.customer_demographics) "
        "SELECT cm13 FROM recent"
    )
    assert not any(
        sqlread.short_name(source) == "recent" for source in statement.sources
    ), "a CTE was treated as a table, which invents a link that is not there"
    assert any(same_table(source, CUSTOMERS) for source in statement.sources)


def test_a_union_records_both_halves_tables() -> None:
    statement = _one(
        "CREATE OR REPLACE TABLE ds.both AS "
        "SELECT cm13 AS a_name FROM ds.customer_demographics "
        "UNION ALL SELECT cm13 AS b_name FROM ds.other_source"
    )
    assert any(same_table(source, "ds.other_source") for source in statement.sources), (
        "only the first SELECT's tables were read, so a change to the second "
        "half's table produces no findings anywhere"
    )


def test_a_statement_that_writes_the_table_it_reads_still_records_it() -> None:
    statement = _one("INSERT INTO ds.t SELECT cm13 FROM ds.t")
    assert any(same_table(source, "ds.t") for source in statement.sources), (
        "the source was excluded by NAME rather than by node, so a statement "
        "that really does read the table it writes is indexed as reading "
        "nothing at all"
    )


def test_information_schema_is_never_a_source() -> None:
    statement = _one(
        "CREATE OR REPLACE TABLE ds.audit AS "
        "SELECT table_name FROM ds.INFORMATION_SCHEMA.TABLES"
    )
    assert statement.sources == set(), (
        "the warehouse describing itself was recorded as lineage: " + repr(statement.sources)
    )


def test_a_generated_range_of_dates_is_not_a_table() -> None:
    statement = _one(
        "SELECT day FROM GENERATE_DATE_ARRAY('2026-01-01', '2026-01-05') AS day"
    )
    assert statement.sources == set(), (
        "a repository that builds a calendar that way reports a table called "
        "GENERATE_DATE_ARRAY feeding production: " + repr(statement.sources)
    )


def test_a_table_handed_into_a_function_is_a_real_read() -> None:
    # Written the way the rescue pass leaves it: the word TABLE has to come out
    # before the parser will take the statement at all.
    statement = _one("SELECT cm13 FROM APPENDS(`prj.ds.customer_demographics`, NULL)")
    assert any(
        same_table(source, "prj.ds.customer_demographics") for source in statement.sources
    ), (
        "an incremental load - exactly how a published table is kept up to "
        "date - was recorded as reading nothing: " + repr(statement.sources)
    )
    assert not any(
        sqlread.short_name(source) == "appends" for source in statement.sources
    ), "the wrapper was taken as a table, which invents a table nobody has"


def test_a_table_function_definition_publishes_a_table() -> None:
    statement = _one(
        "CREATE OR REPLACE TABLE FUNCTION ds.recent(d STRING) AS ("
        "SELECT cm13 FROM ds.customer_demographics WHERE dt = d)"
    )
    assert same_table(statement.target, "ds.recent"), (
        "the definition parsed as a function and published nothing, so the "
        "chain breaks in the middle: " + repr(statement.target)
    )


def test_a_scalar_function_is_not_a_table() -> None:
    statement = _one("CREATE OR REPLACE FUNCTION ds.tidy(x STRING) AS (UPPER(x))")
    assert statement.target == "", (
        "a scalar UDF was published as a table, which turns every helper in "
        "the repository into one: " + repr(statement.target)
    )


def test_a_whole_table_copy_carries_the_column_and_keeps_the_word() -> None:
    statement = _one("CREATE OR REPLACE TABLE ds.published_customers COPY ds.stage_customers")
    assert any(
        same_table(source, "ds.stage_customers") for source in statement.sources
    ), (
        "with no source recorded the trail dies at the staging table and the "
        "screen says 'last table in the chain', which reads as an answer"
    )
    assert statement.whole_copy == "COPY"
    assert output_names(statement, "cm13") == ["cm13"]
    usages = usages_of(statement, "cm13", "ds.stage_customers")
    assert "star" in _kinds(usages)
    starred = [usage for usage in usages if usage.kind == "star"][0]
    assert label_for(starred) == "Carried by COPY", (
        "the row would tell somebody the file says SELECT * when it says COPY"
    )


def test_alter_table_rename_to_is_a_whole_table_copy() -> None:
    statement = _one("ALTER TABLE ds.stage_customers RENAME TO ds.published_customers")
    assert same_table(statement.target, "ds.published_customers")
    assert any(same_table(source, "ds.stage_customers") for source in statement.sources)
    assert statement.whole_copy == "RENAME"


# --------------------------------------------------------------------------
# Names a column leaves under
# --------------------------------------------------------------------------


def test_a_rename_inside_a_subquery_is_followed_out() -> None:
    statement = _one(
        "CREATE OR REPLACE TABLE ds.stage AS SELECT lut_ts FROM "
        "(SELECT c.last_upd AS lut_ts FROM ds.customer_demographics c)"
    )
    assert output_names(statement, "last_upd") == ["lut_ts"], (
        "the rename buried in the subquery was not followed out, so the trail "
        "goes cold at exactly the statements that matter most"
    )


def test_a_column_leaving_under_two_names_returns_both_unchanged_first() -> None:
    statement = _one(
        "CREATE OR REPLACE TABLE ds.stage AS "
        "SELECT CAST(cm13 AS STRING) AS cm13_str, cm13 FROM ds.customer_demographics"
    )
    names = output_names(statement, "cm13")
    assert "cm13" in names and "cm13_str" in names, (
        "only one of the two names was followed, so the next table reading the "
        "other is never reached: " + repr(names)
    )
    assert names[0] == "cm13", (
        "the name carried through unchanged has to come first so it survives "
        "the six-name cap: " + repr(names)
    )


def test_a_union_keeps_the_first_branchs_name_first() -> None:
    statement = _one(
        "CREATE OR REPLACE TABLE ds.both AS "
        "SELECT cm13 AS a_name FROM ds.customer_demographics "
        "UNION ALL SELECT cm13 AS b_name FROM ds.other_source"
    )
    names = output_names(statement, "cm13")
    assert names[:2] == ["a_name", "b_name"], (
        "SQL takes a union's output names from its FIRST branch, and that is "
        "the one the rest of the warehouse is reading: " + repr(names)
    )


def test_a_chain_of_ctes_at_one_depth_runs_to_the_last_name() -> None:
    statement = _one(
        "CREATE OR REPLACE TABLE ds.final AS "
        "WITH src AS (SELECT k, cm13 FROM ds.customer_demographics), "
        "renamed AS (SELECT k, cm13 AS customer_code FROM src), "
        "final AS (SELECT k, customer_code AS cust_code FROM renamed) "
        "SELECT * FROM final"
    )
    names = output_names(statement, "cm13")
    assert "cust_code" in names, (
        "the level was read once instead of run to a fixpoint, so the trail "
        "stops at customer_code while the published table reads cust_code - a "
        "name Ripple never said out loud: " + repr(names)
    )


def test_a_cte_that_says_nothing_about_the_column_does_not_end_the_chain() -> None:
    statement = _one(
        "CREATE OR REPLACE TABLE ds.stage_c AS "
        "WITH other AS (SELECT x FROM ds.y) "
        "SELECT cm13 FROM ds.customer_demographics JOIN other USING (k)"
    )
    assert output_names(statement, "cm13") == ["cm13"], (
        "one unrelated CTE emptied the list of names, so the table the "
        "statement builds is never reached"
    )


def test_a_sibling_except_does_not_delete_another_stars_column() -> None:
    statement = _one(
        "CREATE OR REPLACE TABLE ds.stage_p AS "
        "WITH cust AS (SELECT * FROM ds.customer_demographics), "
        "hits AS (SELECT * EXCEPT (cm13) FROM ds.web_events) "
        "SELECT cust.*, hits.url FROM cust JOIN hits USING (k)"
    )
    assert "cm13" in output_names(statement, "cm13"), (
        "an EXCEPT belonging to a CTE that never reads the scanned table "
        "deleted the column arriving through another star, and the trail died "
        "inside the statement"
    )


def test_select_star_except_on_its_own_still_stops_the_trail() -> None:
    statement = _one(
        "CREATE OR REPLACE TABLE ds.s1 AS "
        "SELECT * EXCEPT (cm13) FROM ds.customer_demographics"
    )
    assert output_names(statement, "cm13") == [], (
        "a column dropped BY NAME was reported as carried through"
    )
    kinds = _kinds(usages_of(statement, "cm13", CUSTOMERS))
    assert "excluded" in kinds
    assert "star" not in kinds, (
        "the star spoke as well, so 'carried through untouched' is printed "
        "beside 'named here, and this statement fails without it'"
    )


def test_select_star_replace_names_the_column() -> None:
    statement = _one(
        "CREATE OR REPLACE TABLE ds.s1 AS "
        "SELECT * REPLACE (legacy_code AS cm13) FROM ds.customer_demographics"
    )
    usages = usages_of(statement, "cm13", CUSTOMERS)
    excluded = [usage for usage in usages if usage.kind == "excluded"]
    assert excluded, (
        "the row read 'breaking: false' about a statement that stops compiling"
    )
    assert label_for(excluded[0]) == "Named in REPLACE", (
        "a REPLACE was labelled as an EXCEPT; they are different statements "
        "and the file says which"
    )


def test_select_star_rename_carries_the_column_on_under_the_new_name() -> None:
    statement = _one(
        "CREATE OR REPLACE TABLE ds.s1 AS "
        "SELECT * RENAME (cm13 AS cm13_new) FROM ds.customer_demographics"
    )
    names = output_names(statement, "cm13")
    assert names == ["cm13_new"], (
        "the star carried cm13 through untouched, so the trail follows a name "
        "the table it builds does not have: " + repr(names)
    )


def test_a_column_list_outside_the_select_renames_by_position() -> None:
    inserted = _one(
        "INSERT INTO ds.stage_tbl (member_id) "
        "SELECT cm13 FROM ds.customer_demographics"
    )
    assert output_names(inserted, "cm13") == ["member_id"], (
        "the SELECT hands its values over by position, and following its own "
        "name walks the chain off the end at the load statement"
    )
    view = _one(
        "CREATE OR REPLACE VIEW ds.v1(a, b) AS "
        "SELECT cm13, region FROM ds.customer_demographics"
    )
    assert output_names(view, "cm13") == ["a"], (
        "the trail stops at the view AND a downstream table reading the old "
        "name is reported as a confident break"
    )


def test_a_positional_list_is_ignored_when_the_arity_cannot_be_checked() -> None:
    statement = _one(
        "INSERT INTO ds.stage_tbl (a, b) SELECT * FROM ds.customer_demographics"
    )
    assert output_names(statement, "cm13") == ["cm13"], (
        "a position was invented for the name where the two lists could not be "
        "lined up"
    )


def test_a_struct_field_is_published_under_its_dotted_name() -> None:
    statement = _one(
        "CREATE OR REPLACE TABLE ds.s AS "
        "SELECT k, STRUCT(cm13 AS code, seg AS segment) AS payload "
        "FROM ds.customer_demographics"
    )
    names = output_names(statement, "cm13")
    assert "payload.code" in names, (
        "the chain stopped at the wrapper while payload.code is how the field "
        "is read one hop later: " + repr(names)
    )
    assert "code" not in names, (
        "publishing the bare field name invents a column the table does not "
        "have - SELECT code FROM that table is an error"
    )


def test_a_struct_field_with_no_as_is_named_after_itself() -> None:
    statement = _one(
        "CREATE OR REPLACE TABLE ds.s AS "
        "SELECT STRUCT(cm13) AS payload FROM ds.customer_demographics"
    )
    assert "payload.cm13" in output_names(statement, "cm13"), (
        "a struct built out of plain column names published nothing at all"
    )


def test_a_value_subquery_does_not_publish_its_own_names() -> None:
    statement = _one(
        "CREATE OR REPLACE TABLE ds.s AS SELECT o.k, "
        "(SELECT MAX(d.cm13) AS c_alias FROM ds.customer_demographics d "
        "WHERE d.k = o.k) AS peak_cm FROM ds.other_source o"
    )
    names = output_names(statement, "cm13")
    assert "c_alias" not in names, (
        "a name that exists only inside the brackets was published, so the "
        "chain went cold one hop early: " + repr(names)
    )
    assert "peak_cm" in names, (
        "the real output name was not followed: " + repr(names)
    )


def test_a_name_written_inside_a_join_condition_is_not_published() -> None:
    statement = _one(
        "CREATE OR REPLACE TABLE ds.s AS SELECT c.k, c.cm13 "
        "FROM ds.customer_demographics c LEFT JOIN ds.ref_bands r "
        "ON r.k = c.k AND c.cm13 IN (SELECT cm13 AS band_code FROM ds.allowed_bands)"
    )
    names = output_names(statement, "cm13")
    assert "band_code" not in names, (
        "a join's ON condition is a value exactly like a WHERE, and its names "
        "belong to no table anywhere: " + repr(names)
    )
    assert "cm13" in names


def test_alter_table_rename_column_is_followed_and_drop_stops_it() -> None:
    renamed = _one("ALTER TABLE ds.customer_demographics RENAME COLUMN cm13 TO cm14")
    assert output_names(renamed, "cm13") == ["cm14"], (
        "the plainest statement of a rename the language has reported no "
        "impact at all"
    )
    assert "renamed" in _kinds(usages_of(renamed, "cm13", CUSTOMERS))

    dropped = _one("ALTER TABLE ds.customer_demographics DROP COLUMN cm13")
    assert output_names(dropped, "cm13") == []
    assert "dropped" in _kinds(usages_of(dropped, "cm13", CUSTOMERS))


# --------------------------------------------------------------------------
# How a column is used
# --------------------------------------------------------------------------


def test_a_filter_records_the_literal_it_compares_against() -> None:
    statement = _one(
        "CREATE OR REPLACE TABLE ds.s AS SELECT k FROM ds.customer_demographics "
        "WHERE cm13 = 'US'"
    )
    usages = usages_of(statement, "cm13", CUSTOMERS)
    filters = [usage for usage in usages if usage.kind == "filter"]
    assert filters, "a WHERE clause on the column was not read at all"
    assert filters[0].detail == "US", (
        "the literal the screen prints beside the filter was lost: "
        + repr(filters[0].detail)
    )


def test_a_join_on_the_other_tables_column_of_the_same_name_is_not_reported() -> None:
    statement = _one(
        "CREATE OR REPLACE TABLE ds.s AS SELECT c.k FROM ds.customer_demographics c "
        "JOIN ds.orders o ON o.cm13 = c.k"
    )
    usages = usages_of(statement, "cm13", CUSTOMERS)
    assert usages == [] or all(not usage.certain for usage in usages), (
        "a filter on the OTHER table's column of the same name was reported as "
        "a usage of the one being changed: " + repr(usages)
    )


def test_where_the_sql_does_not_say_the_usage_is_kept_but_not_certain() -> None:
    statement = _one(
        "CREATE OR REPLACE TABLE ds.s AS SELECT k FROM ds.customer_demographics "
        "JOIN ds.orders USING (k) WHERE cm13 = 'US'"
    )
    usages = usages_of(statement, "cm13", CUSTOMERS)
    assert usages, "the usage was thrown away rather than marked inferred"
    assert all(not usage.certain for usage in usages), (
        "an unqualified column in a two-table statement was asserted as "
        "certain, which is a claim the SQL never made"
    )


def test_an_inner_exists_rebinding_an_alias_does_not_rule_the_usage_out() -> None:
    statement = _one(
        "CREATE OR REPLACE TABLE ds.final_published AS SELECT t.k, o.amount "
        "FROM (SELECT * FROM ds.customer_demographics) t "
        "JOIN ds.orders o ON o.k = t.k "
        "WHERE t.cm13 = 'A' "
        "AND EXISTS (SELECT 1 FROM ds.legacy_dim t WHERE t.k = o.k)"
    )
    assert usages_of(statement, "cm13", CUSTOMERS), (
        "the alias map was flat across the whole statement, so the inner "
        "EXISTS re-bound t and the breaking WHERE was ruled out as some other "
        "table's column"
    )


def test_a_window_order_by_is_a_ranking_and_a_partition_by_is_a_dedup_key() -> None:
    statement = _one(
        "CREATE OR REPLACE TABLE ds.s AS SELECT k, "
        "ROW_NUMBER() OVER (PARTITION BY seg ORDER BY cm13 DESC) AS rn "
        "FROM ds.customer_demographics"
    )
    kinds = _kinds(usages_of(statement, "cm13", CUSTOMERS))
    assert "ranking" in kinds, (
        "a window ORDER BY is where removal is silent and awful, and it was "
        "not read: " + repr(kinds)
    )
    seg_kinds = _kinds(usages_of(statement, "seg", CUSTOMERS))
    assert "dedup_key" in seg_kinds, (
        "the PARTITION BY says what the winner wins against; take it away and "
        "one record survives for the whole table: " + repr(seg_kinds)
    )


def test_qualify_is_read() -> None:
    statement = _one(
        "CREATE OR REPLACE TABLE ds.s AS SELECT k FROM ds.customer_demographics "
        "QUALIFY ROW_NUMBER() OVER (PARTITION BY k ORDER BY loaded_at) = 1 "
        "AND cm13 = 'US'"
    )
    assert "filter" in _kinds(usages_of(statement, "cm13", CUSTOMERS)), (
        "QUALIFY is where nearly every dedup in a real pipeline is written, "
        "and the column often appears nowhere else in the statement"
    )


def test_an_updates_set_list_is_a_usage_of_its_own() -> None:
    statement = _one(
        "UPDATE ds.final_published t SET t.market = s.cm13 "
        "FROM ds.customer_demographics s WHERE t.pub_id = s.pub_id"
    )
    usages = usages_of(statement, "cm13", CUSTOMERS)
    transforms = [usage for usage in usages if usage.kind == "transform"]
    assert transforms, (
        "cm13 is named nowhere else in that statement, so the one statement "
        "that patches the published table reported nothing"
    )
    assert transforms[0].detail == "SET"


def test_a_delete_with_no_select_is_still_a_usage() -> None:
    statement = _one("DELETE FROM ds.stage_customers WHERE cm13 = 'US'")
    assert usages_of(statement, "cm13", "ds.stage_customers"), (
        "requiring a SELECT made a DELETE invisible, and the table it prunes "
        "quietly fills up instead"
    )


def test_all_four_parts_of_a_merge_are_read() -> None:
    statement = _one(
        "MERGE INTO ds.final_published t USING ds.customer_demographics s "
        "ON t.k = s.k "
        "WHEN MATCHED AND s.cm13 = 'US' THEN UPDATE SET t.market = s.cm13 "
        "WHEN NOT MATCHED THEN INSERT (k, market) VALUES (s.k, s.cm13)"
    )
    kinds = _kinds(usages_of(statement, "cm13", CUSTOMERS))
    assert "filter" in kinds, (
        "a WHEN's extra condition is often the only place the column is named "
        "in the whole statement: " + repr(kinds)
    )
    assert "select" in kinds, "the UPDATE SET value and the INSERT's VALUES were not read"
    names = output_names(statement, "cm13")
    assert "market" in names, (
        "the chain followed the source's own name past the one statement that "
        "loads the table, and walked off the end: " + repr(names)
    )


def test_a_merge_does_not_report_the_target_tables_own_column() -> None:
    statement = _one(
        "MERGE INTO ds.final_published t USING ds.customer_demographics s "
        "ON t.k = s.k WHEN MATCHED THEN UPDATE SET t.market = s.cm13"
    )
    assert usages_of(statement, "market", CUSTOMERS) == [], (
        "reading the whole assignment grows a finding about a column that "
        "never came from the source table"
    )


def test_an_insert_with_a_values_list_is_read() -> None:
    # Exactly how a loop body is written, and there is no SELECT anywhere in it.
    statement = _one("INSERT INTO ds.final_published (id, seg) VALUES (rec.id, rec.seg)")
    assert "select" in _kinds(usages_of(statement, "seg", "ds.rec")), (
        "every usage check keyed on a SELECT was skipped, so the statement "
        "that carries the loop row's field into the published table recorded "
        "no usage of anything"
    )


def test_partition_by_on_the_create_line_is_a_layout_usage_and_outranks_select() -> None:
    statement = _one(
        "CREATE OR REPLACE TABLE ds.s PARTITION BY cm13 AS "
        "SELECT cm13 FROM ds.customer_demographics"
    )
    usages = usages_of(statement, "cm13", CUSTOMERS)
    kinds = _kinds(usages)
    assert "layout" in kinds, (
        "a table partitioned by the very column being decommissioned returned "
        "no usage at all: " + repr(kinds)
    )
    assert usages[0].kind == "layout", (
        "the row heads with 'Select' and reads as a column quietly passing "
        "through, on a statement that stops compiling: " + repr(kinds)
    )
    assert label_for(usages[0]) == "Partition or cluster key"


def test_an_unpivot_names_the_column_and_silences_the_star() -> None:
    statement = _one(
        "CREATE OR REPLACE TABLE ds.s1 AS SELECT * FROM ds.customer_demographics "
        "UNPIVOT (val FOR metric IN (cm13, other_col))"
    )
    usages = usages_of(statement, "cm13", CUSTOMERS)
    kinds = _kinds(usages)
    assert "pivoted" in kinds, (
        "an UNPIVOT was read as a plain SELECT *, so the answer said 'nothing "
        "here fails on the day of the change' about a statement whose UNPIVOT "
        "list stops being valid SQL: " + repr(kinds)
    )
    assert "star" not in kinds
    pivoted = [usage for usage in usages if usage.kind == "pivoted"][0]
    assert label_for(pivoted) == "Named in UNPIVOT", (
        "PIVOT and UNPIVOT are opposite operations and the file says which"
    )


def test_a_column_named_after_a_parenless_function_is_read_back() -> None:
    statement = _one("SELECT current_date FROM ds.customer_demographics")
    assert "current_date" in statement.guessed_columns, (
        "the name parsed as a call and not as a column at all, so Ripple did "
        "not miss the column - it never saw one"
    )
    usages = usages_of(statement, "current_date", CUSTOMERS)
    assert usages, "no usage was recorded for the column reading of the name"
    assert all(not usage.certain for usage in usages), (
        "which of the two the writer meant cannot be known from the file, so "
        "no usage of it may be asserted as certain"
    )


def test_a_hole_where_the_column_list_goes_becomes_a_star() -> None:
    statement = _one(
        "CREATE OR REPLACE TABLE ds.final_published AS SELECT cols FROM ds.customer_demographics",
        holes={"cols"},
    )
    assert statement.star_note, (
        "Ripple believes the published table has exactly one column, called "
        "cols"
    )
    assert output_names(statement, "cm13") == ["cm13"], (
        "the trail did not carry on through the placeholder"
    )
    starred = [
        usage for usage in usages_of(statement, "cm13", CUSTOMERS) if usage.kind == "star"
    ]
    assert starred and label_for(starred[0]) == "Carried by a placeholder", (
        "the row claims the file writes SELECT *, and it does not"
    )


def test_a_templated_dataset_is_not_a_dataset() -> None:
    statement = _one(
        "CREATE OR REPLACE TABLE target_dataset.orders AS "
        "SELECT cm13 FROM stage.orders",
        holes={"target_dataset"},
    )
    assert statement.target == "orders", (
        "a filled-in {{target_dataset}} was recorded as a dataset called "
        "target_dataset: " + repr(statement.target)
    )
    assert any(same_table(source, "stage.orders") for source in statement.sources), (
        "the source was lost when the templated dataset was taken off the "
        "target: " + repr(statement.sources)
    )


def test_mode_of_says_transformed_only_when_something_reshapes_the_column() -> None:
    statement = _one(
        "CREATE OR REPLACE TABLE ds.s AS SELECT UPPER(cm13) AS c "
        "FROM ds.customer_demographics"
    )
    assert mode_of(usages_of(statement, "cm13", CUSTOMERS)) == "Transformed"
    plain = _one(
        "CREATE OR REPLACE TABLE ds.s AS SELECT cm13 FROM ds.customer_demographics"
    )
    assert mode_of(usages_of(plain, "cm13", CUSTOMERS)) == "Direct pull"


# --------------------------------------------------------------------------
# Names, fences and shards
# --------------------------------------------------------------------------


def test_a_wildcard_covers_the_family_but_not_a_shorter_name() -> None:
    assert same_table(
        "prj.ds.customer_demographics_*", "prj.ds.customer_demographics_20260101"
    ), "scanning a real shard matched nothing, and the scan came back clean"
    assert same_table("ds.customer_demographics_*", "ds.customer_demographics"), (
        "the family name as a person types it did not match the wildcard"
    )
    assert not same_table("ds.events_*", "ds.ev"), "the match went further than the rule"
    assert not same_table(
        "other.customer_demographics_*", "ds.customer_demographics_20260101"
    ), "the dataset stopped ruling a wildcard match out"


def test_a_partition_decorator_is_a_day_and_not_a_different_table() -> None:
    assert same_table(
        "prj.ds.customer_demographics$20260101", "prj.ds.customer_demographics"
    ), (
        "every decorated read split off from the table it belongs to, so the "
        "answer came back clean on a pipeline that writes that table every "
        "morning"
    )


def test_a_scoped_name_is_absolute_and_is_stripped_for_display() -> None:
    a_side = sqlread.fence("jobs/a.sql", "stg")
    b_side = sqlread.fence("jobs/b.sql", "stg")
    assert not same_table(a_side, b_side), (
        "two unrelated files each building their own stg were merged, which "
        "invents a chain to a published table nobody touched"
    )
    assert not same_table(a_side, "stg"), (
        "the loose 'no dataset given matches anything' rule was left on for a "
        "fenced name"
    )
    assert display_table(a_side) == "stg", (
        "a name on screen that is in no file sends somebody looking for a "
        "table that does not exist: " + display_table(a_side)
    )


def test_reads_from_ignores_a_fenced_source_for_a_bare_name() -> None:
    statement = _one("SELECT cm13 FROM ds.customer_demographics")
    statement.sources = {sqlread.fence("jobs/a.sql", "stg")}
    sqlread.forget_source_cache(statement)
    assert not reads_from(statement, "stg")
    assert reads_from(statement, sqlread.fence("jobs/a.sql", "stg"))


def test_widening_sources_clears_the_cache() -> None:
    statement = _one("SELECT cm13 FROM ds.customer_demographics")
    assert reads_from(statement, CUSTOMERS)
    statement.sources.add("ds.late_addition")
    sqlread.forget_source_cache(statement)
    assert reads_from(statement, "ds.late_addition"), (
        "the cached copy went stale, so the fence, the variable binding and "
        "the CALL edge all look as though they were never applied"
    )


def test_a_table_suffix_predicate_excludes_a_shard_it_cannot_read() -> None:
    statement = _one(
        "SELECT cm13 FROM `prj.ds.customer_demographics_*` "
        "WHERE _TABLE_SUFFIX = '20260101'"
    )
    assert (
        shard_verdict(
            statement,
            "prj.ds.customer_demographics_*",
            "prj.ds.customer_demographics_19991231",
        )
        == "excluded"
    ), (
        "a shard from 1999 this query provably never touches came back "
        "breaking and certain, contradicting the line printed under it"
    )
    assert (
        shard_verdict(
            statement,
            "prj.ds.customer_demographics_*",
            "prj.ds.customer_demographics_20260101",
        )
        == "reads"
    )


def test_a_table_suffix_predicate_it_cannot_evaluate_hedges_rather_than_drops() -> None:
    statement = _one(
        "SELECT cm13 FROM `prj.ds.customer_demographics_*` "
        "WHERE _TABLE_SUFFIX = CAST(run_day AS STRING)"
    )
    assert (
        shard_verdict(
            statement,
            "prj.ds.customer_demographics_*",
            "prj.ds.customer_demographics_19991231",
        )
        == "maybe"
    ), (
        "guessing at a predicate that cannot be read trades an over-confident "
        "answer for a missing one"
    )


def test_the_family_name_with_the_asterisk_in_it_is_never_narrowed() -> None:
    statement = _one(
        "SELECT cm13 FROM `prj.ds.customer_demographics_*` "
        "WHERE _TABLE_SUFFIX = '20260101'"
    )
    assert (
        shard_verdict(
            statement, "prj.ds.customer_demographics_*", "prj.ds.customer_demographics_*"
        )
        == "reads"
    ), "no one suffix can be tested when the person typed the asterisk"


# --------------------------------------------------------------------------
# The shapes that were invisible
# --------------------------------------------------------------------------


def test_execute_immediate_reads_the_statement_inside_the_quotes() -> None:
    sql = (
        "EXECUTE IMMEDIATE '''CREATE OR REPLACE TABLE ds.final_published AS "
        "SELECT cm13 FROM ds.customer_demographics'''"
    )
    statements, problems, _opaque = _read(sql)
    assert not problems
    assert len(statements) == 1, (
        "the CREATE inside the string was understood as nothing and produced "
        "no lineage, with the whole statement sitting in the file in plain "
        "sight"
    )
    assert same_table(statements[0].target, "ds.final_published")
    assert statements[0].built_as_text == "EXECUTE IMMEDIATE", (
        "the line the finding points at holds a string, not the CREATE the row "
        "describes, and the row has to admit it"
    )


def test_execute_immediate_refuses_a_statement_built_out_of_pieces() -> None:
    sql = "EXECUTE IMMEDIATE 'CREATE TABLE ' || env || '_mid AS SELECT 1 AS a'"
    statements, problems, _opaque = _read(sql)
    assert statements == [], (
        "the statement never exists as text anywhere, so inventing the missing "
        "piece is the exact failure this reader exists to avoid"
    )
    assert problems, "the refusal was silent instead of being reported"


def test_a_search_index_is_read_as_a_reference_and_not_as_lineage() -> None:
    text = "CREATE SEARCH INDEX idx1 ON ds.customer_demographics(cm13, other_col)\n"
    references = sqlread._references_in("jobs/a.sql", text)
    assert len(references) == 1, (
        "the whole statement was invisible, so the file landed on the "
        "check-by-hand list with nothing saying which table it was about"
    )
    assert references[0].table == "ds.customer_demographics"
    assert "cm13" in references[0].columns
    statements, problems, _opaque = _read(text)
    assert statements == [], "a reference was recorded as lineage"
    assert problems and problems[0].hint == "referenced", (
        "the statement was reported as a file nobody could understand as well "
        "as on the reference card"
    )


def test_a_call_is_kept_as_opaque_and_not_reported() -> None:
    statements, problems, opaque = _read("CALL ds.publish_it()")
    assert statements == []
    assert problems == [], (
        "every real pipeline is full of calls to procedures kept somewhere "
        "else, and one line each would bury the list"
    )
    assert len(opaque) == 1, "the call was dropped rather than kept"


def test_an_export_hangs_its_delivery_on_the_statement() -> None:
    statements, _problems, _opaque = _read(
        "SELECT cm13 FROM ds.customer_demographics",
        exports={0: "gs://feed/partner"},
    )
    assert statements[0].export_uri == "gs://feed/partner", (
        "an export builds no table, so the answer read 'no production table is "
        "affected' - true, and useless"
    )


# --------------------------------------------------------------------------
# Pointing at a line
# --------------------------------------------------------------------------


def test_locate_scores_the_lines_inside_the_statement_first() -> None:
    text = (
        "SELECT k FROM ds.orders WHERE cm13 = 'X';\n"
        "SELECT k\n"
        "FROM ds.customer_demographics\n"
        "WHERE cm13 = 'US';\n"
    )
    f = _File(path="jobs/a.sql", abs_path="/repo/jobs/a.sql", text=text, lang="sql")
    line = locate(f, "cm13", "filter", 1, 3)
    assert line == 4, (
        "an unbounded search picked the best-scoring WHERE clause in somebody "
        "else's statement about somebody else's table: line " + str(line)
    )


def test_locate_widens_to_the_whole_file_rather_than_dropping_the_finding() -> None:
    text = "SELECT k\nFROM ds.t\nWHERE cm13 = 'US'\n"
    f = _File(path="jobs/a.sql", abs_path="/repo/jobs/a.sql", text=text, lang="sql")
    assert locate(f, "cm13", "filter", 0, 1) == 3, (
        "the finding was dropped where the name only exists outside the "
        "statement's own lines"
    )


def test_snippet_marks_the_line_and_keeps_a_note_off_the_code() -> None:
    text = "one\ntwo\nthree\nfour\nfive\n"
    f = _File(path="jobs/a.sql", abs_path="/repo/jobs/a.sql", text=text, lang="sql")
    lines = snippet(f, 3, note="this line holds a quoted string")
    marked = [line for line in lines if line["hit"]]
    assert len(marked) == 1 and marked[0]["n"] == 3 and marked[0]["t"] == "three"
    assert lines[-1]["n"] == 0 and lines[-1]["t"] == "this line holds a quoted string"


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__]))
