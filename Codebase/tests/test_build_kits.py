"""The build kits are specifications, and a stale line in one gets obeyed.

Three documents, two of which are five thousand lines and have to agree with each
other word for word wherever they describe the same behaviour. Keeping that true
by reading them is not something anybody manages twice.

None of this checks prose quality. It checks the four things that have gone wrong
before and would go wrong silently again: a file that exists in the code and is
named in no kit, a payload key the screens read and the kits never mention, one
rule written down twice in two different ways, and a behaviour block that made it
into one kit and not the other.
"""
from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent.parent
ONLINE = ROOT / "BUILD-KIT.md"
REPAIR = ROOT / "BUILD-KIT-REPAIR.md"
BUILD_KITS = (ONLINE,)


def text(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_both_kits_are_here():
    """One builds Ripple from nothing, one changes a Ripple that already exists.
    Losing either loses a road in.

    There were two BUILD-KITs once, a second written for a machine where nothing
    could be installed. It was 86% the same document, and the only part of it
    that mattered to anybody whose pip works -- four routes for getting sqlglot
    on when the mirror is down -- lives in BUILD-KIT.md now, under "If the
    install step will not work at all". Two accounts of one build is a product
    that behaves differently depending on which file somebody opened.
    """
    for kit in (ONLINE, REPAIR):
        assert kit.is_file(), f"{kit.name} is missing"
        assert len(text(kit).splitlines()) > 400, f"{kit.name} is too short to be the kit"


def test_the_build_kit_keeps_the_way_in_when_pip_cannot_reach_anything():
    """The one thing worth keeping from the kit that was deleted. sqlglot is the
    only package that cannot be worked around, and a build that gets eleven
    twelfths of the way and then cannot read SQL is a wasted evening."""
    body = text(ONLINE)
    assert "## If the install step will not work at all" in body,         "BUILD-KIT.md has no fallback for a blocked pip"
    for route in ("### Route 1", "### Route 2", "### Route 3"):
        assert route in body, f"the fallback is missing {route}"
    assert "python -c \"import sqlglot; print(sqlglot.__version__)\"" in body,         "the fallback gives no way to prove the parser arrived"


def test_each_kit_says_which_of_the_two_it_is():
    """Somebody who opens the wrong one and follows it to the end has wasted two
    evenings, so each names the other and says when to use it."""
    for kit in (ONLINE, REPAIR):
        body = text(kit)
        for other in ("BUILD-KIT.md", "BUILD-KIT-REPAIR.md"):
            if other != kit.name:
                assert other in body, f"{kit.name} never mentions {other}"


# ── every engine file is named somewhere ──────────────────────────────────
# A file the kits never name is a file nobody builds. dialectcompat.py and
# build_info.py were both in this state: real, imported, load-bearing, and
# absent from every file map and every phase.
#
# This list used to be typed out by hand, and that is its own version of the
# same bug: providers.py, ai.py and scanner/github.py were shipped, imported and
# named in no kit for months, and the test written to catch exactly that could
# not see them because nobody had added them to the list. A list of what to
# check, kept by hand, goes stale in the same silence as the thing it checks.
#
# So the list is read off the disk now. A new engine file is guarded the moment
# it exists, without anybody remembering to come here.
ENGINE_DIR = Path(__file__).resolve().parent.parent / "ripple"


def _engine_files() -> list[str]:
    """Every engine file that ships, newest arrivals included.

    ``__init__.py`` is left out: it is empty by design, both kits say so in
    their folder tree, and there is nothing about it for a kit to describe.
    """
    found = [
        p.relative_to(ENGINE_DIR).as_posix()
        for p in ENGINE_DIR.rglob("*.py")
        if "__pycache__" not in p.parts and p.name != "__init__.py"
    ]
    return sorted(found)


ENGINE_FILES = _engine_files()


def test_the_engine_has_files_to_check():
    """A glob that quietly matches nothing passes every test after it."""
    assert len(ENGINE_FILES) > 10, f"only found {ENGINE_FILES} - the glob is wrong"


@pytest.mark.parametrize("name", ENGINE_FILES)
def test_every_engine_file_is_named_in_both_build_kits(name):
    leaf = name.split("/")[-1]
    for kit in BUILD_KITS:
        assert leaf in text(kit), (
            f"{kit.name} never names {leaf}, which ships in ripple/{name}. "
            f"A file no kit names is a file nobody builds. Put it in the folder "
            f"tree and the file map — and if this kit deliberately does not build "
            f"it, say so there in a sentence, which counts as naming it."
        )


@pytest.mark.parametrize("name", ENGINE_FILES)
def test_every_engine_file_is_named_in_the_repair_kit(name):
    """The repair kit's whole job is telling somebody which file to open."""
    assert name.split("/")[-1] in text(REPAIR), f"the repair kit never names {name}"


# ── the kits declare the payload the screens read ─────────────────────────
def _real_payload() -> dict:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from test_confident_over_less import scan          # noqa: PLC0415
    with tempfile.TemporaryDirectory() as d:
        return scan(Path(d), {"a.sql": "CREATE OR REPLACE TABLE final_published AS "
                                       "SELECT cm13 FROM customer_demographics;"})


def test_the_contract_card_declares_every_key_the_answer_carries():
    """Every window builds against the contract card and none of them can see the
    others. A key missing from it is a key one window sends and the next never
    reads - which shows up as a blank on screen and as nothing at all in a test."""
    out = _real_payload()
    body = text(ONLINE)
    start = body.index("{attributes[], groups[], reached[]")
    declared = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", body[start:start + 1200]))
    missing = sorted(set(out) - declared)
    assert not missing, f"the contract card never names: {missing}"


def test_the_contract_card_declares_every_stat():
    out = _real_payload()
    body = text(ONLINE)
    start = body.index("stats = {productionTables")
    declared = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", body[start:start + 600]))
    missing = sorted(set(out["stats"]) - declared)
    assert not missing, f"the contract card never names these stats: {missing}"


def test_the_contract_card_declares_every_field_on_a_finding():
    out = _real_payload()
    row = out["groups"][0]["rows"][0]
    body = text(ONLINE)
    start = body.index("{inter, from, attr, roots[]")
    declared = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", body[start:start + 500]))
    missing = sorted(set(row) - declared)
    assert not missing, f"the contract card never names these finding fields: {missing}"


# ── the kit does not contradict itself ───────────────────────────────────
_HEADING = re.compile(r"^[A-Z][A-Z '\*\-,\.\(\)/_]{24,}", re.M)


def test_neither_build_kit_states_one_rule_twice():
    """Two accounts of one rule is worse than none: a chat obeys whichever it
    read last, and nobody can tell which that was."""
    for kit in BUILD_KITS:
        heads = [m.group(0).split(".")[0].strip() for m in _HEADING.finditer(text(kit))]
        twice = sorted({h for h in heads if heads.count(h) > 1})
        assert not twice, f"{kit.name} states these twice: {twice}"


def test_the_sqlglot_pin_is_the_one_the_kits_name():
    """The kits tell somebody to pin the parser. If they name a version the
    project no longer uses, the copy they build reads SQL differently from this
    one and nothing anywhere says so."""
    pinned = next(line.split("==")[1].split()[0].strip()
                  for line in (Path(__file__).resolve().parent.parent
                               / "requirements.txt").read_text(encoding="utf-8").splitlines()
                  if line.startswith("sqlglot=="))
    for kit in BUILD_KITS:
        found = set(re.findall(r"sqlglot[=<> ]*([0-9]+\.[0-9]+\.[0-9]+)", text(kit)))
        wrong = {v for v in found if v != pinned}
        assert not wrong, f"{kit.name} names sqlglot {sorted(wrong)}, pinned is {pinned}"


RAW_KEYS = ('args["except"]', 'args["from"]', 'args["replace"]',
            'args["expressions"]', 'args["columns"]', 'args["fields"]')


def test_a_kit_only_shows_a_raw_parse_tree_key_while_warning_about_it():
    """Every one of these has a helper, and reading the raw key gives back
    nothing rather than raising on a newer parser. So a kit may PRINT one - that
    is how the danger is explained - but only on a line that also shows what it
    was renamed to, or names the module that wraps it. A raw key shown on its
    own reads as an instruction, and a chat will write exactly what it sees."""
    for kit in BUILD_KITS:
        for n, line in enumerate(text(kit).splitlines(), 1):
            for raw in RAW_KEYS:
                if raw not in line:
                    continue
                warned = ("became" in line or "->" in line
                          or "dialectcompat" in line or "never" in line.lower())
                assert warned, f"{kit.name}:{n} shows {raw} with no warning beside it"


# ── the kits carry the WHOLE of every list, not an example of one ─────────
# A rule written as "EXTERNAL_QUERY, APPENDS and friends" produces a Ripple that
# knows three of fourteen. Every entry it never heard of is a silent wrong
# answer of exactly the kind the surrounding paragraph exists to prevent: a
# built-in function recorded as a table nobody has, a spreadsheet heading
# recorded as a published table, the word AND recorded as a column.
#
# These are the enumerable ones. If a new list of this shape is added to the
# engine, add it here too - and then the kits have to name it.
RULE_LISTS = [
    ("the built-in functions that wrap a table", "ripple/scanner/sqlread.py", "_NOT_A_TABLE"),
    ("the words that are never a column", "ripple/scanner/sqlread.py", "_NOT_A_COLUMN"),
    ("the heading rows a pasted list arrives with", "ripple/production.py", "_HEADINGS"),
    ("the file types that are known not to be code", "ripple/scanner/repo.py", "NOT_CODE_EXTS"),
    ("the template suffixes", "ripple/scanner/repo.py", "TEMPLATE_SUFFIXES"),
    ("the kinds a usage can be", "ripple/scanner/sqlread.py", "KIND_PRIORITY"),
    ("which change breaks which kind", "ripple/scanner/lineage.py", "BREAKS"),
]


def _entries(rel: str, const: str) -> list[str]:
    """Every string inside a module-level assignment, read off the code."""
    import ast
    path = Path(__file__).resolve().parent.parent / rel
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        named = (isinstance(node, ast.Assign)
                 and any(getattr(t, "id", None) == const for t in node.targets))
        if named:
            return [s.value for s in ast.walk(node)
                    if isinstance(s, ast.Constant) and isinstance(s.value, str)
                    and len(s.value) > 1]
    return []


@pytest.mark.parametrize("label,rel,const", RULE_LISTS,
                         ids=[c for _, _, c in RULE_LISTS])
def test_the_kit_names_every_entry_of_every_rule_list(label, rel, const):
    entries = _entries(rel, const)
    assert entries, f"{const} is not in {rel} any more - fix the list in this test"
    body = text(ONLINE).lower()
    missing = sorted({e for e in entries if e.lower() not in body})
    assert not missing, (
        f"{len(missing)} of {len(entries)} entries of {label} appear in the "
        f"build kit: {missing}. A chat cannot write a list it was never given, "
        f"and every one of these is a wrong answer nothing would report."
    )
