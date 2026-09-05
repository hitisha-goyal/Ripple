"""Reading sqlglot parse-tree keys safely, whichever parser version is installed.

WHY THIS FILE EXISTS AT ALL

sqlglot renames the keys inside its own nodes between major versions, and the
renames that matter are SILENT: ask for the old key and you are handed nothing
rather than an error. Code written against the old name keeps running and
quietly stops finding anything, on a machine where every test still passes.

Three of them switch off things Ripple exists to do:

    Star.args["except"]        -> "except_"   SELECT * EXCEPT(col) stops being
                                              noticed, so a column dropped BY
                                              NAME is reported as carried on
    Merge.args["expressions"]  -> "whens"     every rename a MERGE makes
                                              disappears, and a MERGE is how a
                                              published table is loaded
    Select.args["from"]        -> "from_"     the check that decides which
                                              tables a SELECT * covers finds
                                              nothing

So every read of that kind happens here, and NOTHING ELSE ANYWHERE IN RIPPLE
reads one directly. That rule is the whole point of the file.

Every function below returns an empty list, or a plain false, or None, rather
than raising when the key is missing entirely: an unfamiliar parser version
must degrade to finding LESS, never to a crash in the middle of a repository
that takes minutes to read.
"""

from __future__ import annotations

from typing import Any

from sqlglot import exp


class _NoSuchNode:
    """Stands in for a node class this sqlglot does not have.

    WHY a stand-in rather than None: callers write isinstance(x, RENAME_NODE),
    and isinstance against a plain class is simply False. None would raise at
    the first call and take down a scan for a shape the parser never had.
    """


def _first_present(node: Any, *names: str) -> Any:
    """The first of `names` this node actually carries a value under.

    WHY names in order: the newest spelling is tried first so that a current
    parser never pays for the old one, and an old parser still answers.
    """
    args = getattr(node, "args", None)
    if not isinstance(args, dict):
        return None
    for name in names:
        if name in args:
            value = args[name]
            if value is not None:
                return value
    return None


def _as_list(value: Any) -> list:
    """Whatever came back, as a list with the empties taken out."""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [item for item in value if item is not None]
    return [value]


def _name_of(item: Any) -> str:
    """The plain name of a node, an identifier or an already-plain string."""
    if item is None:
        return ""
    if isinstance(item, str):
        return item
    for attribute in ("alias_or_name", "name"):
        value = getattr(item, attribute, "")
        if isinstance(value, str) and value:
            return value
    return ""


# The class for ALTER TABLE a RENAME TO b. Newer versions call it AlterRename,
# older ones RenameTable. This one is loud rather than silent - the class name
# simply does not exist - but it belongs with the rest.
RENAME_NODE: Any = (
    getattr(exp, "AlterRename", None)
    or getattr(exp, "RenameTable", None)
    or _NoSuchNode
)


def from_of(select: Any) -> Any:
    """The FROM clause of a SELECT, or None.

    Read the wrong key and the check that decides which tables a SELECT *
    covers finds nothing at all.
    """
    return _first_present(select, "from", "from_")


def star_except(star: Any) -> list:
    """The columns named in SELECT * EXCEPT(a, b), as a list."""
    return _as_list(_first_present(star, "except", "except_"))


def star_replace(star: Any) -> list:
    """The columns swapped by SELECT * REPLACE(x AS a), as a list."""
    return _as_list(_first_present(star, "replace", "replace_"))


def star_rename(star: Any) -> list:
    """The columns renamed by SELECT * RENAME(a AS b), as a list.

    NOT one of the nine the phase names. It is here because the big file has to
    read RENAME off a star "the same guarded way you read EXCEPT", and the one
    rule says nothing outside this module may touch that key.
    """
    return _as_list(_first_present(star, "rename", "rename_"))


def is_unpivot(pivot: Any) -> bool:
    """True for UNPIVOT, false for PIVOT.

    PIVOT turns rows into columns; UNPIVOT turns columns into rows, and the two
    do opposite things to a column's future - so getting this backwards hedges
    downwards on a statement that hard-fails on the day the column goes.
    """
    value = _first_present(pivot, "unpivot")
    if value is None:
        return False
    if isinstance(value, exp.Boolean):
        return bool(value.this)
    if isinstance(value, str):
        return value.strip().upper() in {"TRUE", "UNPIVOT", "1"}
    return bool(value)


def pivot_fields(pivot: Any) -> list:
    """The FOR x IN (...) parts of a PIVOT or UNPIVOT, as a list.

    For an UNPIVOT the IN list IS the column list being folded away, so reading
    the wrong key means a statement that hard-fails on the day the column goes
    is reported as carrying it through untouched.
    """
    return _as_list(_first_present(pivot, "fields", "field"))


def pivot_columns(pivot: Any) -> list[str]:
    """The output column names a PIVOT produces - total_Q1, total_Q2.

    sqlglot works these out itself, from the aggregate's alias, whether it has
    one, and each IN value. An EMPTY LIST MEANS IT DID NOT WORK THEM OUT, and
    the caller must not pretend to know the names.
    """
    names: list[str] = []
    for item in _as_list(_first_present(pivot, "columns")):
        name = _name_of(item)
        if name:
            names.append(name)
    return names


def is_temporary(stmt: Any) -> bool:
    """Was this CREATE written TEMP or TEMPORARY?

    A temporary table lives inside one script, so two files that each build a
    "t" are not sharing a table. Read the wrong key and they get merged, which
    INVENTS a chain to a published table nobody touched - and that finding
    looks exactly like a real one.
    """
    properties = _first_present(stmt, "properties")
    if properties is None:
        return False
    temporary = getattr(exp, "TemporaryProperty", None)
    if temporary is None:
        return False
    for prop in _as_list(getattr(properties, "expressions", None)):
        if isinstance(prop, temporary):
            return True
    return False


def merge_whens(merge: Any) -> list:
    """Every WHEN branch of a MERGE, whichever shape it arrives in.

    Newer versions wrap the branches in a Whens node under "whens"; older ones
    put the branches straight under "expressions". Miss them and every rename a
    MERGE makes disappears - and a MERGE is how a published table is loaded.
    """
    value = _first_present(merge, "whens", "expressions")
    branches: list = []
    for item in _as_list(value):
        # A Whens node holds the branches; a bare list already is them.
        nested = getattr(item, "expressions", None)
        if nested and not isinstance(item, exp.When):
            branches.extend([branch for branch in nested if branch is not None])
        else:
            branches.append(item)
    return branches
