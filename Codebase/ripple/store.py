"""History of past notifications, so nothing gets lost between people.

A single SQLite file. On a serverless host the filesystem is read-only apart
from /tmp, so the path is configurable and a failure to write is reported
rather than crashing the request.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .config import Settings, settings as default_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS analyses (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at   TEXT NOT NULL,
  subject      TEXT,
  source       TEXT,
  change_type  TEXT,
  effective    TEXT,
  risk         TEXT,
  status       TEXT NOT NULL DEFAULT 'New',
  mode         TEXT,
  vals_json    TEXT,
  scan_json    TEXT,
  summary_json TEXT
);
"""

STATUSES = ("New", "In progress", "Verified", "Closed")


def _connect(cfg: Settings) -> sqlite3.Connection:
    path = Path(cfg.db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # A longer wait than the default five seconds, for one specific reason: this
    # file usually sits in a folder OneDrive is syncing, and OneDrive holds a
    # file open while it uploads it. Five seconds is short enough to lose a
    # saved analysis to a routine upload; fifteen rides it out. If the lock is
    # real rather than passing, the caller still gets a plain refusal.
    con = sqlite3.connect(path, timeout=15)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


KEPT_NOTE = (
    "Saved on the machine that handled this request. This copy of Ripple runs on a "
    "serverless host, which throws that machine away and starts a fresh one, so this "
    "entry can disappear at any time -- often within minutes. Treat the list of past "
    "analyses as a scratchpad here, not a record. Copy anything you need to keep."
)


def save(vals: dict, scan: dict, summary: dict, mode: str,
         cfg: Settings | None = None) -> dict:
    cfg = cfg or default_settings
    try:
        con = _connect(cfg)
    except (sqlite3.Error, OSError) as exc:
        return {"saved": False, "reason": f"history is unavailable here ({exc})"}
    try:
        with con:
            cur = con.execute(
                """INSERT INTO analyses
                   (created_at, subject, source, change_type, effective, risk, status,
                    mode, vals_json, scan_json, summary_json)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    vals.get("subject", ""),
                    vals.get("source", ""),
                    vals.get("changeType", ""),
                    vals.get("effectiveDate", ""),
                    scan.get("risk", "none"),
                    "New",
                    mode,
                    json.dumps(vals),
                    json.dumps(scan),
                    json.dumps(summary),
                ),
            )
        out = {"saved": True, "id": cur.lastrowid}
        if cfg.serverless:
            out["note"] = KEPT_NOTE
        return out
    finally:
        con.close()


def listing(cfg: Settings | None = None, limit: int = 50) -> list[dict]:
    cfg = cfg or default_settings
    try:
        con = _connect(cfg)
    except (sqlite3.Error, OSError):
        return []
    try:
        rows = con.execute(
            """SELECT id, created_at, subject, source, change_type, effective, risk, status, mode
               FROM analyses ORDER BY id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def get(analysis_id: int, cfg: Settings | None = None) -> dict | None:
    cfg = cfg or default_settings
    try:
        con = _connect(cfg)
    except (sqlite3.Error, OSError):
        return None
    try:
        r = con.execute("SELECT * FROM analyses WHERE id = ?", (analysis_id,)).fetchone()
        if not r:
            return None
        d = dict(r)
        for k in ("vals_json", "scan_json", "summary_json"):
            d[k] = json.loads(d[k]) if d.get(k) else None
        return d
    finally:
        con.close()


def set_status(analysis_id: int, status: str, cfg: Settings | None = None) -> bool:
    if status not in STATUSES:
        return False
    cfg = cfg or default_settings
    try:
        con = _connect(cfg)
    except (sqlite3.Error, OSError):
        return False
    try:
        with con:
            cur = con.execute(
                "UPDATE analyses SET status = ? WHERE id = ?", (status, analysis_id)
            )
        return cur.rowcount > 0
    finally:
        con.close()
