"""The offline web service, built on Python's own library.

The same routes, the same JSON and the same refusals as the packaged build --
which is the whole reason the screens do not change. What is different is only
underneath: no FastAPI, no uvicorn, no pydantic, nothing that has to be
installed. See webserver.py for the plumbing.

There is no GitHub route and no AI route -- not disabled, not behind a flag,
absent -- so there is no key to leak, no address to type, and nothing that can
quietly start working because the machine turned out to have internet after all.

Every route below calls the shared engine in ``ripple``. Nothing about scanning,
reading SQL, tracing lineage or writing the summary is reimplemented here; this
is a thin layer, exactly as the packaged service is.
"""
from __future__ import annotations

import copy
import threading
from pathlib import Path
from typing import Any

from . import folderpick, lifecycle, nonet, paths, prefs, synced
from .webserver import HTTPError, Router

from ripple import narrative, production, progress, store
from ripple.build_info import build_info
from ripple.catalog import Catalog, build_catalog
from ripple.config import settings
from ripple.notification import extract_by_rules, read_upload
from ripple.scanner.lineage import trace
from ripple.scanner.repo import RepoIndex
from ripple.scanner.sqlread import ParsedRepo, parse_repo

router = Router()

_state: dict[str, Any] = {"index": None, "parsed": None, "catalog": None}

# ── reading without holding the screen hostage ─────────────────────────────
# Reading a repository the size of a real warehouse takes minutes, and
# /api/health is the request the screen makes before it can paint anything at
# all. On a few thousand files that is a window sitting blank with no way to ask
# what is happening -- because the only request that would tell it is the one it
# is already waiting on. A working program that says nothing for two minutes
# gets reported as a hung one, and here that window is the whole product.
#
# So the read happens on a thread, health answers straight away with
# indexing:true, and the screen shows the counted file numbers.
_build_lock = threading.RLock()
_reading: dict[str, Any] = {"thread": None, "error": ""}


def start_reading() -> None:
    """Begin reading on a thread, unless one is already at it."""
    with _build_lock:
        alive = _reading["thread"]
        if alive is not None and alive.is_alive():
            return

        def work() -> None:
            try:
                _reading["error"] = ""
                repo_state()
            except Exception as exc:                          # noqa: BLE001
                # Kept and shown. A read that failed and a read that never
                # finished look identical from the screen, and one of them needs
                # somebody to go and do something about it.
                _reading["error"] = str(exc)
            finally:
                progress.finish()

        t = threading.Thread(target=work, name="ripple-read", daemon=True)
        _reading["thread"] = t
        t.start()


def repo_state() -> tuple[RepoIndex, ParsedRepo, Catalog]:
    with _build_lock:
        return _read_if_needed()


def _read_if_needed() -> tuple[RepoIndex, ParsedRepo, Catalog]:
    if _state["index"] is None:
        # A folder that is missing, or has never been chosen, is a normal state
        # here rather than an error: the index comes back empty and the screen
        # says why. An unset folder is an empty path, which as a path means
        # "here" -- so without this Ripple would index its own program folder
        # and present it as the repository, which is worse than finding nothing.
        chosen = str(settings.repo_path).strip()
        if chosen in ("", "."):
            idx = RepoIndex(root=None)
        else:
            idx = RepoIndex.build(settings.repo_path, settings,
                                  on_progress=progress.reader("reading"))
        parsed = parse_repo(idx, settings, on_progress=progress.reader("parsing"))
        progress.finish()
        _state.update({"index": idx, "parsed": parsed, "catalog": build_catalog(parsed)})
    return _state["index"], _state["parsed"], _state["catalog"]


def reindex() -> None:
    _state["index"] = None
    repo_state()


# ── what the screen is told ────────────────────────────────────────────────
def _still_reading(values: dict, folder: dict) -> dict:
    """The health answer while the repository is being read for the first time.

    The SAME SHAPE as the finished one, with the counts at zero and ``indexing``
    true. One app.js paints from this, and a key left out here is a blank on
    screen that no test would ever see.
    """
    return {
        "ok": True,
        "indexing": True,
        "readError": _reading["error"],
        "progress": progress.snapshot(),
        "build": build_info(),
        "source": "folder",
        "offline": True,
        "configured": prefs.configured(values),
        "folder": folder,
        "canBrowse": folderpick.available(),
        "settingsFile": str(paths.settings_file()),
        "historyFile": str(paths.history_file()),
        "syncedFolder": synced.detect(paths.app_dir()),
        "dialects": prefs.dialects(),
        "serverless": False,
        "limits": {"maxUploadBytes": settings.max_upload_bytes, "historyKept": True},
        "repo": {
            "label": str(values.get("repoLabel") or ""),
            "path": str(values.get("repoPath") or ""),
            "branch": settings.repo_branch,
            "files": 0, "statements": 0, "unreadable": 0,
            "heldOnline": 0, "pathTooLong": 0, "inSkippedDirs": 0,
            "skippedDirNames": [], "runsSqlFrom": 0,
            "exists": folder["ok"], "kinds": [], "unknownExt": [],
        },
        "catalog": {"tables": 0, "columns": 0},
        "sqlDialect": settings.sql_dialect or "generic",
        "sqlDialectId": settings.sql_dialect,
        "maxHops": settings.max_hops,
        "production": settings.production_rule(),
        "productionRule": settings.production().to_dict(),
        "productionFrom": "entered" if settings.has_production() else "unset",
        "productionSet": settings.has_production(),
    }


def _health() -> dict:
    values = prefs.load()
    # Judged on what was actually chosen, not on the engine's path: an unset
    # path reads as "here", and "here" is Ripple's own program folder.
    folder = prefs.folder_state(values["repoPath"])
    # The folder was read into memory when Ripple started. If it has been moved
    # or deleted since, that reading is no longer true of anything -- and a
    # screen saying "the folder is gone" while offering to scan 24 files from it
    # is worse than either message on its own.
    if not folder["ok"] and _state["index"] is not None and _state["index"].files:
        _state["index"] = None
    if _state["index"] is None and str(values["repoPath"]).strip() not in ("", "."):
        start_reading()
        if _state["index"] is None:
            return _still_reading(values, folder)
    idx, parsed, cat = repo_state()
    kinds: dict[str, int] = {}
    for f in idx.files:
        kinds[f.lang] = kinds.get(f.lang, 0) + 1
    return {
        "ok": True,
        "indexing": False,
        "readError": _reading["error"],
        "build": build_info(),
        "source": "folder",
        "offline": True,
        "configured": prefs.configured(values),
        "folder": folder,
        "canBrowse": folderpick.available(),
        "settingsFile": str(paths.settings_file()),
        "historyFile": str(paths.history_file()),
        "syncedFolder": synced.detect(paths.app_dir()),
        "dialects": prefs.dialects(),
        "serverless": False,
        "limits": {"maxUploadBytes": settings.max_upload_bytes, "historyKept": True},
        "repo": {
            "label": str(values.get("repoLabel") or ""),
            "path": str(values.get("repoPath") or ""),
            "branch": settings.repo_branch,
            "files": len(idx.files),
            "statements": len(parsed.statements),
            "unreadable": len(parsed.unreadable),
            "heldOnline": len(idx.held_online),
            "pathTooLong": len(idx.too_long),
            "inSkippedDirs": len(idx.in_skipped_dirs),
            "skippedDirNames": list(idx.skipped_dir_names),
            "runsSqlFrom": len([r for r in parsed.runs_sql_from if r["runs"]]),
            "exists": folder["ok"],
            "kinds": [{"lang": k, "files": n}
                      for k, n in sorted(kinds.items(), key=lambda kv: (-kv[1], kv[0]))],
            # File types Ripple does not open, biggest first. The screen that
            # shows these is the SAME app.js the packaged build uses, so leaving
            # the key out here means this copy silently shows nothing where that
            # one shows the tally.
            "unknownExt": [
                {"ext": k, "files": n}
                for k, n in sorted(idx.unknown_ext.items(), key=lambda kv: (-kv[1], kv[0]))
            ][:12],
        },
        "catalog": {"tables": len(cat.tables),
                    "columns": sum(len(v) for v in cat.tables.values())},
        "sqlDialect": settings.sql_dialect or "generic",
        "sqlDialectId": settings.sql_dialect,
        "maxHops": settings.max_hops,
        "production": settings.production_rule(),
        "productionRule": settings.production().to_dict(),
        "productionFrom": "entered" if settings.has_production() else "unset",
        "productionSet": settings.has_production(),
    }


# ── routes ─────────────────────────────────────────────────────────────────
@router.get("/api/health")
def health() -> dict:
    return _health()


# ── knowing when to stop ───────────────────────────────────────────────────
# Without these, closing the browser leaves the program running where nobody can
# see it: the folder cannot be deleted, the port stays taken, and the only way
# out is Task Manager.
@router.post("/api/alive")
def alive() -> dict:
    """The open page saying it is still there. Sent every few seconds."""
    lifecycle.beat()
    return {"ok": True}


@router.post("/api/leaving")
def going() -> dict:
    """The page is closing. Starts a short clock rather than stopping now, so a
    refresh -- which sends exactly this -- does not take Ripple down with it."""
    lifecycle.leaving()
    return {"ok": True}


@router.post("/api/quit")
def quit_now() -> dict:
    """The Close Ripple button. Stops the program and lets go of the folder."""
    return {"ok": True, "reason": lifecycle.stop("closed from the screen")}


@router.get("/api/progress")
def progress_now() -> dict:
    """What Ripple is doing this second, asked for by the screen while it waits.

    Every number is counted rather than estimated, and where there is no total
    it says so rather than drawing a bar over a number nobody knows.
    """
    return progress.snapshot()


@router.get("/api/catalog")
def catalog() -> dict:
    _, _, cat = repo_state()
    return cat.to_dict()


@router.post("/api/reindex")
def do_reindex() -> dict:
    reindex()
    return _health()


# ── the settings, chosen on screen ─────────────────────────────────────────
@router.get("/api/settings")
def get_settings() -> dict:
    values = prefs.load()
    return {
        "values": values,
        "dialects": prefs.dialects(),
        "folder": prefs.check_folder(values["repoPath"]),
        "canBrowse": folderpick.available(),
        "settingsFile": str(paths.settings_file()),
        "historyFile": str(paths.history_file()),
    }


@router.post("/api/settings/check")
def check_settings(body: dict) -> dict:
    """Say what is in a folder before anyone commits to it."""
    return prefs.check_folder(body.get("path", ""))


@router.post("/api/settings/browse")
def browse() -> dict:
    """Open this machine's own folder picker, when there is one to open.

    Typing a path is always possible; this only saves the typing. Where the
    picker is not available the screen never offers the button, rather than
    offering one that does nothing.
    """
    if not folderpick.available():
        raise HTTPError(501, "This machine has no folder picker. "
                             "Type or paste the path instead.")
    chosen = folderpick.choose_folder()
    return {"path": chosen or "", "cancelled": not chosen}


@router.post("/api/settings")
def save_settings(body: dict) -> dict:
    """Save the folder and the dialect, then read the repository again.

    A folder that cannot be read is refused here rather than saved and
    discovered later, so the message names the folder that was actually tried.
    """
    repo_path = str(body.get("repoPath", "") or "")
    dialect = str(body.get("sqlDialect", prefs.DEFAULT_DIALECT) or prefs.DEFAULT_DIALECT)
    if not prefs.valid_dialect(dialect):
        raise HTTPError(400, "That is not a SQL dialect Ripple can read.")
    verdict = prefs.check_folder(repo_path)
    if not verdict["ok"]:
        raise HTTPError(400, verdict["message"])
    # Only two of these settings change what was read off the disk. Correcting
    # the published-table list on a repository of a few thousand files would
    # otherwise cost a full re-read -- minutes of waiting for an answer already
    # in memory, which is how somebody learns not to correct it.
    before = prefs.load()
    settled = str(Path(repo_path.strip()).resolve()) if repo_path.strip() else ""
    rereads = (str(before.get("repoPath") or "") != settled
               or str(before.get("sqlDialect") or "") != dialect
               or _state["index"] is None)
    try:
        saved = prefs.save({"repoPath": repo_path, "repoLabel": "",
                            "sqlDialect": dialect,
                            "maxHops": int(body.get("maxHops") or 0),
                            "prodTables": str(body.get("prodTables", "") or "")})
    except OSError as exc:
        # Ripple keeps its settings beside itself. Somewhere like Program Files,
        # or a network share it was opened from, may not allow that -- and
        # "Something went wrong: 500" tells nobody to move the folder.
        raise HTTPError(
            400,
            f"Ripple could not save its settings into {paths.app_dir()} "
            f"({exc.strerror or exc}). That folder does not allow writing. "
            f"Copy the whole Ripple folder somewhere you own - your Desktop or "
            f"Documents - and start it again from there.") from exc
    prefs.apply(saved)
    if rereads:
        reindex()
    return _health()


# ── the tables this team publishes ─────────────────────────────────────────
# The most expensive setting here, so it can be read back before it is saved.
# The question that matters is not "did the paste parse" but "which of these
# tables has Ripple never seen in the folder it just read".
def _production_report(rule: production.ProductionRule) -> dict:
    idx, parsed, _ = repo_state()
    return {**rule.to_dict(), "check": production.check_against_repo(rule, idx, parsed)}


@router.post("/api/production/read")
def production_read(body: dict) -> dict:
    """Read a pasted list without saving it, and say what was made of it."""
    return _production_report(production.parse(str(body.get("text", "") or "")))


@router.get("/api/production")
def production_now() -> dict:
    """The list in play, checked against the folder that is loaded."""
    return _production_report(settings.production())


# ── reading the notification ───────────────────────────────────────────────
@router.post("/api/read-email")
def read_email_file(upload: tuple) -> dict:
    name, raw = upload
    if len(raw) > settings.max_upload_bytes:
        raise HTTPError(
            413,
            f"That file is {len(raw) / 1_000_000:.1f} MB. The most this copy of "
            f"Ripple accepts is {settings.max_upload_bytes / 1_000_000:.0f} MB.")
    n = read_upload(name or "", raw)
    _, _, cat = repo_state()
    out = extract_by_rules(n, cat)
    out["emailPreview"] = {
        "subject": n.subject, "body": n.body[:4000],
        "fromName": n.from_name, "fromEmail": n.from_email,
        "attachments": n.attachments, "kind": n.source_kind,
    }
    return out


# ── scanning and writing it up ─────────────────────────────────────────────
@router.post("/api/scan")
def scan(body: dict) -> dict:
    idx, parsed, _ = repo_state()
    upstream = [{"table": u.get("table", ""), "attrs": list(u.get("attrs") or [])}
                for u in (body.get("upstream") or [])]
    if not upstream:
        raise HTTPError(400, "No upstream tables were supplied.")
    # Refused, never answered around. Without the list every table fails the
    # published test, and a scan that reaches three published tables reports
    # "no production table is affected" -- the same green tick as a genuinely
    # clean answer, over a change that breaks all of them.
    if not settings.has_production():
        raise HTTPError(
            400,
            "Ripple does not know which of your tables are the published ones yet, "
            "so it cannot say whether this change reaches any. Add them on the "
            "settings screen - paste the table names, or a pattern such as "
            "_PUBLISHED - and run this again.")
    cfg = settings
    asked = int(body.get("maxHops") or 0)
    if asked and asked != settings.max_hops:
        # The result screen offers to follow a cut-short trail further. Without
        # this the button would be pressed, the scan would run at the saved
        # depth, and the same cut-short answer would come back -- a button that
        # does nothing, on the one screen that is meant to be honest.
        cfg = copy.copy(settings)
        cfg.max_hops = max(1, min(asked, prefs.max_hops_ceiling()))
    try:
        res = trace(idx, parsed, upstream,
                    change_type=str(body.get("changeKind", "unknown") or "unknown"),
                    cfg=cfg, on_progress=progress.reader("scanning"))
    finally:
        progress.finish()
    out = res.to_dict()
    # No link template: the files are on this machine, and there is no address
    # to send anyone to. The screen offers no link rather than a broken one.
    out["repo"] = {"label": settings.repo_label, "branch": settings.repo_branch,
                   "urlTemplate": ""}
    return out


@router.post("/api/summary")
def summary(body: dict) -> dict:
    """Written from the findings by the rules. There is no AI here to fall back
    from, so this is the only path - which is why the rules-based reader had to
    be worth reading."""
    scan_out = body.get("scan") or {}
    vals = body.get("vals") or {}
    base = narrative.summarise(scan_out, vals)
    return {"summary": base, "reply": narrative.draft_reply(scan_out, vals, base)}


# ── history, which actually lasts here ─────────────────────────────────────
@router.post("/api/history")
def save_analysis(body: dict) -> dict:
    return store.save(body.get("vals") or {}, body.get("scan") or {},
                      body.get("summary") or {},
                      str(body.get("mode", "email") or "email"), settings)


@router.get("/api/history")
def history() -> list:
    return store.listing(settings)


@router.get("/api/history/{analysis_id}")
def history_item(analysis_id: str) -> dict:
    row = store.get(int(analysis_id), settings)
    if not row:
        raise HTTPError(404, "Not found.")
    return row


@router.patch("/api/history/{analysis_id}")
def history_status(analysis_id: str, body: dict) -> dict:
    if not store.set_status(int(analysis_id), str(body.get("status", "")), settings):
        raise HTTPError(400, "Unknown status or id.")
    return {"ok": True}


@router.get("/api/file")
def file_content(path: str) -> dict:
    idx, _, _ = repo_state()
    f = idx.get(path)
    if f is None:
        raise HTTPError(404, "Not in the index.")
    return {"path": f.path, "lang": f.lang, "lines": f.text.splitlines()}


# ── the offline guard, reported rather than assumed ────────────────────────
@router.get("/api/offline-check")
def offline_check() -> dict:
    """Whether this process really is barred from calling out, and what tried.

    A claim on a screen is worth nothing on its own; this is the same guard the
    tests use, answering for the copy that is actually running.
    """
    return {"guardInstalled": nonet.installed(), "attempts": list(nonet.attempts)}


# ── the site itself ────────────────────────────────────────────────────────
def mount_web() -> bool:
    """Serve the front end, from wherever this copy keeps it.

    Two places, and both are ordinary. A copy built on a machine that can
    install things generates the screens into build/web every time it starts, so
    they can never be stale. A copy carried onto a machine that cannot install
    anything has them ready-made in web/, because the thing that generates them
    was left behind with everything else that needed installing.
    """
    for web in (paths.app_dir() / "web", paths.web_dir()):
        if (web / "index.html").is_file():
            router.mount("/static", web)
            router.index(web / "index.html")
            return True
    return False
