"""Proving that nothing leaves the machine.

The failure this exists to prevent: an offline build ships with something in it
that quietly calls out, nobody notices because the build machine has internet,
and the first anyone hears of it is a hang on the locked-down machine.

So the whole flow runs with outbound connections blocked. If any part of Ripple
reaches out, these tests fail with the address it tried, rather than passing
because this machine happened to be online.
"""
from __future__ import annotations

import os
import socket
import threading
import time
import urllib.error
import urllib.request

import pytest
from fastapi.testclient import TestClient

from conftest import MOCKREPO, SAMPLES
from ripple_offline import nonet, prefs
from ripple_offline.app import app, reindex


@pytest.fixture
def blocked():
    """Outbound blocked, loopback allowed -- the state the built app runs in."""
    nonet.attempts.clear()
    already = nonet.installed()
    nonet.install()
    yield
    if not already:
        nonet.uninstall()
    nonet.attempts.clear()


# ── the guard itself ───────────────────────────────────────────────────────
def test_reaching_out_raises(blocked):
    with pytest.raises(nonet.OutboundBlocked):
        socket.create_connection(("93.184.216.34", 80), timeout=1)


def test_reaching_out_by_name_raises_before_it_is_even_looked_up(blocked):
    """Resolving a name is itself a call off the machine, so it is refused there
    rather than at the connection it would have led to."""
    with pytest.raises(nonet.OutboundBlocked):
        socket.getaddrinfo("api.groq.com", 443)


def test_the_refusal_names_what_was_tried(blocked):
    with pytest.raises(nonet.OutboundBlocked) as caught:
        socket.getaddrinfo("api.example.com", 443)
    assert "api.example.com:443" in str(caught.value)
    assert nonet.attempts and "api.example.com:443" in nonet.attempts[0]


def test_an_http_client_cannot_get_out(blocked):
    """httpx is in the shared engine for the AI that is not here. If anything
    ever calls it offline, this is what happens."""
    import httpx
    with pytest.raises(Exception) as caught:
        httpx.get("https://api.groq.com/openai/v1/models", timeout=2)
    assert "groq" in str(caught.value).lower() or "blocked" in str(caught.value).lower()


def test_a_proxy_cannot_carry_the_call_out_instead(monkeypatch):
    """The one way out that allowing loopback left open.

    A corporate proxy listens on this machine, so a client pointed at it never
    connects to the internet itself: it connects to 127.0.0.1, which the guard
    has to allow because Ripple talks to itself, and the proxy makes the call.
    The address the guard would have refused is never handed to it. Measured
    before this was closed, with a proxy on 127.0.0.1: the same request that was
    refused directly came back 200 with the page in it.
    """
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9")
    monkeypatch.setenv("http_proxy", "http://127.0.0.1:9")
    import httpx

    before = urllib.request.getproxies()
    assert before, "this test is meaningless unless a proxy is there to be taken away"

    nonet.attempts.clear()
    nonet.install()
    try:
        # Both places a proxy can be named, gone: what anything reading the
        # environment would find, and what httpx and requests actually ask.
        assert "HTTPS_PROXY" not in os.environ
        assert urllib.request.getproxies() == {}
        with pytest.raises(Exception) as caught:
            httpx.get("https://api.groq.com/openai/v1/models", timeout=2)
        assert "groq" in str(caught.value).lower() or "blocked" in str(caught.value).lower()
    finally:
        nonet.uninstall()

    # Taken away for as long as the guard is on, and no longer: removing it
    # leaves the machine set up exactly the way it was found. Compared against
    # what was really there rather than against a written-in address, so this
    # says the same thing on a machine that has its own proxy set.
    assert os.environ["HTTPS_PROXY"] == "http://127.0.0.1:9"
    assert urllib.request.getproxies() == before


def test_loopback_still_works(blocked):
    """Ripple talks to itself: the server listens on this machine and the
    browser connects to it. Blocking that would break the app, not protect it."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=2) as client:
            assert client is not None
    finally:
        server.close()


def test_localhost_by_name_still_works(blocked):
    assert socket.getaddrinfo("localhost", 80)


# ── the whole flow, with the network blocked ───────────────────────────────
def test_the_whole_flow_runs_with_nothing_reaching_out(blocked, clean_home):
    prefs.apply(prefs.save({"repoPath": str(MOCKREPO), "sqlDialect": "bigquery", "maxHops": 4, "prodTables": "_PROD"}))
    reindex()
    client = TestClient(app)

    assert client.get("/api/health").json()["repo"]["files"] > 15

    # Uploading the file is the only way in now -- the paste box is gone.
    first = (SAMPLES / "01-market-code-value-change.eml").read_bytes()
    read = client.post("/api/read-email",
                       files={"file": ("01.eml", first, "message/rfc822")}).json()
    assert read["upstream"]

    raw = (SAMPLES / "02-timestamp-decommission.eml").read_bytes()
    uploaded = client.post("/api/read-email",
                           files={"file": ("02.eml", raw, "message/rfc822")}).json()
    assert uploaded["upstream"]

    scan = client.post("/api/scan", json={
        "upstream": [{"table": u["table"], "attrs": u["attrs"]} for u in read["upstream"]],
        "changeKind": read["changeKind"]}).json()
    assert scan["groups"]

    written = client.post("/api/summary", json={"scan": scan, "vals": read}).json()
    assert written["summary"]["headline"] and written["reply"]["body"]

    saved = client.post("/api/history", json={"vals": read, "scan": scan,
                                              "summary": written["summary"], "mode": "email"}).json()
    assert saved["saved"] is True
    assert client.get("/api/history").json()

    client.get("/api/catalog")
    client.get("/api/file", params={"path": "odl/customer_profile_odl.sql"})
    client.get("/")

    assert nonet.attempts == [], (
        "something in Ripple tried to reach the network during a normal run: "
        + ", ".join(nonet.attempts))


def test_the_real_server_serves_over_loopback_with_the_guard_on(blocked, clean_home):
    """The flow above never touches a socket, because the test client speaks to
    the app directly. This runs the actual web server on an actual port, which
    is what the built program does."""
    import uvicorn

    prefs.apply(prefs.save({"repoPath": str(MOCKREPO), "sqlDialect": "bigquery", "maxHops": 4, "prodTables": "_PROD"}))
    reindex()

    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        deadline = time.time() + 20
        page = None
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=2) as r:
                    page = r.read()
                break
            except (urllib.error.URLError, ConnectionError, OSError):
                time.sleep(0.2)
        assert page, "the offline server never answered on loopback"
        assert b'"offline":true' in page.replace(b" ", b"")
        assert nonet.attempts == []
    finally:
        server.should_exit = True
        thread.join(timeout=10)
