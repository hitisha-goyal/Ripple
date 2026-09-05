"""Templated SQL and scripting blocks, rewritten on the way into the parser.

Two rules hold everywhere in this file.

Line numbers do not move. Every replacement puts back exactly as many line
breaks as it swallowed, because a finding points at a line number and that
number is the only thing anybody can go and open.

The original text is never changed. Everything here is done to a copy on the
way into the parser; everything shown on screen comes from the file as written.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# PART ONE - placeholders
# ---------------------------------------------------------------------------

# Cut long identifiers here. A hole filled in with a whole rendered SQL block
# would otherwise become a several-hundred-character name that no reader can
# match up with anything.
_MAX_IDENTIFIER = 60

# These are instructions to dbt, not values. Turned into a bare identifier a
# word lands where SQL expects a keyword and the WHOLE file stops parsing - not
# one table, not one column. Every dbt model in the world opens with one.
_DBT_DIRECTIVES = frozenset(
    {
        "config",
        "set",
        "test",
        "macro",
        "endmacro",
        "snapshot",
        "endsnapshot",
        "do",
        "print",
        "log",
    }
)

_LEADING_WORD = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)")
_REF_CALL = re.compile(r"(?is)^\s*(ref|source)\s*\(")
_QUOTED_NAME = re.compile(r"'([^']*)'" + r'|"([^"]*)"')

# The five patterns, in the order they must run. Take the narrow { name }
# pattern first and it matches the inner half of {{ name }}, leaves a stray
# brace behind, and every templated file in the repository comes back
# unreadable - the exact thing this part is here to prevent.
_COMMENT_PATTERN = re.compile(r"\{#.*?#\}", re.S)
_TAG_PATTERN = re.compile(r"\{%.*?%\}", re.S)
_VAR_PATTERN = re.compile(r"\{\{(.*?)\}\}", re.S)
_DOLLAR_PATTERN = re.compile(r"\$\{(.*?)\}", re.S)
# Deliberately narrow, and deliberately single-line: it has to leave a regular
# expression's {3} inside a string literal alone.
_FORMAT_PATTERN = re.compile(r"\{[ \t]*([A-Za-z_][A-Za-z0-9_.\[\]]*)[ \t]*\}")


def _identifier(body: str) -> str:
    """Turn the inside of one placeholder into something that parses.

    Returns an empty string for a dbt directive, which must resolve to nothing
    at all rather than to a word.
    """
    word = _LEADING_WORD.match(body)
    if word is not None and word.group(1).lower() in _DBT_DIRECTIVES:
        return ""

    if _REF_CALL.match(body) is not None:
        # ref('orders') and source('raw','orders') resolve to the last quoted
        # name, because that is a real table and taking it is the whole point
        # of ref().
        quoted = [
            match.group(1) if match.group(1) is not None else match.group(2)
            for match in _QUOTED_NAME.finditer(body)
        ]
        if quoted:
            body = quoted[-1]

    identifier = re.sub(r"[^0-9A-Za-z_]", "_", body).strip("_")
    if not identifier:
        # An empty one leaves FROM .orders behind, a parse error that costs the
        # whole file.
        return "placeholder"
    if identifier[0].isdigit():
        identifier = "p_" + identifier
    return identifier[:_MAX_IDENTIFIER]


def _replace_value(match: re.Match[str]) -> str:
    """Swap one placeholder for its identifier, keeping the line breaks."""
    return _identifier(match.group(1)) + "\n" * match.group(0).count("\n")


def _replace_nothing(match: re.Match[str]) -> str:
    """Drop a comment or a tag, keeping the line breaks it held."""
    return "\n" * match.group(0).count("\n")


def fill_placeholders(text: str) -> str:
    """Replace every templating hole with an ordinary identifier.

    {{tgt_project_id}}.{{stage_dataset}}.web_activity becomes
    tgt_project_id.stage_dataset.web_activity, which parses as the three-part
    name it always was.
    """
    if "{" not in text and "$" not in text:
        # Nothing to fill, so hand back the same object rather than walking it.
        return text
    filled = _COMMENT_PATTERN.sub(_replace_nothing, text)
    filled = _TAG_PATTERN.sub(_replace_nothing, filled)
    filled = _VAR_PATTERN.sub(_replace_value, filled)
    filled = _DOLLAR_PATTERN.sub(_replace_value, filled)
    filled = _FORMAT_PATTERN.sub(_replace_value, filled)
    return filled


def placeholder_names(text: str) -> set[str]:
    """The words that came out of a hole, in upper case.

    One file writes a table as {{tgt_project_id}}.{{stage_dataset}}.orders_daily
    and the DAG that reads it writes {{ params.src }}.raw.orders_daily. Once
    both are filled in one says the dataset is stage_dataset and the other says
    raw - and those are not two datasets, they are two holes. Knowing which
    words came out of a hole is what stops Ripple cutting a real chain in half.
    """
    names: set[str] = set()

    def collect(match: re.Match[str]) -> str:
        identifier = _identifier(match.group(1))
        if identifier:
            # A dbt directive gives back an empty string, and collecting a
            # blank name here would make every file look like it shared one.
            names.add(identifier.upper())
        return identifier + "\n" * match.group(0).count("\n")

    # Comments and tags carry nothing, so they are removed rather than walked.
    scratch = _COMMENT_PATTERN.sub(_replace_nothing, text)
    scratch = _TAG_PATTERN.sub(_replace_nothing, scratch)
    for pattern in (_VAR_PATTERN, _DOLLAR_PATTERN, _FORMAT_PATTERN):
        scratch = pattern.sub(collect, scratch)
    return names


def describe(text: str) -> str:
    """What kind of templating is in this file, in words, for the screen."""
    kinds: list[str] = []
    if _VAR_PATTERN.search(text) is not None:
        kinds.append("{{ ... }} templating (Airflow, dbt or similar)")
    if _TAG_PATTERN.search(text) is not None or _COMMENT_PATTERN.search(text) is not None:
        kinds.append("{% ... %} tags (Airflow, dbt or similar)")
    if _DOLLAR_PATTERN.search(text) is not None:
        kinds.append("${ ... } templating (shell or Databricks)")

    scratch = _COMMENT_PATTERN.sub(_replace_nothing, text)
    scratch = _TAG_PATTERN.sub(_replace_nothing, scratch)
    scratch = _VAR_PATTERN.sub(_replace_value, scratch)
    scratch = _DOLLAR_PATTERN.sub(_replace_value, scratch)
    if _FORMAT_PATTERN.search(scratch) is not None:
        kinds.append("{ ... } templating (Python format)")

    return ", ".join(kinds)


# ---------------------------------------------------------------------------
# PART TWO - scripting blocks
# ---------------------------------------------------------------------------


@dataclass
class _ScanState:
    """Quote and comment state, carried from one line to the next.

    Skip a line and this is stale for everything after it, so an END inside a
    long quoted string reads as scripting and the 600-line statement holding it
    is destroyed.
    """

    quote: str = ""
    in_comment: bool = False

    def copy(self) -> "_ScanState":
        """A look-ahead gets a copy, never the live one.

        Hand a look-ahead the live state and it walks lines the main pass has
        not reached yet, and every quote from there to the end of the file is
        tracked wrong.
        """
        return _ScanState(self.quote, self.in_comment)


def _blank_literals(line: str, state: _ScanState) -> str:
    """A copy of one line with strings and comments turned into spaces.

    The copy comes back EXACTLY as long as the line it was made from. Positions
    measured on it are used to cut the real line, and a copy one character short
    cuts the body in the wrong place.
    """
    out = list(line)
    length = len(line)
    index = 0
    while index < length:
        if state.in_comment:
            if line.startswith("*/", index):
                out[index] = " "
                out[index + 1] = " "
                state.in_comment = False
                index += 2
            else:
                out[index] = " "
                index += 1
            continue

        if state.quote:
            quote = state.quote
            if line[index] == "\\" and quote != "`":
                # An escaped quote does not close the string, so hide both
                # characters and carry on.
                out[index] = " "
                if index + 1 < length:
                    out[index + 1] = " "
                index += 2
                continue
            if line.startswith(quote, index):
                for position in range(index, index + len(quote)):
                    out[position] = " "
                state.quote = ""
                index += len(quote)
                continue
            out[index] = " "
            index += 1
            continue

        if line.startswith("--", index) or line[index] == "#":
            for position in range(index, length):
                out[position] = " "
            index = length
            continue

        if line.startswith("/*", index):
            out[index] = " "
            out[index + 1] = " "
            state.in_comment = True
            index += 2
            continue

        opened = ""
        for quote in ("'''", '"""', "'", '"', "`"):
            if line.startswith(quote, index):
                opened = quote
                break
        if opened:
            for position in range(index, index + len(opened)):
                out[position] = " "
            state.quote = opened
            index += len(opened)
            continue

        index += 1
    return "".join(out)


_CASE_OR_END = re.compile(r"(?i)\b(CASE|END)\b")
_SELECT_WORD = re.compile(r"(?i)\bSELECT\b")

_ALWAYS_SCRIPTING = re.compile(
    r"""(?ix)^\s*(
          BEGIN(\s+TRANSACTION)?
        | END\s+(IF|FOR|WHILE|LOOP)(\s+[A-Za-z_][A-Za-z0-9_]*)?
        | (COMMIT|ROLLBACK)(\s+TRANSACTION)?
        | EXCEPTION\s+WHEN\s+.*?\s+THEN
        | LOOP
        | (LEAVE|ITERATE|BREAK|CONTINUE)(\s+[A-Za-z_][A-Za-z0-9_]*)?
        )\s*;?\s*$"""
)

# BEGIN with something other than TRANSACTION after it on the same line is a
# body, not a bare block opener. BEGIN TRANSACTION is left to the always list.
_BEGIN_BODY = re.compile(r"(?i)^\s*(BEGIN)\b(?!\s*;?\s*$)(?!\s+TRANSACTION\b)")

_BARE_END = re.compile(r"(?i)^\s*END\s*;?\s*$")
_BARE_ELSE = re.compile(r"(?i)^\s*ELSE\s*;?\s*$")
_IF_THEN = re.compile(r"(?i)^\s*(ELSE\s+IF|ELSEIF|IF)\b.*\bTHEN\b\s*;?\s*$")

# Match the word RAISE at the start of the line and nothing more. A pattern
# written around USING MESSAGE misses the bare RAISE;, which on its own puts a
# perfectly readable file on the check-by-hand list.
_RAISE = re.compile(r"(?i)^\s*RAISE\b")

_PROCEDURE = re.compile(
    r"(?i)^\s*CREATE\s+(OR\s+REPLACE\s+)?(TEMP\s+|TEMPORARY\s+)?PROCEDURE\b"
)

_FOR_HEADER = re.compile(r"(?i)^\s*FOR\s+([A-Za-z_][A-Za-z0-9_]*)\s+IN\b")
_WHILE_HEADER = re.compile(r"(?i)^\s*WHILE\b")
_END_LOOP = re.compile(r"(?i)\bEND\s+(FOR|WHILE|LOOP)\b")
_LOOP_TERM = re.compile(r"(?i)\b(DO|LOOP)\b")
_HEADER_TAIL = re.compile(r"(?i)\b(DO|LOOP)\s*$")


def loop_read(variable: str | None, query: str) -> str:
    """The one rewrite every loop goes through.

    A loop body writes through the row variable and through nothing else. Drop
    the variable and the two halves of ONE statement never join up: the header
    reads the table and builds nothing, the INSERT in the body has no source of
    its own, and the row on screen says the column goes into the next table
    while naming no next table at all. The rows a FOR walks are a thing with a
    name, built here, read below, gone at the end of the file.
    """
    read = query.strip()
    if variable:
        return f"CREATE TEMP TABLE {variable} AS SELECT * FROM {read};"
    return f"SELECT * FROM {read};"


def _apply_case_depth(blanked: str, depth: int) -> int:
    """CASE and END counted left to right, and never below zero.

    A whole CASE WHEN x THEN 1 ELSE 2 END on one line nets to nothing and must
    not leave a CASE open over the rest of the file. A stray END with nothing
    open is a scripting END; let the count go negative and the NEXT real CASE
    looks already closed, so its ELSE is cut and the statement around it is
    thrown away.
    """
    for match in _CASE_OR_END.finditer(blanked):
        if match.group(0).upper() == "CASE":
            depth += 1
        elif depth > 0:
            depth -= 1
    return depth


def _bracket_group(written: str, blanked: str, start: int) -> tuple[int, int] | None:
    """The first balanced bracket group at or after start.

    Counted on the blanked copy so an apostrophe inside a string literal cannot
    unbalance the brackets; the span is handed back so the caller can cut the
    line AS WRITTEN, which is the only place a backticked table name survives.
    """
    depth = 0
    opened_at = -1
    for index in range(start, len(blanked)):
        character = blanked[index]
        if character == "(":
            if depth == 0:
                opened_at = index
            depth += 1
        elif character == ")":
            if depth > 0:
                depth -= 1
                if depth == 0:
                    return opened_at, index + 1
    return None


def _flatten(fragment: str) -> str:
    """A gathered header goes back on ONE line, so its query has to fit on one."""
    return re.sub(r"\s*\n\s*", " ", fragment).strip()


def _query_group(written: str, blanked: str, start: int) -> str | None:
    """The first balanced bracket group holding a SELECT, as written."""
    position = start
    while True:
        span = _bracket_group(written, blanked, position)
        if span is None:
            return None
        opened, closed = span
        if _SELECT_WORD.search(blanked[opened:closed]) is not None:
            return _flatten(written[opened:closed])
        position = closed


def _one_line_loop(written: str, blanked: str) -> tuple[str, str] | None:
    """A whole loop on ONE line, rewritten in place.

    It matches "a loop header" and does not end with DO, so treated as a header
    written across several lines the gather looks for a line ending in DO, never
    finds one, and returns everything to the end of the file. Every line after
    it becomes an empty statement: no parse error, no unreadable entry, nothing
    on any screen, and the trail stops one table short.
    """
    for_header = _FOR_HEADER.match(blanked)
    while_header = _WHILE_HEADER.match(blanked)
    header = for_header or while_header
    if header is None:
        return None

    span = _bracket_group(written, blanked, header.end())
    if span is None:
        return None
    opened, closed = span

    ender = _END_LOOP.search(blanked, closed)
    if ender is None:
        return None
    terminator = _LOOP_TERM.search(blanked, closed)
    if terminator is None or terminator.start() >= ender.start():
        return None

    variable = None
    if for_header is not None:
        variable = written[for_header.start(1) : for_header.end(1)]
    body_written = written[terminator.end() : ender.start()]
    body_blanked = blanked[terminator.end() : ender.start()]
    rewritten = loop_read(variable, _flatten(written[opened:closed])) + body_written
    return rewritten, body_blanked


def _semicolon_line(
    first_blanked: str, lines: list[str], start: int, state: _ScanState
) -> int:
    """The line a RAISE ends on, which may be several lines later."""
    if ";" in first_blanked:
        return start
    index = start + 1
    while index < len(lines):
        blanked = _blank_literals(lines[index], state)
        if ";" in blanked:
            return index
        index += 1
    # Never found one: give up on THIS line, never on the rest of the file.
    return start


def _signature_end(
    first_blanked: str, lines: list[str], start: int, state: _ScanState
) -> int:
    """Where a procedure signature ends.

    Not where a RAISE ends: a procedure's first semicolon sits inside its body,
    so "drop up to the semicolon" throws the body away, and the table that
    procedure builds is then known to Ripple nowhere. Count brackets instead.
    """
    depth = first_blanked.count("(") - first_blanked.count(")")
    opened = "(" in first_blanked
    if opened and depth <= 0:
        return start
    index = start + 1
    while index < len(lines):
        blanked = _blank_literals(lines[index], state)
        if _ALWAYS_SCRIPTING.match(blanked) is not None:
            # That always-scripting line is the body's own BEGIN, and the BEGIN
            # line itself is never dropped as part of the signature.
            return index - 1
        depth += blanked.count("(") - blanked.count(")")
        if "(" in blanked:
            opened = True
        if opened and depth <= 0:
            return index
        index += 1
    return start


def _gather_header(
    lines: list[str], start: int, first_blanked: str, state: _ScanState
) -> tuple[int, str, str] | None:
    """A loop header written across several lines, gathered into one."""
    if _HEADER_TAIL.search(first_blanked) is not None:
        return start, lines[start], first_blanked
    written = [lines[start]]
    blanked = [first_blanked]
    index = start + 1
    while index < len(lines):
        copy = _blank_literals(lines[index], state)
        written.append(lines[index])
        blanked.append(copy)
        if _HEADER_TAIL.search(copy) is not None:
            return index, "\n".join(written), "\n".join(blanked)
        index += 1
    return None


def unwrap_blocks(text: str) -> str:
    """Take the scripting out of a file, one line out for every line in.

    Returns the text UNCHANGED, the same object, when there is no scripting in
    it, so callers can hand everything to this without asking first. Asking
    first means walking every line of every file twice, which on a few thousand
    files is minutes rather than seconds.
    """
    lines = text.split("\n")
    out: list[str] = []
    state = _ScanState()
    case_depth = 0
    changed = False
    skip_until = -1
    index = 0
    total = len(lines)

    while index < total:
        line = lines[index]
        # EVERY line goes through the blanking, including lines already being
        # dropped as part of a RAISE or a signature, or the quote state is
        # stale for everything after them.
        blanked = _blank_literals(line, state)

        if index <= skip_until:
            # The rest of a rewrite that covered several lines. A line that is
            # gone contributes nothing to the CASE depth.
            out.append(";")
            index += 1
            continue

        one_line = _one_line_loop(line, blanked)
        if one_line is not None:
            rewritten, body_blanked = one_line
            out.append(rewritten)
            case_depth = _apply_case_depth(body_blanked, case_depth)
            changed = True
            index += 1
            continue

        if _ALWAYS_SCRIPTING.match(blanked) is not None:
            out.append(";")
            changed = True
            index += 1
            continue

        begin_body = _BEGIN_BODY.match(blanked)
        if begin_body is not None:
            # Swap JUST the keyword for a statement end and leave the rest of
            # the line exactly where it is, or the whole body goes to the parser
            # as part of the BEGIN and comes back as one thing nobody can read.
            keyword_end = begin_body.end(1)
            out.append(line[: begin_body.start(1)] + ";" + line[keyword_end:])
            case_depth = _apply_case_depth(blanked[keyword_end:], case_depth)
            changed = True
            index += 1
            continue

        if case_depth == 0 and _RAISE.match(blanked) is not None:
            last = _semicolon_line(blanked, lines, index, state.copy())
            out.append(";")
            if last > index:
                skip_until = last
            changed = True
            index += 1
            continue

        if _PROCEDURE.match(blanked) is not None:
            last = _signature_end(blanked, lines, index, state.copy())
            out.append(";")
            if last > index:
                skip_until = last
            changed = True
            index += 1
            continue

        for_header = _FOR_HEADER.match(blanked)
        while_header = _WHILE_HEADER.match(blanked)
        if for_header is not None or while_header is not None:
            gathered = _gather_header(lines, index, blanked, state.copy())
            if gathered is not None:
                last, header_written, header_blanked = gathered
                header = for_header or while_header
                query = _query_group(header_written, header_blanked, header.end())
                variable = None
                if for_header is not None:
                    variable = header_written[
                        for_header.start(1) : for_header.end(1)
                    ]
                if query is None:
                    out.append(";")
                else:
                    out.append(loop_read(variable, query))
                if last > index:
                    skip_until = last
                changed = True
                index += 1
                continue
            # A gathered header that never finishes: give up on THAT line only.

        if case_depth == 0 and _IF_THEN.match(blanked) is not None:
            # Replace the whole header and the query in the condition goes with
            # it, so the file comes back with risk none and every count zero.
            # The identical guard written as ASSERT reads correctly, and where
            # two spellings of one guard give opposite answers the difference is
            # a bug.
            query = _query_group(line, blanked, 0)
            if query is None:
                out.append(";")
            else:
                out.append(f"SELECT * FROM {query};")
            changed = True
            index += 1
            continue

        if case_depth == 0 and (
            _BARE_END.match(blanked) is not None or _BARE_ELSE.match(blanked) is not None
        ):
            out.append(";")
            changed = True
            index += 1
            continue

        # Kept. Count on every line you keep, including a bare END or ELSE kept
        # because a CASE was open - that END is the one that closes it.
        out.append(line)
        case_depth = _apply_case_depth(blanked, case_depth)
        index += 1

    if not changed:
        return text
    return "\n".join(out)
