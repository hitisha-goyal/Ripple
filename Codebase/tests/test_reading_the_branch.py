"""Which branch is this folder on? Read it, or say nothing.

A folder on somebody's disk may be a copied-out git checkout, in which case the
branch is a real fact worth showing, or it may be a plain folder, in which case
there is no branch at all.

Ripple used to answer "main" either way. The Repository step showed "Branch
main" over every folder on earth -- specific, checkable-looking, and made up. It
is a small lie, and this product's whole claim is that it does not tell the
small ones either.

Worse, it only did that in ONE of the two builds. The packaged build had already
been fixed and read the folder properly, so the same folder produced a different
screen depending on which Ripple somebody opened. Comparing the two builds
answer-for-answer on the same repository, 453 values matched and this was the
only one that did not.

The reader lives in the engine both builds import now, and these are its tests.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ripple.config import Settings, git_branch          # noqa: E402


@pytest.mark.parametrize("head,expected", [
    ("ref: refs/heads/main\n", "main"),
    ("ref: refs/heads/release-2026\n", "release-2026"),
    ("ref: refs/heads/feature/market-code\n", "market-code"),
    ("9f8c1a2b3c4d5e6f\n", "9f8c1a2"),       # a detached checkout: the commit
])
def test_the_branch_is_read_from_the_folder_itself(tmp_path, head, expected):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD").write_text(head, encoding="utf-8")
    assert git_branch(tmp_path) == expected


def test_a_folder_that_was_never_a_checkout_claims_no_branch(tmp_path):
    """The one that matters. Nothing is the honest answer, and "main" is not."""
    assert git_branch(tmp_path) == ""


def test_a_missing_folder_claims_no_branch(tmp_path):
    assert git_branch(tmp_path / "not-here") == ""


def test_an_unreadable_head_claims_no_branch(tmp_path):
    """A .git that is a file, not a folder -- which is what a git worktree
    leaves behind. Unreadable is not a reason to invent a branch."""
    (tmp_path / ".git").write_text("gitdir: ../somewhere/else", encoding="utf-8")
    assert git_branch(tmp_path) == ""


def test_settings_reports_no_branch_for_a_plain_folder(tmp_path):
    """Through the settings object, which is what the screens actually read."""
    s = Settings()
    s.repo_path = tmp_path
    s.repo_branch = ""
    assert s.branch() == "", "a plain folder was given a branch name"


def test_settings_reports_the_real_branch_for_a_checkout(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD").write_text("ref: refs/heads/live\n", encoding="utf-8")
    s = Settings()
    s.repo_path = tmp_path
    s.repo_branch = ""
    assert s.branch() == "live"


def test_a_branch_somebody_set_by_hand_still_wins(tmp_path):
    """RIPPLE_REPO_BRANCH is a deliberate statement about the folder. Reading
    the folder is the fallback, not an override of what somebody said."""
    s = Settings()
    s.repo_path = tmp_path
    s.repo_branch = "whatever-they-said"
    assert s.branch() == "whatever-they-said"


def test_the_branch_follows_the_folder_when_the_folder_changes(tmp_path):
    """The folder can be changed on the settings screen while Ripple runs. A
    branch left over from the folder before is a fact about a repository nobody
    is reading any more."""
    first, second = tmp_path / "one", tmp_path / "two"
    (first / ".git").mkdir(parents=True)
    (first / ".git" / "HEAD").write_text("ref: refs/heads/first\n", encoding="utf-8")
    second.mkdir()

    s = Settings()
    s.repo_branch = ""
    s.repo_path = first
    assert s.branch() == "first"
    s.repo_path = second
    assert s.branch() == "", "the branch of the previous folder survived the change"


def test_the_default_is_not_main():
    """It was, for a long time, and that is the whole bug."""
    assert Settings().repo_branch != "main", (
        "repo_branch defaults to 'main' again, so every plain folder will claim "
        "to be on a branch it has never heard of"
    )
