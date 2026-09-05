from __future__ import annotations

"""Tests for the rules-written summary and the drafted reply.

The tests that matter here are not about wording. They are about the four
sentences this tool must never write: "no impact" over a list of findings,
"no impact" over files nobody could read, "no impact" over an empty folder,
and "please proceed as planned" over any of the three.

Every table and column name below is invented.
"""

from ripple.narrative import draft_reply, summarise

# ---------------------------------------------------------------------------
# builders
# ---------------------------------------------------------------------------

VALS = {
    "attributes": ["MARKET_GRADE"],
    "table": "CUSTOMER_ROLLUP",
    "date": "18 September",
}


def _stats(**over: object) -> dict[str, object]:
    stats: dict[str, object] = {
        "productionTables": 0,
        "tablesReached": 0,
        "intermediateTables": 0,
        "attributesImpacted": 0,
        "filesWithImpact": 0,
        "breakingUsages": 0,
        "couldNotRead": 0,
        "neverOpened": 0,
        "tablesNotVisible": 0,
        "inferredFindings": 0,
        "trailsCutShort": 0,
        "productionStopsLoading": 0,
        "feedsBroken": 0,
    }
    stats.update(over)
    return stats


def _scan(**over: object) -> dict[str, object]:
    scan: dict[str, object] = {
        "attributes": [],
        "groups": [],
        "reached": [],
        "other": [],
        "graphs": [],
        "unreadable": [],
        "mentionsOnly": [],
        "heldOnline": [],
        "pathTooLong": [],
        "starTables": [],
        "cutShort": [],
        "mergedNames": [],
        "wildcardNames": [],
        "namedByFile": [],
        "builtAsText": [],
        "twoDefinitions": [],
        "skippedInFolders": [],
        "skippedFolderNames": [],
        "fileTypesUnopened": [],
        "stopsLoading": [],
        "referencedHere": [],
        "feeds": [],
        "stopsLoadingCapped": False,
        "maxHops": 4,
        "filesScanned": 0,
        "filesMatched": 0,
        "risk": "unknown",
        "lookupFailed": False,
        "coverage": {
            "complete": True,
            "gaps": [],
            "filesMatched": 0,
            "filesUnread": 0,
        },
        "stats": _stats(),
    }
    scan.update(over)
    return scan


def _finding(**over: object) -> dict[str, object]:
    finding: dict[str, object] = {
        "inter": "stage_orders",
        "from": "raw_orders",
        "attr": "market_grade",
        "roots": ["MARKET_GRADE"],
        "alias": "",
        "logic": "",
        "mode": "read",
        "impact": "",
        "breaking": False,
        "noLocalFix": False,
        "file": "pipelines/stage_orders.sql",
        "lang": "sql",
        "lines": [{"n": 12, "t": "select market_grade", "hit": True}],
        "certain": True,
        "viaStar": False,
        "copiedBy": "",
        "builtAsText": "",
        "feed": "",
        "inferredHops": 0,
    }
    finding.update(over)
    return finding


def _everything(summary: dict) -> str:
    """Headline, narrative, bullets and actions as one lump of lowercase
    text, so a forbidden sentence cannot hide in the part nobody asserted
    on."""
    parts = [summary["headline"], summary["narrative"]]
    parts.extend(summary["bullets"])
    parts.extend(summary["actions"])
    return " ".join(parts).lower()


# ---------------------------------------------------------------------------
# the four sentences that must never be written
# ---------------------------------------------------------------------------


def test_a_genuinely_clean_result_still_says_no_impact_in_both() -> None:
    scan = _scan(filesScanned=14, filesMatched=0, risk="none")
    summary = summarise(scan, VALS)
    reply = draft_reply(scan, VALS, summary)

    assert "no impact" in summary["headline"].lower()
    assert "no impact" in reply["body"].lower()
    assert "proceed as planned" in reply["body"].lower()
    assert summary["writtenBy"] == "rules"
    assert reply["writtenBy"] == "rules"


def test_summary_never_says_no_impact_over_a_list_of_findings() -> None:
    scan = _scan(
        filesScanned=9,
        filesMatched=3,
        risk="high",
        groups=[
            {
                "prod": "ORDER_ROLLUP_PUB",
                "note": "",
                "rows": [_finding(breaking=True)],
            }
        ],
        stats=_stats(breakingUsages=1, attributesImpacted=1),
    )
    summary = summarise(scan, VALS)
    reply = draft_reply(scan, VALS, summary)

    assert "no impact" not in _everything(summary)
    assert "no impact" not in reply["body"].lower()
    assert "proceed as planned" not in reply["body"].lower()
    assert "1 production table at risk" in summary["headline"]


def test_no_impact_is_never_claimed_over_files_that_could_not_be_read() -> None:
    scan = _scan(
        filesScanned=10,
        unreadable=[{"path": "pipelines/broken.sql", "why": "1 of 4 statements"}],
        stats=_stats(neverOpened=2, couldNotRead=1),
    )
    summary = summarise(scan, VALS)
    reply = draft_reply(scan, VALS, summary)

    assert "no impact" not in _everything(summary)
    assert "no impact" not in reply["body"].lower()
    assert "proceed as planned" not in reply["body"].lower()
    # 2 never opened plus 1 that could not be followed.
    assert "3 others could not be" in summary["headline"]
    assert "3 others could not be" in reply["body"]


def test_nothing_scanned_is_never_reported_as_no_impact() -> None:
    scan = _scan(filesScanned=0)
    summary = summarise(scan, VALS)
    reply = draft_reply(scan, VALS, summary)

    assert summary["headline"] == (
        "Nothing was scanned — there was no code to search"
    )
    assert "no impact" not in _everything(summary)
    assert "no impact" not in reply["body"].lower()
    assert "proceed as planned" not in reply["body"].lower()
    assert "no answer is possible yet" in reply["body"].lower()


# ---------------------------------------------------------------------------
# branch order
# ---------------------------------------------------------------------------


def test_lookup_failed_comes_after_nothing_was_scanned() -> None:
    # An empty scan also meets every condition for a failed lookup. Printing
    # "check the spelling" over an empty folder sends somebody hunting for a
    # typo that is not there.
    scan = _scan(filesScanned=0, lookupFailed=True)
    summary = summarise(scan, VALS)

    assert summary["headline"].startswith("Nothing was scanned")
    assert "spelling" not in _everything(summary)


def test_lookup_failed_prints_back_the_columns_it_did_read() -> None:
    scan = _scan(
        filesScanned=7,
        lookupFailed=True,
        attributes=[
            {
                "name": "MARKET_GRADE",
                "tableColumns": ["region_id", "market_tier", "opened_on"],
            }
        ],
    )
    summary = summarise(scan, VALS)
    reply = draft_reply(scan, VALS, summary)

    assert summary["headline"] == (
        "MARKET_GRADE was not found - nothing has been checked"
    )
    assert "market_tier" in summary["narrative"]
    assert "Check the spelling before replying." in summary["narrative"]
    assert any("Check the spelling of" in a for a in summary["actions"])
    assert any(
        "Do not reply to the upstream team" in a for a in summary["actions"]
    )
    assert "market_tier" in reply["body"]
    assert "proceed as planned" not in reply["body"].lower()
    assert "no impact" not in _everything(summary)


def test_lookup_failed_with_no_columns_says_the_repository_holds_none() -> None:
    scan = _scan(filesScanned=7, lookupFailed=True)
    summary = summarise(scan, VALS)

    assert (
        "Nothing in this repository writes down the columns of that table."
        in summary["narrative"]
    )


# ---------------------------------------------------------------------------
# how much the answer does not cover
# ---------------------------------------------------------------------------


def test_uncovered_count_sums_all_five_kinds_and_names_each_one() -> None:
    scan = _scan(
        filesScanned=20,
        maxHops=4,
        unreadable=[{"path": "a.sql"}, {"path": "b.sql"}],
        cutShort=[{"table": "stage_alpha"}],
        skippedInFolders=[f"build/gen_{n}.sql" for n in range(7)],
        skippedFolderNames=["build", "target"],
        fileTypesUnopened=[{"ext": ".ipynb", "count": 1}],
        stats=_stats(neverOpened=3, trailsCutShort=1),
    )
    summary = summarise(scan, VALS)
    reply = draft_reply(scan, VALS, summary)

    # 3 never opened + 2 not followed + 1 trail + 7 skipped + 1 unopened type.
    assert "14 others could not be" in summary["headline"]
    assert "14 others could not be" in reply["body"]

    narrative = summary["narrative"]
    assert "3 files could not be opened at all" in narrative
    assert "2 files could not be followed" in narrative
    assert (
        "7 code files sit in a folder Ripple is told to skip (build, target) "
        "and were never read" in narrative
    )
    assert "1 file is of a type Ripple does not open (.ipynb)" in narrative
    assert (
        "1 trail was stopped at 4 renames deep and was still going" in narrative
    )


def test_files_that_could_not_be_opened_come_first_in_bullets_and_actions() -> None:
    scan = _scan(
        filesScanned=20,
        unreadable=[{"path": "a.sql"}],
        stats=_stats(neverOpened=3),
    )
    summary = summarise(scan, VALS)

    assert summary["bullets"][0].startswith("3 files could not be opened at all")
    assert summary["actions"][0].startswith("Open the 3 files")


def test_the_cut_short_caveat_reads_the_hop_limit_off_the_scan() -> None:
    scan = _scan(
        filesScanned=5,
        maxHops=7,
        cutShort=[{"table": "stage_gamma"}],
        other=[_finding()],
        stats=_stats(trailsCutShort=1),
    )
    summary = summarise(scan, VALS)

    assert (
        "Ripple stopped following stage_gamma at 7 renames deep"
        in summary["narrative"]
    )
    assert any(
        "cut short by the hop limit rather than by the code" in b
        for b in summary["bullets"]
    )
    assert any(
        "Run the scan again, deeper" in a for a in summary["actions"]
    )


def test_a_trail_that_was_cut_short_is_never_described_as_ending() -> None:
    scan = _scan(
        filesScanned=5,
        maxHops=4,
        cutShort=[{"table": "stage_gamma"}],
        other=[_finding()],
    )
    summary = summarise(scan, VALS)

    assert "end at" not in summary["narrative"]
    assert "stopped following" in summary["narrative"]


# ---------------------------------------------------------------------------
# findings that reach no published table
# ---------------------------------------------------------------------------


def test_findings_reaching_no_published_table_are_called_unfinished() -> None:
    scan = _scan(
        filesScanned=8,
        other=[
            _finding(file="pipelines/one.sql"),
            _finding(file="pipelines/two.sql"),
            _finding(file="pipelines/three.sql"),
        ],
        reached=[{"table": "stage_beta", "note": "", "rows": []}],
    )
    summary = summarise(scan, VALS)
    reply = draft_reply(scan, VALS, summary)

    assert summary["headline"] == (
        "3 usages found - none of them reaching a table on your published list"
    )
    assert "not a clean result, an unfinished one" in summary["narrative"]
    assert "Those chains end at stage_beta." in summary["narrative"]
    assert "no impact" not in _everything(summary)
    assert "no impact" not in reply["body"].lower()
    assert "proceed as planned" not in reply["body"].lower()
    assert "in progress" in reply["body"].lower()


def test_a_published_table_that_stops_loading_owns_the_headline() -> None:
    scan = _scan(
        filesScanned=5,
        other=[_finding()],
        stopsLoading=[
            {"table": "daily_orders_pub"},
            {"table": "weekly_orders_pub"},
        ],
        stats=_stats(productionStopsLoading=2),
    )
    summary = summarise(scan, VALS)
    reply = draft_reply(scan, VALS, summary)

    assert summary["headline"] == "2 published tables stop being refreshed"
    # Never send the reader off to fix a production rule that matched
    # perfectly, one line under a table it matched.
    assert "none of them reaching" not in summary["headline"]
    assert "settings" not in summary["narrative"].lower()
    assert "settings" not in " ".join(summary["actions"]).lower()
    assert "stale data" in reply["body"]
    assert "daily_orders_pub" in reply["body"]


def test_a_delivery_out_of_the_warehouse_names_its_destination() -> None:
    scan = _scan(
        filesScanned=5,
        other=[_finding()],
        feeds=[{"uri": "gs://partner-drop/market"}],
        stats=_stats(feedsBroken=1),
    )
    summary = summarise(scan, VALS)
    reply = draft_reply(scan, VALS, summary)

    assert summary["headline"] == "1 delivery out of the warehouse breaks"
    assert "gs://partner-drop/market" in summary["narrative"]
    assert "gs://partner-drop/market" in reply["body"]
    assert "settings" not in summary["narrative"].lower()


# ---------------------------------------------------------------------------
# statements that name the column but carry it nowhere
# ---------------------------------------------------------------------------


def test_only_statements_that_name_the_column_are_warned_about() -> None:
    scan = _scan(
        filesScanned=6,
        referencedHere=[
            {
                "kind": "row access policy",
                "table": "customer_rollup",
                "namesColumns": True,
            },
            {"kind": "index", "table": "stage_zeta", "namesColumns": False},
        ],
    )
    summary = summarise(scan, VALS)
    reply = draft_reply(scan, VALS, summary)

    assert summary["headline"] == (
        "No lineage, but 1 statement names MARKET_GRADE directly"
    )
    assert "row access policy on customer_rollup" in summary["narrative"]
    assert "stage_zeta" not in summary["narrative"]
    assert "stop working on the day the column changes" in summary["narrative"]
    assert any(
        a.startswith("Update the row access policy on customer_rollup")
        for a in summary["actions"]
    )
    assert "row access policy on customer_rollup" in reply["body"]
    assert "no impact" not in reply["body"].lower()
    assert "proceed as planned" not in reply["body"].lower()


# ---------------------------------------------------------------------------
# confirmed impact
# ---------------------------------------------------------------------------


def test_the_letter_counts_each_finding_once_across_groups() -> None:
    shared = _finding(file="pipelines/shared.sql", breaking=True)
    only_b = _finding(file="pipelines/only_b.sql", breaking=True)
    scan = _scan(
        filesScanned=11,
        risk="high",
        groups=[
            {"prod": "ALPHA_PUB", "note": "", "rows": [shared]},
            {"prod": "BETA_PUB", "note": "", "rows": [shared, only_b]},
        ],
        stats=_stats(breakingUsages=2, attributesImpacted=1),
    )
    summary = summarise(scan, VALS)
    reply = draft_reply(scan, VALS, summary)

    assert "2 pipeline objects feeding 2 production tables" in reply["body"]
    assert "3 pipeline objects" not in reply["body"]
    assert "2 pipeline objects" in summary["narrative"]


def test_a_usage_with_no_local_fix_asks_the_upstream_team() -> None:
    scan = _scan(
        filesScanned=11,
        risk="high",
        groups=[
            {
                "prod": "REVENUE_PUB",
                "note": "",
                "rows": [
                    _finding(
                        breaking=True,
                        noLocalFix=True,
                        logic="Ranking logic",
                    )
                ],
            }
        ],
        stats=_stats(breakingUsages=1, attributesImpacted=1),
    )
    summary = summarise(scan, VALS)
    reply = draft_reply(scan, VALS, summary)

    assert summary["headline"] == (
        "Ranking logic has no replacement — escalate before the date"
    )
    assert "orders or deduplicates" in reply["body"]
    assert "retain this one" in reply["body"]
    assert "Impact confirmed." in reply["body"]
    assert "What we will do before the effective date:" in reply["body"]
    assert "proceed as planned" not in reply["body"].lower()


def test_breaking_findings_with_unread_files_are_never_all_fixable() -> None:
    scan = _scan(
        filesScanned=11,
        risk="high",
        groups=[
            {
                "prod": "ALPHA_PUB",
                "note": "",
                "rows": [_finding(breaking=True)],
            }
        ],
        stats=_stats(neverOpened=1, breakingUsages=1),
    )
    summary = summarise(scan, VALS)
    reply = draft_reply(scan, VALS, summary)

    assert summary["headline"] == (
        "1 production table at risk, and 1 file Ripple could not follow"
    )
    assert "all fixable in code" not in _everything(summary)
    assert (
        "1 file could not be opened at all on this machine" in reply["body"]
    )
    assert "This assessment does not cover them" in reply["body"]


def test_findings_that_do_not_break_say_so_plainly() -> None:
    scan = _scan(
        filesScanned=11,
        risk="low",
        groups=[
            {"prod": "ALPHA_PUB", "note": "", "rows": [_finding(breaking=False)]}
        ],
    )
    summary = summarise(scan, VALS)

    assert summary["headline"] == "Labels change, but nothing breaks"
    assert "no impact" not in _everything(summary)


# ---------------------------------------------------------------------------
# SELECT * caveat
# ---------------------------------------------------------------------------


def test_star_tables_add_a_sentence_to_the_no_findings_narrative() -> None:
    scan = _scan(
        filesScanned=6,
        starTables=["stage_delta", "stage_epsilon"],
    )
    summary = summarise(scan, VALS)

    assert (
        "2 tables on the way are built with SELECT *" in summary["narrative"]
    )
    assert "worked out rather than read" in summary["narrative"]


def test_star_tables_add_a_sentence_to_the_nothing_published_narrative() -> None:
    scan = _scan(
        filesScanned=6,
        other=[_finding()],
        starTables=["stage_delta"],
    )
    summary = summarise(scan, VALS)

    assert (
        "1 table on the way is built with SELECT *" in summary["narrative"]
    )
