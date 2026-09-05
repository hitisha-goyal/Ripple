"""Following a column by name, in a warehouse where names repeat everywhere.

In his repository ``cm13``, ``cm11`` and ``pub_guid`` are columns in nearly
every table. That breaks two assumptions this reader used to make, and both of
them produced a confident answer that was wrong:

* A column leaves a statement under exactly one name. It does not -- reshaping
  it into one column and passing it through unchanged as another, in the same
  SELECT, is everyday SQL. Following only the first of the two stopped the chain
  one table short of the published table that reads the other, and reported no
  production impact for a change that plainly had some.

* A column called ``cm13`` in a statement is this table's ``cm13``. When the
  same name is on both sides of nearly every join, it very often is not, and a
  filter on the other table's copy was reported as a usage of this one.

Neither is fixed by hiding anything. The first is a chain that was too short;
the second is read off the SQL where the SQL says so, and marked where it does
not.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ripple.config import Settings, parse_production_rule       # noqa: E402
from ripple.scanner.lineage import trace                        # noqa: E402
from ripple.scanner.repo import RepoIndex                       # noqa: E402
from ripple.scanner.sqlread import output_names, parse_repo, short_name, usages_of       # noqa: E402


def _repo(tmp_path: Path, files: dict, production: str = "_published"):
    for rel, text in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    cfg = Settings()
    cfg.sql_dialect = "bigquery"
    cfg.repo_path = tmp_path
    cfg.production_patterns = parse_production_rule(production)
    idx = RepoIndex.build(tmp_path, cfg)
    return cfg, idx, parse_repo(idx, cfg)


# ── a column can leave under more than one name ────────────────────────────
def test_a_column_reshaped_and_passed_through_keeps_both_names(tmp_path):
    _, _, parsed = _repo(tmp_path, {"a.sql": """
        CREATE OR REPLACE TABLE stage_one AS
        SELECT CAST(cm13 AS STRING) AS cm13_str,
               cm13
        FROM customer_demographics;
    """})
    stmt = next(s for s in parsed.statements if short_name(s.target) == "stage_one")
    names = [n.lower() for n in output_names(stmt, "cm13")]
    assert "cm13" in names and "cm13_str" in names
    # The one carried through unchanged comes first, so it survives the cap and
    # is the one shown on screen.
    assert names[0] == "cm13"


def test_the_chain_does_not_stop_at_the_reshaped_copy(tmp_path):
    """The whole point. The published table reads cm13, not cm13_str, and
    following only the reshaped name reported no production impact."""
    cfg, idx, parsed = _repo(tmp_path, {
        "a.sql": """
            CREATE OR REPLACE TABLE stage_one AS
            SELECT CAST(cm13 AS STRING) AS cm13_str, cm13, market_code
            FROM customer_demographics;
        """,
        "b.sql": """
            CREATE OR REPLACE TABLE final_published AS
            SELECT cm13, market_code FROM stage_one WHERE cm13 IS NOT NULL;
        """,
    })
    res = trace(idx, parsed, [{"table": "customer_demographics", "attrs": ["cm13"]}],
                change_type="removal", cfg=cfg)
    assert [g["prod"] for g in res.to_dict()["groups"]] == ["final_published"]


def test_a_statement_with_very_many_derived_columns_stays_bounded(tmp_path):
    """A generated statement can publish one column under a hundred names. The
    cap is here so one scan cannot turn into a search of the whole warehouse;
    it is set far above anything hand-written."""
    derived = ",\n".join(f"CAST(cm13 AS STRING) AS cm13_v{n}" for n in range(80))
    _, _, parsed = _repo(tmp_path, {"a.sql": f"""
        CREATE OR REPLACE TABLE stage_wide AS
        SELECT cm13,
        {derived}
        FROM customer_demographics;
    """})
    stmt = next(s for s in parsed.statements if short_name(s.target) == "stage_wide")
    names = output_names(stmt, "cm13")
    assert len(names) <= 6
    assert names[0].lower() == "cm13"


# ── which table the column came from ───────────────────────────────────────
JOIN_SQL = """
CREATE OR REPLACE TABLE stage_joined_published AS
SELECT a.cm13, d.market_code
FROM account_main a
JOIN customer_demographics d ON d.market_code = a.market_code
WHERE a.cm13 IS NOT NULL;
"""


def test_a_qualified_column_belongs_to_the_table_it_names(tmp_path):
    cfg, idx, parsed = _repo(tmp_path, {"join.sql": JOIN_SQL})
    got = trace(idx, parsed, [{"table": "account_main", "attrs": ["cm13"]}],
                change_type="removal", cfg=cfg).to_dict()
    assert got["stats"]["productionTables"] == 1


def test_the_other_tables_column_is_not_this_tables_finding(tmp_path):
    """customer_demographics has no cm13 anywhere in that statement. Reporting
    one was a finding about the wrong table -- and with cm13 on both sides of
    nearly every join in this repository, that is the ordinary case."""
    cfg, idx, parsed = _repo(tmp_path, {"join.sql": JOIN_SQL})
    got = trace(idx, parsed, [{"table": "customer_demographics", "attrs": ["cm13"]}],
                change_type="removal", cfg=cfg).to_dict()
    assert got["stats"]["productionTables"] == 0
    assert sum(len(g["rows"]) for g in got["groups"]) == 0
    assert got["other"] == []


def test_an_unqualified_column_is_kept_and_marked_never_dropped(tmp_path):
    """The SQL has not said which table it is. Both answers are guesses, and
    dropping it would be the worse guess -- so it is reported, and the screen
    is told the table is inferred rather than read."""
    cfg, idx, parsed = _repo(tmp_path, {"join.sql": """
        CREATE OR REPLACE TABLE stage_bare_published AS
        SELECT market_code
        FROM account_main a
        JOIN customer_demographics d ON d.acct_id = a.acct_id
        WHERE cm13 IS NOT NULL;
    """})
    got = trace(idx, parsed, [{"table": "customer_demographics", "attrs": ["cm13"]}],
                change_type="removal", cfg=cfg).to_dict()
    rows = [r for g in got["groups"] for r in g["rows"]]
    assert len(rows) == 1, "the usage must still be reported"
    assert rows[0]["certain"] is False, "and it must not be asserted"
    assert got["attributes"][0]["uncertain"] == 1


def test_a_column_out_of_a_cte_is_not_ruled_out(tmp_path):
    """A qualifier pointing at a WITH block says nothing about which real table
    the value came from -- and that block is the chain being followed. Treating
    it as "some other table" would drop the commonest shape in this repository."""
    cfg, idx, parsed = _repo(tmp_path, {"cte.sql": """
        CREATE OR REPLACE TABLE stage_cte_published AS
        WITH ranked AS (
          SELECT cm13, market_code,
                 ROW_NUMBER() OVER (PARTITION BY cm13 ORDER BY last_upd_ts DESC) AS rn
          FROM customer_demographics
        )
        SELECT r.cm13, r.market_code FROM ranked r WHERE r.rn = 1;
    """})
    got = trace(idx, parsed, [{"table": "customer_demographics", "attrs": ["cm13"]}],
                change_type="removal", cfg=cfg).to_dict()
    assert got["stats"]["productionTables"] == 1


def test_one_source_table_means_an_unqualified_column_is_certain(tmp_path):
    """Nothing to be ambiguous with, so nothing to hedge about."""
    cfg, idx, parsed = _repo(tmp_path, {"one.sql": """
        CREATE OR REPLACE TABLE stage_single_published AS
        SELECT cm13, market_code FROM customer_demographics WHERE cm13 IS NOT NULL;
    """})
    got = trace(idx, parsed, [{"table": "customer_demographics", "attrs": ["cm13"]}],
                change_type="removal", cfg=cfg).to_dict()
    rows = [r for g in got["groups"] for r in g["rows"]]
    assert rows and all(r["certain"] for r in rows)


# ── saying how common the name is ──────────────────────────────────────────
def test_the_screen_is_told_how_many_tables_share_the_name(tmp_path):
    """A scan for a name half the warehouse shares looks identical on screen to
    a scan for a name one table has, and they are not the same answer. Without
    these numbers there is no way to tell a long list caused by a common name
    from a long list caused by a big change."""
    files = {}
    for n in range(6):
        files[f"t{n}.sql"] = f"""
            CREATE OR REPLACE TABLE stage_{n} AS
            SELECT cm13, cm11 FROM customer_demographics;
        """
    files["rare.sql"] = """
        CREATE OR REPLACE TABLE stage_rare AS
        SELECT market_code FROM customer_demographics;
    """
    cfg, idx, parsed = _repo(tmp_path, files)
    got = trace(idx, parsed,
                [{"table": "customer_demographics", "attrs": ["cm13", "market_code"]}],
                change_type="removal", cfg=cfg).to_dict()
    by_attr = {a["attr"]: a for a in got["attributes"]}
    assert by_attr["cm13"]["nameInTables"] == 6
    assert by_attr["market_code"]["nameInTables"] == 1
    assert by_attr["cm13"]["tablesRead"] == 7
