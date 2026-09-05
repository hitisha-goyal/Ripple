"""Does this copy of Ripple work on this machine?

    python -m unittest tests.test_smoke -v

Run from the folder holding run.py. unittest, not pytest, because pytest is one
more thing to install and the whole point of this copy is that nothing is.

These are not the product's tests -- those live with the product and there are
several hundred. These answer one question: has everything arrived, and does it
work here. Somebody who has just copied this folder onto a locked-down laptop
needs that answered in five seconds, and needs it answered by something other
than "the browser looks all right to me".
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))


class TheParserArrived(unittest.TestCase):
    """The one thing that could not be written by a chat and had to be copied."""

    def test_the_sql_parser_is_here_and_loads(self):
        import sqlglot
        self.assertTrue(sqlglot.__version__, "sqlglot loaded but has no version")

    def test_the_parser_folder_sits_beside_the_code(self):
        self.assertTrue((HERE / "sqlglot").is_dir(),
                        "the sqlglot folder is missing from beside run.py")

    def test_it_really_parses_sql(self):
        import sqlglot
        tree = sqlglot.parse_one("SELECT a, b AS c FROM t", read="bigquery")
        self.assertEqual([e.alias_or_name for e in tree.expressions], ["a", "c"])


class NothingNeedsInstalling(unittest.TestCase):
    """The reason this copy exists. If any of these is importable the copy has
    been assembled on the wrong machine, and it will fail on the locked-down one
    at the first request rather than here."""

    def test_the_web_layer_is_pythons_own(self):
        from ripple_offline import webserver
        self.assertTrue(hasattr(webserver, "Router"))

    def test_nothing_imports_fastapi(self):
        for name in ("fastapi", "uvicorn", "pydantic", "httpx"):
            with self.subTest(package=name):
                self.assertNotIn(name, sys.modules,
                                 f"{name} was imported - this copy is not install-free")


class TheEngineArrived(unittest.TestCase):
    def test_every_engine_file_is_here(self):
        for name in ("config", "production", "catalog", "narrative", "notification",
                     "progress", "store", "build_info"):
            with self.subTest(module=name):
                self.assertTrue((HERE / "ripple" / f"{name}.py").is_file())
        for name in ("repo", "templating", "rescue", "dialectcompat",
                     "sqlread", "lineage"):
            with self.subTest(module=name):
                self.assertTrue((HERE / "ripple" / "scanner" / f"{name}.py").is_file())

    def test_the_screens_are_here(self):
        for name in ("index.html", "app.js", "styles.css"):
            with self.subTest(file=name):
                self.assertTrue((HERE / "web" / name).is_file(),
                                f"web/{name} is missing - the screens will not draw")


class ItFollowsAColumn(unittest.TestCase):
    """The whole product, end to end, on a repository written here and thrown
    away. If this passes, everything under the screens works on this machine."""

    def test_a_renamed_column_is_followed_to_the_published_table(self):
        from ripple.config import Settings
        from ripple.scanner.lineage import trace
        from ripple.scanner.repo import RepoIndex
        from ripple.scanner.sqlread import parse_repo

        files = {
            "a.sql": "CREATE OR REPLACE TABLE stage_one AS\n"
                     "SELECT id, cm13 AS customer_code FROM customer_demographics;",
            "b.sql": "CREATE OR REPLACE TABLE final_published AS\n"
                     "SELECT id, customer_code FROM stage_one\n"
                     "WHERE customer_code IS NOT NULL;",
        }
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name, body in files.items():
                (root / name).write_text(body, encoding="utf-8")
            cfg = Settings()
            cfg.repo_path = root
            cfg.sql_dialect = "bigquery"
            cfg.set_production("_published")
            idx = RepoIndex.build(root, cfg)
            parsed = parse_repo(idx, cfg)
            out = trace(idx, parsed,
                        [{"table": "customer_demographics", "attrs": ["cm13"]}],
                        change_type="removal", cfg=cfg).to_dict()

        self.assertEqual([g["prod"] for g in out["groups"]], ["final_published"],
                         "the rename was not followed to the published table")
        self.assertNotEqual(out["risk"], "none")
        self.assertEqual(out["stats"]["couldNotRead"], 0, out["unreadable"])

    def test_it_refuses_to_say_no_impact_over_a_file_it_could_not_read(self):
        """The rule the whole tool rests on. "I found nothing" and "I could not
        look" are different answers, and printed the same the second one is a
        lie that reads as a promise."""
        from ripple.config import Settings
        from ripple.scanner.lineage import trace
        from ripple.scanner.repo import RepoIndex
        from ripple.scanner.sqlread import parse_repo

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "fine.sql").write_text(
                "CREATE OR REPLACE TABLE t AS SELECT zz FROM elsewhere;", encoding="utf-8")
            (root / "broken.sql").write_text(
                "THIS IS NOT SQL cm13 customer_demographics {{{", encoding="utf-8")
            cfg = Settings()
            cfg.repo_path = root
            cfg.sql_dialect = "bigquery"
            cfg.set_production("_published")
            idx = RepoIndex.build(root, cfg)
            parsed = parse_repo(idx, cfg)
            out = trace(idx, parsed,
                        [{"table": "customer_demographics", "attrs": ["cm13"]}],
                        change_type="removal", cfg=cfg).to_dict()

        self.assertNotEqual(out["risk"], "none",
                            'risk read "none" over a file that could not be read')
        self.assertFalse(out["coverage"]["complete"])


class TheServiceAnswers(unittest.TestCase):
    """The routes the screens call, without starting a browser."""

    def test_health_carries_everything_the_screen_reads(self):
        from ripple_offline import app as service
        out = service.health()
        for key in ("ok", "build", "repo", "catalog", "sqlDialect", "maxHops",
                    "production", "productionSet", "offline", "folder", "dialects"):
            with self.subTest(key=key):
                self.assertIn(key, out, f"the screen reads {key} and it is missing")
        for key in ("files", "statements", "unreadable", "kinds", "unknownExt",
                    "heldOnline", "inSkippedDirs"):
            with self.subTest(repo_key=key):
                self.assertIn(key, out["repo"])

    def test_the_settings_file_sits_beside_ripple(self):
        from ripple_offline import paths
        self.assertEqual(paths.settings_file().parent, paths.app_dir())

    def test_a_scan_with_no_tables_is_refused_with_a_sentence(self):
        from ripple_offline import app as service
        from ripple_offline.webserver import HTTPError
        with self.assertRaises(HTTPError) as caught:
            service.scan({"upstream": []})
        self.assertIn("upstream", str(caught.exception).lower())


class ItCannotReachTheNetwork(unittest.TestCase):
    def test_the_outbound_guard_is_installed_when_ripple_starts(self):
        from ripple_offline import nonet
        nonet.install()
        self.assertTrue(nonet.installed())


if __name__ == "__main__":
    unittest.main(verbosity=2)
