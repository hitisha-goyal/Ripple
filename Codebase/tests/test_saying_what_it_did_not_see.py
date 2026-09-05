"""Answers that were right, worded as something else entirely.

None of these is a lineage bug. Every one of them is the screen telling somebody
a different thing from what Ripple actually worked out, which costs exactly as
much:

* "I never saw that column" was worded byte for byte like "that column goes
  nowhere" -- the same green tick, the same empty list. So a typo in an
  attribute name shipped as "no impact".
* The wildcard card said "the usages below are real" over an empty list, because
  a wildcard in one dataset covers a shard in another and produces nothing.
* ``orders_*`` matched to plain ``orders`` shipped as ``certain``. BigQuery does
  not match that at all -- the separator is required.
* A plain INFORMATION_SCHEMA lookup was blamed on an in-house helper, so the one
  line on screen pointing at the problem named a cause nobody could find.
* "No impact, and I could follow every step of it" and "no impact, and three
  tables on the way were invisible to me" printed as the same three words.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from test_confident_over_less import scan                        # noqa: E402

REPO = {"a.sql": "CREATE OR REPLACE TABLE final_published AS "
                 "SELECT cm13, cm14 FROM customer_demographics;"}


# ── 33. a column Ripple never met ──────────────────────────────────────────
def test_a_column_ripple_never_met_is_a_failed_lookup(tmp_path):
    out = scan(tmp_path, REPO, attrs=("cm99",))
    assert out["lookupFailed"] is True, out["risk"]
    assert out["attributes"][0]["lookupFailed"] is True


def test_a_failed_lookup_prints_back_the_columns_ripple_did_see(tmp_path):
    """The instant self-correction. A typo becomes something somebody spots in
    two seconds instead of a green tick they act on."""
    out = scan(tmp_path, REPO, attrs=("cm99",))
    assert out["attributes"][0]["tableColumns"] == ["cm13", "cm14"], out["attributes"]


def test_the_columns_come_from_reads_as_well_as_from_builds(tmp_path):
    """Nothing in a repository builds a SOURCE table, so its column list is only
    ever written down by the statements that read it."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE mid AS SELECT market_code FROM customer_demographics;"},
        attrs=("cm99",))
    assert out["attributes"][0]["tableColumns"] == ["market_code"], out["attributes"]


def test_a_real_column_that_goes_nowhere_is_not_a_failed_lookup(tmp_path):
    """The other half of the split, and the one that must not move. This column
    exists, it is read, and it reaches nothing published. That is an answer."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE stage_x AS SELECT cm13 FROM customer_demographics;"})
    assert out["lookupFailed"] is False
    assert out["attributes"][0]["lookupFailed"] is False


def test_a_column_list_is_only_worked_out_when_a_lookup_fails(tmp_path):
    """It walks every statement in the repository. On a scan that does not need
    it that is minutes, on a repository the size of his."""
    out = scan(tmp_path, REPO, attrs=("cm13",))
    assert out["attributes"][0]["tableColumns"] == []


# ── 34. the wildcard card contradicting the scan ───────────────────────────
def test_a_wildcard_that_produced_nothing_is_not_put_on_the_card(tmp_path):
    """A wildcard in one dataset and a shard in another are not the same table.
    The card says "the usages below are real" and there were none below."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE final_published AS SELECT cm13 FROM `p.ds_a.events_*`;"},
        table="p.ds_b.events_2024")
    assert out["groups"] == []
    assert out["wildcardNames"] == [], out["wildcardNames"]


def test_a_wildcard_that_did_produce_findings_is_still_on_the_card(tmp_path):
    """The guard. Dropping the card entirely would lose the one warning that
    says a whole family of shards is what the SQL actually named."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE final_published AS SELECT cm13 FROM `p.ds_a.events_*`;"},
        table="p.ds_a.events_2024")
    assert [g["prod"] for g in out["groups"]] == ["final_published"]
    assert [w["patterns"] for w in out["wildcardNames"]] == [["events_*"]], out["wildcardNames"]


# ── 35. the family name is a guess, a shard is a fact ──────────────────────
def test_the_family_name_without_its_separator_is_not_certain(tmp_path):
    """BigQuery does not match ``customer_demographics_*`` to plain
    ``customer_demographics``. Ripple matches it anyway, so that typing the name
    you say out loud cannot give a clean "no impact" -- and says it is a guess."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE final_published AS "
                 "SELECT cm13 FROM customer_demographics_*;"},
        table="customer_demographics")
    rows = [r for g in out["groups"] for r in g["rows"]]
    assert rows and all(r["certain"] is False for r in rows), rows
    assert [w["shorthand"] for w in out["wildcardNames"]] == [["customer_demographics_*"]]


def test_a_real_shard_match_stays_a_fact(tmp_path):
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE final_published AS "
                 "SELECT cm13 FROM customer_demographics_*;"},
        table="customer_demographics_20260101")
    rows = [r for g in out["groups"] for r in g["rows"]]
    assert rows and all(r["certain"] is True for r in rows), rows
    assert [w["shorthand"] for w in out["wildcardNames"]] == [[]]


# ── 36. name what actually happened ────────────────────────────────────────
def test_a_metadata_lookup_is_not_blamed_on_an_in_house_helper(tmp_path):
    """The one line on screen pointing at the problem named the wrong cause, so
    following it would have found no such helper anywhere in the repository."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE final_published AS SELECT column_name "
                 "FROM `p.base`.INFORMATION_SCHEMA.COLUMNS "
                 "WHERE table_name = 'customer_demographics';"})
    entry = out["unreadable"][0]
    assert "catalogue" in entry["reason"], entry
    assert "in-house helpers" not in entry["hint"], entry
    assert "INFORMATION_SCHEMA" in entry["hint"], entry


def test_a_real_helper_call_is_still_described_as_one(tmp_path):
    """The guard. The helper wording is right where there really is a helper."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE final_published AS "
                 "SELECT get_tag('cm13', 'customer_demographics') AS t "
                 "FROM customer_demographics;"})
    entry = out["unreadable"][0]
    assert "in-house helpers" in entry["hint"], entry


# ── 37. how much of it Ripple could see ────────────────────────────────────
def test_a_trail_read_end_to_end_says_so(tmp_path):
    out = scan(tmp_path, REPO)
    assert out["coverage"]["complete"] is True, out["coverage"]
    assert out["coverage"]["gaps"] == []


def test_a_trail_with_an_invisible_table_on_it_says_so(tmp_path):
    """This used to print exactly the same three words as the scan above."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE mid AS SELECT * FROM customer_demographics;",
        "b.sql": "CREATE OR REPLACE TABLE final_published AS SELECT cm13 FROM mid;"})
    cov = out["coverage"]
    assert cov["complete"] is False, cov
    # Pinned on the meaning, not on one sentence. This line is written for
    # somebody reading a scan for the first time, so its wording changes; what
    # may never change is that the coverage list says a table on the way hides
    # what its columns are called.
    assert any("every column at once" in g["what"] or "SELECT *" in g["what"]
               for g in cov["gaps"]), cov
    assert out["risk"] == "medium", "the risk word itself must not move"


def test_an_unread_file_is_a_gap_in_coverage(tmp_path):
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE final_published AS SELECT cm13 FROM customer_demographics;",
        "b.sql": "CREATE OR REPLACE TABLE x AS SELECT cm13 FROM customer_demographics ((( ;"})
    cov = out["coverage"]
    assert cov["complete"] is False, cov
    assert cov["filesUnread"] == 1, cov
