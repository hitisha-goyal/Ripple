"""Saying what is happening during the minutes a real repository takes.

Measured on a repository the size of the one this was built for -- about 1,200
files, 36 MB, single statements six hundred lines long -- reading it takes
around 25 seconds, understanding the SQL around five minutes, and a scan around
a minute. A spinner and a fixed sentence for five minutes is indistinguishable
from a program that has hung.

The usual answer to that is a progress bar, and a progress bar is the easiest
place in a program to put a number that is not true. So these tests are about
what the numbers are, not that they exist: every one of them is counted, and
where there is genuinely no total it stays zero rather than being invented.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ripple import progress                                     # noqa: E402
from ripple.config import Settings, parse_production_rule       # noqa: E402
from ripple.scanner.lineage import trace                        # noqa: E402
from ripple.scanner.repo import RepoIndex                       # noqa: E402
from ripple.scanner.sqlread import parse_repo                   # noqa: E402

STATEMENT = """
CREATE OR REPLACE TABLE `p.stage.stage_{n}_published` AS
SELECT cm13, market_code FROM `p.raw.customer_demographics` WHERE cm13 IS NOT NULL;
"""


def _repo(tmp_path: Path, files: int = 60):
    for n in range(files):
        p = tmp_path / "src" / "sql" / f"job_{n}.sql"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(STATEMENT.format(n=n), encoding="utf-8")
    cfg = Settings()
    cfg.sql_dialect = "bigquery"
    cfg.repo_path = tmp_path
    cfg.production_patterns = parse_production_rule("_published")
    return cfg


def test_reading_counts_real_files(tmp_path):
    cfg = _repo(tmp_path, files=60)
    seen: list[tuple[int, int]] = []
    idx = RepoIndex.build(tmp_path, cfg, on_progress=lambda d, t, l: seen.append((d, t)))

    assert seen, "a repository this size has to report something"
    # Counted, never estimated: it only ever goes up, never past the total, and
    # the last thing it says is the number of files there really were.
    assert all(a <= b for (a, _), (b, _) in zip(seen, seen[1:]))
    assert all(d <= t for d, t in seen)
    assert seen[-1][0] == seen[-1][1] == 60
    assert len(idx.files) == 60


def test_understanding_the_sql_counts_real_files(tmp_path):
    cfg = _repo(tmp_path, files=60)
    idx = RepoIndex.build(tmp_path, cfg)
    seen: list[tuple[int, int]] = []
    parse_repo(idx, cfg, on_progress=lambda d, t, l: seen.append((d, t)))

    assert seen
    assert all(d <= t for d, t in seen)
    assert seen[-1] == (len(idx.files), len(idx.files))


def test_a_scan_reports_a_count_and_refuses_to_invent_a_total(tmp_path):
    """Following a chain looks at as many statements as it turns out to need, so
    there is no denominator. Zero is the honest answer, and the screen shows a
    count with no fraction rather than a bar over a number nobody knows."""
    cfg = _repo(tmp_path, files=400)
    idx = RepoIndex.build(tmp_path, cfg)
    parsed = parse_repo(idx, cfg)
    seen: list[tuple[int, int]] = []
    trace(idx, parsed, [{"table": "customer_demographics", "attrs": ["cm13"]}],
          change_type="removal", cfg=cfg,
          on_progress=lambda d, t, l: seen.append((d, t)))

    assert seen, "400 files is enough work to be worth reporting"
    assert all(t == 0 for _, t in seen), "a total here would be a made-up one"
    assert all(a <= b for (a, _), (b, _) in zip(seen, seen[1:]))


def test_what_the_screen_is_told_is_a_copy(tmp_path):
    """Read while a read is running, so it must never catch half of one update
    and half of the next -- that would put a number on screen that was never
    true of anything."""
    progress.start("reading")
    progress.step(10, 100, "Reading the files")
    first = progress.snapshot()
    progress.step(20, 100, "Reading the files")
    assert first["done"] == 10, "the earlier answer must not change under the caller"
    assert progress.snapshot()["done"] == 20
    progress.finish()
    assert progress.snapshot()["job"] == ""


def test_nothing_is_reported_when_nothing_is_happening():
    progress.finish()
    now = progress.snapshot()
    assert now == {"job": "", "label": "", "done": 0, "total": 0}
