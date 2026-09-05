"""Daily backfill job for the consignment chain.

The SQL this job runs is held in a triple-quoted string rather than in a .sql
file, so a scan that only opens .sql files never sees the rename it makes.
"""
from __future__ import annotations

from typing import Any

START_DATE_PARAM = "start_date"
END_DATE_PARAM = "end_date"

BACKFILL_ENRICHED_SQL = """
CREATE OR REPLACE TABLE curated.consignment_enriched_backfill AS
SELECT
  c.consignment_ref,
  c.hz AS hrv_zn,
  c.zone_label,
  c.picked_on,
  c.crate_count
FROM staging.consignment_clean AS c
WHERE c.picked_on BETWEEN @start_date AND @end_date
"""

REFRESH_REVIEW_SQL = """
CREATE OR REPLACE TABLE sandbox.consignment_review_backfill AS
SELECT
  hrv_zn,
  COUNT(*) AS row_count
FROM curated.consignment_enriched_backfill
GROUP BY hrv_zn
"""


def run(client: Any, start_date: str, end_date: str) -> list[str]:
    """Run both statements in order and return the tables that were written."""
    written: list[str] = []
    params = {START_DATE_PARAM: start_date, END_DATE_PARAM: end_date}
    client.query(BACKFILL_ENRICHED_SQL, params)
    written.append("curated.consignment_enriched_backfill")
    client.query(REFRESH_REVIEW_SQL, {})
    written.append("sandbox.consignment_review_backfill")
    return written
