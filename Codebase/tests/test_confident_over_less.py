"""Answers Ripple used to give confidently over less than the whole picture.

Every case here produced a calm, clean, wrong result. Not a crash, not a "could
not read" -- a green tick on a change that breaks a published table. That is the
one failure this tool cannot have, so each shape is pinned here.

The three that started it:

* A table built with ``SELECT *`` stopped the trail dead. Forty-four tables in
  the repository this was built for are made that way.
* A trail deeper than the hop limit was reported as "the chain ends here and
  does not reach production" -- a setting reported as a fact about a warehouse.
* Two tables sharing a short name in different datasets were treated as one.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ripple.config import Settings, parse_production_rule       # noqa: E402
from ripple.scanner.lineage import trace                        # noqa: E402
from ripple.scanner.repo import RepoIndex                       # noqa: E402
from ripple.scanner.sqlread import parse_repo                   # noqa: E402


def build(tmp_path: Path, files: dict, production: str = "_published",
          max_hops: int = 4) -> tuple:
    for name, text in files.items():
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        # Bytes, not text, when the test is about how the file was SAVED -- a
        # byte-order mark, UTF-16, a stray NUL. Writing those through write_text
        # would put the very bytes under test back through an encoder.
        if isinstance(text, bytes):
            p.write_bytes(text)
        else:
            p.write_text(text, encoding="utf-8")
    cfg = Settings()
    cfg.sql_dialect = "bigquery"
    cfg.repo_path = tmp_path
    cfg.max_hops = max_hops
    cfg.production_patterns = parse_production_rule(production)
    idx = RepoIndex.build(tmp_path, cfg)
    return cfg, idx, parse_repo(idx, cfg)


def scan(tmp_path: Path, files: dict, table: str = "customer_demographics",
         attrs: tuple[str, ...] = ("cm13",), production: str = "_published",
         change: str = "removal", max_hops: int = 4) -> dict:
    cfg, idx, parsed = build(tmp_path, files, production=production, max_hops=max_hops)
    return trace(idx, parsed, [{"table": table, "attrs": list(attrs)}],
                 change_type=change, cfg=cfg).to_dict()


# ── 1. SELECT * ────────────────────────────────────────────────────────────
STAR = {
    "a.sql": """
        CREATE OR REPLACE TABLE stage_star AS
        SELECT * FROM customer_demographics;
    """,
    "b.sql": """
        CREATE OR REPLACE TABLE final_published AS
        SELECT cm13 FROM stage_star WHERE cm13 IS NOT NULL;
    """,
}


def test_a_table_built_with_select_star_does_not_stop_the_trail(tmp_path):
    """The reproduction this was reported with. Two files, one hop apart, and a
    completely clean answer for a change that breaks a published table."""
    out = scan(tmp_path, STAR)
    assert [g["prod"] for g in out["groups"]] == ["final_published"], \
        "the change reaches final_published and always did"
    assert out["stats"]["productionTables"] == 1
    assert out["risk"] != "none"


def test_the_scan_result_itself_says_the_column_list_was_not_visible(tmp_path):
    """Not a different screen. The repository screen has listed these tables for
    months and nothing joined it up to the answer, so the scan said no impact
    while the warning sat somewhere nobody was looking."""
    out = scan(tmp_path, STAR)
    assert [s["table"] for s in out["starTables"]] == ["stage_star"]
    assert out["stats"]["tablesNotVisible"] == 1
    assert out["stats"]["inferredFindings"] == 2, "both findings are past the star"
    assert out["attributes"][0]["notVisible"] == ["stage_star"]


def test_the_star_hop_itself_is_not_called_breaking(tmp_path):
    """A SELECT * does not fail when a column disappears. It quietly builds a
    narrower table, and what breaks is whatever reads the missing column."""
    out = scan(tmp_path, STAR)
    rows = out["groups"][0]["rows"]
    star_row = next(r for r in rows if r["viaStar"])
    assert star_row["breaking"] is False
    assert "SELECT *" in star_row["impact"]
    named = next(r for r in rows if not r["viaStar"])
    assert named["breaking"] is True


def test_a_qualified_star_only_carries_its_own_table(tmp_path):
    """``SELECT a.*`` takes a's columns, not b's."""
    out = scan(tmp_path, {
        "a.sql": """
            CREATE OR REPLACE TABLE stage_star AS
            SELECT b.* FROM customer_demographics a JOIN other_side b ON a.k = b.k;
        """,
        "b.sql": "CREATE OR REPLACE TABLE final_published AS SELECT cm13 FROM stage_star;",
    })
    assert out["groups"] == [], "cm13 travels through b, and b is not being changed"


def test_select_star_except_stops_the_chain_and_still_reports_the_break(tmp_path):
    """Both halves matter. The column never reaches the next table, so the trail
    genuinely stops -- and the statement names it, so removing it breaks here."""
    out = scan(tmp_path, {
        "a.sql": """
            CREATE OR REPLACE TABLE stage_star AS
            SELECT * EXCEPT(cm13) FROM customer_demographics;
        """,
        "b.sql": "CREATE OR REPLACE TABLE final_published AS SELECT cm13 FROM stage_star;",
    })
    assert out["groups"] == [], "cm13 is dropped by name and never reaches final_published"
    rows = [r for g in out["reached"] for r in g["rows"]]
    assert rows, "but the statement that drops it by name is still broken by the change"
    assert rows[0]["breaking"] is True
    assert "EXCEPT" in rows[0]["impact"]


# ── 2. the hop limit ───────────────────────────────────────────────────────
def deep_chain(depth: int) -> dict:
    files = {"t0.sql": "CREATE OR REPLACE TABLE t1 AS SELECT cm13 FROM customer_demographics;"}
    for i in range(1, depth):
        files[f"t{i}.sql"] = f"CREATE OR REPLACE TABLE t{i + 1} AS SELECT cm13 FROM t{i};"
    files["tp.sql"] = f"CREATE OR REPLACE TABLE final_published AS SELECT cm13 FROM t{depth};"
    return files


def test_a_trail_the_limit_cut_is_not_reported_as_a_trail_that_ended(tmp_path):
    """"The chain ends at t4 and does not reach production" is a sentence about
    a setting, printed on the screen where somebody decides whether to worry."""
    out = scan(tmp_path, deep_chain(8))
    assert out["attributes"][0]["endsAt"] == [], "nothing here actually ended"
    assert out["attributes"][0]["cutShortAt"] == ["t4"]
    assert out["stats"]["trailsCutShort"] == 1
    assert [c["table"] for c in out["cutShort"]] == ["t4"]
    assert out["maxHops"] == 4


def test_the_table_the_limit_stopped_at_says_so_on_its_own_card(tmp_path):
    out = scan(tmp_path, deep_chain(8))
    card = next(g for g in out["reached"] if g["prod"] == "t4")
    assert card["cut"] is True
    assert "hop limit" in card["note"]


def test_raising_the_limit_finds_the_published_table(tmp_path):
    """The whole point of saying a trail was cut: it can be run again deeper."""
    out = scan(tmp_path, deep_chain(8), max_hops=12)
    assert [g["prod"] for g in out["groups"]] == ["final_published"]
    assert out["stats"]["trailsCutShort"] == 0
    assert out["cutShort"] == []


def test_a_trail_that_really_ends_is_not_called_cut_short(tmp_path):
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE t1 AS SELECT cm13 FROM customer_demographics;",
    })
    assert out["attributes"][0]["endsAt"] == ["t1"]
    assert out["attributes"][0]["cutShortAt"] == []
    assert out["stats"]["trailsCutShort"] == 0


# ── 3. two tables with the same short name ─────────────────────────────────
TWO_DATASETS = {
    "raw.sql": """
        CREATE OR REPLACE TABLE `prj.stage_dataset.from_raw` AS
        SELECT cm13 FROM `prj.raw_dataset.customer_demographics`;
    """,
    "arch.sql": """
        CREATE OR REPLACE TABLE `prj.stage_dataset.from_archive` AS
        SELECT cm13 FROM `prj.archive_dataset.customer_demographics`;
    """,
}


def test_a_change_to_one_dataset_does_not_produce_findings_for_the_other(tmp_path):
    out = scan(tmp_path, TWO_DATASETS, table="prj.raw_dataset.customer_demographics")
    files = {r["file"] for g in out["reached"] for r in g["rows"]}
    assert files == {"raw.sql"}, "arch.sql reads a different table of the same name"
    assert [g["prod"] for g in out["reached"]] == ["from_raw"]


def test_the_other_dataset_is_reported_as_a_mention_rather_than_dropped(tmp_path):
    out = scan(tmp_path, TWO_DATASETS, table="prj.raw_dataset.customer_demographics")
    assert [m["file"] for m in out["mentionsOnly"]] == ["arch.sql"]


def test_a_project_in_front_of_the_name_does_not_stop_it_matching(tmp_path):
    """Typed in full into the notification, written with a placeholder in the
    file. Ripple used to find nothing at all, which reads as no impact."""
    out = scan(tmp_path, {
        "a.sql": """
            CREATE OR REPLACE TABLE {{tgt}}.{{stage}}.final_published AS
            SELECT cm13 FROM {{src}}.{{raw}}.customer_demographics;
        """,
    }, table="prj-p-cmdl.raw_dataset.customer_demographics")
    assert [g["prod"] for g in out["groups"]] == ["final_published"]


def test_a_templated_dataset_is_not_treated_as_a_dataset_name(tmp_path):
    """One file writes {{stage_dataset}}.orders_umdl, the DAG that reads it
    writes {{params.src}}.raw.orders_umdl. Those are not two datasets -- one of
    them is a hole. Splitting them cuts a real chain and reports no impact."""
    out = scan(tmp_path, {
        "a.sql": """
            CREATE OR REPLACE TABLE {{tgt_project_id}}.{{stage_dataset}}.orders_umdl AS
            SELECT cm13 FROM customer_demographics;
        """,
        "b.sql": """
            CREATE OR REPLACE TABLE final_published AS
            SELECT cm13 FROM `prj.raw.orders_umdl`;
        """,
    })
    assert [g["prod"] for g in out["groups"]] == ["final_published"]


def test_a_name_ripple_had_to_merge_is_said_out_loud(tmp_path):
    """The SQL did not say which of two same-named tables it meant. Ripple
    matches both, because losing the chain is the worse mistake -- and says so
    rather than letting the finding read as a fact about one of them."""
    out = scan(tmp_path, {
        "raw.sql": "CREATE OR REPLACE TABLE mid AS SELECT cm13 FROM `prj.raw_dataset.cust`;",
        "arch.sql": "CREATE OR REPLACE TABLE other AS SELECT cm13 FROM `prj.archive_dataset.cust`;",
        "c.sql": "CREATE OR REPLACE TABLE final_published AS SELECT cm13 FROM mid;",
    }, table="cust")
    merged = out["mergedNames"]
    assert [m["table"] for m in merged] == ["cust"]
    assert merged[0]["datasets"] == ["ARCHIVE_DATASET", "RAW_DATASET"]


# ── 4. the same class, found by asking the same question ───────────────────
def test_both_halves_of_a_union_are_read(tmp_path):
    """One of his tables is called ..._BCA_UNION. Only the first SELECT of a
    union was recorded as reading anything, so a change to a table named in the
    second half produced no findings anywhere at all."""
    for first, second in (("customer_demographics", "other_source"),
                          ("other_source", "customer_demographics")):
        out = scan(tmp_path / f"{first}{second}", {
            "u.sql": f"""
                CREATE OR REPLACE TABLE deduped_bca_union AS
                SELECT cm13 FROM {first}
                UNION ALL
                SELECT cm13 FROM {second};
            """,
            "p.sql": "CREATE OR REPLACE TABLE final_published AS "
                     "SELECT cm13 FROM deduped_bca_union;",
        })
        assert [g["prod"] for g in out["groups"]] == ["final_published"], \
            f"the union half naming customer_demographics was {first}/{second}"


def test_a_finding_points_at_a_line_inside_its_own_statement(tmp_path):
    """A 600-line generated file holds sixty statements. A finding used to be
    free to point at any line in the file that scored well, which regularly
    meant a WHERE clause belonging to a different table entirely -- the finding
    right, the line somebody else's, and the whole finding wasted."""
    out = scan(tmp_path, {
        "f.sql": """CREATE OR REPLACE TABLE final_published AS
SELECT a FROM customer_demographics
WHERE cm13 IS NOT NULL;

CREATE OR REPLACE TABLE unrelated_tbl AS
SELECT a FROM something_else
WHERE cm13 = 'X' AND flag = 1 OR other IS NULL;
""",
    })
    row = out["groups"][0]["rows"][0]
    hit = next(line for line in row["lines"] if line.get("hit"))
    assert hit["n"] == 3, "line 7 belongs to a statement about a different table"
    assert "IS NOT NULL" in hit["t"]


def test_an_insert_column_list_renames_by_position(tmp_path):
    """Every foundation file here loads with TRUNCATE then INSERT INTO t (the
    whole column list) SELECT ... . The SELECT hands values over by position, so
    the name downstream is the one in the INSERT list -- and following the
    SELECT's name instead walked off the end of the chain."""
    out = scan(tmp_path, {
        "a.sql": "INSERT INTO stage_tbl (member_id) SELECT cm13 FROM customer_demographics;",
        "b.sql": "CREATE OR REPLACE TABLE final_published AS SELECT member_id FROM stage_tbl;",
    })
    assert [g["prod"] for g in out["groups"]] == ["final_published"]


def test_a_mismatched_insert_column_list_is_not_guessed_at(tmp_path):
    """Two lists of different lengths cannot be lined up, so nothing is."""
    out = scan(tmp_path, {
        "a.sql": "INSERT INTO stage_tbl (a, b) SELECT cm13 FROM customer_demographics;",
        "b.sql": "CREATE OR REPLACE TABLE final_published AS SELECT cm13 FROM stage_tbl;",
    })
    assert [g["prod"] for g in out["groups"]] == ["final_published"], \
        "the name it arrived under is kept rather than a position being invented"


def test_two_names_differing_only_by_capitals_are_said_out_loud(tmp_path):
    """He has ccm_Wireless_Enroll and ccm_Dell_Enroll. BigQuery treats capitals
    as significant, so two spellings really are two tables there. Ripple follows
    both -- losing a chain is worse -- and says which ones it merged."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE mid AS SELECT cm13 FROM ccm_Wireless_Enroll;",
        "b.sql": "CREATE OR REPLACE TABLE other AS SELECT cm13 FROM ccm_wireless_enroll;",
        "c.sql": "CREATE OR REPLACE TABLE final_published AS SELECT cm13 FROM mid;",
    }, table="ccm_Wireless_Enroll")
    merged = [m for m in out["mergedNames"] if m["reason"] == "capitals"]
    assert merged, "both spellings were followed, and nothing said so"
    assert merged[0]["spellings"] == ["ccm_Wireless_Enroll", "ccm_wireless_enroll"]


def test_a_column_leaving_under_two_names_has_both_followed(tmp_path):
    """Following the onward names stopped at the first one that found
    something, so the second name was dropped exactly when the first name
    worked -- which is most of the time."""
    out = scan(tmp_path, {
        "a.sql": """
            CREATE OR REPLACE TABLE stage_tbl AS
            SELECT cm13, CAST(cm13 AS STRING) AS cm13_str FROM customer_demographics;
        """,
        "b.sql": "CREATE OR REPLACE TABLE ends_here AS SELECT cm13 FROM stage_tbl;",
        "c.sql": "CREATE OR REPLACE TABLE final_published AS SELECT cm13_str FROM stage_tbl;",
    })
    assert [g["prod"] for g in out["groups"]] == ["final_published"], \
        "cm13_str reaches the published table and is the second name, not the first"


def test_a_dataset_matched_against_a_bare_name_is_also_said_out_loud(tmp_path):
    """One file names archive_dataset.cust_stage, another just says cust_stage.
    Ripple matches them, because a bare name has said nothing to rule anything
    out — and that is a merge exactly as much as two named datasets are."""
    out = scan(tmp_path, {
        "a.sql": """
            CREATE OR REPLACE TABLE `prj.archive_dataset.cust_stage` AS
            SELECT cm13 FROM customer_demographics;
        """,
        "b.sql": "CREATE OR REPLACE TABLE final_published AS SELECT cm13 FROM cust_stage;",
    })
    merged = [m for m in out["mergedNames"] if m["table"] == "cust_stage"]
    assert merged, "the bare cust_stage was matched to the archive one, and nothing said so"
    assert merged[0]["reason"] == "dataset"


def test_a_repository_with_no_dataset_names_flags_nothing(tmp_path):
    """His files are templated, so almost no name carries a dataset Ripple can
    read. A warning printed over every table is one nobody reads."""
    out = scan(tmp_path, {
        "a.sql": """
            CREATE OR REPLACE TABLE {{tgt}}.{{stage_dataset}}.mid AS
            SELECT cm13 FROM {{src}}.{{src_dataset}}.customer_demographics;
        """,
        "b.sql": """
            CREATE OR REPLACE TABLE {{tgt}}.{{tgt_dataset}}.final_published AS
            SELECT cm13 FROM {{tgt}}.{{stage_dataset}}.mid;
        """,
    })
    assert [g["prod"] for g in out["groups"]] == ["final_published"]
    assert out["mergedNames"] == []


def test_an_unambiguous_table_is_still_shown_by_its_own_name(tmp_path):
    """Printing "stage_dataset." in front of every table in a repository with
    one dataset is noise, and noise is what stops the line that matters."""
    out = scan(tmp_path, {
        "a.sql": """
            CREATE OR REPLACE TABLE `prj.stage_dataset.final_published` AS
            SELECT cm13 FROM `prj.stage_dataset.customer_demographics`;
        """,
    })
    assert [g["prod"] for g in out["groups"]] == ["final_published"]
    assert out["mergedNames"] == []


# ── 8. clauses a column can hide in ────────────────────────────────────────
# Every case below came back "the name appears, but no lineage to a production
# table" -- the most reassuring sentence Ripple can print -- for a change that
# stops a published table loading. They are one defect wearing several hats: the
# reader had a list of the places in a statement a column can be used, and the
# list was short. Grouped here so the next clause anyone adds gets a case too.
def only_row(out: dict) -> dict:
    assert [g["prod"] for g in out["groups"]] == ["final_published"], out["groups"]
    rows = [r for g in out["groups"] for r in g["rows"]]
    assert len(rows) == 1, rows
    return rows[0]


def test_qualify_is_read_as_the_filter_it_is(tmp_path):
    """QUALIFY is where nearly every dedup in a BigQuery pipeline is written.
    Not reading it made the column invisible whenever it appeared nowhere else
    in the statement -- and the standard dedup is exactly that shape."""
    out = scan(tmp_path, {
        "a.sql": """
            CREATE OR REPLACE TABLE final_published AS
            SELECT pub_id, last_upd FROM customer_demographics
            QUALIFY ROW_NUMBER() OVER (PARTITION BY pub_id ORDER BY last_upd) = 1
               AND cm13 = 'US';
        """,
    })
    assert only_row(out)["logic"] == "Filter"
    assert out["mentionsOnly"] == []


def test_the_partition_key_of_a_ranking_is_a_dedup_key(tmp_path):
    """PARTITION BY is the half of a dedup that was never read. The ORDER BY
    picks the winner; the PARTITION BY says what it wins against. Remove it and
    one record survives for the whole table instead of one per key."""
    out = scan(tmp_path, {
        "a.sql": """
            CREATE OR REPLACE TABLE final_published AS
            SELECT pub_id, last_upd FROM customer_demographics
            QUALIFY ROW_NUMBER() OVER (PARTITION BY cm13 ORDER BY last_upd) = 1;
        """,
    })
    row = only_row(out)
    assert row["logic"] == "Dedup key"
    assert row["noLocalFix"], "a missing partition key cannot be fixed downstream"
    assert out["risk"] == "high"


def test_a_named_window_clause_is_read_like_an_inline_one(tmp_path):
    """WINDOW w AS (PARTITION BY cm13 ...) puts the same dedup somewhere else in
    the statement. Writing it the other way round is not a reason to miss it."""
    out = scan(tmp_path, {
        "a.sql": """
            CREATE OR REPLACE TABLE final_published AS
            SELECT pub_id, ROW_NUMBER() OVER w AS rn
            FROM customer_demographics
            WINDOW w AS (PARTITION BY cm13 ORDER BY last_upd);
        """,
    })
    assert only_row(out)["logic"] == "Dedup key"


def test_a_merge_that_names_its_source_table_is_followed(tmp_path):
    """MERGE is how a published table is normally loaded. With USING naming a
    table directly there is no SELECT in the statement at all, so it recorded no
    sources, was never indexed as reading anything, and no scan could reach it
    however hard it looked."""
    out = scan(tmp_path, {
        "a.sql": """
            MERGE INTO final_published t
            USING customer_demographics s
            ON t.pub_id = s.pub_id AND t.cm13 = s.cm13
            WHEN MATCHED THEN UPDATE SET t.last_upd = s.last_upd;
        """,
    })
    assert only_row(out)["logic"] == "Join key"


def test_a_merge_renames_the_column_into_the_published_table(tmp_path):
    """SET t.market = s.cm13 publishes cm13 as market, and the INSERT list
    renames by position exactly as a plain INSERT does. Following the source's
    own name walked off the end of the chain at the loading statement."""
    out = scan(tmp_path, {
        "a.sql": """
            MERGE INTO mid_stage t
            USING customer_demographics s
            ON t.pub_id = s.pub_id
            WHEN MATCHED THEN UPDATE SET t.market = s.cm13
            WHEN NOT MATCHED THEN INSERT (pub_id, market) VALUES (s.pub_id, s.cm13);
        """,
        "b.sql": """
            CREATE OR REPLACE TABLE final_published AS
            SELECT market FROM mid_stage WHERE market IS NOT NULL;
        """,
    })
    assert [g["prod"] for g in out["groups"]] == ["final_published"]
    hops = {(r["from"], r["attr"], r["alias"]) for g in out["groups"] for r in g["rows"]}
    assert ("customer_demographics", "cm13", "market") in hops, hops
    assert ("mid_stage", "market", "market") in hops, hops


def test_the_condition_on_a_merge_when_is_read(tmp_path):
    """WHEN MATCHED AND s.cm13 = 'DEAD' THEN DELETE decides which rows of a
    published table are deleted, and is often the only place in the whole
    statement the column is named."""
    out = scan(tmp_path, {
        "a.sql": """
            MERGE INTO final_published t
            USING customer_demographics s
            ON t.pub_id = s.pub_id
            WHEN MATCHED AND s.cm13 = 'DEAD' THEN DELETE;
        """,
    })
    assert only_row(out)["logic"] == "Filter"


def test_an_update_reads_the_table_its_from_clause_names(tmp_path):
    """UPDATE ... FROM reads a whole second table. Only the table being written
    was ever recorded, so the source was invisible -- the same hole as MERGE,
    one statement type along."""
    out = scan(tmp_path, {
        "a.sql": """
            UPDATE final_published t SET t.market = s.cm13
            FROM customer_demographics s WHERE t.pub_id = s.pub_id;
        """,
    })
    assert [g["prod"] for g in out["groups"]] == ["final_published"]
    assert out["mentionsOnly"] == []


def test_a_column_opened_out_by_unnest_is_reported(tmp_path):
    """FROM t, UNNEST(cm13) has no ON clause to look at, and the column is named
    nowhere else in the statement."""
    out = scan(tmp_path, {
        "a.sql": """
            CREATE OR REPLACE TABLE final_published AS
            SELECT pub_id, c FROM customer_demographics, UNNEST(cm13) AS c;
        """,
    })
    assert only_row(out)["logic"] == "Transform"


def test_the_statements_own_order_by_is_reported(tmp_path):
    """ORDER BY writes the name down, so removing the column stops the statement
    compiling and the table stops loading. With a LIMIT under it the column also
    decides which rows survive, which is the ranking case."""
    plain = scan(tmp_path / "plain", {
        "a.sql": """
            CREATE OR REPLACE TABLE final_published AS
            SELECT pub_id FROM customer_demographics ORDER BY cm13;
        """,
    })
    row = only_row(plain)
    assert row["logic"] == "Sort order"
    assert row["breaking"], "the statement stops compiling without the column"
    assert not row["noLocalFix"], "a sort order can be changed in this file"

    limited = scan(tmp_path / "limited", {
        "a.sql": """
            CREATE OR REPLACE TABLE final_published AS
            SELECT pub_id FROM customer_demographics ORDER BY cm13 LIMIT 100;
        """,
    })
    assert only_row(limited)["logic"] == "Ranking", "with a LIMIT it picks the survivors"


# ── 9. one file, several statements ────────────────────────────────────────
def test_each_statement_in_a_file_is_its_own_finding(tmp_path):
    """A finding used to be one per file, table, column and kind. One file very
    often builds several tables and filters on the same source column in each,
    so the second and third statements were folded into the first: the row shown
    under the published table pointed at another statement's lines, named
    another statement's target, and the count of usages was quietly short."""
    out = scan(tmp_path, {
        "a.sql": """
            CREATE OR REPLACE TABLE stage_one AS
            SELECT pub_id FROM customer_demographics WHERE cm13 = 'A';

            CREATE OR REPLACE TABLE stage_two AS
            SELECT pub_id FROM customer_demographics WHERE cm13 = 'B';

            CREATE OR REPLACE TABLE final_published AS
            SELECT pub_id FROM customer_demographics WHERE cm13 = 'C';
        """,
    })
    assert out["attributes"][0]["found"] == 3, "three statements, three usages"
    row = only_row(out)
    assert row["inter"] == "final_published", \
        "the row under final_published must be the statement that builds it"
    assert "final_published" in row["impact"], row["impact"]


# ── 10. BigQuery wildcard tables ───────────────────────────────────────────
# Date sharding is how a great deal of BigQuery source data is stored, and the
# only way to read it is a wildcard:
#
#     SELECT cm13 FROM `prj.ds.customer_demographics_*`
#     WHERE _TABLE_SUFFIX BETWEEN '20260101' AND '20260131'
#
# Ripple recorded the source as "customer_demographics_*", asterisk and all.
# Nobody has a table called that. Scanning a real shard matched nothing, and
# scanning the family name matched nothing either -- zero findings, a clean
# "no impact", on a change that breaks a published table.
WILDCARD = {
    "a.sql": """
        CREATE OR REPLACE TABLE stage_wild AS
        SELECT cm13 FROM `prj.ds.customer_demographics_*`
        WHERE _TABLE_SUFFIX BETWEEN '20260101' AND '20260131';
    """,
    "b.sql": """
        CREATE OR REPLACE TABLE final_published AS
        SELECT cm13 FROM stage_wild WHERE cm13 IS NOT NULL;
    """,
}


def test_a_real_shard_is_found_by_the_wildcard_that_reads_it(tmp_path):
    """The reproduction. A shard name is what a person types, and it used to
    match nothing at all."""
    out = scan(tmp_path, WILDCARD, table="customer_demographics_20260101")
    assert [g["prod"] for g in out["groups"]] == ["final_published"]
    assert out["stats"]["productionTables"] == 1
    assert out["risk"] != "none"


def test_the_family_name_a_person_types_is_found_too(tmp_path):
    """BigQuery itself would not match "customer_demographics" against
    "customer_demographics_*" -- the trailing separator is part of the prefix.
    Ripple matches it anyway, because that is what somebody asked what breaks
    actually types, and the cost of refusing is the clean "no impact" this
    whole file exists to prevent."""
    out = scan(tmp_path, WILDCARD, table="customer_demographics")
    assert [g["prod"] for g in out["groups"]] == ["final_published"]


def test_the_wildcard_is_named_on_the_result_not_somewhere_else(tmp_path):
    """A caveat on a different screen from the answer it qualifies is a caveat
    nobody reads. The finding says the table was reached through a wildcard,
    and names the wildcard as the SQL spells it."""
    out = scan(tmp_path, WILDCARD, table="customer_demographics_20260101")
    wild = out["wildcardNames"]
    assert len(wild) == 1, wild
    assert wild[0]["table"] == "customer_demographics_20260101"
    assert wild[0]["patterns"] == ["customer_demographics_*"], \
        "spelt as the file spells it, not as the index keys it"


def test_a_wildcard_does_not_swallow_an_unrelated_table(tmp_path):
    """The star only stands for what comes after the prefix. A shorter name
    that happens to start the same way is a different table, and matching it
    would put a finding about somebody else's table on this result."""
    out = scan(tmp_path, WILDCARD, table="cust")
    assert out["groups"] == []
    assert out["wildcardNames"] == []


def test_nothing_is_said_when_the_wildcard_is_what_was_typed(tmp_path):
    """Somebody who typed the asterisk knows the answer covers a family. A
    warning printed on every scan is a warning nobody reads."""
    out = scan(tmp_path, WILDCARD, table="customer_demographics_*")
    assert [g["prod"] for g in out["groups"]] == ["final_published"]
    assert out["wildcardNames"] == []


def test_a_wildcard_in_another_dataset_is_still_a_different_table(tmp_path):
    """The dataset rules a match out exactly as it does for an ordinary name.
    A wildcard is not a licence to ignore what the SQL did say."""
    out = scan(tmp_path, {
        "a.sql": """
            CREATE OR REPLACE TABLE final_published AS
            SELECT cm13 FROM `prj.archive_ds.customer_demographics_*`;
        """,
    }, table="live_ds.customer_demographics_20260101")
    assert out["groups"] == [], "archive_ds and live_ds are two different tables"


# ── 11. a staging table promoted into a published one ──────────────────────
# The last step of a great many pipelines: build the table in a staging dataset,
# check it, then promote it by copying or renaming it into the published one.
# None of these four statements has a SELECT anywhere in it, so Ripple recorded
# no source for any of them. The trail died at the staging table and the screen
# said "last table in the chain - not matched by your production naming rule" --
# a calm, confident answer, with the published table one line further down the
# same folder never mentioned.
PROMOTE = "CREATE OR REPLACE TABLE stage_x AS SELECT cm13 FROM customer_demographics;"


def promote(tmp_path, statement: str) -> dict:
    return scan(tmp_path, {"a.sql": PROMOTE, "b.sql": statement})


@pytest.mark.parametrize("statement,word", [
    ("CREATE OR REPLACE TABLE final_published COPY stage_x;", "COPY"),
    ("CREATE TABLE final_published CLONE stage_x;", "CLONE"),
    ("CREATE TABLE final_published LIKE stage_x;", "LIKE"),
    ("CREATE SNAPSHOT TABLE final_published CLONE stage_x;", "CLONE"),
    ("ALTER TABLE stage_x RENAME TO final_published;", "RENAME"),
])
def test_a_whole_table_copy_carries_the_chain_into_production(tmp_path, statement, word):
    out = promote(tmp_path, statement)
    assert [g["prod"] for g in out["groups"]] == ["final_published"], statement
    assert out["stats"]["productionTables"] == 1


@pytest.mark.parametrize("statement,word", [
    ("CREATE OR REPLACE TABLE final_published COPY stage_x;", "COPY"),
    ("CREATE TABLE final_published CLONE stage_x;", "CLONE"),
    ("ALTER TABLE stage_x RENAME TO final_published;", "RENAME"),
])
def test_a_copied_table_is_marked_worked_out_and_named_by_its_own_word(
        tmp_path, statement, word):
    """A copy carries every column and writes none of them down, which is what
    SELECT * does -- so it is followed the same way. What it must NOT do is
    tell the reader the file says SELECT *, because the file says COPY.

    Whether the hop is worked out or read depends on the table copied. Here
    stage_x is built with its columns named, so the copy's column list is
    known (see test_star_known.py) and nothing is inferred. The variant below
    copies a table whose list is written nowhere, and there it IS worked out."""
    out = promote(tmp_path, statement)
    assert [g["prod"] for g in out["groups"]] == ["final_published"]
    assert out["stats"]["inferredFindings"] == 0, "stage_x names its columns, so the copy's list is known"
    assert out["stats"]["tablesNotVisible"] == 0
    star = out["starTables"][0]
    assert star["table"] == "final_published"
    assert star["from"] == "stage_x"
    assert star["known"] is True and star["columns"] == 1 and star["listedIn"] == "a.sql"
    assert star["how"] == word, "the card names the word the file actually uses"


@pytest.mark.parametrize("statement,word", [
    ("CREATE OR REPLACE TABLE final_published COPY stage_x;", "COPY"),
    ("CREATE TABLE final_published CLONE stage_x;", "CLONE"),
    ("ALTER TABLE stage_x RENAME TO final_published;", "RENAME"),
])
def test_a_copy_of_a_table_with_no_written_list_is_worked_out_and_named_by_its_own_word(
        tmp_path, statement, word):
    """stage_x is itself a SELECT * from a table nothing here defines, so no
    column list exists anywhere in the repository. The copy carries every
    column and every step past it is worked out rather than read."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE stage_x AS SELECT * FROM customer_demographics;",
        "b.sql": statement})
    assert [g["prod"] for g in out["groups"]] == ["final_published"]
    assert out["stats"]["inferredFindings"] >= 1, "the hop is worked out, not read"
    assert out["stats"]["tablesNotVisible"] == 2, "stage_x and its copy"
    star = next(s for s in out["starTables"] if s["table"] == "final_published")
    assert star["from"] == "stage_x" and star["known"] is False
    assert star["how"] == word, "the card names the word the file actually uses"


def test_an_ordinary_select_star_is_still_not_labelled_a_copy(tmp_path):
    """The guard on the other side: a real SELECT * must not start claiming to
    be a COPY, or the card lies in the opposite direction."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE stage_x AS SELECT * FROM customer_demographics;",
        "b.sql": "CREATE OR REPLACE TABLE final_published AS SELECT cm13 FROM stage_x;"})
    assert [g["prod"] for g in out["groups"]] == ["final_published"]
    assert out["starTables"][0]["how"] == "", "an ordinary star has no copy word"


def test_a_copy_of_an_unrelated_table_is_not_dragged_in(tmp_path):
    """A promote step only carries the chain when it copies a table the chain
    actually reached."""
    out = scan(tmp_path, {
        "a.sql": PROMOTE,
        "b.sql": "CREATE OR REPLACE TABLE final_published COPY some_other_table;"})
    assert out["groups"] == [], "final_published is a copy of a table with no cm13 in it"


# ── 12. table-valued functions ─────────────────────────────────────────────
# A BigQuery TABLE FUNCTION is a table as far as lineage is concerned: it is
# named, it is read in a FROM clause, and every column of its body travels
# through it. Both halves used to be invisible. The definition parses as a
# function rather than a table, so it published nothing; and the call parses as
# a function call whose table node carries no name at all, so it read nothing.
# The chain broke in the middle and the published table was never mentioned.
def tvf(tmp_path, define: str, call: str) -> dict:
    return scan(tmp_path, {"a.sql": define, "b.sql": call})


@pytest.mark.parametrize("define,call", [
    ("CREATE OR REPLACE TABLE FUNCTION mid_tvf(d STRING) AS"
     " (SELECT cm13 FROM customer_demographics WHERE dt = d);",
     "CREATE OR REPLACE TABLE final_published AS SELECT cm13 FROM mid_tvf('x');"),
    ("CREATE OR REPLACE TABLE FUNCTION ds.mid_tvf(d STRING) AS"
     " (SELECT cm13 FROM customer_demographics);",
     "CREATE OR REPLACE TABLE final_published AS SELECT cm13 FROM ds.mid_tvf('x');"),
    ("CREATE OR REPLACE TABLE FUNCTION `prj.ds.mid_tvf`(d STRING) AS"
     " (SELECT cm13 FROM customer_demographics);",
     "CREATE OR REPLACE TABLE final_published AS SELECT cm13 FROM `prj.ds.mid_tvf`('x');"),
])
def test_a_table_function_carries_the_chain(tmp_path, define, call):
    out = tvf(tmp_path, define, call)
    assert [g["prod"] for g in out["groups"]] == ["final_published"], define


def test_a_scalar_udf_is_not_treated_as_a_table(tmp_path):
    """A scalar UDF parses as the same node, with the same kind. Only its body
    tells them apart: a table function returns a SELECT, a scalar one returns an
    expression. Get that wrong and every helper in the repository becomes a
    table nobody has."""
    out = scan(tmp_path, {"a.sql":
        "CREATE TEMP FUNCTION scrub(x STRING) AS (UPPER(x));\n"
        "CREATE OR REPLACE TABLE final_published AS"
        " SELECT scrub(cm13) AS cm13 FROM customer_demographics;"})
    assert [g["prod"] for g in out["groups"]] == ["final_published"]
    rows = [r for g in out["groups"] for r in g["rows"]]
    assert not any("scrub" in (r["inter"] or "").lower() for r in rows), \
        "scrub is a function, not a table on the trail"


def test_a_builtin_wrapper_is_not_invented_as_a_table(tmp_path):
    """BigQuery's own table functions wrap a table rather than being one, and
    the table they wrap is parsed separately and found anyway. Taking the
    wrapper's name too would put a table nobody has on the result."""
    out = scan(tmp_path, {"a.sql":
        "CREATE OR REPLACE TABLE final_published AS "
        "SELECT cm13 FROM customer_demographics UNION ALL "
        "SELECT cm13 FROM EXTERNAL_QUERY('conn', 'SELECT cm13 FROM x');"})
    assert [g["prod"] for g in out["groups"]] == ["final_published"]
    names = [r["inter"] for g in out["groups"] for r in g["rows"]]
    assert not any("external_query" in (n or "").lower() for n in names), names


def test_unnest_is_still_not_a_table(tmp_path):
    """The guard on the change above: UNNEST sits in a FROM clause and looks
    like a function call, and turning it into a table would put one on every
    result in the repository."""
    out = scan(tmp_path, {"a.sql":
        "CREATE OR REPLACE TABLE final_published AS"
        " SELECT cm13, t FROM customer_demographics, UNNEST(tags) AS t;"})
    assert [g["prod"] for g in out["groups"]] == ["final_published"]
    names = [r["inter"] for g in out["groups"] for r in g["rows"]]
    assert not any("unnest" in (n or "").lower() for n in names), names


# ── 13. a source is not the target just because the names look alike ───────
# Sources are gathered by walking every table in a statement, which finds the
# write target too, so the target has to be left out. That was done by
# comparing NAMES with same_table -- and same_table is deliberately loose,
# because a name with no dataset must go on matching one that has a dataset or
# every templated chain in this repository breaks.
#
# Loose is right for FOLLOWING a chain and catastrophic for EXCLUDING a source.
# Both shapes below threw away the only source the statement had, so the
# statement was indexed as reading nothing and the scan came back clean.
def test_a_wildcard_covering_its_own_target_does_not_erase_the_source(tmp_path):
    """events_* covers events_rollup, because a wildcard is a prefix match and
    that really is what BigQuery does. It is still the source, not the target."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE `p.ds.events_rollup` AS "
                 "SELECT cm13 FROM `p.ds.events_*`;",
        "b.sql": "CREATE OR REPLACE TABLE `p.pub.exec_published` AS "
                 "SELECT cm13 FROM `p.ds.events_rollup`;",
    }, table="events_20260101")
    assert [g["prod"] for g in out["groups"]] == ["exec_published"]


def test_a_templated_target_dataset_does_not_erase_the_source(tmp_path):
    """The dataset on the target is a placeholder, so it is dropped -- leaving a
    bare "orders" that matched "stage.orders" and took the source with it."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE {{ target_dataset }}.orders AS "
                 "SELECT id, cm13 AS promo FROM stage.orders;",
        "b.sql": "CREATE OR REPLACE TABLE final_published AS SELECT promo FROM orders;",
    }, table="stage.orders")
    assert [g["prod"] for g in out["groups"]] == ["final_published"]


def test_a_table_rebuilt_from_itself_is_still_read(tmp_path):
    """INSERT INTO t SELECT ... FROM t reads t. Excluding the target by name
    threw that away, and the statement was filed under "the name appears, but
    no lineage to a production table" -- the opposite of the truth."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE final_published AS "
                 "SELECT cm13 FROM customer_demographics;\n"
                 "INSERT INTO final_published (cm13) "
                 "SELECT UPPER(cm13) FROM final_published;",
    })
    assert [g["prod"] for g in out["groups"]] == ["final_published"]
    assert len([r for g in out["groups"] for r in g["rows"]]) >= 2, \
        "both the build and the self-referencing insert are usages"


def test_a_wildcard_with_nothing_in_front_of_it_does_not_match_everything(tmp_path):
    """A bare * matches every table there is. Following that would put the whole
    warehouse on every chain -- not a spare row somebody can dismiss."""
    from ripple.scanner.sqlread import same_table, wildcard_covers
    assert wildcard_covers("*", "anything_at_all") is False
    assert same_table("*", "customer_demographics") is False
    # Scoped by a dataset it is meaningful again, and only inside that dataset.
    assert same_table("ds.*", "ds.customer_demographics") is True
    assert same_table("ds.*", "other_ds.customer_demographics") is False
    assert same_table("ds.*", "customer_demographics") is False, \
        "an unqualified name does not say it is in that dataset"


# ── 14. shapes the SQL parser refuses ──────────────────────────────────────
# sqlglot fails these two ways, and both are quiet: a hard parse error, which
# loses the statement AND its neighbours; or a fall back to a node holding raw
# text and no tables, which is invisible unless it is the only statement in its
# file. Either way the answer is a clean "no impact". Each shape below was
# measured against the installed parser, and each appears in ordinary BigQuery.
@pytest.mark.parametrize("what,files", [
    ("APPENDS(TABLE t) - the incremental read", {
        "a.sql": "CREATE OR REPLACE TABLE stage1 AS "
                 "SELECT cm13 FROM APPENDS(TABLE `prj.ds.customer_demographics`, NULL);",
        "b.sql": "CREATE OR REPLACE TABLE final_published AS SELECT cm13 FROM stage1;"}),
    ("a TVF handed a table", {
        "a.sql": "CREATE OR REPLACE TABLE final_published AS "
                 "SELECT cm13 FROM `prj.ds.pick`(TABLE `prj.ds.customer_demographics`, 'x');"}),
    ("ML.PREDICT(MODEL m, TABLE t)", {
        "a.sql": "CREATE OR REPLACE TABLE final_published AS SELECT cm13 FROM "
                 "ML.PREDICT(MODEL `prj.ds.m1`, TABLE `prj.ds.customer_demographics`);"}),
    ("EXTERNAL TABLE with a BigLake connection", {
        "a.sql": "CREATE OR REPLACE EXTERNAL TABLE customer_demographics (cm13 STRING)\n"
                 " WITH CONNECTION `prj.us.myconn`\n"
                 " WITH PARTITION COLUMNS (dt DATE)\n"
                 " OPTIONS (format='PARQUET', uris=['gs://b/*']);",
        "b.sql": "CREATE OR REPLACE TABLE final_published AS "
                 "SELECT cm13 FROM customer_demographics;"}),
    ("LOAD DATA INTO declares the columns", {
        "a.sql": "LOAD DATA INTO customer_demographics (cm13 STRING, region STRING)\n"
                 " FROM FILES (format='CSV', uris=['gs://b/x.csv']);",
        "b.sql": "CREATE OR REPLACE TABLE final_published AS "
                 "SELECT cm13 FROM customer_demographics;"}),
    ("CLONE ... FOR SYSTEM_TIME AS OF - the restore", {
        "a.sql": "CREATE OR REPLACE TABLE stage1 AS SELECT cm13 FROM customer_demographics;",
        "b.sql": "CREATE TABLE final_published CLONE stage1 "
                 "FOR SYSTEM_TIME AS OF TIMESTAMP('2026-01-01');"}),
    ("MATERIALIZED VIEW AS REPLICA OF", {
        "a.sql": "CREATE OR REPLACE TABLE stage1 AS SELECT cm13 FROM customer_demographics;",
        "b.sql": "CREATE MATERIALIZED VIEW final_published AS REPLICA OF stage1;"}),
])
def test_a_shape_the_parser_refuses_is_still_followed(tmp_path, what, files):
    out = scan(tmp_path, files)
    assert [g["prod"] for g in out["groups"]] == ["final_published"], what


def test_an_export_is_a_real_read_not_an_unreadable_file(tmp_path):
    """EXPORT DATA delivers to somebody outside the warehouse. It builds no
    table, so there is nothing to carry the column on to -- but it IS a read,
    and it used to be filed as a file that could not be read."""
    out = scan(tmp_path, {
        "a.sql": "EXPORT DATA OPTIONS(uri='gs://b/out/*.csv', format='CSV') AS\n"
                 " SELECT cm13 FROM customer_demographics;"})
    assert out["stats"]["couldNotRead"] == 0, "it can be read now"
    assert out["other"], "and the usage is reported, under no production table"


def test_a_partition_decorator_is_the_same_table(tmp_path):
    """customer_demographics$20260101 is ONE DAY of one table, not another
    table. Kept as part of the name it split every decorated read off from the
    table it belongs to, and the scan came back clean."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE stage1 AS "
                 "SELECT cm13 FROM `prj.ds.customer_demographics$20260101`;",
        "b.sql": "CREATE OR REPLACE TABLE final_published AS SELECT cm13 FROM stage1;"})
    assert [g["prod"] for g in out["groups"]] == ["final_published"]


def test_the_rescue_pass_never_moves_a_line():
    """Everything above is done to a copy on the way into the parser. A finding
    that points at the wrong line is worse than no finding, because the person
    goes and looks and finds nothing there."""
    from ripple.scanner import rescue
    for text in [
        "CREATE MATERIALIZED VIEW m\n  AS REPLICA OF\n  src",
        "EXPORT DATA OPTIONS(\n  uri='gs://b/*.csv',\n  format='CSV')\nAS SELECT cm13 FROM cust",
        "CREATE EXTERNAL TABLE t (a STRING)\n WITH CONNECTION `p.us.c`\n"
        " WITH PARTITION COLUMNS (dt DATE)\n OPTIONS (format='PARQUET');",
        "LOAD DATA INTO t (a STRING)\n FROM FILES (format='CSV', uris=['gs://b/x.csv']);",
        "SELECT cm13\n FROM APPENDS(TABLE `p.d.cust`,\n NULL)",
    ]:
        assert rescue.rewrite(text).count("\n") == text.count("\n"), text[:40]


def test_ordinary_sql_goes_through_the_rescue_pass_untouched():
    from ripple.scanner import rescue
    for text in ["SELECT a, b FROM t WHERE x = 1",
                 "CREATE OR REPLACE TABLE x AS SELECT * FROM y",
                 "MERGE INTO t USING s ON t.k = s.k WHEN MATCHED THEN UPDATE SET a = s.a"]:
        assert rescue.rewrite(text) == text, text


# ── 15. a column list written on the CREATE line ───────────────────────────
def test_a_view_with_its_own_column_list_renames_the_column(tmp_path):
    """BigQuery lets a view pin its output names in the CREATE line, and it is
    the ordinary way a team publishes friendly names over warehouse codes. The
    list was thrown away, so the chain stopped at the view."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE VIEW v1(a, b) AS "
                 "SELECT cm13, region FROM customer_demographics;",
        "b.sql": "CREATE OR REPLACE TABLE final_published AS SELECT a FROM v1;"})
    assert [g["prod"] for g in out["groups"]] == ["final_published"]


def test_a_ctas_with_a_column_list_renames_the_column(tmp_path):
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE s1(a STRING, b STRING) AS "
                 "SELECT cm13, region FROM customer_demographics;",
        "b.sql": "CREATE OR REPLACE TABLE final_published AS SELECT a FROM s1;"})
    assert [g["prod"] for g in out["groups"]] == ["final_published"]


def test_a_column_list_of_the_wrong_length_is_not_guessed_at(tmp_path):
    """Where the two lists cannot be lined up, the name is left alone rather
    than mapped to whatever happens to be in that position."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE VIEW v1(a) AS "
                 "SELECT cm13, region FROM customer_demographics;",
        "b.sql": "CREATE OR REPLACE TABLE final_published AS SELECT cm13 FROM v1;"})
    assert [g["prod"] for g in out["groups"]] == ["final_published"], \
        "the old name is kept, so the chain is followed rather than dropped"


# ── 16. an unreadable statement that names a table on the trail ────────────
def test_a_statement_ripple_cannot_read_that_names_a_trail_table_is_reported(tmp_path):
    """The quietest hole left: the file parses, the readable statements produce
    findings, and the one statement that carries the chain onwards is simply
    absent. The result reads as complete because nothing says otherwise."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE staging AS SELECT cm13 FROM customer_demographics;\n"
                 "CALL ds.load_published(staging);"})
    assert out["stats"]["couldNotRead"] == 1
    assert "staging" in out["unreadable"][0]["reason"]


def test_an_unreadable_statement_about_something_else_is_not_reported(tmp_path):
    """Every real pipeline is full of DECLAREs and CALLs that carry no lineage.
    Reporting those would bury the list this is meant to protect."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE staging AS SELECT cm13 FROM customer_demographics;\n"
                 "CALL ds.publish_from_elsewhere();"})
    assert out["stats"]["couldNotRead"] == 0


# ── 17. a table that stops being refreshed ─────────────────────────────────
# A column used only in a WHERE, a JOIN or a GROUP BY never reaches the table
# the statement builds, so the trail for that COLUMN really does end there --
# and Ripple said so, and stopped. But the statement stops working on the day
# the column goes, so the table it builds stops being rebuilt, and everything
# under it is served from data nobody is updating any more. That is an outage
# that arrives quietly, days later, and it was invisible.
FILTER_ONLY = {
    "a.sql": "CREATE OR REPLACE TABLE stage_f AS "
             "SELECT id, amount FROM customer_demographics WHERE cm13 = 'US';",
    "b.sql": "CREATE OR REPLACE TABLE final_published AS SELECT id, amount FROM stage_f;",
}


def test_a_published_table_below_a_broken_statement_is_named(tmp_path):
    out = scan(tmp_path, FILTER_ONLY)
    assert [g["prod"] for g in out["groups"]] == [], \
        "cm13 genuinely does not reach final_published as a column"
    stops = out["stopsLoading"]
    assert [r["prod"] for r in stops] == ["final_published"]
    assert stops[0]["because"] == "stage_f"
    assert stops[0]["via"] == ["stage_f", "final_published"]
    assert out["stats"]["productionStopsLoading"] == 1


def test_it_is_counted_apart_from_the_tables_whose_columns_change(tmp_path):
    """Two different kinds of impact. One number covering both is a number that
    means neither, so the headline count must not absorb it."""
    out = scan(tmp_path, FILTER_ONLY)
    assert out["stats"]["productionTables"] == 0
    assert out["stats"]["productionStopsLoading"] == 1


def test_it_is_followed_more_than_one_hop_down(tmp_path):
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE stage_f AS "
                 "SELECT id FROM customer_demographics WHERE cm13 = 'US';",
        "b.sql": "CREATE OR REPLACE TABLE mid_t AS SELECT id FROM stage_f;",
        "c.sql": "CREATE OR REPLACE TABLE final_published AS SELECT id FROM mid_t;"})
    stops = out["stopsLoading"]
    assert [r["prod"] for r in stops] == ["final_published"]
    assert stops[0]["via"] == ["stage_f", "mid_t", "final_published"]


def test_a_table_already_reported_above_is_not_reported_twice(tmp_path):
    """When the column really does travel, the table is in the findings. Saying
    it again under a different heading reads as two problems."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE stage_s AS SELECT cm13 FROM customer_demographics;",
        "b.sql": "CREATE OR REPLACE TABLE final_published AS SELECT cm13 FROM stage_s;"})
    assert [g["prod"] for g in out["groups"]] == ["final_published"]
    assert out["stopsLoading"] == []


def test_nothing_breaking_means_nothing_stops(tmp_path):
    """A value change does not stop a statement running, so nothing downstream
    stops loading. This list must not fire on every scan."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE stage_f AS SELECT id FROM customer_demographics;",
        "b.sql": "CREATE OR REPLACE TABLE final_published AS SELECT id FROM stage_f;"},
        change="value_change")
    assert out["stopsLoading"] == []


# ── 18. a whole row carried as one value ───────────────────────────────────
# BigQuery lets a query carry an entire row around as a single value, and the
# standard dbt-utils deduplicate macro is written exactly that way. Ripple's
# whole honesty guarantee rests on admitting when a table's column list is not
# written down -- and that admission fired for SELECT * and for alias.* over a
# real table, but not for this. A deduplicated staging table, an ordinary thing
# in a dbt repository, gave a clean "no impact" with no warning at all.
DEDUP = {
    "a.sql": "CREATE OR REPLACE TABLE stage_dedup AS\n"
             "SELECT unique_row.* FROM (\n"
             "  SELECT ARRAY_AGG(original ORDER BY original.loaded_at DESC LIMIT 1)[OFFSET(0)]"
             " AS unique_row\n"
             "  FROM customer_demographics original\n"
             "  GROUP BY original.id);",
    "b.sql": "CREATE OR REPLACE TABLE final_published AS SELECT cm13 FROM stage_dedup;",
}


def test_the_dbt_deduplicate_macro_does_not_stop_the_trail(tmp_path):
    out = scan(tmp_path, DEDUP)
    assert [g["prod"] for g in out["groups"]] == ["final_published"]


def test_a_whole_row_star_admits_the_column_list_is_not_visible(tmp_path):
    """It carries every column and names none of them, which is exactly what a
    SELECT * does -- so it has to be marked the same way, or the finding on the
    far side reads as read rather than worked out."""
    out = scan(tmp_path, DEDUP)
    assert [t["table"] for t in out["starTables"]] == ["stage_dedup"]
    assert out["stats"]["inferredFindings"] >= 1


def test_a_qualified_star_over_a_real_table_still_only_carries_that_table(tmp_path):
    """The guard on the change above, restated: b.* is b's columns, not a's."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE stage_star AS "
                 "SELECT b.* FROM customer_demographics a JOIN other_side b ON a.k = b.k;",
        "b.sql": "CREATE OR REPLACE TABLE final_published AS SELECT cm13 FROM stage_star;"})
    assert out["groups"] == []


def test_a_struct_of_named_columns_is_not_a_whole_row(tmp_path):
    """STRUCT(other_col AS z) names its columns. Treating it as a whole row
    would put every column of the table on the chain, including ones the
    statement plainly never touched."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE s1 AS SELECT p.* FROM "
                 "(SELECT STRUCT(other_col AS z) AS p FROM customer_demographics);",
        "b.sql": "CREATE OR REPLACE TABLE final_published AS SELECT cm13 FROM s1;"})
    assert out["groups"] == []


# ── a query with no CREATE in front of it ──────────────────────────────────
# A dbt model is a bare SELECT. Nothing in the file names the table it builds --
# dbt does, after the file. Before this, a dbt repository produced ZERO lineage:
# every chain came back empty, no production table was ever named, and the answer
# was the calmest, cleanest "no impact" this tool can print. dbt is the commonest
# way a BigQuery pipeline is written.
DBT = {
    "models/staging/stg_customers.sql":
        "SELECT cust_id, cm13 FROM {{ source('raw', 'customer_demographics') }}",
    "models/intermediate/int_customers.sql":
        "SELECT cust_id, cm13 FROM {{ ref('stg_customers') }}",
    "models/marts/customer_published.sql":
        "{{ config(materialized='table') }}\n"
        "SELECT cust_id, cm13, COUNT(*) AS n FROM {{ ref('int_customers') }}\n"
        "GROUP BY cust_id, cm13",
}


def test_a_dbt_repository_reaches_its_published_table(tmp_path):
    """The reproduction. Three models, one chain, and a published table at the
    end of it -- which used to come back as no production table at all."""
    out = scan(tmp_path, DBT)
    assert [g["prod"] for g in out["groups"]] == ["customer_published"]
    assert out["stats"]["productionTables"] == 1


def test_a_dbt_config_header_does_not_make_the_file_unreadable(tmp_path):
    """``{{ config(materialized='table') }}`` is an instruction to dbt, not a
    value. Turned into a bare identifier it put a word where SQL expects a
    keyword, so the WHOLE FILE stopped parsing -- measured at 100% unreadable in
    every spelling tried. Every dbt model in the world opens with one."""
    out = scan(tmp_path, DBT)
    assert out["stats"]["couldNotRead"] == 0, out["unreadable"]


def test_the_dbt_chain_says_the_table_name_came_from_the_file(tmp_path):
    """Nobody sent to that line will find the table name written on it. A
    finding somebody cannot verify is one they dismiss."""
    out = scan(tmp_path, DBT)
    named = {t["table"]: t for t in out["namedByFile"]}
    assert "customer_published" in named
    assert named["customer_published"]["how"] == "dbt"
    assert named["customer_published"]["file"] == "models/marts/customer_published.sql"


def test_one_query_in_a_plain_sql_file_is_still_followed(tmp_path):
    """No models/ folder and no dbt call, so this is the weaker evidence -- but
    something runs the file and puts the rows somewhere, and every tool that
    works this way names it after the file. Labelled for what it is."""
    out = scan(tmp_path, {
        "jobs/mid.sql": "SELECT cust_id, cm13 FROM customer_demographics",
        "jobs/final_published.sql": "SELECT cust_id, cm13 FROM mid"})
    assert [g["prod"] for g in out["groups"]] == ["final_published"]
    assert {t["how"] for t in out["namedByFile"]} == {"file"}


def test_a_file_holding_two_queries_is_not_named_after_itself(tmp_path):
    """Two bare SELECTs cannot both be the table the file is named after, and
    guessing which would merge two unrelated queries into one table."""
    out = scan(tmp_path, {
        "jobs/mid.sql": "SELECT cm13 FROM customer_demographics;\n"
                        "SELECT other_col FROM customer_demographics;",
        "jobs/final_published.sql": "SELECT cm13 FROM mid"})
    assert out["groups"] == []
    assert "mid" not in {t["table"] for t in out["namedByFile"]}


def test_export_data_is_not_a_table_named_after_its_file(tmp_path):
    """EXPORT DATA is rewritten to a bare SELECT on the way into the parser, so
    by the time the tree exists it is indistinguishable from a dbt model. It
    delivers a file to somebody outside the warehouse and builds no table;
    naming its destination after the .sql file would be a table nobody has."""
    out = scan(tmp_path, {
        "a.sql": "EXPORT DATA OPTIONS(uri='gs://b/out/*.csv', format='CSV') AS\n"
                 " SELECT cm13 FROM customer_demographics;"})
    assert out["groups"] == []
    assert out["namedByFile"] == []
    assert out["other"], "the read itself is still reported"


# ── a temporary table belongs to one file ──────────────────────────────────
# A TEMP table is gone when its script finishes, so two files that both build a
# ``t`` are not sharing a table -- and a static scan can never know two files
# ran in one session. Temp names in real repositories are t, tmp, stg, base,
# deduped, so collisions are the norm. Before this, the second file's published
# table was reported as broken by a change nothing in it had touched, and
# mergedNames was EMPTY: no warning of any kind.
TEMP_COLLISION = {
    "a.sql": "CREATE TEMP TABLE t AS SELECT cm13 AS mkt FROM `p.d.customer_demographics`;\n"
             "CREATE OR REPLACE TABLE `p.d.report_a_published` AS SELECT mkt FROM t;",
    "b.sql": "CREATE TEMP TABLE t AS SELECT mkt FROM `p.d.unrelated`;\n"
             "CREATE OR REPLACE TABLE `p.d.report_b_published` AS SELECT mkt FROM t;",
}


def test_two_files_with_the_same_temp_table_name_are_not_one_chain(tmp_path):
    out = scan(tmp_path, TEMP_COLLISION)
    assert [g["prod"] for g in out["groups"]] == ["report_a_published"]


def test_the_unrelated_table_is_named_nowhere_on_the_result(tmp_path):
    """The same merge, one screen further along. "Stops being refreshed" walks
    onwards from a finding, and it walked from the name shown on SCREEN -- which
    for a temporary table is the short one that matches every other file's. So
    fencing the chain off moved the false claim rather than removing it: the
    unrelated published table left the findings and reappeared under "stops
    being refreshed", worded as certainly as before."""
    out = scan(tmp_path, TEMP_COLLISION)
    everywhere = repr(out)
    assert "report_b_published" not in everywhere, out["stopsLoading"]


def test_a_session_table_is_scoped_the_same_way(tmp_path):
    """BigQuery's other spelling for the same thing."""
    out = scan(tmp_path, {
        "a.sql": "CREATE TABLE _SESSION.stg AS SELECT cm13 AS mkt FROM `p.d.customer_demographics`;\n"
                 "CREATE OR REPLACE TABLE `p.d.report_a_published` AS SELECT mkt FROM _SESSION.stg;",
        "b.sql": "CREATE TABLE _SESSION.stg AS SELECT mkt FROM `p.d.unrelated`;\n"
                 "CREATE OR REPLACE TABLE `p.d.report_b_published` AS SELECT mkt FROM _SESSION.stg;"})
    assert [g["prod"] for g in out["groups"]] == ["report_a_published"]


def test_a_temp_table_still_carries_the_chain_inside_its_own_file(tmp_path):
    """The guard on the change above. Fencing them off must not cut the chain
    that runs through one, which is what a temp table is for."""
    out = scan(tmp_path, {
        "a.sql": "CREATE TEMP TABLE t AS SELECT cm13 AS mkt FROM `p.d.customer_demographics`;\n"
                 "CREATE OR REPLACE TABLE `p.d.report_a_published` AS SELECT mkt FROM t;"})
    assert [g["prod"] for g in out["groups"]] == ["report_a_published"]


def test_the_fence_is_not_shown_as_part_of_the_table_name(tmp_path):
    """The scope is Ripple's own, not something anybody wrote. A name on screen
    that is in no file sends somebody looking for a table that does not exist."""
    out = scan(tmp_path, TEMP_COLLISION)
    names = [r["inter"] for g in out["groups"] for r in g["rows"]]
    assert "t" in names, names
    assert not any("#" in (n or "") for n in names), names


def test_a_real_table_sharing_a_name_with_a_temp_one_is_left_alone(tmp_path):
    """``ds.t`` is a real table that happens to be called t. Fencing it off with
    the temporary one would cut a genuine chain."""
    out = scan(tmp_path, {
        "a.sql": "CREATE TEMP TABLE t AS SELECT other_col FROM `p.d.unrelated`;",
        "b.sql": "CREATE OR REPLACE TABLE `p.d.t` AS SELECT cm13 FROM `p.d.customer_demographics`;",
        "c.sql": "CREATE OR REPLACE TABLE `p.d.real_published` AS SELECT cm13 FROM `p.d.t`;"})
    assert [g["prod"] for g in out["groups"]] == ["real_published"]


# ── the warehouse describing itself ────────────────────────────────────────
# INFORMATION_SCHEMA views are called COLUMNS, TABLES, JOBS, VIEWS -- ordinary
# words, and a warehouse of any size has real tables called some of them. Before
# this, the metadata view and the real table were treated as one, a published
# table was reported as fed by a table it never reads, and the warning printed
# beside it blamed CAPITALISATION -- so the one thing on screen pointing at the
# problem named the wrong cause.
METADATA = {
    "a.sql": "CREATE TABLE `p.base.columns` (table_name STRING, column_name STRING);",
    "b.sql": "CREATE OR REPLACE TABLE `p.pub.report_published` AS "
             "SELECT column_name FROM `p.base`.INFORMATION_SCHEMA.COLUMNS;",
}


def test_a_real_table_is_not_merged_with_the_metadata_view_of_that_name(tmp_path):
    out = scan(tmp_path, METADATA, table="columns", attrs=("column_name",))
    assert out["groups"] == []
    assert out["risk"] == "none"


def test_no_warning_blames_capitals_for_a_metadata_read(tmp_path):
    """A warning naming the wrong cause is worse than none: following it does
    not lead anywhere near what actually happened."""
    out = scan(tmp_path, METADATA, table="columns", attrs=("column_name",))
    assert out["mergedNames"] == []


def test_the_region_wide_job_history_is_not_a_table_either(tmp_path):
    """``region-us`` is a whole region's job log addressed as if it were a
    project. Nothing in it is anybody's data -- and ``jobs`` is a name plenty of
    warehouses have a real table under."""
    out = scan(tmp_path, {
        "a.sql": "CREATE TABLE `p.base.jobs` (job_id STRING, cm13 STRING);",
        "b.sql": "CREATE OR REPLACE TABLE `p.pub.usage_published` AS "
                 "SELECT job_id FROM `region-us`.INFORMATION_SCHEMA.JOBS;"},
        table="jobs", attrs=("job_id",))
    assert out["groups"] == []
    assert out["mergedNames"] == []


def test_a_real_table_called_columns_still_carries_its_own_chain(tmp_path):
    """The guard on the change above. Only the metadata view is dropped."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE `p.pub.report_published` AS "
                 "SELECT column_name FROM `p.base.columns`;"},
        table="columns", attrs=("column_name",))
    assert [g["prod"] for g in out["groups"]] == ["report_published"]


# ── PIVOT and UNPIVOT ──────────────────────────────────────────────────────
# Both fold a column away and build differently-named ones out of it, and both
# NAME the column while doing it. Neither was read, and each failed in its own
# direction.
UNPIVOTED = {
    "a.sql": "CREATE OR REPLACE TABLE s1 AS SELECT * FROM customer_demographics\n"
             "UNPIVOT (val FOR metric IN (cm13, other_col));",
    "b.sql": "CREATE OR REPLACE TABLE final_published AS SELECT val, metric FROM s1;",
}
PIVOTED = {
    "a.sql": "CREATE OR REPLACE TABLE s1 AS "
             "SELECT * FROM (SELECT k, quarter, cm13 FROM customer_demographics)\n"
             "PIVOT (SUM(cm13) AS total FOR quarter IN ('Q1', 'Q2'));",
    "b.sql": "CREATE OR REPLACE TABLE final_published AS SELECT k, total_Q1 FROM s1;",
}


def test_an_unpivot_that_names_the_column_is_breaking(tmp_path):
    """The only case in this suite that hedged DOWNWARDS on a statement that
    hard-fails. It read as a plain SELECT *, so the answer was risk low,
    breaking false, and the sentence "Nothing here fails on the day of the
    change" -- about a statement whose UNPIVOT list stops being valid SQL."""
    out = scan(tmp_path, UNPIVOTED)
    rows = [r for g in out["groups"] for r in g["rows"]] + \
           [r for e in out["reached"] for r in e["rows"]]
    named = [r for r in rows if r["file"] == "a.sql"]
    assert named, rows
    assert named[0]["breaking"] is True
    assert "Nothing here fails" not in named[0]["impact"]


def test_an_unpivot_carries_the_column_on_under_its_new_name(tmp_path):
    """The values land in ``val`` and the column's own NAME lands in ``metric``.
    Following neither ended the trail before the published table."""
    out = scan(tmp_path, UNPIVOTED)
    assert [g["prod"] for g in out["groups"]] == ["final_published"]


def test_an_unpivot_row_says_unpivot_and_not_pivot(tmp_path):
    """They are opposite operations and the file says which. A row labelled
    PIVOT beside a line reading UNPIVOT describes a statement that is not
    there, and the reader doubts the finding rather than the label."""
    out = scan(tmp_path, UNPIVOTED)
    rows = [r for g in out["groups"] for r in g["rows"] if r["file"] == "a.sql"]
    assert rows[0]["logic"] == "Named in UNPIVOT", rows[0]["logic"]


def test_a_pivot_output_column_is_derived_so_the_trail_carries_on(tmp_path):
    """PIVOT builds total_Q1 and total_Q2 from the aggregate's alias and each IN
    value. Nothing derived them, so the trail was declared finished one hop
    early -- with the note "Last table in the chain" -- and the published table
    reading total_Q1 was never named."""
    out = scan(tmp_path, PIVOTED)
    assert [g["prod"] for g in out["groups"]] == ["final_published"]
    rows = [r for g in out["groups"] for r in g["rows"] if r["file"] == "a.sql"]
    assert rows[0]["alias"] == "total_Q1", rows[0]["alias"]
    assert rows[0]["breaking"] is True


def test_an_unpivoted_column_is_not_also_reported_as_carried_by_a_star(tmp_path):
    """The star over an UNPIVOT does not carry the folded column: it no longer
    exists as a column. Letting both speak puts "carried through untouched"
    beside "named here, and this statement fails without it"."""
    out = scan(tmp_path, UNPIVOTED)
    assert out["starTables"] == []
    assert out["stats"]["inferredFindings"] == 0


def test_a_column_the_pivot_never_names_is_still_carried_by_the_star(tmp_path):
    """The guard on the change above. UNPIVOT folds the columns in its IN list
    and leaves every other column of the table alone."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE s1 AS SELECT * FROM customer_demographics\n"
                 "UNPIVOT (val FOR metric IN (other_col, third_col));",
        "b.sql": "CREATE OR REPLACE TABLE final_published AS SELECT cm13 FROM s1;"})
    assert [g["prod"] for g in out["groups"]] == ["final_published"]
    assert [t["table"] for t in out["starTables"]] == ["s1"]


# ── how the file was saved ─────────────────────────────────────────────────
# A byte-order mark is invisible in every editor and lethal to a SQL parser. It
# lands on the FIRST statement of the file, which in a pipeline file is the one
# that names the source table -- so the statement that matters is the one that
# is lost, and the file still reports as read. Windows writes these by default:
# Notepad, PowerShell's Out-File, Excel's CSV export, every Office "save as".
BOM = b"\xef\xbb\xbf"
FIRST = "CREATE OR REPLACE TABLE stage1 AS SELECT cm13 FROM customer_demographics;"
SECOND = "CREATE OR REPLACE TABLE final_published AS SELECT cm13 FROM stage1;"


def test_a_byte_order_mark_does_not_eat_the_first_statement(tmp_path):
    out = scan(tmp_path, {"a.sql": BOM + FIRST.encode("utf-8"), "b.sql": SECOND})
    assert out["stats"]["couldNotRead"] == 0, out["unreadable"]
    assert [g["prod"] for g in out["groups"]] == ["final_published"]


def test_a_utf_16_file_is_read_rather_than_half_read(tmp_path):
    """PowerShell's ``>`` has written UTF-16-LE by default for twenty years.
    Read as UTF-8 the file comes back with a NUL between every letter."""
    out = scan(tmp_path, {"a.sql": FIRST.encode("utf-16"), "b.sql": SECOND})
    assert out["stats"]["couldNotRead"] == 0, out["unreadable"]
    assert [g["prod"] for g in out["groups"]] == ["final_published"]


def test_a_file_full_of_nul_bytes_is_said_out_loud(tmp_path):
    """The worst of the three. The parser swallowed the statement and said
    nothing: couldNotRead 0, no warning anywhere, risk none."""
    out = scan(tmp_path, {"a.sql": FIRST.encode("utf-8") + b"\x00\x00rubbish\x00"})
    assert out["stats"]["couldNotRead"] == 1, out["unreadable"]
    assert "NUL" in out["unreadable"][0]["reason"]


# ── "No impact" is the one word that must never cover a gap ────────────────
def test_risk_is_never_none_while_a_file_on_the_subject_could_not_be_read(tmp_path):
    """An EXECUTE IMMEDIATE whose target name is glued together at run time. The
    statement never exists as text anywhere, so nothing can read it -- and Ripple
    printed a green "No impact" over it. "I found nothing" and "I could not look"
    are not the same answer, however similar they look on screen.

    This used to be an EXECUTE IMMEDIATE holding the whole CREATE in ONE quoted
    string. That shape is now READ rather than reported -- see the tests below --
    so the guarantee is pinned here on the shape that genuinely cannot be read.
    """
    out = scan(tmp_path, {
        "a.sql": "EXECUTE IMMEDIATE 'CREATE OR REPLACE TABLE stage_' || env || "
                 "'_mid AS SELECT cm13 FROM customer_demographics';"})
    assert out["stats"]["couldNotRead"] == 1, out["unreadable"]
    assert out["risk"] == "unknown", out["risk"]


def test_a_clean_repository_still_says_no_impact(tmp_path):
    """The guard on the change above. A badge that says "not sure" on every scan
    ever run is a badge nobody reads."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE final_published AS SELECT other_col "
                 "FROM customer_demographics;"})
    assert out["stats"]["couldNotRead"] == 0
    assert out["risk"] == "none"


# ── the CREATE line, outside the SELECT ────────────────────────────────────
def test_a_partition_key_is_read(tmp_path):
    """A table partitioned by the very column being decommissioned returned NO
    usages at all -- the whole chain came back risk low, groups 0, couldNotRead
    0. Nothing published loses a column; the table simply stops being built,
    and everything under it serves data that is no longer refreshed."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE ds.mid PARTITION BY DATE(cm13)\n"
                 "AS SELECT other_col FROM ds.customer_demographics;",
        "b.sql": "CREATE OR REPLACE TABLE ds.final_published AS SELECT other_col FROM ds.mid;"})
    assert out["risk"] != "none"
    assert [s["prod"] for s in out["stopsLoading"]] == ["final_published"], out["stopsLoading"]


def test_a_cluster_key_is_read_too(tmp_path):
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE ds.mid CLUSTER BY cm13\n"
                 "AS SELECT other_col FROM ds.customer_demographics;",
        "b.sql": "CREATE OR REPLACE TABLE ds.final_published AS SELECT other_col FROM ds.mid;"})
    assert [s["prod"] for s in out["stopsLoading"]] == ["final_published"], out["stopsLoading"]


def test_a_bare_partition_column_is_read(tmp_path):
    """``PARTITION BY cm13`` with nothing round it parses as a bare identifier,
    not a column, so searching for columns finds nothing."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE ds.mid PARTITION BY cm13\n"
                 "AS SELECT other_col FROM ds.customer_demographics;",
        "b.sql": "CREATE OR REPLACE TABLE ds.final_published AS SELECT other_col FROM ds.mid;"})
    assert [s["prod"] for s in out["stopsLoading"]] == ["final_published"], out["stopsLoading"]


# ── a column named after a function ────────────────────────────────────────
PARENLESS = {
    "a.sql": "CREATE OR REPLACE TABLE stage_k AS SELECT current_date FROM customer_demographics;",
    "b.sql": "CREATE OR REPLACE TABLE final_published AS SELECT current_date FROM stage_k;",
}


def test_a_column_named_after_a_parenless_function_is_followed(tmp_path):
    """BigQuery lets CURRENT_DATE be written with no brackets, so a column of
    that name parses as a call and is invisible: risk none, found 0,
    nameInTables 0. Backticked, the very same scan reaches production."""
    out = scan(tmp_path, PARENLESS, attrs=("current_date",))
    assert [g["prod"] for g in out["groups"]] == ["final_published"]


def test_that_column_is_never_asserted_because_it_could_be_the_function(tmp_path):
    """Both readings are valid BigQuery and both are written the same way. So
    both are followed, and the row says the table is a guess."""
    out = scan(tmp_path, PARENLESS, attrs=("current_date",))
    rows = [r for g in out["groups"] for r in g["rows"]]
    assert rows and all(r["certain"] is False for r in rows), rows


def test_an_ordinary_use_of_the_function_is_left_alone(tmp_path):
    """The guard. ``WHERE dt = current_date`` is in a great many files, and a
    scan of an unrelated column must not be dragged into doubt by it."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE final_published AS SELECT cm13 "
                 "FROM customer_demographics WHERE dt = current_date;"})
    rows = [r for g in out["groups"] for r in g["rows"]]
    assert rows and all(r["certain"] is True for r in rows), rows


# ── a hole where the column list goes ──────────────────────────────────────
def test_a_placeholder_in_the_select_list_is_not_a_column(tmp_path):
    """A great many Airflow DAGs build SQL as f"SELECT {cols} FROM ...". Ripple
    read it as a column called ``cols``, believed the published table had
    exactly that one, and answered risk none, unreadable 0, couldNotRead 0 -- a
    clean, confident, complete zero."""
    out = scan(tmp_path, {
        "job.py": 'cols = "cm13, cm14"\n'
                  'sql = f"""CREATE OR REPLACE TABLE ds.final_published AS '
                  'SELECT {cols} FROM ds.customer_demographics"""\n'})
    assert [g["prod"] for g in out["groups"]] == ["final_published"]


def test_that_placeholder_is_not_described_as_a_select_star(tmp_path):
    """It carries columns nobody can see and names none of them, which is what
    a star does -- but the file does not say SELECT *, and a row that claims it
    does sends somebody to a line where no such statement is written."""
    out = scan(tmp_path, {
        "job.py": 'cols = "cm13, cm14"\n'
                  'sql = f"""CREATE OR REPLACE TABLE ds.final_published AS '
                  'SELECT {cols} FROM ds.customer_demographics"""\n'})
    star = out["starTables"]
    assert len(star) == 1 and star[0]["filledIn"], star
    rows = [r for g in out["groups"] for r in g["rows"]]
    assert all("SELECT *" not in r["logic"] for r in rows), [r["logic"] for r in rows]


# ── a SELECT written as a value, not as a source of rows ───────────────────
def test_an_alias_inside_a_scalar_subquery_is_not_the_output_name(tmp_path):
    """``c_alias`` exists only inside the brackets and is on no table anywhere.
    The real output name is peak_cm, which is what the next table reads -- so
    the chain went cold one hop early and reported no production impact."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE s1 AS\n"
                 "SELECT o.k, (SELECT MAX(d.cm13) AS c_alias FROM customer_demographics d "
                 "WHERE d.k = o.k) AS peak_cm\nFROM other_source o;",
        "b.sql": "CREATE OR REPLACE TABLE final_published AS SELECT k, peak_cm FROM s1;"})
    assert [g["prod"] for g in out["groups"]] == ["final_published"]


def test_an_alias_inside_an_in_subquery_does_not_invent_a_column(tmp_path):
    """The mirror of the same bug, over-reporting instead of under-reporting: a
    name written inside WHERE ... IN (SELECT cm13 AS c_alias ...) was published
    as a column of the table being built."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE s1 AS SELECT k FROM other_source\n"
                 "WHERE k IN (SELECT cm13 AS c_alias FROM customer_demographics);",
        "b.sql": "CREATE OR REPLACE TABLE final_published AS SELECT c_alias FROM s1;"})
    assert out["groups"] == [], "c_alias is not a column of s1"


def test_a_rename_inside_a_from_subquery_still_survives(tmp_path):
    """The guard. A subquery in FROM really does hand its columns to the query
    around it, and its renames really do reach the table being built."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE s1 AS SELECT mc FROM "
                 "(SELECT cm13 AS mc FROM customer_demographics);",
        "b.sql": "CREATE OR REPLACE TABLE final_published AS SELECT mc FROM s1;"})
    assert [g["prod"] for g in out["groups"]] == ["final_published"]


# ── a folder Ripple is told to skip ────────────────────────────────────────
def test_code_in_a_skipped_folder_is_named_beside_the_answer(tmp_path):
    """``target/`` is dbt's compiled output -- the SQL that actually runs. The
    count reached the repository screen and nothing else, so the scan came back
    clean with the reason on a screen nobody was looking at."""
    out = scan(tmp_path, {
        "target/compiled/a.sql": "CREATE OR REPLACE TABLE final_published AS "
                                 "SELECT cm13 FROM customer_demographics;"})
    assert out["skippedInFolders"] == ["target/compiled/a.sql"]
    assert "target" in out["skippedFolderNames"]


# ── SELECT * REPLACE names the column ──────────────────────────────────────
REPLACED = {
    "a.sql": "CREATE OR REPLACE TABLE stage_r AS "
             "SELECT * REPLACE(legacy_code AS cm13) FROM customer_demographics;",
    "b.sql": "CREATE OR REPLACE TABLE final_published AS SELECT cm13 FROM stage_r;",
}


def test_a_replaced_column_breaks_the_statement_that_names_it(tmp_path):
    """Ripple got the right answer for the wrong reason: the rename was
    followed, but nothing said the name is written down here, so the row read
    breaking false about a statement that stops compiling."""
    out = scan(tmp_path, REPLACED)
    rows = [r for e in out["reached"] for r in e["rows"] if r["file"] == "a.sql"]
    assert rows and rows[0]["breaking"] is True, rows
    assert "REPLACE" in rows[0]["logic"], rows[0]["logic"]


def test_a_replaced_column_stops_carrying_its_own_values_onward(tmp_path):
    """The output column of that name holds the replacement's value from here
    on. The original column reaches nothing past this statement -- but the
    table it builds does stop being refreshed."""
    out = scan(tmp_path, REPLACED)
    assert out["groups"] == []
    assert [s["prod"] for s in out["stopsLoading"]] == ["final_published"]
    assert out["starTables"] == [], "it is not carried by the star either"


# ── the line under the wildcard ────────────────────────────────────────────
SUFFIXED = {
    "a.sql": "CREATE OR REPLACE TABLE g_published AS SELECT cm13 FROM "
             "`p.ds.customer_demographics_*` WHERE _TABLE_SUFFIX = '20260101';",
}


def test_a_shard_the_query_never_reads_is_not_reported(tmp_path):
    """A shard from 1999 against a query pinned to one day in 2026 came back
    risk medium, breaking true, CERTAIN true -- with the predicate that
    contradicts it printed in the snippet underneath."""
    out = scan(tmp_path, SUFFIXED, table="customer_demographics_19991231")
    assert out["groups"] == []


def test_the_shard_the_query_does_read_is_still_reported(tmp_path):
    """The guard on the change above."""
    out = scan(tmp_path, SUFFIXED, table="customer_demographics_20260101")
    assert [g["prod"] for g in out["groups"]] == ["g_published"]


def test_a_range_of_shards_is_read_as_a_range(tmp_path):
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE g_published AS SELECT cm13 FROM "
                 "`p.ds.customer_demographics_*` WHERE _TABLE_SUFFIX BETWEEN "
                 "'20260101' AND '20260131';"}, table="customer_demographics_20260115")
    assert [g["prod"] for g in out["groups"]] == ["g_published"]


def test_a_suffix_filter_ripple_cannot_evaluate_hedges_rather_than_drops(tmp_path):
    """A parameter is not something a static reader can work out. Dropping the
    finding on a guess would trade an over-confident answer for a missing one."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE g_published AS SELECT cm13 FROM "
                 "`p.ds.customer_demographics_*` WHERE _TABLE_SUFFIX = @run_date;"},
        table="customer_demographics_19991231")
    rows = [r for g in out["groups"] for r in g["rows"]]
    assert rows and all(r["certain"] is False for r in rows), rows


def test_asking_about_the_family_itself_is_never_narrowed(tmp_path):
    """Somebody who typed the asterisk is asking about every shard, so no one
    suffix can be tested against the predicate."""
    out = scan(tmp_path, SUFFIXED, table="customer_demographics_*")
    assert [g["prod"] for g in out["groups"]] == ["g_published"]


# ── one table, two files that build it ─────────────────────────────────────
def test_a_table_built_in_two_files_is_said_out_loud(tmp_path):
    """The only finding reported came from a stale copy under archive/,
    presented with breaking true and certain true and the same wording as any
    live finding, while the live definition sat under "mentions only"."""
    out = scan(tmp_path, {
        "live/a.sql": "CREATE OR REPLACE TABLE ds.final_published AS "
                      "SELECT id FROM ds.customer_demographics;",
        "archive/old.sql": "CREATE OR REPLACE TABLE ds.final_published AS "
                           "SELECT cm13 FROM ds.customer_demographics;"})
    forked = out["twoDefinitions"]
    assert len(forked) == 1, forked
    assert forked[0]["table"] == "final_published"
    assert forked[0]["files"] == ["archive/old.sql", "live/a.sql"]


def test_one_table_built_in_one_file_says_nothing(tmp_path):
    """The guard. A warning printed on every scan is one nobody reads."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE ds.final_published AS "
                 "SELECT cm13 FROM ds.customer_demographics;"})
    assert out["twoDefinitions"] == []


def test_a_table_loaded_by_several_inserts_is_not_a_fork(tmp_path):
    """Several files adding rows to one table is ordinary. Only a CREATE that
    replaces the whole thing makes two definitions of it."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE ds.final_published AS "
                 "SELECT cm13 FROM ds.customer_demographics;",
        "b.sql": "INSERT INTO ds.final_published (cm13) "
                 "SELECT cm13 FROM ds.customer_demographics;"})
    assert out["twoDefinitions"] == []


# ── Dataform ───────────────────────────────────────────────────────────────
# Google's own tool for building BigQuery pipelines, and the likeliest thing in
# a BigQuery repository after dbt. A .sqlx file is an ordinary SELECT with a
# JavaScript ``config { }`` block on top. It was not opened, not counted and not
# mentioned: indexed False, risk none, prod [], with nothing anywhere recording
# that the file existed.
DATAFORM = {
    "definitions/mid.sqlx": 'config { type: "table" }\n\n'
                            'SELECT cm13 FROM ${ref("customer_demographics")}',
    "definitions/final_published.sqlx": 'config { type: "table" }\n\n'
                                        'SELECT cm13 FROM ${ref("mid")}',
}


def test_a_dataform_repository_reaches_its_published_table(tmp_path):
    out = scan(tmp_path, DATAFORM)
    assert [g["prod"] for g in out["groups"]] == ["final_published"]
    assert out["stats"]["couldNotRead"] == 0, out["unreadable"]


def test_a_dataform_model_says_where_its_name_came_from(tmp_path):
    out = scan(tmp_path, DATAFORM)
    assert {t["how"] for t in out["namedByFile"]} == {"Dataform"}


def test_dataform_pre_operations_are_read_as_the_sql_they_are(tmp_path):
    """config { } and js { } carry no lineage. pre_operations { } holds real
    SQL that runs before the model builds, so its brackets go and its contents
    stay."""
    _, _, parsed = build(tmp_path, {
        "definitions/mid.sqlx":
            'config { type: "incremental" }\n'
            'pre_operations {\n'
            '  DELETE FROM `p.d.staging_published` WHERE cm13 IS NULL\n'
            '}\n'
            'SELECT other_col FROM ${ref("customer_demographics")}'})
    targets = {s.target for s in parsed.statements}
    assert "d.staging_published" in targets, targets
    assert "mid" in targets, "the model itself is still named after its file"
    assert parsed.unreadable == [], parsed.unreadable


# ── Sibling CTEs: one WITH, one SELECT depth, several different tables ─────
# Every CTE of a single WITH sits at the same SELECT depth, and the projection
# map was built one bucket per depth. So the CTEs of one WITH were merged into
# a single map and applied in a single pass. Two separate clean wrong answers
# came out of that, and both of these ran before either was fixed.


def test_a_sibling_ctes_except_does_not_delete_an_unrelated_star(tmp_path):
    """``hits`` drops cm13 and never reads the scanned table at all. The column
    arrives through ``cust.*`` from a different table, so it really is in
    stage_p and the published table really does break.

    Before: risk low, groups [] -- the EXCEPT was applied to the whole level."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE stage_p AS\n"
                 "WITH cust AS (SELECT * FROM customer_demographics),\n"
                 "     hits AS (SELECT * EXCEPT (cm13) FROM web_events)\n"
                 "SELECT cust.*, hits.url FROM cust JOIN hits USING (k);",
        "b.sql": "CREATE OR REPLACE TABLE final_published AS "
                 "SELECT cm13 FROM stage_p WHERE cm13 IS NOT NULL;"})
    assert [g["prod"] for g in out["groups"]] == ["final_published"]
    assert out["risk"] != "none"


def test_the_only_star_dropping_a_column_still_stops_the_trail(tmp_path):
    """The guard on the test above. Where nothing else could be carrying the
    column, EXCEPT still ends the chain -- that is a shipped behaviour and the
    reason the rule is unanimity among stars rather than ignoring EXCEPT."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE stage_q AS "
                 "SELECT * EXCEPT (cm13) FROM customer_demographics;",
        "b.sql": "CREATE OR REPLACE TABLE final_published AS "
                 "SELECT cm13 FROM stage_q WHERE cm13 IS NOT NULL;"})
    assert [g["prod"] for g in out["groups"]] == []


def test_every_star_dropping_a_column_still_stops_the_trail(tmp_path):
    """Two stars, both dropping it. Unanimous, so it is dropped."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE stage_u AS\n"
                 "WITH one AS (SELECT * EXCEPT (cm13) FROM customer_demographics),\n"
                 "     two AS (SELECT * EXCEPT (cm13) FROM customer_demographics)\n"
                 "SELECT one.*, two.k AS k2 FROM one JOIN two USING (k);",
        "b.sql": "CREATE OR REPLACE TABLE final_published AS "
                 "SELECT cm13 FROM stage_u WHERE cm13 IS NOT NULL;"})
    assert [g["prod"] for g in out["groups"]] == []


def test_a_rename_fed_by_a_rename_in_the_same_with_is_followed(tmp_path):
    """Three CTEs in a row, each renaming what the last one made. The level was
    read once, so cm13 became customer_code and stopped -- and the published
    table reads cust_code, a name Ripple never said out loud.

    Before: risk medium, groups [], recorded alias 'cm13'."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE stage_c AS\n"
                 "WITH src AS (SELECT k, cm13 FROM customer_demographics),\n"
                 "     renamed AS (SELECT k, cm13 AS customer_code FROM src),\n"
                 "     final AS (SELECT k, customer_code AS cust_code FROM renamed)\n"
                 "SELECT * FROM final;",
        "b.sql": "CREATE OR REPLACE TABLE final_published AS "
                 "SELECT cust_code FROM stage_c WHERE cust_code IS NOT NULL;"})
    assert [g["prod"] for g in out["groups"]] == ["final_published"]


def test_a_chain_of_renames_keeps_the_untouched_name_first(tmp_path):
    """The name shown on screen is still the one carried through unchanged, not
    whichever the fixpoint happened to reach last."""
    _, _, parsed = build(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE stage_c AS\n"
                 "WITH src AS (SELECT k, cm13 FROM customer_demographics),\n"
                 "     renamed AS (SELECT k, cm13 AS customer_code FROM src)\n"
                 "SELECT * FROM renamed;"})
    from ripple.scanner.sqlread import output_names
    stmt = [s for s in parsed.statements if s.target == "stage_c"][0]
    names = output_names(stmt, "cm13")
    assert names[0].lower() == "cm13", names
    assert "customer_code" in names, names


# ── One alias, two scopes ──────────────────────────────────────────────────
# The alias map was flat across a whole statement, so an alias re-bound inside
# an EXISTS decided what the same letter meant in the outer WHERE.


def test_an_alias_rebound_inside_exists_does_not_steal_the_outer_filter(tmp_path):
    """``t`` is a subquery outside and legacy_dim inside. The breaking
    ``WHERE t.cm13`` belongs to the subquery, which reads the scanned table.

    Before: risk low, breaking false -- Ripple reached final_published through
    the star but said nothing failed, over a change that stops this statement
    compiling."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE final_published AS\n"
                 "SELECT t.k, o.amount\n"
                 "FROM (SELECT * FROM customer_demographics) t\n"
                 "JOIN orders o ON o.k = t.k\n"
                 "WHERE t.cm13 = 'A'\n"
                 "  AND EXISTS (SELECT 1 FROM legacy_dim t WHERE t.k = o.k);"})
    assert [g["prod"] for g in out["groups"]] == ["final_published"]
    assert out["stats"]["breakingUsages"] == 1, out["stats"]
    assert out["risk"] != "low"


def test_a_column_that_really_is_another_tables_is_still_ruled_out(tmp_path):
    """The guard. Scoping the alias map must not make every qualifier
    'unknown' -- a name plainly attributed to another table is still not this
    table's, which is what keeps join keys off every finding in the warehouse."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE final_published AS\n"
                 "SELECT o.k FROM orders o\n"
                 "JOIN legacy_dim d ON d.k = o.k\n"
                 "WHERE d.cm13 = 'A';"})
    assert [g["prod"] for g in out["groups"]] == [], out["groups"]


def test_a_subquery_alias_carries_the_table_it_reads(tmp_path):
    """The half of the fix that is not about shadowing: a subquery alias was
    bound to nothing at all, so every ``t.col`` on one was 'an alias from
    somewhere we cannot see'."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE final_published AS\n"
                 "SELECT t.k FROM (SELECT * FROM customer_demographics) t\n"
                 "WHERE t.cm13 = 'A';"})
    assert out["stats"]["breakingUsages"] == 1, out["stats"]


# ── A STRUCT built here and unpacked by field one hop later ────────────────


def test_a_struct_field_read_downstream_keeps_the_trail(tmp_path):
    """The table has one column, payload. The next statement reads
    payload.code -- both in its select list and in its WHERE -- so a change to
    cm13 breaks the published table.

    Before: risk medium, groups [], trail ended at the struct."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE stage_r AS\n"
                 "SELECT k, STRUCT(cm13 AS code, seg AS segment) AS payload\n"
                 "FROM customer_demographics;",
        "b.sql": "CREATE OR REPLACE TABLE final_published AS\n"
                 "SELECT k, payload.code AS customer_code FROM stage_r\n"
                 "WHERE payload.code IS NOT NULL;"})
    assert [g["prod"] for g in out["groups"]] == ["final_published"], out["groups"]


def test_a_struct_field_is_not_published_under_its_bare_name(tmp_path):
    """The guard, and the reason the field is carried dotted. stage_s has no
    column called code, so a bare 'code' downstream is a different column on a
    different table and inventing that link would be worse than losing it."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE stage_s AS\n"
                 "SELECT k, STRUCT(cm13 AS code) AS payload\n"
                 "FROM customer_demographics;",
        "b.sql": "CREATE OR REPLACE TABLE final_published AS SELECT k, code FROM stage_s;"})
    assert [g["prod"] for g in out["groups"]] == [], out["groups"]


def test_a_struct_read_whole_downstream_is_still_followed(tmp_path):
    """The wrapper's own name is carried alongside the field names, not
    replaced by them."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE stage_w AS\n"
                 "SELECT k, STRUCT(cm13 AS code) AS payload\n"
                 "FROM customer_demographics;",
        "b.sql": "CREATE OR REPLACE TABLE final_published AS "
                 "SELECT k, payload FROM stage_w;"})
    assert [g["prod"] for g in out["groups"]] == ["final_published"], out["groups"]


# -- Airflow's own config shape, and bq's own command line ------------------
# Only ONE way of writing a BigQuery destination ever reached the published
# table: quoted AND dot-separated. Every other spelling of the very same
# destination gave "the name appears, but no lineage to a production table".


def test_an_airflow_nested_config_dict_names_its_destination(tmp_path):
    """BigQueryInsertJobOperator hands BigQuery its API shape: camelCase, and
    the name split across projectId, datasetId and tableId."""
    out = scan(tmp_path, {"dags/load.py": '''
job = BigQueryInsertJobOperator(
    task_id="load_final",
    configuration={
        "query": {
            "query": "SELECT id, cm13 FROM customer_demographics",
            "destinationTable": {"projectId": "prj", "datasetId": "marts",
                                 "tableId": "final_published"},
            "writeDisposition": "WRITE_TRUNCATE",
        }
    },
)
'''})
    assert [g["prod"] for g in out["groups"]] == ["final_published"], out["groups"]


def test_a_source_table_in_the_same_config_is_not_read_as_a_write(tmp_path):
    """The guard. tableId also appears under sourceTable, and reading that
    would turn a READ into a write and invent a chain nobody wrote."""
    out = scan(tmp_path, {"dags/copy.py": '''
job = BigQueryToBigQueryOperator(
    task_id="copy",
    configuration={"copy": {
        "sourceTable": {"projectId": "prj", "datasetId": "raw",
                        "tableId": "final_published"},
    }},
)
sql = "SELECT id, cm13 FROM customer_demographics"
'''})
    assert [g["prod"] for g in out["groups"]] == [], out["groups"]


def test_the_bq_command_line_colon_separator_is_read(tmp_path):
    """bq's OWN separator between project and dataset is a colon, and a shell
    command quotes nothing."""
    out = scan(tmp_path, {"load.sh": """#!/bin/bash
bq query --destination_table=prj:marts.final_published --use_legacy_sql=false \
  'SELECT id, cm13 FROM customer_demographics'
"""})
    assert [g["prod"] for g in out["groups"]] == ["final_published"], out["groups"]


def test_an_unquoted_destination_that_is_not_a_name_invents_nothing(tmp_path):
    """The guard on reading unquoted values at all. A qualified name is
    required, so destination_table=None does not become a published table."""
    out = scan(tmp_path, {"dags/none.py": '''
run(destination_table=None, sql="SELECT id, cm13 FROM customer_demographics")
run(destination_table=chosen_target, sql="SELECT id FROM customer_demographics")
'''})
    assert [g["prod"] for g in out["groups"]] == [], out["groups"]
    assert "None" not in str(out["groups"]) and "None" not in str(out["reached"])


# -- A value passed through a script variable, not through a table ----------
# A BigQuery script passes values from statement to statement in variables as
# well as in tables. Both halves were read as statements with nothing to do
# with each other, and both shapes came back with no production table at all.


def test_a_for_loop_body_that_writes_the_published_table_is_followed(tmp_path):
    """The loop header was rewritten to a read with no target and the INSERT in
    the body had no source, so the two halves of one statement never joined.

    Before: groups [], while the finding's own text said the column went 'into
    the next table' and named no next table."""
    out = scan(tmp_path, {
        "a.sql": "FOR rec IN (SELECT id, cm13 AS seg FROM customer_demographics) DO\n"
                 "  INSERT INTO final_published (id, seg) VALUES (rec.id, rec.seg);\n"
                 "END FOR;\n"})
    assert [g["prod"] for g in out["groups"]] == ["final_published"], out["groups"]


def test_a_loop_row_variable_belongs_to_its_own_file(tmp_path):
    """The guard. Two files both looping over a variable called rec must not
    join up -- the variable is gone at the end of its file, exactly like a
    temporary table."""
    out = scan(tmp_path, {
        "a.sql": "FOR rec IN (SELECT id, cm13 AS seg FROM customer_demographics) DO\n"
                 "  INSERT INTO staging_a (id, seg) VALUES (rec.id, rec.seg);\n"
                 "END FOR;\n",
        "b.sql": "FOR rec IN (SELECT id, other AS seg FROM unrelated_source) DO\n"
                 "  INSERT INTO final_published (id, seg) VALUES (rec.id, rec.seg);\n"
                 "END FOR;\n"})
    assert [g["prod"] for g in out["groups"]] == [], out["groups"]


def test_a_while_loop_still_keeps_its_read(tmp_path):
    """WHILE has no row variable. It was always read as a plain read of what it
    tests, and it still is."""
    _, _, parsed = build(tmp_path, {
        "a.sql": "WHILE (SELECT COUNT(*) FROM customer_demographics WHERE cm13 IS NULL) > 0 DO\n"
                 "  SELECT 1;\n"
                 "END WHILE;\n"})
    assert any("customer_demographics" in s.sources for s in parsed.statements), \
        [s.sources for s in parsed.statements]
    assert parsed.unreadable == [], parsed.unreadable


def test_a_declared_watermark_reaches_the_table_it_chooses_the_rows_of(tmp_path):
    """final_published's whole row set is chosen by cutoff, and cutoff IS
    MAX(cm13). Removing the column stops this script compiling.

    Before: groups [], filed as a dead end two lines above the CREATE."""
    out = scan(tmp_path, {
        "a.sql": "DECLARE cutoff DATE DEFAULT (SELECT MAX(cm13) FROM customer_demographics);\n"
                 "CREATE OR REPLACE TABLE final_published AS\n"
                 "SELECT order_id, amount FROM orders WHERE order_date > cutoff;\n"})
    assert [g["prod"] for g in out["groups"]] == ["final_published"], out["groups"]
    assert out["risk"] != "none"


def test_a_set_watermark_is_read_the_same_way_as_a_declare(tmp_path):
    """The same guard written the other way. DECLARE ... DEFAULT and SET are one
    thing, and two spellings of one thing that disagree IS the bug."""
    out = scan(tmp_path, {
        "a.sql": "DECLARE cutoff DATE;\n"
                 "SET cutoff = (SELECT MAX(cm13) FROM customer_demographics);\n"
                 "CREATE OR REPLACE TABLE final_published AS\n"
                 "SELECT order_id, amount FROM orders WHERE order_date > cutoff;\n"})
    assert [g["prod"] for g in out["groups"]] == ["final_published"], out["groups"]


def test_a_declared_counter_is_not_given_a_table_of_its_own(tmp_path):
    """The guard. Only a variable filled FROM A QUERY can be followed. Giving
    every loop counter a name on the screen would fill it with dead ends."""
    _, _, parsed = build(tmp_path, {
        "a.sql": "DECLARE i INT64 DEFAULT 0;\n"
                 "CREATE OR REPLACE TABLE final_published AS "
                 "SELECT cm13 FROM customer_demographics;\n"})
    assert [s.target for s in parsed.statements if s.script_var] == [], \
        [(s.target, s.script_var) for s in parsed.statements]


def test_a_variable_belongs_to_its_own_file(tmp_path):
    """The guard. cutoff in one file is not cutoff in another."""
    out = scan(tmp_path, {
        "a.sql": "DECLARE cutoff DATE DEFAULT (SELECT MAX(cm13) FROM customer_demographics);\n"
                 "CREATE OR REPLACE TABLE staging_a AS SELECT 1 AS x WHERE TRUE;\n",
        "b.sql": "CREATE OR REPLACE TABLE final_published AS\n"
                 "SELECT order_id FROM orders WHERE order_date > cutoff;\n"})
    assert [g["prod"] for g in out["groups"]] == [], out["groups"]


# -- A file type Ripple does not open at all --------------------------------
# RepoIndex counted these all along. The count reached the REPOSITORY screen and
# nothing else, so a chain whose middle hop sat in a notebook printed "the name
# appears, but no lineage to a production table" with nothing beside the answer
# saying a file had been passed over.
import json as _json

_NOTEBOOK = _json.dumps({"cells": [{"cell_type": "code", "source": [
    "q = '''CREATE OR REPLACE TABLE final_published AS "
    "SELECT id, cm13 FROM stage_n'''\n"]}]})


def test_an_unopened_file_type_is_named_beside_the_answer(tmp_path):
    """The caveat belongs on the same screen as the answer it qualifies."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE stage_n AS "
                 "SELECT id, cm13 FROM customer_demographics;",
        "mid.ipynb": _NOTEBOOK})
    assert out["fileTypesUnopened"] == [{"ext": ".ipynb", "count": 1}], \
        out["fileTypesUnopened"]
    assert out["coverage"]["complete"] is False
    assert any("does not open" in g["what"] for g in out["coverage"]["gaps"]), \
        out["coverage"]["gaps"]


def test_nothing_found_over_an_unopened_file_type_is_not_no_impact(tmp_path):
    """"I found nothing" and "I could not look" are not the same answer. With a
    whole file type unread, Ripple has not earned a confident none."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE t AS SELECT other FROM somewhere;",
        "mid.ipynb": _NOTEBOOK})
    assert out["risk"] == "unknown", out["risk"]


def test_a_readme_does_not_cry_wolf_on_every_scan(tmp_path):
    """The guard, and the whole reason the list is of types that are KNOWN not
    to be code. Every repository has a README. A warning printed over every
    scan is one nobody reads, and it would take "no impact" with it."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE t AS SELECT other FROM somewhere;",
        "README.md": "# The pipeline\n\nNotes.\n",
        "LICENSE.txt": "MIT\n",
        "logo.png": "not really a png\n"})
    assert out["fileTypesUnopened"] == [], out["fileTypesUnopened"]
    assert out["risk"] == "none", out["risk"]
    assert out["coverage"]["complete"] is True


def test_an_extension_ripple_has_never_heard_of_counts(tmp_path):
    """Written as a list of what is NOT code on purpose: a type nobody thought
    of is a gap by default, because that is how a middle hop goes missing."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE t AS SELECT other FROM somewhere;",
        "job.wibble": "CREATE OR REPLACE TABLE final_published AS SELECT cm13 FROM x;"})
    assert [t["ext"] for t in out["fileTypesUnopened"]] == [".wibble"], \
        out["fileTypesUnopened"]
    assert out["risk"] == "unknown"


def test_the_letter_does_not_say_proceed_over_an_unopened_file_type(tmp_path):
    """"Please proceed as planned" is the most consequential sentence this tool
    writes, and it is only ever sent over a genuinely complete clean scan."""
    from ripple import narrative
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE t AS SELECT other FROM somewhere;",
        "mid.ipynb": _NOTEBOOK})
    vals = {"pocName": "Priya Raman",
            "upstream": [{"table": "customer_demographics", "attrs": ["cm13"]}]}
    summary = narrative.summarise(out, vals)
    body = narrative.draft_reply(out, vals, summary)["body"]
    assert "proceed as planned" not in body.lower(), body
    assert "not confirming no impact yet" in body.lower(), body
    # ... and the summary beside it names the file type by its own extension,
    # so nobody has to go to another screen to find out what was missed.
    assert "does not open" in summary["narrative"].lower(), summary["narrative"]
    assert ".ipynb" in summary["narrative"], summary["narrative"]


# -- A query kept as a template, and a query kept as a shell argument --------


def test_a_templated_query_file_is_read_as_the_sql_it_is(tmp_path):
    """load_final.sql.j2. Python calls that suffix '.j2', so the file was never
    opened -- and the 'runs the SQL in X' warning could not fire either, because
    that only matched names ending '.sql'. A double miss, which is what made it
    silent."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE stage_j AS "
                 "SELECT id, cm13 FROM customer_demographics;",
        "load_final.sql.j2": "CREATE OR REPLACE TABLE {{ target }}.final_published AS "
                             "SELECT id, cm13 FROM stage_j;",
        "run.py": 'render("load_final.sql.j2")\n'})
    assert [g["prod"] for g in out["groups"]] == ["final_published"], out["groups"]


def test_a_backup_of_a_query_is_not_read_as_a_live_one(tmp_path):
    """The guard. Only a known template suffix counts. Reading anything at all
    past a .sql would take load_final.sql.bak with it, and a backup read as a
    live file turns into 'this table is built in two files'."""
    out = scan(tmp_path, {
        "load_final.sql": "CREATE OR REPLACE TABLE final_published AS "
                          "SELECT cm13 FROM customer_demographics;",
        "load_final.sql.bak": "CREATE OR REPLACE TABLE final_published AS "
                              "SELECT cm13 FROM customer_demographics;"})
    assert out["twoDefinitions"] == [], out["twoDefinitions"]


def test_a_multi_line_quoted_query_beside_a_heredoc_is_read(tmp_path):
    """A shell leaves a single-quoted string alone, so a query written across
    several lines as one argument is every bit as ordinary as a heredoc. The
    string miner refuses newlines, so nothing mined this at all."""
    out = scan(tmp_path, {"two.sh": """#!/bin/bash
bq query --use_legacy_sql=false 'CREATE OR REPLACE TABLE final_published AS
SELECT id, cm13 FROM customer_demographics'

bq query --use_legacy_sql=false <<EOF
CREATE OR REPLACE TABLE other_published AS SELECT id, zz9 FROM some_other_table
EOF
"""})
    assert [g["prod"] for g in out["groups"]] == ["final_published"], out["groups"]
    assert out["stats"]["couldNotRead"] == 0, out["unreadable"]


def test_an_apostrophe_in_a_shell_comment_does_not_mine_anything(tmp_path):
    """The guard, and the reason this is anchored on a command that RUNS SQL
    rather than on the quote character. One 'don't' in a comment must not
    swallow the rest of the file."""
    _, _, parsed = build(tmp_path, {"job.sh": """#!/bin/bash
# don't run this by hand, the scheduler owns it
echo "starting"
bq query --use_legacy_sql=false 'CREATE OR REPLACE TABLE final_published AS
SELECT id, cm13 FROM customer_demographics'
"""})
    targets = {s.target for s in parsed.statements}
    assert "final_published" in targets, targets
    assert parsed.unreadable == [], parsed.unreadable


def test_a_one_line_shell_query_is_not_counted_twice(tmp_path):
    """The guard on adding a second miner over the same text."""
    _, _, parsed = build(tmp_path, {
        "one.sh": "#!/bin/bash\nbq query --use_legacy_sql=false "
                  "'CREATE OR REPLACE TABLE final_published AS SELECT cm13 "
                  "FROM customer_demographics'\n"})
    built = [s for s in parsed.statements if s.target == "final_published"]
    assert len(built) == 1, [s.target for s in parsed.statements]


# -- a temp table handed to a procedure CALLed in the same script -----------
# A CALL runs in the SAME BigQuery session as the line above it, so a TEMP table
# the caller has just built IS visible inside the procedure. The per-file fence
# renamed the caller's side only, the two names stopped matching, and the trail
# died on the temp table -- with the file that really breaks filed under "the
# name appears, but no lineage to a production table".
PROC_CALL = {
    "a.sql": "CREATE TEMP TABLE stg AS SELECT id, cm13 FROM customer_demographics;\n"
             "CALL ds.publish_it();",
    "b.sql": "CREATE OR REPLACE PROCEDURE ds.publish_it()\n"
             "BEGIN\n"
             "  CREATE OR REPLACE TABLE final_published AS SELECT id, cm13 FROM stg;\n"
             "END;",
}


def test_a_temp_table_crosses_a_call_into_the_procedure_that_reads_it(tmp_path):
    out = scan(tmp_path, PROC_CALL)
    assert [g["prod"] for g in out["groups"]] == ["final_published"], out["reached"]
    assert out["mentionsOnly"] == [], out["mentionsOnly"]


def test_the_fence_marker_never_goes_on_screen(tmp_path):
    """The scope name is Ripple's own bookkeeping. Anybody sent to look for a
    table called #A_SQL.stg would find no such thing written anywhere."""
    out = scan(tmp_path, PROC_CALL)
    assert "#" not in repr(out), "the fence name reached the payload"


def test_a_one_line_procedure_body_is_read(tmp_path):
    """Found underneath the defect above. BEGIN with the body on the SAME line
    was not scripting the reader recognised, so the whole procedure fell out as
    one unreadable Command -- and the table it builds was known nowhere."""
    out = scan(tmp_path, {
        "a.sql": "CREATE TEMP TABLE stg AS SELECT id, cm13 FROM customer_demographics;\n"
                 "CALL ds.publish_it();",
        "b.sql": "CREATE OR REPLACE PROCEDURE ds.publish_it()\n"
                 "BEGIN CREATE OR REPLACE TABLE final_published AS "
                 "SELECT id, cm13 FROM stg; END;"})
    assert [g["prod"] for g in out["groups"]] == ["final_published"], out["groups"]


def test_the_fence_still_holds_where_nothing_calls_anything(tmp_path):
    """The guard. Take the CALL away and the two files are two sessions again."""
    out = scan(tmp_path, {
        "a.sql": "CREATE TEMP TABLE stg AS SELECT id, cm13 FROM customer_demographics;",
        "b.sql": "CREATE OR REPLACE PROCEDURE ds.publish_it()\nBEGIN\n"
                 "  CREATE OR REPLACE TABLE final_published AS SELECT id, cm13 FROM stg;\n"
                 "END;"})
    assert [g["prod"] for g in out["groups"]] == [], out["groups"]


def test_two_scripts_calling_two_procedures_do_not_share_their_temp_tables(tmp_path):
    """The reason the fence exists, one CALL further along. Both scripts build a
    ``stg``; only the one fed by customer_demographics may appear."""
    out = scan(tmp_path, {
        "a.sql": "CREATE TEMP TABLE stg AS SELECT id, cm13 FROM customer_demographics;\n"
                 "CALL ds.pub_a();",
        "z.sql": "CREATE TEMP TABLE stg AS SELECT id, other FROM unrelated_table;\n"
                 "CALL ds.pub_z();",
        "pa.sql": "CREATE OR REPLACE PROCEDURE ds.pub_a()\nBEGIN\n"
                  "  CREATE OR REPLACE TABLE a_published AS SELECT id, cm13 FROM stg;\nEND;",
        "pz.sql": "CREATE OR REPLACE PROCEDURE ds.pub_z()\nBEGIN\n"
                  "  CREATE OR REPLACE TABLE z_published AS SELECT id, other FROM stg;\nEND;"})
    assert [g["prod"] for g in out["groups"]] == ["a_published"], out["groups"]
    assert "z_published" not in repr(out)


def test_two_scripts_calling_the_same_procedure_are_both_followed(tmp_path):
    """Ripple cannot tell which caller's rows the procedure is running over, so
    it follows BOTH rather than picking one. A spare row is dismissed by opening
    the file; a lost chain is invisible."""
    out = scan(tmp_path, {
        "a.sql": "CREATE TEMP TABLE stg AS SELECT id, cm13 FROM customer_demographics;\n"
                 "CALL ds.pub();",
        "z.sql": "CREATE TEMP TABLE stg AS SELECT id, other FROM unrelated_table;\n"
                 "CALL ds.pub();",
        "p.sql": "CREATE OR REPLACE PROCEDURE ds.pub()\nBEGIN\n"
                 "  CREATE OR REPLACE TABLE both_published AS SELECT id, cm13 FROM stg;\nEND;"})
    assert [g["prod"] for g in out["groups"]] == ["both_published"], out["groups"]


def test_a_real_table_inside_a_procedure_is_not_taken_for_a_temp_one(tmp_path):
    """The guard on the widening. A name the SQL qualified is a real table that
    happens to share a short name with somebody's temporary one."""
    out = scan(tmp_path, {
        "a.sql": "CREATE TEMP TABLE stg AS SELECT id, cm13 FROM customer_demographics;\n"
                 "CALL ds.pub();",
        "p.sql": "CREATE OR REPLACE PROCEDURE ds.pub()\nBEGIN\n"
                 "  CREATE OR REPLACE TABLE final_published AS SELECT id, cm13 FROM warehouse.stg;\n"
                 "END;"})
    assert [g["prod"] for g in out["groups"]] == [], out["groups"]


def test_a_temp_table_built_inside_a_procedure_reaches_its_caller(tmp_path):
    """The same pair read the other way round: the procedure builds the temp
    table and the script that called it reads it."""
    out = scan(tmp_path, {
        "a.sql": "CALL ds.pub();\n"
                 "CREATE OR REPLACE TABLE tail_published AS SELECT id, cm13 FROM stg;",
        "p.sql": "CREATE OR REPLACE PROCEDURE ds.pub()\nBEGIN\n"
                 "  CREATE TEMP TABLE stg AS SELECT id, cm13 FROM customer_demographics;\nEND;"})
    assert [g["prod"] for g in out["groups"]] == ["tail_published"], out["groups"]


def test_a_call_to_a_procedure_that_is_not_in_the_repository_reports_nothing(tmp_path):
    """The guard on noise. Every real pipeline is full of CALLs to procedures
    that live somewhere else, and a gap reported for each of them would bury the
    one list Ripple has for admitting what it missed."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE final_published AS "
                 "SELECT cm13 FROM customer_demographics;\n"
                 "CALL ds.something_defined_elsewhere();"})
    assert out["stats"]["couldNotRead"] == 0, out["unreadable"]


# ── the guards the round-four hunt earned ──────────────────────────────────
# Everything this round widened -- the rename fixpoint, the star vote, the CALL
# edge, the scoped alias map, the script variable -- can only be trusted for as
# long as it still refuses a chain that is not there.


def test_a_long_chain_of_renames_in_one_with_is_followed_to_the_end(tmp_path):
    """Six renames, all at one SELECT depth. The fixpoint has to walk the whole
    way, not one step and not to its own cap."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE stage_x AS WITH\n"
                 " c0 AS (SELECT cm13 AS n1 FROM customer_demographics),\n"
                 " c1 AS (SELECT n1 AS n2 FROM c0),\n"
                 " c2 AS (SELECT n2 AS n3 FROM c1),\n"
                 " c3 AS (SELECT n3 AS n4 FROM c2),\n"
                 " c4 AS (SELECT n4 AS n5 FROM c3),\n"
                 " c5 AS (SELECT n5 AS n6 FROM c4)\n"
                 "SELECT n6 FROM c5;",
        "b.sql": "CREATE OR REPLACE TABLE final_published AS SELECT n6 FROM stage_x;"})
    assert [g["prod"] for g in out["groups"]] == ["final_published"], out["groups"]


def test_a_rename_cycle_in_one_with_terminates(tmp_path):
    """a becomes b becomes a. The fixpoint grows a bounded set, so this ends --
    but it is pinned, because a hang here would look exactly like a slow scan."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE stage_x AS WITH\n"
                 " p AS (SELECT cm13 AS a FROM customer_demographics),\n"
                 " q AS (SELECT a AS b FROM p),\n"
                 " r AS (SELECT b AS a FROM q)\n"
                 "SELECT a FROM r;",
        "b.sql": "CREATE OR REPLACE TABLE final_published AS SELECT a FROM stage_x;"})
    assert [g["prod"] for g in out["groups"]] == ["final_published"], out["groups"]


def test_a_loop_variable_named_like_the_column_invents_nothing(tmp_path):
    """The guard on binding script variables by name. A loop row called cm13 is
    a row, not the column being scanned."""
    out = scan(tmp_path, {
        "a.sql": "FOR cm13 IN (SELECT x FROM unrelated_source) DO\n"
                 "  INSERT INTO final_published (x) VALUES (cm13.x);\nEND FOR;\n"
                 "CREATE OR REPLACE TABLE other_tbl AS "
                 "SELECT cm13 FROM customer_demographics;"})
    assert [g["prod"] for g in out["groups"]] == [], out["groups"]


def test_a_declared_variable_named_like_the_column_invents_nothing(tmp_path):
    """The same guard for a scalar."""
    out = scan(tmp_path, {
        "a.sql": "DECLARE cm13 DATE DEFAULT (SELECT MAX(x) FROM unrelated_source);\n"
                 "CREATE OR REPLACE TABLE final_published AS SELECT y FROM orders "
                 "WHERE dt > cm13;"})
    assert [g["prod"] for g in out["groups"]] == [], out["groups"]


def test_a_script_variable_works_wherever_it_is_written_in_the_file(tmp_path):
    """The DECLARE below the statement that reads it. BigQuery hoists nothing,
    but Ripple reads the file as a whole and the fence is per file, so the order
    the two are written in must not decide whether the chain is found."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE final_published AS SELECT y FROM orders "
                 "WHERE dt > cutoff;\n"
                 "DECLARE cutoff DATE DEFAULT (SELECT MAX(cm13) FROM customer_demographics);"})
    assert [g["prod"] for g in out["groups"]] == ["final_published"], out["groups"]


def test_two_temp_tables_and_one_call_are_both_hops(tmp_path):
    """The caller builds one temp table, the procedure builds a second out of
    it, and the caller reads that. Both directions of the CALL edge at once."""
    out = scan(tmp_path, {
        "a.sql": "CREATE TEMP TABLE stg AS SELECT k, cm13 FROM customer_demographics;\n"
                 "CALL ds.p();\n"
                 "CREATE OR REPLACE TABLE final_published AS SELECT cm13 FROM stg2;",
        "b.sql": "CREATE OR REPLACE PROCEDURE ds.p()\nBEGIN\n"
                 "  CREATE TEMP TABLE stg2 AS SELECT k, cm13 FROM stg;\nEND;"})
    assert [g["prod"] for g in out["groups"]] == ["final_published"], out["groups"]


def test_a_loop_body_that_writes_only_literals_carries_nothing(tmp_path):
    """The guard on reading an INSERT's VALUES. Nothing of the column reaches
    the table, so nothing may be reported as though it did."""
    out = scan(tmp_path, {
        "a.sql": "FOR rec IN (SELECT k, cm13 FROM customer_demographics) DO\n"
                 "  INSERT INTO final_published (k, seg) VALUES (1, 'fixed');\nEND FOR;"})
    assert [g["prod"] for g in out["groups"]] == [], out["groups"]


def test_a_non_sql_quoted_shell_argument_is_not_mined(tmp_path):
    """The guard on the shell argument miner. A quoted argument that is not SQL
    must not become a statement."""
    _, _, parsed = build(tmp_path, {
        "j.sh": "#!/bin/bash\npsql -c 'this is a sentence about customer_demographics "
                "and cm13 that goes on for quite a while but is not a query'\n"})
    assert [s.target for s in parsed.statements] == [], \
        [s.target for s in parsed.statements]


def test_bigquery_pipe_syntax_is_followed(tmp_path):
    """BigQuery's newer spelling of the same query. Pinned because a dialect
    that stops parsing is silent -- the file reads as empty, not as broken."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE stage_x AS\nFROM customer_demographics\n"
                 "|> SELECT k, cm13;",
        "b.sql": "CREATE OR REPLACE TABLE final_published AS SELECT cm13 FROM stage_x;"})
    assert [g["prod"] for g in out["groups"]] == ["final_published"], out["groups"]


# ── a UNION names its output from the FIRST branch, by position ────────────
# The same table, built by the same two SELECTs, with the two written the other
# way round. SQL takes the output column names from the branch written first, so
# the SECOND branch's columns are published under the FIRST branch's names -- by
# position, never by their own name.
#
# Measured before this: with the traced column in the first branch the published
# table was found; move the same SELECT below the UNION ALL and the answer became
# "the chain ends at stage_u", `prod []`, no production table affected. Nothing
# on any screen said a branch had been read under the wrong name, because as far
# as the trail knew there was no branch -- the column simply stopped existing.
#
# A current table UNION'd with an archive or legacy one is how half the staging
# layer of a warehouse is built, and which of the two is written first is
# arbitrary. So this was a coin flip on whether a real break was reported at all.
UNION_SECOND = {
    "a.sql": """
        CREATE OR REPLACE TABLE stage_u AS
        SELECT id, other_col AS market FROM legacy_demographics
        UNION ALL
        SELECT id, cm13 FROM customer_demographics;
    """,
    "b.sql": """
        CREATE OR REPLACE TABLE union_published AS
        SELECT market FROM stage_u;
    """,
}
UNION_FIRST = {
    "a.sql": """
        CREATE OR REPLACE TABLE stage_u AS
        SELECT id, cm13 AS market FROM customer_demographics
        UNION ALL
        SELECT id, other_col FROM legacy_demographics;
    """,
    "b.sql": """
        CREATE OR REPLACE TABLE union_published AS
        SELECT market FROM stage_u;
    """,
}


def test_a_union_branch_is_published_under_the_first_branchs_names(tmp_path):
    """The reproduction. The column is in the second branch and reaches
    production exactly as it does from the first."""
    out = scan(tmp_path, UNION_SECOND, production="_published")
    assert [g["prod"] for g in out["groups"]] == ["union_published"], out["groups"]
    assert out["stats"]["productionTables"] == 1
    assert out["risk"] != "none"


def test_which_union_branch_it_is_written_in_changes_nothing(tmp_path):
    """The two spellings of one table have to give the same answer. This is the
    test that would have caught it: each half passed on its own for months."""
    first = scan(tmp_path / "a", UNION_FIRST, production="_published")
    second = scan(tmp_path / "b", UNION_SECOND, production="_published")
    assert ([g["prod"] for g in first["groups"]]
            == [g["prod"] for g in second["groups"]]), \
        (first["groups"], second["groups"])
    assert first["risk"] == second["risk"]


def test_a_union_branch_of_a_different_width_is_not_lined_up(tmp_path):
    """The guard. Where the branches are not plainly the same width, nothing is
    known about which column lands where, so no name is invented."""
    out = scan(tmp_path, {
        "a.sql": """
            CREATE OR REPLACE TABLE stage_w AS
            SELECT id, region, other_col AS market FROM legacy_demographics
            UNION ALL
            SELECT id, cm13 FROM customer_demographics;
        """,
        "b.sql": "CREATE OR REPLACE TABLE union_published AS SELECT market FROM stage_w;",
    }, production="_published")
    assert out["risk"] != "none" or [g["prod"] for g in out["groups"]] == []


def test_a_union_of_three_branches_takes_the_first_ones_names(tmp_path):
    """Written as Union(Union(a, b), c). The third branch is the one most
    likely to be read as if it wrapped the others rather than sat beside them."""
    out = scan(tmp_path, {
        "a.sql": """
            CREATE OR REPLACE TABLE stage_v AS
            SELECT id, a_col AS market FROM t_a
            UNION ALL
            SELECT id, b_col FROM t_b
            UNION ALL
            SELECT id, cm13 FROM customer_demographics;
        """,
        "b.sql": "CREATE OR REPLACE TABLE union_published AS SELECT market FROM stage_v;",
    }, production="_published")
    assert [g["prod"] for g in out["groups"]] == ["union_published"], out["groups"]


# ── templates that use their own control flow ─────────────────────────────
# Templating was read as holes with names in them: blank the tags, keep every
# body. Real pipeline SQL also uses it as a small programming language, and
# those shapes do not survive that treatment -- an if/else leaves BOTH branches
# concatenated, a {% set %} block leaves a value sitting inside the statement,
# and a placeholder alone on its line becomes a bare word welded to the line
# below it.
#
# None of those parse, so the file was not half-read: it was not read at all.
# Measured on a real BigQuery warehouse of 7,304 files -- 329 of its 2,320 .sql
# files are templated, and 176 of them produced no statement, no table and no
# column anywhere in any answer.
#
# Each rendering is only tried on a file that ALREADY failed to parse, so no
# file that reads today can start reading differently.


def test_an_if_else_does_not_kill_the_whole_file(tmp_path):
    """Both branches kept, run together, is not SQL. Before this the file
    produced nothing at all and the chain to the published table vanished."""
    out = scan(tmp_path, {
        "a.sql": """
            CREATE OR REPLACE TABLE stage_t AS
            SELECT id, cm13
            FROM customer_demographics
            {% if backfill %}
              WHERE dt >= '2020-01-01'
            {% else %}
              WHERE dt = CURRENT_DATE()
            {% endif %};
        """,
        "b.sql": "CREATE OR REPLACE TABLE final_published AS SELECT cm13 FROM stage_t;",
    })
    assert [g["prod"] for g in out["groups"]] == ["final_published"], out["groups"]
    assert out["stats"]["couldNotRead"] == 0, out["unreadable"]


def test_a_set_block_is_a_value_not_part_of_the_statement(tmp_path):
    """{% set clause %}...{% endset %} holds a fragment used somewhere else.
    Left where it is written it puts a WHERE in front of a WITH."""
    out = scan(tmp_path, {
        "a.sql": """
            {% set extra_filter %}
              WHERE dt = CURRENT_DATE()
            {% endset %}
            CREATE OR REPLACE TABLE stage_s AS
            SELECT id, cm13 FROM customer_demographics;
        """,
        "b.sql": "CREATE OR REPLACE TABLE final_published AS SELECT cm13 FROM stage_s;",
    })
    assert [g["prod"] for g in out["groups"]] == ["final_published"], out["groups"]
    assert out["stats"]["couldNotRead"] == 0, out["unreadable"]


def test_a_placeholder_alone_on_its_line_is_a_block_not_a_name(tmp_path):
    """{{ header }} on its own line is a whole block of SQL dropped in. Turned
    into a bare identifier it welds itself to the statement below and takes the
    entire file down with it -- 79 files of one real warehouse, this shape."""
    out = scan(tmp_path, {
        "a.sql": """{{ header }}
            CREATE OR REPLACE TABLE stage_h AS
            SELECT id, cm13 FROM customer_demographics;
        """,
        "b.sql": "CREATE OR REPLACE TABLE final_published AS SELECT cm13 FROM stage_h;",
    })
    assert [g["prod"] for g in out["groups"]] == ["final_published"], out["groups"]
    assert out["stats"]["couldNotRead"] == 0, out["unreadable"]


def test_a_table_name_on_its_own_line_is_still_read_as_a_table(tmp_path):
    """The guard, and the reason the standalone rendering is tried LAST. A
    source table written under a FROM is this exact shape, and blanking it
    would lose a real table with nothing said. This file parses as it stands,
    so no rendering may touch it."""
    out = scan(tmp_path, {
        "a.sql": """
            CREATE OR REPLACE TABLE stage_n AS
            SELECT id, cm13
            FROM
              {{ project }}.{{ dataset }}.customer_demographics;
        """,
        "b.sql": "CREATE OR REPLACE TABLE final_published AS SELECT cm13 FROM stage_n;",
    })
    assert [g["prod"] for g in out["groups"]] == ["final_published"], out["groups"]


def test_a_rendering_never_moves_a_line_number(tmp_path):
    """Every finding sends somebody to a line to look at it. A rendering that
    dropped a branch and its newlines with it would point at the wrong one."""
    out = scan(tmp_path, {
        "a.sql": "-- one\n-- two\n{% if x %}\n-- three\n{% else %}\n-- four\n"
                 "{% endif %}\nCREATE OR REPLACE TABLE final_published AS\n"
                 "SELECT cm13 FROM customer_demographics;\n",
    })
    hits = [ln["n"] for g in out["groups"] for r in g["rows"]
            for ln in r["lines"] if ln.get("hit")]
    # The SELECT really is on line 9 of the file as it is written. A rendering
    # that dropped the else-branch and its newlines with it would report 7.
    assert hits == [9], (hits, out["groups"])


def test_a_template_that_still_will_not_parse_is_still_reported(tmp_path):
    """The rendering list is a second chance, never a way of claiming a file
    was read. Nothing here parses any way round, and it has to say so."""
    _, _, parsed = build(tmp_path, {
        "a.sql": "{% if x %}\n((((\n{% else %}\n))))\n{% endif %}\n"
                 "SELECT cm13 FROM customer_demographics WHERE ((((;\n"})
    assert parsed.unreadable, "a file nothing could read must be on the list"


# ── SQL in a program that never says SELECT ───────────────────────────────
# A block of text inside a program is only mined when it looks like SQL, and
# the list of words that count left out every statement that has no SELECT in
# it. A DELETE, a TRUNCATE or a CREATE FUNCTION written as a string was not
# mined, not read, and not lineage -- and the file it sat in went onto the
# "check by hand" list saying there was SQL in it that could not be taken out.
#
# Measured on a real BigQuery warehouse: 24 such blocks in 9 files, 18 of them
# a DELETE against a table the same repository publishes.


def test_a_delete_written_as_a_string_is_read(tmp_path):
    """No SELECT anywhere in it, so nothing mined it. The published table it
    maintains was named on no screen at all."""
    _, _, parsed = build(tmp_path, {
        "job.py": 'q = """DELETE FROM final_published WHERE cm13 IS NULL"""\n'
                  'client.query(q)\n'})
    assert parsed.statements, "the DELETE is a statement and has to be read"
    assert not parsed.unreadable, parsed.unreadable


def test_a_create_function_written_as_a_string_is_read(tmp_path):
    """The other half of the same miss: a UDF defined from a program."""
    _, _, parsed = build(tmp_path, {
        "job.py": 'q = """CREATE TEMP FUNCTION udf_seg(x STRING) AS '
                  '(LOWER(cm13))"""\n'})
    assert parsed.statements or parsed.opaque, \
        "the function body names a column and something has to have read it"
    assert not parsed.unreadable, parsed.unreadable


def test_english_prose_about_creating_a_table_is_not_mined(tmp_path):
    """The guard, and the reason the list of words is written tightly. A
    docstring saying it will "create the destination table" is not SQL, and a
    statement invented out of prose puts a table on screen that does not
    exist."""
    _, _, parsed = build(tmp_path, {
        "job.py": '"""This helper will create the destination table for you, '
                  'then update the customer_demographics rows it finds."""\n'})
    assert [s.target for s in parsed.statements] == [], \
        [s.target for s in parsed.statements]


def test_both_branches_of_a_template_are_followed(tmp_path):
    """Nothing in the file says which way it runs -- a variable set somewhere
    else decides that -- so choosing one branch is a guess, and a guess that
    goes the wrong way loses a source table with nothing said.

    Measured on a real BigQuery warehouse: of 103 templated files with an
    if/else that read more than one way, 26 name DIFFERENT tables in their two
    branches. Following one of those and calling the file read is the quietest
    version of this tool's worst failure."""
    files = {
        "a.sql": "CREATE OR REPLACE TABLE stage_t AS\n"
                 "SELECT id, cm13 FROM customer_demographics\n"
                 "{% if backfill %}\n"
                 "  UNION ALL SELECT id, cm13 FROM archive_demographics\n"
                 "{% else %}\n"
                 "  UNION ALL SELECT id, cm13 FROM live_demographics\n"
                 "{% endif %};\n",
        "b.sql": "CREATE OR REPLACE TABLE final_published AS SELECT cm13 FROM stage_t;",
    }
    _, _, parsed = build(tmp_path, files)
    read = set()
    for s in parsed.statements:
        read |= {t.upper() for t in s.sources}
    assert "ARCHIVE_DEMOGRAPHICS" in read, read
    assert "LIVE_DEMOGRAPHICS" in read, read


def test_reading_a_template_both_ways_is_not_two_definitions(tmp_path):
    """The guard on merging. The parts of the file outside the branches are
    nearly all of it, and read once per rendering they would come back as the
    same table built twice -- a warning about something that is not there."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE stage_t AS\n"
                 "SELECT id, cm13 FROM customer_demographics\n"
                 "{% if backfill %}\n  WHERE dt > '2020-01-01'\n"
                 "{% else %}\n  WHERE dt = CURRENT_DATE()\n{% endif %};\n",
        "b.sql": "CREATE OR REPLACE TABLE final_published AS SELECT cm13 FROM stage_t;",
    })
    assert out["twoDefinitions"] == [], out["twoDefinitions"]
    assert [g["prod"] for g in out["groups"]] == ["final_published"], out["groups"]


# ── one statement written as several strings ──────────────────────────────
# The worst answer found in this whole file, and the only one where the
# coverage card itself said there was nothing missing::
#
#     sql  = "CREATE OR REPLACE TABLE final_published AS SELECT cm13 "
#     sql += "FROM customer_demographics WHERE dt = @d"
#
# Every miner looked for a whole statement inside ONE pair of quotes, so it
# found the first piece. And the first piece PARSES -- BigQuery is happy with a
# SELECT that has no FROM -- so nothing failed, nothing landed on the
# check-by-hand list, and the scan came back:
#
#     risk none, prod [], coverage {"complete": true, "gaps": []}
#
# A green tick with "I could see all of it" printed beside it, over a job that
# really does rebuild the published table out of that column. Measured on a real
# BigQuery warehouse: 111 of its Python files hold SQL, 52 of them build it out
# of adjacent strings, 37 with a +, 11 with a +=.
GLUED = {
    "job.py": 'sql = "CREATE OR REPLACE TABLE final_published AS SELECT cm13 "\n'
              'sql += "FROM customer_demographics WHERE dt = @d"\n'
              'client.query(sql)\n',
}


def test_a_statement_glued_from_two_strings_is_read_whole(tmp_path):
    """The reproduction."""
    out = scan(tmp_path, GLUED)
    assert [g["prod"] for g in out["groups"]] == ["final_published"], out["groups"]
    assert out["risk"] != "none"


def test_the_half_that_parsed_never_bought_a_clean_bill_of_health(tmp_path):
    """The half-statement parsing is what made this silent rather than loud.
    Nothing may report complete coverage over half a statement."""
    out = scan(tmp_path, GLUED)
    assert not (out["coverage"]["complete"] and not out["groups"]), \
        "complete coverage and no impact, over a statement read in half"


def test_the_same_statement_written_whole_gives_the_same_answer(tmp_path):
    """Two spellings of one job. This is the test that would have caught it."""
    glued = scan(tmp_path / "a", GLUED)
    whole = scan(tmp_path / "b", {
        "job.py": 'sql = """CREATE OR REPLACE TABLE final_published AS SELECT cm13 '
                  'FROM customer_demographics WHERE dt = @d"""\nclient.query(sql)\n'})
    assert ([g["prod"] for g in glued["groups"]]
            == [g["prod"] for g in whole["groups"]]), (glued["groups"], whole["groups"])
    assert glued["risk"] == whole["risk"]


def test_a_list_of_separate_queries_is_not_welded_into_one(tmp_path):
    """The guard. A comma between two strings means two queries, and joining
    them would invent a statement that is in no file -- the opposite failure,
    and just as wrong."""
    _, _, parsed = build(tmp_path, {
        "job.py": 'queries = [\n'
                  '  "CREATE OR REPLACE TABLE one_published AS SELECT cm13 FROM customer_demographics",\n'
                  '  "CREATE OR REPLACE TABLE two_published AS SELECT k FROM orders",\n]\n'})
    targets = sorted(s.target for s in parsed.statements if s.target)
    assert targets == ["one_published", "two_published"], targets


def test_two_variables_holding_two_queries_stay_two_queries(tmp_path):
    """The other guard. A += only ever joins to the variable the run before it
    was assigned to."""
    _, _, parsed = build(tmp_path, {
        "job.py": 'a = "CREATE OR REPLACE TABLE one_published AS SELECT cm13 FROM customer_demographics"\n'
                  'b = "CREATE OR REPLACE TABLE two_published AS SELECT k FROM orders"\n'})
    targets = sorted(s.target for s in parsed.statements if s.target)
    assert targets == ["one_published", "two_published"], targets


def test_a_welded_statement_is_not_also_read_in_half(tmp_path):
    """The first piece of a welded run is a quoted string in its own right, so
    the ordinary miner finds it too. Read once whole and once in half, every
    finding in it lands on screen twice."""
    out = scan(tmp_path, GLUED)
    rows = [r for g in out["groups"] for r in g["rows"]]
    assert len(rows) == 1, [(r["file"], r["lines"][0]["n"]) for r in rows]


# ── the trail ends where the code ends, not where a counter does ──────────
# A limit of 10 renames was reported as "the chain ends here and does not reach
# production" -- a sentence about a setting wearing the clothes of a sentence
# about the warehouse. The result screen offered to follow the trail twice as
# far, and on a chain longer than the ceiling that button changed NOTHING: the
# same cut-short trail, the same empty production list, run again for the same
# answer. Measured on a 36-hop chain: 10 hops cut short, 20 cut short, and 25 --
# the highest the screen would offer -- cut short as well. There was no number
# to type that produced an answer.
#
# The walk already carries a set of every (table, column) it has been through,
# so a cycle cannot run forever whatever the limit is. The counter was a second
# guard that could only ever truncate a real answer. Measured on a real
# BigQuery warehouse of 7,304 files: following to the end costs 10.6s against
# 10.5s at ten hops, and finds the same tables plus the ones past the limit.
DEEP_CHAIN = {"00.sql": "CREATE OR REPLACE TABLE s00 AS SELECT id, cm13 AS c00 "
                        "FROM customer_demographics;"}
for _i in range(1, 30):
    DEEP_CHAIN[f"{_i:02d}.sql"] = (
        f"CREATE OR REPLACE TABLE s{_i:02d} AS SELECT id, c{_i - 1:02d} AS c{_i:02d} "
        f"FROM s{_i - 1:02d};")
DEEP_CHAIN["99.sql"] = ("CREATE OR REPLACE TABLE deep_published AS "
                        "SELECT c29 AS market_code FROM s29;")


def test_a_chain_longer_than_any_offered_limit_still_reaches_production(tmp_path):
    """Thirty renames deep. Nothing a person could choose on screen reached it,
    so the answer was "no production table" however many times they asked."""
    out = scan(tmp_path, DEEP_CHAIN, max_hops=0)
    assert [g["prod"] for g in out["groups"]] == ["deep_published"], out["groups"]
    assert out["cutShort"] == [], out["cutShort"]


def test_following_to_the_end_is_the_default(tmp_path):
    """The setting a person never touches has to be the one that answers the
    question. A default that quietly truncates is the same wrong answer with
    nobody to blame for it."""
    cfg, idx, parsed = build(tmp_path, DEEP_CHAIN, max_hops=Settings().max_hops)
    from ripple.scanner.lineage import trace                      # noqa: PLC0415
    out = trace(idx, parsed, [{"table": "customer_demographics", "attrs": ["cm13"]}],
                change_type="removal", cfg=cfg).to_dict()
    assert [g["prod"] for g in out["groups"]] == ["deep_published"], out["groups"]
    assert out["cutShort"] == [], out["cutShort"]


def test_a_limit_that_was_asked_for_is_still_obeyed_and_still_said(tmp_path):
    """The guard. Somebody who sets a limit gets it -- and a trail stopped by it
    is still reported as stopped, never as a chain that ended."""
    out = scan(tmp_path, DEEP_CHAIN, max_hops=5)
    assert [g["prod"] for g in out["groups"]] == [], out["groups"]
    assert out["cutShort"], "a trail stopped by a limit must say so"
    assert out["maxHops"] == 5


def test_a_ring_of_tables_does_not_run_forever(tmp_path):
    """Why the counter looked necessary. It never was: the walk carries every
    (table, column) it has been through, so a ring closes on itself."""
    out = scan(tmp_path, {
        "a.sql": "CREATE OR REPLACE TABLE ring_a AS SELECT cm13 FROM customer_demographics;",
        "b.sql": "CREATE OR REPLACE TABLE ring_b AS SELECT cm13 FROM ring_a;",
        "c.sql": "CREATE OR REPLACE TABLE ring_a AS SELECT cm13 FROM ring_b;",
        "d.sql": "CREATE OR REPLACE TABLE final_published AS SELECT cm13 FROM ring_b;",
    }, max_hops=0)
    assert [g["prod"] for g in out["groups"]] == ["final_published"], out["groups"]


# ── the published-table list is the person's, never Ripple's ──────────────
# The list of table names that count as published shipped with a default:
# _PROD, _PRD, _PUBLISHED. On a warehouse that names its published tables
# anything else, that default matches NOTHING -- and matching nothing does not
# read as "I do not know which tables are yours". It reads as "no production
# table is affected", in green, over a change that breaks all of them.
#
# It is the most expensive setting in the tool and the only one Ripple cannot
# work out for itself, so it is now asked for rather than guessed, and nothing
# is scanned until it has been given.


def test_a_scan_with_no_published_list_refuses_rather_than_reassures(tmp_path):
    """The whole point. Silence here has to be a refusal, never a green tick."""
    from ripple.config import Settings                             # noqa: PLC0415
    cfg = Settings()
    cfg.set_production("")
    assert not cfg.has_production(), \
        "an empty list must read as 'not given', never as 'nothing is published'"


def test_an_empty_list_does_not_quietly_become_the_shipped_default(tmp_path):
    """The old behaviour: an empty box fell back to _PROD, _PRD, _PUBLISHED, and
    the screen then reported findings against a rule nobody chose."""
    from ripple.config import Settings                             # noqa: PLC0415
    cfg = Settings()
    cfg.set_production("")
    assert cfg.production_patterns == (), cfg.production_patterns
    assert cfg.production_text == "", cfg.production_text


def test_a_list_that_was_given_is_used_exactly_as_given(tmp_path):
    """The guard. Asking for the list is only an improvement if what arrives is
    what gets matched."""
    from ripple.config import Settings                             # noqa: PLC0415
    cfg = Settings()
    cfg.set_production("marts_gold, _published")
    assert cfg.has_production()
    assert cfg.is_production_table("customer_marts_gold") or \
        cfg.is_production_table("marts_gold")
    assert cfg.is_production_table("anything_published")


def test_asking_for_the_end_of_the_code_is_not_read_as_asking_for_nothing(tmp_path):
    """Zero is a real request -- follow it to the end -- and read as falsy it
    was indistinguishable from not asking at all. The button ran, the saved
    limit was used anyway, and the same cut-short answer came back."""
    from fastapi.testclient import TestClient                     # noqa: PLC0415
    from ripple import api                                        # noqa: PLC0415
    from ripple.config import settings as live                    # noqa: PLC0415

    for name, text in DEEP_CHAIN.items():
        (tmp_path / name).write_text(text, encoding="utf-8")
    before_path, before_hops = live.repo_path, live.max_hops
    live.repo_path, live.max_hops = tmp_path, 5
    live.set_production("_published")
    api._state["index"] = None
    try:
        api.repo_state()
        with TestClient(api.app) as c:
            body = {"upstream": [{"table": "customer_demographics", "attrs": ["cm13"]}],
                    "changeKind": "removal"}
            shallow = c.post("/api/scan", json=body).json()
            assert shallow["cutShort"], "a limit of five must cut this chain short"
            deep = c.post("/api/scan", json={**body, "maxHops": 0}).json()
            assert deep["maxHops"] == 0, deep["maxHops"]
            assert deep["cutShort"] == [], deep["cutShort"]
            assert [g["prod"] for g in deep["groups"]] == ["deep_published"], deep["groups"]
    finally:
        live.repo_path, live.max_hops = before_path, before_hops
        api._state["index"] = None
