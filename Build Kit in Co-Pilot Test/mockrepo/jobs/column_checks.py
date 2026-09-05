"""Morning column checks.

Every mention of a column in this file is a quoted string handed to a helper,
never SQL. Ripple must list the file as a mention only, and say how many lines
of it do that, rather than claiming an impact it cannot stand behind.
"""
from __future__ import annotations

from typing import Any


def assert_not_null(client: Any, table: str, column: str) -> bool:
    """Return True when the named column holds no null values."""
    return client.count_nulls(table, column) == 0


def assert_present(client: Any, table: str, column: str) -> bool:
    """Return True when the named column exists on the named table."""
    return column in client.columns_of(table)


def check_daily(client: Any) -> list[str]:
    """Run the morning checks and return the columns that failed."""
    failed: list[str] = []
    if not assert_present(client, "raw_orchard.consignment_source", "HARVEST_ZONE"):
        failed.append("HARVEST_ZONE")
    if not assert_not_null(client, "raw_orchard.consignment_source", "HARVEST_ZONE"):
        failed.append("HARVEST_ZONE")
    if not assert_present(client, "staging.consignment_clean", "hz"):
        failed.append("hz")
    if not assert_present(client, "curated.consignment_enriched", "hrv_zn"):
        failed.append("hrv_zn")
    if not assert_not_null(client, "marts.consignment_prod", "hrv_zn"):
        failed.append("hrv_zn")
    return failed
