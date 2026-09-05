"""Shared setup for the whole suite.

Ripple has no shipped list of published tables any more. It is the one setting
the tool cannot work out for itself, and a wrong one is the most expensive thing
it can have: on a warehouse that names its published tables anything other than
what was shipped, the default matched NOTHING, and matching nothing did not read
as "I do not know which tables are yours" -- it read as "no production table is
affected", in green, over a change that broke all of them. So nothing is scanned
until somebody says which tables are theirs.

Every test below the ones that check that gate is about something else --
following a column, reading a file, wording a screen -- and each of them stands
for a Ripple somebody has finished setting up. This fixture is that setup, in
one place, so a test about lineage does not have to restate it.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ripple.config import settings                              # noqa: E402
from ripple.production import DEFAULT_TEXT                      # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def a_repository_already_read():
    """The repository, read once before anything asks about it.

    /api/health no longer blocks for the minutes a real read takes -- it answers
    straight away with indexing:true and the screen waits, showing counted
    progress. A test client is not that screen, and every test below is about
    something other than the boot sequence, so the read is done here instead of
    each test having to model the wait.
    """
    from ripple.api import repo_state                            # noqa: PLC0415

    repo_state()


@pytest.fixture
def ready():
    """Ask a test client for health, waiting out the first read the way the
    screen does. Any test about what health SAYS wants this rather than the
    indexing:true answer it gets while the repository is still being opened."""
    import time                                                  # noqa: PLC0415

    def go(client, tries: int = 600) -> dict:
        for _ in range(tries):
            h = client.get("/api/health").json()
            if not h.get("indexing"):
                return h
            time.sleep(0.05)
        raise AssertionError("the repository was never finished being read")

    return go


@pytest.fixture(autouse=True)
def a_configured_ripple():
    """The published-table list a person would have entered, put back after."""
    before = settings.production_text
    settings.set_production(DEFAULT_TEXT)
    yield
    settings.set_production(before)
