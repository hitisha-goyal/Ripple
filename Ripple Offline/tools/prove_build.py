"""Start the packaged program and drive it through its own API.

    ..\\Codebase\\.venv\\Scripts\\python tools\\prove_build.py

"It built" proves nothing. "It started, read a folder, followed a whole table,
read a SELECT * view's column list, refused the request it must refuse, wrote
a summary, and stopped when asked" proves the program somebody will unpack
does what this commit says it does. The cloud build runs this between packing
the zip and publishing it, so a zip that fails here is never published.

Every check below names a fact. The block printed at the end is what the
build log carries, so anybody can read what was proved without re-running it.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent                      # D:\Apps\Ripple
OUT = ROOT / "Ripple Offline" / "dist" / "Ripple Offline"
EXE = OUT / "Ripple Offline.exe"
LOG = OUT / "ripple-log.txt"
MOCKREPO = ROOT / "Codebase" / "mockrepo"

sys.path.insert(0, str(ROOT / "Codebase"))
from ripple.build_info import VERSION                                # noqa: E402

PROVED: list[str] = []


def proved(fact: str) -> None:
    PROVED.append(fact)
    print("  proved:", fact, flush=True)


def call(method: str, url: str, body=None, timeout: int = 120):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, method=method, data=data,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            text = r.read().decode()
            return r.status, (json.loads(text) if text.strip() else {})
    except urllib.error.HTTPError as e:
        text = e.read().decode()
        try:
            return e.code, json.loads(text)
        except json.JSONDecodeError:
            return e.code, {"detail": text[:400]}


def wait_for(what: str, check, secs: int):
    end = time.time() + secs
    last = None
    while time.time() < end:
        try:
            found = check()
            if found:
                return found
        except Exception as exc:                          # noqa: BLE001
            last = exc
        time.sleep(0.5)
    raise SystemExit(f"timed out waiting for {what}" + (f" ({last})" if last else ""))


def port_from_log() -> int | None:
    if not LOG.is_file():
        return None
    m = re.search(r"open http://localhost:(\d+)", LOG.read_text(encoding="utf-8", errors="replace"))
    return int(m.group(1)) if m else None


def main() -> int:
    if not EXE.is_file():
        print(f"{EXE} is not there. Run build.py first.")
        return 1
    for stray in ("ripple-settings.json", "ripple-history.db", "ripple-log.txt"):
        p = OUT / stray
        if p.exists():
            p.unlink()

    print(f"\n  starting {EXE.name} ({EXE.stat().st_size / 1_000_000:.1f} MB)")
    proc = subprocess.Popen([str(EXE), "--no-browser"], cwd=str(OUT))
    try:
        port = wait_for("the program to say which port it took", port_from_log, 90)
        base = f"http://127.0.0.1:{port}"
        proved(f"the program started and listens on {base}")

        def healthy():
            code, h = call("GET", base + "/api/health", timeout=10)
            return h if code == 200 and h.get("ok") else None

        h = wait_for("/api/health to answer", healthy, 90)
        assert h.get("offline") is True, "health does not say offline"
        build = h.get("build") or {}
        # --any-version is for trying this tool against an OLD build on a
        # person's machine. The cloud build never passes it: there, the
        # program must be the version this commit says it is.
        if "--any-version" not in sys.argv:
            assert build.get("version") == VERSION, \
                f"the program says version {build.get('version')}, the code says {VERSION}"
            assert build.get("commit") and "+edits" not in build["commit"], \
                f"the build stamp is {build.get('commit')!r} - it must name one clean commit"
        proved(f"it is version {build.get('version')} at commit {build.get('commit')}, "
               f"and says it is the offline build")

        code, guard = call("GET", base + "/api/offline-check", timeout=10)
        assert code == 200 and guard.get("guardInstalled") is True, f"the network guard: {code} {guard}"
        proved("the network guard reports itself installed")

        code, out = call("POST", base + "/api/settings", {
            "repoPath": str(MOCKREPO), "sqlDialect": "bigquery", "maxHops": 4,
            "prodTables": "_PROD, _PRD, _PUBLISHED"})
        assert code == 200, f"/api/settings: {code} {out}"

        def read():
            code, h = call("GET", base + "/api/health", timeout=10)
            return h if code == 200 and not h.get("indexing") and (h.get("repo") or {}).get("files") else None

        h = wait_for("the practice pipeline to be read", read, 180)
        proved(f"it read the practice pipeline: {h['repo']['files']} files, "
               f"{h['repo']['statements']} statements")

        code, sc = call("POST", base + "/api/scan", {
            "upstream": [{"table": "CUSTOMER_DEMOGRAPHICS", "attrs": []}], "changeKind": "removal"})
        assert code == 400 and "Whole table" in str(sc.get("detail")), f"a table with nothing on it: {code} {sc}"
        proved("a table with no attribute and no whole mark is refused, with the sentence that says what to do")

        code, sc = call("POST", base + "/api/scan", {
            "upstream": [{"table": "CUSTOMER_DEMOGRAPHICS", "attrs": [], "whole": True}],
            "changeKind": "removal"})
        assert code == 200, f"whole-table scan: {code} {sc}"
        assert sc["stats"]["wholeTables"] == 1 and sc["groups"], "the whole table reached no published table"
        proved(f"a whole-table scan of CUSTOMER_DEMOGRAPHICS reaches "
               f"{len(sc['groups'])} published tables: {', '.join(g['prod'] for g in sc['groups'])}")

        code, col = call("POST", base + "/api/scan", {
            "upstream": [{"table": "CUSTOMER_DEMOGRAPHICS", "attrs": ["MARKET_CODE"]}],
            "changeKind": "removal"})
        assert code == 200, f"column scan: {code} {col}"
        star = next((s for s in col["starTables"] if s["table"] == "vw_everything"), None)
        assert star and star["known"] is True and star["listedIn"].endswith("customer_demographics.sql"), \
            f"the SELECT * view: {star}"
        assert col["stats"]["tablesNotVisible"] == 0
        proved(f"the SELECT * view's column list was read from {star['listedIn']} "
               f"({star['columns']} columns), so nothing is marked not readable")

        code, s = call("POST", base + "/api/summary", {
            "scan": sc,
            "vals": {"upstream": [{"table": "CUSTOMER_DEMOGRAPHICS", "attrs": [], "whole": True}],
                     "effectiveLabel": "18 Sep 2026", "pocName": "Priya Raman",
                     "subject": "CUSTOMER_DEMOGRAPHICS decommission"}})
        assert code == 200 and s["summary"]["headline"], f"summary: {code}"
        assert "the whole of CUSTOMER_DEMOGRAPHICS" in s["reply"]["body"]
        proved(f"the summary reads: {s['summary']['headline']}")

        code, r = call("POST", base + "/api/production/read", {
            "text": "prj-p-demo:foundation.final_targeting_prod\nmarket_rollup_prod (published)\n"
                    "final_odl_prod - the ODL feed\n"})
        assert code == 200 and r["nameCount"] == 3, f"production read: {code} {r.get('nameCount')}"
        assert r["check"]["foundCount"] == 3, f"the three shapes: {r['check']}"
        proved("the published-table list reads the colon form, a note in brackets and a "
               "description after the name, and finds all three")
    finally:
        try:
            call("POST", base + "/api/quit", {}, timeout=5)        # noqa: F821
        except Exception:                                          # noqa: BLE001
            pass
        try:
            proc.wait(timeout=30)
            proved("it stopped when asked")
        except subprocess.TimeoutExpired:
            proc.kill()
            print("  the program did not stop when asked; it was killed")
            return 1

    print("\n  PROVED, from the packaged program itself:")
    for fact in PROVED:
        print("   -", fact)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
