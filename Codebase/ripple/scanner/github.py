"""Reading a repository straight from GitHub, with an access token.

Ripple's scanner works on a folder of files. This module gets that folder from
GitHub instead of from disk: it asks GitHub for the repository as a single
compressed archive, unpacks it in memory, and hands back the same RepoIndex the
local reader produces. Everything downstream -- the SQL reader, the lineage
tracer, the catalogue -- is unchanged and does not know where the files came
from.

One archive is a single request. Asking for each file separately would be
hundreds of requests and would exhaust the hourly limit on a real repository.

The access token is only ever used as an Authorization header. It is never
written to disk, never logged, and never returned by any route.
"""
from __future__ import annotations

import io
import re
import tarfile
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from ..config import Settings, settings as default_settings
from .repo import LANG_BY_EXT, RepoIndex, SourceFile


class GitHubError(RuntimeError):
    """Something went wrong that the person on the screen needs to read."""


@dataclass(frozen=True)
class RepoRef:
    owner: str
    repo: str
    branch: str = ""          # empty means "whatever the repository's default is"

    @property
    def slug(self) -> str:
        return f"{self.owner}/{self.repo}"

    def web_url(self) -> str:
        return f"https://github.com/{self.owner}/{self.repo}"


@dataclass
class Connection:
    """What Ripple actually connected to. Deliberately carries no token."""

    ref: RepoRef
    branch: str = ""          # the branch really used, once resolved
    commit: str = ""          # the exact commit read, so a link points at that code
    private: bool = False
    default_branch: str = ""
    truncated: bool = False
    total_files: int = 0      # every file in the archive, before filtering
    skipped_dirs: int = 0

    def url_template(self) -> str:
        """A link straight to the line in GitHub, for the exact commit we read."""
        anchor = self.commit or self.branch or self.default_branch or "HEAD"
        return f"{self.ref.web_url()}/blob/{anchor}/{{path}}#L{{line}}"


# ── working out what the user typed ────────────────────────────────────────
_REF = re.compile(
    r"""^\s*
    (?:https?://)?                      # https:// is optional
    (?:www\.)?
    (?:github\.com[:/])?                # so is the host
    (?P<owner>[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)
    /
    (?P<repo>[A-Za-z0-9._-]+?)
    (?:\.git)?                          # a clone URL pasted straight in
    (?:/(?:tree|blob)/(?P<branch>[^/\s#?]+))?   # .../tree/some-branch
    /?
    (?:[#?].*)?                         # trailing anchors or query strings
    \s*$""",
    re.VERBOSE,
)


def parse_repo_ref(text: str, branch: str = "") -> RepoRef:
    """Accept anything a person is likely to paste and pull owner/repo out of it.

    Handles `owner/repo`, `github.com/owner/repo`, a full https URL, a `.git`
    clone URL, and a URL that points at a branch.
    """
    m = _REF.match(text or "")
    if not m:
        raise GitHubError(
            "That does not look like a GitHub repository. "
            "Use owner/repository, or paste the address from GitHub."
        )
    return RepoRef(
        owner=m.group("owner"),
        repo=m.group("repo"),
        branch=(branch or m.group("branch") or "").strip(),
    )


# ── talking to GitHub ──────────────────────────────────────────────────────
def _headers(token: str) -> dict[str, str]:
    h = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "ripple-impact-analysis",
    }
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _explain(status: int, ref: RepoRef, has_token: bool) -> str:
    """Turn an HTTP status into something worth putting on a screen."""
    if status == 401:
        return ("GitHub rejected the access token. It may be mistyped, expired, "
                "or revoked. Create a new one and paste it in again.")
    if status == 403:
        return ("GitHub refused the request. Either the hourly limit is used up, "
                "or the token does not have permission to read this repository.")
    if status == 404:
        if has_token:
            return (f"No repository called {ref.slug} that this token can see. "
                    "Check the spelling, and that the token has access to it "
                    "(a fine-grained token must list this repository).")
        return (f"No public repository called {ref.slug}. If it is private, "
                "add an access token below.")
    if status == 451:
        return "GitHub has made this repository unavailable."
    return f"GitHub returned an unexpected error ({status})."


def describe(ref: RepoRef, token: str, cfg: Settings | None = None) -> dict:
    """Check the repository exists and we can read it, before downloading it."""
    cfg = cfg or default_settings
    url = f"{cfg.github_api}/repos/{ref.owner}/{ref.repo}"
    try:
        r = httpx.get(url, headers=_headers(token), timeout=cfg.github_timeout)
    except httpx.HTTPError as exc:
        raise GitHubError(f"Could not reach GitHub: {exc}") from exc
    if r.status_code != 200:
        raise GitHubError(_explain(r.status_code, ref, bool(token)))
    return r.json()


def download_archive(ref: RepoRef, token: str, cfg: Settings | None = None) -> bytes:
    """The whole repository as one gzipped tar, at the requested branch."""
    cfg = cfg or default_settings
    branch = ref.branch or ""
    url = f"{cfg.github_api}/repos/{ref.owner}/{ref.repo}/tarball"
    if branch:
        url += f"/{branch}"
    chunks: list[bytes] = []
    size = 0
    try:
        with httpx.stream("GET", url, headers=_headers(token), timeout=cfg.github_timeout,
                          follow_redirects=True) as r:
            if r.status_code != 200:
                r.read()
                if r.status_code == 404 and branch:
                    raise GitHubError(
                        f"No branch called '{branch}' in {ref.slug}. "
                        "Leave the branch blank to use the repository's default."
                    )
                raise GitHubError(_explain(r.status_code, ref, bool(token)))
            for chunk in r.iter_bytes():
                size += len(chunk)
                if size > cfg.max_repo_bytes:
                    raise GitHubError(
                        f"{ref.slug} is larger than {cfg.max_repo_bytes // 1_000_000} MB "
                        "compressed, which is more than Ripple will pull in one go."
                    )
                chunks.append(chunk)
    except GitHubError:
        raise
    except httpx.HTTPError as exc:
        raise GitHubError(f"Could not download {ref.slug} from GitHub: {exc}") from exc
    return b"".join(chunks)


# ── turning the archive into the same index the local reader builds ────────
def index_from_archive(data: bytes, cfg: Settings | None = None) -> tuple[RepoIndex, dict]:
    """Unpack the archive in memory and keep the files worth reading.

    Applies exactly the same rules as the folder reader: known extensions only,
    skip the usual noise directories, and refuse anything oversized. Files that
    cannot be decoded are recorded rather than dropped silently.
    """
    cfg = cfg or default_settings
    idx = RepoIndex(root=None)
    meta = {"total_files": 0, "truncated": False}
    try:
        tar = tarfile.open(fileobj=io.BytesIO(data), mode="r:gz")
    except tarfile.TarError as exc:
        raise GitHubError(f"GitHub sent an archive Ripple could not open ({exc}).") from exc

    with tar:
        for member in tar:
            if not member.isfile():
                continue
            meta["total_files"] += 1
            # GitHub wraps everything in one folder named owner-repo-commit.
            rel = member.name.split("/", 1)[1] if "/" in member.name else member.name
            if not rel:
                continue
            parts = rel.split("/")
            if any(p in cfg.skip_dirs for p in parts):
                continue
            ext = Path(rel).suffix.lower()
            if ext not in cfg.code_extensions:
                continue
            if member.size > cfg.max_file_bytes:
                idx.skipped.append(
                    {"file": rel, "reason": f"file is {member.size // 1024} KB - too large to read"}
                )
                continue
            handle = tar.extractfile(member)
            if handle is None:                       # pragma: no cover - defensive
                idx.skipped.append({"file": rel, "reason": "could not be read from the archive"})
                continue
            raw = handle.read()
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                try:
                    text = raw.decode("latin-1")
                except Exception as exc:             # pragma: no cover - defensive
                    idx.skipped.append({"file": rel, "reason": f"could not decode ({exc})"})
                    continue
            idx.files.append(
                SourceFile(path=rel, abs_path=Path(rel), text=text,
                           lang=LANG_BY_EXT.get(ext, "Text"))
            )
    idx.files.sort(key=lambda f: f.path)
    return idx, meta


def connect(repo_text: str, token: str, branch: str = "",
            cfg: Settings | None = None) -> tuple[RepoIndex, Connection]:
    """Everything at once: check access, download, unpack, index."""
    cfg = cfg or default_settings
    ref = parse_repo_ref(repo_text, branch)
    info = describe(ref, token, cfg)
    default_branch = info.get("default_branch") or "main"
    wanted = ref.branch or default_branch
    ref = RepoRef(owner=ref.owner, repo=ref.repo, branch=wanted)

    data = download_archive(ref, token, cfg)
    idx, meta = index_from_archive(data, cfg)
    if not idx.files:
        raise GitHubError(
            f"{ref.slug} was read, but none of its {meta['total_files']} files are of a kind "
            "Ripple can scan (SQL, Python, Scala, Java, shell, XML or YAML)."
        )
    conn = Connection(
        ref=ref,
        branch=wanted,
        commit=_commit_from_archive(data),
        private=bool(info.get("private")),
        default_branch=default_branch,
        total_files=meta["total_files"],
    )
    return idx, conn


def _commit_from_archive(data: bytes) -> str:
    """The archive's top folder is named owner-repo-<commit>, so read it there.

    Knowing the exact commit means a link on a finding points at the code Ripple
    actually read, not at whatever the branch has moved on to since.
    """
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
            first = tar.next()
            if first is None:
                return ""
            top = first.name.split("/", 1)[0]
            tail = top.rsplit("-", 1)[-1]
            return tail if re.fullmatch(r"[0-9a-f]{7,40}", tail) else ""
    except tarfile.TarError:                          # pragma: no cover - defensive
        return ""
