"""A repository half of which was never opened.

Everyone in this office has OneDrive sync switched on, and Files On-Demand
leaves a file in the folder listing -- with its real name and its real size --
when the contents are still in the cloud. It looks exactly like a file. Opening
it asks OneDrive to fetch it, which needs the network, and Ripple Offline is
built for a machine that has none.

That is the worst thing that can happen to this tool, and it is worse than a
file that will not parse. A file that will not parse lands on the "check by
hand" list and somebody goes and looks at it. A file that was never opened
leaves no trace at all: the finding list is shorter, the tick is green, and
every number on the screen is true -- of the half of the repository that was
read. So these tests pin that it can never happen quietly.

The same goes for a path Windows will not open. His real folders run to about
140 characters before the filename starts, and Windows still refuses anything
past 260 unless long path support has been turned on, which on a managed office
laptop it usually has not.
"""
from __future__ import annotations

import ctypes
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ripple import narrative                                    # noqa: E402
from ripple.config import Settings                              # noqa: E402
from ripple.scanner import repo as repo_mod                      # noqa: E402
from ripple.scanner.lineage import trace                         # noqa: E402
from ripple.scanner.repo import RepoIndex                        # noqa: E402
from ripple.scanner.sqlread import parse_repo                    # noqa: E402

windows_only = pytest.mark.skipif(os.name != "nt", reason="Windows file attributes")

SQL = "CREATE OR REPLACE TABLE stage_thing AS SELECT market_code FROM customer_demographics;\n"


def _cfg(root: Path) -> Settings:
    cfg = Settings()
    cfg.sql_dialect = "bigquery"
    cfg.repo_path = root
    return cfg


@windows_only
def test_the_windows_attribute_is_really_being_read(tmp_path):
    """Proof the flag check is wired to Windows and not to a guess.

    Windows will not let anything but the sync provider set the two recall
    flags, so this uses the one it does allow. If this ever stops working, the
    detection above it is decoration.
    """
    f = tmp_path / "held.sql"
    f.write_text(SQL, encoding="utf-8")
    assert repo_mod.online_only(f) == 0

    ctypes.windll.kernel32.SetFileAttributesW(str(f), repo_mod.FILE_ATTRIBUTE_OFFLINE)
    assert repo_mod.online_only(f) & repo_mod.FILE_ATTRIBUTE_OFFLINE
    ctypes.windll.kernel32.SetFileAttributesW(str(f), 0x80)  # FILE_ATTRIBUTE_NORMAL


def test_a_file_held_in_the_cloud_is_never_opened_and_is_named(tmp_path, monkeypatch):
    (tmp_path / "here.sql").write_text(SQL, encoding="utf-8")
    (tmp_path / "in_the_cloud.sql").write_text(SQL, encoding="utf-8")
    monkeypatch.setattr(
        repo_mod, "online_only",
        lambda p: repo_mod.FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS
        if p.name == "in_the_cloud.sql" else 0,
    )
    idx = RepoIndex.build(tmp_path, _cfg(tmp_path))

    assert [f.path for f in idx.files] == ["here.sql"]
    assert idx.held_online == ["in_the_cloud.sql"]
    # Counted once. A file that was never opened is not a file to "check by
    # hand" -- there is nothing on this machine to open, so listing it in both
    # places would count two problems where there is one and send somebody to
    # read a file that is not there.
    assert idx.skipped == []


def test_a_clean_result_over_unread_files_still_says_so(tmp_path, monkeypatch):
    """The failure this whole file exists to prevent: a short finding list and a
    green tick over a repository that was never fully read."""
    (tmp_path / "read_me.sql").write_text(SQL, encoding="utf-8")
    for n in range(3):
        (tmp_path / f"cloud_{n}.sql").write_text(SQL, encoding="utf-8")
    monkeypatch.setattr(
        repo_mod, "online_only",
        lambda p: repo_mod.FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS
        if p.name.startswith("cloud_") else 0,
    )
    cfg = _cfg(tmp_path)
    idx = RepoIndex.build(tmp_path, cfg)
    parsed = parse_repo(idx, cfg)
    # A name nothing in the read file touches, so the finding list comes back empty.
    res = trace(idx, parsed, [{"table": "SOMETHING_ELSE", "attrs": ["NOT_HERE"]}], cfg=cfg)
    out = res.to_dict()

    assert out["groups"] == [], "this test is only meaningful when the result is otherwise clean"
    assert out["stats"]["neverOpened"] == 3
    assert len(out["heldOnline"]) == 3
    # Not double-counted as files to check by hand, which is a different problem
    # with a different answer.
    assert out["stats"]["couldNotRead"] == 0

    # ...and it reaches the words on the page and the words in the reply, not
    # just a number in the payload.
    written = narrative.summarise(out, {"upstream": [{"table": "SOMETHING_ELSE", "attrs": ["NOT_HERE"]}]})
    assert any("could not even be opened" in b for b in written["bullets"])
    assert any("read the repository again" in a.lower() for a in written["actions"])


def test_a_path_longer_than_windows_allows_is_still_read(tmp_path):
    """About 140 characters of folder before the filename is what his real
    repository looks like, and Windows stops at 260 unless long paths are
    switched on. The walk opts out of the limit rather than relying on the
    machine being set up for it."""
    deep = tmp_path
    for part in ("src", "sql", "DML", "transform", "ccm_entity"):
        deep = deep / ("a_realistically_long_pipeline_folder_" + part)
    target = deep / "cmdl_TL_card_data_entity_r42_loyalty_profile.sql"
    if os.name == "nt":
        long_target = Path(f"\\\\?\\{target.resolve()}")
        long_target.parent.mkdir(parents=True, exist_ok=True)
        long_target.write_text(SQL, encoding="utf-8")
    else:
        deep.mkdir(parents=True, exist_ok=True)
        target.write_text(SQL, encoding="utf-8")
    assert len(str(target)) > 260, "this test is pointless unless the path is genuinely long"

    idx = RepoIndex.build(tmp_path, _cfg(tmp_path))
    assert len(idx.files) == 1
    assert idx.skipped == []
    # The long-path form Windows needs must never reach anything shown on screen.
    assert "?" not in idx.files[0].path
    assert idx.files[0].path.endswith("cmdl_TL_card_data_entity_r42_loyalty_profile.sql")


def test_an_ordinary_repository_is_untouched_by_any_of_this(tmp_path):
    """The opposite failure: refusing to read a perfectly normal repository
    because a backup tool once set a flag. Nothing here fires without cause."""
    (tmp_path / "a.sql").write_text(SQL, encoding="utf-8")
    (tmp_path / "b.sql").write_text(SQL, encoding="utf-8")
    idx = RepoIndex.build(tmp_path, _cfg(tmp_path))
    assert len(idx.files) == 2
    assert idx.held_online == [] and idx.too_long == [] and idx.skipped == []


@windows_only
def test_the_looser_offline_flag_alone_does_not_refuse_a_file(tmp_path):
    """OFFLINE is an old flag and some backup software sets it on files that are
    perfectly local. On its own it is a suspicion, not a verdict -- refusing to
    read a repository over it would be its own disaster."""
    f = tmp_path / "flagged_but_here.sql"
    f.write_text(SQL, encoding="utf-8")
    ctypes.windll.kernel32.SetFileAttributesW(str(f), repo_mod.FILE_ATTRIBUTE_OFFLINE)
    try:
        idx = RepoIndex.build(tmp_path, _cfg(tmp_path))
        assert [x.path for x in idx.files] == ["flagged_but_here.sql"]
        assert idx.held_online == []
    finally:
        ctypes.windll.kernel32.SetFileAttributesW(str(f), 0x80)
