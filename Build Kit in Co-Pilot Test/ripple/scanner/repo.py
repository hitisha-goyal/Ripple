from __future__ import annotations

"""Walking a repository folder, holding what was read, and mining SQL out of it.

Everything in here exists so that a later phase can say, honestly, what was
read and what was not. Anything this file passes over silently becomes a gap
nobody downstream can report, so every branch that declines to read a file
records the fact somewhere.
"""

import os
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Sequence

# ---------------------------------------------------------------------------
# Extensions
# ---------------------------------------------------------------------------

# A template suffix is only ever looked through when a SQL suffix is behind it.
# Reading anything at all past a .sql takes load_final.sql.bak with it, and a
# backup read as a live file turns into "this table is built in two files" - a
# fork reported on every scan over a file nothing runs.
TEMPLATE_SUFFIXES: tuple[str, ...] = (
    ".j2",
    ".jinja",
    ".jinja2",
    ".tmpl",
    ".template",
    ".tpl",
    ".mustache",
    ".hbs",
    ".erb",
)

SQL_SUFFIXES: tuple[str, ...] = (".sql", ".sqlx", ".ddl", ".hql")
PROGRAM_SUFFIXES: tuple[str, ...] = (".py", ".scala", ".java", ".sh")
MARKUP_SUFFIXES: tuple[str, ...] = (".yaml", ".yml", ".xml")

READABLE_SUFFIXES: tuple[str, ...] = SQL_SUFFIXES + PROGRAM_SUFFIXES + MARKUP_SUFFIXES

# Written as what is NOT code, never as what is. A file type nobody thought of
# then counts as a gap by default, which is how a middle hop written in a
# notebook or in Terraform stops going missing without a word.
NOT_CODE_SUFFIXES: frozenset[str] = frozenset(
    {
        # prose, documents
        ".md",
        ".markdown",
        ".rst",
        ".txt",
        ".adoc",
        ".pdf",
        ".doc",
        ".docx",
        ".odt",
        ".rtf",
        ".tex",
        # images
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".svg",
        ".ico",
        ".webp",
        ".bmp",
        ".tif",
        ".tiff",
        ".psd",
        # styling, fonts, browser build output
        ".css",
        ".scss",
        ".sass",
        ".less",
        ".woff",
        ".woff2",
        ".ttf",
        ".eot",
        ".otf",
        ".map",
        # packed data
        ".csv",
        ".tsv",
        ".parquet",
        ".avro",
        ".orc",
        ".xlsx",
        ".xls",
        ".pb",
        # archives, binaries
        ".zip",
        ".gz",
        ".tgz",
        ".tar",
        ".bz2",
        ".xz",
        ".7z",
        ".rar",
        ".jar",
        ".war",
        ".whl",
        ".egg",
        ".so",
        ".dll",
        ".dylib",
        ".exe",
        ".bin",
        ".pyc",
        ".pyo",
        ".class",
        ".o",
        ".a",
        ".lib",
        ".pdb",
        # media
        ".mp3",
        ".mp4",
        ".mov",
        ".avi",
        ".wav",
        ".webm",
        ".flac",
        ".ogg",
        # locks, logs, housekeeping
        ".lock",
        ".log",
        ".bak",
        ".swp",
        ".ds_store",
    }
)

# Words that are never a column. Only consulted where a name is read back out
# of text rather than off the parse tree, or a WHERE clause reports a usage of
# a column called AND. The type names matter as much as the keywords:
# CAST(cm13 AS FLOAT64) holds two bare words and only one of them is a column.
NOT_A_COLUMN: frozenset[str] = frozenset(
    {
        "AND",
        "OR",
        "NOT",
        "IN",
        "IS",
        "NULL",
        "TRUE",
        "FALSE",
        "LIKE",
        "BETWEEN",
        "CASE",
        "WHEN",
        "THEN",
        "ELSE",
        "END",
        "AS",
        "CAST",
        "ANY",
        "ALL",
        "STRING",
        "INT64",
        "FLOAT64",
        "BOOL",
        "DATE",
        "TIMESTAMP",
        "SESSION_USER",
        "CURRENT_DATE",
        "CURRENT_TIMESTAMP",
    }
)

# Used only when the settings object carries no size limit of its own. A walk
# with no limit at all will happily pull a two-gigabyte export into memory.
DEFAULT_MAX_FILE_BYTES: int = 2_000_000

# Windows file attributes. RECALL_ON_* mean the bytes are still in the cloud
# and opening the file asks OneDrive to fetch it, which on a machine with no
# network hangs and then fails, once per file, and there can be thousands.
FILE_ATTRIBUTE_OFFLINE = 0x1000
FILE_ATTRIBUTE_RECALL_ON_OPEN = 0x40000
FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS = 0x400000

# The 260-character limit a managed laptop usually still enforces.
LONG_PATH_LIMIT = 260


# ---------------------------------------------------------------------------
# Shapes
# ---------------------------------------------------------------------------


@dataclass
class SourceFile:
    """One file that was read, in memory.

    path is repo-relative with forward slashes, because that is the only form
    a person can go and open. abs_path is kept beside it so the miners can ask
    what the file really is later without guessing.
    """

    path: str
    abs_path: str
    text: str
    lang: str


@dataclass
class SkippedFile:
    """A file that could have been read and was not, with a reason in English."""

    path: str
    reason: str


@dataclass
class Match:
    """One line mentioning a name, as a whole word."""

    path: str
    line: int  # 1-based, because this number is printed and opened
    text: str
    name: str


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------


def effective_ext(path: str) -> str:
    """The last suffix, except that a SQL suffix behind a template one wins.

    load_final.sql.j2 has a suffix of ".j2" as far as Python is concerned, so
    nothing opens it and the "runs the SQL in X" warning cannot fire either.
    A double miss, and the double is what makes it silent.
    """
    base, last = os.path.splitext(path)
    last = last.lower()
    if last in TEMPLATE_SUFFIXES:
        _, inner = os.path.splitext(base)
        if inner.lower() in SQL_SUFFIXES:
            return inner.lower()
    return last


def long_path(abs_path: str) -> str:
    """The form used for OPENING a file on Windows, and for nothing else.

    Real repository folders are 140 characters before the filename starts, and
    long path support is usually switched off on a managed laptop.
    """
    if os.name != "nt":
        return abs_path
    if abs_path.startswith("\\\\?\\"):
        return abs_path
    absolute = os.path.abspath(abs_path)
    if absolute.startswith("\\\\"):
        return "\\\\?\\UNC\\" + absolute[2:]
    return "\\\\?\\" + absolute


def _strip_long_prefix(path: str) -> str:
    if path.startswith("\\\\?\\UNC\\"):
        return "\\\\" + path[len("\\\\?\\UNC\\") :]
    if path.startswith("\\\\?\\"):
        return path[len("\\\\?\\") :]
    return path


def repo_relative(root: str, abs_path: str) -> str:
    """The path a person reads out: inside the repository, forward slashes.

    A finding pointing at a filename that does not exist as printed is a
    finding nobody can check, and one they cannot check is one they dismiss.
    """
    plain_root = _strip_long_prefix(root)
    plain_path = _strip_long_prefix(abs_path)
    try:
        rel = os.path.relpath(plain_path, plain_root)
    except ValueError:
        rel = os.path.basename(plain_path)
    return rel.replace("\\", "/")


def file_attributes(abs_path: str) -> int:
    """Windows attribute bits, asked for defensively.

    A machine that is not Windows, and a Python that does not report them,
    both mean "an ordinary file" - not a crash in the middle of a walk.
    """
    try:
        stat_result = os.stat(long_path(abs_path))
    except OSError:
        return 0
    try:
        return int(getattr(stat_result, "st_file_attributes", 0) or 0)
    except (TypeError, ValueError):
        return 0


def held_in_cloud(attributes: int) -> bool:
    """True when the contents are certainly not on this machine."""
    recall = FILE_ATTRIBUTE_RECALL_ON_OPEN | FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS
    return bool(attributes & recall)


def suspected_offline(attributes: int) -> bool:
    """The older, much looser flag - some backup software sets it on local files.

    On its own it is suspicion only: the file is still opened. It only decides
    anything if the read then fails, and that pairing is what makes opening an
    OFFLINE-flagged file safe in the first place.
    """
    return bool(attributes & FILE_ATTRIBUTE_OFFLINE)


# ---------------------------------------------------------------------------
# How the file was saved
# ---------------------------------------------------------------------------


def decode_bytes(raw: bytes) -> str:
    """Work the encoding out from the bytes rather than asking for UTF-8.

    A byte-order mark is invisible in every editor and lethal to a SQL parser.
    It lands on the FIRST statement of the file, which in a pipeline file is
    the one that names the source table, so the statement that matters is the
    one that is lost and the file still reports as read.
    """
    if raw.startswith(b"\xff\xfe\x00\x00"):
        return raw.decode("utf-32-le", errors="replace").lstrip("\\ufeff")
    if raw.startswith(b"\x00\x00\xfe\xff"):
        return raw.decode("utf-32-be", errors="replace").lstrip("\\ufeff")
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig", errors="replace")
    if raw.startswith(b"\xff\xfe"):
        return raw.decode("utf-16-le", errors="replace").lstrip("\\ufeff")
    if raw.startswith(b"\xfe\xff"):
        return raw.decode("utf-16-be", errors="replace").lstrip("\\ufeff")

    # No mark. PowerShell's ">" redirection has written UTF-16-LE by default
    # for twenty years, and real text has no NUL bytes at all.
    head = raw[:4096]
    if head:
        nul_share = head.count(0) / len(head)
        if nul_share > 0.1:
            # In UTF-16-BE the third byte of "SELECT" is the NUL half of the
            # second character; in UTF-16-LE it is the letter itself.
            encoding = "utf-16-be" if raw[2:3] == b"\x00" else "utf-16-le"
            return raw.decode(encoding, errors="replace").lstrip("\\ufeff")

    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1", errors="replace")


# ---------------------------------------------------------------------------
# What counts as SQL
# ---------------------------------------------------------------------------

# Written too tightly this leaves out every statement that has no SELECT in
# it - a DELETE that clears a published table before a reload, a TRUNCATE, a
# CREATE FUNCTION. Written too loosely, a docstring saying it will "create the
# destination table for you" becomes a statement, and a table that exists
# nowhere appears on screen as a fact. Hence: only those modifiers.
SQL_START_RE = re.compile(
    r"\bSELECT\b"
    r"|\bINSERT\s+INTO\b"
    r"|\bINSERT\s+OVERWRITE\b"
    r"|\bMERGE\s+INTO\b"
    r"|\bUPDATE\b"
    r"|\bDELETE\s+FROM\b"
    r"|\bTRUNCATE\s+TABLE\b"
    r"|\bCREATE\s+OR\s+REPLACE\b"
    r"|\bCREATE\s+(?:(?:TEMP|TEMPORARY|MATERIALIZED|EXTERNAL|SNAPSHOT)\s+)?"
    r"(?:TABLE|VIEW|FUNCTION)\b",
    re.IGNORECASE,
)


def looks_like_sql(text: str) -> bool:
    """Is this block worth handing to the parser at all."""
    return SQL_START_RE.search(text) is not None


def count_sql_starts(text: str) -> int:
    """How many statement starts are written in this text."""
    return len(SQL_START_RE.findall(text))


# ---------------------------------------------------------------------------
# Mining SQL out of a program file
# ---------------------------------------------------------------------------

TRIPLE_QUOTE_RE = re.compile(r"(\"\"\"|''')(.*?)\1", re.DOTALL)

# A quoted piece that sits on one line. Refusing a newline is not a limitation
# to fix: allow one and a single apostrophe in a comment swallows the rest of
# the file.
SINGLE_LINE_STRING_RE = re.compile(r"(['\"])((?:\\.|(?!\1)[^\\\n])*)\1")

ASSIGNED_VAR_RE = re.compile(r"([A-Za-z_]\w*)\s*\+?=\s*$")
PLUS_JOIN_RE = re.compile(r"\s*\+\s*")
PLUS_EQUALS_JOIN_RE = re.compile(r"\s*;?\s*([A-Za-z_]\w*)\s*\+=\s*")

# Commands that RUN SQL. Anchoring on the command is what stops "don't" in a
# comment setting the shell miner off.
SQL_RUNNER_RE = re.compile(
    r"\b(?:bq\s+query"
    r"|psql"
    r"|mysql"
    r"|hive\s+-e"
    r"|impala-shell"
    r"|spark-sql"
    r"|snowsql"
    r"|sqlcmd"
    r"|clickhouse-client"
    r"|beeline"
    r"|athena)\b",
    re.IGNORECASE,
)

HEREDOC_RE = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_]\w*)\1")


def _line_of(text: str, index: int) -> int:
    """0-based line number of a character offset."""
    return text.count("\n", 0, index)


def _mask_triple_quoted(text: str) -> str:
    """Replace triple-quoted regions with spaces of the same length.

    Never remove them, so every offset is still an offset into the real file.
    Three quote characters in a row otherwise read as two empty pieces, and
    the docstring then welds itself onto whatever follows it.
    """
    out: list[str] = []
    last = 0
    for match in TRIPLE_QUOTE_RE.finditer(text):
        out.append(text[last : match.start()])
        region = text[match.start() : match.end()]
        out.append("".join("\n" if ch == "\n" else " " for ch in region))
        last = match.end()
    out.append(text[last:])
    return "".join(out)


def _trim_leading_blank_lines(body: str, line_offset: int) -> tuple[str, int]:
    """Drop blank leading lines and move the offset on by as many."""
    lines = body.split("\n")
    dropped = 0
    while lines and lines[0].strip() == "":
        lines.pop(0)
        dropped += 1
    return "\n".join(lines), line_offset + dropped


def _welded_string_blocks(masked: str) -> list[tuple[str, int]]:
    """Join runs of quoted pieces that are plainly still one statement.

    A program that has to fill something in writes its SQL in pieces, and the
    first piece PARSES on its own because BigQuery is happy with a SELECT that
    has no FROM. Nothing fails, and the scan comes back risk none with the
    coverage card saying there is nothing missing. That is the worst answer
    this tool is capable of giving.
    """
    pieces = [
        (match.start(), match.end(), match.group(2))
        for match in SINGLE_LINE_STRING_RE.finditer(masked)
    ]
    if not pieces:
        return []

    runs: list[list[tuple[int, int, str]]] = []
    current: list[tuple[int, int, str]] = [pieces[0]]
    run_var = _run_variable(masked, pieces[0][0])

    for piece in pieces[1:]:
        between = masked[current[-1][1] : piece[0]]
        if _joins(between, run_var):
            current.append(piece)
            continue
        runs.append(current)
        current = [piece]
        run_var = _run_variable(masked, piece[0])
    runs.append(current)

    blocks: list[tuple[str, int]] = []
    for run in runs:
        body = "".join(part[2] for part in run)
        # A run of two or more SUPPRESSES the ordinary miner over the same
        # characters simply by being emitted in its place: the first piece is
        # a quoted string in its own right, and a statement read once whole
        # and once in half puts every finding in it on screen twice.
        if not looks_like_sql(body):
            continue
        blocks.append((body, _line_of(masked, run[0][0])))
    return blocks


def _run_variable(masked: str, start: int) -> str:
    """The variable a run was assigned to, or "" when there is not one."""
    head = masked[:start]
    match = ASSIGNED_VAR_RE.search(head)
    return match.group(1) if match else ""


def _joins(between: str, run_var: str) -> bool:
    """Is what lies between two quoted pieces plainly still one string."""
    # Never join across a comma. That is a LIST of separate queries, and
    # welding those together invents a statement that is in no file.
    if "," in between:
        return False
    if between.strip(" \t\r\n\\") == "":
        return True
    flattened = between.replace("\\\n", " ").replace("\\\r\n", " ")
    if PLUS_JOIN_RE.fullmatch(flattened):
        return True
    match = PLUS_EQUALS_JOIN_RE.fullmatch(flattened)
    if match:
        # Only to the variable the run before it was assigned to, or two
        # variables holding two different queries become one.
        return bool(run_var) and match.group(1) == run_var
    return False


def extract_sql_blocks(f: SourceFile) -> list[tuple[str, int]]:
    """SQL inside triple-quoted and long single strings, with a 0-based line offset."""
    blocks: list[tuple[str, int]] = []
    text = f.text

    for match in TRIPLE_QUOTE_RE.finditer(text):
        body = match.group(2)
        if not looks_like_sql(body):
            continue
        offset = _line_of(text, match.start(2))
        body, offset = _trim_leading_blank_lines(body, offset)
        blocks.append((body, offset))

    masked = _mask_triple_quoted(text)
    blocks.extend(_welded_string_blocks(masked))

    blocks.sort(key=lambda pair: pair[1])
    return blocks


def _heredoc_blocks(text: str) -> list[tuple[str, int]]:
    """SQL fed to a command through a shell heredoc.

    <<EOF, <<-EOF, <<'EOF', <<"EOF", ending at a line whose only content is
    the tag.
    """
    blocks: list[tuple[str, int]] = []
    lines = text.split("\n")
    index = 0
    while index < len(lines):
        match = HEREDOC_RE.search(lines[index])
        if not match:
            index += 1
            continue
        tag = match.group(2)
        body: list[str] = []
        start = index + 1
        cursor = start
        while cursor < len(lines):
            if lines[cursor].strip() == tag:
                break
            body.append(lines[cursor])
            cursor += 1
        joined = "\n".join(body)
        if looks_like_sql(joined):
            trimmed, offset = _trim_leading_blank_lines(joined, start)
            blocks.append((trimmed, offset))
        index = cursor + 1
    return blocks


def _shell_command_blocks(text: str) -> list[tuple[str, int]]:
    """One quoted argument written across several lines, handed to a SQL runner.

    A shell leaves a single-quoted string completely alone, so this is every
    bit as ordinary as a heredoc - and the plain string miner refuses a
    newline inside a quoted value, so this shape is mined by nothing at all.
    """
    blocks: list[tuple[str, int]] = []
    for match in SQL_RUNNER_RE.finditer(text):
        index = match.end()
        quote = ""
        while index < len(text):
            ch = text[index]
            if ch in " \t":
                index += 1
                continue
            if ch == "\\" and text[index + 1 : index + 2] in ("\n", "\r"):
                # bq's destination flag is usually written on the line above
                # the query, continued with a backslash.
                index += 2
                if text[index - 1 : index] == "\r" and text[index : index + 1] == "\n":
                    index += 1
                continue
            if ch in "'\"":
                quote = ch
                break
            if ch == "\n":
                break
            index += 1
        if not quote:
            continue
        end = text.find(quote, index + 1)
        if end == -1:
            continue
        body = text[index + 1 : end]
        if looks_like_sql(body):
            blocks.append((body, _line_of(text, index)))
    return blocks


# ---------------------------------------------------------------------------
# Mining SQL out of markup
# ---------------------------------------------------------------------------

YAML_KEY_RE = re.compile(
    r"^(?P<lead>\s*(?:-\s+)*)(?P<key>[A-Za-z_][\w.\-]*)\s*:\s*(?P<val>.*?)\s*$"
)

# YAML writes | and >, and it also writes |- >- |+ >+ and |2. Airflow DAGs are
# full of "sql: |-", and matching "|" exactly reads that as a one-line value.
YAML_BLOCK_MARKER_RE = re.compile(r"^[|>][-+]?\d*$")

YAML_SQL_KEY_WORDS = ("sql", "query", "script", "statement")
XML_SQL_TAG_WORDS = ("script", "query", "sql", "statement", "command")

CDATA_RE = re.compile(r"<!\[CDATA\[(.*?)\]\]>", re.DOTALL)
XML_ELEMENT_RE = re.compile(r"<([A-Za-z_][\w.:\-]*)\b[^>]*>(.*?)</\1\s*>", re.DOTALL)


def _unescape_xml(text: str) -> str:
    """Undo the five XML escapes, ampersand LAST or &amp;lt; decodes twice."""
    out = text.replace("&lt;", "<")
    out = out.replace("&gt;", ">")
    out = out.replace("&quot;", '"')
    out = out.replace("&apos;", "'")
    return out.replace("&amp;", "&")


def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip())


def _yaml_blocks(text: str) -> list[tuple[str, int]]:
    blocks: list[tuple[str, int]] = []
    lines = text.split("\n")
    index = 0
    while index < len(lines):
        line = lines[index]
        match = YAML_KEY_RE.match(line)
        if not match:
            index += 1
            continue
        key = match.group("key").lower()
        if not any(word in key for word in YAML_SQL_KEY_WORDS):
            index += 1
            continue

        # Measure from the KEY's column rather than the line's, so "- sql: |"
        # works.
        key_col = len(match.group("lead"))
        value = match.group("val")

        if YAML_BLOCK_MARKER_RE.match(value):
            body_lines: list[str] = []
            cursor = index + 1
            while cursor < len(lines):
                candidate = lines[cursor]
                # A BLANK LINE DOES NOT END A BLOCK. Stop at one and the
                # parser is handed the first half of a statement, which
                # parses, and is therefore counted as read.
                if candidate.strip() != "" and _indent_of(candidate) <= key_col:
                    break
                body_lines.append(candidate)
                cursor += 1
            while body_lines and body_lines[-1].strip() == "":
                body_lines.pop()
            indents = [
                _indent_of(one) for one in body_lines if one.strip() != ""
            ]
            strip_by = min(indents) if indents else 0
            dedented = "\n".join(
                one[strip_by:] if len(one) >= strip_by else one.lstrip()
                for one in body_lines
            )
            trimmed, offset = _trim_leading_blank_lines(dedented, index + 1)
            if looks_like_sql(trimmed):
                blocks.append((trimmed, offset))
            index = cursor
            continue

        if value[:1] in ("'", '"'):
            quote = value[0]
            rest = value[1:]
            if quote in rest:
                body = rest[: rest.index(quote)]
                cursor = index + 1
            else:
                # A quoted YAML value may run over several lines. Taking only
                # the key's own line gave back a CREATE with no SELECT - half
                # a statement, which parses, and was counted as READ.
                parts = [rest]
                cursor = index + 1
                closed = False
                while cursor < len(lines):
                    candidate = lines[cursor].strip()
                    if quote in candidate:
                        parts.append(candidate[: candidate.index(quote)])
                        cursor += 1
                        closed = True
                        break
                    parts.append(candidate)
                    cursor += 1
                if closed:
                    body = " ".join(part for part in parts if part != "")
                else:
                    # If the quote never closes, give back the first line only
                    # rather than swallowing the file.
                    body = rest
                    cursor = index + 1
            if looks_like_sql(body):
                blocks.append((body, index))
            index = cursor
            continue

        if value and looks_like_sql(value):
            blocks.append((value, index))
        index += 1
    return blocks


def _xml_blocks(text: str) -> list[tuple[str, int]]:
    blocks: list[tuple[str, int]] = []
    taken: set[int] = set()

    for match in CDATA_RE.finditer(text):
        body = _unescape_xml(match.group(1))
        if not looks_like_sql(body):
            continue
        offset = _line_of(text, match.start(1))
        trimmed, offset = _trim_leading_blank_lines(body, offset)
        blocks.append((trimmed, offset))
        taken.add(match.start(1))

    for match in XML_ELEMENT_RE.finditer(text):
        tag = match.group(1).lower()
        if not any(word in tag for word in XML_SQL_TAG_WORDS):
            continue
        inner = match.group(2)
        if match.start(2) in taken:
            continue
        body = _unescape_xml(CDATA_RE.sub(r"\1", inner))
        if not looks_like_sql(body):
            continue
        offset = _line_of(text, match.start(2))
        trimmed, offset = _trim_leading_blank_lines(body, offset)
        blocks.append((trimmed, offset))

    blocks.sort(key=lambda pair: pair[1])
    return blocks


def _first_code_line_is_sql(text: str) -> bool:
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped == "":
            continue
        if stripped.startswith("#") or stripped.startswith("<?") or stripped.startswith("<!--"):
            continue
        return SQL_START_RE.match(stripped) is not None
    return False


def extract_markup_sql(f: SourceFile) -> list[tuple[str, int]]:
    """SQL taken out of a .yaml, .yml or .xml file, with its starting line.

    Handing one of these to a SQL parser whole can only ever fail, and every
    ordinary Kubernetes YAML in the repository then lands on the check-by-hand
    list - which is the one place Ripple admits what it missed.
    """
    ext = effective_ext(f.path)
    if ext == ".xml":
        blocks = _xml_blocks(f.text)
    elif ext in (".yaml", ".yml"):
        blocks = _yaml_blocks(f.text)
    else:
        blocks = []

    if not blocks and _first_code_line_is_sql(f.text):
        return [(f.text, 0)]
    return blocks


# ---------------------------------------------------------------------------
# What a file yields
# ---------------------------------------------------------------------------


def _dedupe_blocks(blocks: Sequence[tuple[str, int]]) -> list[tuple[str, int]]:
    """A one-line bq query is found by the ordinary string miner as well.

    Read twice, every finding in it is counted twice over.
    """
    seen: set[str] = set()
    out: list[tuple[str, int]] = []
    for body, offset in blocks:
        key = re.sub(r"\s+", " ", body).strip().lower()
        if key in seen:
            continue
        seen.add(key)
        out.append((body, offset))
    out.sort(key=lambda pair: pair[1])
    return out


def statements_for(f: SourceFile) -> list[tuple[str, int]]:
    """Every block of SQL this file yields, each with its 0-based line offset."""
    ext = effective_ext(f.path)
    if ext in MARKUP_SUFFIXES:
        return _dedupe_blocks(extract_markup_sql(f))
    if ext == ".sh":
        blocks = list(extract_sql_blocks(f))
        blocks.extend(_heredoc_blocks(f.text))
        blocks.extend(_shell_command_blocks(f.text))
        return _dedupe_blocks(blocks)
    if ext in PROGRAM_SUFFIXES:
        return _dedupe_blocks(extract_sql_blocks(f))
    if ext in SQL_SUFFIXES:
        return [(f.text, 0)]
    return []


def looks_like_unread_sql(f: SourceFile, blocks: Sequence[tuple[str, int]]) -> bool:
    """SQL is plainly written in this file and some of it was not taken out.

    This COUNTS, it does not ask "were there any blocks". One recognised sql:
    block must not buy silence for the bash_command: beside it.
    """
    in_file = count_sql_starts(f.text)
    if in_file == 0:
        return False
    mined = sum(count_sql_starts(body) for body, _ in blocks)
    return mined < in_file


# ---------------------------------------------------------------------------
# References and destinations
# ---------------------------------------------------------------------------

SQL_FILE_REF_RE = re.compile(
    r"[\w\-./\\]*\w[\w\-./\\]*"
    r"\.(?:sql|sqlx|ddl|hql)"
    r"(?:\.(?:j2|jinja|jinja2|tmpl|template|tpl|mustache|hbs|erb))?",
    re.IGNORECASE,
)


def sql_file_refs(f: SourceFile) -> list[tuple[str, int]]:
    """Every "something.sql" name this file mentions, with its 1-based line.

    A DAG that runs the most important query in the pipeline used to look
    identical to an empty file. The optional template tail is here so a
    .sql.j2 kept outside the repository is still reported by name.
    """
    ext = effective_ext(f.path)
    if ext not in PROGRAM_SUFFIXES and ext not in MARKUP_SUFFIXES:
        return []

    found: list[tuple[str, int]] = []
    seen: set[str] = set()
    for number, line in enumerate(f.text.split("\n"), start=1):
        for match in SQL_FILE_REF_RE.finditer(line):
            name = match.group(0).replace("\\", "/")
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            found.append((name, number))
    return found


WRITE_CALL_RE = re.compile(
    r"(?:saveAsTable|insertInto|createOrReplaceTempView|registerTempTable)"
    r"\s*\(\s*(['\"])([^'\"]+)\1"
)
WRITE_KEYWORD_RE = re.compile(
    r"(?:destination_table|destination)\s*=\s*(['\"])([^'\"]+)\1", re.IGNORECASE
)
TO_GBQ_RE = re.compile(r"to_gbq\s*\(\s*(['\"])([^'\"]+)\1")

# Anchor on destinationTable and stop at the closing brace. A bare tableId
# also sits under sourceTable, and reading that turns a READ into a write and
# invents a chain.
DESTINATION_TABLE_BLOCK_RE = re.compile(
    r"destinationTable\s*[\"']?\s*:\s*\{(.*?)\}", re.DOTALL | re.IGNORECASE
)
TABLE_ID_RE = re.compile(r"[\"']tableId[\"']\s*:\s*[\"']([^\"']+)[\"']")

# The bq command line itself, where nothing is quoted at all. Require the name
# to be QUALIFIED, or destination_table=None becomes a published table called
# None.
BQ_CLI_DESTINATION_RE = re.compile(
    r"--destination_table[=\s]+([A-Za-z0-9_$\-]+[.:][A-Za-z0-9_$.:\-]+)", re.IGNORECASE
)


def _last_part(name: str) -> str:
    """Take the last part after a dot OR a colon.

    bq's own separator between project and dataset is a colon, so the
    character class needs one.
    """
    parts = re.split(r"[.:]", name)
    return parts[-1].strip() if parts else name.strip()


def written_tables(f: SourceFile) -> list[str]:
    """Tables a program writes to, named outside the SQL, in file order.

    Spark and BigQuery jobs run a bare SELECT and name the destination in the
    program, so without this the chain stops exactly where the interesting
    renames are. Each name only once: a job writing the same table on two
    lines has one destination, not two.
    """
    ext = effective_ext(f.path)
    if ext not in PROGRAM_SUFFIXES:
        return []

    hits: list[tuple[int, str]] = []
    for pattern in (WRITE_CALL_RE, WRITE_KEYWORD_RE, TO_GBQ_RE):
        for match in pattern.finditer(f.text):
            hits.append((match.start(), match.group(2)))
    for match in DESTINATION_TABLE_BLOCK_RE.finditer(f.text):
        inner = TABLE_ID_RE.search(match.group(1))
        if inner:
            hits.append((match.start(), inner.group(1)))
    for match in BQ_CLI_DESTINATION_RE.finditer(f.text):
        hits.append((match.start(), match.group(1)))

    hits.sort(key=lambda pair: pair[0])
    names: list[str] = []
    seen: set[str] = set()
    for _, raw in hits:
        name = _last_part(raw)
        if not name or name.lower() in ("none", "null"):
            continue
        if name.lower() in seen:
            continue
        seen.add(name.lower())
        names.append(name)
    return names


# ---------------------------------------------------------------------------
# Which unopened types reach the answer
# ---------------------------------------------------------------------------


def unopened_code_types(unknown_ext: dict[str, int]) -> dict[str, int]:
    """The same tally with the types that are KNOWN not to be code taken out.

    Leave any of them in and the warning fires on every scan of every
    repository - every one has a README, a lock file and a logo - and a
    warning printed every time is one nobody reads.
    """
    kept = {
        ext: count
        for ext, count in unknown_ext.items()
        if ext.lower() not in NOT_CODE_SUFFIXES
    }
    return dict(sorted(kept.items(), key=lambda pair: (-pair[1], pair[0])))


# ---------------------------------------------------------------------------
# The walk
# ---------------------------------------------------------------------------


@dataclass
class RepoIndex:
    """Every readable file in the repository, held in memory.

    Text compresses well and only files with a useful extension are kept, so a
    real repository fits easily.
    """

    root: str = ""
    files: list[SourceFile] = field(default_factory=list)
    skipped: list[SkippedFile] = field(default_factory=list)
    held_online: list[str] = field(default_factory=list)
    too_long: list[str] = field(default_factory=list)
    in_skipped_dirs: list[str] = field(default_factory=list)
    skipped_dir_names: list[str] = field(default_factory=list)
    unknown_ext: dict[str, int] = field(default_factory=dict)

    # -- building ---------------------------------------------------------

    @classmethod
    def build(
        cls,
        root: str,
        cfg: Any,
        on_progress: Callable[[int, str], None] | None = None,
    ) -> "RepoIndex":
        index = cls(root=root)

        skip_names = {
            str(name).strip().lower()
            for name in (getattr(cfg, "skip_dirs", ()) or ())
            if str(name).strip()
        }
        max_bytes = getattr(cfg, "max_file_bytes", None)
        if not isinstance(max_bytes, int) or max_bytes <= 0:
            max_bytes = DEFAULT_MAX_FILE_BYTES

        walk_root = long_path(root)
        seen_skipped_dirs: set[str] = set()
        scanned = 0

        for dirpath, dirnames, filenames in os.walk(walk_root):
            # Deterministic order, so two runs over the same folder produce the
            # same lists and a difference between them means a real difference.
            dirnames.sort()
            filenames.sort()

            for filename in filenames:
                abs_path = os.path.join(dirpath, filename)
                rel = repo_relative(root, abs_path)
                scanned += 1
                ext = effective_ext(rel)

                # Judge the skip names against the path INSIDE the repository,
                # never the whole path - a repository that happens to live
                # under a folder called build must not read as empty.
                folders = rel.split("/")[:-1]
                hit = [name for name in folders if name.lower() in skip_names]
                if hit:
                    if ext in READABLE_SUFFIXES:
                        index.in_skipped_dirs.append(rel)
                        for name in hit:
                            if name.lower() not in seen_skipped_dirs:
                                seen_skipped_dirs.add(name.lower())
                                index.skipped_dir_names.append(name)
                    if on_progress is not None:
                        on_progress(scanned, rel)
                    continue

                if ext not in READABLE_SUFFIXES:
                    # No bare continue with no counter. The point is not to
                    # read them; it is that the NEXT unlisted extension is
                    # visible instead of silent. Only files that HAVE an
                    # extension, or a Makefile is tallied under a blank one.
                    if ext:
                        index.unknown_ext[ext] = index.unknown_ext.get(ext, 0) + 1
                    if on_progress is not None:
                        on_progress(scanned, rel)
                    continue

                index._take_file(abs_path, rel, ext, max_bytes)
                if on_progress is not None:
                    on_progress(scanned, rel)

        index.skipped_dir_names.sort(key=str.lower)
        return index

    def _take_file(self, abs_path: str, rel: str, ext: str, max_bytes: int) -> None:
        attributes = file_attributes(abs_path)
        if held_in_cloud(attributes):
            # Counted THERE AND NOWHERE ELSE. There is nothing on this machine
            # to open, so listing it on the check-by-hand list as well counts
            # two problems where there is one.
            self.held_online.append(rel)
            return

        try:
            size = os.path.getsize(long_path(abs_path))
        except OSError as error:
            self._record_open_failure(abs_path, rel, attributes, error)
            return

        if size > max_bytes:
            self.skipped.append(
                SkippedFile(
                    path=rel,
                    reason=(
                        "This file is "
                        + _plain_size(size)
                        + ", which is larger than the "
                        + _plain_size(max_bytes)
                        + " Ripple opens, so it was not read."
                    ),
                )
            )
            return

        try:
            with open(long_path(abs_path), "rb") as handle:
                raw = handle.read()
        except OSError as error:
            self._record_open_failure(abs_path, rel, attributes, error)
            return

        text = decode_bytes(raw)
        if "\x00" in text:
            # A NUL left in the text makes the parser swallow the statement it
            # sits in and say nothing.
            self.skipped.append(
                SkippedFile(
                    path=rel,
                    reason=(
                        "This file contains NUL bytes, so it is either not text "
                        "or it was saved in an encoding Ripple could not work out."
                    ),
                )
            )
            return

        self.files.append(
            SourceFile(
                path=rel,
                abs_path=_strip_long_prefix(abs_path),
                text=text,
                lang=ext.lstrip("."),
            )
        )

    def _record_open_failure(
        self, abs_path: str, rel: str, attributes: int, error: OSError
    ) -> None:
        message = str(error)
        # A read that FAILS on a file carrying the loose OFFLINE flag is the
        # same problem said the same way: held online, rather than an error
        # code nobody can act on.
        if "cloud" in message.lower() or suspected_offline(attributes):
            self.held_online.append(rel)
            return
        if len(_strip_long_prefix(abs_path)) > LONG_PATH_LIMIT:
            self.too_long.append(rel)
            return
        self.skipped.append(
            SkippedFile(
                path=rel,
                reason="Ripple could not open this file: " + message,
            )
        )

    # -- asking it things -------------------------------------------------

    def get(self, path: str) -> SourceFile | None:
        wanted = path.replace("\\", "/")
        for one in self.files:
            if one.path == wanted:
                return one
        lowered = wanted.lower()
        for one in self.files:
            if one.path.lower() == lowered:
                return one
        return None

    def search(self, names: Iterable[str]) -> list[Match]:
        """Every line mentioning any of these names as a whole word.

        Case-insensitive, and a substring is not a mention: a column called id
        is not found by a column called identity_flag.
        """
        wanted = [str(name) for name in names if str(name).strip()]
        if not wanted:
            return []
        patterns = [
            (
                name,
                re.compile(
                    r"(?<![A-Za-z0-9_])" + re.escape(name) + r"(?![A-Za-z0-9_])",
                    re.IGNORECASE,
                ),
            )
            for name in wanted
        ]

        matches: list[Match] = []
        for one in self.files:
            for number, line in enumerate(one.text.split("\n"), start=1):
                for name, pattern in patterns:
                    if pattern.search(line):
                        matches.append(
                            Match(path=one.path, line=number, text=line, name=name)
                        )
                        break
        return matches

    def files_mentioning(self, names: Iterable[str]) -> list[SourceFile]:
        paths = {match.path for match in self.search(names)}
        return [one for one in self.files if one.path in paths]


def _plain_size(size: int) -> str:
    """A size a non-engineer can read, rather than a byte count."""
    if size >= 1024 * 1024:
        return "{:.1f} MB".format(size / (1024 * 1024))
    if size >= 1024:
        return "{:.0f} KB".format(size / 1024)
    return "{} bytes".format(size)
