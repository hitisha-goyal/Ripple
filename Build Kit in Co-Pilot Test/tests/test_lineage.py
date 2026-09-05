"""Tests for the catalogue and the walk.

Every table and column name here is invented.

Two stand-ins live in this file on purpose. The repository index and the
unreadable-file record are built by other parts of Ripple, and these tests are
about the walk, so they hand it the smallest object carrying the fields the
walk reads. That means these tests would go on passing if those two shapes were
renamed elsewhere, which is worth knowing when reading a green run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import sqlglot
from sqlglot import expressions as exp

from ripple.catalog import build_catalog
from ripple.scanner.lineage import trace
from ripple.scanner.repo import SourceFile
from ripple.scanner.sqlread import ParsedRepo, Statement


@dataclass
class FakeIndex:
    """The repository facts the walk reads off the index it is handed."""

    files: list[SourceFile] = field(default_factory=list)
    files_scanned: int = 0
    held_online: list[str] = field(default_factory=list)
    path_too_long: list[str] = field(default_factory=list)
    skipped_in_folders: int = 0
    skipped_folder_names: list[str] = field(default_factory=list)
    unopened_extensions: dict[str, int] = field(default_factory=dict)


@dataclass
class FakeSettings:
    max_hops: int = 8
    production_patterns: list[str] = field(default_factory=list)


@dataclass
class FakeUnreadable:
    path: str
    line: int
    text: str
    why: str


def one_source(path: str, text: str) -> SourceFile:
    return SourceFile(
        path=path,
        abs_path="C:/mockrepo/" + path,
        text=text,
        lang="sql",
    )


def one_statement(
    path: str, sql: str, target: str, sources: set[str], line_offset: int = 1
) -> Statement:
    expr = sqlglot.parse_one(sql)
    return Statement(
        file=path,
        lang="sql",
        line_offset=line_offset,
        line_end=line_offset + sql.count("\n"),
        sql=sql,
        target=target,
        sources=set(sources),
        select=expr.find(exp.Select),
        expr=expr,
    )


def build(
    entries: list[tuple[str, str, str, set[str]]],
    unreadable: list[Any] | None = None,
    extra_files: list[SourceFile] | None = None,
    opaque: dict[str, list[dict[str, Any]]] | None = None,
    references: list[Any] | None = None,
) -> tuple[FakeIndex, ParsedRepo]:
    files = [one_source(path, sql) for path, sql, _, _ in entries]
    files.extend(extra_files or [])
    parsed = ParsedRepo(
        statements=[
            one_statement(path, sql, target, sources)
            for path, sql, target, sources in entries
        ],
        unreadable=list(unreadable or []),
        parsed_files={path for path, _, _, _ in entries},
        opaque=dict(opaque or {}),
        runs_sql_from=[],
        references=list(references or []),
        procedure_calls=[],
    )
    return FakeIndex(files=files, files_scanned=len(files)), parsed


CHAIN: list[tuple[str, str, str, set[str]]] = [
    (
        "sql/stage_one.sql",
        "CREATE TABLE stg_orders AS\n"
        "SELECT order_ref AS order_key, market_code AS mc\n"
        "FROM raw_orders",
        "stg_orders",
        {"raw_orders"},
    ),
    (
        "sql/stage_two.sql",
        "CREATE TABLE mid_orders AS\nSELECT order_key, mc AS mkt_cd\nFROM stg_orders",
        "mid_orders",
        {"stg_orders"},
    ),
    (
        "sql/final.sql",
        "CREATE TABLE orders_published AS\n"
        "SELECT order_key, mkt_cd\n"
        "FROM mid_orders",
        "orders_published",
        {"mid_orders"},
    ),
]

ASKED = [{"table": "raw_orders", "attrs": ["market_code"]}]


def test_a_chain_through_two_renames_reaches_the_published_table() -> None:
    index, parsed = build(CHAIN)
    said: list[str] = []
    result = trace(
        index,
        parsed,
        ASKED,
        "removal",
        FakeSettings(production_patterns=["*_published"]),
        said.append,
    )

    assert [group["prod"] for group in result.groups] == ["orders_published"]
    # Every hop is under the published table, not only the last one.
    assert {row["inter"] for row in result.groups[0]["rows"]} == {
        "stg_orders",
        "mid_orders",
        "orders_published",
    }
    assert result.attributes[0].reaches_production is True
    assert result.risk in ("medium", "high")
    assert said


def test_a_column_leaving_under_two_names_does_not_lose_the_chain() -> None:
    entries = [
        (
            "sql/fan.sql",
            "CREATE TABLE fan_out AS\n"
            "SELECT market_code AS mc_west, market_code AS mc_east\n"
            "FROM raw_orders",
            "fan_out",
            {"raw_orders"},
        ),
        (
            "sql/west.sql",
            "CREATE TABLE west_published AS\nSELECT mc_west\nFROM fan_out",
            "west_published",
            {"fan_out"},
        ),
        (
            "sql/east.sql",
            "CREATE TABLE east_published AS\nSELECT mc_east\nFROM fan_out",
            "east_published",
            {"fan_out"},
        ),
    ]
    index, parsed = build(entries)
    result = trace(
        index,
        parsed,
        ASKED,
        "removal",
        FakeSettings(production_patterns=["*_published"]),
        None,
    )

    assert {group["prod"] for group in result.groups} == {
        "west_published",
        "east_published",
    }


def test_findings_survive_when_nothing_matches_the_published_rule() -> None:
    """The one to insist on.

    An empty result here is the exact bug this tool exists to prevent: a real
    breaking impact shown as a clean result because the tables are not called
    _PROD.
    """
    index, parsed = build(CHAIN)
    result = trace(
        index,
        parsed,
        ASKED,
        "removal",
        FakeSettings(production_patterns=["*_gold"]),
        None,
    )

    assert result.groups == []
    assert "orders_published" in {row["table"] for row in result.reached}
    assert result.findings()
    assert result.stats.breaking_usages > 0
    assert result.risk != "none"


def test_correcting_the_rule_turns_them_into_production_tables() -> None:
    index, parsed = build(CHAIN)
    result = trace(
        index,
        parsed,
        ASKED,
        "removal",
        FakeSettings(production_patterns=["*_published"]),
        None,
    )

    assert "orders_published" in {group["prod"] for group in result.groups}
    assert "orders_published" not in {row["table"] for row in result.reached}


def test_a_genuinely_clean_result_is_still_clean() -> None:
    entries = [
        (
            "sql/notes.sql",
            "CREATE TABLE stg_notes AS\nSELECT note_ref\nFROM raw_notes",
            "stg_notes",
            {"raw_notes"},
        )
    ]
    index, parsed = build(entries)
    result = trace(
        index,
        parsed,
        ASKED,
        "removal",
        FakeSettings(production_patterns=["*_published"]),
        None,
    )

    assert result.findings() == []
    assert result.risk == "none"
    assert result.coverage is not None
    assert result.coverage.complete is True
    assert result.attributes[0].found == 0
    assert result.attributes[0].mentioned_in == 0


def test_nothing_found_but_a_file_it_could_not_read_is_unknown() -> None:
    entries = [
        (
            "sql/notes.sql",
            "CREATE TABLE stg_notes AS\nSELECT note_ref\nFROM raw_notes",
            "stg_notes",
            {"raw_notes"},
        )
    ]
    broken = one_source(
        "sql/broken.sql",
        "CREATE OR REPLACE PROCEDURE load_orders()\nBEGIN\n  -- market_code\nEND",
    )
    index, parsed = build(
        entries,
        unreadable=[
            FakeUnreadable(
                path="sql/broken.sql",
                line=1,
                text="CREATE OR REPLACE PROCEDURE load_orders()",
                why="the parser stopped here",
            )
        ],
        extra_files=[broken],
    )
    result = trace(
        index,
        parsed,
        ASKED,
        "removal",
        FakeSettings(production_patterns=["*_published"]),
        None,
    )

    assert result.findings() == []
    assert result.risk == "unknown"
    assert result.coverage is not None
    assert result.coverage.complete is False
    # "I never saw that column" may not be printed over a file nobody read.
    assert result.lookup_failed is False
    assert "sql/broken.sql" in {item.file for item in result.unreadable}


def test_a_quoted_name_is_reported_even_in_a_file_that_has_findings() -> None:
    entries = [
        (
            "sql/tagged.sql",
            "CREATE TABLE tagged_orders AS\n"
            "SELECT get_sde_tag('market_code') AS tag_one,\n"
            "       get_sde_tag('market_code') AS tag_two,\n"
            "       market_code\n"
            "FROM raw_orders",
            "tagged_orders",
            {"raw_orders"},
        )
    ]
    index, parsed = build(entries)
    result = trace(
        index,
        parsed,
        ASKED,
        "removal",
        FakeSettings(production_patterns=["*_published"]),
        None,
    )

    assert result.findings(), "the plain column in this file is a real usage"
    tagged = [item for item in result.unreadable if item.file == "sql/tagged.sql"]
    assert tagged, "fixing the findings does not fix the text that still says the name"
    # Two lines set a tag, and a report naming one line sends somebody to fix
    # one line out of two.
    assert tagged[0].mention_lines == 2


def test_groups_come_back_worst_first() -> None:
    entries = [
        (
            "sql/alpha.sql",
            "CREATE TABLE alpha_published AS\nSELECT market_code\nFROM raw_orders",
            "alpha_published",
            {"raw_orders"},
        ),
        (
            "sql/beta_mid.sql",
            "CREATE TABLE mid_beta AS\nSELECT market_code AS mc\nFROM raw_orders",
            "mid_beta",
            {"raw_orders"},
        ),
        (
            "sql/beta.sql",
            "CREATE TABLE beta_published AS\nSELECT mc\nFROM mid_beta",
            "beta_published",
            {"mid_beta"},
        ),
    ]
    index, parsed = build(entries)
    result = trace(
        index,
        parsed,
        ASKED,
        "removal",
        FakeSettings(production_patterns=["*_published"]),
        None,
    )

    # beta_published carries two usages, alpha_published one. Alphabetical
    # order would put alpha first and hide the worse one.
    assert [group["prod"] for group in result.groups] == [
        "beta_published",
        "alpha_published",
    ]


def test_the_hop_limit_is_carried_out_as_a_setting_not_an_ending() -> None:
    index, parsed = build(CHAIN)
    result = trace(
        index,
        parsed,
        ASKED,
        "removal",
        FakeSettings(max_hops=1, production_patterns=["*_published"]),
        None,
    )

    assert result.cut_short, "the limit stopped the walk and has to say so"
    assert result.stats.trails_cut_short == len(result.cut_short)
    assert result.max_hops == 1
    stopped = {entry["table"] for entry in result.cut_short}
    report = result.attributes[0]
    assert report.cut_short_at == stopped
    # A branch Ripple gave up on has not ended.
    assert report.ends_at.isdisjoint(stopped)
    assert any(row["cut"] for row in result.reached if row["table"] in stopped)
    assert result.coverage is not None
    assert result.coverage.complete is False


def test_a_filter_only_usage_ends_the_column_trail_and_stops_the_table_loading() -> None:
    entries = [
        (
            "sql/filtered.sql",
            "CREATE TABLE stg_kept AS\n"
            "SELECT order_ref\n"
            "FROM raw_orders\n"
            "WHERE market_code = 'aa'",
            "stg_kept",
            {"raw_orders"},
        ),
        (
            "sql/downstream.sql",
            "CREATE TABLE kept_published AS\nSELECT order_ref\nFROM stg_kept",
            "kept_published",
            {"stg_kept"},
        ),
    ]
    index, parsed = build(entries)
    result = trace(
        index,
        parsed,
        ASKED,
        "removal",
        FakeSettings(production_patterns=["*_published"]),
        None,
    )

    # The column never reaches the table, so the trail ends at stg_kept.
    assert "stg_kept" in {row["table"] for row in result.reached}
    # The statement still stops working, so the published table below it stops
    # being refreshed - a different question, its own count.
    assert [row["prod"] for row in result.stops_loading] == ["kept_published"]
    assert result.stats.production_stops_loading == 1
    assert result.stats.production_tables == 0


def test_the_catalogue_reads_a_column_list_and_admits_a_star() -> None:
    entries = [
        (
            "sql/defined.sql",
            "CREATE TABLE stg_orders (order_key STRING, market_code STRING)",
            "stg_orders",
            set(),
        ),
        (
            "sql/copied.sql",
            "CREATE TABLE copy_orders AS\nSELECT *\nFROM stg_orders",
            "copy_orders",
            {"stg_orders"},
        ),
    ]
    _, parsed = build(entries)
    catalog = build_catalog(parsed)

    assert catalog.columns_of("stg_orders") == ["order_key", "market_code"]
    assert catalog.tables_naming("market_code") == ["stg_orders"]
    # The real column list is not visible there, and pretending otherwise is a
    # lie.
    assert catalog.columns_of("copy_orders") == []
    assert "copy_orders" in catalog.gap_tables()
