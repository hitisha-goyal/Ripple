"""Reference table refresh.

The three files it names are all in this folder, so this job is the contrast
case for run_zone_backfill.py: nothing here should come back as unread.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
REFERENCE_SQL_FILES = (
    "sql/01_source_zone_lookup.sql",
    "sql/02_source_depot_roster.sql",
    "sql/03_source_grade_scale.sql",
)


def run(client: Any, repo_root: Path = REPO_ROOT) -> list[str]:
    """Run each reference file in order and return the paths that ran."""
    ran: list[str] = []
    for relative_path in REFERENCE_SQL_FILES:
        sql = (repo_root / relative_path).read_text(encoding="utf-8")
        client.query(sql, {})
        ran.append(relative_path)
    return ran
