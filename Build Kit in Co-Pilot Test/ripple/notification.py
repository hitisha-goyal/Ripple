from __future__ import annotations

"""Reading the notification email that starts an analysis.

Everything in here is a SUGGESTION for the confirm screen, never an answer.
Nothing is scanned until a person has ticked the fields, so the rules below are
deliberately wide: a spare name on the confirm screen is a tick somebody can
clear, while a missing one is invisible.
"""

import email
import email.header
import email.parser
import html as html_module
import io
import re
from dataclasses import dataclass, field
from datetime import date


# --------------------------------------------------------------------------
# The shape that crosses a file boundary
# --------------------------------------------------------------------------


@dataclass
class Notification:
    """One email, however it arrived.

    warnings is carried on the notification itself because the reader is the
    only thing that knows the Outlook file would not open. If that sentence
    does not travel with the email, the screen shows a confident blank form.
    """

    subject: str = ""
    body: str = ""
    from_name: str = ""
    from_email: str = ""
    attachments: list[str] = field(default_factory=list)
    source_kind: str = ""
    warnings: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------
# Patterns and word lists
# --------------------------------------------------------------------------

# The address pattern, used by every path in: the .msg sender line, the Outlook
# To line somebody pasted, the sign-off at the bottom.
ADDRESS_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

# A name a person could have typed for a table or a column. Dotted so that
# project.dataset.table survives as one candidate rather than three.
NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*")

# Capitals with an underscore. This narrow rule has ONE job: listing the names
# an email SHOUTED that the repository has never heard of. Used for matching it
# would miss cm13 and customer_demographics, which is the disaster the kit
# describes.
SHOUTED_RE = re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b")

HEADER_LINE_RE = re.compile(r"^([A-Za-z][A-Za-z0-9\-]*)\s*:\s?(.*)$")

# Only these keys let a line join a header block. A wider rule swallows
# "Impact: this breaks the nightly load" when it happens to sit next to a
# forwarded block, and that line is the one sentence worth reading.
HEADER_NAMES = {
    "from",
    "sent",
    "to",
    "cc",
    "bcc",
    "subject",
    "date",
    "reply-to",
    "importance",
    "sensitivity",
    "priority",
    "content-type",
    "content-transfer-encoding",
    "content-disposition",
    "content-language",
    "content-id",
    "mime-version",
    "message-id",
    "in-reply-to",
    "references",
    "received",
    "return-path",
    "delivered-to",
    "authentication-results",
    "dkim-signature",
    "thread-topic",
    "thread-index",
    "accept-language",
    "user-agent",
    "organisation",
    "organization",
    "precedence",
    "auto-submitted",
    "list-id",
    "list-unsubscribe",
}

# "On Mon, 3 Aug 2026 at 09:14, Priya Raman <priya@corp.example.com> wrote:"
ATTRIBUTION_RE = re.compile(r"^\s*On\b.*,.*\bwrote:\s*$", re.IGNORECASE)

# Plumbing that first_sentence must never read out as the description of the
# change. Kept deliberately narrow: a rule that skipped every line with a colon
# would throw away "Impact: this breaks the nightly load".
PLUMBING_PREFIXES = {
    "content-type",
    "content-transfer-encoding",
    "content-disposition",
    "mime-version",
    "message-id",
    "received",
    "return-path",
    "delivered-to",
    "authentication-results",
    "dkim-signature",
    "thread-topic",
    "thread-index",
    "accept-language",
}

GREETING_RE = re.compile(
    r"^\s*(hi|hello|hey|dear|greetings|good\s+morning|good\s+afternoon|"
    r"good\s+evening|team|all)\b",
    re.IGNORECASE,
)

# The closing comes BEFORE the name, so it has to be stepped over rather than
# read as one.
CLOSINGS = {
    "regards",
    "kind regards",
    "best regards",
    "warm regards",
    "warmest regards",
    "many thanks",
    "thanks",
    "thanks again",
    "thank you",
    "best wishes",
    "best",
    "cheers",
    "sincerely",
    "yours sincerely",
    "yours faithfully",
    "yours truly",
    "all the best",
    "regards and thanks",
}

# A team has to SAY what the team does. Without this the second name in a
# sign-off becomes somebody's team.
TEAM_WORDS = {
    "data",
    "governance",
    "office",
    "team",
    "platform",
    "engineering",
    "operations",
    "ops",
    "group",
    "dept",
    "department",
    "services",
    "service",
    "support",
    "delivery",
    "programme",
    "program",
    "function",
    "domain",
    "coe",
}

# A bracketed tag off the front of a subject line is a source system only when
# it is a code. These are flags about how to feel about the email, not about
# where it came from.
PRIORITY_TAGS = {
    "action required",
    "notice",
    "fyi",
    "urgent",
    "reminder",
    "important",
    "confidential",
    "internal",
    "update",
    "alert",
}

CHARACTERS_A_NAME_NEVER_HOLDS = set("@:_/\\|\t")

MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "sept": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

# Longest first, so "september" is not eaten as "sep".
_MONTH_ALT = "|".join(sorted(MONTHS, key=len, reverse=True))

DATE_ISO_RE = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")
DATE_DAY_MONTH_RE = re.compile(
    r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(" + _MONTH_ALT + r")\b\.?,?"
    r"(?:\s+(\d{4}))?",
    re.IGNORECASE,
)
DATE_MONTH_DAY_RE = re.compile(
    r"\b(" + _MONTH_ALT + r")\b\.?\s+(\d{1,2})(?:st|nd|rd|th)?\b,?"
    r"(?:\s+(\d{4}))?",
    re.IGNORECASE,
)
# Day first. British spelling everywhere else, British date order here.
DATE_SLASHED_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")

# Change kind. Order in this list is only the tie-break: the word that appears
# EARLIEST in the email wins, because that is the sentence the email is about.
CHANGE_KIND_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "removal",
        re.compile(
            r"\b(decommission\w*|retir\w+|remov\w+|drop|dropping|dropped|"
            r"delet\w+|sunset\w*|withdraw\w+|no longer (?:be )?populat\w+)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "rename",
        re.compile(
            r"\b(renam\w+|new (?:column |field |attribute )?name|"
            r"will be called|being called)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "type_change",
        re.compile(
            r"\b(format change|change of format|changing the format|"
            r"data ?type\w*|type change|retyp\w+|changing the type|"
            r"reformat\w*)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "value_change",
        re.compile(
            r"\b(value change|values? will change|changing the values?|"
            r"new values?|recod\w+|code change|new code set|"
            r"re-?map\w*)\b",
            re.IGNORECASE,
        ),
    ),
]

CHANGE_TYPE_WORDS = {
    "unknown": "Unknown",
    "removal": "Column removal",
    "value_change": "Value change",
    "type_change": "Format or type change",
    "rename": "Column rename",
}


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------


def _reason(exc: Exception) -> str:
    """Plain words for the screen. The class name alone means nothing to the
    person reading it, but it is better than an empty bracket."""
    text = str(exc).strip()
    return text if text else type(exc).__name__


def _decode_bytes(raw: bytes, declared: str = "") -> str:
    """Decode, falling back rather than raising. A mail that will not decode is
    still worth showing badly; a traceback shows nothing at all."""
    for charset in (declared, "utf-8", "cp1252"):
        if not charset:
            continue
        try:
            return raw.decode(charset)
        except (LookupError, UnicodeDecodeError):
            continue
    return raw.decode("utf-8", errors="replace")


def _decode_header_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return _decode_bytes(value)
    try:
        parts = email.header.decode_header(str(value))
    except Exception:
        return str(value)
    out: list[str] = []
    for chunk, charset in parts:
        if isinstance(chunk, bytes):
            out.append(_decode_bytes(chunk, charset or ""))
        else:
            out.append(chunk)
    return "".join(out).strip()


def strip_html(raw: str) -> str:
    """Flatten an HTML body to text.

    Table cells become tabs on purpose. That is why the signature reader
    refuses any candidate name holding a tab: a tab means a table cell, not a
    person.
    """
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", raw)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</(p|div|tr|li|h[1-6]|table)\s*>", "\n", text)
    text = re.sub(r"(?i)</(td|th)\s*>", "\t", text)
    text = re.sub(r"(?s)<[^>]+>", "", text)
    text = html_module.unescape(text)
    lines = [line.rstrip() for line in text.splitlines()]
    return _collapse_blank_lines(lines)


def _collapse_blank_lines(lines: list[str]) -> str:
    out: list[str] = []
    blank = False
    for line in lines:
        if line.strip():
            out.append(line)
            blank = False
        else:
            if not blank and out:
                out.append("")
            blank = True
    return "\n".join(out).strip("\n")


def extract_emails(text: str) -> list[str]:
    """Every address in a blob of text, once each, lower-cased, in order.

    People paste a whole Outlook To line rather than typing addresses one at a
    time.
    """
    seen: list[str] = []
    for match in ADDRESS_RE.finditer(text or ""):
        address = match.group(0).lower().rstrip(".,;")
        if address not in seen:
            seen.append(address)
    return seen


def parse_sender(value: str) -> tuple[str, str]:
    """One From: value in any of its four shapes."""
    raw = (value or "").strip()
    if not raw:
        return "", ""

    address = ""
    name = ""

    angled = re.search(r"<\s*([^<>]+?)\s*>", raw)
    mailto = re.search(r"\[\s*mailto:\s*([^\]]+?)\s*\]", raw, re.IGNORECASE)
    if angled:
        found = ADDRESS_RE.search(angled.group(1))
        address = found.group(0).lower() if found else angled.group(1).strip().lower()
        name = raw[: angled.start()]
    elif mailto:
        found = ADDRESS_RE.search(mailto.group(1))
        address = found.group(0).lower() if found else mailto.group(1).strip().lower()
        name = raw[: mailto.start()]
    else:
        found = ADDRESS_RE.search(raw)
        if found:
            address = found.group(0).lower()
            name = raw[: found.start()]

    name = name.strip().strip(",;").strip()
    if name.startswith('"') and name.endswith('"') and len(name) >= 2:
        name = name[1:-1]
    name = name.strip().strip("'").strip()

    if not name and address:
        name = _name_from_address(address)

    return name, address


def _name_from_address(address: str) -> str:
    """priya.raman@corp.example.com -> Priya Raman.

    A bare address is the fourth shape the kit lists, and a person on the
    confirm screen would rather correct "Priya Raman" than type it.
    """
    local = address.split("@", 1)[0]
    words = [w for w in re.split(r"[._\-+]+", local) if w and not w.isdigit()]
    if not words:
        return ""
    return " ".join(word[:1].upper() + word[1:] for word in words)


# --------------------------------------------------------------------------
# Header blocks pasted into the body
# --------------------------------------------------------------------------


def _header_key_and_value(line: str) -> tuple[str, str] | None:
    match = HEADER_LINE_RE.match(line)
    if not match:
        return None
    key = match.group(1).lower()
    if key in HEADER_NAMES or key.startswith("x-"):
        return key, match.group(2).strip()
    return None


def _is_continuation(line: str) -> bool:
    return bool(line) and line[0] in " \t" and bool(line.strip())


def _is_separator(line: str) -> bool:
    """The row Outlook draws above a forwarded block. Left behind it floats in
    the middle of the message."""
    stripped = line.strip()
    if len(stripped) < 3:
        return False
    if set(stripped) <= set("-_= "):
        return True
    return bool(re.match(r"^[-_]{3,}.*[-_]{3,}$", stripped))


def split_pasted_headers(body: str) -> tuple[dict[str, str], str]:
    """Lift Outlook header blocks out of pasted text.

    A block only counts when it is anchored on a From: line, so a sentence
    beginning "To: be clear" is left alone. Every block found is taken out - a
    twice-forwarded email has several - but the values reported are the FIRST
    one's, because that is the message actually in front of the reader.

    This must run BEFORE the effective date is looked for. The Sent: date and
    the date in the message are written the same way, so whichever is read
    first wins.
    """
    lines = (body or "").splitlines()
    remove = [False] * len(lines)
    blocks: list[dict[str, str]] = []

    index = 0
    while index < len(lines):
        if remove[index]:
            index += 1
            continue

        if ATTRIBUTION_RE.match(lines[index]):
            blocks.append(_attribution_headers(lines[index]))
            remove[index] = True
            index += 1
            continue

        parsed = _header_key_and_value(lines[index])
        if parsed is None or parsed[0] != "from":
            index += 1
            continue

        start = index
        while start - 1 >= 0 and (
            _header_key_and_value(lines[start - 1]) is not None
            or _is_continuation(lines[start - 1])
        ):
            start -= 1

        end = index
        while end + 1 < len(lines) and (
            _header_key_and_value(lines[end + 1]) is not None
            or _is_continuation(lines[end + 1])
        ):
            end += 1

        found: dict[str, str] = {}
        current_key = ""
        for line_number in range(start, end + 1):
            remove[line_number] = True
            pair = _header_key_and_value(lines[line_number])
            if pair is not None:
                current_key = pair[0]
                if current_key not in found:
                    found[current_key] = pair[1]
            elif current_key and _is_continuation(lines[line_number]):
                found[current_key] = (found[current_key] + " " + lines[line_number].strip()).strip()
        blocks.append(found)

        above = start - 1
        while above >= 0 and not lines[above].strip():
            above -= 1
        if above >= 0 and _is_separator(lines[above]):
            remove[above] = True

        index = end + 1

    kept = [line for number, line in enumerate(lines) if not remove[number]]
    cleaned = _collapse_blank_lines([line.rstrip() for line in kept])
    headers = blocks[0] if blocks else {}
    return headers, cleaned


def _attribution_headers(line: str) -> dict[str, str]:
    """The one-line attribution phones and Gmail write instead of a block.

    The name is the part after the LAST comma, so a name holding a comma would
    be lost - but reading from the first comma instead swallows the whole date.
    """
    text = line.strip()
    text = re.sub(r"\bwrote:\s*$", "", text, flags=re.IGNORECASE).strip()
    cut = text.rfind(",")
    if cut == -1:
        return {}
    sender_part = text[cut + 1 :].strip()
    sent_part = text[:cut].strip()
    sent_part = re.sub(r"^On\b\s*", "", sent_part, flags=re.IGNORECASE).strip()
    found: dict[str, str] = {}
    if sender_part:
        found["from"] = sender_part
    if sent_part:
        found["sent"] = sent_part
    return found


# --------------------------------------------------------------------------
# Reading facts out of the words
# --------------------------------------------------------------------------


def _looks_like_a_person(line: str) -> bool:
    """Two to four words, each capitalised, under 45 characters, no digits and
    none of @ : _ / \\ | or a tab.

    Guess nothing. An unrecognised shape leaves the field blank for a person to
    fill in, which is recoverable; a wrong one is not.
    """
    text = line.strip()
    if not text or len(text) >= 45:
        return False
    if any(character in CHARACTERS_A_NAME_NEVER_HOLDS for character in text):
        return False
    if any(character.isdigit() for character in text):
        return False
    if text.lower().strip(".,;") in CLOSINGS:
        return False
    words = text.replace(".", " ").split()
    if not 2 <= len(words) <= 4:
        return False
    for word in words:
        cleaned = word.strip(",;'")
        if not cleaned:
            return False
        if not cleaned[0].isupper():
            return False
    return True


def _looks_like_a_team(line: str) -> bool:
    text = line.strip()
    if not text or len(text) >= 60:
        return False
    if "@" in text or "\t" in text:
        return False
    words = [word.strip(",.;").lower() for word in text.split()]
    return any(word in TEAM_WORDS for word in words)


def signature(body: str) -> dict[str, str]:
    """The name, team and address a notice is signed off with.

    Read from the BOTTOM UP. Reading down from the top, the first tidy-looking
    line of the message wins instead.
    """
    result = {"name": "", "team": "", "email": ""}
    lines = [line.rstrip() for line in (body or "").splitlines() if line.strip()]
    if not lines:
        return result
    tail = lines[-8:]

    for address in extract_emails("\n".join(tail)):
        result["email"] = address
        break

    for position in range(len(tail) - 1, -1, -1):
        line = tail[position].strip()
        if line.lower().strip(".,;") in CLOSINGS:
            continue

        if "," in line:
            left, right = line.split(",", 1)
            left = left.strip()
            right = right.strip()
            if _looks_like_a_person(left) and _looks_like_a_team(right):
                result["name"] = left
                result["team"] = right
                return result
            if not right and _looks_like_a_person(left):
                result["name"] = left
                if position + 1 < len(tail) and _looks_like_a_team(tail[position + 1]):
                    result["team"] = tail[position + 1].strip()
                return result

        if _looks_like_a_person(line):
            result["name"] = line
            if position + 1 < len(tail) and _looks_like_a_team(tail[position + 1]):
                result["team"] = tail[position + 1].strip()
            return result

    return result


def source_system(team: str, subject: str) -> str:
    """Which upstream system this came from, never who typed the email."""
    words = [word for word in (team or "").replace(",", " ").split() if word]
    while words and words[-1].strip(".,;").lower() in TEAM_WORDS:
        words.pop()
    if words:
        return " ".join(words).strip(".,;")

    match = re.match(r"^\s*[\[\(]([^\]\)]+)[\]\)]", subject or "")
    if match:
        tag = match.group(1).strip()
        lowered = tag.lower()
        if lowered not in PRIORITY_TAGS:
            letters = [character for character in tag if character.isalpha()]
            is_code = bool(letters) and all(character.isupper() for character in letters)
            has_digit = any(character.isdigit() for character in tag)
            if is_code or has_digit:
                return tag

    return "Unknown"


def first_sentence(body: str) -> str:
    """The first line over forty characters that is not a greeting."""
    for raw_line in (body or "").splitlines():
        line = raw_line.strip()
        if len(line) <= 40:
            continue
        if GREETING_RE.match(line):
            continue
        head = HEADER_LINE_RE.match(line)
        if head is not None:
            key = head.group(1).lower()
            # Narrow on purpose: "Impact: this breaks the nightly load" is a
            # real first sentence and must survive.
            if key in PLUMBING_PREFIXES or key.startswith("x-"):
                continue
        return line[:240].strip()
    return ""


def _iso_or_blank(year: int, month: int, day: int) -> str:
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return ""


def effective_date(text: str) -> str:
    """A date in any common written form, as ISO.

    The earliest date in the text wins. The header block has already been taken
    out by the time this runs, so the Sent: date cannot win over the date in
    the message.
    """
    body = text or ""
    found: list[tuple[int, str]] = []

    for match in DATE_ISO_RE.finditer(body):
        iso = _iso_or_blank(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        if iso:
            found.append((match.start(), iso))

    for match in DATE_DAY_MONTH_RE.finditer(body):
        month = MONTHS.get(match.group(2).lower())
        if month is None:
            continue
        # A year nobody wrote down is this year. The person confirms the field
        # before anything is scanned, and a blank date helps nobody.
        year = int(match.group(3)) if match.group(3) else date.today().year
        iso = _iso_or_blank(year, month, int(match.group(1)))
        if iso:
            found.append((match.start(), iso))

    for match in DATE_MONTH_DAY_RE.finditer(body):
        month = MONTHS.get(match.group(1).lower())
        if month is None:
            continue
        year = int(match.group(3)) if match.group(3) else date.today().year
        iso = _iso_or_blank(year, month, int(match.group(2)))
        if iso:
            found.append((match.start(), iso))

    for match in DATE_SLASHED_RE.finditer(body):
        iso = _iso_or_blank(int(match.group(3)), int(match.group(2)), int(match.group(1)))
        if iso:
            found.append((match.start(), iso))

    if not found:
        return ""
    found.sort(key=lambda pair: pair[0])
    return found[0][1]


def change_kind(text: str) -> str:
    """Which kind of change the words describe."""
    body = text or ""
    hits: list[tuple[int, int, str]] = []
    for order, (kind, pattern) in enumerate(CHANGE_KIND_PATTERNS):
        match = pattern.search(body)
        if match:
            hits.append((match.start(), order, kind))
    if not hits:
        return "unknown"
    hits.sort()
    return hits[0][2]


# --------------------------------------------------------------------------
# The catalogue built in Phase 5
# --------------------------------------------------------------------------


def _column_names(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [str(key) for key in value]
    inner = getattr(value, "columns", None)
    if inner is not None and not isinstance(value, (list, tuple, set)):
        return _column_names(inner)
    if isinstance(value, (list, tuple, set)):
        out: list[str] = []
        for item in value:
            if isinstance(item, str):
                out.append(item)
            else:
                name = getattr(item, "name", None)
                if isinstance(name, str):
                    out.append(name)
        return out
    name = getattr(value, "name", None)
    return [name] if isinstance(name, str) else []


def _catalogue_tables(catalog: object) -> dict[str, list[str]]:
    """Flatten whatever the catalogue is into {table name: [column names]}.

    Phase 5 owns that object and this window cannot see it, so this reads the
    two shapes it can be sure of - a mapping, or something holding one on
    .tables - and treats anything else as an empty catalogue rather than
    guessing.
    """
    source: object = catalog
    if source is None:
        return {}
    if not hasattr(source, "items"):
        inner = getattr(source, "tables", None)
        if inner is None:
            return {}
        source = inner
    if not hasattr(source, "items"):
        return {}

    tables: dict[str, list[str]] = {}
    try:
        pairs = list(source.items())  # type: ignore[union-attr]
    except Exception:
        return {}
    for key, value in pairs:
        tables[str(key)] = _column_names(value)
    return tables


def _match_catalogue(text: str, tables: dict[str, list[str]]) -> list[dict[str, object]]:
    """Names in the text that the catalogue confirms, in the order the email
    writes them, so the table the email is actually about comes first.

    Matching is case-insensitive and does not require an underscore. Matching
    only SHOUTED_NAMES looks reasonable and is a quiet disaster: BigQuery names
    are lower case, real tables are mixed case, and cm13 is one word.
    """
    by_table_key: dict[str, str] = {}
    for canonical in tables:
        for key in (canonical.lower(), canonical.split(".")[-1].lower()):
            by_table_key.setdefault(key, canonical)

    columns_by_table: dict[str, dict[str, str]] = {}
    for canonical, columns in tables.items():
        lookup: dict[str, str] = {}
        for column in columns:
            lookup.setdefault(column.lower(), column)
        columns_by_table[canonical] = lookup

    # Addresses first, or priya.raman@corp.example.com donates two candidates
    # that were never table names.
    without_addresses = ADDRESS_RE.sub(" ", text or "")
    candidates = [match.group(0) for match in NAME_RE.finditer(without_addresses)]

    order: list[str] = []
    for candidate in candidates:
        canonical = by_table_key.get(candidate.lower())
        if canonical is None:
            canonical = by_table_key.get(candidate.split(".")[-1].lower())
        if canonical is not None and canonical not in order:
            order.append(canonical)

    attrs: dict[str, list[str]] = {table: [] for table in order}
    for candidate in candidates:
        for table in order:
            column = columns_by_table.get(table, {}).get(candidate.lower())
            if column is not None and column not in attrs[table]:
                attrs[table].append(column)

    return [{"table": table, "attrs": attrs[table]} for table in order]


def _unknown_shouted_names(text: str, tables: dict[str, list[str]]) -> list[str]:
    known: set[str] = set()
    for canonical, columns in tables.items():
        known.add(canonical.lower())
        known.add(canonical.split(".")[-1].lower())
        for column in columns:
            known.add(column.lower())

    unknown: list[str] = []
    for match in SHOUTED_RE.finditer(text or ""):
        name = match.group(0)
        if name.lower() in known:
            continue
        if name not in unknown:
            unknown.append(name)
    return unknown


# --------------------------------------------------------------------------
# The three ways in
# --------------------------------------------------------------------------


def _read_the_words(note: Notification) -> None:
    """Read the same facts out of the words on every path in.

    A saved .eml or .msg hands over real headers. A plain .txt does not, and
    neither does a forwarded email, which hides the original sender inside its
    own body. Nothing here ever overwrites what the envelope already carried.
    """
    headers, body = split_pasted_headers(note.body)
    note.body = body

    if not note.subject:
        note.subject = headers.get("subject", "")

    if not note.from_name or not note.from_email:
        name, address = parse_sender(headers.get("from", ""))
        if not note.from_name and name:
            note.from_name = name
        if not note.from_email and address:
            note.from_email = address

    if not note.from_name or not note.from_email:
        signed = signature(note.body)
        if not note.from_name and signed["name"]:
            note.from_name = signed["name"]
        if not note.from_email and signed["email"]:
            note.from_email = signed["email"]


def read_pasted(text: str) -> Notification:
    note = Notification(source_kind="pasted", body=text or "")
    _read_the_words(note)
    return note


def read_eml(raw_bytes: bytes) -> Notification:
    note = Notification(source_kind="eml")
    try:
        message = email.parser.BytesParser().parsebytes(raw_bytes)
    except Exception as exc:
        note.warnings.append(
            "Could not open the email file: "
            + _reason(exc)
            + ". Paste the text of the email instead."
        )
        return note

    plain: list[str] = []
    marked_up: list[str] = []
    try:
        for part in message.walk():
            if part.get_content_maintype() == "multipart":
                continue
            disposition = str(part.get("Content-Disposition") or "")
            filename = part.get_filename()
            if filename or "attachment" in disposition.lower():
                note.attachments.append(_decode_header_value(filename) or "attachment")
                continue
            payload = part.get_payload(decode=True)
            if payload is None:
                continue
            text = _decode_bytes(payload, part.get_content_charset() or "")
            content_type = part.get_content_type()
            if content_type == "text/plain":
                plain.append(text)
            elif content_type == "text/html":
                marked_up.append(text)
    except Exception as exc:
        note.warnings.append(
            "Part of the email could not be read: "
            + _reason(exc)
            + ". Paste the text of the email instead."
        )

    if plain:
        note.body = _collapse_blank_lines(
            [line.rstrip() for line in "\n".join(plain).splitlines()]
        )
    elif marked_up:
        note.body = strip_html("\n".join(marked_up))

    note.subject = _decode_header_value(message.get("Subject"))
    note.from_name, note.from_email = parse_sender(_decode_header_value(message.get("From")))

    _read_the_words(note)

    if not note.body.strip():
        note.warnings.append(
            "The email had no readable text body. Paste the text of the email instead."
        )
    return note


def _import_extract_msg() -> object:
    """Imported behind a function so the failure is a warning on screen rather
    than an import error nobody sees."""
    import extract_msg

    return extract_msg


def _sender_from_msg_line(line: str) -> tuple[str, str]:
    """The .msg sender line: the name is the part before the "<", and the
    address comes out of the same line with the address pattern."""
    text = (line or "").strip()
    if not text:
        return "", ""
    found = ADDRESS_RE.search(text)
    address = found.group(0).lower() if found else ""
    if "<" in text:
        name = text.split("<", 1)[0].strip().strip('"').strip("'").strip()
    else:
        name = "" if found and found.group(0) == text else text.strip('"').strip()
        if name and "@" in name:
            name = ""
    if not name and address:
        name = _name_from_address(address)
    return name, address


def read_msg(raw_bytes: bytes) -> Notification:
    note = Notification(source_kind="msg")

    try:
        extract_msg = _import_extract_msg()
    except Exception as exc:
        note.warnings.append(
            "Could not open the Outlook file: the extract_msg reader is not available ("
            + _reason(exc)
            + "). Save the email as .eml, or paste the text of the email instead."
        )
        return note

    try:
        message = extract_msg.Message(io.BytesIO(raw_bytes))  # type: ignore[attr-defined]
    except Exception as exc:
        note.warnings.append(
            "Could not open the Outlook file: "
            + _reason(exc)
            + ". Save the email as .eml, or paste the text of the email instead."
        )
        return note

    try:
        subject = getattr(message, "subject", "") or ""
        sender_line = getattr(message, "sender", "") or ""
        body = getattr(message, "body", "") or ""
        if isinstance(body, bytes):
            body = _decode_bytes(body)
        if not str(body).strip():
            marked_up = getattr(message, "htmlBody", "") or ""
            if isinstance(marked_up, bytes):
                marked_up = _decode_bytes(marked_up)
            if str(marked_up).strip():
                body = strip_html(str(marked_up))
        for attachment in getattr(message, "attachments", []) or []:
            name = (
                getattr(attachment, "longFilename", "")
                or getattr(attachment, "shortFilename", "")
                or "attachment"
            )
            note.attachments.append(str(name))
    except Exception as exc:
        note.warnings.append(
            "Could not read the Outlook file: "
            + _reason(exc)
            + ". Save the email as .eml, or paste the text of the email instead."
        )
        return note

    note.subject = str(subject).strip()
    note.body = _collapse_blank_lines([line.rstrip() for line in str(body).splitlines()])
    note.from_name, note.from_email = _sender_from_msg_line(str(sender_line))

    _read_the_words(note)

    if not note.body.strip():
        note.warnings.append(
            "The Outlook file opened but held no readable text. "
            "Paste the text of the email instead."
        )
    return note


def read_upload(filename: str, raw_bytes: bytes) -> Notification:
    lowered = (filename or "").lower()
    if lowered.endswith(".msg"):
        return read_msg(raw_bytes)
    if lowered.endswith(".eml"):
        return read_eml(raw_bytes)
    note = read_pasted(_decode_bytes(raw_bytes))
    note.source_kind = "txt"
    return note


# --------------------------------------------------------------------------
# What the confirm screen is offered
# --------------------------------------------------------------------------


def extract_by_rules(notification: Notification, catalog: object) -> dict[str, object]:
    """Match the email against the repository catalogue, so what comes out is
    names that actually exist in the code rather than a guess.

    Nothing is scanned until the person has confirmed these fields, so every
    value here is a suggestion, never an answer.
    """
    # The list starts as a copy of the reader's own warnings. That is the only
    # way "Could not open the Outlook file" reaches the screen at all.
    warnings: list[str] = list(notification.warnings)

    headers, body = split_pasted_headers(notification.body)

    subject = notification.subject or headers.get("subject", "")

    header_name, header_email = parse_sender(headers.get("from", ""))
    signed = signature(body)

    poc_name = notification.from_name or header_name or signed["name"]
    poc_email = notification.from_email or header_email or signed["email"]
    poc_team = signed["team"]

    tables = _catalogue_tables(catalog)
    haystack = (subject + "\n" + body) if subject else body

    upstream = _match_catalogue(haystack, tables)

    unknown = _unknown_shouted_names(haystack, tables)
    if unknown:
        # The first eight only. Every ordinary word in the message is already
        # checked against the catalogue, and listing all of those back would
        # bury the one line that matters.
        warnings.append(
            "These names were mentioned but are not in the connected repository: "
            + ", ".join(unknown[:8])
        )

    if not upstream:
        warnings.append(
            "No table from the connected repository was recognised. "
            "Add the table and attributes by hand before scanning."
        )

    kind = change_kind(haystack)

    return {
        "source": source_system(poc_team, subject),
        "changeType": CHANGE_TYPE_WORDS[kind],
        "changeKind": kind,
        "changeDesc": first_sentence(body),
        "subject": subject,
        "effectiveDate": effective_date(body),
        "pocName": poc_name,
        "pocEmail": poc_email,
        "pocTeam": poc_team,
        "upstream": upstream,
        "warnings": warnings,
        "extractedBy": "rules",
    }
