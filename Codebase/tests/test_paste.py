"""Reading a notification that was pasted in rather than uploaded.

Pasted text has no envelope: no From header, no Subject header, nothing but the
words. It used to leave the source system and the contact blank, which barely
showed online because the AI filled them in -- and matters a great deal offline,
where the rules are the only reader there is.

The rule these tests hold to: pasting the text of an email must produce the same
fields as uploading that same email, apart from facts that genuinely are not in
the text.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ripple.catalog import build_catalog                       # noqa: E402
from ripple.config import settings                             # noqa: E402
from ripple.notification import (                              # noqa: E402
    Notification, extract_by_rules, parse_sender, read_pasted, read_upload,
    signature, source_system, split_pasted_headers,
)
from ripple.scanner.repo import RepoIndex                      # noqa: E402
from ripple.scanner.sqlread import parse_repo                  # noqa: E402

SAMPLES = Path(__file__).resolve().parent.parent / "samples"

OUTLOOK_PASTE = """From: Priya Raman <priya.raman@corp.example.com>
Sent: Monday, 3 August 2026 09:14
To: CMDL Data Engineering <cmdl-data-eng@corp.example.com>
Subject: [Action Required] MARKET_CODE value format change - effective 2026-09-18

Team,

Effective 2026-09-18, MARKET_CODE and MARKET_NAME on CUSTOMER_DEMOGRAPHICS will
change from ISO abbreviations to full country names.

- Priya Raman
  C360 Data Governance
"""


@pytest.fixture(scope="module")
def cat():
    return build_catalog(parse_repo(RepoIndex.build(settings.repo_path, settings), settings))


# ── the header block someone pastes in with the message ────────────────────
def test_pasted_outlook_headers_are_read():
    n = read_pasted(OUTLOOK_PASTE)
    assert n.from_name == "Priya Raman"
    assert n.from_email == "priya.raman@corp.example.com"
    assert "MARKET_CODE value format change" in n.subject


def test_header_block_is_taken_out_of_the_body():
    """Left in, the From: line becomes the description of the change."""
    n = read_pasted(OUTLOOK_PASTE)
    assert "priya.raman@corp.example.com" not in n.body
    assert not n.body.lower().startswith("from:")
    assert "Effective 2026-09-18" in n.body


def test_the_sent_date_is_not_mistaken_for_the_effective_date(cat):
    """Both dates are ISO, so whichever is read first wins. It must be the one
    in the message, not the moment the message was sent."""
    out = extract_by_rules(read_pasted(
        "From: A Sender <a@corp.example.com>\n"
        "Sent: 2026-08-03 09:14\n"
        "Subject: change notice\n\n"
        "MARKET_CODE on CUSTOMER_DEMOGRAPHICS changes effective 2026-09-18.\n"), cat)
    assert out["effectiveDate"] == "2026-09-18"


def test_a_sentence_beginning_to_is_not_treated_as_a_header():
    body = "To: be clear, MARKET_CODE is unchanged.\nNothing else is moving."
    found, kept = split_pasted_headers(body)
    assert found == {} and kept == body


def test_gmail_style_attribution_is_read():
    n = read_pasted("On Mon, 3 Aug 2026 at 09:14, Priya Raman <priya.raman@corp.example.com> wrote:\n"
                    "MARKET_CODE is changing.")
    assert n.from_name == "Priya Raman" and n.from_email == "priya.raman@corp.example.com"


@pytest.mark.parametrize("value,name,email", [
    ('"Priya Raman" <priya.raman@corp.example.com>', "Priya Raman", "priya.raman@corp.example.com"),
    ("Priya Raman <priya.raman@corp.example.com>", "Priya Raman", "priya.raman@corp.example.com"),
    ("Priya Raman [mailto:priya.raman@corp.example.com]", "Priya Raman", "priya.raman@corp.example.com"),
    ("priya.raman@corp.example.com", "Priya Raman", "priya.raman@corp.example.com"),
])
def test_sender_is_read_in_every_shape(value, name, email):
    assert parse_sender(value) == (name, email)


# ── the sign-off at the bottom ─────────────────────────────────────────────
@pytest.mark.parametrize("body,name,team", [
    ("Text.\n\n- Priya Raman\n  C360 Data Governance", "Priya Raman", "C360 Data Governance"),
    ("Text.\n\nRegards,\nMarcus Hale\nCODN Platform Team", "Marcus Hale", "CODN Platform Team"),
    ("Text.\n\nRegards,\nPriya Raman, C360 Data Governance", "Priya Raman", "C360 Data Governance"),
    ("Text.\n\nThanks,\nDana Whitfield\nDNA Data Office\ndana@corp.example.com",
     "Dana Whitfield", "DNA Data Office"),
])
def test_sign_off_gives_the_name_and_the_team(body, name, team):
    sig = signature(body)
    assert sig["name"] == name and sig["team"] == team


def test_a_second_name_is_not_treated_as_a_team():
    """Only a line that says what a team does counts as a team."""
    assert signature("Text.\n\nRegards,\nPriya Raman\nMarcus Hale")["team"] == ""


def test_a_table_row_is_not_treated_as_a_person():
    """An HTML table flattens to tab-separated lines that look tidy enough."""
    assert signature("Table\tAttribute\tChange\nCUSTOMER_ADDRESS\tCOUNTRY_CODE\tchanged")["name"] == ""


def test_an_unrecognised_sign_off_leaves_the_fields_blank():
    sig = signature("Some prose that ends the message without signing off at all.")
    assert sig["name"] == "" and sig["team"] == ""


# ── which system the notice came from ──────────────────────────────────────
@pytest.mark.parametrize("team,expected", [
    ("C360 Data Governance", "C360"),
    ("CODN Platform Team", "CODN"),
    ("DNA Data Office", "DNA"),
    ("Data Governance", ""),          # says nothing about which system
    ("", ""),
])
def test_source_system_comes_from_the_team(team, expected):
    assert source_system(team, "") == expected


def test_source_system_is_never_the_senders_first_name(cat):
    """The old rule filed a notice from Priya Raman under "Priya"."""
    out = extract_by_rules(read_pasted(OUTLOOK_PASTE), cat)
    assert out["source"] == "C360"
    assert out["pocName"] == "Priya Raman"


def test_a_priority_tag_is_not_a_system_name():
    assert source_system("", "[Action Required] something changes") == ""
    assert source_system("", "[Notice] something changes") == ""
    assert source_system("", "[C360] something changes") == "C360"


# ── the promise: pasting matches uploading ─────────────────────────────────
@pytest.mark.parametrize("sample", [
    "01-market-code-value-change.eml",
    "02-timestamp-decommission.eml",
    "03-no-impact.eml",
])
def test_pasting_a_sample_matches_uploading_it(sample, cat):
    """Same email, both ways in. Only the address differs, and only because it
    lives in the envelope rather than in the words."""
    uploaded = read_upload(sample, (SAMPLES / sample).read_bytes())
    a = extract_by_rules(uploaded, cat)
    b = extract_by_rules(read_pasted(uploaded.body), cat)     # the body, as pasted
    for key in ("source", "pocName", "pocTeam", "changeKind", "effectiveDate"):
        assert a[key] == b[key], f"{key} differs between uploading and pasting"
    assert [u["table"] for u in a["upstream"]] == [u["table"] for u in b["upstream"]]


def test_uploaded_email_now_reports_the_team_not_the_sender(cat):
    """pocTeam used to be a copy of the sender's name."""
    out = extract_by_rules(read_upload("01.eml", (SAMPLES / "01-market-code-value-change.eml").read_bytes()), cat)
    assert out["pocTeam"] == "C360 Data Governance"
    assert out["source"] == "C360"


def test_plain_text_with_nothing_to_read_does_not_invent(cat):
    out = extract_by_rules(Notification(body="MARKET_CODE on CUSTOMER_DEMOGRAPHICS is changing."), cat)
    assert out["source"] == "Unknown"
    assert out["pocName"] == "" and out["pocTeam"] == "" and out["pocEmail"] == ""


# ── someone opens the saved file in Notepad and pastes the lot ─────────────
def test_pasting_a_whole_raw_email_file_does_not_leak_its_plumbing(cat):
    """Content-Type and MIME-Version are header-shaped lines with no blank line
    between them and the rest. Left in the body, the first long one becomes
    Ripple's description of the change."""
    raw = (SAMPLES / "01-market-code-value-change.eml").read_text(encoding="utf-8")
    out = extract_by_rules(read_pasted(raw), cat)
    assert "Content-Type" not in out["changeDesc"]
    assert "MIME-Version" not in out["changeDesc"]
    assert "MARKET_CODE" in out["changeDesc"] or "Effective" in out["changeDesc"]
    assert out["source"] == "C360" and out["pocName"] == "Priya Raman"
    assert out["effectiveDate"] == "2026-09-18"


def test_a_real_sentence_with_a_colon_is_still_the_description(cat):
    """The narrow rule matters: a line like this is what somebody wrote."""
    out = extract_by_rules(read_pasted(
        "From: A Sender <a@corp.example.com>\n"
        "Subject: change\n\n"
        "Impact: MARKET_CODE on CUSTOMER_DEMOGRAPHICS changes to full country names.\n"), cat)
    assert out["changeDesc"].startswith("Impact:")


# ── names as they are actually written ─────────────────────────────────────
LOWER_CASE_EMAIL = """From: Priya Raman <priya.raman@corp.example.com>
Subject: Change to customer_demographics

Hello,

Effective 18 September 2026 we are changing segment_cd on
customer_demographics. The market_code column moves at the same time.

ACCOUNT_MASTER is unaffected by this change.

- Priya Raman
  C360 Data Governance
"""


def test_names_written_in_lower_case_are_found(cat):
    """Ripple used to match only SHOUTED_NAMES. BigQuery names are written in
    lower case, so an email like this one produced exactly one table to scan --
    ACCOUNT_MASTER, the only one the email says is fine -- with no warning of
    any kind and a clean, confident, useless result at the end of it."""
    out = extract_by_rules(read_pasted(LOWER_CASE_EMAIL), cat)
    found = {u["table"].upper(): [a.upper() for a in u["attrs"]] for u in out["upstream"]}
    assert "CUSTOMER_DEMOGRAPHICS" in found, out["upstream"]
    assert set(found["CUSTOMER_DEMOGRAPHICS"]) >= {"SEGMENT_CD", "MARKET_CODE"}, found
    assert out["upstream"][0]["table"].upper() == "CUSTOMER_DEMOGRAPHICS", \
        "the table the email is about comes first"


def test_a_one_word_column_name_is_found(cat):
    """cust_id has an underscore; plenty of real column names do not. A name
    with no underscore in it never matched the old rule at all, so it never
    reached the confirm screen and could not even be ticked by hand."""
    out = extract_by_rules(read_pasted(
        "From: A Sender <a@corp.example.com>\n"
        "Subject: change\n\n"
        "We are removing cust_id from customer_demographics.\n"), cat)
    found = {u["table"].upper(): [a.upper() for a in u["attrs"]] for u in out["upstream"]}
    assert "CUST_ID" in found.get("CUSTOMER_DEMOGRAPHICS", []), out["upstream"]


def test_ordinary_english_words_are_not_reported_as_unknown_names(cat):
    """Every word in the email is now checked against the catalogue. Only the
    SHOUTED ones are worth listing back as "not in your repository" -- listing
    all of them would bury the one line that matters."""
    out = extract_by_rules(read_pasted(LOWER_CASE_EMAIL), cat)
    listed = " ".join(out["warnings"])
    for ordinary in ("Hello", "Effective", "September", "change", "unaffected"):
        assert ordinary not in listed, listed
