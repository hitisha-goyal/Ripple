"""The offline web service.

The same shape as the online one, minus everything that reaches out. There is
no GitHub route and no AI route — not disabled, not behind a flag, absent — so
there is no key to leak, no address to type, and nothing that can quietly start
working because the machine turned out to have internet after all.

What is here instead: the two settings that were environment variables online,
asked for on screen and remembered in a file beside the executable.

Every route below calls the shared engine in ``Codebase/ripple``. Nothing about
scanning, reading SQL, tracing lineage or writing the summary is reimplemented
here — this is a thin layer, exactly as the online service is.
"""
from __future__ import annotations

import copy
import threading
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import folderpick, lifecycle, nonet, paths, prefs, synced

# The shared engine. Importing this package has already put it on the path.
from ripple import narrative, production, progress, store          # noqa: E402
from ripple.build_info import build_info                           # noqa: E402
from ripple.catalog import Catalog, build_catalog                  # noqa: E402
from ripple.config import settings                                 # noqa: E402
from ripple.notification import extract_by_rules, read_upload  # noqa: E402
from ripple.scanner.lineage import trace                           # noqa: E402
from ripple.scanner.repo import RepoIndex                          # noqa: E402
from ripple.scanner.sqlread import ParsedRepo, parse_repo          # noqa: E402

app = FastAPI(title="Ripple Offline", docs_url="/api/docs", redoc_url=None)

_state: dict[str, Any] = {"index": None, "parsed": None, "catalog": None}

# ── reading without holding the screen hostage ─────────────────────────────
# Reading a repository the size of a real warehouse takes minutes, and /api/health
# is the request the screen makes before it can paint anything at all. Measured
# on 7,304 files: 101 seconds in there, during which the window is blank and has
# no way to ask what is happening -- because the only request that would tell it
# is the one it is already waiting on. A working program that says nothing for a
# hundred seconds gets reported as a hung one, and here that window is the whole
# product.
#
# So the read happens on a thread, health answers straight away with
# indexing:true, and the screen shows the counted file numbers that were always
# being recorded and never had anywhere to go.
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
            except Exception as exc:                       # noqa: BLE001
                # Kept and shown. A read that failed and a read that never
                # finished look identical from the screen, and one of them needs
                # somebody to go and do something about it.
                _reading["error"] = str(exc)
            finally:
                progress.finish()

        t = threading.Thread(target=work, name="ripple-read", daemon=True)
        _reading["thread"] = t
        t.start()


# ── the repository, read once and kept until something changes ─────────────
def repo_state() -> tuple[RepoIndex, ParsedRepo, Catalog]:
    # One reader at a time: the first read now happens on a thread while other
    # requests keep arriving, and two threads reading the same repository would
    # do all of it twice and then disagree about which answer to keep.
    with _build_lock:
        return _read_if_needed()


def _read_if_needed() -> tuple[RepoIndex, ParsedRepo, Catalog]:
    if _state["index"] is None:
        # A folder that is missing, or has never been chosen, is a normal state
        # here rather than an error: the index comes back empty and the screen
        # says why. Nothing crashes and nothing pretends to have scanned.
        #
        # An unset folder is an empty path, which as a path means "here" -- so
        # without this Ripple would index its own program folder and present it
        # as the repository, which is worse than finding nothing.
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
    screen that no test would ever see -- see test_offline_app.
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
            "branch": settings.branch(),
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
    # screen that says "the folder is gone" while offering to scan 24 files
    # from it is worse than either message on its own.
    if not folder["ok"] and _state["index"] is not None and _state["index"].files:
        _state["index"] = None
    # Still reading: answer now, with the counted progress, rather than holding
    # the window blank for the minutes a real repository takes. See start_reading.
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
        # Which build this is. It matters most here: this is the copy running
        # on a machine nobody can check, and an old one looks exactly like a
        # new one. Written into the folder by build.py at packaging time.
        "build": build_info(),
        "source": "folder",
        # Said out loud so the screen can state it rather than imply it.
        "offline": True,
        "configured": prefs.configured(values),
        "folder": folder,
        "canBrowse": folderpick.available(),
        "settingsFile": str(paths.settings_file()),
        "historyFile": str(paths.history_file()),
        # Whether Ripple's own folder is one something uploads to the cloud. It
        # changes two things a person should know about rather than find out:
        # the saved history is a database file in there, and the whole program
        # is going up with it.
        "syncedFolder": synced.detect(paths.app_dir()),
        "dialects": prefs.dialects(),
        "serverless": False,
        "limits": {
            "maxUploadBytes": settings.max_upload_bytes,
            # A real disk, so saved analyses genuinely last.
            "historyKept": True,
        },
        "repo": {
            "label": prefs.folder_label(values["repoPath"]) or "no folder chosen",
            "branch": settings.branch(),
            "path": values["repoPath"],
            "files": len(idx.files),
            "statements": len(parsed.statements),
            "unreadable": len(parsed.unreadable),
            # Files never opened at all. This build is the one that meets them:
            # it runs where there is no internet, so a file OneDrive is holding
            # online-only can never be fetched.
            "heldOnline": len(idx.held_online),
            "pathTooLong": len(idx.too_long),
            # Code files Ripple walked past because of the folder they sit in.
            "inSkippedDirs": len(idx.in_skipped_dirs),
            "skippedDirNames": list(idx.skipped_dir_names),
            # Programs that run SQL kept in a separate .sql file. Two folders of
            # DAGs are written that way, and without this they read as empty.
            "runsSqlFrom": len([r for r in parsed.runs_sql_from if r["runs"]]),
            "exists": folder["ok"],
            "kinds": [{"lang": k, "files": n}
                      for k, n in sorted(kinds.items(), key=lambda kv: (-kv[1], kv[0]))],
            # File types Ripple does not open, biggest first. The screen that
            # shows these is the SAME app.js the online build uses, so leaving
            # the key out here means the offline copy silently shows nothing
            # where the online one shows the tally.
            "unknownExt": [
                {"ext": k, "files": n}
                for k, n in sorted(idx.unknown_ext.items(), key=lambda kv: (-kv[1], kv[0]))
            ][:12],
        },
        "catalog": {"tables": len(cat.tables),
                    "columns": sum(len(v) for v in cat.tables.values())},
        "sqlDialect": settings.sql_dialect or "generic",
        # The stored value as well as the readable one: generic SQL is the
        # empty string, and the settings screen has to be able to select it.
        "sqlDialectId": settings.sql_dialect,
        "maxHops": settings.max_hops,
        # Which table names count as the ones this team publishes. On screen so
        # that "no production table is impacted" can be checked rather than
        # believed -- it is only ever as true as this rule is. The one-line form
        # is for a status row; the full one is what the settings screen shows,
        # and it holds the paste exactly as it arrived so it can be edited again.
        "production": settings.production_rule(),
        "productionRule": settings.production().to_dict(),
        # Where the list came from, and whether there is one at all. The screens
        # gate on these rather than on the text being non-empty, so both builds
        # give the same answer to the same question.
        "productionFrom": "entered" if settings.has_production() else "unset",
        "productionSet": settings.has_production(),
        # The repository is read and every number above is real.
        "indexing": False,
        "readError": _reading["error"],
        "progress": progress.snapshot(),
    }


# ── models ─────────────────────────────────────────────────────────────────
class UpstreamIn(BaseModel):
    table: str
    attrs: list[str] = []
    # The table itself is changing -- dropped, renamed, moved, rebuilt -- and
    # every statement that reads it is what is asked about. Never inferred
    # from an empty attrs: a table with nothing on it is refused, see scan().
    whole: bool = False


class ScanIn(BaseModel):
    upstream: list[UpstreamIn]
    changeKind: str = "unknown"
    # For this scan only, when a trail was cut short by the hop limit and the
    # screen offered to follow it further. Saved settings are left alone.
    maxHops: int | None = None


class SummaryIn(BaseModel):
    scan: dict
    vals: dict


class SaveIn(BaseModel):
    vals: dict
    scan: dict
    summary: dict
    mode: str = "email"


class StatusIn(BaseModel):
    status: str


class PathIn(BaseModel):
    path: str = ""


class ProductionIn(BaseModel):
    text: str = ""


class SettingsIn(BaseModel):
    repoPath: str = ""
    sqlDialect: str = prefs.DEFAULT_DIALECT
    # Missing means "keep whatever is saved". ZERO means something real and
    # different -- follow the trail to the end of the code -- and the two were
    # the same value here while the comment claimed otherwise, so a screen that
    # left the box alone silently reset the setting.
    maxHops: int | None = None
    prodTables: str = ""


# ── routes ─────────────────────────────────────────────────────────────────
@app.get("/api/health")
def health() -> dict:
    return _health()


# ── knowing when to stop ───────────────────────────────────────────────────
# Without these, closing the browser leaves the program running where nobody can
# see it: the folder cannot be deleted, the port stays taken, and the only way
# out is Task Manager. See ripple_offline/lifecycle.py.
@app.post("/api/alive")
def alive() -> dict:
    """The open page saying it is still there. Sent every few seconds."""
    lifecycle.beat()
    return {"ok": True}


@app.post("/api/leaving")
def going() -> dict:
    """The page is closing. Starts a short clock rather than stopping now, so a
    refresh -- which sends exactly this -- does not take Ripple down with it."""
    lifecycle.leaving()
    return {"ok": True}


@app.post("/api/quit")
def quit_now() -> dict:
    """The Close Ripple button. Stops the program and lets go of the folder."""
    return {"ok": True, "reason": lifecycle.stop("closed from the screen")}


@app.get("/api/progress")
def progress_now() -> dict:
    """What Ripple is doing this second, asked for by the screen while it waits.

    This build is the one that meets a repository of a few thousand files on a
    laptop, where reading it takes minutes. Every number is counted rather than
    estimated, and where there is no total it says so rather than drawing a bar.
    """
    return progress.snapshot()


@app.get("/api/catalog")
def catalog() -> dict:
    _, _, cat = repo_state()
    return cat.to_dict()


@app.post("/api/reindex")
def do_reindex() -> dict:
    reindex()
    return _health()


# ── the two settings, chosen on screen ─────────────────────────────────────
@app.get("/api/settings")
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


@app.post("/api/settings/check")
def check_settings(payload: PathIn) -> dict:
    """Say what is in a folder before anyone commits to it."""
    return prefs.check_folder(payload.path)


# ── the tables this team publishes ─────────────────────────────────────────
# The most expensive setting here, so it can be read back before it is saved.
# The question that matters is not "did the paste parse" but "which of these
# tables has Ripple never seen in the folder it just read".
def _production_report(rule: production.ProductionRule) -> dict:
    idx, parsed, _ = repo_state()
    return {**rule.to_dict(), "check": production.check_against_repo(rule, idx, parsed)}


@app.post("/api/production/read")
def production_read(payload: ProductionIn) -> dict:
    """Read a pasted list without saving it, and say what was made of it."""
    return _production_report(production.parse(payload.text or ""))


@app.get("/api/production")
def production_now() -> dict:
    """The list in play, checked against the folder that is loaded."""
    return _production_report(settings.production())


@app.post("/api/settings/browse")
def browse() -> dict:
    """Open this machine's own folder picker, when there is one to open.

    Typing a path is always possible; this only saves the typing. If the picker
    is not available the screen never offers the button, rather than offering
    one that does nothing.
    """
    if not folderpick.available():
        raise HTTPException(status_code=501,
                            detail="This machine has no folder picker. Type or paste the path instead.")
    chosen = folderpick.choose_folder()
    return {"path": chosen or "", "cancelled": not chosen}


@app.post("/api/settings")
def save_settings(payload: SettingsIn) -> dict:
    """Save the folder and the dialect, then read the repository again.

    A folder that cannot be read is refused here rather than saved and
    discovered later, so the message names the folder that was actually tried.
    """
    if not prefs.valid_dialect(payload.sqlDialect):
        raise HTTPException(status_code=400, detail="That is not a SQL dialect Ripple can read.")
    verdict = prefs.check_folder(payload.repoPath)
    if not verdict["ok"]:
        raise HTTPException(status_code=400, detail=verdict["message"])
    # Only two of these settings change what was read off the disk. Correcting
    # the published-table list on a repository of a few thousand files used to
    # cost a full re-read -- minutes of waiting for an answer that was already
    # in memory, which is how somebody learns not to correct it.
    before = prefs.load()
    rereads = (str(before.get("repoPath") or "") != str(Path(payload.repoPath.strip()).resolve()
                                                        if payload.repoPath.strip() else "")
               or str(before.get("sqlDialect") or "") != payload.sqlDialect
               or _state["index"] is None)
    try:
        saved = prefs.save({
            "repoPath": payload.repoPath, "repoLabel": "",
            "sqlDialect": payload.sqlDialect,
            # Left out of the request means leave it alone. See SettingsIn.
            "maxHops": before.get("maxHops") if payload.maxHops is None else payload.maxHops,
            "prodTables": payload.prodTables})
    except OSError as exc:
        # Ripple keeps its settings beside itself. Somewhere like Program Files,
        # or a network share it was opened from, may not allow that -- and
        # "Something went wrong: 500" tells nobody to move the folder.
        raise HTTPException(
            status_code=400,
            detail=(f"Ripple could not save its settings into {paths.app_dir()} "
                    f"({exc.strerror or exc}). That folder does not allow writing. "
                    f"Copy the whole Ripple folder somewhere you own — your Desktop or "
                    f"Documents — and start it again from there.")) from exc
    prefs.apply(saved)
    if rereads:
        reindex()
    return _health()


# ── reading the notification ───────────────────────────────────────────────
def _extract(n) -> dict:
    _, _, cat = repo_state()
    return extract_by_rules(n, cat)


@app.post("/api/read-email")
async def read_email_file(file: UploadFile = File(...)) -> dict:
    raw = await file.read()
    if len(raw) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail=(f"That file is {len(raw) / 1_000_000:.1f} MB. The most this copy of "
                    f"Ripple accepts is {settings.max_upload_bytes / 1_000_000:.0f} MB."))
    n = read_upload(file.filename or "", raw)
    out = _extract(n)
    out["emailPreview"] = {
        "subject": n.subject, "body": n.body[:4000],
        "fromName": n.from_name, "fromEmail": n.from_email,
        "attachments": n.attachments, "kind": n.source_kind,
    }
    return out


# ── scanning and writing it up ─────────────────────────────────────────────
@app.post("/api/scan")
def scan(payload: ScanIn) -> dict:
    idx, parsed, cat = repo_state()
    upstream = [{"table": u.table, "attrs": u.attrs, "whole": bool(u.whole)}
                for u in payload.upstream]
    if not upstream:
        raise HTTPException(status_code=400, detail="No upstream tables were supplied.")
    # Refused, never answered around. A table with no attribute on it used to
    # go through the column walk with nothing to walk, and came back "no usage
    # found" -- a clean answer to a question that was never asked.
    for u in upstream:
        if not u["attrs"] and not u["whole"]:
            raise HTTPException(status_code=400, detail=(
                f"{u['table']} has no attribute on it and is not marked as a whole-table "
                f"change. Add the attribute that is changing, or tick 'Whole table' to follow "
                f"every column and every statement that reads it."))
    # Refused, never answered around. Without the list every table fails the
    # published test, and a scan that reaches three published tables reports
    # "no production table is affected" -- the same green tick as a genuinely
    # clean answer, over a change that breaks all of them.
    if not settings.has_production():
        raise HTTPException(
            status_code=400,
            detail=("Ripple does not know which of your tables are the published ones yet, "
                    "so it cannot say whether this change reaches any. Add them on the "
                    "settings screen — paste the table names, or a pattern such as "
                    "_PUBLISHED — and run this again."))
    cfg = settings
    # ``is not None``, never truthiness. Zero is a real choice -- "follow it to
    # the end of the code" -- and read as falsy the deeper button sent its
    # request, the saved limit was used anyway, and the same cut-short answer
    # came back: a button that does nothing.
    if payload.maxHops is not None and payload.maxHops != settings.max_hops:
        # The result screen offers to follow a cut-short trail further. Without
        # this the button would be pressed, the scan would run at the saved
        # depth, and the same cut-short answer would come back -- a button that
        # does nothing, on the one screen that is meant to be honest.
        cfg = copy.copy(settings)
        cfg.max_hops = prefs.clamp_hops(payload.maxHops)
    try:
        res = trace(idx, parsed, upstream, change_type=payload.changeKind, cfg=cfg,
                    on_progress=progress.reader("scanning"), catalog=cat)
    finally:
        progress.finish()
    out = res.to_dict()
    # No link template: the files are on this machine, and there is no address
    # to send anyone to. The screen offers no link rather than a broken one.
    out["repo"] = {"label": settings.repo_label, "branch": settings.branch(),
                   "urlTemplate": ""}
    return out


@app.post("/api/summary")
def summary(payload: SummaryIn) -> dict:
    """Written from the findings by the rules. There is no AI here to fall back
    from, so this is the only path — which is why the rules-based reader had to
    be worth reading."""
    base = narrative.summarise(payload.scan, payload.vals)
    return {"summary": base,
            "reply": narrative.draft_reply(payload.scan, payload.vals, base)}


# ── history, which actually lasts here ─────────────────────────────────────
@app.post("/api/history")
def save_analysis(payload: SaveIn) -> dict:
    return store.save(payload.vals, payload.scan, payload.summary, payload.mode, settings)


@app.get("/api/history")
def history() -> list[dict]:
    return store.listing(settings)


@app.get("/api/history/{analysis_id}")
def history_item(analysis_id: int) -> dict:
    row = store.get(analysis_id, settings)
    if not row:
        raise HTTPException(status_code=404, detail="Not found.")
    return row


@app.patch("/api/history/{analysis_id}")
def history_status(analysis_id: int, payload: StatusIn) -> dict:
    if not store.set_status(analysis_id, payload.status, settings):
        raise HTTPException(status_code=400, detail="Unknown status or id.")
    return {"ok": True}


@app.get("/api/file")
def file_content(path: str) -> dict:
    idx, _, _ = repo_state()
    f = idx.get(path)
    if f is None:
        raise HTTPException(status_code=404, detail="Not in the index.")
    return {"path": f.path, "lang": f.lang, "lines": f.text.splitlines()}


# ── the offline guard, reported rather than assumed ────────────────────────
@app.get("/api/offline-check")
def offline_check() -> dict:
    """Whether this process really is barred from calling out, and what tried.

    A claim on a screen is worth nothing on its own; this is the same guard the
    tests use, answering for the copy that is actually running.
    """
    return {"guardInstalled": nonet.installed(), "attempts": list(nonet.attempts)}


# ── the site itself ────────────────────────────────────────────────────────
@app.middleware("http")
async def cache_rules(request, call_next):
    """The page and its script are never cached: during a demo that is the
    difference between seeing a change and staring at yesterday's page. The
    fonts are cached — they are 350 KB, they never change, and here they are
    read straight off the disk anyway."""
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/static/fonts/") and path.endswith(".woff2"):
        response.headers["Cache-Control"] = "public, max-age=2592000"
    elif path.startswith("/static") or path == "/":
        response.headers["Cache-Control"] = "no-store, must-revalidate"
    return response


def mount_web() -> bool:
    """Serve the built offline front end, if it has been built."""
    web = paths.web_dir()
    if not (web / "index.html").is_file():
        return False
    app.mount("/static", StaticFiles(directory=web), name="static")
    return True


if mount_web():
    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(paths.web_dir() / "index.html")
else:  # pragma: no cover - only when the front end was never built
    @app.get("/")
    def index() -> JSONResponse:
        return JSONResponse(
            {"error": "The offline front end has not been built yet. Run build.py, "
                      "or start Ripple with run.py which builds it first."},
            status_code=500)
