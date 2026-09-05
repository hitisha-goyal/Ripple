"""Backfill runner for the zone tables.

It names a .sql file that is not in this folder. Ripple must report that as a
query it has never read, rather than counting this job as fully scanned.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKFILL_SQL_PATH = "sql/zone_backfill_missing.sql"
LOG_INSERT_SQL = "INSERT INTO ops.backfill_runs (run_label) VALUES (@run_label)"


def load_sql(repo_root: Path = REPO_ROOT) -> str:
    """Read the backfill statement from the path named above."""
    return (repo_root / BACKFILL_SQL_PATH).read_text(encoding="utf-8")


def run(client: Any, run_label: str) -> str:
    """Run the backfill and record the label it ran under."""
    sql = load_sql()
    client.query(sql, {})
    client.query(LOG_INSERT_SQL, {"run_label": run_label})
    return run_label
