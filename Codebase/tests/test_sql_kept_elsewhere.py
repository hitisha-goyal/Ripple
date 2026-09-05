"""SQL that is not in a .sql file, and SQL that is not written as SQL at all.

Every shape here measured a clean, calm, complete answer over none of the
picture: the statement that builds the published table was sitting in the file
in plain sight, and no scan could reach it.

    Airflow YAML     sql: |                     a block scalar
    Oozie XML        <script>, <![CDATA[        element text
    a shell job      bq query <<EOF             a heredoc
    a BigQuery job   EXECUTE IMMEDIATE '...'    the statement, quoted

And the other half of the same problem. Handing 200 ordinary Kubernetes YAML
files to a SQL parser puts 200 entries on the "check by hand" list, which is the
one place Ripple admits what it missed. Flooding it is how a real miss stops
being seen.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from test_confident_over_less import scan                       # noqa: E402


# ── YAML ───────────────────────────────────────────────────────────────────
def test_sql_in_an_airflow_yaml_block_is_read(tmp_path):
    out = scan(tmp_path, {
        "dags/load.yaml": "task:\n"
                          "  id: load_final\n"
                          "  sql: |\n"
                          "    CREATE OR REPLACE TABLE final_published AS\n"
                          "    SELECT cm13 FROM customer_demographics;\n"})
    assert [g["prod"] for g in out["groups"]] == ["final_published"], out["groups"]
    assert out["stats"]["couldNotRead"] == 0, out["unreadable"]


def test_a_yaml_list_item_keeps_its_own_indent(tmp_path):
    """``- query: |`` indents its block past the key, not past the dash."""
    out = scan(tmp_path, {
        "dags/load.yml": "tasks:\n"
                         "  - name: build\n"
                         "    query: |\n"
                         "      CREATE OR REPLACE TABLE final_published AS\n"
                         "      SELECT cm13 FROM customer_demographics;\n"
                         "  - name: notify\n"
                         "    to: ops@example.com\n"})
    assert [g["prod"] for g in out["groups"]] == ["final_published"], out["groups"]


def test_a_one_line_yaml_query_is_read(tmp_path):
    out = scan(tmp_path, {
        "dags/load.yaml":
            'sql: "CREATE OR REPLACE TABLE final_published AS '
            'SELECT cm13 FROM customer_demographics"\n'})
    assert [g["prod"] for g in out["groups"]] == ["final_published"], out["groups"]


def test_the_line_a_yaml_finding_points_at_is_inside_the_block(tmp_path):
    """Every rewrite in this reader puts back the lines it swallowed, or a
    finding sends somebody to the wrong part of the file."""
    out = scan(tmp_path, {
        "dags/load.yaml": "# a comment\n"
                          "# another\n"
                          "task:\n"
                          "  sql: |\n"
                          "    CREATE OR REPLACE TABLE final_published AS\n"
                          "    SELECT cm13 FROM customer_demographics;\n"})
    rows = [r for g in out["groups"] for r in g["rows"]]
    hit = [ln["n"] for r in rows for ln in r["lines"] if ln.get("hit")]
    assert hit and all(n >= 5 for n in hit), hit


# ── XML ────────────────────────────────────────────────────────────────────
def test_sql_in_an_oozie_xml_script_element_is_read(tmp_path):
    out = scan(tmp_path, {
        "oozie/workflow.xml": "<workflow-app>\n"
                              "  <action name='load'>\n"
                              "    <hive><script>\n"
                              "      CREATE OR REPLACE TABLE final_published AS\n"
                              "      SELECT cm13 FROM customer_demographics;\n"
                              "    </script></hive>\n"
                              "  </action>\n"
                              "</workflow-app>\n"})
    assert [g["prod"] for g in out["groups"]] == ["final_published"], out["groups"]
    assert out["stats"]["couldNotRead"] == 0, out["unreadable"]


def test_sql_in_an_xml_cdata_section_is_read_and_unescaped(tmp_path):
    """CDATA is how a query with a ``<`` in it gets written in XML at all."""
    out = scan(tmp_path, {
        "oozie/workflow.xml":
            "<workflow><query><![CDATA[\n"
            "CREATE OR REPLACE TABLE final_published AS\n"
            "SELECT cm13 FROM customer_demographics WHERE cm13 &lt; 100;\n"
            "]]></query></workflow>\n"})
    assert [g["prod"] for g in out["groups"]] == ["final_published"], out["groups"]


# ── a shell heredoc ────────────────────────────────────────────────────────
def test_sql_in_a_shell_heredoc_is_read(tmp_path):
    out = scan(tmp_path, {
        "bin/load.sh": "#!/bin/sh\n"
                       "bq query --use_legacy_sql=false <<EOF\n"
                       "CREATE OR REPLACE TABLE final_published AS\n"
                       "SELECT cm13 FROM customer_demographics;\n"
                       "EOF\n"})
    assert [g["prod"] for g in out["groups"]] == ["final_published"], out["groups"]
    assert out["stats"]["couldNotRead"] == 0, out["unreadable"]


def test_a_quoted_heredoc_tag_is_read_too(tmp_path):
    """Quoting the tag is how a script stops the shell touching the SQL."""
    body = "bq query <<-'SQL'\n" \
           "CREATE OR REPLACE TABLE final_published AS\n" \
           "SELECT cm13 FROM customer_demographics;\n" \
           "SQL\n"
    out = scan(tmp_path, {"bin/load.sh": body})
    assert [g["prod"] for g in out["groups"]] == ["final_published"], out["groups"]


# ── the "check by hand" list ───────────────────────────────────────────────
def test_ordinary_config_files_no_longer_flood_the_check_by_hand_list(tmp_path):
    """Measured before this: twelve ordinary Kubernetes files and one genuinely
    broken query gave couldNotRead 13, sorted alphabetically, with the real
    failure at the bottom."""
    files = {f"k8s/dep{i}.yaml": ("apiVersion: apps/v1\nkind: Deployment\n"
                                  f"metadata:\n  name: svc-{i}\n"
                                  "spec:\n  replicas: 2\n")
             for i in range(12)}
    files["zz_broken.sql"] = ("CREATE OR REPLACE TABLE final_published AS\n"
                              "SELECT cm13 FROM customer_demographics\n"
                              "  THIS IS NOT SQL AT ALL ((( ;\n")
    out = scan(tmp_path, files)
    assert [u["file"] for u in out["unreadable"]] == ["zz_broken.sql"], out["unreadable"]


def test_the_check_by_hand_list_puts_the_sql_like_files_first(tmp_path):
    """Two files Ripple could not read. One is a query; one is a program that
    happens to mention SQL. Alphabetical order puts the wrong one first."""
    out = scan(tmp_path, {
        "a_script.py": "def go():\n    run('SELECT this is not valid sql at all ((( ')\n",
        "z_query.sql": "CREATE OR REPLACE TABLE final_published AS\n"
                       "SELECT cm13 FROM customer_demographics ((( ;\n",
    })
    assert out["unreadable"][0]["file"] == "z_query.sql", out["unreadable"]


def test_a_yaml_that_plainly_holds_sql_it_could_not_take_out_is_still_reported(tmp_path):
    """The guard on the silence. Skipping non-SQL YAML must not become skipping
    a YAML that holds a query Ripple failed to mine."""
    out = scan(tmp_path, {
        "dags/load.yaml": "steps:\n"
                          "  - run: |\n"
                          "      CREATE OR REPLACE TABLE final_published AS\n"
                          "      SELECT cm13 FROM customer_demographics;\n"})
    assert out["stats"]["couldNotRead"] == 1, out["unreadable"]
    assert out["risk"] == "unknown", out["risk"]


def test_a_yaml_naming_a_sql_file_that_is_not_here_is_reported(tmp_path):
    """An Airflow YAML writes the filename with no quotes round it, so the
    quoted-string rule that covers .py files found nothing in it at all."""
    out = scan(tmp_path, {"dags/load.yaml": "task:\n  sql: queries/load_final.sql\n"})
    assert out["stats"]["couldNotRead"] == 1, out["unreadable"]
    assert "load_final.sql" in out["unreadable"][0]["reason"]


# ── SQL written as text and run later ──────────────────────────────────────
IMMEDIATE = ("EXECUTE IMMEDIATE '''CREATE OR REPLACE TABLE final_published AS "
             "SELECT cm13 FROM customer_demographics''';")


def test_a_plain_execute_immediate_is_read_and_followed(tmp_path):
    out = scan(tmp_path, {"a.sql": IMMEDIATE})
    assert [g["prod"] for g in out["groups"]] == ["final_published"], out["groups"]
    assert out["stats"]["couldNotRead"] == 0, out["unreadable"]


def test_a_statement_run_as_text_says_so_on_the_row_and_on_a_card(tmp_path):
    """The line the row points at holds a quoted string, not the CREATE the row
    describes. Somebody who opens it expecting the statement doubts the finding
    rather than the label."""
    out = scan(tmp_path, {"a.sql": IMMEDIATE})
    assert [c["how"] for c in out["builtAsText"]] == ["EXECUTE IMMEDIATE"], out["builtAsText"]
    rows = [r for g in out["groups"] for r in g["rows"]]
    assert rows and all(r["builtAsText"] == "EXECUTE IMMEDIATE" for r in rows), rows


def test_an_execute_immediate_carries_on_down_the_chain(tmp_path):
    out = scan(tmp_path, {
        "a.sql": "EXECUTE IMMEDIATE '''CREATE OR REPLACE TABLE mid AS "
                 "SELECT cm13 AS mc FROM customer_demographics''';",
        "b.sql": "CREATE OR REPLACE TABLE final_published AS SELECT mc FROM mid;"})
    assert [g["prod"] for g in out["groups"]] == ["final_published"], out["groups"]


def test_a_formatted_execute_immediate_stays_unreadable(tmp_path):
    """FORMAT builds the table name out of a value. The statement never exists
    as text, so there is nothing to read -- and inventing the missing piece is
    the exact failure this reader exists to avoid."""
    out = scan(tmp_path, {
        "a.sql": "EXECUTE IMMEDIATE FORMAT('CREATE OR REPLACE TABLE %s AS "
                 "SELECT cm13 FROM customer_demographics', tgt);"})
    assert out["stats"]["couldNotRead"] == 1, out["unreadable"]
    assert out["risk"] == "unknown", out["risk"]


def test_a_concatenated_execute_immediate_stays_unreadable(tmp_path):
    out = scan(tmp_path, {
        "a.sql": "EXECUTE IMMEDIATE 'CREATE OR REPLACE TABLE stage_' || env || "
                 "'_mid AS SELECT cm13 FROM customer_demographics';"})
    assert out["stats"]["couldNotRead"] == 1, out["unreadable"]
    assert out["risk"] == "unknown", out["risk"]


def test_an_execute_immediate_with_a_placeholder_stays_unreadable(tmp_path):
    """A ``?`` is a value handed over when the job runs. The text is not
    complete without it."""
    out = scan(tmp_path, {
        "a.sql": "EXECUTE IMMEDIATE 'INSERT INTO final_published (cm13) "
                 "SELECT cm13 FROM customer_demographics WHERE cm13 = ?' USING v;"})
    assert out["stats"]["couldNotRead"] == 1, out["unreadable"]
