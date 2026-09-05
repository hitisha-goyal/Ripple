"""The web service. Thin on purpose: every route is a few lines calling a module.

WHAT THIS FILE CALLS, as the other windows really wrote it. The names below were
checked against the files themselves rather than assumed, because a wrong
signature here fails at the first request and takes every number on the screen
with it:

  config.settings                       a module-level object, not get_settings()
  settings.set_production(text)         keeps production_patterns in step
  settings.production() / .production_rule() / .branch()
  repo.RepoIndex.build(root, cfg, on_progress)   root is a separate argument,
                                        and on_progress takes (done, label)
  index.files/.held_online/.too_long/.in_skipped_dirs/.skipped_dir_names/
  index.unknown_ext/.get(path)
  sqlread.parse_repo(index, cfg, on_progress)    on_progress takes
                                        (done, total, path)
  catalog.build_catalog(parsed)         a function, not Catalog.build
  production.parse_production(text) and production.check_against_repo(rule,
                                        index, parsed)
  notification.read_upload(filename, data) and
  notification.extract_by_rules(note, catalog)
  narrative.summarise(scan, vals) and narrative.draft_reply(scan, vals, summary)
  lineage.trace(index, parsed, upstream, change_type, cfg, on_progress) - upstream
                                        is [{table, attrs[]}], and on_progress
                                        takes one sentence
  lineage.settings_with_max_hops(cfg, wanted)    the clamp lives there, so this
                                        file does not keep a second copy of it
  store.save/listing/get/set_status/history_kept

THE INDEX LINEAGE WANTS IS NOT THE INDEX THE WALKER BUILDS. lineage reads
files_scanned, path_too_long, skipped_in_folders, skipped_folder_names and
unopened_extensions; repo.RepoIndex writes the same facts down under too_long,
in_skipped_dirs and unknown_ext. _ForScan below presents the one over the other.
Nothing is invented in it and no count is changed - it is names only.

THERE IS NO AI READER IN THIS BUILD. No window produced ripple/ai.py, so there
are no /api/ai routes here. The "ai" block on /api/health is still sent, and it
says plainly that no reader is available, because a screen that can say "there is
no AI here" is honest and a screen that shows a key box with nothing behind it is
not. The key box on the settings screen has to go with them.

Every route that CHANGES what Ripple is set to answers with the whole health
block rather than an acknowledgement. The page keeps one copy of that block and
replaces its copy with whatever comes back, so a route that returns {"ok": true}
leaves every number on screen showing the answer from before the change, with
nothing anywhere saying so.

The routes are plain def, not async def, on purpose: FastAPI runs a plain def in
a worker thread, so /api/progress is still answered while a scan is running. An
async def would hold the loop for the whole four minutes and the progress line
would never move.
"""

from __future__ import annotations

import copy
import os
from collections import Counter
from pathlib import Path
from threading import RLock
from typing import Any, Callable

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ripple import paths, progress, store
from ripple.build_info import VERSION, build_info
from ripple.catalog import build_catalog
from ripple.config import settings as SETTINGS
from ripple.narrative import draft_reply, summarise
from ripple.notification import extract_by_rules, read_upload
from ripple.production import check_against_repo, parse_production
from ripple.scanner import repo as repo_module
from ripple.scanner.lineage import settings_with_max_hops, trace
from ripple.scanner.repo import RepoIndex
from ripple.scanner.sqlread import parse_repo

# At most twelve file types on the health block: enough to show a pipeline
# written in something Ripple does not open, short enough to stay a status line.
MAX_UNKNOWN_EXTENSIONS = 12

# The review screen shows the email beside the fields taken out of it, and a
# whole quoted thread would push those fields off the page.
EMAIL_PREVIEW_CHARACTERS = 4000

_MONTH_SECONDS = 60 * 60 * 24 * 30

# The web folder is found through paths.web_dir() and never by walking up from
# __file__ - see the reason in Phase 1. A packaged copy has __file__ somewhere
# that walking up from does not reach.
_WEB_DIR = Path(paths.web_dir())

app = FastAPI(title="Ripple", version=VERSION)


class _Engine:
    """What has been read off the disk, kept until something re-reads it."""

    def __init__(self, settings: Any) -> None:
        self.settings = settings
        self.index: Any = None
        self.parsed: Any = None
        self.catalog: Any = None
        # Counted once, when the repository is read, because working it out on
        # every health request would walk every program file again on a page
        # load.
        self.runs_sql_from = 0
        # Where the published-table list in force came from. config.py does not
        # record this and the screen cannot do without it: without it there is no
        # telling "nobody has ever said which tables we publish" from "somebody
        # set the list this morning", and the warning that a clean result is
        # being judged against a guessed naming rule never appears at all.
        self.production_from = (
            "environment" if os.environ.get("RIPPLE_PROD_TABLES", "").strip() else "default"
        )


# ONE settings object for the whole process, and it is the one config.py itself
# holds, so run.py prints the same repository this service reads. Routes that
# change a setting change THIS object; asking config for a fresh one each time
# would quietly throw away the published-table list somebody just saved.
_engine = _Engine(settings=SETTINGS)

# Routes run on worker threads, so two page loads can arrive together. Without
# this lock they build the index twice, which on a real repository is minutes of
# work done twice and two different answers in flight.
_engine_lock = RLock()


class _ForScan:
    """The repository index under the names lineage.trace reads it by.

    repo.py and lineage.py were written in different windows and they spell the
    same four facts differently. Translating here keeps both files as their own
    window wrote them, and nothing below counts anything a second time: every
    value is handed straight through.
    """

    def __init__(self, index: Any) -> None:
        self.files = index.files
        self.files_scanned = len(index.files)
        self.held_online = list(index.held_online)
        self.path_too_long = list(index.too_long)
        self.skipped_in_folders = len(index.in_skipped_dirs)
        self.skipped_folder_names = list(index.skipped_dir_names)
        self.unopened_extensions = dict(index.unknown_ext)


def _reading_progress() -> Callable[..., None]:
    """RepoIndex.build calls back with (count, path), and no total.

    os.walk hands the files over as it finds them, so there is no denominator
    until the walk has finished - which is the moment the count stops mattering.
    The page prints a rising count and no fraction, which is the honest shape.
    """
    report = progress.reader("reading")

    def on_progress(done: int, label: str = "") -> None:
        report(done, 0, str(label))

    return on_progress


def _scanning_progress() -> Callable[..., None]:
    """lineage.trace calls back with a sentence and no numbers at all.

    The count reported here is the number of steps the walk has ANNOUNCED, which
    is a thing that really happened, and the total stays 0 because following a
    chain looks at as many statements as it turns out to need. It is not a count
    of statements, and nothing on screen should call it one.
    """
    report = progress.reader("scanning")
    steps = {"done": 0}

    def on_progress(message: str = "") -> None:
        steps["done"] += 1
        report(steps["done"], 0, str(message))

    return on_progress


def _build_index(settings: Any) -> Any:
    try:
        return RepoIndex.build(
            str(settings.repo_path), settings, on_progress=_reading_progress()
        )
    finally:
        # In a finally so a folder that cannot be read does not leave the screen
        # counting for ever.
        progress.finish()


def _parse(index: Any, settings: Any) -> Any:
    try:
        return parse_repo(index, settings, on_progress=progress.reader("parsing"))
    finally:
        progress.finish()


def _count_runs_sql_from(index: Any) -> int:
    """Programs that run SQL held in a separate .sql file Ripple did find.

    Whole folders of DAGs are written that way. Without this they read as empty
    files, and an empty file reads on every screen after it as nothing to worry
    about. Counted here rather than taken from parsed.runs_sql_from, which is the
    opposite list: the .sql files that are NOT in this repository.
    """
    known = [str(found.path) for found in index.files]
    total = 0
    for found in index.files:
        for name, _line in repo_module.sql_file_refs(found):
            tail = name.split("/")[-1].lower()
            if any(path.lower().endswith(tail) for path in known):
                total += 1
                break
    return total


def _ensure_ready() -> _Engine:
    """Build the index once and keep it until something re-reads it."""
    with _engine_lock:
        if _engine.index is None:
            _engine.index = _build_index(_engine.settings)
            _engine.runs_sql_from = _count_runs_sql_from(_engine.index)
        if _engine.parsed is None:
            _engine.parsed = _parse(_engine.index, _engine.settings)
        if _engine.catalog is None:
            _engine.catalog = build_catalog(_engine.parsed)
        return _engine


def _forget_everything() -> None:
    """Throw away everything read from the old folder.

    All four together: half of one repository and half of another answers about
    neither, and nothing on screen could show that had happened.
    """
    with _engine_lock:
        _engine.index = None
        _engine.parsed = None
        _engine.catalog = None
        _engine.runs_sql_from = 0


def _kinds(index: Any) -> list[dict[str, Any]]:
    counted = Counter(str(found.lang or "") for found in index.files)
    return [{"lang": lang, "files": total} for lang, total in counted.most_common()]


def _unknown_ext(index: Any) -> list[dict[str, Any]]:
    """The types that were not opened and could still hold a pipeline.

    repo.unopened_code_types leaves out the types known NOT to be code. A
    repository with a README, a lock file and a logo is every repository, and a
    warning that fires every time is one nobody reads.
    """
    kept = repo_module.unopened_code_types(dict(index.unknown_ext))
    rows = list(kept.items())[:MAX_UNKNOWN_EXTENSIONS]
    return [{"ext": str(ext), "files": int(total)} for ext, total in rows]


def _repo_block(engine: _Engine) -> dict[str, Any]:
    """The fourteen keys, every one counted from what was really read."""
    index = engine.index
    parsed = engine.parsed
    settings = engine.settings
    return {
        "label": str(settings.repo_label or ""),
        # Empty, never "main": a guessed branch is printed on screen as a fact.
        # config.branch() reads the folder's own .git/HEAD and returns nothing
        # when the folder was never a checkout.
        "branch": str(settings.branch() or ""),
        "path": str(index.root),
        "files": len(index.files),
        "statements": len(parsed.statements),
        "unreadable": len(parsed.unreadable),
        "heldOnline": len(index.held_online),
        "pathTooLong": len(index.too_long),
        "inSkippedDirs": len(index.in_skipped_dirs),
        "skippedDirNames": [str(name) for name in index.skipped_dir_names],
        "unknownExt": _unknown_ext(index),
        "runsSqlFrom": int(engine.runs_sql_from),
        "exists": Path(str(index.root)).is_dir(),
        "kinds": _kinds(index),
    }


def _ai_block() -> dict[str, Any]:
    """What this build can honestly say about an AI reader: that it has none.

    The block is still sent, key for key, so the screen prints "not available"
    rather than nothing at all. reason is one key more than the contract card
    names, and it is here because a blank block and a build with no reader look
    identical on screen otherwise.
    """
    return {
        "available": False,
        "model": "",
        "modelLabel": "",
        "provider": "",
        "providerLabel": "",
        "keyFrom": "",
        "models": [],
        "providers": [],
        "unsupported": [],
        "keyLasts": False,
        "reason": (
            "This build has no AI reader, so there is nowhere for a key to go. "
            "Every summary and every drafted reply is written by the rules."
        ),
    }


def _rule_json(text: str, rule: Any, one_line: str) -> dict[str, Any]:
    """The parsed published-table rule, as the settings box reads it.

    text is the paste exactly as it arrived, never a tidied version: the box is
    filled from this, and handing somebody back a cleaned-up copy of their own
    list is how a correction gets lost.
    """
    entries = [
        {"raw": entry.raw, "match": entry.match, "kind": entry.kind}
        for entry in rule.entries
    ]
    names = [entry.raw for entry in rule.entries if entry.kind == "exact"]
    patterns = [entry.raw for entry in rule.entries if entry.kind != "exact"]
    return {
        "text": text,
        "entries": entries,
        "names": names,
        "patterns": patterns,
        "nameCount": len(names),
        "patternCount": len(patterns),
        "notes": list(rule.notes),
        "column": str(rule.column_used or ""),
        "oneLine": one_line,
    }


def _production_from(engine: _Engine, rule: Any) -> str:
    """entered, environment or default.

    from_default wins whatever was typed: an empty box means the list actually in
    force is Ripple's own default, and the screen has to warn that a clean result
    is being judged against a guessed naming rule.
    """
    if getattr(rule, "from_default", False):
        return "default"
    return engine.production_from


def _health() -> dict[str, Any]:
    """The whole block, key by key.

    app.js reads whatever this returns, and a key it looks for that is not here
    fails nowhere: no error, no warning, the screen simply shows nothing where a
    number belongs and nobody finds out. Anything added here has to be added to
    every place that builds this block.
    """
    engine = _ensure_ready()
    settings = engine.settings
    rule = settings.production()
    tables = dict(engine.catalog.tables)
    return {
        "ok": True,
        "build": build_info(),
        "source": "folder",
        "limits": {
            "maxUploadBytes": int(settings.max_upload_bytes),
            "historyKept": bool(store.history_kept(settings)),
        },
        "sqlDialect": str(settings.sql_dialect or "generic"),
        "maxHops": int(settings.max_hops),
        "production": settings.production_rule(),
        "productionRule": _rule_json(
            settings.production_text, rule, settings.production_rule()
        ),
        "productionFrom": _production_from(engine, rule),
        "catalog": {
            "tables": len(tables),
            "columns": sum(len(columns) for columns in tables.values()),
        },
        "repo": _repo_block(engine),
        "ai": _ai_block(),
    }


def _rule_payload(engine: _Engine, text: str) -> dict[str, Any]:
    """The parsed rule, flat, with check sitting beside its own keys.

    Wrap the rule in a key of its own and the settings box shows an empty list of
    chips above a red warning about nothing.

    The rule is read on a COPY of the settings so that typing in the box works
    out the one-line form with exactly the code that will be used once it is
    saved, without saving it.
    """
    trial = copy.copy(engine.settings)
    rule = trial.set_production(text)
    payload = _rule_json(text, rule, trial.production_rule())
    payload["check"] = check_against_repo(rule, engine.index, engine.parsed)
    return payload


class TextIn(BaseModel):
    text: str = ""


class FolderIn(BaseModel):
    path: str = ""


class ScanIn(BaseModel):
    # One entry per table: {"table": "...", "attrs": ["...", "..."]}, which is
    # the shape the confirm screen holds and the shape lineage.trace follows. A
    # bare column name with no table cannot be followed out of anything.
    upstream: list[dict] = Field(default_factory=list)
    changeKind: str = ""
    maxHops: int | None = None


class SummaryIn(BaseModel):
    scan: dict = Field(default_factory=dict)
    vals: dict = Field(default_factory=dict)


class HistoryIn(BaseModel):
    vals: dict = Field(default_factory=dict)
    scan: dict = Field(default_factory=dict)
    summary: dict = Field(default_factory=dict)
    mode: str = ""


class StatusIn(BaseModel):
    status: str = ""


@app.middleware("http")
async def _cache_rules(request: Request, call_next: Any) -> Any:
    """No-store for the page and the script, a month for the fonts.

    During a demo or an edit, a cached script is the difference between seeing a
    change and staring at yesterday's page.
    """
    response = await call_next(request)
    path = request.url.path.lower()
    if path.endswith((".woff", ".woff2", ".ttf", ".otf")):
        response.headers["Cache-Control"] = "public, max-age=" + str(_MONTH_SECONDS)
    elif path == "/" or path.endswith((".html", ".js", ".css")):
        response.headers["Cache-Control"] = "no-store"
    return response


if _WEB_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(_WEB_DIR)), name="static")


@app.get("/")
def home() -> FileResponse:
    page = _WEB_DIR / "index.html"
    if not page.is_file():
        raise HTTPException(
            status_code=500,
            detail=(
                "The browser page was not found at "
                + str(page)
                + ". Ripple is running, but it has no screen to show."
            ),
        )
    return FileResponse(
        str(page), media_type="text/html", headers={"Cache-Control": "no-store"}
    )


@app.get("/api/health")
def health() -> dict[str, Any]:
    return _health()


@app.get("/api/progress")
def progress_now() -> dict[str, Any]:
    return progress.snapshot()


@app.get("/api/catalog")
def catalog_now() -> dict[str, Any]:
    """Everything learned from the CREATE statements.

    The counts are tableCount and columnCount HERE, and tables and columns inside
    /api/health. Two shapes, two sets of names, and the same screen reads both.
    """
    engine = _ensure_ready()
    tables = {
        str(name): [str(column) for column in columns]
        for name, columns in engine.catalog.tables.items()
    }
    return {
        "tables": tables,
        "definedIn": {
            str(name): str(where) for name, where in engine.catalog.defined_in.items()
        },
        "gaps": [gap.to_json() for gap in engine.catalog.gaps],
        "tableCount": len(tables),
        "columnCount": sum(len(columns) for columns in tables.values()),
    }


@app.post("/api/reindex")
def reindex() -> dict[str, Any]:
    _forget_everything()
    return _health()


@app.get("/api/production")
def production_now() -> dict[str, Any]:
    engine = _ensure_ready()
    return _rule_payload(engine, engine.settings.production_text)


@app.post("/api/production/read")
def production_read(body: TextIn) -> dict[str, Any]:
    """Read a pasted list WITHOUT saving it. The settings box types into this."""
    engine = _ensure_ready()
    return _rule_payload(engine, body.text)


@app.post("/api/production")
def production_save(body: TextIn) -> dict[str, Any]:
    """Use this list from now on.

    _ensure_ready() builds nothing that is already built, so saving the list
    never re-reads the repository. Which tables count as published changes
    nothing about the files that were read off the disk, and charging somebody
    minutes for correcting a typo is how a typo stays uncorrected - on the one
    setting that decides whether "no production table is impacted" is a result or
    an accident.
    """
    engine = _ensure_ready()
    with _engine_lock:
        # set_production, not an assignment: it also refreshes the parsed rule
        # and the match patterns every scan reads.
        engine.settings.set_production(body.text)
        engine.production_from = "entered"
    return _health()


@app.post("/api/repo/folder")
def repo_folder(body: FolderIn) -> dict[str, Any]:
    """Read THIS folder on this machine from now on."""
    # Windows Explorer's "Copy as path" wraps the path in quotation marks, and
    # pasting that in is the single most likely thing anybody will do.
    cleaned = str(body.path or "").strip().strip('"').strip("'").strip()
    if not cleaned:
        raise HTTPException(
            status_code=400,
            detail=(
                "No folder was given. Paste the full path to the folder that "
                "holds the pipeline code, for example C:\\work\\pipelines."
            ),
        )
    folder = Path(cleaned).expanduser()
    if not folder.exists():
        # Accepted quietly this indexes zero files, and zero files found reads on
        # every screen after it as "no impact" - the one sentence this tool may
        # never get wrong.
        raise HTTPException(
            status_code=400,
            detail=(
                "There is no folder at "
                + str(folder)
                + ". That is almost always a typo in the path rather than an "
                "empty repository, so nothing has been changed. Check the path "
                "and paste it again."
            ),
        )
    if not folder.is_dir():
        raise HTTPException(
            status_code=400,
            detail=(
                str(folder)
                + " is a file, not a folder. Point Ripple at the folder that "
                "holds the pipeline code, not at one file inside it."
            ),
        )
    settled = folder.resolve()
    with _engine_lock:
        _forget_everything()
        _engine.settings.repo_path = settled
        if not os.environ.get("RIPPLE_REPO_LABEL", "").strip():
            # The heading is the folder's name unless somebody named the
            # repository themselves. Left alone it would go on printing the name
            # of the folder Ripple has just stopped reading.
            _engine.settings.repo_label = settled.name
    return _health()


@app.post("/api/read-email")
def read_email(file: UploadFile = File(...)) -> dict[str, Any]:
    """Read an uploaded .msg, .eml or plain text file.

    There is no route that takes typed-in email text. There was one, and a box
    somebody pastes an email into produces a notification with no envelope - no
    From, no Subject, nothing but words - so the source system and the contact
    came back blank far more often than from the same email uploaded as a file.
    """
    engine = _ensure_ready()
    data = file.file.read()
    ceiling = int(engine.settings.max_upload_bytes)
    if len(data) > ceiling:
        raise HTTPException(
            status_code=413,
            detail=(
                "That file is "
                + format(len(data), ",")
                + " bytes and the biggest this build will accept is "
                + format(ceiling, ",")
                + " bytes. The whole file is held in memory while it is read, "
                "which is why there is a ceiling at all. Save the message on its "
                "own, without the attachments, and upload that."
            ),
        )
    note = read_upload(str(file.filename or ""), data)
    payload = dict(extract_by_rules(note, engine.catalog))
    # The review screen shows the email beside the fields pulled out of it.
    # Without this there is no way on screen to check a field against the
    # sentence it came from, which is the entire point of asking somebody to
    # confirm before anything is scanned.
    payload["emailPreview"] = {
        "subject": str(note.subject or ""),
        "body": str(note.body or "")[:EMAIL_PREVIEW_CHARACTERS],
        "fromName": str(note.from_name or ""),
        "fromEmail": str(note.from_email or ""),
        "attachments": [str(name) for name in note.attachments],
        # notification.py records which of the three shapes it read as
        # source_kind; the screen reads it as kind.
        "kind": str(note.source_kind or ""),
    }
    return payload


@app.post("/api/scan")
def scan(body: ScanIn) -> dict[str, Any]:
    upstream: list[dict[str, Any]] = []
    for entry in body.upstream:
        if not isinstance(entry, dict):
            continue
        table = str(entry.get("table", "") or "").strip()
        attrs = [
            str(attr).strip()
            for attr in (entry.get("attrs") or [])
            if str(attr).strip()
        ]
        if table and attrs:
            upstream.append({"table": table, "attrs": attrs})
    if not upstream:
        raise HTTPException(
            status_code=400,
            detail=(
                "No table and column were sent, so there is nothing to follow. "
                "Nothing is scanned until the names have been confirmed on "
                "screen - a request carrying none is a mistake, not an "
                "instruction to search everything."
            ),
        )
    engine = _ensure_ready()
    # A copy for this one scan when a depth was asked for, so following one trail
    # deeper does not quietly change every later scan. The clamp lives in
    # lineage, which owns the ceiling.
    settings = settings_with_max_hops(engine.settings, body.maxHops)
    try:
        found = trace(
            _ForScan(engine.index),
            engine.parsed,
            upstream,
            str(body.changeKind or ""),
            settings,
            on_progress=_scanning_progress(),
        )
    finally:
        # Including when the scan FAILS, or the screen counts for ever.
        progress.finish()
    result = found.to_json()
    result["repo"] = {
        "label": str(engine.settings.repo_label or ""),
        "branch": str(engine.settings.branch() or ""),
        # On a folder there is no address to send anyone to, so the screen offers
        # no link rather than a broken one.
        "urlTemplate": "",
    }
    return result


@app.post("/api/summary")
def summary(body: SummaryIn) -> dict[str, Any]:
    """The written summary and the drafted reply, both by the rules.

    draft_reply is given the summary because the letter is assembled from what
    the summary already worked out. A screen and a letter that disagree about how
    much of the repository was read are worse than either one alone.
    """
    written = summarise(body.scan, body.vals)
    return {
        "summary": written,
        "reply": draft_reply(body.scan, body.vals, written),
    }


@app.post("/api/history")
def history_save(body: HistoryIn) -> dict[str, Any]:
    return store.save(
        body.vals, body.scan, body.summary, body.mode, _engine.settings
    )


@app.get("/api/history")
def history_list() -> dict[str, Any]:
    return store.listing(_engine.settings)


@app.get("/api/history/{item_id}")
def history_one(item_id: int) -> dict[str, Any]:
    answer = store.get(item_id, _engine.settings)
    if answer["available"] and not answer["found"]:
        raise HTTPException(
            status_code=404,
            detail="There is no saved analysis numbered " + str(item_id) + ".",
        )
    return answer


@app.patch("/api/history/{item_id}")
def history_status(item_id: int, body: StatusIn) -> dict[str, Any]:
    return store.set_status(item_id, body.status, _engine.settings)


@app.get("/api/file")
def file_text(path: str = "") -> dict[str, Any]:
    """The real text of a scanned file.

    Only files that are really in the index are served. A path that is not one of
    them is refused rather than read off the disk: this route would otherwise
    hand out any file on the machine to anything that could reach the port.
    """
    engine = _ensure_ready()
    wanted = str(path or "").replace("\\", "/").strip()
    found = engine.index.get(wanted) if wanted else None
    if found is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "No file called "
                + wanted
                + " was read in this repository, so its text cannot be shown."
            ),
        )
    return {"path": found.path, "lang": found.lang, "text": found.text}
