"""Saved analyses, kept in a SQLite file.

Nothing in here raises at the caller. A database that cannot be written comes
back as saved=False with a sentence a person can act on, because the screen has
to be able to say "history is not available here" rather than show a saved
analysis that was never saved.

THE COLUMN NAMES ARE PART OF THE ANSWER. The Past analyses table reads
created_at, change_type and the rest exactly as they are spelled here. Rename
one to createdAt and every row in that table prints a dash, with nothing on
screen saying why: all the rows there, and all of them empty.

The settings object is passed in rather than imported so this module has no
opinion about where the file lives. It reads exactly one attribute off it -
db_path - and that read is in one function, _db_path, so a different name in
config.py is a one-line change here.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from tempfile import gettempdir
from typing import Any

# Five seconds - the sqlite3 default - is short enough to lose a saved analysis
# to a routine cloud upload, because a sync holds the file open while it sends
# it. Fifteen rides that out. A lock that is real rather than passing still comes
# back after fifteen seconds as a plain refusal, which is the honest answer.
_TIMEOUT_SECONDS = 15.0

# The Past analyses table shows the recent ones. Reading thousands of rows to
# throw all but fifty away costs time on a synced file for nothing.
_MAX_ROWS = 50

STATUSES = ("New", "In progress", "Verified", "Closed")

# The row the listing hands back, in this order and with these exact names.
_ROW_COLUMNS = (
    "id",
    "created_at",
    "subject",
    "source",
    "change_type",
    "effective",
    "risk",
    "status",
    "mode",
)

_BLOB_COLUMNS = ("vals_json", "scan_json", "summary_json")

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS analyses (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at   TEXT NOT NULL,
    subject      TEXT NOT NULL DEFAULT '',
    source       TEXT NOT NULL DEFAULT '',
    change_type  TEXT NOT NULL DEFAULT '',
    effective    TEXT NOT NULL DEFAULT '',
    risk         TEXT NOT NULL DEFAULT '',
    status       TEXT NOT NULL DEFAULT 'New',
    mode         TEXT NOT NULL DEFAULT '',
    vals_json    TEXT NOT NULL DEFAULT '{}',
    scan_json    TEXT NOT NULL DEFAULT '{}',
    summary_json TEXT NOT NULL DEFAULT '{}'
)
"""


def _db_path(settings: Any) -> Path:
    """Where the history file lives.

    The only place in this module that asks the settings object anything.
    """
    return Path(str(settings.db_path))


def _connect(settings: Any) -> sqlite3.Connection:
    """Open the history file, making the folder and the table if need be."""
    path = _db_path(settings)
    parent = path.parent
    if str(parent):
        parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=_TIMEOUT_SECONDS)
    conn.row_factory = sqlite3.Row
    conn.execute(_CREATE_SQL)
    conn.commit()
    return conn


def _trouble(exc: BaseException, path: Path) -> str:
    """One sentence a person can act on, never a stack trace."""
    text = str(exc)
    if isinstance(exc, sqlite3.OperationalError) and "locked" in text.lower():
        return (
            "The history file at "
            + str(path)
            + " was busy for fifteen seconds and would not let go. Something else "
            "has it open - a cloud sync uploading it, or another copy of Ripple. "
            "Nothing was saved. Try again in a moment."
        )
    if isinstance(exc, OSError):
        return (
            "The history file at "
            + str(path)
            + " could not be written: "
            + text
            + ". Nothing was saved, and history is not available here until that "
            "folder can be written to."
        )
    return (
        "The history file at "
        + str(path)
        + " could not be used: "
        + text
        + ". Nothing was saved."
    )


def _text(values: Any, *names: str) -> str:
    """The first of these keys that is really there, as plain text.

    More than one spelling is accepted on purpose: the scan route calls the kind
    of change changeKind, and the column it is stored in is change_type. A row
    that prints a dash because of a spelling nobody can see is the failure this
    guards against.
    """
    if not isinstance(values, dict):
        return ""
    for name in names:
        found = values.get(name)
        if found is None:
            continue
        as_text = str(found).strip()
        if as_text:
            return as_text
    return ""


def _dump(value: Any) -> str:
    """Store a block as JSON text.

    default=str so a date or a Path inside a scan result is written as something
    readable rather than taking the whole save down.
    """
    return json.dumps(value, default=str)


def _load(text: Any) -> Any:
    """Read a stored block back into objects, or None if it will not read."""
    if text is None:
        return None
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return None


def _row_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {name: row[name] for name in _ROW_COLUMNS}


def save(
    vals: Any,
    scan: Any,
    summary: Any,
    mode: str,
    settings: Any,
) -> dict[str, Any]:
    """Save one analysis. Returns {saved, id, reason}."""
    path = _db_path(settings)
    conn: sqlite3.Connection | None = None
    try:
        conn = _connect(settings)
        cursor = conn.execute(
            "INSERT INTO analyses ("
            "created_at, subject, source, change_type, effective, risk, status, "
            "mode, vals_json, scan_json, summary_json"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                datetime.now().isoformat(timespec="seconds"),
                _text(vals, "subject"),
                _text(vals, "source"),
                _text(vals, "changeKind", "changeType", "change_type"),
                _text(vals, "effective"),
                _text(scan, "risk"),
                STATUSES[0],
                str(mode or ""),
                _dump(vals),
                _dump(scan),
                _dump(summary),
            ),
        )
        new_id = int(cursor.lastrowid or 0)
        conn.commit()
        return {"saved": True, "id": new_id, "reason": ""}
    except (sqlite3.Error, OSError, ValueError, TypeError) as exc:
        return {"saved": False, "id": 0, "reason": _trouble(exc, path)}
    finally:
        # sqlite3's context manager commits, it does not close. A connection left
        # open holds the file, which is the last thing to do to a file something
        # is syncing to the cloud.
        if conn is not None:
            conn.close()


def listing(settings: Any) -> dict[str, Any]:
    """The saved analyses, newest first, at most fifty.

    Returns {available, reason, rows}. An empty rows list with available=False is
    "history could not be read", which is a different thing from "nothing has
    been saved yet" - and the screen has to be able to tell them apart.
    """
    path = _db_path(settings)
    conn: sqlite3.Connection | None = None
    try:
        conn = _connect(settings)
        # id descending, not created_at: two saves in the same second would sort
        # by chance, and id is what the row is fetched back by.
        cursor = conn.execute(
            "SELECT " + ", ".join(_ROW_COLUMNS) + " FROM analyses "
            "ORDER BY id DESC LIMIT ?",
            (_MAX_ROWS,),
        )
        rows = [_row_dict(row) for row in cursor.fetchall()]
        return {"available": True, "reason": "", "rows": rows}
    except (sqlite3.Error, OSError, ValueError, TypeError) as exc:
        return {"available": False, "reason": _trouble(exc, path), "rows": []}
    finally:
        if conn is not None:
            conn.close()


def get(item_id: int, settings: Any) -> dict[str, Any]:
    """One saved analysis, with the three stored blocks read back into objects.

    Returns {available, reason, found, row}. row carries the same nine names the
    listing uses, plus vals_json, scan_json and summary_json as objects rather
    than as text.
    """
    path = _db_path(settings)
    conn: sqlite3.Connection | None = None
    try:
        conn = _connect(settings)
        cursor = conn.execute(
            "SELECT " + ", ".join(_ROW_COLUMNS + _BLOB_COLUMNS) + " FROM analyses "
            "WHERE id = ?",
            (int(item_id),),
        )
        row = cursor.fetchone()
        if row is None:
            return {"available": True, "reason": "", "found": False, "row": None}
        answer = _row_dict(row)
        unreadable: list[str] = []
        for name in _BLOB_COLUMNS:
            block = _load(row[name])
            if block is None and row[name] not in (None, ""):
                unreadable.append(name)
            answer[name] = block
        reason = ""
        if unreadable:
            # Say it rather than hand back a silent None: a block that will not
            # read back is a saved analysis that is missing part of itself.
            reason = (
                "This saved analysis was read, but "
                + ", ".join(unreadable)
                + " could not be read back into anything and is shown as empty."
            )
        return {"available": True, "reason": reason, "found": True, "row": answer}
    except (sqlite3.Error, OSError, ValueError, TypeError) as exc:
        return {
            "available": False,
            "reason": _trouble(exc, path),
            "found": False,
            "row": None,
        }
    finally:
        if conn is not None:
            conn.close()


def set_status(item_id: int, status: str, settings: Any) -> dict[str, Any]:
    """Move one saved analysis to another status. Returns {saved, reason}."""
    wanted = str(status or "").strip()
    if wanted not in STATUSES:
        return {
            "saved": False,
            "reason": (
                "'"
                + wanted
                + "' is not a status this build knows. The four are: "
                + ", ".join(STATUSES)
                + "."
            ),
        }
    path = _db_path(settings)
    conn: sqlite3.Connection | None = None
    try:
        conn = _connect(settings)
        cursor = conn.execute(
            "UPDATE analyses SET status = ? WHERE id = ?", (wanted, int(item_id))
        )
        conn.commit()
        if cursor.rowcount < 1:
            return {
                "saved": False,
                "reason": (
                    "There is no saved analysis numbered "
                    + str(item_id)
                    + ", so nothing was changed."
                ),
            }
        return {"saved": True, "reason": ""}
    except (sqlite3.Error, OSError, ValueError, TypeError) as exc:
        return {"saved": False, "reason": _trouble(exc, path)}
    finally:
        if conn is not None:
            conn.close()


def history_kept(settings: Any) -> bool:
    """Do saved analyses really last on this machine.

    This is the historyKept line in the health block. It is answered by really
    opening the file and really making the table, because a folder that cannot be
    written to looks exactly like one that can until something tries.

    A file inside the machine's temporary folder is counted as not lasting: the
    machine deletes that folder, so a screen offering to save into it would be
    promising something it cannot keep.
    """
    path = _db_path(settings)
    conn: sqlite3.Connection | None = None
    try:
        temp_root = Path(gettempdir()).resolve()
        here = path.resolve()
        if here == temp_root or temp_root in here.parents:
            return False
        conn = _connect(settings)
        return True
    except (sqlite3.Error, OSError, ValueError, TypeError):
        return False
    finally:
        if conn is not None:
            conn.close()
