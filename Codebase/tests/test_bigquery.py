"""Tests for reading a BigQuery pipeline.

BigQuery is not a dialect Ripple can guess at. Left as generic SQL, everyday
constructs -- QUALIFY, EXCEPT, UNNEST, MERGE, backtick-quoted three-part names
-- do not parse at all, and a change with real impact comes back as "no impact".
That is the worst possible failure for a tool like this, so it is pinned here.

The other thing pinned: a BigQuery pipeline usually loads its production table
with MERGE, and its Python jobs name the destination in the job settings rather
than in the SQL. Miss either and the chain stops one step short of the table
anyone actually reads.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ripple.catalog import build_catalog                        # noqa: E402
from ripple.config import Settings                              # noqa: E402
from ripple.scanner.lineage import trace                        # noqa: E402
from ripple.scanner.repo import RepoIndex, written_tables       # noqa: E402
from ripple.scanner.sqlread import parse_repo, short_name       # noqa: E402

# A small pipeline in the shape a BigQuery team really writes it.
FILES = {
    "ddl/customer_demographics.sql": """
        CREATE OR REPLACE TABLE `acme-prod.c360.customer_demographics`
        (
          customer_id STRING NOT NULL,
          market_code STRING,
          last_upd    TIMESTAMP,
          tags        ARRAY<STRING>,
          address     STRUCT<line1 STRING, city STRING>
        )
        PARTITION BY DATE(last_upd)
        CLUSTER BY market_code;
    """,
    "etl/customer_snapshot.sql": """
        CREATE OR REPLACE TABLE `acme-prod.staging.customer_snapshot` AS
        SELECT
          c.customer_id,
          UPPER(TRIM(c.market_code)) AS mkt_cd,
          c.last_upd                 AS lut_ts
        FROM `acme-prod.c360.customer_demographics` AS c
        WHERE c.market_code IS NOT NULL
        QUALIFY ROW_NUMBER() OVER (
          PARTITION BY c.customer_id ORDER BY c.last_upd DESC, c.market_code ASC
        ) = 1;
    """,
    "etl/market_enrich.sql": """
        DECLARE run_date DATE DEFAULT CURRENT_DATE();

        CREATE OR REPLACE TABLE `acme-prod.staging.market_enriched` AS
        SELECT s.* EXCEPT (lut_ts), m.region, tag
        FROM `acme-prod.staging.customer_snapshot` AS s
        LEFT JOIN `acme-prod.ref.market_ref` AS m ON m.market_code = s.mkt_cd
        CROSS JOIN UNNEST(s.tags) AS tag
        WHERE DATE(s.lut_ts) <= run_date;
    """,
    "odl/customer_profile_prod.sql": """
        MERGE INTO `acme-prod.odl.customer_profile_prod` AS t
        USING (
          SELECT customer_id, mkt_cd, region
          FROM `acme-prod.staging.market_enriched`
          WHERE mkt_cd IN ('US', 'GB', 'IN')
        ) AS s
        ON t.customer_id = s.customer_id
        WHEN MATCHED THEN UPDATE SET t.mkt_cd = s.mkt_cd
        WHEN NOT MATCHED THEN INSERT (customer_id, mkt_cd) VALUES (s.customer_id, s.mkt_cd);
    """,
    "etl/daily_targeting.py": '''
from google.cloud import bigquery

client = bigquery.Client(project="acme-prod")

TARGETING_SQL = """
SELECT p.customer_id, p.mkt_cd
FROM `acme-prod.odl.customer_profile_prod` AS p
WHERE p.mkt_cd IS NOT NULL
"""


def build():
    job_config = bigquery.QueryJobConfig(
        destination="acme-prod.odl.final_targeting_prod",
        write_disposition="WRITE_TRUNCATE",
    )
    client.query(TARGETING_SQL, job_config=job_config).result()
''',
}


@pytest.fixture
def repo(tmp_path):
    for rel, text in FILES.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return tmp_path


def scan(repo: Path, dialect: str):
    cfg = Settings()
    cfg.sql_dialect = dialect
    cfg.repo_path = repo
    # There is no shipped list of published tables any more -- see
    # Settings.has_production. This stands for one somebody entered.
    cfg.set_production("_PROD")
    idx = RepoIndex.build(repo, cfg)
    parsed = parse_repo(idx, cfg)
    result = trace(idx, parsed,
                   [{"table": "customer_demographics", "attrs": ["market_code"]}],
                   change_type="value_change", cfg=cfg)
    return cfg, idx, parsed, build_catalog(parsed), result.to_dict()


# ── the setting is not optional on BigQuery ────────────────────────────────
def test_without_the_dialect_bigquery_sql_does_not_parse(repo):
    _, _, parsed, cat, out = scan(repo, "")
    assert len(parsed.unreadable) >= 3, "generic SQL should visibly fail on BigQuery"
    assert not cat.tables, "nothing should be learned from unparsed files"
    # It used to say "No impact" here, in green, with three unreadable files
    # underneath it and nothing at all learned from the repository. That is the
    # one answer this tool sells, printed over a scan that read nothing.
    assert out["risk"] == "unknown", "a green No impact over files it could not read"


def test_with_the_dialect_every_file_is_read(repo):
    _, _, parsed, cat, out = scan(repo, "bigquery")
    assert parsed.unreadable == [], [u["reason"] for u in parsed.unreadable]
    assert {"CUSTOMER_DEMOGRAPHICS", "CUSTOMER_SNAPSHOT", "MARKET_ENRICHED"} <= set(cat.tables)
    assert out["risk"] != "none"


def test_the_change_reaches_the_production_table(repo):
    """The whole point: a value change upstream lands on the table people read.

    Both of them. customer_profile_prod is loaded by the MERGE, and the Python
    job then builds final_targeting_prod out of it -- in this same repository,
    so it is this team's to defend too. Ripple used to stop at the first
    published table it met, which under-counted the one number on the summary
    that anybody acts on.
    """
    _, _, _, _, out = scan(repo, "bigquery")
    # Listed worst first, so the order is by how many impacts each carries
    # rather than by the alphabet -- on a real scan this list is hundreds long.
    assert {g["prod"] for g in out["groups"]} == {"customer_profile_prod",
                                                  "final_targeting_prod"}
    counts = [len(g["rows"]) for g in out["groups"]]
    assert counts == sorted(counts, reverse=True)
    files = {r["file"] for g in out["groups"] for r in g["rows"]}
    assert "etl/customer_snapshot.sql" in files
    assert "odl/customer_profile_prod.sql" in files
    assert any(r["breaking"] for g in out["groups"] for r in g["rows"])


# ── the two places the chain used to stop ──────────────────────────────────
def test_merge_counts_as_writing_to_its_table(repo):
    _, _, parsed, _, _ = scan(repo, "bigquery")
    merge = next(s for s in parsed.statements if s.file == "odl/customer_profile_prod.sql")
    assert short_name(merge.target) == "customer_profile_prod"
    assert "market_enriched" in {short_name(s).lower() for s in merge.sources}


def test_a_python_job_names_its_destination_in_the_job_settings(repo):
    _, idx, _, _, _ = scan(repo, "bigquery")
    job = idx.get("etl/daily_targeting.py")
    assert written_tables(job) == ["final_targeting_prod"]


def test_pandas_to_gbq_is_recognised_too(tmp_path):
    p = tmp_path / "load.py"
    p.write_text(
        'df.to_gbq("acme-prod.odl.spend_summary_prod", if_exists="replace")\n'
        'q = """SELECT market_code FROM `acme-prod.c360.customer_demographics`"""\n',
        encoding="utf-8",
    )
    idx = RepoIndex.build(tmp_path, Settings())
    assert written_tables(idx.get("load.py")) == ["spend_summary_prod"]


def test_a_spark_job_still_works_the_way_it_did(tmp_path):
    """The BigQuery patterns must not disturb the Spark ones already relied on."""
    p = tmp_path / "job.py"
    p.write_text(
        'df = spark.sql("""SELECT market_code FROM customer_demographics""")\n'
        'df.write.saveAsTable("odl.market_rollup_prod")\n',
        encoding="utf-8",
    )
    idx = RepoIndex.build(tmp_path, Settings())
    assert written_tables(idx.get("job.py")) == ["market_rollup_prod"]


def test_a_python_file_is_called_python(repo):
    """It might be Spark, it might be BigQuery. Only ".py" is known for certain."""
    _, idx, _, _, _ = scan(repo, "bigquery")
    assert idx.get("etl/daily_targeting.py").lang == "Python"
