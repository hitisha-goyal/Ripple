"""EXPORT DATA is a delivery, not a parse failure and not a table.

    EXPORT DATA OPTIONS(uri='gs://feed/partner/*.csv', format='CSV') AS
    SELECT cm13, market_code FROM `p.d.stg`;

The statement builds no table, so there was nothing for the trail to carry the
column on to. Ripple reported the READ correctly -- and then the headline said
"no production table is affected", which is true and useless. The delivery is
what breaks, the file lands in somebody else's bucket, and whoever reads it
every morning is outside this repository -- so no scan of this repository will
ever find them. That is precisely why the destination has to be named.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from test_confident_over_less import scan                        # noqa: E402

FEED = ("EXPORT DATA OPTIONS(uri='gs://feed/partner/*.csv', format='CSV') AS\n"
        "SELECT cm13, market_code FROM customer_demographics;\n")


def test_the_destination_is_named(tmp_path):
    out = scan(tmp_path, {"a.sql": FEED})
    assert [f["uri"] for f in out["feeds"]] == ["gs://feed/partner"], out["feeds"]


def test_the_delivery_is_counted_apart_from_published_tables(tmp_path):
    """A file in a bucket is not a published table. One number covering both is
    a number that means neither."""
    out = scan(tmp_path, {"a.sql": FEED})
    assert out["stats"]["feedsBroken"] == 1, out["stats"]
    assert out["stats"]["productionTables"] == 0, out["stats"]


def test_the_row_says_the_delivery_breaks_not_that_a_column_changes(tmp_path):
    out = scan(tmp_path, {"a.sql": FEED})
    rows = out["other"] + [r for g in out["groups"] + out["reached"] for r in g["rows"]]
    assert rows, out
    assert "gs://feed/partner" in rows[0]["impact"], rows[0]["impact"]
    assert "outside this repository" in rows[0]["impact"], rows[0]["impact"]


def test_the_delivery_says_which_attribute_it_carries(tmp_path):
    out = scan(tmp_path, {"a.sql": FEED})
    assert out["feeds"][0]["attrs"] == ["cm13"], out["feeds"]
    assert out["feeds"][0]["from"] == "customer_demographics", out["feeds"]


def test_a_single_file_uri_keeps_its_folder(tmp_path):
    """The last part of the path is a filename, not a place. Dropping it turns
    a pattern nobody recognises into the name of a feed somebody does."""
    out = scan(tmp_path, {
        "a.sql": "EXPORT DATA OPTIONS(uri='gs://exports/finance/daily.csv') AS\n"
                 "SELECT cm13 FROM customer_demographics;\n"})
    assert [f["uri"] for f in out["feeds"]] == ["gs://exports/finance"], out["feeds"]


def test_a_uri_with_no_filename_is_left_alone(tmp_path):
    out = scan(tmp_path, {
        "a.sql": "EXPORT DATA OPTIONS(uri='gs://exports/finance/') AS\n"
                 "SELECT cm13 FROM customer_demographics;\n"})
    assert [f["uri"] for f in out["feeds"]] == ["gs://exports/finance"], out["feeds"]


def test_two_exports_in_one_file_keep_their_own_destinations(tmp_path):
    out = scan(tmp_path, {
        "a.sql": "EXPORT DATA OPTIONS(uri='gs://one/a/*.csv') AS\n"
                 "SELECT cm13 FROM customer_demographics;\n"
                 "EXPORT DATA OPTIONS(uri='gs://two/b/*.csv') AS\n"
                 "SELECT cm13 FROM customer_demographics;\n"})
    assert [f["uri"] for f in out["feeds"]] == ["gs://one/a", "gs://two/b"], out["feeds"]


def test_an_ordinary_create_has_no_delivery(tmp_path):
    """The guard. A card printed on every scan is one nobody reads."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE final_published AS "
                 "SELECT cm13 FROM customer_demographics;"})
    assert out["feeds"] == []
    assert out["stats"]["feedsBroken"] == 0
