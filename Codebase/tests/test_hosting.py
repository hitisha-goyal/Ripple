"""Tests for running Ripple on a hosted, serverless copy (Vercel and friends).

A serverless host is not a laptop. The disk is thrown away between requests, a
request body over about 4.5 MB is refused before Ripple sees it, and a request
is killed after 60 seconds. Ripple has to say so rather than promise laptop
behaviour and quietly fail.

The thing most worth guarding: the word "Saved". Where saving does not last,
the app must say that in the same breath -- not leave someone believing there
is a record when there is not.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ripple import store                                        # noqa: E402
from ripple.api import app                                      # noqa: E402
from ripple.config import Settings, _default_db, settings       # noqa: E402


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def forget_the_cached_repository():
    """The app holds the read repository in one module-level cache. A test that
    points it at a different folder must not leave that behind for the next."""
    yield
    from ripple import api as rapi
    rapi._state.update({"index": None, "parsed": None, "catalog": None,
                        "source": "folder", "conn": None, "token": "", "error": ""})


@pytest.fixture
def hosted(monkeypatch, tmp_path):
    """Settings as they come out on a serverless host."""
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.delenv("RIPPLE_MAX_UPLOAD_BYTES", raising=False)
    monkeypatch.delenv("RIPPLE_MAX_REPO_BYTES", raising=False)
    monkeypatch.delenv("RIPPLE_AI_TIMEOUT", raising=False)
    cfg = Settings()
    # Keep the test off a real /tmp; the path itself is checked separately.
    cfg.db_path = tmp_path / "ripple.db"
    return cfg


# ── what the host actually imposes ─────────────────────────────────────────
def test_a_hosted_copy_knows_it_is_hosted(hosted):
    assert hosted.serverless is True


def test_a_laptop_is_not_treated_as_a_host(monkeypatch):
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)
    assert Settings().serverless is False


def test_history_is_written_to_temporary_space_on_a_host(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.delenv("RIPPLE_DB", raising=False)
    assert _default_db() == "/tmp/ripple.db"


def test_the_upload_ceiling_is_the_hosts_real_one(hosted, monkeypatch):
    """4.5 MB is the platform's limit. Ripple must not advertise 25 MB there."""
    assert hosted.max_upload_bytes <= 4_500_000
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)
    assert Settings().max_upload_bytes > hosted.max_upload_bytes


def test_two_ai_calls_still_fit_inside_the_request_limit(hosted):
    """Writing a summary calls the model twice, one after the other. Both have
    to finish inside 60 seconds or the page dies with no explanation."""
    assert hosted.ai_timeout * 2 < 60


def test_a_host_will_not_promise_to_pull_a_huge_repository(hosted, monkeypatch):
    """Better a clear "too big for this host" than a 60-second blank timeout."""
    assert hosted.max_repo_bytes <= 25_000_000
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)
    assert Settings().max_repo_bytes > hosted.max_repo_bytes


# ── the honesty that matters: "Saved" ──────────────────────────────────────
def test_saving_on_a_host_says_it_may_not_last(hosted):
    out = store.save({"subject": "x"}, {"risk": "low"}, {}, "manual", hosted)
    assert out["saved"] is True
    assert "note" in out, "a hosted copy must warn that the entry can disappear"
    assert "disappear" in out["note"].lower()


def test_saving_on_a_laptop_makes_no_such_excuse(tmp_path, monkeypatch):
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)
    cfg = Settings()
    cfg.db_path = tmp_path / "ripple.db"
    out = store.save({"subject": "x"}, {"risk": "low"}, {}, "manual", cfg)
    assert out["saved"] is True
    assert "note" not in out


def test_history_survives_a_disk_that_refuses_to_be_written(monkeypatch, tmp_path):
    """A read-only disk must produce a readable answer, never a 500."""
    cfg = Settings()
    cfg.db_path = tmp_path / "nope" / "ripple.db"

    def refuse(*a, **k):
        raise OSError("read-only file system")

    monkeypatch.setattr(store.Path, "mkdir", refuse)
    out = store.save({}, {}, {}, "manual", cfg)
    assert out["saved"] is False
    assert "unavailable" in out["reason"]
    assert store.listing(cfg) == []
    assert store.get(1, cfg) is None
    assert store.set_status(1, "Closed", cfg) is False


# ── what the screen is told ────────────────────────────────────────────────
def test_health_reports_the_real_ceilings(client):
    h = client.get("/api/health").json()
    assert "limits" in h
    assert h["limits"]["maxUploadBytes"] == settings.max_upload_bytes
    assert h["limits"]["historyKept"] is not settings.serverless


def test_an_oversized_upload_is_refused_with_the_real_number(client, monkeypatch):
    monkeypatch.setattr(settings, "max_upload_bytes", 1_000_000, raising=False)
    r = client.post("/api/read-email", files={"file": ("big.eml", b"x" * 1_200_001)})
    assert r.status_code == 413
    detail = r.json()["detail"]
    assert "1.2 MB" in detail, detail        # the size it really was
    assert "is 1 MB" in detail, detail       # the limit it really is


# ── serving the site from the app itself ───────────────────────────────────
def test_fonts_are_cached_but_the_app_script_is_not(client):
    """On a hosted copy there is no separate web server: every uncached request
    runs the app. The fonts are a third of a megabyte and never change."""
    font = client.get("/static/fonts/public-sans-400-latin.woff2")
    assert font.status_code == 200
    assert "max-age" in font.headers.get("cache-control", "")

    script = client.get("/static/app.js")
    assert script.status_code == 200
    assert "no-store" in script.headers.get("cache-control", "")


def test_the_page_still_loads_when_the_repository_folder_is_missing(client, monkeypatch):
    """Vercel bundles mockrepo, but if a host ever loses it the site must still
    open and say so, not return a blank error."""
    monkeypatch.setattr(settings, "repo_path", Path("/definitely/not/here"), raising=False)
    from ripple import api as rapi
    rapi._state["index"] = None          # force a re-read from the bad path
    h = client.get("/api/health")
    assert h.status_code == 200
    assert h.json()["repo"]["exists"] is False
    assert h.json()["repo"]["files"] == 0


def test_the_answer_given_while_still_reading_is_a_whole_one():
    """The screen paints from this payload before the repository has been read,
    and a key missing from it is a blank on screen and nothing at all in a test.
    Every key the finished answer carries has to be here too, with real zeros
    rather than absent."""
    from ripple.api import _still_reading, health                 # noqa: PLC0415

    whole = set(health())
    partial = set(_still_reading())
    missing = sorted(whole - partial)
    assert not missing, f"the still-reading answer never names: {missing}"
