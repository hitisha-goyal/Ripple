"""Shapes taken from photographs of the real pipeline, with the names changed.

The point of this file is that none of these were invented. Each one is
something the SQL in that repository actually does, and each one was capable of
producing a confident answer that was wrong.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ripple.config import Settings, parse_production_rule       # noqa: E402
from ripple.scanner.lineage import trace                        # noqa: E402
from ripple.scanner.repo import RepoIndex                       # noqa: E402
from ripple.scanner.sqlread import parse_repo, short_name       # noqa: E402

# Straight off the screen: an in-house helper that is handed the column name and
# the table name as quoted strings, wrapped around the column itself.
REAL_STATEMENT = """
DECLARE ret_json STRING;
BEGIN
CALL `{{tgt_project_id}}.{{foundation_dataset}}.get_table_code_params`('cmdl_account_main', ret_json);

CREATE OR REPLACE TABLE `{{tgt_project_id}}.{{stage_dataset}}.acct_demographics_data` AS (
    SELECT  cm13
    ,cm11
    ,prod_id as cshprodid
    ,substr(`{{src_project_id}}`.{{src_dataset}}.decrypt_sde(
        `{{src_project_id}}`.{{src_dataset}}.get_sde_tag('cm13', 'triumph_demographics'), cm13),1,11) as cm11_dec
    ,CASE
        WHEN gaidateeffd = '9999-12-31'
            THEN - 999
    ELSE (FLOOR(TIMESTAMP_DIFF(CURRENT_DATE(),gaidateeffd, DAY)/30.4375))
        END AS acct_tenure
    ,TRIM(cshcardhacctno) AS cshcardhacctno
    FROM {{tgt_project_id}}.{{foundation_dataset}}.triumph_demographics
    WHERE SUBSTR(cm13, 12, 2) = '00'
);
EXCEPTION WHEN ERROR THEN
  RAISE USING MESSAGE = @@error.message;
END;
"""


def _repo(tmp_path: Path, text: str = REAL_STATEMENT, production: str = "_data"):
    p = tmp_path / "src/sql/DML/transform/cmdl_TL_acct_data_entity_umdl.sql"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    cfg = Settings()
    cfg.sql_dialect = "bigquery"
    cfg.repo_path = tmp_path
    cfg.production_patterns = parse_production_rule(production)
    idx = RepoIndex.build(tmp_path, cfg)
    return cfg, idx, parse_repo(idx, cfg)


def test_the_whole_statement_is_read(tmp_path):
    """Leading commas, a parenthesised CTAS body, a CASE down the page, a helper
    call qualified by a backticked dataset, and the scripting frame around all
    of it. Any one of these refusing costs the file."""
    _, _, parsed = _repo(tmp_path)
    assert "acct_demographics_data" in {short_name(s.target) for s in parsed.statements}
    assert parsed.unreadable == []


def test_a_dataset_path_in_front_of_a_function_is_not_a_table(tmp_path):
    """`proj.dataset`.decrypt_sde(...) is a call, not a read. Counting the path
    as a table would put a table on the dependency map that does not exist and
    that nobody could go and look at."""
    _, _, parsed = _repo(tmp_path)
    stmt = next(s for s in parsed.statements if short_name(s.target) == "acct_demographics_data")
    assert {short_name(x).lower() for x in stmt.sources} == {"triumph_demographics"}


def test_the_column_named_as_text_is_reported_even_though_the_file_has_findings(tmp_path):
    """The one that would have cost him.

    That line uses cm13 twice: once as a column, which Ripple reports, and once
    as the string 'cm13' handed to an in-house helper, which no parser can see
    as anything but text. The file was skipped for the second check because it
    already had findings -- so the only thing on screen was the column. Fix
    that, ship, and the helper carries on asking for a name that has gone.
    """
    cfg, idx, parsed = _repo(tmp_path)
    out = trace(idx, parsed, [{"table": "triumph_demographics", "attrs": ["cm13"]}],
                change_type="rename", cfg=cfg).to_dict()

    assert sum(len(g["rows"]) for g in out["groups"]) >= 1, "the column usage is still reported"
    flagged = [u for u in out["unreadable"] if "ALSO written as text" in u["reason"]]
    assert len(flagged) == 1, "and so is the one written as text"
    assert "cm13" in flagged[0]["reason"]
    assert "does not fix this one" in flagged[0]["hint"]
    assert flagged[0]["line"] > 1, "it has to say which line to open the file at"


def test_a_file_with_no_name_written_as_text_is_not_flagged(tmp_path):
    """The opposite failure: a note on every file that has a finding would be
    noise, and noise is how the real one gets missed."""
    cfg, idx, parsed = _repo(tmp_path, text="""
        CREATE OR REPLACE TABLE `{{p}}.{{d}}.acct_demographics_data` AS
        SELECT cm13, cm11 FROM `{{p}}.{{d}}.triumph_demographics` WHERE cm13 IS NOT NULL;
    """)
    out = trace(idx, parsed, [{"table": "triumph_demographics", "attrs": ["cm13"]}],
                change_type="rename", cfg=cfg).to_dict()
    assert sum(len(g["rows"]) for g in out["groups"]) >= 1
    assert [u for u in out["unreadable"] if "ALSO written as text" in u["reason"]] == []
