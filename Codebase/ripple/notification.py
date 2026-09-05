"""Reading the impact notification.

Two ways in, and both end at the same editable form:

* upload a saved Outlook message, or paste the text
* type the tables and attributes yourself (manual mode)

Extraction never has the last word. Whatever comes out of here is shown to a
human to correct before a single file is scanned.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime

from .catalog import Catalog

# A SHOUTED_NAME. Narrow on purpose, and kept that way for the two jobs where
# being narrow is right: telling a table name apart from a person's team, and
# listing the names an email mentioned that this repository has never heard of.
IDENT = re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b")
# Anything that could be a name at all, in whatever case it happens to be
# written. Matching only SHOUTED_NAMES was a quiet disaster: BigQuery names are
# written in lower case, his own repository has ccm_Wireless_Enroll in mixed
# case, and a great many columns -- cm13, pub_guid -- are one word with no
# underscore in them at all.
#
# An email reading "we are removing cm13 from customer_demographics ...
# ACCOUNT_MASTER is unaffected" produced exactly one table to scan:
# ACCOUNT_MASTER. The only one the email says is fine, with no warning of any
# kind, and a clean confident result at the end of it.
#
# Being wide costs nothing here, because a token only becomes a table or a
# column once the catalogue built from the repository confirms that it is one.
# A spare name on the confirm screen is a tick somebody can clear; a missing
# one is invisible.
NAME_TOKEN = re.compile(r"\b[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)*\b")

DATE_PATTERNS = [
    (re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"), "%Y-%m-%d"),
    (re.compile(r"\b(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{4})\b", re.I), None),
    (re.compile(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{1,2}),?\s*(\d{4})?\b", re.I), None),
]
MONTHS = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}

# The labels no longer say "attribute" in front of the change: the same notice
# can be about a whole table, and "Attribute decommission" printed over a table
# being dropped describes a change that is not the one happening.
CHANGE_HINTS = [
    (("decommission", "removed", "removal", "dropped", "retire", "sunset", "deleted", "deletion"),
     "removal", "Decommission"),
    (("renamed", "rename", "renaming"), "rename", "Rename"),
    (("format", "value", "iso", "full country"), "value_change", "Value format change"),
    (("data type", "datatype", "length", "precision", "varchar", "widened"), "type_change", "Data type change"),
]

# ── the table itself, not a column of it ───────────────────────────────────
# How a notice says the TABLE is what changes. Checked per table the catalogue
# confirmed, against the words around its own name, so "the table X will be
# dropped" is read as X going and "column Y on table X will be dropped" is
# read as Y going. The scan follows the two completely differently.
TABLE_VERBS = (r"dropped|removed|decommissioned|retired|renamed|migrated|moved|deprecated|"
               r"deleted|replaced|sunset|rebuilt|discontinued|archived|decommission")
TABLE_VERBS_ING = (r"dropping|removing|decommissioning|retiring|renaming|migrating|moving|"
                   r"deprecating|deleting|replacing|sunsetting|rebuilding|discontinuing|archiving")
TABLE_NOUNS = (r"decommission|decommissioning|removal|retirement|deletion|migration|"
               r"deprecation|rename|renaming|replacement|sunset")
WHOLE_HINTS = ("whole table", "entire table", "the table itself", "all columns", "all attributes",
               "every column", "all of its columns", "table as a whole", "table-level", "table level")


def names_the_whole_table(text: str, table: str) -> bool:
    """Does the text say this table itself is changing?"""
    flat = re.sub(r"\s+", " ", text or "")
    low = flat.lower()
    if any(h in low for h in WHOLE_HINTS):
        return True
    t = re.escape(table)
    lead = r"(?:will be|is being|is to be|shall be|are being|is getting|gets|is|are|to be|being)"
    if re.search(rf"\b{t}\b\s*(?:table\s+)?{lead}\s+(?:{TABLE_VERBS})\b", flat, re.I):
        return True
    if re.search(rf"\b(?:{TABLE_VERBS_ING})\s+(?:the\s+|of\s+)?(?:table\s+)?{t}\b", flat, re.I):
        return True
    if re.search(rf"\b(?:{TABLE_NOUNS})\s+of\s+(?:the\s+)?(?:table\s+)?{t}\b", flat, re.I):
        return True
    return False

EMAIL_ADDR = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")


@dataclass
class Notification:
    subject: str = ""
    body: str = ""
    from_name: str = ""
    from_email: str = ""
    attachments: list[str] = field(default_factory=list)
    source_kind: str = "paste"          # msg | eml | paste | manual
    warnings: list[str] = field(default_factory=list)

    def text(self) -> str:
        return f"{self.subject}\n\n{self.body}"


# ── getting the words out of the file ──────────────────────────────────────
def read_eml(raw: bytes) -> Notification:
    from email import policy
    from email.parser import BytesParser

    msg = BytesParser(policy=policy.default).parsebytes(raw)
    n = Notification(source_kind="eml")
    n.subject = str(msg.get("subject") or "")
    sender = str(msg.get("from") or "")
    m = re.match(r"\s*\"?([^\"<]*)\"?\s*<?([^>]*)>?", sender)
    if m:
        n.from_name = m.group(1).strip()
        n.from_email = m.group(2).strip()
    body_parts: list[str] = []
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = str(part.get("Content-Disposition") or "")
            if "attachment" in disp:
                n.attachments.append(part.get_filename() or "attachment")
                continue
            if ctype == "text/plain":
                body_parts.append(part.get_content())
            elif ctype == "text/html" and not body_parts:
                body_parts.append(strip_html(part.get_content()))
    else:
        content = msg.get_content()
        body_parts.append(
            strip_html(content) if msg.get_content_type() == "text/html" else content
        )
    n.body = "\n".join(p for p in body_parts if p).strip()
    if not n.body:
        n.warnings.append("The email had no readable text body - paste the text instead.")
    return enrich(n)


def read_msg(raw: bytes) -> Notification:
    try:
        import extract_msg
    except ImportError:  # pragma: no cover
        n = Notification(source_kind="msg")
        n.warnings.append("Outlook .msg support is not installed - paste the text instead.")
        return n
    n = Notification(source_kind="msg")
    try:
        m = extract_msg.Message(io.BytesIO(raw))
        n.subject = m.subject or ""
        n.from_name = (m.sender or "").split("<")[0].strip().strip('"')
        em = re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", m.sender or "")
        n.from_email = em.group(0) if em else ""
        n.body = (m.body or "").strip()
        if not n.body and getattr(m, "htmlBody", None):
            html = m.htmlBody
            n.body = strip_html(html.decode("utf-8", "ignore") if isinstance(html, bytes) else html)
        n.attachments = [a.longFilename or a.shortFilename or "attachment"
                         for a in (m.attachments or [])]
    except Exception as exc:
        n.warnings.append(f"Could not open the Outlook file ({type(exc).__name__}) - paste the text instead.")
    if not n.body and not n.warnings:
        n.warnings.append("The Outlook file had no readable text body - paste the text instead.")
    return enrich(n)


def strip_html(html: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?</\1>", " ", html or "")
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</(p|div|tr|li|h[1-6])>", "\n", text)
    text = re.sub(r"(?i)</t[dh]>", "\t", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = (text.replace("&nbsp;", " ").replace("&amp;", "&")
                .replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"'))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


# ── headers and sign-offs that live inside the text itself ─────────────────
# A saved .msg or .eml carries real headers, so the sender and the subject are
# handed to us. Pasted text carries none: everything the reader needs is in the
# words themselves. That used to leave the source system and the contact blank
# on the one path that has no AI to cover for it, so the same facts are read
# out of the text here -- for pasted text and for uploads alike, because a
# forwarded email hides the original sender in its body too.

HEADER_KEYS = ("from", "sent", "date", "to", "cc", "bcc", "subject", "reply-to", "importance")
HEADER_LINE = re.compile(r"^\s*(" + "|".join(HEADER_KEYS) + r")\s*:\s*(.*)$", re.I)
# Anything header-shaped, used only to decide how far a block reaches. Someone
# who opens a saved .eml in Notepad and pastes the lot brings Content-Type and
# MIME-Version with them, and left in the body one of those becomes Ripple's
# description of the change.
ANY_HEADER = re.compile(r"^\s*[A-Za-z][A-Za-z0-9-]{1,40}\s*:\s")
# "-----Original Message-----", or the row of underscores Outlook draws above a
# forwarded block. Worth removing with the block, or it is left floating.
FORWARD_RULE = re.compile(r"^\s*(?:[-_=*]{5,}|-{2,}\s*original message\s*-{2,}|-{2,}\s*forwarded message\s*-{2,})\s*$", re.I)
# Gmail and most phones write the attribution as one line instead of a block.
# The name is the part after the last comma, so it may not contain one itself --
# otherwise the whole date swallows it ("Mon, 3 Aug 2026 at 09:14, Priya Raman").
WROTE_LINE = re.compile(r"^\s*On\b.{0,80}?,\s*(?P<who>[^<>,]{2,60}?)\s*(?:<(?P<email>[^>]+)>)?\s*wrote:\s*$", re.I)

# How people end these notices. The name comes after the closing, not before.
SIGNOFF_OPENERS = re.compile(
    r"^\s*(regards|kind regards|best regards|best wishes|best|thanks|thank you|many thanks|"
    r"cheers|sincerely|yours|warm regards|br)\s*[,.!]*\s*$", re.I)
# Words that describe what a team does rather than which system it owns, so
# "C360 Data Governance" yields "C360" and "Data Governance" yields nothing.
TEAM_TAIL_WORDS = {
    "data", "governance", "office", "team", "platform", "engineering", "operations",
    "ops", "group", "dept", "department", "services", "service", "support", "delivery",
    "programme", "program", "function", "domain", "coe",
}
# Bracketed subject tags that are a priority flag, not a system name.
SUBJECT_TAG_STOPWORDS = {
    "action required", "action", "notice", "fyi", "eom", "external", "urgent",
    "reminder", "info", "important", "confidential", "internal", "update", "alert",
}


def split_pasted_headers(body: str) -> tuple[dict[str, str], str]:
    """Lift an Outlook-style header block out of text and hand back both halves.

    Only a run of header lines anchored on a ``From:`` line counts, so a
    sentence that merely begins "To: " is left alone. Every block found is
    removed -- a twice-forwarded email has several -- but the values reported
    are the first block's, which is the one at the top of what was pasted.
    """
    lines = (body or "").splitlines()
    found: dict[str, str] = {}
    keep: list[str] = []
    i = 0
    while i < len(lines):
        m = WROTE_LINE.match(lines[i])
        if m:
            found.setdefault("from", (m.group("who") or "").strip()
                             + (f" <{m.group('email')}>" if m.group("email") else ""))
            i += 1
            continue
        head = HEADER_LINE.match(lines[i])
        if not (head and head.group(1).lower() == "from"):
            keep.append(lines[i])
            i += 1
            continue
        # A real block: this From: line plus the header lines packed around it.
        # A block reaches as far as header-shaped lines go, but only the ones
        # worth reading are read -- the rest are noise to be taken out of the way.
        start = i
        while start > 0 and keep and ANY_HEADER.match(keep[-1]):
            keep.pop()
            start -= 1
        end = i
        block: list[str] = []
        while end < len(lines) and ANY_HEADER.match(lines[end]):
            block.append(lines[end])
            end += 1
        for line in block:
            hm = HEADER_LINE.match(line)
            if hm:
                found.setdefault(hm.group(1).lower(), hm.group(2).strip())
        # the rule Outlook draws above the block goes with it
        while keep and (not keep[-1].strip() or FORWARD_RULE.match(keep[-1])):
            if FORWARD_RULE.match(keep[-1]):
                keep.pop()
                break
            keep.pop()
        i = end
    return found, "\n".join(keep).strip()


def parse_sender(value: str) -> tuple[str, str]:
    """A name and an address out of one ``From:`` value, in any of its shapes."""
    raw = (value or "").strip()
    if not raw:
        return "", ""
    email = ""
    m = EMAIL_ADDR.search(raw)
    if m:
        email = m.group(0)
    # strip the address itself, however it was wrapped, and any mailto: label
    name = re.sub(r"<[^>]*>|\[mailto:[^\]]*\]|\(mailto:[^)]*\)", " ", raw, flags=re.I)
    name = name.replace(email, " ").strip().strip('",;').strip()
    if name.lower().startswith("mailto:"):
        name = ""
    # "priya.raman@corp.example.com" alone -> make a readable name from it
    if not name and email:
        name = email.split("@")[0].replace(".", " ").replace("_", " ").title()
    return name, email


def _is_person(line: str) -> bool:
    words = line.split()
    if not (1 < len(words) <= 4) or len(line) > 45:
        return False
    # A tab means a table cell, not a person -- an HTML table flattens to tabs.
    if any(c in line for c in "@:_/\\|\t") or any(c.isdigit() for c in line):
        return False
    if line.rstrip().endswith((".", "?", "!")):
        return False
    return all(w[0].isupper() or (len(w) <= 3 and w.islower()) for w in words if w)


def _is_team(line: str) -> bool:
    """A team line has to say what the team does, not merely look tidy.

    Without that, the second name in a sign-off, or any short capitalised line,
    becomes somebody's "team". Requiring one of the words teams are actually
    named after means an unrecognised shape leaves the field blank instead.
    """
    words = line.split()
    if not (0 < len(words) <= 6) or len(line) > 60:
        return False
    if any(c in line for c in "@:|\t") or line.rstrip().endswith((".", "?", "!")):
        return False
    if IDENT.search(line):                 # a table name is not a team name
        return False
    return any(w.strip(",.").lower() in TEAM_TAIL_WORDS for w in words)


def signature(body: str) -> dict[str, str]:
    """The name, team and address a notice is signed off with.

    Read from the bottom up, because that is where a sign-off is: reading down
    from the top, the first tidy-looking line of the message body wins instead.
    Only the tail is considered, and only lines that plainly read as a person
    and a team are accepted. Nothing here guesses -- an unrecognised shape
    leaves the field blank for someone to fill in, rather than filling it in
    wrongly.
    """
    out = {"name": "", "team": "", "email": ""}
    tail = [ln.strip() for ln in (body or "").splitlines() if ln.strip()][-8:]
    if not tail:
        return out
    pending_team, pending_at = "", -1
    for i in range(len(tail) - 1, -1, -1):
        clean = tail[i].lstrip("-–—•* ").strip()
        if not clean or SIGNOFF_OPENERS.match(clean):
            continue
        # "Priya Raman, C360 Data Governance" -- both on one line
        if "," in clean:
            left, right = (p.strip() for p in clean.split(",", 1))
            if _is_person(left) and _is_team(right):
                out["name"], out["team"] = left, right
                break
        if _is_team(clean):
            pending_team, pending_at = clean, i
            continue
        if _is_person(clean):
            out["name"] = clean
            if pending_at == i + 1:        # the team sits directly beneath it
                out["team"] = pending_team
            break
    for line in tail:
        m = EMAIL_ADDR.search(line)
        if m:
            out["email"] = m.group(0)
            break
    return out


def source_system(team: str, subject: str) -> str:
    """Which upstream system this came from -- never who typed the email.

    It used to be the sender's first name, so a notice from Priya Raman was
    filed under "Priya". The system is named by the team that owns it, or by a
    tag on the subject line when that tag is a system code rather than a
    priority flag.
    """
    words = (team or "").split()
    while words and words[-1].strip(",.").lower() in TEAM_TAIL_WORDS:
        words.pop()
    if words:
        return " ".join(words).strip(",.-")
    m = re.match(r"\s*[\[(]([^\])]{1,20})[\])]", subject or "")
    if m:
        tag = m.group(1).strip()
        if tag.lower() not in SUBJECT_TAG_STOPWORDS and (tag.isupper() or any(c.isdigit() for c in tag)):
            return tag
    return ""


def enrich(n: Notification) -> Notification:
    """Fill in whatever the envelope did not carry, from the text itself."""
    found, body = split_pasted_headers(n.body)
    n.body = body or n.body
    if found.get("subject") and not n.subject:
        n.subject = found["subject"]
    if found.get("from"):
        name, email = parse_sender(found["from"])
        if not n.from_name:
            n.from_name = name
        if not n.from_email:
            n.from_email = email
    if not (n.from_name and n.from_email):
        sig = signature(n.body)
        n.from_name = n.from_name or sig["name"]
        n.from_email = n.from_email or sig["email"]
    return n


def read_pasted(text: str) -> Notification:
    """Text someone pasted in, read as carefully as an uploaded file is."""
    return enrich(Notification(body=(text or "").strip(), source_kind="paste"))


def read_upload(filename: str, raw: bytes) -> Notification:
    name = (filename or "").lower()
    if name.endswith(".msg"):
        return read_msg(raw)
    if name.endswith(".eml"):
        return read_eml(raw)
    try:
        return read_pasted(raw.decode("utf-8"))
    except UnicodeDecodeError:
        n = Notification(source_kind="paste")
        n.warnings.append("That file is not a .msg, .eml or plain text file.")
        return n


# ── turning the words into fields, with no AI involved ─────────────────────
def parse_date(text: str) -> str:
    for pat, fmt in DATE_PATTERNS:
        m = pat.search(text)
        if not m:
            continue
        try:
            if fmt:
                return datetime.strptime(m.group(0), fmt).date().isoformat()
            groups = [g for g in m.groups() if g]
            if groups[0].isdigit():                     # 18 September 2026
                day, mon, year = int(groups[0]), MONTHS[groups[1][:3].lower()], int(groups[2])
            else:                                       # September 18, 2026
                mon = MONTHS[groups[0][:3].lower()]
                day = int(groups[1])
                year = int(groups[2]) if len(groups) > 2 and groups[2] else date.today().year
            return date(year, mon, day).isoformat()
        except (ValueError, KeyError, IndexError):
            continue
    return ""


def classify_change(text: str) -> tuple[str, str]:
    low = (text or "").lower()
    for words, kind, label in CHANGE_HINTS:
        if any(w in low for w in words):
            return kind, label
    return "unknown", "Not specified"


def extract_by_rules(n: Notification, cat: Catalog) -> dict:
    """Pull fields out using the catalogue - the fallback when there is no AI.

    Columns are only accepted once their own table has matched. Without that
    rule, generic words like STATUS or AMOUNT produce a page of false hits.
    """
    n = enrich(n)                      # however this arrived, read its own text too
    text = n.text()
    idents = [m.group(0) for m in NAME_TOKEN.finditer(text)]
    seen_tables: list[str] = []
    for tok in idents:
        if cat.has_table(tok) and tok.upper() not in [t.upper() for t in seen_tables]:
            seen_tables.append(tok)

    upstream = []
    for t in seen_tables:
        attrs = [tok for tok in idents if cat.has_column(t, tok)]
        deduped: list[str] = []
        for a in attrs:
            if a.upper() not in [x.upper() for x in deduped]:
                deduped.append(a)
        # A named attribute wins. Only a table with none, and words saying
        # the table itself is going, is read as a whole-table change -- and
        # either way the screen says which, because the two scans are
        # completely different questions.
        whole = not deduped and names_the_whole_table(text, t)
        upstream.append({"table": t, "attrs": deduped, "whole": whole})

    kind, label = classify_change(text)
    warnings = list(n.warnings)
    for u in upstream:
        if u["whole"]:
            warnings.append(
                f"{u['table']} reads as a whole-table change: every column, and every "
                f"statement that reads the table. Untick 'Whole table' on the next screen if "
                f"only some attributes change.")
        elif not u["attrs"]:
            warnings.append(
                f"No attribute of {u['table']} was recognised. If the table itself is "
                f"changing, tick 'Whole table' on the next screen. Otherwise add the "
                f"attribute, or nothing can be scanned for it.")
    # Only SHOUTED_NAMES are worth complaining about. Every ordinary word in the
    # email is now checked against the catalogue above, and listing all of them
    # back as "not in your repository" would bury the one line that matters.
    shouted = [m.group(0) for m in IDENT.finditer(text)]
    unknown = [tok for tok in dict.fromkeys(shouted)
               if not cat.has_table(tok) and not any(cat.has_column(t, tok) for t in seen_tables)]
    if unknown:
        warnings.append(
            "These names were mentioned but are not in the connected repository: "
            + ", ".join(unknown[:8])
        )
    if not upstream:
        warnings.append(
            "No table from the connected repository was recognised. Add the table and "
            "attributes by hand before scanning."
        )

    sig = signature(n.body)
    return {
        "source": source_system(sig["team"], n.subject) or "Unknown",
        "changeType": label,
        "changeKind": kind,
        "changeDesc": first_sentence(n.body),
        "subject": n.subject,
        "effectiveDate": parse_date(text),
        "pocName": n.from_name or sig["name"],
        "pocEmail": n.from_email or sig["email"],
        "pocTeam": sig["team"],
        "upstream": upstream,
        "warnings": warnings,
        "extractedBy": "rules",
    }


# Header names that are plumbing rather than words a person wrote. Kept narrow
# on purpose: "Impact: this breaks the nightly load" is a real first sentence,
# and a rule that skipped every line with a colon in it would throw that away.
PLUMBING_HEADERS = re.compile(
    r"^\s*(content-type|content-transfer-encoding|content-disposition|content-language|"
    r"mime-version|message-id|received|return-path|delivered-to|authentication-results|"
    r"dkim-signature|thread-topic|thread-index|accept-language|x-[a-z0-9-]+)\s*:", re.I)


def first_sentence(body: str, limit: int = 240) -> str:
    clean = re.sub(r"\s+", " ", (body or "")).strip()
    for line in (body or "").splitlines():
        line = line.strip()
        if PLUMBING_HEADERS.match(line):
            continue
        if len(line) > 40 and not line.lower().startswith(("hi ", "hello", "team", "dear")):
            clean = line
            break
    return clean[:limit]
