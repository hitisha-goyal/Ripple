from __future__ import annotations

"""Settings, read from environment variables.

Every field has a default read from the environment, so a laptop, a demo host
and a locked-down machine differ only by environment and not by edited code.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from . import paths
from .production import (
    DEFAULT_PRODUCTION,
    ProductionEntry,
    ProductionRule,
    matches,
    parse_production,
)

# Up to this many entries, the one-line summary prints the list itself. Past
# it, two hundred pasted names do not fit on a line, so they are counted.
SHORT_LIST = 4


def _env(name: str) -> str:
    value = os.environ.get(name)
    return value.strip() if value else ""


def _default_repo_path() -> Path:
    raw = _env("RIPPLE_REPO")
    if raw:
        return Path(raw).expanduser()
    # The practice pipeline. A Ripple pointed here answers questions about the
    # practice pipeline, confidently and correctly and about nothing anybody
    # cares about, which is why run.py prints the folder every single time.
    return paths.app_dir() / "mockrepo"


def _default_repo_label() -> str:
    return _env("RIPPLE_REPO_LABEL")


def _default_dialect() -> str:
    # ONE default, and it is the warehouse this is being built for. Read as
    # generic, a BigQuery-ism the parser does not recognise becomes an
    # unreadable statement, the chain running through it is never followed, and
    # the answer comes back cleaner than the truth. Two builds of Ripple once
    # disagreed about exactly this and read the same folder as two different
    # languages.
    return _env("RIPPLE_SQL_DIALECT") or "bigquery"


def _default_max_hops() -> int:
    raw = _env("RIPPLE_MAX_HOPS")
    if not raw:
        return 4
    try:
        value = int(raw)
    except ValueError:
        # A typo in an environment variable must not silently mean zero hops,
        # which would follow no rename at all and report nothing.
        return 4
    return value if value > 0 else 4


def _default_db_path() -> Path:
    raw = _env("RIPPLE_DB")
    if raw:
        return Path(raw).expanduser()
    # Never a path worked out from this file's own location: see paths.py.
    return paths.data_dir() / "ripple.db"


def _default_production_text() -> str:
    return os.environ.get("RIPPLE_PROD_TABLES", "")


def _join_plainly(items: list[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]


@dataclass
class Settings:
    """One place every other file asks what it is meant to be doing."""

    repo_path: Path = field(default_factory=_default_repo_path)
    repo_label: str = field(default_factory=_default_repo_label)
    # EMPTY, and read off the folder when it is empty. Defaulting to "main" put
    # "Branch main" on the Repository step over every folder on earth:
    # specific, checkable-looking, and true of nothing.
    repo_branch: str = ""
    sql_dialect: str = field(default_factory=_default_dialect)
    max_hops: int = field(default_factory=_default_max_hops)
    code_extensions: tuple[str, ...] = (
        ".sql",
        # .sqlx is Dataform, Google's own way of writing a BigQuery pipeline.
        # Leave it out and a whole Dataform repository is never opened, never
        # read and never counted, and the scan reports no lineage anywhere.
        ".sqlx",
        ".ddl",
        ".hql",
        ".py",
        ".scala",
        ".java",
        ".sh",
        ".xml",
        ".yaml",
        ".yml",
    )
    skip_dirs: tuple[str, ...] = (
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        "target",
        "build",
        "dist",
    )
    max_file_bytes: int = 2_000_000
    max_upload_bytes: int = 25_000_000
    db_path: Path = field(default_factory=_default_db_path)
    production_patterns: tuple[str, ...] = ()
    # The raw paste, kept exactly as it arrived, so the box can be opened and
    # edited again rather than handing somebody back a tidied version of their
    # own list.
    production_text: str = field(default_factory=_default_production_text)

    # The parsed rule is asked for once per table visited on every hop of every
    # scan, so it is worked out once and kept until the paste changes.
    _rule: ProductionRule | None = field(
        default=None, repr=False, compare=False
    )
    _rule_text: str = field(default="", repr=False, compare=False)

    def __post_init__(self) -> None:
        if not self.repo_label:
            self.repo_label = Path(self.repo_path).name
        self.production_patterns = tuple(
            entry.match for entry in self.production().entries
        )

    def production(self) -> ProductionRule:
        """The parsed published-table rule."""
        if self._rule is None or self._rule_text != self.production_text:
            self._rule = parse_production(self.production_text)
            self._rule_text = self.production_text
        return self._rule

    def set_production(self, text: str) -> ProductionRule:
        """Replace the pasted list, and return what Ripple made of it."""
        self.production_text = text or ""
        self._rule = None
        rule = self.production()
        self.production_patterns = tuple(entry.match for entry in rule.entries)
        return rule

    def is_production_table(self, name: str) -> bool:
        return matches(self.production(), name)

    def production_rule(self) -> str:
        """A short one-line summary of the rule, for the screen."""
        rule = self.production()
        entries: list[ProductionEntry] = list(rule.entries)
        if len(entries) <= SHORT_LIST:
            return _join_plainly([entry.raw for entry in entries])
        names = [entry.raw for entry in entries if entry.kind == "exact"]
        patterns = [entry.raw for entry in entries if entry.kind != "exact"]
        parts: list[str] = []
        if names:
            word = "table name" if len(names) == 1 else "table names"
            parts.append(f"{len(names)} {word}")
        if patterns:
            shown = patterns[:3]
            more = len(patterns) - len(shown)
            listed = ", ".join(shown)
            if more:
                listed = f"{listed} and {more} more"
            word = "pattern" if len(patterns) == 1 else "patterns"
            parts.append(f"{len(patterns)} {word} ({listed})")
        if not parts:
            # parse_production never returns an empty rule, but a summary that
            # said nothing at all would read as "no rule set" on screen.
            return _join_plainly(list(DEFAULT_PRODUCTION))
        return " and ".join(parts)

    def branch(self) -> str:
        """The branch of the folder being read, or empty when there is none.

        A folder on somebody's disk may be a copied-out git checkout, in which
        case .git/HEAD holds the real branch and it is worth showing, or it may
        be a plain folder, in which case there is no branch at all and the
        screen must say nothing rather than guess.
        """
        if self.repo_branch:
            return self.repo_branch
        head = Path(self.repo_path) / ".git" / "HEAD"
        try:
            text = head.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            return ""
        marker = "ref: refs/heads/"
        if text.startswith(marker):
            # Branch names contain slashes, so this takes everything after the
            # prefix rather than the last slash-separated part.
            return text[len(marker) :].strip()
        # A detached checkout leaves a bare commit id here. That is not a
        # branch, and calling it one would put a lie on the Repository step.
        return ""


settings = Settings()
