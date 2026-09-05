"""The offline app, end to end, and the things that must not be in it."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from conftest import MOCKREPO, SAMPLES
from ripple_offline import prefs
from ripple_offline.app import app, reindex


@pytest.fixture(scope="module")
def client():
    prefs.apply(prefs.save({"repoPath": str(MOCKREPO), "sqlDialect": "bigquery", "maxHops": 4, "prodTables": "_PROD"}))
    reindex()
    return TestClient(app)


@pytest.fixture
def unconfigured(clean_home):
    prefs.apply(prefs.load())
    reindex()
    with TestClient(app) as c:
        yield c
    prefs.apply(prefs.save({"repoPath": str(MOCKREPO), "sqlDialect": "bigquery", "maxHops": 4, "prodTables": "_PROD"}))
    reindex()


# ── nothing that reaches out ───────────────────────────────────────────────
@pytest.mark.parametrize("method,path", [
    ("post", "/api/repo/connect"),
    ("post", "/api/repo/disconnect"),
    ("post", "/api/ai/check"),
    ("post", "/api/ai/connect"),
    ("post", "/api/ai/forget"),
])
def test_the_routes_that_reach_out_do_not_exist(client, method, path):
    """Not disabled, not behind a flag -- absent."""
    assert getattr(client, method)(path).status_code == 404


def test_health_says_nothing_about_ai_or_a_token(client):
    h = client.get("/api/health").json()
    assert "ai" not in h and "github" not in h and "tokenSet" not in h
    assert h["offline"] is True


def test_the_guard_is_reported_honestly(client):
    """The screen claims nothing about being sealed off that this cannot confirm."""
    from ripple_offline import nonet
    out = client.post("/api/offline-check").status_code
    assert out == 405 or out == 404          # it is a GET, and only a GET
    body = client.get("/api/offline-check").json()
    assert body["guardInstalled"] == nonet.installed()


# ── before anything has been chosen ────────────────────────────────────────
def test_a_fresh_machine_does_not_crash_and_says_what_is_missing(unconfigured):
    h = unconfigured.get("/api/health").json()
    assert h["ok"] is True and h["configured"] is False
    assert h["folder"]["state"] == "unset"


def test_ripple_never_scans_its_own_program_folder(unconfigured):
    """An unset folder is an empty path, and an empty path means "here". Without
    care that indexes Ripple's own files and shows them as the repository."""
    h = unconfigured.get("/api/health").json()
    assert h["repo"]["files"] == 0
    assert h["repo"]["path"] == ""


def test_a_scan_before_ripple_is_set_up_is_refused_rather_than_answered(unconfigured):
    """Nothing has been chosen: no folder, and no list of published tables. An
    answer computed from that is worth less than no answer, because "no
    production table is affected" over an empty setup looks exactly like the
    same words over a real scan. So it is refused, and the refusal says what to
    go and do."""
    r = unconfigured.post("/api/scan", json={
        "upstream": [{"table": "customer_demographics", "attrs": ["market_code"]}],
        "changeKind": "value_change"})
    assert r.status_code == 400, r.json()
    assert "published" in r.json()["detail"].lower()


# ── choosing the folder and the dialect ────────────────────────────────────
def test_saving_a_folder_reads_it(clean_home):
    with TestClient(app) as c:
        # The published-table list goes in with the folder. Without it Ripple is
        # not set up: it can read every file and still not know what any of it
        # means for anybody. See prefs.configured.
        h = c.post("/api/settings", json={"repoPath": str(MOCKREPO),
                                          "sqlDialect": "bigquery", "maxHops": 4,
                                          "prodTables": "_PROD"}).json()
        assert h["configured"] is True
        assert h["repo"]["files"] > 15
        assert h["sqlDialect"] == "bigquery"


def test_saving_a_folder_that_is_not_there_is_refused_with_the_reason(client):
    r = client.post("/api/settings", json={"repoPath": r"D:\gone\missing",
                                           "sqlDialect": "bigquery", "maxHops": 4})
    assert r.status_code == 400
    assert "not on this machine any more" in r.json()["detail"]


def test_saving_an_unknown_dialect_is_refused(client):
    r = client.post("/api/settings", json={"repoPath": str(MOCKREPO),
                                           "sqlDialect": "klingon", "maxHops": 4})
    assert r.status_code == 400


def test_a_folder_that_disappears_stops_being_offered(clean_home, tmp_path):
    """Ripple reads the folder into memory when it starts. If the folder is gone
    by the time somebody looks at the screen, the reading is no longer true of
    anything -- and "that folder is gone" beside "24 files ready to scan" is
    worse than either on its own."""
    repo = tmp_path / "a-real-repo"
    repo.mkdir()
    (repo / "load.sql").write_text("CREATE TABLE A_PROD AS SELECT 1 AS X;", encoding="utf-8")
    with TestClient(app) as c:
        h = c.post("/api/settings", json={"repoPath": str(repo),
                                          "sqlDialect": "bigquery", "maxHops": 4}).json()
        assert h["repo"]["files"] == 1 and h["repo"]["exists"] is True

        shutil.rmtree(repo)                       # as if somebody tidied up
        after = c.get("/api/health").json()
        assert after["repo"]["exists"] is False
        assert after["repo"]["files"] == 0, "a folder that is gone cannot have files in it"
        assert "not on this machine any more" in after["folder"]["message"]


def test_a_place_ripple_cannot_write_to_says_what_to_do(client, monkeypatch):
    """Copied into Program Files, or opened straight off a network share, Ripple
    cannot save its settings beside itself. "Something went wrong: 500" tells
    nobody to move the folder."""
    def refuse(*_a, **_kw):
        raise PermissionError(13, "Access is denied")

    monkeypatch.setattr(prefs, "save", refuse)
    r = client.post("/api/settings", json={"repoPath": str(MOCKREPO),
                                           "sqlDialect": "bigquery", "maxHops": 4})
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert "does not allow writing" in detail
    assert "Desktop or Documents" in detail


def test_a_folder_can_be_checked_before_it_is_saved(client):
    out = client.post("/api/settings/check", json={"path": str(MOCKREPO)}).json()
    assert out["ok"] and out["files"] > 15


def test_the_dialect_really_changes_what_is_read(clean_home, tmp_path):
    """The whole reason the setting is on screen. Read as generic SQL, a
    BigQuery file is not read less well -- it is not read at all.

    Measured on BigQuery SQL, not on the plain-SQL mock repository: plain SQL
    reads the same either way, so proving the point there proved nothing. On its
    own client, too — changing the folder on the shared one leaves every test
    after it reading a four-line temporary repository.
    """
    (tmp_path / "snapshot.sql").write_text(
        "CREATE OR REPLACE TABLE `acme.stage.snap` AS\n"
        "SELECT c.customer_id, UPPER(c.market_code) AS mkt_cd\n"
        "FROM `acme.c360.customer_demographics` AS c\n"
        "QUALIFY ROW_NUMBER() OVER (PARTITION BY c.customer_id ORDER BY c.last_upd) = 1;\n",
        encoding="utf-8")
    try:
        with TestClient(app) as c:
            bq = c.post("/api/settings", json={"repoPath": str(tmp_path),
                                               "sqlDialect": "bigquery", "maxHops": 4}).json()
            generic = c.post("/api/settings", json={"repoPath": str(tmp_path),
                                                    "sqlDialect": "", "maxHops": 4}).json()
        assert bq["repo"]["statements"] == 1 and bq["repo"]["unreadable"] == 0
        assert generic["repo"]["statements"] == 0 and generic["repo"]["unreadable"] == 1
    finally:
        prefs.apply(prefs.save({"repoPath": str(MOCKREPO), "sqlDialect": "bigquery",
                                "maxHops": 4, "prodTables": "_PROD"}))
        reindex()


# ── the whole flow ─────────────────────────────────────────────────────────
def test_the_whole_flow_from_an_uploaded_email(client):
    raw = (SAMPLES / "01-market-code-value-change.eml").read_bytes()
    read = client.post("/api/read-email",
                       files={"file": ("01.eml", raw, "message/rfc822")}).json()
    assert read["extractedBy"] == "rules"
    assert read["source"] == "C360"
    assert read["pocName"] == "Priya Raman"
    assert [u["table"].upper() for u in read["upstream"]][0] == "CUSTOMER_DEMOGRAPHICS"

    scan = client.post("/api/scan", json={
        "upstream": [{"table": u["table"], "attrs": u["attrs"]} for u in read["upstream"]],
        "changeKind": read["changeKind"]}).json()
    assert scan["groups"] and scan["stats"]["productionTables"] >= 1

    written = client.post("/api/summary", json={"scan": scan, "vals": read}).json()
    assert written["summary"]["headline"] and written["reply"]["body"]
    assert written["summary"]["writtenBy"] == "rules"

    saved = client.post("/api/history", json={"vals": read, "scan": scan,
                                              "summary": written["summary"], "mode": "email"}).json()
    assert saved["saved"] is True
    rows = client.get("/api/history").json()
    assert any(r["id"] == saved["id"] for r in rows)


def test_an_uploaded_eml_is_read(client):
    raw = (SAMPLES / "02-timestamp-decommission.eml").read_bytes()
    out = client.post("/api/read-email", files={"file": ("02.eml", raw, "message/rfc822")}).json()
    assert out["changeKind"] == "removal"
    assert out["pocTeam"] == "CODN Platform Team"


def test_history_is_kept_rather_than_thrown_away(client):
    """The one thing that is better offline: a real disk."""
    assert client.get("/api/health").json()["limits"]["historyKept"] is True


def test_a_finding_offers_no_link_to_click(client):
    """The files are on this machine. There is nowhere to send anyone."""
    scan = client.post("/api/scan", json={
        "upstream": [{"table": "customer_demographics", "attrs": ["market_code"]}],
        "changeKind": "value_change"}).json()
    assert scan["repo"]["urlTemplate"] == ""


def test_the_honesty_features_are_still_there(client):
    scan = client.post("/api/scan", json={
        "upstream": [{"table": "customer_demographics", "attrs": ["market_code"]}],
        "changeKind": "value_change"}).json()
    assert scan["unreadable"], "the 'could not read' list must survive"
    clean = client.post("/api/scan", json={
        "upstream": [{"table": "prospect_master", "attrs": ["legacy_segment_code"]}],
        "changeKind": "removal"}).json()
    assert clean["mentions_only"] if "mentions_only" in clean else clean["mentionsOnly"]


def test_file_contents_can_be_opened_in_place(client):
    out = client.get("/api/file", params={"path": "odl/customer_profile_odl.sql"}).json()
    assert any("market_code" in line.lower() for line in out["lines"])


def test_a_path_outside_the_index_is_refused(client):
    assert client.get("/api/file", params={"path": "../../secrets.txt"}).status_code == 404


def test_the_offline_page_is_served(client):
    page = client.get("/")
    assert page.status_code == 200
    assert "Ripple Offline" in page.text


# ── knowing when to stop ───────────────────────────────────────────────────
def test_the_page_can_say_it_is_still_there(client):
    """The program has no console window and no window of its own, so the open
    page is the only thing that knows anybody is using it."""
    from ripple_offline import lifecycle

    lifecycle.reset()
    assert client.post("/api/alive").json() == {"ok": True}
    assert lifecycle.facts()["secondsSinceBeat"] is not None


def test_saying_goodbye_does_not_stop_it_on_the_spot(client):
    """A refresh sends the same goodbye. Stopping on it would close Ripple
    every time somebody pressed F5."""
    from ripple_offline import lifecycle

    lifecycle.reset()
    client.post("/api/alive")
    assert client.post("/api/leaving").json() == {"ok": True}
    assert lifecycle.stopping() is False


def test_the_close_button_stops_it(client):
    from ripple_offline import lifecycle

    lifecycle.reset()

    class FakeServer:
        should_exit = False

    server = FakeServer()
    lifecycle.attach(server)
    out = client.post("/api/quit").json()
    assert out["ok"] is True
    assert server.should_exit is True, "the program is still running after being told to stop"
    lifecycle.reset()


# ── which build is this? ───────────────────────────────────────────────────
# It matters more here than anywhere else. This is the copy running on a machine
# nobody can check, handed over as a zip and copied from folder to folder, and
# an old one looks exactly like a new one. "It does not work" has more than once
# turned out to be "that was fixed a while ago, on a copy nobody replaced".
def test_the_offline_health_says_which_build_it_is(client):
    b = client.get("/api/health").json().get("build")
    assert b, "the offline settings screen has nothing to show without this"
    assert b["version"] and b["label"]
    assert b["from"] in {"build", "host", "git", "files"}


def test_the_offline_screen_shows_the_build_card():
    """The stamp is only worth having if it is on a screen. The offline build
    has its own settings view, so adding the card online does not put it here --
    that is exactly how the online-only half of a fix gets shipped alone."""
    offline_js = Path(__file__).resolve().parent.parent / "web" / "offline.js"
    source = offline_js.read_text(encoding="utf-8")
    assert "buildCard(h)" in source, "the offline settings screen must show the build stamp"


def test_the_repository_block_carries_everything_the_screen_reads(client):
    """This build has its own /api/health, and the SCREEN it feeds is the very
    same app.js the online build uses. So a key added to one health block and
    not the other does not fail anywhere -- the offline copy just silently shows
    nothing where the online one shows a number. That is how the file-types-not-
    opened tally shipped online and was blank here.

    Compared against the online block itself rather than against a list written
    out by hand, because a list written out by hand goes stale the same way.
    """
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "Codebase"))
    import inspect
    import re as _re
    from ripple import api as online

    source = inspect.getsource(online.health)
    block = source.split('"repo": {', 1)[1]
    online_keys = set(_re.findall(r'^\s{12}"([A-Za-z]+)":', block, _re.MULTILINE))
    here = set(client.get("/api/health").json()["repo"])
    missing = online_keys - here
    assert not missing, f"the offline repository block is missing {sorted(missing)}"


def test_the_answer_given_while_still_reading_is_a_whole_one(clean_home):
    """One app.js paints both builds. The screen reads this payload before the
    repository has been read, and a key missing from it is a blank on screen and
    nothing at all in a test."""
    from ripple_offline import prefs                              # noqa: PLC0415
    from ripple_offline.app import _health, _still_reading        # noqa: PLC0415

    prefs.apply(prefs.save({"repoPath": str(MOCKREPO), "sqlDialect": "bigquery",
                            "maxHops": 4, "prodTables": "_PROD"}))
    values = prefs.load()
    whole = set(_health())
    partial = set(_still_reading(values, prefs.folder_state(values["repoPath"])))
    missing = sorted(whole - partial)
    assert not missing, f"the still-reading answer never names: {missing}"
