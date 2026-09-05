"""Choosing the repository folder and the SQL dialect on screen.

Online these are environment variables. Offline nobody is going to set one, so
they are asked for — and the answers have to survive a restart, survive the
folder being moved, and never quietly fall back to reading BigQuery as generic
SQL.
"""
from __future__ import annotations

import json

import pathlib

import pytest

from conftest import MOCKREPO
from ripple_offline import prefs


def test_the_default_dialect_is_bigquery(clean_home):
    """Our stack. A wrong default here inverts answers rather than blurring them."""
    assert prefs.load()["sqlDialect"] == "bigquery"


def test_the_hop_limit_matches_the_shared_engine(clean_home):
    """The number of renames Ripple follows is not a setting of this build's own.

    It was hard-coded to 4 here while the engine moved to 10, which would have
    shipped the old, too-shallow behaviour to the one machine where nobody can
    check it. Offline is a wrapper, so this number has to come from the engine.
    """
    from ripple.config import Settings

    assert prefs.DEFAULTS["maxHops"] == Settings().max_hops
    assert prefs.load()["maxHops"] == Settings().max_hops


def test_the_hop_limit_can_be_raised_far_enough_to_follow_a_cut_trail(clean_home):
    """The result screen offers to follow a cut-short trail at twice the depth.
    A ceiling below that would make the button do nothing."""
    from ripple.config import Settings

    assert prefs.max_hops_ceiling() >= Settings().max_hops * 2
    saved = prefs.save({"repoPath": str(MOCKREPO), "maxHops": 20, "prodTables": "_PROD"})
    assert saved["maxHops"] == 20


def test_nothing_is_configured_on_a_fresh_machine(clean_home):
    assert prefs.configured(prefs.load()) is False


def test_settings_survive_a_restart(clean_home):
    prefs.save({"repoPath": str(MOCKREPO), "sqlDialect": "snowflake", "maxHops": 5, "prodTables": "_PROD"})
    again = prefs.load()
    assert again["repoPath"] == str(MOCKREPO)
    assert again["sqlDialect"] == "snowflake"
    assert again["maxHops"] == 5
    assert prefs.configured(again) is True


def test_the_settings_file_is_readable_by_a_person(clean_home):
    prefs.save({"repoPath": str(MOCKREPO), "sqlDialect": "bigquery", "maxHops": 4, "prodTables": "_PROD"})
    written = json.loads((clean_home / "ripple-settings.json").read_text(encoding="utf-8"))
    assert written["repoPath"] == str(MOCKREPO)
    assert written["sqlDialect"] == "bigquery"


def test_a_damaged_settings_file_does_not_stop_ripple_starting(clean_home):
    (clean_home / "ripple-settings.json").write_text("{not json at all", encoding="utf-8")
    values = prefs.load()
    assert values["sqlDialect"] == "bigquery" and values["repoPath"] == ""


def test_a_dialect_that_does_not_exist_is_refused(clean_home):
    assert not prefs.valid_dialect("klingon")
    saved = prefs.save({"repoPath": str(MOCKREPO), "sqlDialect": "klingon", "maxHops": 4, "prodTables": "_PROD"})
    assert saved["sqlDialect"] == "bigquery"


def test_every_offered_dialect_is_one_sqlglot_really_knows():
    """An option that cannot work is worse than a missing one: it gets picked,
    saved, and then quietly reads everything as generic SQL anyway."""
    from sqlglot import Dialect
    for choice in prefs.dialects():
        assert choice["id"] == "" or choice["id"] in Dialect.classes


def test_the_label_defaults_to_the_folder_name(clean_home):
    saved = prefs.save({"repoPath": str(MOCKREPO), "sqlDialect": "bigquery", "maxHops": 4, "prodTables": "_PROD"})
    assert saved["repoLabel"] == "mockrepo"


# ── which tables count as the ones this team publishes ─────────────────────
def test_the_published_table_rule_is_asked_for_and_remembered(clean_home):
    """Online this is an environment variable. Offline there is nobody to set
    one, and leaving it at _PROD on a repository that names nothing _PROD is
    what turns a real impact into a confident "no impact"."""
    prefs.save({"repoPath": str(MOCKREPO), "sqlDialect": "bigquery", "maxHops": 4,
                "prodTables": "_UMDL, _GDI"})
    assert prefs.load()["prodTables"] == "_UMDL, _GDI"


def test_the_rule_reaches_the_shared_engine(clean_home):
    from ripple.config import settings
    prefs.apply(prefs.save({"repoPath": str(MOCKREPO), "sqlDialect": "bigquery",
                            "maxHops": 4, "prodTables": "_UMDL, _GDI"}))
    assert settings.is_production_table("card_pub_pvt_guid_umdl") is True
    assert settings.is_production_table("sales_prod") is False


def test_an_empty_rule_is_not_given_rather_than_calling_everything_safe(clean_home):
    """An empty box means no table is ever production, which would report every
    repository on earth as clean. It used to fall back to what Ripple shipped
    with -- and on a warehouse naming its published tables anything other than
    _PROD, that matched nothing and read exactly the same way.

    So an empty box is now NOT GIVEN: Ripple is not set up, and the scan route
    refuses rather than answering against a rule nobody chose."""
    saved = prefs.save({"repoPath": str(MOCKREPO), "sqlDialect": "bigquery",
                        "maxHops": 4, "prodTables": "   "})
    assert saved["prodTables"] == ""
    assert prefs.configured(saved) is False, "a folder alone is not set up"
    prefs.apply(saved)
    from ripple.config import settings
    assert settings.has_production() is False


PASTED = """Table name\tOwner
• cust360_market_lookup\tPriya
• cust360_address_book\tMarcus
`sales_daily_summary`,
_UMDL
"""


def test_a_pasted_list_survives_a_restart_and_can_be_edited_again(clean_home):
    """Two hundred table names do not fit in the sentence "the rule", so what
    was pasted is kept exactly and handed back to the box, not a tidied version
    of somebody's list."""
    prefs.save({"repoPath": str(MOCKREPO), "sqlDialect": "bigquery", "maxHops": 4,
                "prodTables": PASTED})
    again = prefs.load()
    assert again["prodTables"].strip() == PASTED.strip()
    assert "\n" in again["prodTables"], "a long list must not be flattened to one line"


def test_a_pasted_list_reaches_the_engine_as_exact_table_names(clean_home):
    from ripple.config import settings
    prefs.apply(prefs.save({"repoPath": str(MOCKREPO), "sqlDialect": "bigquery",
                            "maxHops": 4, "prodTables": PASTED}))
    assert settings.is_production_table("cust360_market_lookup") is True
    assert settings.is_production_table("sales_daily_summary") is True
    # An exact name is exact: a staging copy of it is not a published table.
    assert settings.is_production_table("stg_cust360_market_lookup") is False
    # And a pattern in the same paste goes on behaving like a pattern.
    assert settings.is_production_table("card_guid_umdl") is True
    rule = settings.production()
    assert len(rule.names) == 3 and len(rule.patterns) == 1


def test_the_settings_file_holds_the_whole_paste(clean_home):
    prefs.save({"repoPath": str(MOCKREPO), "sqlDialect": "bigquery", "maxHops": 4,
                "prodTables": PASTED})
    written = json.loads((clean_home / "ripple-settings.json").read_text(encoding="utf-8"))
    assert "cust360_address_book" in written["prodTables"]


# ── a folder that is not where it was ──────────────────────────────────────
def test_a_good_folder_says_how_much_it_holds():
    verdict = prefs.check_folder(MOCKREPO)
    assert verdict["ok"] and verdict["files"] > 15
    assert "file" in verdict["message"]


def test_a_deleted_folder_says_so_plainly():
    verdict = prefs.check_folder(r"D:\this\folder\was\deleted")
    assert not verdict["ok"] and verdict["state"] == "missing"
    assert "not on this machine any more" in verdict["message"]
    assert "deleted" in verdict["message"]        # names the folder it tried


def test_a_folder_that_is_really_a_file_says_so(tmp_path):
    f = tmp_path / "notafolder.txt"
    f.write_text("hello", encoding="utf-8")
    verdict = prefs.check_folder(f)
    assert not verdict["ok"] and "not a folder" in verdict["message"]


def test_a_folder_with_no_code_says_so(tmp_path):
    (tmp_path / "holiday.jpg").write_bytes(b"\x00")
    verdict = prefs.check_folder(tmp_path)
    assert not verdict["ok"] and verdict["state"] == "empty"
    assert "no files Ripple can read" in verdict["message"]


def test_no_folder_chosen_is_not_an_error_message_about_crashes():
    verdict = prefs.check_folder("")
    assert not verdict["ok"] and verdict["state"] == "unset"


# ── what the settings mean to the shared engine ────────────────────────────
def test_applying_settings_points_the_shared_engine_at_the_folder(clean_home):
    from ripple.config import settings
    prefs.apply(prefs.save({"repoPath": str(MOCKREPO), "sqlDialect": "bigquery", "maxHops": 4, "prodTables": "_PROD"}))
    assert str(settings.repo_path) == str(MOCKREPO)
    assert settings.sql_dialect == "bigquery"
    assert settings.repo_source == "folder"


def test_applying_settings_leaves_no_way_to_reach_out(clean_home):
    """Belt and braces: the engine is told there is no key and no repository to
    pull, rather than trusted to leave them alone."""
    from ripple.config import settings
    prefs.apply(prefs.load())
    assert settings.ai_key == ""
    assert settings.github_token == "" and settings.github_repo == ""
    assert settings.ai_available() is False


def test_history_is_kept_beside_the_program(clean_home):
    from ripple.config import settings
    prefs.apply(prefs.load())
    assert settings.db_path.parent == clean_home
    assert settings.serverless is False


def test_the_branch_reader_is_the_shared_one_and_not_a_second_copy():
    """It lived here once and the online build kept its own default of "main",
    so the two builds disagreed on screen about the same folder: this one read
    the folder and said nothing when there was nothing to say, and the other
    printed "Branch main" over every folder on earth.

    One copy now, in the engine both builds import. The tests for what it reads
    moved with it, into Codebase/tests/test_reading_the_branch.py.
    """
    from ripple.config import git_branch
    src = pathlib.Path(prefs.__file__).read_text(encoding="utf-8")
    assert "def git_branch(" not in src, (
        "prefs.py has its own git_branch again. Two copies of this drifted once "
        "and put a made-up branch name on one of the two screens."
    )
    assert callable(git_branch), "the shared branch reader is gone"


def test_both_builds_read_sql_as_the_same_language_by_default():
    """The dialect is not cosmetic, and the two builds used to disagree on it.

    This build set its own DEFAULT_DIALECT of "bigquery" while the shared engine
    defaulted to "" -- generic. So the batch-file Ripple and the packaged Ripple
    read the SAME folder as two different languages. Read as generic, a
    BigQuery-ism the parser does not know becomes an unreadable statement, the
    chain through it is never followed, and the answer comes back cleaner than
    the truth: the one failure this product exists to prevent.

    Nothing caught it. Each build's tests only ever asked its own build. It was
    found by running both against one folder and comparing every value in the
    answer -- see tools/compare_builds.py.
    """
    from ripple.config import DEFAULT_DIALECT as shared, Settings
    assert prefs.DEFAULT_DIALECT == shared, (
        "the packaged build has its own dialect default again"
    )
    assert Settings().sql_dialect == shared, (
        "a fresh engine does not start on the shared default, so the two builds "
        "will read the same folder as different languages"
    )
    src = pathlib.Path(prefs.__file__).read_text(encoding="utf-8")
    assert 'DEFAULT_DIALECT = "' not in src, (
        "prefs.py defines its own dialect default again rather than importing it"
    )
