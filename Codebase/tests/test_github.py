"""Tests for reading a repository from GitHub.

None of these touch the network. The archive GitHub would send is built here
from the mock repository, so the unpacking, filtering and error handling are
tested for real while the HTTP call is stubbed out.

The thing most worth guarding: the access token must never come back out of the
app in any response.
"""
from __future__ import annotations

import io
import sys
import tarfile
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ripple import api                                          # noqa: E402
from ripple.api import app                                      # noqa: E402
from ripple.config import settings                              # noqa: E402
from ripple.scanner import github as ghub                       # noqa: E402

SECRET = "ghp_thisisnotarealtoken0000000000000000"


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def back_to_the_folder():
    """Every test starts and ends on the local folder, so none leak into others."""
    yield
    api._state.update({"token": "", "error": "", "conn": None, "source": "folder", "index": None})


def make_archive(root: Path, top: str = "aucksy-ripple-abc1234") -> bytes:
    """The same shape GitHub sends: everything inside one top-level folder."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for p in sorted(root.rglob("*")):
            if not p.is_file():
                continue
            info = tarfile.TarInfo(f"{top}/{p.relative_to(root).as_posix()}")
            data = p.read_bytes()
            info.size = len(data)
            info.mtime = int(time.time())
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def add(tar: tarfile.TarFile, name: str, body: bytes) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(body)
    info.mtime = int(time.time())
    tar.addfile(info, io.BytesIO(body))


# ── working out what was typed ─────────────────────────────────────────────
@pytest.mark.parametrize("text", [
    "aucksy/Ripple",
    "github.com/aucksy/Ripple",
    "https://github.com/aucksy/Ripple",
    "https://github.com/aucksy/Ripple.git",
    "https://www.github.com/aucksy/Ripple/",
    "  https://github.com/aucksy/Ripple  ",
])
def test_every_shape_of_address_is_understood(text):
    ref = ghub.parse_repo_ref(text)
    assert (ref.owner, ref.repo) == ("aucksy", "Ripple")


def test_a_branch_in_the_address_is_picked_up():
    ref = ghub.parse_repo_ref("https://github.com/aucksy/Ripple/tree/develop")
    assert ref.branch == "develop"


def test_an_explicit_branch_wins_over_one_in_the_address():
    ref = ghub.parse_repo_ref("https://github.com/aucksy/Ripple/tree/develop", branch="main")
    assert ref.branch == "main"


@pytest.mark.parametrize("text", ["", "   ", "not a repo", "https://gitlab.com/a/b/c/d/e"])
def test_nonsense_is_refused_with_something_readable(text):
    with pytest.raises(ghub.GitHubError) as exc:
        ghub.parse_repo_ref(text)
    assert "repository" in str(exc.value).lower()


# ── unpacking the archive ──────────────────────────────────────────────────
def test_archive_produces_the_same_files_as_the_folder():
    data = make_archive(settings.repo_path)
    idx, meta = ghub.index_from_archive(data, settings)
    from ripple.scanner.repo import RepoIndex
    local = RepoIndex.build(settings.repo_path, settings)
    assert {f.path for f in idx.files} == {f.path for f in local.files}
    assert meta["total_files"] >= len(idx.files)


def test_languages_are_labelled_the_same_as_on_disk():
    data = make_archive(settings.repo_path)
    idx, _ = ghub.index_from_archive(data, settings)
    from ripple.scanner.repo import RepoIndex
    local = RepoIndex.build(settings.repo_path, settings)
    assert {f.path: f.lang for f in idx.files} == {f.path: f.lang for f in local.files}


def test_noise_directories_and_other_file_types_are_left_out():
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        add(tar, "o-r-abc/wanted.sql", b"SELECT 1;")
        add(tar, "o-r-abc/.git/config", b"[core]")
        add(tar, "o-r-abc/node_modules/x/y.sql", b"SELECT 2;")
        add(tar, "o-r-abc/logo.png", b"\x89PNG")
        add(tar, "o-r-abc/notes.md", b"# hello")
    idx, meta = ghub.index_from_archive(buf.getvalue(), settings)
    assert [f.path for f in idx.files] == ["wanted.sql"]
    assert meta["total_files"] == 5


def test_an_oversized_file_is_reported_not_dropped_silently():
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        add(tar, "o-r-abc/small.sql", b"SELECT 1;")
        add(tar, "o-r-abc/huge.sql", b"x" * (settings.max_file_bytes + 10))
    idx, _ = ghub.index_from_archive(buf.getvalue(), settings)
    assert [f.path for f in idx.files] == ["small.sql"]
    assert any(s["file"] == "huge.sql" and "too large" in s["reason"] for s in idx.skipped)


def test_a_file_that_is_not_utf8_is_still_read():
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        add(tar, "o-r-abc/latin.sql", "SELECT 'caf\xe9';".encode("latin-1"))
    idx, _ = ghub.index_from_archive(buf.getvalue(), settings)
    assert len(idx.files) == 1
    assert "caf" in idx.files[0].text


def test_a_broken_archive_says_so():
    with pytest.raises(ghub.GitHubError) as exc:
        ghub.index_from_archive(b"this is not a tarball", settings)
    assert "could not open" in str(exc.value).lower()


def test_the_exact_commit_is_read_from_the_archive():
    data = make_archive(settings.repo_path, top="aucksy-Ripple-0782807deadbeef")
    assert ghub._commit_from_archive(data) == "0782807deadbeef"


def test_a_link_points_at_the_commit_that_was_read():
    conn = ghub.Connection(ref=ghub.RepoRef("aucksy", "Ripple", "main"),
                           branch="main", commit="0782807")
    tpl = conn.url_template()
    assert tpl == "https://github.com/aucksy/Ripple/blob/0782807/{path}#L{line}"


# ── what the person on the screen is told when it goes wrong ───────────────
@pytest.mark.parametrize("status,expect", [
    (401, "token"),
    (403, "permission"),
    (404, "spelling"),
])
def test_failures_are_explained_in_words(status, expect):
    ref = ghub.RepoRef("aucksy", "Ripple")
    assert expect in ghub._explain(status, ref, has_token=True).lower()


def test_a_missing_public_repo_suggests_a_token():
    ref = ghub.RepoRef("aucksy", "Ripple")
    assert "token" in ghub._explain(404, ref, has_token=False).lower()


# ── the routes ─────────────────────────────────────────────────────────────
def test_a_public_repository_needs_no_token(client, monkeypatch):
    """No token is demanded up front -- GitHub decides, and says why."""
    monkeypatch.setattr(settings, "github_token", "", raising=False)
    seen = {}
    monkeypatch.setattr(ghub, "describe",
                        lambda ref, token, cfg=None: seen.update(token=token) or
                        {"default_branch": "main", "private": False})
    monkeypatch.setattr(ghub, "download_archive",
                        lambda ref, token, cfg=None: make_archive(settings.repo_path))
    r = client.post("/api/repo/connect", json={"repo": "aucksy/Ripple"})
    assert r.status_code == 200
    assert seen["token"] == ""
    assert r.json()["tokenSet"] is False


def test_a_private_repository_without_a_token_says_to_add_one(client, monkeypatch):
    monkeypatch.setattr(settings, "github_token", "", raising=False)
    ref = ghub.RepoRef("aucksy", "Secret")

    def refuse(r, token, cfg=None):
        raise ghub.GitHubError(ghub._explain(404, ref, has_token=bool(token)))

    monkeypatch.setattr(ghub, "describe", refuse)
    r = client.post("/api/repo/connect", json={"repo": "aucksy/Secret"})
    assert r.status_code == 502
    assert "token" in r.json()["detail"].lower()


def test_connecting_without_a_repository_is_refused(client):
    r = client.post("/api/repo/connect", json={"repo": "", "token": SECRET})
    assert r.status_code == 400


def _stub_github(monkeypatch, private=False):
    """Answer as GitHub would, without a network."""
    monkeypatch.setattr(ghub, "describe",
                        lambda ref, token, cfg=None: {"default_branch": "main", "private": private})
    monkeypatch.setattr(ghub, "download_archive",
                        lambda ref, token, cfg=None: make_archive(settings.repo_path))


def test_connecting_reports_the_repository_it_really_read(client, monkeypatch):
    _stub_github(monkeypatch)
    r = client.post("/api/repo/connect",
                    json={"repo": "aucksy/Ripple", "branch": "", "token": SECRET})
    assert r.status_code == 200
    h = r.json()
    assert h["source"] == "github"
    assert h["github"]["slug"] == "aucksy/Ripple"
    assert h["github"]["branch"] == "main"
    assert h["repo"]["files"] > 15
    assert h["tokenSet"] is True
    assert h["tokenFrom"] == "entered"


def test_the_token_never_comes_back_out(client, monkeypatch):
    _stub_github(monkeypatch)
    connect = client.post("/api/repo/connect", json={"repo": "aucksy/Ripple", "token": SECRET})
    assert SECRET not in connect.text
    for path in ("/api/health", "/api/catalog"):
        assert SECRET not in client.get(path).text
    scan = client.post("/api/scan", json={
        "upstream": [{"table": "CUSTOMER_DEMOGRAPHICS", "attrs": ["MARKET_CODE"]}],
        "changeKind": "value_change",
    })
    assert SECRET not in scan.text


def test_findings_link_to_github_once_connected(client, monkeypatch):
    _stub_github(monkeypatch)
    client.post("/api/repo/connect", json={"repo": "aucksy/Ripple", "token": SECRET})
    r = client.post("/api/scan", json={
        "upstream": [{"table": "CUSTOMER_DEMOGRAPHICS", "attrs": ["MARKET_CODE"]}],
        "changeKind": "value_change",
    })
    tpl = r.json()["repo"]["urlTemplate"]
    assert tpl.startswith("https://github.com/aucksy/Ripple/blob/")
    assert "{path}" in tpl and "{line}" in tpl


def test_a_failed_connection_leaves_the_old_one_alone(client, monkeypatch):
    _stub_github(monkeypatch)
    client.post("/api/repo/connect", json={"repo": "aucksy/Ripple", "token": SECRET})
    before = client.get("/api/health").json()["repo"]["files"]

    def boom(ref, token, cfg=None):
        raise ghub.GitHubError("GitHub rejected the access token.")

    monkeypatch.setattr(ghub, "describe", boom)
    bad = client.post("/api/repo/connect", json={"repo": "aucksy/Other", "token": "nope"})
    assert bad.status_code == 502
    assert "token" in bad.json()["detail"].lower()
    still = client.get("/api/health").json()
    assert still["source"] == "github"
    assert still["repo"]["files"] == before


def test_disconnecting_goes_back_to_the_folder(client, monkeypatch):
    # What disconnecting forgets is the token that was typed in. A token set in
    # the environment is a separate thing and stays, so it is cleared here --
    # otherwise this passes or fails on whether the machine running the tests
    # happens to have GITHUB_TOKEN set, which says nothing about disconnecting.
    monkeypatch.setattr(settings, "github_token", "", raising=False)
    _stub_github(monkeypatch)
    client.post("/api/repo/connect", json={"repo": "aucksy/Ripple", "token": SECRET})
    out = client.post("/api/repo/disconnect").json()
    assert out["source"] == "folder"
    assert out["github"] is None
    assert out["tokenSet"] is False
    assert out["repo"]["label"] == settings.repo_label


def test_a_file_that_fails_twice_is_still_one_file_to_check():
    """The "could not read" count is what the whole tool is judged on."""
    from ripple.scanner.sqlread import _one_entry_per_file
    merged = _one_entry_per_file([
        {"file": "a.py", "reason": "ParseError"},
        {"file": "a.py", "reason": "ParseError"},
        {"file": "b.sql", "reason": "TokenError"},
    ])
    assert len(merged) == 2
    by_file = {m["file"]: m for m in merged}
    assert by_file["a.py"]["places"] == 2
    assert by_file["b.sql"]["places"] == 1


def test_no_file_is_listed_twice_after_a_real_scan(client, monkeypatch):
    _stub_github(monkeypatch)
    client.post("/api/repo/connect", json={"repo": "aucksy/Ripple", "token": SECRET})
    r = client.post("/api/scan", json={
        "upstream": [{"table": "CUSTOMER_DEMOGRAPHICS", "attrs": ["MARKET_CODE"]}],
        "changeKind": "value_change",
    }).json()
    files = [u["file"] for u in r["unreadable"]]
    assert len(files) == len(set(files))
    assert r["stats"]["couldNotRead"] == len(set(files))


def test_a_repository_with_nothing_scannable_says_so(monkeypatch):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        add(tar, "o-r-abc/README.md", b"# nothing to scan")
    monkeypatch.setattr(ghub, "describe",
                        lambda ref, token, cfg=None: {"default_branch": "main", "private": False})
    monkeypatch.setattr(ghub, "download_archive", lambda ref, token, cfg=None: buf.getvalue())
    with pytest.raises(ghub.GitHubError) as exc:
        ghub.connect("aucksy/Ripple", SECRET, "", settings)
    assert "scan" in str(exc.value).lower()
