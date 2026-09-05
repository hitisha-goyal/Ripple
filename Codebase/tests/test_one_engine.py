"""One engine, three editions.

Ripple ships three ways: run locally, hosted on Vercel, and as a program that
runs where there is no internet. All three have to be the same tool. A fix made
once must appear in all three, and a fix that only reaches one of them is worse
than no fix -- somebody reads a result from the edition that still has the bug
and has no way of knowing which one they were looking at.

The rule is that there is exactly one copy of the analysis engine and one copy
of the front end, both in ``Codebase``. These tests fail the moment a second
copy appears.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

CODEBASE = Path(__file__).resolve().parent.parent
ROOT = CODEBASE.parent
OFFLINE = ROOT / "Ripple Offline"


def test_the_hosted_copy_runs_the_very_same_application():
    """Vercel imports api/index.py. If that ever built its own app, the hosted
    copy would drift away from the one every test here is run against."""
    source = (CODEBASE / "api" / "index.py").read_text(encoding="utf-8")
    assert "from ripple.api import app" in source
    assert "FastAPI(" not in source, "the hosted copy must not build an app of its own"

    sys.path.insert(0, str(CODEBASE / "api"))
    import index                                            # noqa: E402
    from ripple.api import app as shared                    # noqa: E402

    assert index.app is shared, "the hosted copy is running a different application"


def test_the_offline_edition_has_no_engine_of_its_own():
    """Two copies would drift, and the drifting one would be the copy running
    where nobody can check it."""
    if not OFFLINE.is_dir():
        return
    assert not (OFFLINE / "ripple").exists(), "Ripple Offline has forked the engine"
    for name in ("lineage.py", "sqlread.py", "catalog.py", "narrative.py", "config.py"):
        copies = [p for p in OFFLINE.rglob(name)
                  if "dist" not in p.parts and "build" not in p.parts]
        assert not copies, f"{name} has been copied into Ripple Offline: {copies}"


def test_the_offline_edition_has_no_front_end_of_its_own():
    """Its screens are generated from Codebase/web/app.js with the online-only
    parts cut out. offline.js holds only what genuinely differs."""
    if not OFFLINE.is_dir():
        return
    web = OFFLINE / "web"
    if not web.is_dir():
        return
    assert not (web / "index.html").exists(), "Ripple Offline has forked the page"
    assert not (web / "styles.css").exists(), "Ripple Offline has forked the stylesheet"
    assert sorted(p.name for p in web.iterdir()) == ["offline.js"], \
        "only the offline-only screens belong here"


def test_the_markers_that_split_the_two_editions_are_still_paired():
    """The offline build deletes everything between these. One lost marker and
    the build either ships a key box onto a locked-down machine or deletes half
    the app, so they are counted here as well as at build time."""
    js = (CODEBASE / "web" / "app.js").read_text(encoding="utf-8")
    opens = js.count("//<online-only>")
    closes = js.count("//</online-only>")
    assert opens == closes, f"{opens} online-only blocks opened, {closes} closed"
    assert opens > 0, "the markers have gone entirely"


def test_a_fix_to_the_engine_is_visible_from_all_three_editions():
    """Named checks rather than a vague one: these are the things fixed for the
    SELECT * and hop-limit work, and every edition reads them from one place."""
    from ripple.config import Settings
    from ripple.scanner.lineage import ScanResult
    from ripple.scanner.sqlread import same_table, star_carries

    # Zero means "follow until the code runs out", which is the default. A
    # number here is a wall, and every wall reported itself as the end of the
    # warehouse. See Settings.max_hops.
    assert Settings().max_hops == 0
    assert callable(star_carries) and callable(same_table)
    result = ScanResult()
    for field in ("star_tables", "cut_short", "merged_names", "max_hops"):
        assert hasattr(result, field), field
