"""Shapes the SQL parser simply refuses, rewritten on the way in.

Some BigQuery statements are perfectly ordinary and the parser still refuses
them. When it refuses one it does not refuse only that statement - it can lose
the statements either side of it too, so one unusual line costs a whole file.

This file keeps the same two rules as the templating file, and for the same
reasons. The rewrite is done to a COPY on the way INTO the parser; the file on
disk is never touched and everything shown on screen comes from the file as
written, so somebody sent to a line to check finds what they were told they
would find. And every replacement puts back exactly as many line breaks as it
swallowed, because a finding points at a line number and that number is the
only thing anybody can act on.

Where a new shape turns up later that the parser refuses, it is added HERE.
Never work around a parse failure in the reading file or the lineage file - by
the time the trouble reaches those, the statement has already been lost.
"""

from __future__ import annotations

import re

_NAME = r"(`[^`]*`|[A-Za-z_][A-Za-z0-9_$.]*)"

# One cheap scan of the text. Almost every file in a repository contains none
# of these words, and walking every file twice is minutes rather than seconds
# on a few thousand. The bare-TABLE test is deliberately NOT behind a word
# boundary: a backticked function name ends in a backtick, so `p.d.f`(TABLE x)
# would be skipped while APPENDS(TABLE x) was caught.
_TRIGGER = re.compile(
    r"""(?ix)
      \bUNDROP\b
    | \bSNAPSHOT\b
    | \bREPLICA\b
    | \bSYSTEM_TIME\b
    | [(,]\s*TABLE\s
    | \bWITH\s+CONNECTION\b
    | \bWITH\s+PARTITION\s+COLUMNS\b
    | \bLOAD\s+DATA\b
    | \bEXPORT\s+DATA\b
    | \bconfig\s*\{
    | \bjs\s*\{
    | \bpre_operations\s*\{
    | \bpost_operations\s*\{
    """
)

_UNDROP = re.compile(r"(?i)\bUNDROP\s+TABLE\b")
_SNAPSHOT = re.compile(r"(?i)\bCREATE\s+(OR\s+REPLACE\s+)?SNAPSHOT\s+TABLE\b")
_REPLICA = re.compile(
    r"(?i)\bCREATE\s+(OR\s+REPLACE\s+)?MATERIALIZED\s+VIEW\s+"
    + _NAME
    + r"\s+AS\s+REPLICA\s+OF\s+"
    + _NAME
)
_SYSTEM_TIME = re.compile(r"(?i)\bFOR\s+SYSTEM_TIME\s+AS\s+OF\b")
_COPY_WORD = re.compile(r"(?i)\b(CLONE|COPY)\b")
_TABLE_ARGUMENT = re.compile(r"(?i)([(,])(\s*)TABLE(\s)")
_WITH_CONNECTION = re.compile(r"(?i)\bWITH\s+CONNECTION\s+" + _NAME)
_WITH_PARTITION_COLUMNS = re.compile(r"(?i)\bWITH\s+PARTITION\s+COLUMNS\b")
_LOAD_DATA = re.compile(r"(?i)\bLOAD\s+DATA\s+(INTO|OVERWRITE)\s+")
_FROM_FILES = re.compile(r"(?i)\bFROM\s+FILES\s*\(")
_EXPORT_DATA = re.compile(r"(?i)\bEXPORT\s+DATA\b")
_OPTIONS_CALL = re.compile(r"(?i)\bOPTIONS\s*\(")
_QUERY_START = re.compile(r"(?i)\b(SELECT|WITH)\b")
_URI_OPTION = re.compile(r"(?i)\bURIS?\s*=")
_FIRST_STRING = re.compile(r"(?s)'([^']*)'|\"([^\"]*)\"")


def _blank_quoted(text: str) -> str:
    """A copy of the text with strings and comments turned into spaces.

    Exactly as long as the text it was made from, and with its line breaks left
    alone, so a position measured on the copy cuts the real text in the right
    place. Everything here counts brackets and braces on this copy, because an
    OPTIONS clause is full of quoted strings and a bracket inside one closes
    nothing.
    """
    out = list(text)
    length = len(text)
    index = 0
    quote = ""
    in_block_comment = False
    in_line_comment = False
    while index < length:
        character = text[index]

        if in_line_comment:
            if character == "\n":
                in_line_comment = False
            else:
                out[index] = " "
            index += 1
            continue

        if in_block_comment:
            if text.startswith("*/", index):
                out[index] = " "
                out[index + 1] = " "
                in_block_comment = False
                index += 2
            else:
                if character != "\n":
                    out[index] = " "
                index += 1
            continue

        if quote:
            if character == "\\" and quote != "`":
                out[index] = " "
                if index + 1 < length and text[index + 1] != "\n":
                    out[index + 1] = " "
                index += 2
                continue
            if text.startswith(quote, index):
                for position in range(index, index + len(quote)):
                    out[position] = " "
                index += len(quote)
                quote = ""
                continue
            if character != "\n":
                out[index] = " "
            index += 1
            continue

        if text.startswith("--", index) or character == "#":
            out[index] = " "
            in_line_comment = True
            index += 1
            continue

        if text.startswith("/*", index):
            out[index] = " "
            out[index + 1] = " "
            in_block_comment = True
            index += 2
            continue

        opened = ""
        for candidate in ("'''", '"""', "'", '"', "`"):
            if text.startswith(candidate, index):
                opened = candidate
                break
        if opened:
            for position in range(index, index + len(opened)):
                out[position] = " "
            quote = opened
            index += len(opened)
            continue

        index += 1
    return "".join(out)


def _drop_span(text: str, start: int, end: int) -> str:
    """Take a span out, putting back exactly the line breaks it held."""
    removed = text[start:end]
    return text[:start] + "\n" * removed.count("\n") + text[end:]


def _sub_keep_lines(pattern: re.Pattern[str], replacement: str, text: str) -> str:
    """A plain substitution that cannot lose a line break."""

    def swap(match: re.Match[str]) -> str:
        return replacement + "\n" * match.group(0).count("\n")

    return pattern.sub(swap, text)


def _closing(blanked: str, open_index: int, opener: str, closer: str) -> int | None:
    """The index just past the bracket or brace that closes this one."""
    depth = 0
    for index in range(open_index, len(blanked)):
        character = blanked[index]
        if character == opener:
            depth += 1
        elif character == closer:
            depth -= 1
            if depth == 0:
                return index + 1
    return None


def _statement_start(blanked: str, position: int) -> int:
    """Where the statement holding this position began."""
    marker = blanked.rfind(";", 0, position)
    if marker == -1:
        return 0
    return marker + 1


# ---------------------------------------------------------------------------
# The shapes
# ---------------------------------------------------------------------------


def _rewrite_sqlx_blocks(text: str) -> str:
    """config { } and js { } dropped whole, the operations blocks kept."""
    for name in ("config", "js"):
        pattern = re.compile(r"(?i)\b" + name + r"\s*\{")
        while True:
            blanked = _blank_quoted(text)
            match = pattern.search(blanked)
            if match is None:
                break
            closing = _closing(blanked, match.end() - 1, "{", "}")
            if closing is None:
                break
            text = _drop_span(text, match.start(), closing)

    for name in ("pre_operations", "post_operations"):
        pattern = re.compile(r"(?i)\b" + name + r"\s*\{")
        while True:
            blanked = _blank_quoted(text)
            match = pattern.search(blanked)
            if match is None:
                break
            closing = _closing(blanked, match.end() - 1, "{", "}")
            if closing is None:
                break
            # These hold real SQL that really runs: drop the braces, keep the
            # contents, and end them with a semicolon so they read as one more
            # statement in the file.
            characters = list(text)
            for position in range(match.start(), match.end()):
                if characters[position] != "\n":
                    characters[position] = " "
            characters[closing - 1] = ";"
            text = "".join(characters)
    return text


def _rewrite_snapshot(text: str) -> str:
    """CREATE SNAPSHOT TABLE becomes CREATE TABLE, keeping the CLONE."""

    def swap(match: re.Match[str]) -> str:
        head = "CREATE OR REPLACE TABLE" if match.group(1) else "CREATE TABLE"
        return head + "\n" * match.group(0).count("\n")

    return _SNAPSHOT.sub(swap, text)


def _rewrite_replica(text: str) -> str:
    """A materialised view that is a replica is a whole-table copy."""

    def swap(match: re.Match[str]) -> str:
        head = "CREATE OR REPLACE TABLE" if match.group(1) else "CREATE TABLE"
        return (
            f"{head} {match.group(2)} COPY {match.group(3)}"
            + "\n" * match.group(0).count("\n")
        )

    return _REPLICA.sub(swap, text)


def _drop_system_time(text: str) -> str:
    """Drop FOR SYSTEM_TIME AS OF, but only beside a CLONE or a COPY.

    The same words are legal on an ordinary FROM and the parser reads those, so
    dropping them everywhere would quietly change what a readable statement
    says.
    """
    searched_from = 0
    while True:
        blanked = _blank_quoted(text)
        match = _SYSTEM_TIME.search(blanked, searched_from)
        if match is None:
            return text
        start = _statement_start(blanked, match.start())
        if _COPY_WORD.search(blanked[start : match.start()]) is None:
            searched_from = match.end()
            continue
        end = blanked.find(";", match.end())
        if end == -1:
            end = len(text)
        text = _drop_span(text, match.start(), end)
        searched_from = match.start()


def _rewrite_undrop(text: str) -> str:
    """UNDROP TABLE t is a hard parse error, which takes its neighbours down.

    Rewritten so it lands as a generic command, with the table name still in
    the text of that command for the reading file to take back out.
    """
    return _sub_keep_lines(_UNDROP, "EXECUTE UNDROP TABLE", text)


def _drop_table_arguments(text: str) -> str:
    """A bare TABLE in argument position is a hard parse error.

    This is how an incremental load is written, which is how a published table
    is kept up to date.
    """
    blanked = _blank_quoted(text)
    pieces: list[str] = []
    previous = 0
    for match in _TABLE_ARGUMENT.finditer(blanked):
        # Drop the word and leave the name behind, keeping the whitespace
        # either side so nothing moves onto another line.
        pieces.append(text[previous : match.start()])
        pieces.append(text[match.start() : match.start(2)])
        pieces.append(text[match.start(2) : match.end(2)])
        pieces.append(text[match.start(3) : match.end(3)])
        previous = match.end()
    if not pieces:
        return text
    pieces.append(text[previous:])
    return "".join(pieces)


def _drop_external_clauses(text: str) -> str:
    """WITH CONNECTION and WITH PARTITION COLUMNS, off every external table."""
    while True:
        # Matched on the text AS WRITTEN, because the connection is a
        # backticked name and the blanked copy has emptied those backticks -
        # there would be nothing left for the name pattern to match.
        match = _WITH_CONNECTION.search(text)
        if match is None:
            break
        text = _drop_span(text, match.start(), match.end())

    while True:
        blanked = _blank_quoted(text)
        match = _WITH_PARTITION_COLUMNS.search(blanked)
        if match is None:
            break
        end = match.end()
        rest = blanked[end:]
        stripped = len(rest) - len(rest.lstrip())
        if end + stripped < len(blanked) and blanked[end + stripped] == "(":
            closing = _closing(blanked, end + stripped, "(", ")")
            if closing is not None:
                end = closing
        text = _drop_span(text, match.start(), end)
    return text


def _rewrite_load_data(text: str) -> str:
    """LOAD DATA INTO t (a STRING) becomes CREATE TABLE t (a STRING).

    Often the only place a landing table's columns are written down anywhere in
    the repository.
    """
    text = _sub_keep_lines(_LOAD_DATA, "CREATE TABLE ", text)
    while True:
        blanked = _blank_quoted(text)
        match = _FROM_FILES.search(blanked)
        if match is None:
            return text
        closing = _closing(blanked, match.end() - 1, "(", ")")
        if closing is None:
            return text
        # A bucket rather than a table, so it goes.
        text = _drop_span(text, match.start(), closing)


def _rewrite_export_data(text: str) -> str:
    """Leave the SELECT and take everything before it away."""
    searched_from = 0
    while True:
        blanked = _blank_quoted(text)
        match = _EXPORT_DATA.search(blanked, searched_from)
        if match is None:
            return text
        after = match.end()
        options = _OPTIONS_CALL.search(blanked, after)
        if options is not None:
            closing = _closing(blanked, options.end() - 1, "(", ")")
            if closing is not None:
                after = closing
        query = _QUERY_START.search(blanked, after)
        if query is None:
            searched_from = match.end()
            continue
        text = _drop_span(text, match.start(), query.start())
        searched_from = match.start()


def export_targets(text: str) -> list[tuple[int, str]]:
    """Every EXPORT DATA in the text: its 0-based line, and where it delivers.

    Read BEFORE the rewrite, because the rewrite takes the OPTIONS clause with
    it. Where no uri is written down the feed comes back empty rather than
    guessed at.
    """
    blanked = _blank_quoted(text)
    found: list[tuple[int, str]] = []
    for match in _EXPORT_DATA.finditer(blanked):
        line = text.count("\n", 0, match.start())
        feed = ""
        options = _OPTIONS_CALL.search(blanked, match.end())
        if options is not None:
            closing = _closing(blanked, options.end() - 1, "(", ")")
            if closing is not None:
                body = text[options.end() - 1 : closing]
                body_blanked = blanked[options.end() - 1 : closing]
                uri = _URI_OPTION.search(body_blanked)
                if uri is not None:
                    string = _FIRST_STRING.search(body, uri.end())
                    if string is not None:
                        feed = (
                            string.group(1)
                            if string.group(1) is not None
                            else string.group(2)
                        )
        found.append((line, feed))
    return found


def rescue_text(text: str) -> str:
    """Rewrite the shapes the parser refuses, on a copy, keeping every line.

    Everything rewritten here must still be reported honestly downstream. A
    statement that only became readable because of a rewrite is still a real
    statement, but a statement that could NOT be rescued must end up on the
    check-by-hand list rather than silently producing nothing.
    """
    if _TRIGGER.search(text) is None:
        return text
    rescued = _rewrite_sqlx_blocks(text)
    rescued = _rewrite_snapshot(rescued)
    rescued = _rewrite_replica(rescued)
    rescued = _drop_system_time(rescued)
    rescued = _rewrite_undrop(rescued)
    rescued = _drop_table_arguments(rescued)
    rescued = _drop_external_clauses(rescued)
    rescued = _rewrite_load_data(rescued)
    rescued = _rewrite_export_data(rescued)
    return rescued
