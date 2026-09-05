"""The web service.

Thin on purpose: every route is a few lines that call the scanner, the reader
or the writer. All of the thinking lives in those modules, so the same logic
runs from the command line, from a test, or from this API.
"""
from __future__ import annotations

import copy
import os
import threading
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from dataclasses import replace

from . import ai, narrative, production, progress, store
from .build_info import build_info
from .catalog import Catalog, build_catalog
from . import providers
from .config import Settings, settings
from .notification import Notification, extract_by_rules, read_upload
from .scanner import github as ghub
from .scanner.lineage import trace
from .scanner.repo import RepoIndex
from .scanner.sqlread import ParsedRepo, parse_repo

WEB_DIR = Path(__file__).resolve().parent.parent / "web"

app = FastAPI(title="Ripple", docs_url="/api/docs", redoc_url=None)

# ── the index, built once and reused ───────────────────────────────────────
# "token" is a secret held only in this process. It is never written to disk,
# never logged, and never put in a response -- routes report whether one is set,
# never what it is.
_state: dict[str, Any] = {
    "index": None, "parsed": None, "catalog": None,
    "source": "folder", "conn": None, "token": "", "error": "",
    # The AI key is a secret on exactly the same terms as the GitHub token:
    # held here while the process runs, and nowhere else, ever.
    "aiKey": "", "aiModel": "", "aiModels": [],
    # Whether the published-table list in play was typed into the screen rather
    # than set on the host. It changes one thing worth saying out loud: a typed
    # list is gone when this server restarts.
    "prodEntered": False,
}


# The thread doing the first read, and the lock that stops two starting. See
# health() for why this exists at all.
_reading_lock = threading.Lock()
_reading: dict[str, Any] = {"thread": None, "error": ""}


def _start_reading() -> None:
    """Begin reading the repository on a thread, unless one is already at it."""
    with _reading_lock:
        alive = _reading["thread"]
        if alive is not None and alive.is_alive():
            return

        def work() -> None:
            try:
                _reading["error"] = ""
                repo_state()
            except Exception as exc:                       # noqa: BLE001
                # Kept and shown rather than swallowed. A read that failed and a
                # read that never finished look identical from the screen, and
                # one of them needs somebody to go and do something.
                _reading["error"] = str(exc)
            finally:
                progress.finish()

        t = threading.Thread(target=work, name="ripple-read", daemon=True)
        _reading["thread"] = t
        t.start()


def _still_reading() -> dict:
    """The health answer while the repository is being read for the first time.

    Deliberately the same shape as the real one, with the counts at zero and
    ``indexing`` true. A screen given half a payload has to guess at the rest,
    and every guess it makes is a number on screen that nothing counted.
    """
    return {
        "ok": True,
        "indexing": True,
        "readError": _reading["error"],
        "progress": progress.snapshot(),
        "build": build_info(),
        "source": _state["source"],
        "github": None,
        "tokenSet": bool(_active_token()),
        "tokenFrom": _token_origin(),
        "connectError": _state["error"],
        "error": _state["error"],
        "serverless": settings.serverless,
        "limits": {
            "maxUploadBytes": settings.max_upload_bytes,
            "maxRepoBytes": settings.max_repo_bytes,
            "historyKept": not settings.serverless,
        },
        "repo": {
            "label": settings.repo_label,
            "path": str(settings.repo_path),
            "branch": settings.branch(),
            "files": 0, "statements": 0, "unreadable": 0, "kinds": [],
            "heldOnline": 0, "pathTooLong": 0, "inSkippedDirs": 0,
            "skippedDirNames": [], "unknownExt": [],
            "exists": settings.repo_path.exists(),
        },
        "catalog": {"tables": 0, "columns": 0},
        "sqlDialect": settings.sql_dialect or "generic",
        "maxHops": settings.max_hops,
        "production": settings.production_rule(),
        "productionRule": settings.production().to_dict(),
        "productionFrom": _production_origin(),
        "productionSet": settings.has_production(),
        "ai": _ai_facts(),
    }


def _active_token() -> str:
    """A token typed into the app wins over one set in the environment."""
    return _state["token"] or settings.github_token


def _ai_cfg() -> Settings:
    """Settings as the AI should see them, with anything typed in applied.

    A copy is made rather than the global being edited, so a key entered on the
    screen can be forgotten again by clearing one value -- and so nothing else
    in the app can accidentally read it.
    """
    return replace(
        settings,
        ai_key=_state["aiKey"] or settings.ai_key,
        ai_model=_state["aiModel"] or settings.ai_model,
    )


def _ai_facts() -> dict:
    """What the screen may know about the AI -- never the key itself."""
    cfg = _ai_cfg()
    found = cfg.ai_provider()
    return {
        "available": cfg.ai_available(),
        "model": cfg.ai_model,
        # The model id IS the label now. A hand-written pretty name for every
        # model of every provider is a list that rots, and a wrong pretty name
        # on screen is worse than the real id, which somebody can search for.
        "modelLabel": (f"{found['label']} - {cfg.ai_model}" if found and cfg.ai_model
                       else cfg.ai_model or (found["label"] if found else "")),
        "provider": found["id"] if found else "",
        "providerLabel": found["label"] if found else "",
        # Where the key came from, so "it stopped working" has an explanation.
        "keyFrom": "entered" if _state["aiKey"] else ("environment" if settings.ai_key else ""),
        # The models this key can really use, fetched from the provider when the
        # key was accepted. Empty until then -- never a guessed list.
        "models": list(_state.get("aiModels") or []),
        # So the screen can name the provider as the key is typed, before
        # anything is sent anywhere. One box, not one box per company.
        "providers": [
            {"id": pr["id"], "label": pr["label"], "prefixes": list(pr["prefixes"]),
             "where": pr["where"]}
            for pr in providers.PROVIDERS
        ],
        "unsupported": [
            {"label": u["label"], "prefixes": list(u["prefixes"])}
            for u in providers.KNOWN_BUT_UNSUPPORTED
        ],
        # A key typed in here dies with the machine, and while it lives anyone
        # else using this copy of Ripple is spending it. The screen says both.
        "keyLasts": not settings.serverless,
    }


def _install(idx: RepoIndex, source: str, conn: "ghub.Connection | None") -> None:
    parsed = parse_repo(idx, settings, on_progress=progress.reader("parsing"))
    _state.update({
        "index": idx, "parsed": parsed, "catalog": build_catalog(parsed),
        "source": source, "conn": conn,
    })
    progress.finish()


def _use_folder() -> None:
    idx = RepoIndex.build(settings.repo_path, settings,
                          on_progress=progress.reader("reading"))
    _install(idx, "folder", None)


def _use_github(repo: str, token: str, branch: str) -> None:
    idx, conn = ghub.connect(repo, token, branch, settings)
    _install(idx, "github", conn)
    _state["error"] = ""


def repo_state() -> tuple[RepoIndex, ParsedRepo, Catalog]:
    """The current repository, built on first use and kept until re-read.

    If GitHub is configured but cannot be reached, Ripple falls back to the
    local folder and remembers why, so the screen can say so rather than the
    whole app failing.
    """
    # One reader at a time. The first read now happens on a thread (see
    # _start_reading) while other requests keep arriving, and two threads
    # reading the same repository at once would do all of it twice and then
    # disagree about which answer to keep.
    with _build_lock:
        return _build_if_needed()


_build_lock = threading.RLock()


def _build_if_needed() -> tuple[RepoIndex, ParsedRepo, Catalog]:
    if _state["index"] is None:
        if settings.repo_source == "github" and settings.github_repo:
            token = _active_token()
            if not token:
                _state["error"] = ("GitHub is configured but no access token is set. "
                                   "Add one on the Repository step, or set GITHUB_TOKEN.")
                _use_folder()
            else:
                try:
                    _use_github(settings.github_repo, token, settings.github_branch)
                except ghub.GitHubError as exc:
                    _state["error"] = str(exc)
                    _use_folder()
        else:
            _use_folder()
    return _state["index"], _state["parsed"], _state["catalog"]


def reindex() -> None:
    """Read the repository again from wherever it currently comes from."""
    source, conn = _state["source"], _state["conn"]
    _state["index"] = None
    if source == "github" and conn is not None:
        _use_github(conn.ref.slug, _active_token(), conn.branch)
    else:
        _state["index"] = None
        repo_state()


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
    # How many renames deep to follow, for this scan only. Sent by the screen
    # when a trail was cut short by the limit, so "run it again, deeper" is one
    # button on the result rather than a trip to the settings screen and back.
    maxHops: int | None = None


class SummaryIn(BaseModel):
    scan: dict
    vals: dict
    useAI: bool = True


class SaveIn(BaseModel):
    vals: dict
    scan: dict
    summary: dict
    mode: str = "email"


class StatusIn(BaseModel):
    status: str


class AIKeyIn(BaseModel):
    key: str = ""            # blank means keep whatever is already set
    model: str = ""          # blank means keep the model already selected


class ProductionIn(BaseModel):
    text: str = ""


class FolderIn(BaseModel):
    path: str = ""          # a folder on this machine, holding the SQL to read


class ConnectIn(BaseModel):
    repo: str = ""          # owner/repository, or the address pasted from GitHub
    branch: str = ""        # blank means the repository's default branch
    token: str = ""         # blank means keep using whatever is already set


# ── routes ─────────────────────────────────────────────────────────────────
def _token_origin() -> str:
    """Where the token in play came from -- never the token itself."""
    if _state["token"]:
        return "entered"
    if settings.github_token:
        return "environment"
    return ""


def _github_facts() -> dict | None:
    conn: ghub.Connection | None = _state["conn"]
    if _state["source"] != "github" or conn is None:
        return None
    return {
        "slug": conn.ref.slug,
        "owner": conn.ref.owner,
        "repo": conn.ref.repo,
        "branch": conn.branch,
        "commit": conn.commit,
        "shortCommit": conn.commit[:7],
        "private": conn.private,
        "defaultBranch": conn.default_branch,
        "archiveFiles": conn.total_files,
        "webUrl": conn.ref.web_url(),
    }


@app.get("/api/health")
def health() -> dict:
    # Reading a repository the size of a real warehouse takes minutes, and this
    # is the request the screen makes before it can paint anything at all.
    # Measured on 7,304 files: 101 seconds in here, during which the browser has
    # a blank page and no way to ask what is happening -- because the only
    # request that would tell it is the one it is already waiting on. A working
    # program that says nothing for a hundred seconds is a hung one.
    #
    # So the read happens on a thread, this answers straight away, and the
    # screen shows the counted progress that was always being recorded and never
    # had anywhere to go. See _start_reading and /api/progress.
    if _state["index"] is None:
        _start_reading()
        return _still_reading()
    idx, parsed, cat = repo_state()
    # What kinds of file are actually in the index, biggest group first. The
    # screen shows these, so they have to be counted rather than assumed.
    kinds: dict[str, int] = {}
    for f in idx.files:
        kinds[f.lang] = kinds.get(f.lang, 0) + 1
    gh = _github_facts()
    on_github = gh is not None
    return {
        "ok": True,
        # Which build this is. There was no way to tell from any screen, and
        # "it does not work" has more than once turned out to be "that was
        # fixed a while ago, on a copy nobody installed".
        "build": build_info(),
        "source": _state["source"],
        "github": gh,
        "tokenSet": bool(_active_token()),
        "tokenFrom": _token_origin(),
        "connectError": _state["error"],
        # On a serverless host each request can land on a fresh instance, so a
        # token typed into the screen will not last. The screen says so.
        "serverless": settings.serverless,
        # The real ceilings on this host, so the screen never promises more than
        # it can do. On a laptop these are generous; on Vercel they are not.
        "limits": {
            "maxUploadBytes": settings.max_upload_bytes,
            "maxRepoBytes": settings.max_repo_bytes,
            "historyKept": not settings.serverless,
        },
        "repo": {
            "label": gh["slug"] if on_github else settings.repo_label,
            "branch": gh["branch"] if on_github else settings.branch(),
            "path": gh["webUrl"] if on_github else str(settings.repo_path),
            "files": len(idx.files),
            "statements": len(parsed.statements),
            "unreadable": len(parsed.unreadable),
            # Files never opened at all. Shown next to the file count, because
            # "1,770 files read" beside "412 never opened" is a different
            # sentence from "1,770 files read".
            "heldOnline": len(idx.held_online),
            "pathTooLong": len(idx.too_long),
            # Code files Ripple walked past because of the folder they sit in.
            "inSkippedDirs": len(idx.in_skipped_dirs),
            "skippedDirNames": list(idx.skipped_dir_names),
            # File types Ripple does not open, biggest first. Nothing recorded
            # these before, so a repository whose pipeline is written in one of
            # them looked exactly like a repository with no pipeline in it.
            "unknownExt": [
                {"ext": k, "files": n}
                for k, n in sorted(idx.unknown_ext.items(), key=lambda kv: (-kv[1], kv[0]))
            ][:12],
            # Programs that run SQL kept in a separate .sql file. Two folders of
            # DAGs are written that way, and without this they read as empty.
            "runsSqlFrom": len([r for r in parsed.runs_sql_from if r["runs"]]),
            "exists": True if on_github else settings.repo_path.exists(),
            "kinds": [
                {"lang": k, "files": n}
                for k, n in sorted(kinds.items(), key=lambda kv: (-kv[1], kv[0]))
            ],
        },
        "catalog": {"tables": len(cat.tables), "columns": sum(len(v) for v in cat.tables.values())},
        "sqlDialect": settings.sql_dialect or "generic",
        "maxHops": settings.max_hops,
        # Which table names count as the ones this team publishes. On screen so
        # that "no production table is impacted" can be checked rather than
        # believed -- it is only ever as true as this rule is. The one-line form
        # is for a status row; the full one is what the settings screen shows.
        "production": settings.production_rule(),
        "productionRule": settings.production().to_dict(),
        # Where the list came from, so "I set that and it is gone" has an
        # answer. Online it survives a restart only as an environment variable.
        "productionFrom": _production_origin(),
        # Whether anything can be scanned at all yet. The screens gate on this
        # rather than on the text being non-empty, so there is one answer to
        # the question and every screen gives the same one.
        "productionSet": settings.has_production(),
        # The repository is read and these numbers are real. The screen paints
        # the reading progress instead when this is true. See _still_reading.
        "indexing": False,
        "readError": _reading["error"],
        "ai": _ai_facts(),
    }


def _production_origin() -> str:
    """Where the published-table list in play came from -- typed, set on the
    host, or nothing at all yet."""
    if _state["prodEntered"]:
        return "entered"
    if os.environ.get("RIPPLE_PROD_TABLES", "").strip():
        return "environment"
    # "unset", not "default". There is no default any more: nothing is scanned
    # until somebody says which tables are theirs. See Settings.has_production.
    return "unset"


@app.get("/api/progress")
def progress_now() -> dict:
    """What Ripple is doing this second.

    Asked for by the screen while it waits. Every number is counted rather than
    estimated, and where there is genuinely no total it says so rather than
    drawing a bar over a number nobody knows.
    """
    return progress.snapshot()


@app.get("/api/catalog")
def catalog() -> dict:
    _, _, cat = repo_state()
    return cat.to_dict()


@app.post("/api/ai/check")
def ai_check() -> dict:
    """Really call the model that is really selected, and say which one.

    A key that is present is not the same as a key that works, and a key that
    works with one model can be refused by another. The only honest check is
    the round trip.
    """
    return ai.check_key(_ai_cfg())


@app.post("/api/ai/connect")
def ai_connect(payload: "AIKeyIn") -> dict:
    """Turn the AI on from the screen, without touching the environment.

    The key is held in this process and nowhere else: not written to disk, not
    logged, and not returned by this or any other route.
    """
    model = (payload.model or "").strip()
    key = (payload.key or "").strip()
    # A key already typed into this screen counts. Without it, changing only
    # the model after the AI is already on was refused as "no key".
    if not key and not _state["aiKey"] and not settings.ai_key:
        raise HTTPException(
            status_code=400,
            detail="Paste an OpenAI, Google Gemini or Groq key to turn the AI on.")

    before = (_state["aiKey"], _state["aiModel"], list(_state.get("aiModels") or []))
    if key:
        # Which company issued it is worked out from the key, not asked for.
        if providers.detect(key) is None:
            maker = providers.name_of_unsupported(key)
            _state["aiKey"], _state["aiModel"], _state["aiModels"] = before
            raise HTTPException(status_code=400, detail=(
                f"That looks like an {maker} key. Ripple reads OpenAI, Google Gemini "
                "and Groq keys." if maker else
                "Ripple does not recognise that key. It reads OpenAI keys (sk-...), "
                "Google Gemini keys (AIza...) and Groq keys (gsk_...)."))
        _state["aiKey"] = key
        _state["aiModel"] = ""
        _state["aiModels"] = []
    if model:
        _state["aiModel"] = model

    # Ask the provider which models this key can actually use. That proves the
    # key and produces the real list in one call, so nothing on screen is a
    # remembered model name that may no longer exist.
    try:
        found = ai.list_models(_ai_cfg())
    except ai.AIUnavailable as exc:
        _state["aiKey"], _state["aiModel"], _state["aiModels"] = before
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    ranked = providers.rank_models(providers.detect(_ai_cfg().ai_key), found)
    _state["aiModels"] = ranked
    if not _state["aiModel"]:
        if not ranked:
            _state["aiKey"], _state["aiModel"], _state["aiModels"] = before
            raise HTTPException(
                status_code=502,
                detail="That key works, but the provider offers no chat model it can use.")
        _state["aiModel"] = ranked[0]
    elif ranked and _state["aiModel"] not in ranked:
        chosen = _state["aiModel"]
        _state["aiKey"], _state["aiModel"], _state["aiModels"] = before
        raise HTTPException(
            status_code=400,
            detail=f"That key cannot use {chosen}. Pick one of the models listed.")

    # Prove it answers, now rather than at the worst moment. A key the provider
    # refuses is reported straight back, and is not kept.
    result = ai.check_key(_ai_cfg())
    if not result.get("ok"):
        _state["aiKey"], _state["aiModel"], _state["aiModels"] = before
        raise HTTPException(status_code=502, detail=result.get("reason", "The key did not work."))
    return health()


@app.post("/api/ai/forget")
def ai_forget() -> dict:
    """Forget a key typed into the screen. One set in the environment stays."""
    _state["aiKey"] = ""
    _state["aiModel"] = ""
    _state["aiModels"] = []
    return health()


# ── the tables this team publishes ─────────────────────────────────────────
# The most expensive setting in Ripple, so it gets its own routes: one to read
# a paste and say what was made of it before anything is committed to, and one
# to actually use it. Both answer the question that matters -- which of the
# tables on the list Ripple has never seen in this repository.
def _production_report(rule: production.ProductionRule) -> dict:
    idx, parsed, _ = repo_state()
    return {**rule.to_dict(), "check": production.check_against_repo(rule, idx, parsed)}


@app.post("/api/production/read")
def production_read(payload: ProductionIn) -> dict:
    """Read a pasted list without saving it, and say exactly what was made of it."""
    return _production_report(production.parse(payload.text or ""))


@app.get("/api/production")
def production_now() -> dict:
    """The list in play, checked against the repository that is loaded."""
    return _production_report(settings.production())


@app.post("/api/production")
def production_set(payload: ProductionIn) -> dict:
    """Use this list from now on.

    Held in this process, exactly like the GitHub token and the AI key: online
    there is nowhere to write it. The screen says so rather than letting a list
    somebody spent ten minutes assembling quietly vanish on the next restart.
    """
    settings.set_production(payload.text or "")
    _state["prodEntered"] = bool((payload.text or "").strip())
    return health()


@app.post("/api/repo/folder")
def repo_folder(payload: "FolderIn") -> dict:
    """Read this folder on this machine from now on.

    RIPPLE_REPO decides which folder Ripple starts on, and that is right for a
    server somebody administers. It is wrong for a laptop: it meant the only way
    to point Ripple at your own SQL was to edit a file and restart, and until you
    did, every answer described the small practice pipeline -- confidently,
    correctly, and about nothing anybody cares about.

    Held in this process, exactly like the published-table list, the GitHub token
    and the AI key. The screen says so rather than letting somebody believe a
    folder they chose will still be chosen tomorrow.

    Everything read from the previous folder is thrown away first. A repository
    half read from one folder and half from another would answer questions about
    neither, and nothing on screen could show that had happened.
    """
    raw = (payload.path or "").strip().strip('"')
    if not raw:
        raise HTTPException(status_code=400, detail="Type the folder Ripple should read.")
    folder = Path(raw).expanduser()
    try:
        folder = folder.resolve()
    except OSError:
        raise HTTPException(status_code=400, detail=f"That is not a folder Windows can open: {raw}") from None
    if not folder.exists():
        raise HTTPException(
            status_code=400,
            detail=f"There is no folder at {folder}. Check the path - a typo here is not "
                   f"an empty repository, and Ripple will not treat it as one.")
    if not folder.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"{folder} is a file, not a folder. Choose the folder that holds the SQL.")

    settings.repo_path = folder
    settings.repo_label = folder.name or str(folder)
    settings.repo_source = "folder"
    _state.update({"index": None, "parsed": None, "catalog": None,
                   "conn": None, "source": "folder", "error": ""})
    try:
        _use_folder()
    except OSError as exc:
        raise HTTPException(status_code=400, detail=f"That folder could not be read: {exc}") from None
    return health()


@app.post("/api/reindex")
def do_reindex() -> dict:
    try:
        reindex()
    except ghub.GitHubError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return health()


# ── connecting to GitHub ───────────────────────────────────────────────────
@app.post("/api/repo/connect")
def repo_connect(payload: "ConnectIn") -> dict:
    """Read a GitHub repository with an access token.

    The token is kept in this process only, for as long as it is running. It is
    not written anywhere and is not returned by this or any other route.
    """
    repo = (payload.repo or "").strip()
    if not repo:
        raise HTTPException(status_code=400, detail="Enter the repository to read.")
    # No token is required up front: a public repository can be read without one.
    # If GitHub refuses, its own answer tells the person to add a token.
    token = (payload.token or "").strip() or _active_token()
    try:
        _use_github(repo, token, (payload.branch or "").strip())
    except ghub.GitHubError as exc:
        # Leave whatever was connected before in place, and say what went wrong.
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if payload.token and payload.token.strip():
        _state["token"] = payload.token.strip()
    return health()


@app.post("/api/repo/disconnect")
def repo_disconnect() -> dict:
    """Forget the token and go back to the folder on this machine."""
    _state["token"] = ""
    _state["error"] = ""
    _state["index"] = None
    _state["conn"] = None
    _state["source"] = "folder"
    _use_folder()
    return health()


def _extract(n: Notification, use_ai: bool) -> dict:
    _, _, cat = repo_state()
    cfg = _ai_cfg()
    rules = extract_by_rules(n, cat)
    if not (use_ai and cfg.ai_available()):
        rules.setdefault("aiNote", "AI is off - fields were found by matching the repository catalogue.")
        return rules
    try:
        out = ai.read_email(n.text(), cfg)
    except ai.AIUnavailable as exc:
        rules["warnings"] = list(rules.get("warnings", [])) + [
            f"The AI reader was unavailable ({exc}). Fields below were found without it."
        ]
        rules["aiNote"] = "AI unavailable - fell back to matching the repository catalogue."
        return rules
    # Keep the rules-based answers for anything the model left blank, and always
    # keep our own warnings about names that are not in the repository.
    for key in ("source", "changeType", "changeKind", "changeDesc", "subject",
                "effectiveDate", "pocName", "pocEmail", "pocTeam"):
        if not out.get(key):
            out[key] = rules.get(key, "")
    if not out.get("upstream"):
        out["upstream"] = rules.get("upstream", [])
    out["warnings"] = list(out.get("warnings") or []) + _unknown_name_warnings(out, cat)
    out["aiNote"] = f"Read by {cfg.ai_model}. Check it before scanning."
    return out


def _unknown_name_warnings(vals: dict, cat: Catalog) -> list[str]:
    missing = [u["table"] for u in vals.get("upstream", []) if not cat.has_table(u["table"])]
    if missing:
        return [
            "Not found in the connected repository: " + ", ".join(missing)
            + ". Scanning will still run, but expect no results for those."
        ]
    return []


def _too_big(size: int) -> str:
    """Say what the real ceiling is, and why it is that number."""
    # One decimal on the file, none on the limit -- otherwise a 4.4 MB file
    # reads as "that file is 4 MB, the most accepted is 4 MB", which is absurd.
    msg = (f"That file is {size / 1_000_000:.1f} MB. The most this copy of Ripple "
           f"accepts is {settings.max_upload_bytes / 1_000_000:.0f} MB.")
    if settings.serverless:
        msg += (" This copy runs on a serverless host, which refuses anything bigger"
                " before Ripple sees it. Save the email as .eml, which is far smaller"
                " than a .msg, or enter the change by hand.")
    return msg


@app.post("/api/read-email")
async def read_email_file(file: UploadFile = File(...), useAI: str = "true") -> dict:
    raw = await file.read()
    if len(raw) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail=_too_big(len(raw)))
    n = read_upload(file.filename or "", raw)
    out = _extract(n, useAI.lower() == "true")
    out["emailPreview"] = {
        "subject": n.subject,
        "body": n.body[:4000],
        "fromName": n.from_name,
        "fromEmail": n.from_email,
        "attachments": n.attachments,
        "kind": n.source_kind,
    }
    return out


# The deepest Ripple will follow a rename, however deep it is asked to. Not a
# guess about pipelines -- a stop on a scan that has clearly gone wrong, set far
# above any real chain. Each extra hop is more statements to look at, and a scan
# nobody can cancel is worse than one that stopped too soon.
HOP_CEILING = 25


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
        # This scan only. The setting on the settings screen is left alone, so
        # running one scan deeper does not quietly change every later scan.
        cfg = copy.copy(settings)
        asked = int(payload.maxHops)
        # Zero survives the clamp: it means "to the end of the code", which is
        # bounded by the walk's own memory of where it has been, not by a number.
        cfg.max_hops = 0 if asked <= 0 else min(asked, HOP_CEILING)
    try:
        res = trace(idx, parsed, upstream, change_type=payload.changeKind, cfg=cfg,
                    on_progress=progress.reader("scanning"), catalog=cat)
    finally:
        progress.finish()
    out = res.to_dict()
    conn: ghub.Connection | None = _state["conn"]
    on_github = _state["source"] == "github" and conn is not None
    # A link is only offered when Ripple genuinely knows the address. On GitHub
    # it points at the exact commit that was read, not at whatever the branch
    # has moved on to since.
    out["repo"] = {
        "label": conn.ref.slug if on_github else settings.repo_label,
        "branch": conn.branch if on_github else settings.branch(),
        "urlTemplate": conn.url_template() if on_github else settings.repo_url_template,
    }
    return out


@app.post("/api/summary")
def summary(payload: SummaryIn) -> dict:
    cfg = _ai_cfg()
    base = narrative.summarise(payload.scan, payload.vals)
    reply = narrative.draft_reply(payload.scan, payload.vals, base)
    out = {"summary": base, "reply": reply}
    if not (payload.useAI and cfg.ai_available()):
        return out
    def _trim(groups: list[dict]) -> list[dict]:
        return [
            {
                "prod": g["prod"],
                "rows": [
                    {k: r[k] for k in ("inter", "attr", "alias", "logic", "mode", "impact",
                                       "breaking", "noLocalFix", "file")}
                    for r in g["rows"]
                ],
            }
            for g in groups
        ]

    trimmed = {
        "risk": payload.scan.get("risk"),
        "stats": payload.scan.get("stats"),
        "groups": _trim(payload.scan.get("groups", [])),
        # Sent as well, or the model writes "no impact" over a list of findings
        # that simply did not match the production naming rule.
        "reachedButNotOnTheProductionList": _trim(payload.scan.get("reached", [])),
        "couldNotRead": [u.get("file") for u in payload.scan.get("unreadable", [])],
        "change": {k: payload.vals.get(k) for k in
                   ("source", "changeType", "changeDesc", "effectiveLabel", "pocName", "pocTeam")},
        "upstream": payload.vals.get("upstream", []),
    }
    try:
        out["summary"] = {**base, **ai.write_summary(trimmed, cfg)}
        out["reply"] = {**reply, **ai.write_reply({**trimmed, "summary": out["summary"]}, cfg)}
    except ai.AIUnavailable as exc:
        out["aiNote"] = f"AI unavailable ({exc}). Written without it."
    return out


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
    """The real text of a scanned file, so a finding can be opened in place."""
    idx, _, _ = repo_state()
    f = idx.get(path)
    if f is None:
        raise HTTPException(status_code=404, detail="Not in the index.")
    return {"path": f.path, "lang": f.lang, "lines": f.text.splitlines()}


# ── static site ────────────────────────────────────────────────────────────
@app.middleware("http")
async def cache_rules(request, call_next):
    """Browsers hold on to app.js hard. During a demo or an edit that means you
    stare at yesterday's page and think the change did not work -- so the page
    and its script are never cached.

    The font files are the exception. They are 350 KB together and they do not
    change. On a hosted copy there is no separate web server for them: every
    request runs the app itself, so refusing to cache them means re-serving a
    third of a megabyte on every page view. A month is long enough to help and
    short enough that a replaced font is not stuck forever.
    """
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/static/fonts/") and path.endswith(".woff2"):
        response.headers["Cache-Control"] = "public, max-age=2592000, s-maxage=2592000"
    elif path.startswith("/static") or path == "/":
        response.headers["Cache-Control"] = "no-store, must-revalidate"
    return response


if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")
else:  # pragma: no cover
    @app.get("/")
    def index() -> JSONResponse:
        return JSONResponse({"error": "web folder missing"}, status_code=500)
