"""The two settings a person has to choose, kept in a file beside the app.

Online, the repository folder and the SQL dialect are environment variables.
That is fine for someone who deploys things and hopeless for everybody else: a
colleague who has been handed a folder to double-click will never set one, so
they would silently scan the wrong folder, reading BigQuery as generic SQL.

So both are asked for on screen and written to ``ripple-settings.json`` next to
the executable. Nothing else is stored, and the file is plain text so it can be
read, edited or deleted by hand.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import paths

# Dialects worth offering, in the order they are shown. BigQuery is first and
# is the default: reading a BigQuery pipeline as generic SQL does not give a
# vaguer answer, it gives the opposite answer -- 2 of 5 files parsed and a
# confident "no impact" on a change that broke two things.
DIALECT_CHOICES: tuple[dict[str, str], ...] = (
    {"id": "bigquery", "label": "BigQuery", "note": "Our stack. Backticked names, EXCEPT, QUALIFY, UNNEST, MERGE."},
    {"id": "snowflake", "label": "Snowflake", "note": ""},
    {"id": "databricks", "label": "Databricks SQL", "note": ""},
    {"id": "spark", "label": "Spark SQL", "note": ""},
    {"id": "hive", "label": "Hive", "note": ""},
    {"id": "teradata", "label": "Teradata", "note": ""},
    {"id": "oracle", "label": "Oracle", "note": ""},
    {"id": "tsql", "label": "SQL Server (T-SQL)", "note": ""},
    {"id": "postgres", "label": "PostgreSQL", "note": ""},
    {"id": "mysql", "label": "MySQL", "note": ""},
    {"id": "redshift", "label": "Redshift", "note": ""},
    {"id": "presto", "label": "Presto", "note": ""},
    {"id": "trino", "label": "Trino", "note": ""},
    {"id": "duckdb", "label": "DuckDB", "note": ""},
    {"id": "sqlite", "label": "SQLite", "note": ""},
    {"id": "", "label": "Generic SQL", "note": "Only when the stack is genuinely unknown. Reads least, and can be confidently wrong."},
)

# Taken from the shared engine, never set here. Two defaults meant the two
# builds read the SAME folder as two different languages, and the dialect
# decides whether a chain is followed or quietly lost.
from ripple.config import DEFAULT_DIALECT                     # noqa: E402,F401


def default_hops() -> int:
    """How many renames deep to follow, taken from the shared engine.

    Not a number of its own. This was hard-coded to 4 here while the engine
    moved to 10, so the program a colleague double-clicks would have gone on
    quietly stopping six hops short of every published table -- the exact
    failure the engine change was made to fix, shipped only to the machine
    where nobody can check it.
    """
    from ripple.config import Settings

    return Settings().max_hops


def max_hops_ceiling() -> int:
    """The deepest this program will follow when a limit is asked for.

    Zero is not capped by this: zero means "follow until the code runs out",
    which is the default and is bounded by the walk's own memory of where it has
    been rather than by a number. See ripple.config.Settings.max_hops -- a
    counter here could only ever cut a real trail short and report the cut as
    the end of the warehouse.
    """
    return 25


def clamp_hops(value) -> int:
    """A hop setting, kept meaningful. Zero survives; anything else is 1..25."""
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default_hops()
    if n <= 0:
        return 0
    return min(max_hops_ceiling(), n)


def default_production() -> str:
    from ripple.config import DEFAULT_PRODUCTION

    return ", ".join(DEFAULT_PRODUCTION)


DEFAULTS: dict[str, Any] = {
    "repoPath": "",
    "repoLabel": "",
    "sqlDialect": DEFAULT_DIALECT,
    # Zero: follow until the code runs out. Matches the shared engine, and
    # test_settings.py fails if the two ever drift.
    "maxHops": 0,
    # Which table names are the ones this team publishes. There is no default,
    # and there must never be one again: leaving it at _PROD on a repository
    # that names nothing _PROD is what turns a real impact into a confident
    # "no impact". Empty means NOT GIVEN, and nothing is scanned until it is.
    "prodTables": "",
}


def dialects() -> list[dict[str, str]]:
    """The choices, minus any this copy of sqlglot does not actually know.

    An option that cannot work is worse than a missing one: it would be picked,
    saved, and then quietly read every file as generic SQL anyway.
    """
    from sqlglot import Dialect
    known = set(Dialect.classes)
    return [d for d in DIALECT_CHOICES if d["id"] == "" or d["id"] in known]


def valid_dialect(value: str) -> bool:
    return (value or "") in {d["id"] for d in dialects()}


# ── the file ───────────────────────────────────────────────────────────────
def load() -> dict[str, Any]:
    """Whatever was saved last time, with anything missing or broken defaulted."""
    out = dict(DEFAULTS)
    path = paths.settings_file()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return out                      # never seen it before, or it is damaged
    if not isinstance(raw, dict):
        return out
    for key in DEFAULTS:
        if key in raw and isinstance(raw[key], type(DEFAULTS[key])):
            out[key] = raw[key]
    if not valid_dialect(str(out["sqlDialect"])):
        out["sqlDialect"] = DEFAULT_DIALECT
    out["maxHops"] = clamp_hops(out["maxHops"])
    # No fallback. An unset list is a state to be asked about, not a rule to be
    # matched against. See DEFAULTS above.
    out["prodTables"] = str(out["prodTables"] or "").strip()
    return out


def save(values: dict[str, Any]) -> dict[str, Any]:
    """Write the settings file. Returns what was actually saved."""
    keep = {k: values.get(k, DEFAULTS[k]) for k in DEFAULTS}
    # Stored as a full path. A relative one would mean something different
    # depending on where Ripple happened to be started from, and "." would mean
    # Ripple's own program folder.
    raw_path = str(keep["repoPath"] or "").strip()
    keep["repoPath"] = str(Path(raw_path).resolve()) if raw_path else ""
    keep["repoLabel"] = str(keep["repoLabel"] or "").strip() or folder_label(keep["repoPath"])
    if not valid_dialect(str(keep["sqlDialect"])):
        keep["sqlDialect"] = DEFAULT_DIALECT
    keep["maxHops"] = clamp_hops(keep["maxHops"])
    # Saved exactly as typed, empty included. Empty means NOT GIVEN -- see
    # DEFAULTS. Falling back here is what let a scan run against a rule nobody
    # chose and report "no production table is affected" from it.
    keep["prodTables"] = str(keep["prodTables"] or "").strip()
    path = paths.settings_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(keep, indent=2) + "\n", encoding="utf-8")
    return keep


def configured(values: dict[str, Any] | None = None) -> bool:
    """Is Ripple set up enough to answer anything?

    Two things, and BOTH are required. A folder with no published-table list is
    a Ripple that can read every file and still not know what any of it means
    for anybody: every table fails the published test, and a change that breaks
    three published tables comes back "no production table is affected". That is
    the same green tick as a genuinely clean answer.
    """
    values = values if values is not None else load()
    return (bool(str(values.get("repoPath") or "").strip())
            and bool(str(values.get("prodTables") or "").strip()))


def folder_label(path: str | Path) -> str:
    name = Path(str(path or "")).name
    return name or str(path or "")


# ── what the settings mean to the shared engine ────────────────────────────
def apply(values: dict[str, Any]) -> None:
    """Push the chosen settings into the shared engine's configuration.

    The engine reads one settings object. Rather than forking it, the offline
    app edits that object: the folder, the dialect and where history is kept,
    plus the things that must never be true offline -- no GitHub source, no AI
    key, and no serverless limits, because this runs on a real machine with a
    real disk.
    """
    from ripple.config import git_branch, settings

    settings.repo_path = Path(str(values.get("repoPath") or ""))
    settings.repo_label = str(values.get("repoLabel") or "") or folder_label(settings.repo_path)
    settings.repo_branch = git_branch(settings.repo_path)
    settings.sql_dialect = str(values.get("sqlDialect") or "")
    settings.max_hops = clamp_hops(values.get("maxHops"))
    # The pasted list, in whatever shape it arrived. An empty one stays empty
    # and means NOT GIVEN; the scan route refuses rather than answering against
    # a rule nobody chose. See DEFAULTS.
    settings.set_production(str(values.get("prodTables") or ""))
    settings.db_path = paths.history_file()
    settings.serverless = False
    settings.repo_source = "folder"
    settings.repo_url_template = ""
    # Offline there is no AI and no GitHub, so the engine is told so directly
    # rather than being trusted to leave them alone.
    settings.ai_key = ""
    settings.github_repo = ""
    settings.github_branch = ""
    settings.github_token = ""


# ── is the folder still there, and does it hold anything? ──────────────────
def folder_state(path: str | Path) -> dict[str, Any]:
    """Is the folder there at all? Cheap enough to ask on every page load.

    A folder that has been moved, renamed or deleted since it was chosen is the
    normal case on a locked-down machine, not an exceptional one, so it gets a
    sentence a person can act on instead of an empty scan or a crash.
    """
    raw = str(path or "").strip()
    if not raw:
        return {"ok": False, "state": "unset",
                "message": "No repository folder chosen yet."}
    folder = Path(raw)
    if not folder.exists():
        return {"ok": False, "state": "missing",
                "message": f"That folder is not on this machine any more: {folder}"}
    if not folder.is_dir():
        return {"ok": False, "state": "notafolder",
                "message": f"That is a file, not a folder: {folder}"}
    return {"ok": True, "state": "ok", "message": ""}


def check_folder(path: str | Path) -> dict[str, Any]:
    """The same answer, plus how much is in there.

    This one walks the folder, so it is asked when somebody presses "check" or
    saves — not on every page load, where a large repository would make the
    screen sit there doing nothing visible.
    """
    from ripple.config import settings

    base = folder_state(path)
    if not base["ok"]:
        return {**base, "files": 0}
    folder = Path(str(path).strip())
    try:
        found = _count_code_files(folder, settings)
    except OSError as exc:
        return {"ok": False, "state": "unreadable", "files": 0,
                "message": f"That folder could not be read ({exc.strerror or exc})."}
    if not found:
        kinds = ", ".join(sorted(settings.code_extensions)[:6])
        return {"ok": False, "state": "empty", "files": 0,
                "message": f"That folder has no files Ripple can read. It looks for {kinds} and similar."}
    return {"ok": True, "state": "ok", "files": found,
            "message": f"{found} file{'' if found == 1 else 's'} Ripple can read."}


def _count_code_files(folder: Path, settings, cap: int = 20000) -> int:
    """Counted the same way the scanner counts, so the two never disagree.

    In particular the skipped-folder names are matched inside the repository
    only. A repository that happens to sit under a folder called build or venv
    is a normal thing on somebody's machine, and must not read as empty.
    """
    found = 0
    for p in folder.rglob("*"):
        if found >= cap:
            break
        if not p.is_file():
            continue
        if any(part in settings.skip_dirs for part in p.relative_to(folder).parts):
            continue
        if p.suffix.lower() in settings.code_extensions:
            found += 1
    return found
