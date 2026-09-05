"""The two folders of Airflow DAGs.

His pipeline has ``src/dag`` and ``src/dt_dag`` full of Python. Some of those
files hold their SQL as a string and Ripple reads it. Plenty of others name a
``.sql`` file and run that -- either by opening it, or by handing Airflow a
filename and letting ``template_searchpath`` find it. And a few build the
statement by adding short pieces of text together, so it never exists in the
file as one thing to read.

Ripple used to get nothing from any of those and say nothing about them, which
made a DAG running the most important query in the pipeline look exactly like a
config file with nothing in it. That is the same failure as everything else here:
silence being read as "nothing to report".
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ripple.config import Settings                              # noqa: E402
from ripple.scanner.repo import RepoIndex                       # noqa: E402
from ripple.scanner.sqlread import parse_repo, short_name       # noqa: E402

REAL_SQL = (
    "CREATE OR REPLACE TABLE `p.stage.customer_main_umdl` AS\n"
    "SELECT cm13, market_code FROM `p.raw.customer_demographics`;\n"
)


def _repo(tmp_path: Path, files: dict):
    for rel, text in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    cfg = Settings()
    cfg.sql_dialect = "bigquery"
    cfg.repo_path = tmp_path
    idx = RepoIndex.build(tmp_path, cfg)
    return idx, parse_repo(idx, cfg)


def test_sql_built_with_format_is_read(tmp_path):
    """A great many DAGs build their SQL with .format(). The placeholders are
    filled in before parsing, so this already works -- pinned so it stays that
    way."""
    _, parsed = _repo(tmp_path, {"src/dag/job.py": '''
TEMPLATE = """
CREATE OR REPLACE TABLE `{tgt}.{dataset}.card_main_umdl` AS
SELECT cm13, market_code FROM `{src}.raw.card_source`
"""
sql = TEMPLATE.format(tgt=TGT, dataset=DS, src=SRC)
'''})
    assert "card_main_umdl" in {short_name(s.target) for s in parsed.statements}
    assert any("card_source" in {short_name(x).lower() for x in s.sources} for s in parsed.statements)


def test_sql_in_an_f_string_is_read(tmp_path):
    _, parsed = _repo(tmp_path, {"src/dag/job.py": '''
sql = f"""
CREATE OR REPLACE TABLE `{TGT}.stage.loyalty_umdl` AS
SELECT cm13, rwrd_pts FROM `{TGT}.raw.loyalty_source`
"""
'''})
    assert "loyalty_umdl" in {short_name(s.target) for s in parsed.statements}


def test_a_dag_that_opens_a_sql_file_is_linked_to_it(tmp_path):
    """The DAG holds no SQL, so it is not a finding and not a gap -- the query
    was read on its own account. It is not empty either, and that is the thing
    worth saying."""
    _, parsed = _repo(tmp_path, {
        "src/sql/DML/transform/cmdl_TL_customer_main_umdl.sql": REAL_SQL,
        "src/dag/job.py": '''
QUERY_FILE = "src/sql/DML/transform/cmdl_TL_customer_main_umdl.sql"
with open(QUERY_FILE) as fh:
    sql = fh.read()
''',
    })
    links = [r for r in parsed.runs_sql_from if r["file"] == "src/dag/job.py"]
    assert len(links) == 1
    assert links[0]["runs"] == "src/sql/DML/transform/cmdl_TL_customer_main_umdl.sql"
    # And it is not reported as a problem, because there is no problem.
    assert not any(u["file"] == "src/dag/job.py" for u in parsed.unreadable)


def test_a_bare_filename_is_matched_too(tmp_path):
    """Airflow's template_searchpath means the DAG names the file and nothing
    else -- no path, no open()."""
    _, parsed = _repo(tmp_path, {
        "src/sql/DML/transform/cmdl_TL_account_main_umdl.sql": REAL_SQL,
        "src/dag/job.py": '''
build = BigQueryInsertJobOperator(
    task_id="build_account_main",
    configuration={"query": {"query": "cmdl_TL_account_main_umdl.sql"}},
)
''',
    })
    links = [r for r in parsed.runs_sql_from if r["runs"]]
    assert len(links) == 1
    assert links[0]["runs"].endswith("cmdl_TL_account_main_umdl.sql")


def test_a_sql_file_that_is_not_here_is_a_gap(tmp_path):
    """The real hole. The DAG runs a query Ripple has never read, so no scan can
    cover it, and saying nothing would leave a clean result standing over it."""
    _, parsed = _repo(tmp_path, {"src/dag/job.py": '''
run = BigQueryInsertJobOperator(
    configuration={"query": {"query": "cmdl_TL_somewhere_else.sql"}})
'''})
    gap = next(u for u in parsed.unreadable if u["file"] == "src/dag/job.py")
    assert "not in this repository" in gap["reason"]
    assert "cmdl_TL_somewhere_else.sql" in gap["reason"]


def test_sql_glued_together_from_short_strings_is_reported(tmp_path):
    """No single piece is long enough to recognise and the statement never
    exists as one thing to read -- so it is listed to be checked by hand rather
    than counted as an empty file.

    Pieces separated only by whitespace ARE welded back together now, so part of
    this one is read: the run after ``+ SRC +`` joins up on its own. A variable
    in the middle is what nothing can weld across, which is why the file is
    still on the list -- and the wording has to say SOME of it, because saying
    none of it was read when some of it was sends somebody looking for the
    wrong thing."""
    _, parsed = _repo(tmp_path, {"src/dag/job.py": '''
sql = (
    "CREATE OR REPLACE TABLE `" + TGT + ".stage.merchant_umdl` AS "
    "SELECT cm13, merchant_id "
    "FROM `" + SRC + ".raw.merchant_source`"
)
'''})
    gap = next(u for u in parsed.unreadable if u["file"] == "src/dag/job.py")
    assert "could not be taken out of it" in gap["reason"], gap["reason"]
    assert "some of" in gap["reason"], gap["reason"]


def test_an_ordinary_python_file_is_left_alone(tmp_path):
    """The opposite failure. Most Python in a repository is not SQL at all, and
    a gap reported for every helper module is a list nobody reads."""
    _, parsed = _repo(tmp_path, {"src/dag/util.py": '''
import os

def chunk(items, size=100):
    for n in range(0, len(items), size):
        yield items[n:n + size]
'''})
    assert parsed.unreadable == []
    assert parsed.runs_sql_from == []
