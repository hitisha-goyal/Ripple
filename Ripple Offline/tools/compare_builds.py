r"""Do the two Ripples give the same answer? Ask them both and compare.

    ..\Codebase\.venv\Scripts\python tools\compare_builds.py

There are two ways to run Ripple: the folder started by a batch file, and the
packaged program. They share ONE analysis engine and were never meant to differ
in what they report -- but they do NOT share a route layer. ripple_offline/app.py
rewrites every route and calls the same engine underneath, and two copies of glue
code is exactly where drift lives.

It has drifted twice already. A health key added to one showed blank on the other
and nothing failed anywhere. And repo.branch defaulted to "main" in one while the
other read the real branch off the folder, so the same folder produced a different
Repository step depending on which Ripple somebody opened.

Neither was caught by any test, because each build's tests only ever asked its own
build. So this asks BOTH the same question about the SAME folder and compares the
whole answer, leaf by leaf.

Run it before showing either build to anybody who matters. It needs the packaged
program to have been built already (python build.py).
"""
from __future__ import annotations

import json
import subprocess
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
BAT_DIR = ROOT / "RIPPLE COPILOT DEMO"
EXE = ROOT / "Ripple Offline" / "dist" / "Ripple Offline" / "Ripple Offline.exe"
PY = ROOT / "Codebase" / ".venv" / "Scripts" / "python.exe"

# One folder for both, so any difference is the build and not the input.
REPO = ROOT / "Codebase" / "mockrepo"
TABLES = "cust360_customer_demographics\nfoundation.cust360_customer_address"
SCAN = {
    "upstream": [{"table": "customer_demographics", "attrs": ["market_code"]}],
    "changeKind": "column",
    "effectiveDate": "2026-09-18",
    "vals": {},
}

# Values that MUST differ between a source folder and a packaged program, and
# are not drift. Anything not named here has to match exactly.
ALLOWED = ("build.", "generatedAt", "elapsed", "ms", "analysisId", "id", "when")


def call(port: int, path: str, body: dict | None = None):
    url = f"http://127.0.0.1:{port}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET")
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read().decode())


def wait_for(seconds: int = 60) -> int:
    """Whichever port it took. Both search 8000 upwards and print what they got."""
    end = time.time() + seconds
    while time.time() < end:
        for p in range(8000, 8021):
            try:
                call(p, "/api/health")
                return p
            except Exception:
                continue
        time.sleep(1)
    raise SystemExit("neither build answered on 8000-8020")


def setup_bat(port: int) -> None:
    call(port, "/api/repo/folder", {"path": str(REPO)})
    call(port, "/api/production", {"text": TABLES})


def setup_exe(port: int) -> None:
    """The packaged build saves folder, dialect and the published list through
    ONE route. A different shape is fine; a different ANSWER is not."""
    now = call(port, "/api/settings")
    call(port, "/api/settings", {
        "repoPath": str(REPO),
        "sqlDialect": now["values"].get("sqlDialect", ""),
        "prodTables": TABLES,
    })


def flatten(o, prefix="") -> dict:
    """Every leaf in the answer by its full path, so nothing hides in a nest."""
    out = {}
    if isinstance(o, dict):
        for k, v in o.items():
            out.update(flatten(v, f"{prefix}.{k}" if prefix else k))
    elif isinstance(o, list):
        out[f"{prefix}[len]"] = len(o)
        for i, v in enumerate(o):
            out.update(flatten(v, f"{prefix}[{i}]"))
    else:
        out[prefix] = o
    return out


def ask_the_batch_build() -> tuple[dict, dict]:
    proc = subprocess.Popen([str(PY), "run.py", "--no-browser"], cwd=str(BAT_DIR),
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        port = wait_for()
        print(f"   the batch build answered on {port}")
        setup_bat(port)
        return call(port, "/api/scan", SCAN), call(port, "/api/health")
    finally:
        proc.terminate()
        proc.wait(timeout=30)


def ask_the_packaged_build() -> tuple[dict, dict]:
    if not EXE.is_file():
        raise SystemExit(f"{EXE} is not there. Run python build.py first.")
    proc = subprocess.Popen([str(EXE)], cwd=str(EXE.parent),
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        port = wait_for()
        print(f"   the packaged build answered on {port}")
        setup_exe(port)
        return call(port, "/api/scan", SCAN), call(port, "/api/health")
    finally:
        subprocess.run(["taskkill", "/F", "/IM", EXE.name], capture_output=True)
        proc.wait(timeout=30)


def main() -> int:
    print(f"\nAsking both builds the same question about {REPO}\n")
    bat_scan, bat_health = ask_the_batch_build()
    time.sleep(3)
    exe_scan, exe_health = ask_the_packaged_build()

    a, b = flatten(bat_scan), flatten(exe_scan)
    keys = sorted(set(a) | set(b))
    diffs = [(k, a.get(k, "<missing>"), b.get(k, "<missing>")) for k in keys
             if not any(part in k for part in ALLOWED)
             and a.get(k, "<missing>") != b.get(k, "<missing>")]

    print(f"\nThe answer: {len(keys)} values compared")
    print(f"  risk       batch {bat_scan.get('risk')!r}   packaged {exe_scan.get('risk')!r}")
    if not diffs:
        print("  IDENTICAL - every value in the answer matches")
    else:
        print(f"  {len(diffs)} DIFFERENCES - these are drift, and each one is a bug:")
        for k, x, y in diffs[:40]:
            print(f"    {k}\n        batch   : {str(x)[:110]}\n        packaged: {str(y)[:110]}")

    # The health block legitimately differs: one has an AI key box and a GitHub
    # source, the other has a dialect list and a folder browser. Reported so a
    # NEW difference here is visible, never asserted on.
    ha, hb = set(flatten(bat_health)), set(flatten(exe_health))
    print(f"\nThe settings each screen can show (expected to differ):")
    print(f"  only the batch build has    : {len(ha - hb)} values (AI and GitHub)")
    print(f"  only the packaged build has : {len(hb - ha)} values (dialects, folder browser, offline)")
    return 1 if diffs else 0


if __name__ == "__main__":
    raise SystemExit(main())
