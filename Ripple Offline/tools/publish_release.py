"""Publish Ripple Offline to the releases page, keeping only the latest.

    ..\\..\\Codebase\\.venv\\Scripts\\python tools\\publish_release.py

The version is read from ``ripple/build_info.py``, so the tag, the download's
filename and the line on the settings screen can never disagree -- they are one
number, written down once.

Any older release is deleted first. Git keeps every version of every file for
ever, which is why the download stopped being committed at all; a releases page
that quietly piles them up has the same problem one folder further out.

The token comes from the git credential helper, which already holds one for
this repository. Nothing here stores a secret, and nothing prints one.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import subprocess
import sys
import urllib.error
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent                      # D:\Apps\Ripple
REPO = "aucksy/Ripple"
API = f"https://api.github.com/repos/{REPO}"

sys.path.insert(0, str(ROOT / "Codebase"))
from ripple.build_info import VERSION                                # noqa: E402

TAG = f"v{VERSION}"
ZIP = ROOT / "Ripple Offline" / "dist" / f"Ripple-Offline-{TAG}.zip"


def token() -> str:
    """The repository token: the cloud build's own, or the git credential helper's.

    The cloud job (.github/workflows/release.yml) hands its token in as
    GITHUB_TOKEN. On a person's machine the credential helper already holds
    one for this repository. Nothing here stores a secret, and nothing prints one.
    """
    for name in ("GITHUB_TOKEN", "RIPPLE_RELEASE_TOKEN"):
        if os.environ.get(name, "").strip():
            return os.environ[name].strip()
    done = subprocess.run(
        ["git", "credential", "fill"], cwd=str(ROOT), text=True,
        input="protocol=https\nhost=github.com\n\n", capture_output=True)
    for line in done.stdout.splitlines():
        if line.startswith("password="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("No GitHub token in GITHUB_TOKEN or the credential helper. "
                     "Nothing was published.")


def call(method: str, url: str, tok: str, body=None, raw=None, content_type=None):
    headers = {
        "Authorization": f"Bearer {tok}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if content_type:
        headers["Content-Type"] = content_type
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(url, method=method, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            text = r.read().decode()
            return r.status, (json.loads(text) if text.strip() else {})
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode()[:400]}


def notes() -> str:
    """What the release page says. Kept next to the code it describes."""
    return (
        f"**Ripple Offline {TAG}** - the whole program, for a machine with no "
        "internet.\n\n"
        "Download the zip, unpack it anywhere, double-click `Ripple Offline.exe`. "
        "Nothing to install, nothing registered, no administrator rights. "
        "`READ-ME-FIRST-for-IT.txt` inside is the page to hand to whoever has to "
        "approve it.\n\n"
        "The settings screen says which build you are running, so \"it does not "
        "work\" can be told apart from \"that was fixed, on a copy nobody "
        "installed\".\n"
    )


def main() -> int:
    if not ZIP.is_file():
        print(f"{ZIP.name} is not in dist/. Run build.py first.")
        return 1
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(ROOT),
                          capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=str(ROOT),
                           capture_output=True, text=True).stdout.strip()
    if dirty:
        print("The working copy has changes in it, so the build stamp inside the zip")
        print("names a commit plus unrecorded edits. Commit first, rebuild, then publish.")
        return 1

    tok = token()
    # The fingerprint of what leaves here. The releases page reports the
    # fingerprint of what arrived, so the two can be compared without
    # downloading anything.
    digest = hashlib.sha256(ZIP.read_bytes()).hexdigest()
    print(f"publishing {ZIP.name} ({ZIP.stat().st_size / 1_000_000:.0f} MB) at {head[:7]}")
    print(f"  sha256: {digest}")

    code, existing = call("GET", f"{API}/releases", tok)
    if code == 200:
        for rel in existing:
            print(f"  deleting the previous release {rel['tag_name']}")
            call("DELETE", f"{API}/releases/{rel['id']}", tok)
            call("DELETE", f"{API}/git/refs/tags/{rel['tag_name']}", tok)

    code, out = call("POST", f"{API}/releases", tok, {
        "tag_name": TAG, "target_commitish": head,
        "name": f"Ripple Offline {TAG}", "body": notes(),
        "draft": False, "prerelease": False,
    })
    if code not in (200, 201):
        print("  the release was not created:", code, out)
        return 1
    print("  release:", out["html_url"])

    upload = out["upload_url"].split("{")[0] + f"?name={ZIP.name}"
    code, asset = call("POST", upload, tok, raw=ZIP.read_bytes(),
                       content_type="application/zip")
    if code not in (200, 201):
        print("  the zip was not uploaded:", code, asset)
        return 1
    print("  download:", asset["browser_download_url"])
    print(f"  arrived : {asset.get('size', 0):,} bytes, {asset.get('digest') or 'no digest reported'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
