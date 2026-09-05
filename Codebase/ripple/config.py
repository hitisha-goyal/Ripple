"""Settings for a Ripple installation.

Everything that would differ between a laptop, a demo host and a real corporate
network lives here, so nothing has to be hunted for in code.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from . import providers
from .production import (           # noqa: F401  (re-exported for older callers)
    DEFAULT_PRODUCTION,
    DEFAULT_TEXT as DEFAULT_PRODUCTION_TEXT,
    ProductionRule,
    parse as parse_production_text,
    parse_production_rule,
)

BASE_DIR = Path(__file__).resolve().parent.parent

# Which tables are the ones this team publishes -- the tables a finding has to
# reach before anybody outside the team notices. Every organisation names them
# differently, and getting this wrong is the most expensive mistake Ripple can
# make: a change that really breaks three tables is reported as "no impact"
# purely because the tables are not called _PROD. So it is a setting, it is on
# screen, and findings that reach nothing on this list are still shown.
#
# Two shapes are accepted, side by side. A pasted list of the real table names
# is read as written -- that is the answer rather than a guess about it. A
# pattern is still a pattern, unchanged: a word beginning with an underscore
# matches the end of a table name (_PROD, _UMDL, _PUBLISHED), and one with a *
# is matched in full, so PROD_* works too and * on its own means every table.
# See ripple/production.py for how a paste is read.

# Which model Ripple asks, when a key has been given.
#
# There is no list of model names in this file any more. A hand-typed list is
# wrong within months, and then it tells somebody a model exists that does not
# -- which they discover at the moment they are trying to read an email. The
# list is fetched from whichever provider issued the key, which produces the
# real names and proves the key in the same call. See ripple/providers.py.
#
# The job is narrow: pull table and attribute names out of a forwarded, badly
# quoted email and return strict JSON, then write a few careful sentences from
# findings that are already worked out. That rewards instruction-following
# rather than breadth, so the preference order in providers.py leans towards
# the larger models, and any model the provider offers can still be chosen.


# Which SQL Ripple reads a repository as, when nobody has said otherwise.
#
# This was "" -- generic -- here, while the packaged build set its own default
# of "bigquery". So the two builds read the SAME folder as two different
# languages, and the dialect is not a cosmetic setting: read as generic, a
# BigQuery-ism the parser does not recognise becomes an unreadable statement,
# the chain through it is never followed, and the answer comes back cleaner than
# the truth. Comparing the two builds on one folder, this was the difference
# hiding underneath everything else.
#
# One value, here, read by both. Override it per machine with
# RIPPLE_SQL_DIALECT, or on the settings screen where a build has that control.
DEFAULT_DIALECT = "bigquery"


def git_branch(path: Path | str) -> str:
    """The branch a copied-out repository was on, read from the folder itself.

    A real fact when the folder is a git checkout, and nothing at all when it is
    not -- better than showing "main" because that is the usual answer.

    This lived only in the packaged build for a while, and the two builds then
    disagreed on screen about the same folder: the packaged one read the folder
    and said nothing when there was nothing to say, and this one printed
    "Branch main" over every folder on earth. One copy, here, where both reach
    it.
    """
    head = Path(str(path or "")) / ".git" / "HEAD"
    try:
        text = head.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    if text.startswith("ref:"):
        return text.split("/")[-1].strip()
    return text[:7] if text else ""     # a detached checkout: the commit itself


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default).strip()


def _env_any(names: tuple[str, ...], default: str = "") -> str:
    """First of several environment variables that is actually set."""
    for n in names:
        v = os.environ.get(n, "").strip()
        if v:
            return v
    return default


def _serverless() -> bool:
    return bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))


def _default_db() -> str:
    if os.environ.get("RIPPLE_DB"):
        return os.environ["RIPPLE_DB"].strip()
    return "/tmp/ripple.db" if _serverless() else str(BASE_DIR / "ripple.db")


@dataclass
class Settings:
    # ── is this a serverless host? ─────────────────────────────────────────
    # Vercel, Lambda and friends impose limits a laptop does not: the disk is
    # read-only apart from /tmp, the machine is thrown away between requests,
    # a request body cannot exceed about 4.5 MB, and a request is killed at
    # 60 seconds. Several defaults below change because of that, so the app
    # says what it will really do instead of promising laptop behaviour.
    serverless: bool = field(default_factory=_serverless)

    # ── where the code comes from ──────────────────────────────────────────
    # "folder" reads a directory on this machine. "github" pulls a repository
    # over the network with an access token. Either can be chosen on screen.
    repo_source: str = field(default_factory=lambda: _env("RIPPLE_REPO_SOURCE", "folder"))

    # ── which repository is scanned (folder mode) ──────────────────────────
    repo_path: Path = field(
        default_factory=lambda: Path(_env("RIPPLE_REPO", str(BASE_DIR / "mockrepo")))
    )
    repo_label: str = field(default_factory=lambda: _env("RIPPLE_REPO_LABEL", "mockrepo"))
    # Empty means "read it off the folder". It used to default to "main", so a
    # plain folder on somebody's disk showed "Branch main" on the Repository
    # step -- a specific, checkable-looking fact about a folder that has no
    # branch at all. See branch() below.
    repo_branch: str = field(default_factory=lambda: _env("RIPPLE_REPO_BRANCH", ""))

    # ── GitHub mode ────────────────────────────────────────────────────────
    # The token is a secret. It is only ever sent to GitHub as a header; it is
    # never logged, never saved to disk, and never returned by any route.
    github_repo: str = field(default_factory=lambda: _env("RIPPLE_GITHUB_REPO", ""))
    github_branch: str = field(default_factory=lambda: _env("RIPPLE_GITHUB_BRANCH", ""))
    github_token: str = field(
        default_factory=lambda: _env_any(("RIPPLE_GITHUB_TOKEN", "GITHUB_TOKEN"))
    )
    github_api: str = field(default_factory=lambda: _env("RIPPLE_GITHUB_API", "https://api.github.com"))
    github_timeout: float = field(default_factory=lambda: float(_env("RIPPLE_GITHUB_TIMEOUT", "30")))
    # How much compressed repository Ripple will pull in one go. Lower on a
    # serverless host, where the whole request is killed at 60 seconds: a clear
    # "that repository is too big for this host" beats a blank timeout.
    max_repo_bytes: int = field(
        default_factory=lambda: int(
            _env("RIPPLE_MAX_REPO_BYTES", "25000000" if _serverless() else "60000000")
        )
    )

    # Link template so a finding can jump to the real file. {path} and {line}
    # are filled in. Point this at your own Git host when you get there.
    repo_url_template: str = field(
        default_factory=lambda: _env("RIPPLE_REPO_URL_TEMPLATE", "")
    )

    # ── how the SQL is read ────────────────────────────────────────────────
    # One of: oracle, teradata, snowflake, hive, spark, postgres, mysql, tsql,
    # duckdb, bigquery, redshift, databricks, presto, trino, sqlite, "" (generic).
    sql_dialect: str = field(default_factory=lambda: _env("RIPPLE_SQL_DIALECT", DEFAULT_DIALECT))

    # How many renames deep to follow a column.
    #
    # This was 4, and 4 was measured to be wrong for the pipeline Ripple was
    # built for. That pipeline runs source -> foundation -> tmp -> run_datetime
    # -> union -> stage -> entity -> published, which is eight hops before a
    # published table is reached at all, and further again to the reports built
    # on top of it. On a generated repository of that exact shape, a limit of 4
    # found NO production tables; 8 found all of them; 10 finished every trail
    # with nothing left cut short. The cost of the change was 0.21s to 0.32s on
    # that repository -- a scan is dominated by looking up statements, not by
    # how deep it goes.
    #
    # A limit that is too low does not fail loudly. It reports "the chain ends
    # here and does not reach production", which is a sentence about this
    # number wearing the clothes of a sentence about the warehouse.
    #
    # ZERO means follow the trail until the CODE runs out, and that is now the
    # default. Ten was still a wall, just a further-off one, and the screen's
    # offer to follow twice as far did not get past it either: measured on a
    # 36-hop chain, ten renames cut the trail short, twenty cut it short, and
    # twenty-five -- the deepest the screen would offer -- cut it short as well.
    # There was no number a person could choose that produced an answer, and
    # every attempt cost another whole scan to be told the same thing.
    #
    # This is safe because the walk already carries a set of every
    # (table, column) it has been through, so a ring of tables closes on itself
    # whatever this is set to. The counter was a second guard that could only
    # ever truncate a real answer. Measured on a real BigQuery warehouse of
    # 7,304 files: following to the end costs 10.6s against 10.5s at ten hops,
    # for the same tables plus the ones that were past the limit.
    #
    # A limit somebody sets on purpose is still obeyed, and a trail stopped by
    # it is still reported as stopped rather than as a chain that ended.
    max_hops: int = field(default_factory=lambda: int(_env("RIPPLE_MAX_HOPS", "0")))

    # Which tables count as the ones this team publishes. See the note at the
    # top of this file for why this is a setting and not a constant.
    #
    # Two fields, and both matter. ``production_patterns`` is what is matched
    # against: every entry Ripple recognised, whether a real table name or a
    # pattern. ``production_text`` is what was actually pasted, kept exactly as
    # it arrived so the box can be opened and edited again rather than being
    # handed back a tidied-up version of somebody's list.
    #
    # There is no default any more, and that is deliberate. Whoever deploys a
    # hosted copy can still set RIPPLE_PROD_TABLES; on a copy where nobody has,
    # this is empty, and empty means NOT GIVEN rather than "nothing is
    # published". See set_production and has_production.
    production_patterns: tuple[str, ...] = field(
        default_factory=lambda: parse_production_rule(_env("RIPPLE_PROD_TABLES", ""))
    )
    production_text: str = field(
        default_factory=lambda: _env("RIPPLE_PROD_TABLES", "")
    )

    # File types worth reading at all.
    #
    # ``.sqlx`` is Dataform -- Google's own tool for building BigQuery pipelines,
    # and the one most likely to be in a BigQuery repository after dbt. A .sqlx
    # file is an ordinary SELECT with a ``config { }`` block on top, and it was
    # not opened, not counted and not mentioned: `indexed False, risk none,
    # prod []`, with nothing anywhere recording that the file existed.
    code_extensions: tuple[str, ...] = (
        ".sql", ".sqlx", ".ddl", ".hql", ".py", ".scala", ".java", ".sh",
        ".xml", ".yaml", ".yml",
    )
    # Never walk into these.
    skip_dirs: tuple[str, ...] = (
        ".git", ".venv", "venv", "node_modules", "__pycache__", "target", "build", "dist",
    )
    max_file_bytes: int = 2_000_000

    # The biggest email file that can be uploaded. A serverless host refuses a
    # request body over roughly 4.5 MB before Ripple ever sees it, so the limit
    # on screen has to be the real one, not a friendlier invented one.
    max_upload_bytes: int = field(
        default_factory=lambda: int(
            _env("RIPPLE_MAX_UPLOAD_BYTES", "4000000" if _serverless() else "25000000")
        )
    )

    # ── AI (entirely optional) ─────────────────────────────────────────────
    # One key, whoever issued it. Which provider it belongs to is worked out
    # from the key itself rather than asked for -- see ripple/providers.py.
    #
    # The old GROQ_* names are still read, because they are set on a running
    # host and silently ignoring them would turn the AI off without a word.
    ai_key: str = field(default_factory=lambda: _env_any(
        ("RIPPLE_AI_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY",
         "GOOGLE_API_KEY", "GROQ_API_KEY")))
    # Empty means "whichever the provider recommends", worked out on connect
    # from the list it actually returns.
    ai_model: str = field(default_factory=lambda: _env_any(("RIPPLE_AI_MODEL", "GROQ_MODEL")))
    # Only for a proxy or a provider Ripple does not know. Left empty, the
    # address comes from whichever provider issued the key.
    ai_base_url: str = field(default_factory=lambda: _env_any(
        ("RIPPLE_AI_BASE_URL", "GROQ_BASE_URL")))
    # How long to wait for the model. Writing the summary makes two calls one
    # after the other, so on a serverless host both have to finish inside the
    # 60-second cap -- otherwise the page dies with no explanation instead of
    # falling back to the written-without-AI version.
    ai_timeout: float = field(
        default_factory=lambda: float(_env("RIPPLE_AI_TIMEOUT", "20" if _serverless() else "45"))
    )

    # ── storage ────────────────────────────────────────────────────────────
    # Serverless hosts give you a read-only filesystem apart from /tmp, and even
    # that is wiped between runs -- so on Vercel, history is per-session only.
    db_path: Path = field(default_factory=lambda: Path(_default_db()))

    def branch(self) -> str:
        """Which branch this folder is on, or nothing at all.

        Worked out each time rather than stored, because the folder can change
        while Ripple is running -- somebody chooses a different one on the
        settings screen -- and a branch left over from the folder before is a
        fact about a repository nobody is reading any more.
        """
        return self.repo_branch or git_branch(self.repo_path)

    def ai_available(self) -> bool:
        return bool(self.ai_key)

    def ai_provider(self) -> dict | None:
        """The company that issued this key, worked out from the key itself."""
        return providers.detect(self.ai_key)

    def ai_endpoint(self) -> str:
        """Where to send the request. An explicit setting always wins."""
        if self.ai_base_url:
            return self.ai_base_url.rstrip("/")
        found = self.ai_provider()
        return found["base_url"] if found else ""

    # ── the published-table rule ───────────────────────────────────────────
    def production(self) -> ProductionRule:
        """The rule, read. Rebuilt only when the entries themselves change.

        Asked once per table visited on every hop of every scan, and a real
        list is hundreds of names long, so the answer is worked out once and
        kept rather than re-parsed each time.
        """
        entries = tuple(self.production_patterns)
        cached = getattr(self, "_production_cache", None)
        if cached is None or cached[0] != entries:
            rule = ProductionRule(text=self.production_text,
                                  entries=parse_production_text(
                                      "\n".join(entries)).entries)
            object.__setattr__(self, "_production_cache", (entries, rule))
            return rule
        return cached[1]

    def set_production(self, text: str) -> ProductionRule:
        """Take a pasted list, in whatever shape it arrived. Returns what was read.

        An empty box stays empty. It used to fall back to the shipped default --
        _PROD, _PRD, _PUBLISHED -- and that is the most expensive thing this
        tool ever did: on a warehouse that names its published tables anything
        else, the default matches NOTHING, and matching nothing does not read as
        "I do not know which tables are yours". It reads as "no production table
        is affected", in green, over a change that breaks all of them.

        Empty now means NOT GIVEN, which is a different thing from "nothing is
        published" and is treated as one everywhere: see has_production, which
        every entry point checks before it will scan.
        """
        rule = parse_production_text(text or "")
        self.production_text = "" if rule.is_empty() else str(text or "")
        self.production_patterns = tuple(e.given for e in rule.entries)
        object.__setattr__(self, "_production_cache",
                           (self.production_patterns, rule))
        return rule

    def has_production(self) -> bool:
        """Has anybody said which tables this team publishes?

        The one setting Ripple cannot work out for itself, and the one that
        decides whether the answer says "production impact" at all. Nothing may
        be scanned until it has been given -- an answer computed against a list
        nobody chose is worth less than no answer, because it looks the same as
        a real one.
        """
        return bool(self.production_patterns)

    def is_production_table(self, table: str) -> bool:
        return self.production().matches(table)

    def production_rule(self) -> str:
        """The rule as one short line, for a status row rather than a screen.

        Two hundred pasted table names do not fit on a line, and pretending
        otherwise produces a row of dots that says nothing. A long list is
        counted instead; a short one is still shown in full.
        """
        return self.production().one_line()


settings = Settings()
