"""The eight files nobody can write again, and whether they still exist.

WHAT HAPPENED, so nobody has to guess why this file is here.

The demo snapshot -- the Ripple that runs on a laptop where nothing can be
installed -- is assembled by ``tools/make_demo_snapshot.py``. Almost all of it
is copied from the product. Eight files are not: a web layer rewritten on
http.server instead of FastAPI, a launcher for it, an engine finder that looks
inside its own folder, a smoke test written for unittest, a batch file and the
instructions a person actually follows.

Those eight lived only inside the output folder, which git ignores on purpose.
The tool read them into memory, deleted the folder, and wrote them back at the
end. On 24 August that delete failed half way through -- a command prompt left
sitting inside the folder is enough -- and the tool died. The files were already
off the disk, and the only other copy was in a process that had just ended.
Nothing anywhere held a second copy. The folder was recovered from a backup
taken minutes earlier, by luck rather than design.

So the eight now live in ``demo_files``, in git, and these tests check they are
still there and still say what they have to say. Every path read below is a
tracked one; nothing here reads the output folder, which would be green on this
machine and missing everywhere else.
"""
from __future__ import annotations

import re
from pathlib import Path

OFFLINE_DIR = Path(__file__).resolve().parent.parent
OWNED_SRC = OFFLINE_DIR / "demo_files"
TOOL = OFFLINE_DIR / "tools" / "make_demo_snapshot.py"
INSTRUCTIONS = OWNED_SRC / "HOW-TO-RUN-THIS.md"
BATCH = OWNED_SRC / "START RIPPLE.bat"

# The same list the tool works from. Written out again here on purpose: if the
# tool ever quietly drops one, these two disagree and the test below says so.
OWNED = [
    "ripple_offline/__init__.py",
    "ripple_offline/engine.py",
    "ripple_offline/app.py",
    "ripple_offline/webserver.py",
    "run.py",
    "HOW-TO-RUN-THIS.md",
    "tests/test_smoke.py",
    "START RIPPLE.bat",
]


def test_every_file_the_snapshot_owns_is_kept_in_git():
    """The one that would have caught the loss."""
    missing = [n for n in OWNED if not (OWNED_SRC / n).is_file()]
    assert not missing, (
        f"These cannot be copied from the product and are not in git either: {missing}. "
        f"Nothing can rebuild them. Expected them under {OWNED_SRC}."
    )


def test_the_tool_and_this_test_agree_on_which_files_are_owned():
    """A file added to the tool but not to git would slip past the test above."""
    text = TOOL.read_text(encoding="utf-8")
    listed = set(re.findall(r'"([^"]+\.(?:py|md|bat))"', text.split("OWNED = [")[1].split("]")[0]))
    assert listed == set(OWNED), (
        f"The snapshot tool owns {sorted(listed)}, this test guards {sorted(OWNED)}."
    )


def test_the_sources_are_checked_before_anything_is_deleted():
    """Check first, delete second. The other order is what cost the folder."""
    body = TOOL.read_text(encoding="utf-8").split("def main(")[1]
    check_at = body.find("check_sources_first(")
    delete_at = body.find("fresh(DEMO)")
    assert check_at != -1, "the tool no longer checks its sources exist"
    assert delete_at != -1, "the tool no longer empties the output folder"
    assert check_at < delete_at, (
        "make_demo_snapshot.py deletes the output folder before it has checked "
        "the eight owned files are readable. That is the order that destroyed "
        "the folder once already."
    )


def test_the_tool_never_reads_the_owned_files_back_out_of_the_output():
    """The old pattern, in one line: read from DEMO, delete DEMO, write back.

    Said precisely: nothing in the tool may touch the output folder before it
    has been emptied. The moment it does, the tool has a copy of something that
    exists nowhere else, and the next line throws that copy away.
    """
    body = TOOL.read_text(encoding="utf-8").split("def main(")[1]
    first_touch = body.find("DEMO")
    empties_it = body.find("fresh(DEMO)")
    assert empties_it != -1, "the tool no longer empties the output folder"
    assert first_touch == empties_it + len("fresh("), (
        "make_demo_snapshot.py reads from the output folder before emptying it. "
        "That copy lives only in memory, and the delete on the next line is what "
        "destroyed the folder once already. Owned files come from demo_files."
    )


def test_the_engine_finder_does_not_reach_back_into_codebase():
    """The dangerous file, and the failure that only shows up on the other laptop.

    The product's engine finder puts ``Codebase`` on the import path. Let that
    copy win here and everything still runs on this machine, because Codebase is
    next door, and every test passes. It fails only on the laptop the folder was
    made for -- which is the one place nobody can debug it.
    """
    finder = (OWNED_SRC / "ripple_offline" / "engine.py").read_text(encoding="utf-8")
    assert '/ "Codebase"' not in finder, (
        "the snapshot's engine finder points at Codebase, so the folder only "
        "works while it is sitting next to the repository. That is the product's "
        "version of this file, not the snapshot's."
    )
    assert '/ "ripple"' in finder, (
        "the snapshot's engine finder no longer looks for the engine inside its "
        "own folder."
    )


def test_the_instructions_quote_the_batch_file_as_it_really_is():
    """The page prints the batch file. A person reads that, not the file."""
    doc = INSTRUCTIONS.read_text(encoding="utf-8")
    blocks = re.findall(r"```bat\n(.*?)```", doc, re.DOTALL)
    assert len(blocks) == 1, f"expected one bat block in the instructions, found {len(blocks)}"
    quoted = blocks[0].strip().replace("\r\n", "\n")
    real = BATCH.read_text(encoding="utf-8").strip().replace("\r\n", "\n")
    assert quoted == real, (
        "HOW-TO-RUN-THIS.md prints a START RIPPLE.bat that is not the one in the "
        "folder. The page is what a person follows, so the page is what goes wrong."
    )


def test_the_instructions_name_no_version_number_that_can_go_stale():
    """A release filename with a number in it is wrong one release later.

    The page told people to look for ``Ripple-Offline-v1.7.0.zip`` for the whole
    of 1.8. Nothing failed; the file simply was not there, on a laptop with
    nobody to ask.
    """
    doc = INSTRUCTIONS.read_text(encoding="utf-8")
    stale = re.findall(r"v\d+\.\d+\.\d+", doc)
    assert not stale, (
        f"the instructions name {stale}, which stops being true at the next "
        f"release. Describe the file instead of numbering it."
    )


def test_the_batch_file_copes_with_a_laptop_that_only_has_py():
    """``python`` and ``py`` are the same Python under two names, and plenty of
    Windows installs answer to only one of them. The double-click path has to
    survive that without a person to ask."""
    bat = BATCH.read_text(encoding="utf-8")
    assert "set PY=py" in bat, "START RIPPLE.bat gives up when only `py` exists"
    assert "%PY% run.py" in bat, "START RIPPLE.bat is not using the Python it found"
