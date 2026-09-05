"""What is, and is not, inside the executable that gets copied across.

The strongest form of "offline": the code that could reach out is not in the
program at all. These tests read the built executable and check that — so if
somebody ever wires the AI reader or the repository downloader back into the
offline app, the build stops being honest and this says so.

Skipped when there is no build yet, so the suite still runs from a fresh clone.
"""
from __future__ import annotations

from pathlib import Path

import pytest

DIST = Path(__file__).resolve().parent.parent / "dist" / "Ripple Offline"
EXE = DIST / "Ripple Offline.exe"

# Reached from the offline app, so they have to be in there.
ENGINE_NEEDED = (
    "ripple.catalog", "ripple.config", "ripple.narrative", "ripple.notification",
    "ripple.store", "ripple.scanner.lineage", "ripple.scanner.repo", "ripple.scanner.sqlread",
)
# The parts of the shared code that talk to the outside world, and the HTTP
# client they would need. None of them belongs in this build.
MUST_NOT_BE_BUNDLED = ("ripple.ai", "ripple.api", "ripple.scanner.github", "httpx", "httpcore")


@pytest.fixture(scope="module")
def bundled(tmp_path_factory):
    if not EXE.is_file():
        pytest.skip("no build yet - run build.py first")
    from PyInstaller.archive.readers import CArchiveReader, ZlibArchiveReader
    archive = CArchiveReader(str(EXE))
    modules: list[str] = []
    for name in archive.toc:
        if not name.endswith(".pyz"):
            continue
        holder = tmp_path_factory.mktemp("pyz") / "archive.pyz"
        holder.write_bytes(archive.extract(name))
        modules += list(ZlibArchiveReader(str(holder)).toc)
    return set(modules)


@pytest.mark.parametrize("module", ENGINE_NEEDED)
def test_the_shared_engine_is_inside_the_executable(bundled, module):
    """Pulled in from Codebase/ripple at build time. There is no second copy of
    it on disk to go stale."""
    assert module in bundled


@pytest.mark.parametrize("module", MUST_NOT_BE_BUNDLED)
def test_nothing_that_can_reach_out_is_inside_the_executable(bundled, module):
    assert not any(m == module or m.startswith(module + ".") for m in bundled), \
        f"{module} was packaged into the offline build"


def test_the_offline_front_end_travels_with_it():
    assert (DIST / "_internal" / "web" / "index.html").is_file() if EXE.is_file() else True


def test_the_front_end_in_the_build_has_nothing_that_reaches_out():
    if not EXE.is_file():
        pytest.skip("no build yet - run build.py first")
    from ripple_offline import webbuild
    shipped = (DIST / "_internal" / "web" / "app.js").read_text(encoding="utf-8").lower()
    for word in webbuild.BANNED:
        assert word not in shipped, f"the shipped front end mentions {word}"


def test_the_fonts_travel_with_it():
    """A font fetched from the internet is a blank-looking page on a machine
    that has none."""
    if not EXE.is_file():
        pytest.skip("no build yet - run build.py first")
    assert len(list((DIST / "_internal" / "web" / "fonts").glob("*.woff2"))) > 8
