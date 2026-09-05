"""Pointing Ripple at your own SQL, from the screen.

RIPPLE_REPO decides which folder Ripple starts on. That is right for a server
somebody administers and wrong for a laptop, where it meant the only way to read
your own SQL was to edit a file and restart. Until you did, every answer
described the small practice pipeline -- confidently, correctly, and about
nothing anybody cares about. That is the failure this route exists to remove,
and it is the same shape as every other one in this product: a clean answer to
the wrong question.

Three things are guarded.

A path that is wrong has to be REFUSED, not read. A folder that is not there is
a typo, and a typo is not an empty repository. Accepted quietly it would index
zero files and every scan after it would say nothing was found, which reads as
"no impact" and is the one sentence this tool may never get wrong.

Everything from the previous folder has to go. A repository half read from one
folder and half from another would answer about neither, and nothing on screen
could show it had happened.

And the screen must not promise the choice will last. There is nowhere to write
it down, so it says so.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ripple.api import app                                      # noqa: E402
from ripple.config import settings                              # noqa: E402

CODEBASE = Path(__file__).resolve().parent.parent


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """Put the folder back afterwards -- settings is a live singleton."""
    was = (settings.repo_path, settings.repo_label, settings.repo_source)
    yield TestClient(app)
    settings.repo_path, settings.repo_label, settings.repo_source = was


def test_a_folder_on_this_machine_can_be_chosen_from_the_screen(client):
    """The whole point. Without this the build reads the practice pipeline
    for ever, whatever anybody does on screen."""
    target = CODEBASE / "mockrepo"
    r = client.post("/api/repo/folder", json={"path": str(target)})
    assert r.status_code == 200, r.text
    h = r.json()
    assert Path(h["repo"]["path"]) == target.resolve(), h["repo"]
    assert h["repo"]["files"] > 0, "it accepted the folder and read nothing out of it"


def test_a_folder_that_is_not_there_is_refused_and_not_read_as_empty(client):
    """The dangerous one. A typo indexes zero files, every scan then finds
    nothing, and finding nothing reads as "no impact"."""
    r = client.post("/api/repo/folder", json={"path": r"C:\this\does\not\exist\anywhere"})
    assert r.status_code == 400, "a folder that does not exist was accepted"
    said = r.json()["detail"]
    assert "no folder at" in said.lower(), said
    assert "typo" in said.lower(), (
        "the message does not say a wrong path is a typo rather than an empty "
        "repository, which is the mistake somebody is about to make"
    )


def test_a_file_is_not_a_folder(client, tmp_path):
    f = tmp_path / "one.sql"
    f.write_text("SELECT 1", encoding="utf-8")
    r = client.post("/api/repo/folder", json={"path": str(f)})
    assert r.status_code == 400
    assert "not a folder" in r.json()["detail"].lower()


def test_an_empty_box_is_refused_rather_than_meaning_anything(client):
    r = client.post("/api/repo/folder", json={"path": "   "})
    assert r.status_code == 400
    assert "type the folder" in r.json()["detail"].lower()


def test_a_path_pasted_with_quotes_round_it_still_works(client):
    """Windows Explorer's "Copy as path" wraps the path in quotation marks, and
    pasting that in is the most likely single thing anybody will do."""
    target = CODEBASE / "mockrepo"
    r = client.post("/api/repo/folder", json={"path": f'"{target}"'})
    assert r.status_code == 200, r.text
    assert Path(r.json()["repo"]["path"]) == target.resolve()


def test_choosing_a_folder_throws_away_what_was_read_from_the_last_one(client):
    """Half of one repository and half of another answers about neither."""
    first = CODEBASE / "mockrepo"
    client.post("/api/repo/folder", json={"path": str(first)})
    before = client.get("/api/health").json()["repo"]["files"]
    assert before > 0

    empty = CODEBASE / "tests"          # a real folder with no SQL in it
    r = client.post("/api/repo/folder", json={"path": str(empty)})
    assert r.status_code == 200, r.text
    after = r.json()["repo"]
    assert Path(after["path"]) == empty.resolve()
    assert after["files"] != before or after["statements"] == 0, (
        "the counts did not change, so what was read from the first folder is "
        "still in place while the screen names the second"
    )


def test_the_screen_says_the_choice_does_not_survive_a_restart(client):
    """There is nowhere to write it down. Saying otherwise, or saying nothing,
    lets somebody believe a folder they chose is still chosen tomorrow."""
    js = (CODEBASE / "web" / "app.js").read_text(encoding="utf-8")
    assert "/api/repo/folder" in js, "no screen calls the route"
    assert "Set RIPPLE_REPO to keep it after a restart" in js, (
        "the folder box never says the choice is only held while Ripple runs"
    )


def test_the_screen_clears_a_result_that_belonged_to_the_other_folder():
    """A finding left on screen after the folder changes is right-looking and
    about a repository nobody is reading any more."""
    js = (CODEBASE / "web" / "app.js").read_text(encoding="utf-8")
    box = js.split("function folderBox(", 1)[1].split("\nfunction ", 1)[0]
    assert "S.scan = null" in box, "the previous scan survives a folder change"
    assert "S.summary = null" in box, "the previous summary survives a folder change"
