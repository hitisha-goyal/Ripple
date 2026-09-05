"""Sentences that were only ever wrong when you looked at the rendered screen.

Neither of these is a lineage bug. Both are the tool sounding careless on the
one screen where care is the entire product.

* The coverage lines were written in the plural only, so a scan with one of
  anything printed "1 findings are on a line", "1 trails were still going" and
  "1 tables on the trail are built with SELECT *".

* "N files mention these names and could not be read" was said about every file
  in the repository the parser choked on, whether or not it had anything to do
  with the scan. On a clean scan that printed "3 files mention these names"
  directly above a row saying the attribute was named in one file and read from
  nowhere. Those two cannot both be true.

* The summary counted a finding that feeds two published tables once; the letter
  counted it twice. So the summary said "8 pipeline objects" and the reply one
  click later said 9 -- and the reply is the one that leaves the building.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ripple import narrative                                     # noqa: E402
from test_confident_over_less import scan                        # noqa: E402


ONE_OF_EACH = {
    # one table with no column list, one file that will not parse, and one
    # finding on the far side of the star -- so every count comes out as 1.
    "a.sql": "CREATE OR REPLACE TABLE mid AS SELECT * FROM customer_demographics;",
    "b.sql": "CREATE OR REPLACE TABLE final_published AS SELECT cm13 FROM mid;",
    "c.sql": "CREATE OR REPLACE TABLE x AS SELECT cm13 FROM customer_demographics ((( ;",
}


def test_a_count_of_one_reads_as_one(tmp_path):
    """Every coverage line, with one of the thing it counts."""
    cov = scan(tmp_path, ONE_OF_EACH)["coverage"]
    assert cov["complete"] is False, cov
    singles = [g for g in cov["gaps"] if g["count"] == 1]
    assert singles, cov
    for gap in singles:
        line = f"{gap['count']} {gap['what']}"
        # "1 files", "1 tables", "1 findings", "1 trails" -- the whole family.
        assert not re.match(r"^1 \w+s\b", line), line
        # ... and the verb straight after the noun agrees with it. Only that
        # verb: "so your code never lists what its columns are called" is a
        # perfectly good sentence, and an "are" anywhere in the line is not a
        # bug -- checking for one was.
        assert not re.match(r"^1 \w+ (are|were)\b", line), line


def test_a_count_of_more_than_one_still_reads_as_many(tmp_path):
    """The singular forms must not have replaced the plural ones."""
    cov = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE m1 AS SELECT * FROM customer_demographics;",
        "b.sql": "CREATE OR REPLACE TABLE m2 AS SELECT * FROM customer_demographics;",
        "c.sql": "CREATE OR REPLACE TABLE final_published AS "
                 "SELECT a.cm13 FROM m1 a JOIN m2 b ON a.cm13 = b.cm13;",
    })["coverage"]
    many = [g for g in cov["gaps"] if g["count"] > 1]
    assert many, cov
    for gap in many:
        assert gap["what"].split()[0].endswith("s"), gap


def test_unreadable_files_are_not_claimed_to_mention_the_names(tmp_path):
    """A file the parser choked on that has nothing to do with this scan is
    still a gap -- it is simply not a gap ABOUT these names, and saying it is
    contradicts the row that says where the attribute was seen."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE final_published AS "
                 "SELECT cm13 FROM customer_demographics;",
        # broken, and about something else entirely
        "b.sql": "CREATE OR REPLACE TABLE payroll AS SELECT emp_id FROM staff ((( ;",
    })
    line = next(g for g in out["coverage"]["gaps"] if "could not be read" in g["what"])
    assert "mention these names" not in line["what"], line


def test_an_unreadable_file_that_does_mention_them_says_so(tmp_path):
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE final_published AS "
                 "SELECT cm13 FROM customer_demographics;",
        "b.sql": "CREATE OR REPLACE TABLE x AS SELECT cm13 FROM customer_demographics ((( ;",
    })
    line = next(g for g in out["coverage"]["gaps"] if "could not be read" in g["what"])
    # "and it mentions these names" for one, "and N of them mention these names"
    # for more than one.
    assert "mention" in line["what"], line


# ── the summary and the letter must agree ──────────────────────────────────
TWO_TABLES = {
    "shared.sql": "CREATE OR REPLACE TABLE mid AS SELECT cm13 FROM customer_demographics;",
    "one.sql": "CREATE OR REPLACE TABLE first_published AS SELECT cm13 FROM mid;",
    "two.sql": "CREATE OR REPLACE TABLE second_published AS SELECT cm13 FROM mid;",
}

VALS = {"upstream": [{"table": "customer_demographics", "attrs": ["cm13"]}],
        "effectiveLabel": "18 Sept 2026", "pocName": "Priya", "subject": "change"}


def test_the_letter_counts_the_same_objects_as_the_summary(tmp_path):
    """One finding upstream of two published tables appears under both. The
    summary lists it once; the letter used to list it twice, so the two screens
    gave different numbers for the same thing one click apart."""
    out = scan(tmp_path, TWO_TABLES, production="_published")
    assert len(out["groups"]) == 2, [g["prod"] for g in out["groups"]]
    summary = narrative.summarise(out, VALS)
    reply = narrative.draft_reply(out, VALS, summary)

    def objects(text: str) -> str | None:
        m = re.search(r"(\d+) pipeline objects?", text)
        return m.group(1) if m else None

    said = objects(summary["narrative"])
    written = objects(reply["body"])
    assert said is not None, summary["narrative"]
    assert written is not None, reply["body"]
    assert said == written, (
        f"the summary says {said} pipeline objects and the letter says {written}")
