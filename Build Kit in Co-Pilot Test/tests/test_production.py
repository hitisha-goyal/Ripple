from __future__ import annotations

"""Tests for the published-table list.

Every table name here is invented. This file decides whether "no production
table is impacted" is a real answer or an accident, so the tests that matter
most are the messy ones: a heading row, Slack bullets, and a line of ordinary
prose all in the same paste.
"""

import pytest

from ripple.config import Settings
from ripple.production import matches, parse_production

THREE = {"alpha_daily", "beta_weekly", "gamma_monthly"}


def keys(text: str) -> set[str]:
    return {entry.match for entry in parse_production(text).entries}


def notes(text: str) -> list[str]:
    return list(parse_production(text).notes)


@pytest.mark.parametrize(
    "pasted",
    [
        "alpha_daily\nbeta_weekly\ngamma_monthly",
        "alpha_daily, beta_weekly, gamma_monthly",
        "alpha_daily, beta_weekly,\ngamma_monthly",
        "alpha_daily; beta_weekly; gamma_monthly",
        "\n  alpha_daily  \n\n beta_weekly\n\n gamma_monthly \n",
        "• alpha_daily\n• beta_weekly\n• gamma_monthly",
        "- alpha_daily\n* beta_weekly\n- gamma_monthly",
        "1. alpha_daily\n2) beta_weekly\n(3) gamma_monthly",
        "`alpha_daily`\n`beta_weekly`\n`gamma_monthly`",
        "```\nalpha_daily\nbeta_weekly\ngamma_monthly\n```",
        "\"alpha_daily\",\n'beta_weekly',\ngamma_monthly,",
        "alpha_daily beta_weekly gamma_monthly",
    ],
)
def test_a_list_survives_however_it_was_copied(pasted: str) -> None:
    assert keys(pasted) == THREE


def test_an_excel_column_keeps_its_heading_out_of_the_list() -> None:
    pasted = "Table name\nalpha_daily\nbeta_weekly\ngamma_monthly"
    assert keys(pasted) == THREE
    assert any("heading row" in note for note in notes(pasted))


def test_several_excel_columns_pick_the_table_column_and_say_which() -> None:
    pasted = (
        "Table name\tOwner\tStatus\n"
        "alpha_daily\tpayments\tactive\n"
        "beta_weekly\tlogistics\tactive\n"
        "gamma_monthly\tpayments\tretired"
    )
    rule = parse_production(pasted)
    assert {entry.match for entry in rule.entries} == THREE
    assert rule.column_used == "Table name"
    assert any(
        'The paste had 3 columns. Ripple read the column headed "Table name" '
        "and ignored the other 2." == note
        for note in rule.notes
    )


def test_several_columns_with_no_heading_still_pick_the_table_column() -> None:
    pasted = (
        "payments\talpha_daily\tactive\n"
        "logistics\tbeta_weekly\tactive\n"
        "payments\tgamma_monthly\tretired"
    )
    rule = parse_production(pasted)
    assert {entry.match for entry in rule.entries} == THREE
    assert any("Ripple read column 2" in note for note in rule.notes)


def test_a_markdown_table_from_confluence_reads_as_a_list() -> None:
    pasted = (
        "| Table name | Owner |\n"
        "| --- | --- |\n"
        "| alpha_daily | payments |\n"
        "| beta_weekly | logistics |\n"
        "| gamma_monthly | payments |"
    )
    assert keys(pasted) == THREE


def test_qualified_two_part_and_bare_names_mix_in_one_paste() -> None:
    pasted = (
        "prj-x-1.mart_zone.alpha_daily\n"
        "mart_zone.beta_weekly\n"
        "gamma_monthly"
    )
    rule = parse_production(pasted)
    assert {entry.match for entry in rule.entries} == THREE
    # The whole thing as pasted is kept for showing back on screen.
    assert "prj-x-1.mart_zone.alpha_daily" in {entry.raw for entry in rule.entries}
    assert matches(rule, "alpha_daily")
    assert matches(rule, "other_zone.alpha_daily")


def test_duplicates_and_capitalisation_are_reduced_and_reported() -> None:
    pasted = (
        "alpha_daily\nALPHA_DAILY\nbeta_weekly\nBeta_Weekly\nalpha_daily"
    )
    rule = parse_production(pasted)
    assert {entry.match for entry in rule.entries} == {
        "alpha_daily",
        "beta_weekly",
    }
    assert "3 duplicates removed." in rule.notes


def test_two_names_ripple_cannot_tell_apart_are_reported() -> None:
    pasted = "zone_one.alpha_daily\nzone_two.alpha_daily"
    rule = parse_production(pasted)
    assert len(rule.entries) == 1
    assert any("the same table to Ripple" in note for note in rule.notes)
    # Not the same thing as a duplicate, and must not be reported as one.
    assert not any("duplicate" in note for note in rule.notes)


def test_a_line_that_is_not_a_table_name_is_reported() -> None:
    pasted = (
        "alpha_daily\n"
        "see the attached sheet for the rest\n"
        "beta_weekly"
    )
    rule = parse_production(pasted)
    assert {entry.match for entry in rule.entries} == {
        "alpha_daily",
        "beta_weekly",
    }
    assert (
        "1 line did not look like a table name and was ignored." in rule.notes
    )


def test_prose_is_never_split_into_invented_table_names() -> None:
    pasted = "alpha_daily\nplease confirm by friday\nbeta_weekly"
    found = keys(pasted)
    assert found == {"alpha_daily", "beta_weekly"}
    for word in ("please", "confirm", "by", "friday"):
        assert word not in found
    assert any("did not look like a table name" in note for note in notes(pasted))


def test_a_messy_paste_reports_everything_it_left_out() -> None:
    pasted = (
        "```\n"
        "Table name\n"
        "• alpha_daily\n"
        "- beta_weekly\n"
        "1. gamma_monthly\n"
        "ALPHA_DAILY\n"
        "please confirm by friday\n"
        "```"
    )
    rule = parse_production(pasted)
    assert {entry.match for entry in rule.entries} == THREE
    assert "1 line looked like a heading row and was ignored." in rule.notes
    assert (
        "1 line did not look like a table name and was ignored." in rule.notes
    )
    assert "1 duplicate removed." in rule.notes


@pytest.mark.parametrize(
    "pattern,table,expected",
    [
        ("_PROD", "orders_prod", True),
        ("_PROD", "mart_zone.orders_prod", True),
        ("_PROD", "ORDERS_PROD", True),
        ("_PROD", "orders_staging", False),
        ("_PROD", "prod_orders", False),
        ("_PUBLISHED", "alpha_published", True),
        ("PROD_*", "prod_orders", True),
        ("PROD_*", "orders_prod", False),
        ("*_snap", "alpha_snap", True),
        ("*_snap", "alpha_snapshot", False),
        ("alpha_?", "alpha_1", True),
        ("alpha_?", "alpha_12", False),
    ],
)
def test_every_pattern_still_does_what_it_did_before(
    pattern: str, table: str, expected: bool
) -> None:
    rule = parse_production(pattern)
    assert matches(rule, table) is expected


def test_an_exact_name_matches_only_that_table() -> None:
    rule = parse_production("sales_daily")
    assert matches(rule, "sales_daily")
    assert matches(rule, "mart_zone.sales_daily")
    # The one that matters: an exact name is not a suffix.
    assert not matches(rule, "stg_sales_daily")
    assert not matches(rule, "sales_daily_backup")


def test_names_and_patterns_work_side_by_side() -> None:
    chosen = Settings()
    chosen.set_production("alpha_daily\n_PROD\nPROD_*")
    assert chosen.is_production_table("alpha_daily")
    assert chosen.is_production_table("mart_zone.orders_prod")
    assert chosen.is_production_table("prod_orders")
    assert not chosen.is_production_table("beta_weekly")


def test_an_empty_box_falls_back_rather_than_meaning_nothing_is_production() -> None:
    rule = parse_production("   \n\n")
    assert rule.from_default
    assert matches(rule, "orders_prod")
    assert matches(rule, "orders_prd")
    assert matches(rule, "orders_published")
    assert not matches(rule, "orders_staging")
    assert any("default" in note for note in rule.notes)


def test_the_one_line_form_counts_a_long_list_instead_of_printing_it() -> None:
    chosen = Settings()
    chosen.set_production("alpha_daily\nbeta_weekly")
    assert chosen.production_rule() == "alpha_daily and beta_weekly"

    long_list = "\n".join(f"tbl_{number}_daily" for number in range(40))
    chosen.set_production(long_list + "\n_PROD")
    line = chosen.production_rule()
    assert line == "40 table names and 1 pattern (_PROD)"
    assert "tbl_7_daily" not in line
