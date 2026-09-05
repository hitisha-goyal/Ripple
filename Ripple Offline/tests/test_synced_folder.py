"""Noticing that Ripple's own folder is one something uploads to the cloud.

Everyone in this office has OneDrive sync switched on, so the folder Ripple gets
copied into is very likely a folder OneDrive uploads. Ripple keeps its settings,
its saved history and its log beside the executable, which is what makes the
folder portable -- and also means all of it, plus the 44 MB program itself, goes
up to the company's cloud.

Neither is a reason to stop. Both are a reason to say so on screen instead of
letting somebody find out later.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from ripple_offline import synced


def test_an_ordinary_folder_says_nothing(monkeypatch, tmp_path):
    """The quiet case has to stay quiet. A warning on every machine is a warning
    nobody reads on the machine where it matters."""
    for var in ("OneDrive", "OneDriveCommercial", "OneDriveConsumer"):
        monkeypatch.delenv(var, raising=False)
    got = synced.detect(tmp_path / "Ripple Offline")
    assert got["synced"] is False
    assert got["client"] == ""


def test_the_onedrive_environment_variable_is_believed(monkeypatch, tmp_path):
    """The reliable signal, because it comes from OneDrive itself."""
    root = tmp_path / "OD"
    here = root / "Desktop" / "Ripple Offline"
    here.mkdir(parents=True)
    monkeypatch.setenv("OneDrive", str(root))
    got = synced.detect(here)
    assert got["synced"] is True
    assert got["client"] == "OneDrive"


def test_a_work_account_folder_is_recognised_by_name(monkeypatch, tmp_path):
    """A work account names its root "OneDrive - Contoso Ltd", and on a machine
    where the environment variable is not set that name is all there is."""
    for var in ("OneDrive", "OneDriveCommercial", "OneDriveConsumer"):
        monkeypatch.delenv(var, raising=False)
    here = tmp_path / "OneDrive - Contoso Ltd" / "Desktop" / "Ripple Offline"
    here.mkdir(parents=True)
    got = synced.detect(here)
    assert got["synced"] is True
    assert got["client"] == "OneDrive"


@pytest.mark.parametrize("folder,client", [
    ("Dropbox", "Dropbox"),
    ("Google Drive", "Google Drive"),
    ("Box", "Box"),
])
def test_the_other_clients_people_have(monkeypatch, tmp_path, folder, client):
    for var in ("OneDrive", "OneDriveCommercial", "OneDriveConsumer"):
        monkeypatch.delenv(var, raising=False)
    here = tmp_path / folder / "Ripple Offline"
    here.mkdir(parents=True)
    assert synced.detect(here)["client"] == client


def test_a_folder_that_merely_mentions_a_client_is_not_one(monkeypatch, tmp_path):
    """Matched on whole folder names, never as substrings -- otherwise a folder
    called "dropbox-migration-notes" raises a warning about nothing."""
    for var in ("OneDrive", "OneDriveCommercial", "OneDriveConsumer"):
        monkeypatch.delenv(var, raising=False)
    here = tmp_path / "dropbox-migration-notes" / "Ripple Offline"
    here.mkdir(parents=True)
    assert synced.detect(here)["synced"] is False


def test_the_running_program_reports_it(monkeypatch, clean_home):
    """It has to reach the screen, not just exist as a function."""
    from fastapi.testclient import TestClient
    from ripple_offline import app as app_mod, paths

    monkeypatch.setenv("OneDrive", str(paths.app_dir()))
    got = TestClient(app_mod.app).get("/api/health").json()
    assert got["syncedFolder"]["synced"] is True
    assert got["syncedFolder"]["client"] == "OneDrive"
