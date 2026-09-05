"""Reading the SQL a real pipeline is actually written in.

Almost nothing in a production repository is plain SQL. The project and dataset
names are placeholders filled in by Airflow, dbt or an in-house generator before
a database ever sees the file. A parser refuses those outright, so an entire
repository comes back "could not be read" -- and a scan over a repository that
was never read reports no impact, confidently, on a change that breaks things.

That is the worst failure this tool has, so the shapes that caused it are
pinned here: the templating, one bad statement taking a whole file down with it,
and a chain that ends somewhere the production naming rule does not match.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ripple import narrative                                    # noqa: E402
from ripple.catalog import build_catalog                        # noqa: E402
from ripple.config import Settings, parse_production_rule       # noqa: E402
from ripple.scanner.lineage import trace                        # noqa: E402
from ripple.scanner.repo import RepoIndex                       # noqa: E402
from ripple.scanner.sqlread import parse_repo, short_name, split_statements       # noqa: E402
from ripple.scanner.templating import fill_placeholders         # noqa: E402

# The shape of the office repository this was reported from: Airflow-templated
# BigQuery, tables named _umdl and _gdi, and not one of them named _prod.
FILES = {
    "src/sql/DML/transform/cmdl_TL_web_activity_umdl.sql": """
        SET operation_time = PARSE_TIMESTAMP("%Y-%m-%dT%H:%M:%S", CURRENT_TIMESTAMP());

        --pub Guid AND pvt guid
        CREATE OR REPLACE TABLE {{tgt_project_id}}.{{stage_dataset}}.myca_web_activity AS
        SELECT LOWER(user_pvt_guid) AS user_pvt_guid,
               LOWER(pub_guid)      AS pub_guid,
               MAX(creat_ts)        AS creat_ts
        FROM {{src_project_id}}.{{src_anon_dataset}}.myca_mobile_web_logon_activity
        WHERE TRIM(logon_sta_cd) = '0'
          AND TRIM(UPPER(pub_guid)) <> 'BLUEBOXPUBLIC'
        GROUP BY LOWER(user_pvt_guid), LOWER(pub_guid);

        CREATE OR REPLACE TABLE {{tgt_project_id}}.{{stage_dataset}}.card_pub_pvt_guid_umdl AS
        SELECT w.pub_guid, w.creat_ts
        FROM {{tgt_project_id}}.{{stage_dataset}}.myca_web_activity w
        WHERE w.pub_guid IS NOT NULL;
    """,
    "src/dag/transformation/gdi/cmdl_transaction_billed_gdi.py": '''
BILLED_SQL = """
CREATE OR REPLACE TABLE {{ params.tgt }}.{dataset}.transaction_billed_gdi AS
SELECT c.pub_guid, t.bill_amt
FROM {{ params.src }}.raw.card_pub_pvt_guid_umdl AS c
JOIN {{ params.src }}.raw.txn AS t ON t.pub_guid = c.pub_guid
"""
''',
    "src/sql/DML/common/cmdl_get_last_lumi_source_creation_time.sql": """
        CREATE OR REPLACE TABLE {{p}}.{{d}}.first_one AS
        SELECT pub_guid FROM {{p}}.{{d}}.myca_web_activity;

        THIS LINE IS NOT SQL AND NEVER WAS @@@ ;

        CREATE OR REPLACE TABLE {{p}}.{{d}}.last_one AS
        SELECT pub_guid FROM {{p}}.{{d}}.myca_web_activity;
    """,
}


def build(tmp_path: Path, dialect: str = "bigquery", production: str = "") -> tuple:
    for rel, text in FILES.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    cfg = Settings()
    cfg.sql_dialect = dialect
    cfg.repo_path = tmp_path
    if production:
        cfg.production_patterns = parse_production_rule(production)
    idx = RepoIndex.build(tmp_path, cfg)
    parsed = parse_repo(idx, cfg)
    return cfg, idx, parsed


def scan(tmp_path: Path, production: str = "") -> dict:
    cfg, idx, parsed = build(tmp_path, production=production)
    return trace(idx, parsed,
                 [{"table": "myca_mobile_web_logon_activity", "attrs": ["pub_guid"]}],
                 change_type="value_change", cfg=cfg).to_dict()


# ── filling the placeholders in ────────────────────────────────────────────
def test_a_templated_table_name_still_names_the_table():
    """{{project}}.{{dataset}}.orders is the orders table, and always was."""
    out = fill_placeholders("SELECT * FROM {{tgt_project_id}}.{{stage_dataset}}.orders")
    assert out == "SELECT * FROM tgt_project_id.stage_dataset.orders"


def test_line_numbers_do_not_move():
    """Findings point at a line of the real file, so a replacement must never
    swallow a line break -- a finding on the wrong line is worse than none."""
    sql = "SELECT 1\n{% if params.full %}\nWHERE {{ x }} = 1\n{% endif %}\n"
    assert fill_placeholders(sql).count("\n") == sql.count("\n")


def test_dbt_ref_names_the_model_it_refers_to():
    assert fill_placeholders("SELECT * FROM {{ ref('orders') }}") == "SELECT * FROM orders"
    assert fill_placeholders("FROM {{ source('raw', 'orders') }}") == "FROM orders"


def test_a_regular_expression_is_left_alone():
    """{3} in a pattern is a quantifier, not a placeholder."""
    sql = r"SELECT REGEXP_CONTAINS(x, r'\d{3}') FROM t"
    assert fill_placeholders(sql) == sql


def test_a_templated_repository_is_read(tmp_path):
    _, _, parsed = build(tmp_path)
    targets = {short_name(s.target) for s in parsed.statements}
    assert {"myca_web_activity", "card_pub_pvt_guid_umdl", "transaction_billed_gdi"} <= targets
    cat = build_catalog(parsed)
    assert "MYCA_WEB_ACTIVITY" in cat.tables


# ── one bad statement is one bad statement ─────────────────────────────────
def test_one_unreadable_statement_does_not_lose_the_whole_file(tmp_path):
    _, _, parsed = build(tmp_path)
    targets = {short_name(s.target) for s in parsed.statements}
    assert {"first_one", "last_one"} <= targets, "the statements either side survived"


def test_the_gap_says_which_line_and_shows_it(tmp_path):
    """This list exists so somebody goes and checks those files. "ParseError"
    sends them hunting; a line number and the line itself does not."""
    _, _, parsed = build(tmp_path)
    gap = next(u for u in parsed.unreadable if "lumi" in u["file"])
    assert gap["line"] == 5
    assert "NOT SQL" in gap["snippet"]
    assert "1 of 3 statements" in gap["reason"]


def test_semicolons_inside_quotes_do_not_split_a_statement():
    parts = split_statements("SELECT ';' AS a FROM t; SELECT 2;")
    assert len(parts) == 2


def test_a_semicolon_in_a_comment_does_not_split_a_statement():
    parts = split_statements("SELECT 1 -- a; comment\nFROM t;\nSELECT 2;")
    assert len(parts) == 2


# ── a chain that reaches no _PROD table is still a chain ───────────────────
def test_findings_are_reported_even_when_nothing_matches_the_production_rule(tmp_path):
    """The report that started all of this: three real, breaking usages shown
    as a clean result, purely because no table in the repository is named
    _PROD. Nothing may be hidden behind the naming rule."""
    out = scan(tmp_path)
    assert out["groups"] == [], "nothing here is named _PROD"
    assert out["reached"], "but the change plainly reaches tables, and they must be listed"
    assert out["risk"] != "none"
    assert out["stats"]["tablesReached"] >= 1


def test_correcting_the_rule_turns_them_into_production_tables(tmp_path):
    out = scan(tmp_path, production="_UMDL, _GDI")
    assert {g["prod"] for g in out["groups"]} == {"card_pub_pvt_guid_umdl",
                                                  "transaction_billed_gdi"}
    assert out["stats"]["productionTables"] == 2
    # Worst first: the table with the most impacts heads the page.
    counts = [len(g["rows"]) for g in out["groups"]]
    assert counts == sorted(counts, reverse=True)


def test_the_summary_does_not_say_no_impact_over_a_list_of_findings(tmp_path):
    """This wording is forwarded to the upstream team in writing."""
    out = scan(tmp_path)
    vals = {"upstream": [{"table": "myca_mobile_web_logon_activity", "attrs": ["pub_guid"]}]}
    s = narrative.summarise(out, vals)
    r = narrative.draft_reply(out, {**vals, "pocName": "Priya Raman"}, s)
    assert "no impact" not in s["headline"].lower()
    assert "no impact" not in r["body"].lower()
    assert "no impact" not in r["subject"].lower()


def test_a_genuinely_clean_result_still_says_no_impact(tmp_path):
    """The honest half of the same rule: nothing found really is nothing.

    "Genuinely" is doing work here. Every file has to have been read as well as
    found - see the test below, which is the same repository with one file left
    on the "check by hand" list.
    """
    cfg, idx, parsed = build(tmp_path)
    out = trace(idx, parsed, [{"table": "nowhere", "attrs": ["not_a_column"]}],
                change_type="removal", cfg=cfg).to_dict()
    assert out["groups"] == [] and out["reached"] == [] and out["other"] == []
    out["unreadable"] = []
    out["stats"]["couldNotRead"] = 0
    s = narrative.summarise(out, {"upstream": []})
    assert "No impact" in s["headline"]
    r = narrative.draft_reply(out, {"upstream": [], "pocName": "Priya Raman"}, s)
    assert "No impact" in r["body"]


def test_no_impact_is_never_claimed_over_files_that_could_not_be_read(tmp_path):
    """The headline and the letter are quoted in meetings and forwarded to the
    upstream team. Neither may say "no impact, proceed as planned" about a
    repository Ripple only managed to read part of."""
    cfg, idx, parsed = build(tmp_path)
    out = trace(idx, parsed, [{"table": "nowhere", "attrs": ["not_a_column"]}],
                change_type="removal", cfg=cfg).to_dict()
    assert out["unreadable"], "this repository has a file that cannot be followed"
    s = narrative.summarise(out, {"upstream": []})
    r = narrative.draft_reply(out, {"upstream": [], "pocName": "Priya Raman"}, s)
    assert "No impact" not in s["headline"]
    assert "could not be" in s["headline"]
    assert "proceed as planned" not in r["body"]
    assert "checked by hand" in r["body"]


def test_nothing_scanned_is_never_reported_as_no_impact(tmp_path):
    """An empty folder produces a scan with nothing in it, and "no impact" over
    nothing at all is a statement about an empty folder, not about a pipeline."""
    empty = {"groups": [], "reached": [], "other": [], "unreadable": [],
             "filesScanned": 0, "filesMatched": 0, "stats": {}}
    s = narrative.summarise(empty, {"upstream": []})
    r = narrative.draft_reply(empty, {"upstream": [], "pocName": "Priya Raman"}, s)
    assert "no impact" not in s["headline"].lower()
    assert "Nothing was scanned" in s["headline"]
    assert "no impact" not in r["body"].lower()


# ── the answer to "how do I check this?" ───────────────────────────────────
def test_every_attribute_reports_what_came_back(tmp_path):
    cfg, idx, parsed = build(tmp_path)
    out = trace(idx, parsed,
                [{"table": "myca_mobile_web_logon_activity",
                  "attrs": ["pub_guid", "attribute_that_is_not_there"]}],
                change_type="value_change", cfg=cfg).to_dict()
    by_attr = {a["attr"]: a for a in out["attributes"]}
    assert by_attr["pub_guid"]["found"] > 0
    assert by_attr["pub_guid"]["mentionedIn"] > 0
    missing = by_attr["attribute_that_is_not_there"]
    assert missing["found"] == 0 and missing["mentionedIn"] == 0


def test_attributes_impacted_counts_what_was_confirmed(tmp_path):
    """The card says "of those you confirmed", so a column renamed twice on the
    way down is one attribute, not three."""
    out = scan(tmp_path)
    assert out["stats"]["attributesImpacted"] == 1


# ── the production rule itself ─────────────────────────────────────────────
@pytest.mark.parametrize("rule,table,expected", [
    ("_PROD", "sales_prod", True),
    ("_PROD", "sales_umdl", False),
    ("_UMDL, _GDI", "card_pub_pvt_guid_umdl", True),
    ("_UMDL, _GDI", "transaction_billed_gdi", True),
    ("PROD_*", "prod_sales", True),
    ("PROD_*", "sales_prod", False),
    ("*", "anything_at_all", True),
    ("CUSTOMER_PROFILE_PROD", "customer_profile_prod", True),
])
def test_the_production_rule_matches_the_way_it_is_described(rule, table, expected):
    cfg = Settings()
    cfg.production_patterns = parse_production_rule(rule)
    assert cfg.is_production_table(table) is expected


# ── the shapes real pipeline code is written in ────────────────────────────
# Everything below came from reading actual files from the pipeline this tool
# is for. Each one used to produce a quiet, confident nothing.
def _repo(tmp_path: Path, files: dict, production: str = "") -> tuple:
    for rel, text in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    cfg = Settings()
    cfg.sql_dialect = "bigquery"
    cfg.repo_path = tmp_path
    if production:
        cfg.production_patterns = parse_production_rule(production)
    idx = RepoIndex.build(tmp_path, cfg)
    return cfg, idx, parse_repo(idx, cfg)


@pytest.mark.parametrize("sql,expected", [
    # The whole three-part name inside one pair of backticks -- the commonest
    # shape of all, and the one that would have broken every single chain.
    ("SELECT a FROM `{{p}}.{{d}}.usmr_cm_status` x", "usmr_cm_status"),
    ("SELECT a FROM `{{p}}`.{{d}}.promo_synch_up_data t", "promo_synch_up_data"),
    ("SELECT a FROM `{{p}}.{{d}}`.medulla_product_detail AS pt", "medulla_product_detail"),
    ("SELECT a FROM {{p}}.{{d}}.web_activity w", "web_activity"),
])
def test_every_way_the_name_is_written_still_names_the_table(sql, expected):
    got = sqlglot_tables(fill_placeholders(sql))
    assert expected in got


def sqlglot_tables(sql: str) -> set[str]:
    import sqlglot
    from sqlglot import exp
    return {t.name for s in sqlglot.parse(sql, read="bigquery") if s
            for t in s.find_all(exp.Table)}


def test_begin_does_not_swallow_the_statement_after_it(tmp_path):
    """The quietest failure this reader had.

    BEGIN has no semicolon of its own, so a SQL parser that does not know the
    keyword takes the statement after it as part of the same thing -- and hands
    back one blob it cannot read. Nothing errors. The file "parses". The FIRST
    REAL STATEMENT OF THE FILE is simply gone, and in a repository where every
    file opens with BEGIN, that is most of the lineage in it.
    """
    _, _, parsed = _repo(tmp_path, {"job.sql": """
        DECLARE run_dt DATE;
        BEGIN
          CREATE OR REPLACE TABLE `{{p}}.{{d}}.first_thing` AS
          SELECT market_code FROM `{{p}}.{{d}}.customer_demographics`;

          CREATE OR REPLACE TABLE `{{p}}.{{d}}.second_thing` AS
          SELECT market_code FROM `{{p}}.{{d}}.first_thing`;
        END;
    """})
    assert {short_name(s.target) for s in parsed.statements} >= {"first_thing", "second_thing"}
    first = next(s for s in parsed.statements if short_name(s.target) == "first_thing")
    assert {short_name(x).lower() for x in first.sources} == {"customer_demographics"}


@pytest.mark.parametrize("opener", [
    "BEGIN", "BEGIN TRANSACTION", "IF x IS NULL THEN", "ELSE", "EXCEPTION WHEN ERROR THEN",
])
def test_no_scripting_keyword_swallows_the_next_statement(tmp_path, opener):
    _, _, parsed = _repo(tmp_path, {"job.sql": f"""
        DECLARE x STRING;
        {opener}
          CREATE OR REPLACE TABLE `{{{{p}}}}.{{{{d}}}}.made_here` AS
          SELECT market_code FROM `{{{{p}}}}.{{{{d}}}}.customer_demographics`;
        END;
    """})
    assert "made_here" in {short_name(s.target) for s in parsed.statements}, opener


def test_a_loop_still_shows_the_table_it_loops_over(tmp_path):
    """The loop itself cannot be followed, but the query in its header is an
    ordinary read of an ordinary table, and dropping the whole line lost it."""
    _, _, parsed = _repo(tmp_path, {"loop.sql": """
        BEGIN
          FOR tbl IN (SELECT table_name FROM `{{p}}.{{d}}.sor_mapping`) DO
            EXECUTE IMMEDIATE v_sql;
          END FOR;
        END;
    """})
    assert any("sor_mapping" in {short_name(x).lower() for x in s.sources} for s in parsed.statements)


def test_a_case_written_across_lines_survives_the_scripting_stripper(tmp_path):
    """The fix for BEGIN was quietly breaking real statements.

    ELSE and a bare END are scripting keywords. They are also how anybody writes
    a CASE expression down the page. Cutting those two lines out put a semicolon
    in the middle of a CASE, so the whole CREATE TABLE around it was refused --
    and in this pipeline that is a 600-line statement, with every table and every
    column in it, gone. Reported on screen as a file to "check by hand", which
    reads like a small thing and is not.
    """
    _, _, parsed = _repo(tmp_path, {"job.sql": """
        BEGIN
          CREATE OR REPLACE TABLE `{{tgt}}.{{stage}}.card_demographics` AS
          SELECT
            cm13,
            CASE
              WHEN status = 'A' THEN 'Active'
              WHEN status = 'C' THEN 'Closed'
              ELSE
                'Unknown'
            END
              AS status_desc
          FROM `{{src}}.{{raw}}.account_main`;
        EXCEPTION WHEN ERROR THEN
          RAISE USING MESSAGE = @@error.message;
        END;
    """})
    assert "card_demographics" in {short_name(s.target) for s in parsed.statements}
    assert any("account_main" in {short_name(x).lower() for x in s.sources} for s in parsed.statements)
    assert parsed.unreadable == []


def test_raise_does_not_put_the_whole_file_on_the_check_by_hand_list(tmp_path):
    """Every generated file in this pipeline ends with the same two lines, and a
    parser refuses both. One unreadable line is enough to list the file -- so the
    honest "check these by hand" list filled up with hundreds of files where
    there is nothing to check, and a list that long is a list nobody opens."""
    _, _, parsed = _repo(tmp_path, {"job.sql": """
        BEGIN
          CREATE OR REPLACE TABLE `{{tgt}}.{{stage}}.enrollment` AS
          SELECT cm11 FROM `{{src}}.{{raw}}.enrollment_src`;
        EXCEPTION WHEN ERROR THEN
          RAISE USING MESSAGE = @@error.message;
        END;
    """})
    assert "enrollment" in {short_name(s.target) for s in parsed.statements}
    assert parsed.unreadable == []


@pytest.mark.parametrize("raise_line", [
    "RAISE USING MESSAGE = @@error.message;",
    'RAISE USING MESSAGE = "No latest cstone_feed_key data to be processed";',
    "RAISE USING MESSAGE = msg;",
    "RAISE;",
])
def test_every_shape_of_raise_seen_in_the_real_repository(tmp_path, raise_line):
    _, _, parsed = _repo(tmp_path, {"job.sql": f"""
        BEGIN
          CREATE OR REPLACE TABLE `{{{{t}}}}.{{{{s}}}}.made_here` AS
          SELECT cm13 FROM `{{{{t}}}}.{{{{s}}}}.source_table`;
        EXCEPTION WHEN ERROR THEN
          {raise_line}
        END;
    """})
    assert "made_here" in {short_name(s.target) for s in parsed.statements}, raise_line
    assert parsed.unreadable == [], raise_line


def test_a_procedure_signature_does_not_cost_the_body(tmp_path):
    """No SQL parser reads a procedure signature, and there is nothing in one to
    read. The BEGIN ... END body underneath it is ordinary SQL, and that is where
    the tables are."""
    _, _, parsed = _repo(tmp_path, {"proc.sql": """
        CREATE OR REPLACE PROCEDURE `{{p}}.foundation.get_last_source_time`(
          IN tbl_name STRING,
          OUT last_ts TIMESTAMP)
        BEGIN
          CREATE OR REPLACE TABLE `{{p}}.{{d}}.load_status` AS
          SELECT MAX(creat_ts) AS creat_ts FROM `{{p}}.{{d}}.sor_load_audit`;
        END;
    """})
    assert "load_status" in {short_name(s.target) for s in parsed.statements}
    assert any("sor_load_audit" in {short_name(x).lower() for x in s.sources} for s in parsed.statements)
    assert parsed.unreadable == []


def test_a_loop_header_written_across_lines_still_names_its_table(tmp_path):
    """Same loop as above with the DO on its own line, which is how it is
    actually written in the file this came from."""
    _, _, parsed = _repo(tmp_path, {"loop.sql": """
        BEGIN
          FOR tbl IN
          (
            SELECT table_name FROM `{{p}}.{{d}}.sor_mapping`
          )
          DO
            EXECUTE IMMEDIATE v_sql;
          END FOR;
        END;
    """})
    assert any("sor_mapping" in {short_name(x).lower() for x in s.sources} for s in parsed.statements)


def test_a_scripting_word_inside_a_string_is_not_scripting(tmp_path):
    """A 600-line statement is exactly where a stray 'END' inside a quoted string
    turns up, and cutting that line would break the statement holding it."""
    _, _, parsed = _repo(tmp_path, {"job.sql": """
        BEGIN
          CREATE OR REPLACE TABLE `{{t}}.{{s}}.notes` AS
          SELECT cm13, '''
        ELSE
        END
        ''' AS note
          FROM `{{t}}.{{s}}.note_source`;
        END;
    """})
    assert "notes" in {short_name(s.target) for s in parsed.statements}
    assert any("note_source" in {short_name(x).lower() for x in s.sources} for s in parsed.statements)


def test_a_scripting_block_does_not_hide_the_statements_inside_it(tmp_path):
    """Every file in this pipeline is wrapped in DECLARE ... BEGIN ... END, with
    the real work inside. If the block swallowed its contents, Ripple would read
    the file happily and learn nothing at all from it."""
    _, _, parsed = _repo(tmp_path, {"job.sql": """
        DECLARE operation_str STRING;
        BEGIN
          SET operation_str = FORMAT_TIMESTAMP("%Y-%m-%d", CURRENT_TIMESTAMP());
          CREATE OR REPLACE TABLE `{{tgt}}.{{stage}}.web_activity` AS
          SELECT pub_guid FROM `{{src}}.{{anon}}.logon_activity`;
        EXCEPTION WHEN ERROR THEN
          SET msg = @@error.message;
        END;
    """})
    reading = {short_name(s.target) for s in parsed.statements}
    assert "web_activity" in reading
    assert any("logon_activity" in {short_name(x).lower() for x in s.sources} for s in parsed.statements)


def test_a_delete_that_filters_on_the_column_is_a_finding(tmp_path):
    """It builds nothing, so it looks uninteresting. But the day the column goes
    the DELETE fails, the pruning silently stops, and the table fills up."""
    cfg, idx, parsed = _repo(tmp_path, {"prune.sql": """
        CREATE OR REPLACE TABLE `{{p}}.{{d}}.stage_tbl` AS
        SELECT market_code FROM `{{p}}.{{d}}.customer_demographics`;
        DELETE FROM `{{p}}.{{d}}.stage_tbl` WHERE market_code = 'US';
    """})
    out = trace(idx, parsed, [{"table": "customer_demographics", "attrs": ["market_code"]}],
                change_type="removal", cfg=cfg).to_dict()
    rows = [r for g in out["reached"] + out["groups"] for r in g["rows"]] + out["other"]
    assert any(r["logic"] == "Filter" for r in rows), "the DELETE's WHERE clause must be seen"


def test_an_update_that_filters_on_the_column_is_a_finding(tmp_path):
    cfg, idx, parsed = _repo(tmp_path, {"fix.sql": """
        CREATE OR REPLACE TABLE `{{p}}.{{d}}.stage_tbl` AS
        SELECT market_code, cust_id FROM `{{p}}.{{d}}.customer_demographics`;
        UPDATE `{{p}}.{{d}}.stage_tbl` SET cust_id = 0 WHERE market_code IS NULL;
    """})
    out = trace(idx, parsed, [{"table": "customer_demographics", "attrs": ["market_code"]}],
                change_type="removal", cfg=cfg).to_dict()
    rows = [r for g in out["reached"] + out["groups"] for r in g["rows"]] + out["other"]
    assert any(r["logic"] == "Filter" for r in rows)


def test_a_name_written_as_text_inside_a_call_is_not_called_harmless(tmp_path):
    """In-house helpers take the column and the table as quoted strings. No
    parser turns that back into lineage -- but filing it under "mentions the
    name but carries it nowhere" reads as a reassurance, and this is the one
    place somebody genuinely has to go and look."""
    cfg, idx, parsed = _repo(tmp_path, {"tags.sql": """
        DECLARE cm11_tag STRING;
        BEGIN
          SET cm11_tag = `{{src}}`.{{d}}.get_sde_tag('home_phone_no','customer_demographics');
          CREATE OR REPLACE TABLE `{{p}}.{{d}}.unrelated` AS SELECT 1 AS x;
        END;
    """})
    out = trace(idx, parsed, [{"table": "customer_demographics", "attrs": ["home_phone_no"]}],
                change_type="removal", cfg=cfg).to_dict()
    gap = next(u for u in out["unreadable"] if "tags.sql" in u["file"])
    assert "appears as text" in gap["reason"] and "home_phone_no" in gap["reason"]
    assert gap["line"] == 4 and "get_sde_tag" in gap["snippet"]
    assert not out["mentionsOnly"], "it must not also sit in the reassuring list"


def test_sql_built_as_text_and_run_later_is_flagged_with_its_line(tmp_path):
    cfg, idx, parsed = _repo(tmp_path, {"refresh.sql": """
        DECLARE v_sql STRING;
        BEGIN
          FOR tbl IN (SELECT table_name FROM `{{p}}.{{d}}.sor_mapping`) DO
            SET v_sql = FORMAT(\"\"\"INSERT INTO %s SELECT market_code FROM %s\"\"\", a, b);
            EXECUTE IMMEDIATE v_sql;
          END FOR;
        END;
    """})
    out = trace(idx, parsed, [{"table": "customer_demographics", "attrs": ["market_code"]}],
                change_type="removal", cfg=cfg).to_dict()
    gap = next(u for u in out["unreadable"] if "refresh.sql" in u["file"])
    # The whole query lives inside one quoted string, so that is what it is
    # reported as -- more specific than "somewhere I cannot follow", and it
    # points at the line the query is written on.
    assert "appears as text" in gap["reason"]
    assert gap["line"] == 5 and "FORMAT" in gap["snippet"]


def test_a_file_that_only_writes_the_name_in_a_comment_stays_reassuring(tmp_path):
    """The other half of the same rule. If everything became "check by hand",
    the list would be ignored within a week."""
    cfg, idx, parsed = _repo(tmp_path, {"other.sql": """
        -- market_code is not loaded here
        CREATE OR REPLACE TABLE `{{p}}.{{d}}.unrelated` AS
        SELECT cust_id FROM `{{p}}.{{d}}.something_else`;
    """})
    out = trace(idx, parsed, [{"table": "customer_demographics", "attrs": ["market_code"]}],
                change_type="removal", cfg=cfg).to_dict()
    assert [m["file"] for m in out["mentionsOnly"]] == ["other.sql"]
    assert not out["unreadable"]


def test_a_cte_is_not_reported_as_a_table(tmp_path):
    """A name defined by WITH is a name for a query. Treating it as a table
    invents a link between two files that have nothing to do with each other."""
    _, _, parsed = _repo(tmp_path, {"cte.sql": """
        CREATE OR REPLACE TABLE `{{p}}.{{d}}.out_tbl` AS (
          WITH cardmember_raw AS (
            SELECT cm_num FROM `{{src}}.{{anon}}.cm_status`
          )
          SELECT cm_num FROM cardmember_raw
        );
    """})
    stmt = next(s for s in parsed.statements if short_name(s.target) == "out_tbl")
    assert {short_name(x).lower() for x in stmt.sources} == {"cm_status"}


def test_an_empty_rule_is_not_read_as_every_table_being_safe():
    """An empty list would make is_production_table always false, which reports
    every repository in the world as clean."""
    assert parse_production_rule("  ,  , ") == ()
    cfg = Settings()
    cfg.set_production("")
    assert cfg.has_production() is False, \
        "an unset list must be refusable, never quietly matched against"
