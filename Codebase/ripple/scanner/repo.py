"""Reading the repository and finding candidate files.

Step one of a scan is deliberately dumb and fast: find every file that so much
as mentions the name. Understanding what the mention *means* happens later.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from ..config import Settings, settings as default_settings

# Which files carry SQL inside string literals rather than being SQL themselves.
EMBEDDED_SQL_EXTS = {".py", ".scala", ".java", ".sh"}

# Which files carry SQL inside markup rather than being SQL themselves. An
# Airflow YAML holds it under ``sql: |``; an Oozie workflow.xml holds it in a
# ``<script>`` element. Both were being handed to the SQL parser whole, which is
# never going to work -- so every one of them landed on the "check by hand" list
# instead. Measured: twelve ordinary Kubernetes YAML files and one genuinely
# broken .sql gave couldNotRead 13, sorted alphabetically, with the real failure
# last. That list is the one place Ripple admits what it missed, and burying it
# under config files nobody wrote SQL in is how a real miss stops being seen.
MARKUP_SQL_EXTS = {".yaml", ".yml", ".xml"}

# File types that plainly do not hold pipeline SQL. Every OTHER type Ripple does
# not open is carried onto the scan answer as a gap, because an extension nobody
# thought of -- .ipynb, .tf, .j2, or no extension at all -- is exactly how the
# middle hop of a chain goes missing without a word being said about it.
#
# The list is written this way round on purpose. A new file type Ripple has
# never seen counts as a gap by default; only what is KNOWN to be prose, an
# image, packed data or a binary is passed over in silence. The opposite way
# round, every unheard-of extension would be silently harmless, which is the
# failure this exists to stop.
#
# The repository screen still lists EVERY skipped extension, this one included.
# What this decides is only whether the ANSWER carries the warning -- and a
# warning printed over every scan, because every repository has a README, is one
# nobody reads.
NOT_CODE_EXTS = frozenset({
    # prose and documents
    ".md", ".markdown", ".rst", ".txt", ".adoc", ".pdf", ".doc", ".docx", ".odt",
    ".rtf", ".tex",
    # images
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp", ".bmp", ".tif",
    ".tiff", ".psd",
    # styling, fonts and browser build output
    ".css", ".scss", ".sass", ".less", ".woff", ".woff2", ".ttf", ".eot",
    ".otf", ".map",
    # packed data -- rows, not the code that makes them
    ".csv", ".tsv", ".parquet", ".avro", ".orc", ".xlsx", ".xls", ".pb",
    # archives and binaries
    ".zip", ".gz", ".tgz", ".tar", ".bz2", ".xz", ".7z", ".rar", ".jar", ".war",
    ".whl", ".egg", ".so", ".dll", ".dylib", ".exe", ".bin", ".pyc", ".pyo",
    ".class", ".o", ".a", ".lib", ".pdb",
    # media
    ".mp3", ".mp4", ".mov", ".avi", ".wav", ".webm", ".flac", ".ogg",
    # locks, logs and housekeeping
    ".lock", ".log", ".bak", ".swp", ".ds_store",
})


# A query kept as a template is named for what it IS and then for how it is
# filled in: load_final.sql.j2. Python calls that file's suffix ".j2", so it was
# never opened -- and the "runs the SQL in X, which is not in this repository"
# warning could not fire either, because that only matches names ending ".sql".
# A double miss, which is exactly what made it silent: no file read, no gap
# reported, and a published table that traced back to nothing.
#
# Only these outer suffixes count, and only over an inner SQL one. Reading
# anything at all past a .sql would take load_final.sql.bak with it, and a
# backup file read as a live one turns into "this table is built in two files".
TEMPLATE_SUFFIXES = frozenset({
    ".j2", ".jinja", ".jinja2", ".tmpl", ".template", ".tpl",
    ".mustache", ".hbs", ".erb",
})
_TEMPLATABLE = frozenset({".sql", ".sqlx", ".ddl", ".hql"})


def effective_ext(path) -> str:
    """The extension that decides how this file is read. See TEMPLATE_SUFFIXES."""
    suffixes = [s.lower() for s in path.suffixes]
    if (len(suffixes) >= 2 and suffixes[-1] in TEMPLATE_SUFFIXES
            and suffixes[-2] in _TEMPLATABLE):
        return suffixes[-2]
    return path.suffix.lower()


def unopened_code_types(unknown_ext: dict) -> dict:
    """The unopened file types that could plausibly hold SQL. See NOT_CODE_EXTS."""
    return {ext: n for ext, n in unknown_ext.items()
            if ext.lower() not in NOT_CODE_EXTS}

# ── files that are not really on this machine ──────────────────────────────
# OneDrive's Files On-Demand leaves a file in the folder listing, with its real
# name and its real size, when the contents are still in the cloud. It looks
# exactly like a file. Opening it asks OneDrive to fetch it, which needs the
# network -- and Ripple Offline is for a machine that has none.
#
# This is the most dangerous thing that can happen to a scan. A repository half
# of which was never read comes back with a short finding list and a green tick,
# and the whole point of this tool is that the green tick can be trusted. So
# these are found before anything is opened, counted, and said out loud.
FILE_ATTRIBUTE_OFFLINE = 0x1000
FILE_ATTRIBUTE_RECALL_ON_OPEN = 0x40000
FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS = 0x400000

# The two recall flags are set by the cloud provider itself and mean one thing
# only: the contents are not here. OFFLINE is older and much looser -- some
# backup software sets it on files that are perfectly local -- so on its own it
# is treated as a suspicion, and the file is still opened. Refusing to read a
# repository because a backup tool touched a flag would be its own disaster.
_DEFINITELY_ONLINE_ONLY = FILE_ATTRIBUTE_RECALL_ON_OPEN | FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS

ONLINE_ONLY_REASON = "not really on this machine - OneDrive is holding it online-only"

# Windows still refuses a path over 260 characters unless long path support has
# been switched on, and on a managed office laptop it usually has not been. His
# real folders are about 140 characters before the filename even starts, so this
# is not a theoretical limit. Prefixing the root with \\?\ opts this walk out of
# the limit whatever the machine is set to.
_LONG_PATH_LIMIT = 260


def _walk_root(root: Path) -> Path:
    """The same folder, in the form Windows will walk past 260 characters."""
    if os.name != "nt":
        return root
    text = str(root)
    if text.startswith("\\\\?\\"):
        return root
    absolute = os.path.abspath(text)
    if absolute.startswith("\\\\"):                 # \\server\share\...
        return Path("\\\\?\\UNC\\" + absolute[2:])
    return Path("\\\\?\\" + absolute)


def online_only(p: Path) -> int:
    """Which placeholder flags this file carries, or 0 for an ordinary file."""
    if os.name != "nt":
        return 0
    try:
        attrs = p.stat().st_file_attributes            # type: ignore[attr-defined]
    except (OSError, AttributeError):
        return 0
    return attrs & (_DEFINITELY_ONLINE_ONLY | FILE_ATTRIBUTE_OFFLINE)


# ── the first three bytes of a file ────────────────────────────────────────
# A byte-order mark is invisible in every editor and lethal to a SQL parser. It
# arrives on the front of the FIRST statement, which in a pipeline file is the
# one that names the source table -- so the statement that matters is the one
# that is lost, and the file still reports as read.
#
# Measured before this: the first statement failed, `risk` came back `none`, and
# with two statements in the file the wording actively reassured -- "1 of 2
# statements in this file could not be read - the other 1 was". Windows writes
# these by default: Notepad, PowerShell's `Out-File`, Excel's CSV export, and
# every "save as UTF-8" box in Office.
#
# UTF-16 is the same problem one step worse. PowerShell's `>` redirection has
# written UTF-16-LE by default for twenty years, and read as UTF-8 the file
# comes back as text with a NUL between every letter, which parses as nothing at
# all and says so about the whole file rather than about one statement.
_BOMS = (
    (b"\xef\xbb\xbf", "utf-8-sig"),
    (b"\xff\xfe\x00\x00", "utf-32"),
    (b"\x00\x00\xfe\xff", "utf-32"),
    (b"\xff\xfe", "utf-16"),
    (b"\xfe\xff", "utf-16"),
)
# How much of the head to look at when there is no mark to go by, and how much
# of it has to be NUL before UTF-16 is the better guess. Real text has none.
_SNIFF_BYTES = 4096
_NUL_SHARE = 0.10


def _decoded(raw: bytes) -> str:
    """The file as text, whichever way Windows happened to write it.

    Raises UnicodeDecodeError like ``read_text`` does, so the caller's existing
    fallback still runs.
    """
    for mark, encoding in _BOMS:
        if raw.startswith(mark):
            return raw.decode(encoding)
    head = raw[:_SNIFF_BYTES]
    if head.count(0) > len(head) * _NUL_SHARE:
        # No mark, but full of NULs. Which end the NULs sit on says which way
        # round it is; guessing wrong here only costs the same failure as now.
        try:
            return raw.decode("utf-16-le" if raw[1:2] == b"\x00" else "utf-16-be")
        except UnicodeDecodeError:
            pass
    return raw.decode("utf-8")


def _looks_like_a_cloud_error(exc: BaseException) -> bool:
    """Did this read fail because the file was still in the cloud?

    Matched on the words Windows itself uses rather than on error numbers, so a
    number remembered wrongly cannot turn a real problem into a reassuring one.
    """
    return "cloud" in str(exc).lower()

LANG_BY_EXT = {
    ".sql": "SQL",
    ".sqlx": "Dataform SQL",
    ".ddl": "SQL",
    ".hql": "Hive SQL",
    # "Python", not "Spark SQL": a .py file here might be a Spark job, a
    # BigQuery job or neither, and guessing wrong is visible on screen.
    ".py": "Python",
    ".scala": "Scala",
    ".java": "Java",
    ".sh": "Shell",
    ".xml": "XML",
    ".yaml": "YAML",
    ".yml": "YAML",
}


@dataclass
class SourceFile:
    path: str            # repo-relative, forward slashes
    abs_path: Path
    text: str
    lang: str

    @property
    def lines(self) -> list[str]:
        return self.text.splitlines()


@dataclass
class Match:
    file: str
    line_no: int
    line: str
    name: str


@dataclass
class RepoIndex:
    """Every readable file in the repository, held in memory.

    The mock repository is tiny. A real one is bigger but still small compared
    with the memory on any server -- text compresses extremely well and we only
    keep files with an extension we can do something with.
    """

    files: list[SourceFile] = field(default_factory=list)
    skipped: list[dict] = field(default_factory=list)
    root: Path | None = None
    # Files OneDrive is keeping in the cloud, which is a different thing from a
    # file that would not parse and needs saying differently.
    held_online: list[str] = field(default_factory=list)
    # Files whose path went past what Windows will open on this machine.
    too_long: list[str] = field(default_factory=list)
    # Files Ripple never looked at because of the folder they sit in: build,
    # dist, target, venv and the rest. Those names mean "generated output" in
    # most repositories and "our SQL" in a few, and when they mean the second
    # thing an entire folder of code is missing from every answer with nothing
    # on screen to say so. Counted, and said.
    in_skipped_dirs: list[str] = field(default_factory=list)
    # Files whose extension is not on the read list, counted by extension. This
    # is the only place an unlisted file type is recorded at all: the walk had a
    # bare ``continue`` with no counter, so a repository whose pipeline lives in
    # .sqlx, .ipynb or .tf files reported `indexed False, risk none, prod []`
    # with NOTHING anywhere saying a file had been passed over. The point is not
    # to read them -- it is that the NEXT unlisted extension is visible instead
    # of silent.
    unknown_ext: dict = field(default_factory=dict)
    skipped_dir_names: list[str] = field(default_factory=list)

    @classmethod
    def build(cls, root: Path | str, cfg: Settings | None = None,
              on_progress=None) -> "RepoIndex":
        """Read the repository. ``on_progress(done, total, label)`` is called as
        it goes, with real counts -- a repository this size takes minutes, and a
        screen that says nothing for four of them looks broken."""
        cfg = cfg or default_settings
        root = Path(root)
        idx = cls(root=root)
        if not root.exists():
            idx.skipped.append({"file": str(root), "reason": "repository folder not found"})
            return idx

        walk = _walk_root(root)
        candidates = [p for p in sorted(walk.rglob("*")) if p.is_file()]
        total = len(candidates)
        for seen, p in enumerate(candidates, start=1):
            if on_progress is not None and (seen % 25 == 0 or seen == total):
                on_progress(seen, total, "Reading the files")
            # Judged on the path *inside* the repository, never the whole path.
            # Otherwise a repository that merely happens to live under a folder
            # called build, dist, target or venv has every one of its files
            # skipped, and the scan comes back clean because it read nothing.
            relative = p.relative_to(walk)
            ext = effective_ext(p)
            hit = next((part for part in relative.parts if part in cfg.skip_dirs), "")
            if hit:
                # Only worth mentioning when it is a file Ripple would otherwise
                # have read. A folder of compiled output holds thousands of
                # files nobody wants counted.
                if ext in cfg.code_extensions:
                    idx.in_skipped_dirs.append(relative.as_posix())
                    if hit not in idx.skipped_dir_names:
                        idx.skipped_dir_names.append(hit)
                continue
            if ext not in cfg.code_extensions:
                # Counted, not read. See RepoIndex.unknown_ext.
                if ext:
                    idx.unknown_ext[ext] = idx.unknown_ext.get(ext, 0) + 1
                continue
            rel = relative.as_posix()

            # Held in the cloud: do not open it. Opening asks OneDrive to fetch
            # it, which on a machine with no network hangs and then fails, once
            # per file -- and there can be thousands.
            # Counted here and nowhere else. A file that was never opened is not
            # a file to "check by hand" -- there is nothing on this machine to
            # open. Listing it in both places counts two problems where there is
            # one, and tells somebody to go and read a file that is not there.
            flags = online_only(p)
            if flags & _DEFINITELY_ONLINE_ONLY:
                idx.held_online.append(rel)
                continue

            try:
                size = p.stat().st_size
                if size > cfg.max_file_bytes:
                    idx.skipped.append(
                        {"file": rel, "reason": f"file is {size // 1024} KB - too large to read"}
                    )
                    continue
                text = _decoded(p.read_bytes())
            except UnicodeDecodeError:
                try:
                    text = p.read_text(encoding="latin-1")
                except Exception as exc:  # pragma: no cover - defensive
                    idx.skipped.append({"file": rel, "reason": f"could not decode ({exc})"})
                    continue
            except Exception as exc:
                # A read that fails on a file already flagged OFFLINE, or that
                # fails with Windows' own cloud wording, is the same problem as
                # above -- said in the same words rather than as an error code
                # nobody can act on.
                if flags or _looks_like_a_cloud_error(exc):
                    idx.held_online.append(rel)
                elif len(str(p)) > _LONG_PATH_LIMIT:
                    idx.too_long.append(rel)
                else:
                    idx.skipped.append({"file": rel, "reason": f"could not open ({exc})"})
                continue
            # A NUL that survived decoding. The parser swallows the statement it
            # sits in and says nothing at all -- measured: couldNotRead 0, no
            # warning of any kind, risk none. Either this is a mis-decoded file
            # the sniff above did not catch, or it is not text; both are worth
            # saying out loud rather than half-reading.
            if "\x00" in text:
                idx.skipped.append({
                    "file": rel,
                    "reason": "contains NUL bytes - it is not plain text, or it was "
                              "saved in an encoding Ripple could not work out",
                    "hint": "Open it and save it as UTF-8. Nothing in it has been read.",
                })
                continue
            idx.files.append(
                SourceFile(path=rel, abs_path=p, text=text, lang=LANG_BY_EXT.get(ext, "Text"))
            )
        return idx

    # ── searching ──────────────────────────────────────────────────────────
    @staticmethod
    def _pattern(names: list[str]) -> re.Pattern:
        parts = sorted({re.escape(n) for n in names if n}, key=len, reverse=True)
        if not parts:
            return re.compile(r"(?!x)x")  # matches nothing
        return re.compile(r"\b(" + "|".join(parts) + r")\b", re.IGNORECASE)

    def search(self, names: list[str]) -> list[Match]:
        """Every line mentioning any of these names, as whole words."""
        pat = self._pattern(names)
        out: list[Match] = []
        for f in self.files:
            if not pat.search(f.text):
                continue
            for i, line in enumerate(f.lines, start=1):
                m = pat.search(line)
                if m:
                    out.append(Match(file=f.path, line_no=i, line=line.rstrip(), name=m.group(1)))
        return out

    def files_mentioning(self, names: list[str]) -> list[SourceFile]:
        pat = self._pattern(names)
        return [f for f in self.files if pat.search(f.text)]

    def get(self, path: str) -> SourceFile | None:
        for f in self.files:
            if f.path == path:
                return f
        return None


# ── pulling SQL out of programs that build it as text ──────────────────────
_TRIPLE = re.compile(r'("""|\'\'\')(?P<body>.*?)\1', re.DOTALL)
_SINGLE = re.compile(r'"(?P<body>[^"\n]{40,})"|\'(?P<body2>[^\'\n]{40,})\'')
# Which blocks of text inside a program, a YAML file or a shell script are worth
# handing to the SQL parser.
#
# Every word here used to need a SELECT in it somewhere, so a statement that has
# none was mined by nothing: a DELETE that clears a published table before a
# reload, a TRUNCATE, a CREATE FUNCTION. The file was not read, and it went onto
# the "check by hand" list saying there was SQL in it that could not be taken
# out -- which named neither the table nor the column. Measured on a real
# BigQuery warehouse: 24 such blocks in 9 files, 18 of them a DELETE against a
# table that same repository publishes.
#
# Written tightly on purpose, and this is the whole difficulty of the list. It
# is matched against ordinary prose -- docstrings, comments, log messages -- and
# a loose CREATE ... TABLE takes "this helper will create the destination table"
# with it. Measured: three docstrings in one repository became statements, each
# one a table on screen that does not exist anywhere. So only real SQL modifiers
# may sit between CREATE and its noun, never "the", "a" or "your".
_LOOKS_SQL = re.compile(
    r"""\b(
          SELECT
        | INSERT\s+(?:INTO|OVERWRITE)
        | MERGE\s+INTO
        | UPDATE
        | DELETE\s+FROM
        | TRUNCATE\s+TABLE
        | CREATE\s+OR\s+REPLACE
        | CREATE\s+(?:TEMP\s+|TEMPORARY\s+|MATERIALIZED\s+|EXTERNAL\s+|SNAPSHOT\s+)?
          (?:TABLE|VIEW|FUNCTION)
      )\b""",
    re.IGNORECASE | re.VERBOSE,
)


# ── SQL a program builds out of several strings ───────────────────────────
# One statement, written as pieces, is the ordinary way a program that has to
# fill something in writes SQL::
#
#     sql  = "CREATE OR REPLACE TABLE final_published AS SELECT cm13 "
#     sql += "FROM customer_demographics WHERE dt = @d"
#
# Every miner below looks for a whole statement inside ONE pair of quotes, so
# what it found here was the first half. And the first half PARSES -- BigQuery
# is happy with a SELECT that has no FROM -- so nothing failed, nothing landed
# on the check-by-hand list, and the scan came back `risk none, prod [],
# coverage complete` over a job that really does rebuild the published table
# out of that column. A green tick, with "I could see all of it" printed beside
# it. That is the worst answer this tool is capable of giving.
#
# The pieces are welded back together on the way in. Only where the join is
# plainly one string -- whitespace, a +, a line continuation, or the same
# variable += -- and never across a comma, so a LIST of separate queries is
# left as the separate queries it is.
#
# Every character position is kept: the quotes and the joining text are replaced
# by spaces and newlines of exactly the same length, never removed. A finding
# still points at the line the statement starts on, which is the only line
# anybody can go and look at.
_STR_PREFIX = r"[fFrRbBuU]{0,2}"
# One quoted piece, on one line. Its own line, deliberately: the miner below
# joins pieces itself, and a quote allowed to run over a line break is how one
# apostrophe in a comment swallows the rest of a file.
_PIECE = re.compile(r"""(?P<q>['"])(?P<body>[^'"\n]*)(?P=q)""")
# What may sit BETWEEN two pieces for them to still be one string: whitespace, a
# line continuation, a +, or the same variable being added to. Never a comma --
# that is a LIST of separate queries, and welding those together would invent a
# statement that is in no file.
_WELD_GAP = re.compile(
    r"""^[ \t]*(?:\\\r?\n[ \t]*)?\+?[ \t]*(?:\r?\n[ \t]*)?"""
    r"""(?:(?P<name>\w+)[ \t]*\+=[ \t]*)?""" + _STR_PREFIX + r"""$""")
_ASSIGNED = re.compile(
    r"""(?P<name>\w+)[ \t]*\+?=[ \t]*""" + _STR_PREFIX + r"""['"]""")


def welded_blocks(text: str) -> tuple[list[tuple[str, int]], list[tuple[int, int]]]:
    """One statement written as several strings, joined back into one.

    Gives back the joined blocks AND the character spans they were built from.
    The spans matter: the first piece of a welded run is a quoted string in its
    own right, so the ordinary miner finds it too, and a statement read once
    whole and once in half puts every finding in it on screen twice.

    Only runs of TWO OR MORE pieces are welded. A lone string is already found
    by the ordinary miners and is left to them.

    The line offset is the line the FIRST piece starts on, which is the line of
    the file somebody opens to check the finding.
    """
    out: list[tuple[str, int]] = []
    spans: list[tuple[int, int]] = []
    # A triple-quoted block is three quote characters in a row, so the piece
    # scanner reads its fence as two empty pieces and welds the whole docstring
    # onto whatever follows it. Blanked to spaces first -- same length, so every
    # offset below is still an offset into the real file. What is inside them is
    # already mined by _TRIPLE.
    scan = _TRIPLE.sub(lambda m: " " * (m.end() - m.start()), text)
    pieces = list(_PIECE.finditer(scan))
    used = 0
    while used < len(pieces):
        run = [pieces[used]]
        at = used + 1
        while at < len(pieces):
            gap = scan[run[-1].end():pieces[at].start()]
            m = _WELD_GAP.match(gap)
            if m is None:
                break
            if m.group("name"):
                # "sql += ..." only joins to the variable the run was assigned
                # to. Two variables holding two queries must stay two queries.
                before = _ASSIGNED.findall(scan[:run[0].end()])
                owner = before[-1] if before else None
                if owner is not None and owner != m.group("name"):
                    break
            run.append(pieces[at])
            at += 1
        if len(run) > 1:
            body = "".join(p.group("body") for p in run)
            if _LOOKS_SQL.search(body):
                out.append((body, scan[:run[0].start("body")].count("\n")))
                spans.append((run[0].start(), run[-1].end()))
        used = at if at > used else used + 1
    return out, spans


def extract_sql_blocks(f: SourceFile) -> list[tuple[str, int]]:
    """Return (sql_text, line_offset) for SQL found inside a program file.

    line_offset is the 0-based line number in the file where the block starts,
    so findings can still point at a real line in the real file.
    """
    blocks: list[tuple[str, int]] = []
    # One statement written as several strings, joined back into one. See
    # welded_blocks -- without it the miners take the first piece, that piece
    # parses on its own, and the scan reports complete coverage over half a
    # statement.
    welded, welded_spans = welded_blocks(f.text)
    blocks.extend(welded)
    text = f.text

    def already_welded(at: int) -> bool:
        return any(lo <= at < hi for lo, hi in welded_spans)

    for m in _TRIPLE.finditer(text):
        body = m.group("body")
        if _LOOKS_SQL.search(body):
            offset = text[: m.start("body")].count("\n")
            blocks.append((body, offset))
    for m in _SINGLE.finditer(text):
        body = m.group("body") or m.group("body2") or ""
        if _LOOKS_SQL.search(body):
            start = m.start("body") if m.group("body") else m.start("body2")
            # This piece was already read as part of a whole statement above.
            # Reading it again puts every finding in it on screen twice.
            if already_welded(start):
                continue
            offset = text[:start].count("\n")
            blocks.append((body, offset))
    return blocks


# ── SQL kept inside markup and inside a shell script ───────────────────────
# Three shapes, all of them ordinary, none of them readable as SQL as they
# stand. Every one of these measured `risk unknown, prod []` before this: the
# statement that builds the published table was sitting in the file in plain
# sight and no scan could reach it.
#
#     Airflow YAML     sql: |            <- a block scalar
#     Oozie XML        <script>...       <- element text, often in CDATA
#     a shell job      bq query <<EOF    <- a heredoc
#
# The line each block starts on is carried out with it, so a finding still
# points at the real line of the real file.

# ``sql:``, ``query:``, ``script:`` and the handful of names that mean the same
# thing. Matched loosely at both ends because real files write ``sql_query:``,
# ``hive_script:`` and ``bql:`` -- but anchored on the whole key so that
# ``sql_conn_id:`` (a connection name, not a query) does not match.
_YAML_SQL_KEY = re.compile(
    r"^(?P<lead>[ \t]*(?:-[ \t]+)*)"
    r"(?P<key>[\"']?[A-Za-z0-9_.\-]*(?:sql|query|script|statement)[A-Za-z0-9_.\-]*[\"']?)"
    r"[ \t]*:[ \t]*(?P<rest>.*)$",
    re.IGNORECASE,
)
# ``|``, ``>``, ``|-``, ``>+``, ``|2`` -- YAML's ways of saying "the value is
# the indented block below".
_YAML_BLOCK_MARK = re.compile(r"^[|>][-+]?\d*[ \t]*$")


def _yaml_quoted_value(lines: list[str], at: int, rest: str) -> tuple[str, int]:
    """A value written on the key's line, and the last line it occupies.

    A quoted YAML scalar may run over several lines and is folded back into one
    when it is read. Stopping at the first line handed the parser half a
    statement -- and a half-statement that still parses is counted as read,
    which is worse than not reading it at all.
    """
    quote = rest[:1]
    if quote not in ("'", '"'):
        return rest.strip("\"'"), at
    if rest.count(quote) >= 2:
        return rest[1:rest.rfind(quote)], at
    parts = [rest[1:]]
    for j in range(at + 1, len(lines)):
        line = lines[j]
        end = line.find(quote)
        if end >= 0:
            parts.append(line[:end])
            return " ".join(p.strip() for p in parts), j
        parts.append(line)
    # The quote never closes. Give back the first line only, exactly as before,
    # rather than swallowing the rest of the file.
    return rest.strip("\"'"), at


def _yaml_blocks(text: str) -> list[tuple[str, int]]:
    """SQL held under a ``sql:``-ish key in a YAML file."""
    out: list[tuple[str, int]] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        m = _YAML_SQL_KEY.match(lines[i])
        if not m:
            i += 1
            continue
        # The key's own column, not the line's indent -- a list item writes
        # "  - sql: |" and the block under it is indented past the "sql", not
        # past the dash.
        col = len(m.group("lead"))
        rest = m.group("rest").strip()
        if not _YAML_BLOCK_MARK.match(rest):
            # A value on the key's own line. YAML lets a quoted one run over
            # several lines, and taking only the first gave back
            # "CREATE OR REPLACE TABLE final_published AS" with no SELECT --
            # half a statement, handed to the parser, and counted as read.
            body, i = _yaml_quoted_value(lines, i, rest)
            if _LOOKS_SQL.search(body):
                out.append((body, i))
            i += 1
            continue
        body_lines: list[str] = []
        j = i + 1
        while j < len(lines):
            line = lines[j]
            if line.strip() and len(line) - len(line.lstrip()) <= col:
                break                       # dedented back out of the block
            body_lines.append(line)
            j += 1
        # Strip the block's own indent, and no more. Taking the first line's
        # indent off every line is what YAML itself does.
        pad = min((len(b) - len(b.lstrip()) for b in body_lines if b.strip()), default=0)
        body = "\n".join(b[pad:] if len(b) >= pad else b for b in body_lines)
        if _LOOKS_SQL.search(body):
            out.append((body, i + 1))
        i = j
    return out


# An element whose contents are a query. Oozie writes <script>, Hadoop tooling
# writes <query> and <command>, and several write it inside a CDATA section so
# that the SQL's own < and > do not have to be escaped.
_XML_SQL_ELEMENT = re.compile(
    r"<\s*(?P<tag>[A-Za-z0-9_.:\-]*(?:script|query|sql|statement|command)[A-Za-z0-9_.:\-]*)"
    r"(?:\s[^>]*)?>(?P<body>.*?)</\s*(?P=tag)\s*>",
    re.IGNORECASE | re.DOTALL,
)
_CDATA = re.compile(r"<!\[CDATA\[(?P<body>.*?)\]\]>", re.DOTALL)
_XML_ENTITIES = (("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'),
                 ("&apos;", "'"), ("&#10;", "\n"), ("&amp;", "&"))


def _unescape_xml(text: str) -> str:
    """XML's five escapes, undone. ``&amp;`` last, or ``&amp;lt;`` decodes twice."""
    for mark, ch in _XML_ENTITIES:
        text = text.replace(mark, ch)
    return text


def _xml_blocks(text: str) -> list[tuple[str, int]]:
    """SQL held in the text of an XML element, or in a CDATA section."""
    out: list[tuple[str, int]] = []
    seen: set[int] = set()
    for m in _XML_SQL_ELEMENT.finditer(text):
        start = m.start("body")
        body = m.group("body")
        inner = _CDATA.search(body)
        if inner is not None:
            start += inner.start("body")
            body = inner.group("body")
        body = _unescape_xml(body)
        if _LOOKS_SQL.search(body):
            seen.add(start)
            out.append((body, text[:start].count("\n")))
    # A CDATA section under a tag this does not know the name of. Only worth
    # taking when it is plainly SQL, which _LOOKS_SQL already decides.
    for m in _CDATA.finditer(text):
        if m.start("body") in seen:
            continue
        body = _unescape_xml(m.group("body"))
        if _LOOKS_SQL.search(body):
            out.append((body, text[: m.start("body")].count("\n")))
    return out


# bq query <<EOF ... EOF, and every variation of it: quoted so the shell leaves
# the body alone, and <<- so the terminator may be indented.
_HEREDOC = re.compile(r"<<-?[ \t]*(?P<q>['\"]?)(?P<tag>[A-Za-z_][A-Za-z0-9_]*)(?P=q)")


def _heredoc_blocks(text: str) -> list[tuple[str, int]]:
    """SQL fed to a command through a shell heredoc."""
    out: list[tuple[str, int]] = []
    lines = text.splitlines()
    starts = {}
    for m in _HEREDOC.finditer(text):
        starts.setdefault(text[: m.start()].count("\n"), []).append(m.group("tag"))
    i = 0
    while i < len(lines):
        tags = starts.get(i)
        if not tags:
            i += 1
            continue
        tag = tags[0]
        body_lines: list[str] = []
        j = i + 1
        while j < len(lines) and lines[j].strip() != tag:
            body_lines.append(lines[j])
            j += 1
        body = "\n".join(body_lines)
        if _LOOKS_SQL.search(body):
            out.append((body, i + 1))
        i = j + 1
    return out


# The OTHER way a shell script hands a query to a command: as one quoted
# argument, written across several lines. A shell leaves a single-quoted string
# completely alone, so this is every bit as ordinary as a heredoc::
#
#     bq query --use_legacy_sql=false 'CREATE OR REPLACE TABLE final_published AS
#     SELECT id, cm13 FROM customer_demographics'
#
# The string miner every other language uses refuses a newline inside a quoted
# value -- it has to, or one stray apostrophe in a Python comment swallows the
# rest of the file -- so this shape was mined by nothing. Measured, beside a
# heredoc in the same file: the heredoc was read and this was not, and the file
# reported one gap rather than naming which of the two was missed.
#
# Anchored on a command that RUNS SQL rather than on the quote, for exactly the
# apostrophe reason above. Starting from ``bq query`` and reading to the closing
# quote cannot be set off by "don't" in a comment.
_RUNS_SQL_CMD = re.compile(
    r"\b(?:bq\s+query|psql|mysql|hive\s+-e|impala-shell|spark-sql|snowsql|"
    r"sqlcmd|clickhouse-client|beeline|athena)\b[^\n'\"]*",
    re.IGNORECASE,
)


def _shell_argument_blocks(text: str) -> list[tuple[str, int]]:
    """SQL handed to a shell command as one quoted argument. See _RUNS_SQL_CMD."""
    out: list[tuple[str, int]] = []
    for m in _RUNS_SQL_CMD.finditer(text):
        i = m.end()
        # Skip the flags between the command and its query, which may run over
        # a backslash-continued line before the quote opens.
        while i < len(text) and text[i] in " \t\\\n":
            i += 1
        if i >= len(text) or text[i] not in "'\"":
            continue
        quote = text[i]
        close = text.find(quote, i + 1)
        if close == -1:
            continue
        body = text[i + 1:close]
        if _LOOKS_SQL.search(body):
            out.append((body, text[: i + 1].count("\n")))
    return out


# A file whose FIRST line of code is a SQL keyword really is SQL, whatever it is
# called. Rare, but a .xml holding nothing but a CREATE would otherwise be read
# as markup with no SQL in it and silently produce nothing.
_OPENS_WITH_SQL = re.compile(
    r"^\s*(?:--[^\n]*\n|#[^\n]*\n|/\*.*?\*/|\s)*"
    r"(SELECT|WITH|CREATE|INSERT|MERGE|UPDATE|DELETE|ALTER|TRUNCATE|EXPORT|LOAD)\b",
    re.IGNORECASE | re.DOTALL,
)


def extract_markup_sql(f: SourceFile) -> list[tuple[str, int]]:
    """SQL taken out of a YAML or XML file, with the line each block starts on."""
    ext = effective_ext(f.abs_path)
    blocks = _xml_blocks(f.text) if ext == ".xml" else _yaml_blocks(f.text)
    if blocks:
        return blocks
    if _OPENS_WITH_SQL.match(f.text):
        return [(f.text, 0)]
    return []


def statements_for(f: SourceFile) -> list[tuple[str, int]]:
    """SQL statements in a file, with the line each one starts on."""
    ext = effective_ext(f.abs_path)
    if ext in MARKUP_SQL_EXTS:
        return extract_markup_sql(f)
    if ext in EMBEDDED_SQL_EXTS:
        blocks = extract_sql_blocks(f)
        if ext == ".sh":
            blocks += _heredoc_blocks(f.text)
            blocks += _shell_argument_blocks(f.text)
            # A one-line ``bq query 'SELECT ...'`` is found by the ordinary
            # string miner AND by the argument miner. Reading it twice would
            # count every finding in it twice over.
            blocks = list(dict.fromkeys(blocks))
        return blocks
    return [(f.text, 0)]


# ── a program that runs SQL kept somewhere else ────────────────────────────
# His pipeline has two folders of Airflow DAGs. Some hold their SQL as a string,
# which is read above. Plenty of others name a .sql file and run that -- either
# by opening it, or by handing Airflow a filename and letting template_searchpath
# find it. Ripple got nothing out of those files and said nothing about them, so
# a DAG that runs the most important query in the pipeline looked identical to an
# empty file.
#
# Both shapes come down to the same thing: a string ending in .sql.
#
# ... and a templated one is named load_final.sql.j2, so the optional template
# suffix is part of the name. Without it, a .j2 that lives OUTSIDE the
# repository could not be reported either: the file was not opened, and the
# "runs the SQL in X" warning did not match the name, so nothing was said at
# all. See TEMPLATE_SUFFIXES.
_TEMPLATE_TAIL = r"(?:\.(?:j2|jinja2?|tmpl|template|tpl|mustache|hbs|erb))?"
_SQL_FILE_REF = re.compile(
    r"""["']([^"'\n]*?[A-Za-z0-9_\-]+\.sql""" + _TEMPLATE_TAIL + r""")["']""")
# The same thing in markup, where the value carries no quotes at all:
#     sql: queries/load_final.sql
#     <script>hive/load_final.sql</script>
_MARKUP_SQL_FILE_REF = re.compile(
    r"""(?:[:>=][ \t]*|["'])([^\s"'<>]*[A-Za-z0-9_\-]+\.sql"""
    + _TEMPLATE_TAIL + r""")\b""")


def sql_file_refs(f: SourceFile) -> list[dict]:
    """Every .sql file this program names, with the line it names it on."""
    ext = effective_ext(f.abs_path)
    if ext not in EMBEDDED_SQL_EXTS and ext not in MARKUP_SQL_EXTS:
        return []
    pattern = _MARKUP_SQL_FILE_REF if ext in MARKUP_SQL_EXTS else _SQL_FILE_REF
    out: list[dict] = []
    seen: set[str] = set()
    for m in pattern.finditer(f.text):
        ref = m.group(1).strip()
        if not ref or ref.lower() in seen:
            continue
        seen.add(ref.lower())
        out.append({"ref": ref, "line": f.text[: m.start()].count("\n") + 1})
    return out


def looks_like_unread_sql(f: SourceFile, blocks: list[tuple[str, int]]) -> bool:
    """More SQL is written in this file than could be taken out of it.

    Two shapes. The first is SQL built by adding short strings together -- no
    single piece long enough to be recognised, and the statement never existing
    as text anywhere. Worth reporting, because the alternative is a file with a
    CREATE TABLE in it that Ripple treats as empty.

    The second is why this counts rather than asking "were there any blocks".
    An Airflow YAML, an Oozie workflow and a shell job all normally hold SEVERAL
    tasks of DIFFERENT kinds, and Ripple knows how to mine some of them. One
    recognised ``sql:`` block used to buy silence for the ``bash_command:``
    beside it -- measured: two blocks in one file, one mined and one lost, and
    couldNotRead came back 0 with the coverage card reporting no gaps at all.
    Removing the recognised block from that same file put it straight back on
    the check-by-hand list, which is the whole tell.
    """
    ext = effective_ext(f.abs_path)
    if ext not in EMBEDDED_SQL_EXTS and ext not in MARKUP_SQL_EXTS:
        return False
    in_file = len(_LOOKS_SQL.findall(f.text))
    if not in_file:
        return False
    mined = sum(len(_LOOKS_SQL.findall(body)) for body, _ in blocks)
    return mined < in_file


# A Spark or Scala job usually runs a bare SELECT and then writes the result
# from the surrounding program, not from SQL. Without this the chain stops dead
# at the job -- which is exactly where the interesting renames tend to happen.
_WRITE_TARGET = re.compile(
    r"""(?:saveAsTable|insertInto|createOrReplaceTempView|registerTempTable)\s*\(\s*["']([A-Za-z0-9_.]+)["']""",
    re.IGNORECASE,
)

# The same problem in the BigQuery world. A Python job there runs a bare SELECT
# and names its destination in the job settings, not in the SQL -- so without
# this the chain stops at the job, exactly as it would for Spark. Project ids
# may contain hyphens, hence the wider character set.
_BQ_WRITE_TARGET = re.compile(
    r"""(?:destination(?:_table)?\s*=\s*["']([A-Za-z0-9_.:\-]+)["']"""
    r"""|to_gbq\s*\(\s*["']([A-Za-z0-9_.\-]+)["'])""",
    re.IGNORECASE,
)

# Airflow's BigQueryInsertJobOperator does not write the name at all. It hands
# BigQuery its own API shape -- a NESTED dict, camelCase, the name split across
# three keys::
#
#     "destinationTable": {"projectId": "prj", "datasetId": "marts",
#                          "tableId": "final_published"}
#
# Measured before this: groups [], "the name appears, but no lineage to a
# production table", over a DAG that really does load the published table.
#
# Anchored on destinationTable and stopped at the closing brace on purpose. A
# bare "tableId" also appears under sourceTable and sourceUris, and reading
# those would turn a READ into a write and invent a chain that is not there.
_BQ_JSON_TARGET = re.compile(
    r"""["']destinationTable["']\s*:\s*\{[^}]*?["']tableId["']\s*:\s*["']([A-Za-z0-9_\-]+)["']""",
    re.IGNORECASE | re.DOTALL,
)

# Straight off the bq command line, where BigQuery's OWN separator between the
# project and the dataset is a COLON and the value carries no quotes at all::
#
#     bq query --destination_table=prj:marts.final_published --use_legacy_sql=false ...
#
# The name must be QUALIFIED -- one dot or one colon in it -- because unquoted
# means anything at all otherwise, and destination_table=None would have become
# a published table called None.
_BQ_CLI_TARGET = re.compile(
    r"""destination(?:_table)?=([A-Za-z0-9_\-]+[.:][A-Za-z0-9_.:\-]+)""",
    re.IGNORECASE,
)


def written_tables(f: SourceFile) -> list[str]:
    """Tables a program file writes to, in the order they appear."""
    if effective_ext(f.abs_path) not in EMBEDDED_SQL_EXTS:
        return []
    hits: list[tuple[int, str]] = []
    for pat in (_WRITE_TARGET, _BQ_WRITE_TARGET, _BQ_JSON_TARGET, _BQ_CLI_TARGET):
        for m in pat.finditer(f.text):
            raw = next((g for g in m.groups() if g), "")
            if raw:
                # project:dataset.table and project.dataset.table both end in
                # the table, whichever separator the writer used.
                hits.append((m.start(), raw.split(".")[-1].split(":")[-1]))
    out: list[str] = []
    for _, name in sorted(hits):          # order they appear in the file
        if name not in out:
            out.append(name)
    return out
