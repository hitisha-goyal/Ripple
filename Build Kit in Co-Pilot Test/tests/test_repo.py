from __future__ import annotations

"""Tests for the repository walk.

Every table and column name here is invented. Each test is written so that it
fails if the behaviour it names is missing, rather than merely passing over an
empty result.
"""

import os
from dataclasses import dataclass

import pytest

from ripple.scanner.repo import (
    RepoIndex,
    effective_ext,
    extract_markup_sql,
    extract_sql_blocks,
    sql_file_refs,
    unopened_code_types,
    written_tables,
)


@dataclass
class FakeSettings:
    """Stands in for ripple/config.py, which this window cannot see.

    Only the two settings the walk asks for.
    """

    skip_dirs: tuple[str, ...] = ("build", ".git")
    max_file_bytes: int = 2000


JOB_PY = "\n".join(
    [
        '"""Load the final table."""',
        "",
        'QUERY = """',
        "CREATE OR REPLACE TABLE final_published AS",
        "SELECT id, market_band FROM customer_demographics",
        '"""',
        "",
        'RUN_FILE = "queries/load_final.sql"',
        'writer.saveAsTable("marts.final_published")',
        'writer.saveAsTable("marts.final_published")',
        "",
    ]
)

WELD_PY = "\n".join(
    [
        'sql = "CREATE OR REPLACE TABLE final_published AS SELECT cm_band "',
        'sql += "FROM customer_demographics WHERE dt = @d"',
        "",
    ]
)

PIPELINE_YAML = "\n".join(
    [
        "tasks:",
        "  - name: load_final",
        "    sql: |-",
        "      CREATE OR REPLACE TABLE final_published AS",
        "      SELECT id, market_band FROM customer_demographics",
        "  - name: cleanup",
        "    bash_command: echo done",
        "",
    ]
)

LOAD_FINAL_SQL = "\n".join(
    [
        "-- builds the published table",
        "CREATE OR REPLACE TABLE final_published AS",
        "SELECT id, market_band",
        "FROM customer_demographics;",
        "",
    ]
)

TEMPLATED_SQL = "\n".join(
    [
        "CREATE OR REPLACE TABLE final_staging AS",
        "SELECT id FROM {{ source_table }};",
        "",
    ]
)


def _write(path, text: str, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(str(path), "w", encoding=encoding, newline="\n") as handle:
        handle.write(text)


@pytest.fixture()
def repo(tmp_path):
    """A small repository that itself lives under a folder called build.

    That parent folder is the point of the fixture: a repository which happens
    to sit under a skipped name must not read as empty.
    """
    root = tmp_path / "build" / "repo"

    # The byte-order mark is written on purpose. It is invisible in every
    # editor and it lands on the first statement of the file.
    _write(root / "src" / "load_final.sql", LOAD_FINAL_SQL, encoding="utf-8-sig")
    _write(root / "src" / "load_final.sql.j2", TEMPLATED_SQL)
    _write(root / "src" / "job.py", JOB_PY)
    _write(root / "src" / "weld.py", WELD_PY)
    _write(root / "dags" / "pipeline.yaml", PIPELINE_YAML)
    _write(root / "build" / "generated.sql", "SELECT 1;\n")
    _write(root / "notes.md", "# Notes on the pipeline.\n")
    _write(root / "analysis" / "report.ipynb", "{}\n")
    _write(root / "big.sql", "-- padding\n" * 300)

    index = RepoIndex.build(str(root), FakeSettings())
    return index


def test_only_useful_extensions_are_read_and_the_rest_are_counted(repo):
    assert repo.get("src/load_final.sql") is not None
    assert repo.get("src/job.py") is not None
    assert repo.get("src/job.py").lang == "py"
    assert repo.get("dags/pipeline.yaml") is not None

    # Passed over, but never silently: the next unlisted extension has to be
    # visible rather than absent.
    assert repo.get("notes.md") is None
    assert repo.get("analysis/report.ipynb") is None
    assert repo.unknown_ext == {".md": 1, ".ipynb": 1}


def test_unopened_code_types_drops_prose_and_keeps_the_unknown(repo):
    # A README is on every repository, so warning about it every time is how a
    # warning stops being read. A notebook could hold a middle hop.
    assert unopened_code_types(repo.unknown_ext) == {".ipynb": 1}


def test_skip_dirs_are_judged_inside_the_repository_only(repo):
    # The repository lives under a folder literally called build.
    assert "build" in repo.root.replace("\\", "/").split("/")
    assert repo.get("src/job.py") is not None

    assert repo.get("build/generated.sql") is None
    assert "build/generated.sql" in repo.in_skipped_dirs
    assert "build" in repo.skipped_dir_names


def test_a_file_too_large_is_reported_in_plain_english(repo):
    reasons = {one.path: one.reason for one in repo.skipped}
    assert "big.sql" in reasons
    assert "larger" in reasons["big.sql"]


def test_a_byte_order_mark_never_reaches_the_first_statement(repo):
    text = repo.get("src/load_final.sql").text
    assert not text.startswith("\\ufeff")
    assert text.startswith("-- builds the published table")


def test_effective_ext_looks_through_a_template_suffix_but_no_further():
    assert effective_ext("src/load_final.sql.j2") == ".sql"
    assert effective_ext("src/load_final.sql") == ".sql"
    # A backup read as a live file becomes "this table is built in two files".
    assert effective_ext("src/load_final.sql.bak") == ".bak"


def test_a_templated_query_is_read_as_sql(repo):
    templated = repo.get("src/load_final.sql.j2")
    assert templated is not None
    assert templated.lang == "sql"


def test_sql_in_a_triple_quoted_string_keeps_its_line(repo):
    job = repo.get("src/job.py")
    blocks = extract_sql_blocks(job)

    assert len(blocks) == 1
    body, offset = blocks[0]
    assert "CREATE OR REPLACE TABLE final_published" in body
    # The offset has to point at the real line of the real file, because that
    # is the only line anybody can go and open.
    assert offset == 3
    assert job.text.split("\n")[offset].startswith("CREATE OR REPLACE")


def test_a_statement_written_as_two_strings_is_one_statement(repo):
    welded = repo.get("src/weld.py")
    blocks = extract_sql_blocks(welded)

    # Read as one piece the first half parses on its own, and the scan comes
    # back with nothing missing over a job that rebuilds the published table.
    assert len(blocks) == 1
    body, offset = blocks[0]
    assert "FROM customer_demographics" in body
    assert offset == 0


def test_a_yaml_block_marker_with_a_dash_is_still_a_block(repo):
    dag = repo.get("dags/pipeline.yaml")
    blocks = extract_markup_sql(dag)

    assert len(blocks) == 1
    body, offset = blocks[0]
    assert body.startswith("CREATE OR REPLACE TABLE final_published")
    assert "SELECT id, market_band" in body
    assert offset == 3


def test_a_sql_file_reference_is_found_with_its_line(repo):
    job = repo.get("src/job.py")
    assert sql_file_refs(job) == [("queries/load_final.sql", 8)]


def test_a_write_target_is_found_once_not_twice(repo):
    job = repo.get("src/job.py")
    # The same table on two lines is one destination. Counted twice, the job
    # reports writing to two tables with the same name.
    assert written_tables(job) == ["final_published"]


def test_search_matches_whole_words_only(repo):
    # market_band is written in several files; market is written in none.
    assert repo.search(["market"]) == []

    paths = {one.path for one in repo.search(["market_band"])}
    assert "src/job.py" in paths
    assert "src/load_final.sql" in paths


def test_files_mentioning_gives_back_the_files_themselves(repo):
    names = {one.path for one in repo.files_mentioning(["market_band"])}
    assert "dags/pipeline.yaml" in names
    assert "src/weld.py" not in names


def test_paths_on_screen_are_repository_relative_with_forward_slashes(repo):
    for one in repo.files:
        assert "\\" not in one.path
        assert not one.path.startswith("/")
        assert os.path.isabs(one.abs_path)
