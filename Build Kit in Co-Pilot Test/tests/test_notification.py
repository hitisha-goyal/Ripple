from __future__ import annotations

"""Tests for reading the notification email.

Every table, column, person and address here is invented.
"""

import types
from email.message import EmailMessage

from ripple.notification import (
    Notification,
    change_kind,
    effective_date,
    extract_by_rules,
    extract_emails,
    first_sentence,
    parse_sender,
    read_pasted,
    read_upload,
    signature,
    source_system,
    split_pasted_headers,
)
import ripple.notification as notification_module


# --------------------------------------------------------------------------
# An invented catalogue, standing in for the one Phase 5 builds
# --------------------------------------------------------------------------

CATALOGUE = {
    "customer_demographics": ["cm13", "market_code", "pub_guid"],
    "ACCOUNT_MASTER": ["acct_key", "open_dt"],
    "ccm_Wireless_Enroll": ["enrol_dt", "cm13"],
}


SAMPLE_BODY = "\n".join(
    [
        "Hi team,",
        "",
        "We are removing the attribute cm13 from customer_demographics",
        "with effect from 18 September 2026, as part of a clean-up of",
        "legacy fields.",
        "",
        "Impact: any report that filters on cm13 will need a change.",
        "ACCOUNT_MASTER is unaffected.",
        "LEGACY_FEED_TABLE is not in your repository.",
        "",
        "Regards,",
        "",
        "Priya Raman",
        "C360 Data Governance",
        "priya.raman@corp.example.com",
    ]
)


def _sample_eml_bytes() -> bytes:
    message = EmailMessage()
    message["From"] = "Priya Raman <priya.raman@corp.example.com>"
    message["To"] = "Data Platform Team <platform@corp.example.com>"
    message["Subject"] = "[C360] Change to customer_demographics"
    message["Date"] = "Mon, 3 Aug 2026 09:14:00 +0100"
    message.set_content(SAMPLE_BODY)
    return message.as_bytes()


# --------------------------------------------------------------------------
# parse_sender and the address extractor
# --------------------------------------------------------------------------


def test_parse_sender_reads_all_four_shapes() -> None:
    assert parse_sender('"Priya Raman" <priya@corp.example.com>') == (
        "Priya Raman",
        "priya@corp.example.com",
    )
    assert parse_sender("Priya Raman <priya@corp.example.com>") == (
        "Priya Raman",
        "priya@corp.example.com",
    )
    assert parse_sender("Priya Raman [mailto:priya@corp.example.com]") == (
        "Priya Raman",
        "priya@corp.example.com",
    )
    assert parse_sender("priya.raman@corp.example.com") == (
        "Priya Raman",
        "priya.raman@corp.example.com",
    )


def test_extract_emails_reads_a_pasted_outlook_line() -> None:
    line = (
        "Priya Raman <priya@corp.example.com>; "
        "Marcus Hale <MARCUS@corp.example.com>; "
        "priya@corp.example.com"
    )
    assert extract_emails(line) == [
        "priya@corp.example.com",
        "marcus@corp.example.com",
    ]


# --------------------------------------------------------------------------
# Header blocks pasted into the body
# --------------------------------------------------------------------------


def test_a_sentence_starting_to_is_left_alone() -> None:
    body = "To: be clear, nothing is being changed this month."
    headers, cleaned = split_pasted_headers(body)
    assert headers == {}
    assert "To: be clear" in cleaned


def test_header_block_is_lifted_out_with_its_row_of_dashes() -> None:
    body = "\n".join(
        [
            "Hi team,",
            "",
            "-----Original Message-----",
            "From: Priya Raman <priya@corp.example.com>",
            "Sent: 03 August 2026 09:14",
            "To: Data Platform Team <platform@corp.example.com>",
            "Subject: Change to customer_demographics",
            'Content-Type: text/plain; charset="utf-8"; format=flowed',
            "MIME-Version: 1.0",
            "",
            "We will change the values of market_code on 18 September 2026.",
        ]
    )
    headers, cleaned = split_pasted_headers(body)
    assert headers["from"] == "Priya Raman <priya@corp.example.com>"
    assert headers["subject"] == "Change to customer_demographics"
    assert "Original Message" not in cleaned
    assert "Content-Type" not in cleaned
    assert "MIME-Version" not in cleaned
    assert "Sent:" not in cleaned
    assert "market_code" in cleaned


def test_two_forwarded_blocks_both_go_and_the_first_is_reported() -> None:
    body = "\n".join(
        [
            "From: Marcus Hale <marcus@corp.example.com>",
            "Sent: 05 August 2026 11:00",
            "Subject: FW: attribute change",
            "",
            "Passing this on.",
            "",
            "From: Priya Raman <priya@corp.example.com>",
            "Sent: 03 August 2026 09:14",
            "Subject: attribute change",
            "",
            "We are removing cm13 on 18 September 2026.",
        ]
    )
    headers, cleaned = split_pasted_headers(body)
    assert headers["from"] == "Marcus Hale <marcus@corp.example.com>"
    assert "priya@corp.example.com" not in cleaned
    assert "marcus@corp.example.com" not in cleaned
    assert "Passing this on." in cleaned


def test_attribution_line_is_read_and_removed() -> None:
    body = "\n".join(
        [
            "Thanks for the heads up.",
            "",
            "On Mon, 3 Aug 2026 at 09:14, Priya Raman "
            "<priya@corp.example.com> wrote:",
            "",
            "We are removing cm13 on 18 September 2026.",
        ]
    )
    headers, cleaned = split_pasted_headers(body)
    assert parse_sender(headers["from"]) == (
        "Priya Raman",
        "priya@corp.example.com",
    )
    assert "wrote:" not in cleaned
    assert "3 Aug 2026" not in cleaned


# --------------------------------------------------------------------------
# The sign-off
# --------------------------------------------------------------------------


def test_signature_is_read_from_the_bottom_up() -> None:
    body = "\n".join(
        [
            "Marcus Hale",
            "Please read the note below before Friday, it matters.",
            "",
            "Regards,",
            "",
            "Priya Raman",
            "C360 Data Governance",
            "priya.raman@corp.example.com",
        ]
    )
    signed = signature(body)
    assert signed["name"] == "Priya Raman"
    assert signed["team"] == "C360 Data Governance"
    assert signed["email"] == "priya.raman@corp.example.com"


def test_signature_reads_the_one_line_comma_layout() -> None:
    body = "\n".join(
        [
            "We will confirm the date next week once it is agreed.",
            "",
            "Thanks,",
            "Priya Raman, C360 Data Governance",
        ]
    )
    signed = signature(body)
    assert signed["name"] == "Priya Raman"
    assert signed["team"] == "C360 Data Governance"


def test_signature_refuses_a_flattened_table_row() -> None:
    body = "\n".join(
        [
            "The table below lists the affected fields for this change.",
            "Priya Raman\tC360 Data Governance",
        ]
    )
    assert signature(body)["name"] == ""


def test_signature_refuses_digits_and_lower_case_lines() -> None:
    body = "\n".join(
        [
            "The change lands in the September release of the platform.",
            "Room 12 Block",
            "thanks again everyone",
        ]
    )
    signed = signature(body)
    assert signed["name"] == ""
    assert signed["team"] == ""


def test_a_second_name_does_not_become_a_team() -> None:
    body = "\n".join(
        [
            "Please shout if any of this is a problem for your loads.",
            "",
            "Priya Raman",
            "Marcus Hale",
        ]
    )
    assert signature(body)["team"] == ""


# --------------------------------------------------------------------------
# Source system
# --------------------------------------------------------------------------


def test_source_system_drops_the_words_that_describe_a_team() -> None:
    assert source_system("C360 Data Governance", "") == "C360"
    assert source_system("Data Governance", "") == "Unknown"


def test_source_system_takes_a_code_off_the_subject_only() -> None:
    assert source_system("", "[CRM7] Attribute change") == "CRM7"
    assert source_system("", "[FYI] Attribute change") == "Unknown"
    assert source_system("", "[Weekly] Attribute change") == "Unknown"
    assert source_system("", "No tag at all here") == "Unknown"


# --------------------------------------------------------------------------
# The first sentence
# --------------------------------------------------------------------------


def test_first_sentence_skips_greetings_and_plumbing_but_keeps_impact() -> None:
    body = "\n".join(
        [
            "Hello everyone, I hope the week is treating you well so far.",
            'Content-Type: text/plain; charset="utf-8"; format=flowed',
            "X-Mailer: something long enough to be over forty characters",
            "Impact: this breaks the nightly load into the reporting layer.",
        ]
    )
    assert first_sentence(body) == (
        "Impact: this breaks the nightly load into the reporting layer."
    )


def test_first_sentence_is_capped_at_two_hundred_and_forty() -> None:
    assert len(first_sentence("a" * 400)) == 240


# --------------------------------------------------------------------------
# Dates and change kinds
# --------------------------------------------------------------------------


def test_dates_in_common_written_forms_become_iso() -> None:
    assert effective_date("with effect from 18 September 2026") == "2026-09-18"
    assert effective_date("on September 18, 2026 the field goes") == "2026-09-18"
    assert effective_date("on 18/09/2026 the field goes") == "2026-09-18"
    assert effective_date("on 2026-09-18 the field goes") == "2026-09-18"
    assert effective_date("no date in this line at all") == ""


def test_change_kind_words() -> None:
    assert change_kind("we are decommissioning the field") == "removal"
    assert change_kind("this is a format change for the field") == "type_change"
    assert change_kind("the values will change next month") == "value_change"
    assert change_kind("we are renaming the field") == "rename"
    assert change_kind("please review the attached document") == "unknown"


def test_the_word_the_email_leads_with_wins() -> None:
    assert change_kind("We are renaming cm13. Nothing is being removed.") == "rename"


# --------------------------------------------------------------------------
# extract_by_rules
# --------------------------------------------------------------------------


def test_names_match_in_any_case_and_without_an_underscore() -> None:
    body = "\n".join(
        [
            "We are removing cm13 from customer_demographics on 18 September 2026.",
            "The mixed case table ccm_wireless_enroll is affected as well.",
            "ACCOUNT_MASTER is unaffected.",
        ]
    )
    result = extract_by_rules(read_pasted(body), CATALOGUE)
    tables = [entry["table"] for entry in result["upstream"]]
    assert tables == [
        "customer_demographics",
        "ccm_Wireless_Enroll",
        "ACCOUNT_MASTER",
    ]
    assert result["upstream"][0]["attrs"] == ["cm13"]
    assert result["changeKind"] == "removal"
    assert result["effectiveDate"] == "2026-09-18"


def test_upstream_keeps_the_order_of_the_email() -> None:
    body = "ACCOUNT_MASTER changes before customer_demographics does."
    result = extract_by_rules(read_pasted(body), CATALOGUE)
    tables = [entry["table"] for entry in result["upstream"]]
    assert tables == ["ACCOUNT_MASTER", "customer_demographics"]


def test_shouted_names_the_repository_never_heard_of_are_warned_about() -> None:
    body = (
        "Changing customer_demographics. Also LEGACY_FEED_TABLE and "
        "OLD_STAGING_AREA are going."
    )
    result = extract_by_rules(read_pasted(body), CATALOGUE)
    mentioned = [
        warning
        for warning in result["warnings"]
        if warning.startswith("These names were mentioned")
    ]
    assert len(mentioned) == 1
    assert "LEGACY_FEED_TABLE" in mentioned[0]
    assert "OLD_STAGING_AREA" in mentioned[0]
    assert "customer_demographics" not in mentioned[0]


def test_only_the_first_eight_unknown_names_are_listed() -> None:
    names = [
        "ALPHA_ONE",
        "BETA_TWO",
        "GAMMA_THREE",
        "DELTA_FOUR",
        "EPSILON_FIVE",
        "ZETA_SIX",
        "ETA_SEVEN",
        "THETA_EIGHT",
        "IOTA_NINE",
        "KAPPA_TEN",
    ]
    body = "These are going: " + ", ".join(names) + "."
    result = extract_by_rules(read_pasted(body), CATALOGUE)
    mentioned = [
        warning
        for warning in result["warnings"]
        if warning.startswith("These names were mentioned")
    ][0]
    assert "THETA_EIGHT" in mentioned
    assert "IOTA_NINE" not in mentioned
    assert "KAPPA_TEN" not in mentioned


def test_no_table_recognised_says_so() -> None:
    result = extract_by_rules(read_pasted("Nothing here names a table."), CATALOGUE)
    assert result["upstream"] == []
    assert (
        "No table from the connected repository was recognised. "
        "Add the table and attributes by hand before scanning."
    ) in result["warnings"]


def test_a_recognised_table_produces_no_no_table_warning() -> None:
    result = extract_by_rules(
        read_pasted("customer_demographics is changing."), CATALOGUE
    )
    assert not [
        warning
        for warning in result["warnings"]
        if warning.startswith("No table from the connected repository")
    ]


def test_the_readers_own_warning_reaches_the_screen() -> None:
    complaint = (
        "Could not open the Outlook file: the file is not a compound file. "
        "Save the email as .eml, or paste the text of the email instead."
    )
    note = Notification(body="customer_demographics", warnings=[complaint])
    result = extract_by_rules(note, CATALOGUE)
    assert complaint in result["warnings"]


def test_the_envelope_name_is_never_overwritten() -> None:
    note = read_pasted(SAMPLE_BODY)
    note.from_name = "Marcus Hale"
    note.from_email = "marcus@corp.example.com"
    result = extract_by_rules(note, CATALOGUE)
    assert result["pocName"] == "Marcus Hale"
    assert result["pocEmail"] == "marcus@corp.example.com"


def test_the_effective_date_beats_the_sent_date() -> None:
    body = "\n".join(
        [
            "From: Priya Raman <priya@corp.example.com>",
            "Sent: 03 August 2026 09:14",
            "Subject: Attribute change",
            "",
            "We will change the values of market_code in",
            "customer_demographics on 18 September 2026.",
        ]
    )
    result = extract_by_rules(read_pasted(body), CATALOGUE)
    assert result["effectiveDate"] == "2026-09-18"
    assert result["pocName"] == "Priya Raman"
    assert result["pocEmail"] == "priya@corp.example.com"
    assert result["subject"] == "Attribute change"


def test_a_catalogue_object_holding_tables_is_read_too() -> None:
    catalog = types.SimpleNamespace(tables=CATALOGUE)
    result = extract_by_rules(read_pasted("customer_demographics cm13"), catalog)
    assert result["upstream"] == [
        {"table": "customer_demographics", "attrs": ["cm13"]}
    ]


def test_an_unreadable_catalogue_is_empty_rather_than_a_guess() -> None:
    result = extract_by_rules(read_pasted("customer_demographics"), None)
    assert result["upstream"] == []
    assert [
        warning
        for warning in result["warnings"]
        if warning.startswith("No table from the connected repository")
    ]


# --------------------------------------------------------------------------
# The Outlook path, where it cannot
# --------------------------------------------------------------------------


class _FakeAttachment:
    longFilename = "field_list.csv"
    shortFilename = "field.csv"


class _FakeMessage:
    subject = "Attribute change"
    sender = "Priya Raman <priya.raman@corp.example.com>"
    body = SAMPLE_BODY
    htmlBody = ""
    attachments = [_FakeAttachment()]

    def __init__(self, stream: object) -> None:
        self.stream = stream


class _EmptyMessage:
    subject = "Attribute change"
    sender = "Priya Raman <priya.raman@corp.example.com>"
    body = ""
    htmlBody = ""
    attachments: list[object] = []

    def __init__(self, stream: object) -> None:
        self.stream = stream


def test_a_missing_outlook_reader_is_a_warning_not_a_blank_form(monkeypatch) -> None:
    def boom() -> object:
        raise ImportError("no module named extract_msg")

    monkeypatch.setattr(notification_module, "_import_extract_msg", boom)
    note = read_upload("notice.msg", b"\x00\x01\x02")
    assert note.source_kind == "msg"
    assert note.body == ""
    assert note.warnings
    assert note.warnings[0].startswith("Could not open the Outlook file:")
    result = extract_by_rules(note, CATALOGUE)
    assert note.warnings[0] in result["warnings"]


def test_an_outlook_file_that_will_not_open_says_so(monkeypatch) -> None:
    def refuse(stream: object) -> object:
        raise OSError("this is not a compound file")

    monkeypatch.setattr(
        notification_module,
        "_import_extract_msg",
        lambda: types.SimpleNamespace(Message=refuse),
    )
    note = read_upload("notice.msg", b"not really an outlook file")
    assert note.warnings
    assert "this is not a compound file" in note.warnings[0]


def test_an_outlook_file_with_no_text_says_so(monkeypatch) -> None:
    monkeypatch.setattr(
        notification_module,
        "_import_extract_msg",
        lambda: types.SimpleNamespace(Message=_EmptyMessage),
    )
    note = read_upload("notice.msg", b"anything")
    assert note.warnings == [
        "The Outlook file opened but held no readable text. "
        "Paste the text of the email instead."
    ]


def test_an_outlook_file_that_opens_gives_sender_body_and_attachments(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        notification_module,
        "_import_extract_msg",
        lambda: types.SimpleNamespace(Message=_FakeMessage),
    )
    note = read_upload("notice.msg", b"anything")
    assert note.warnings == []
    assert note.from_name == "Priya Raman"
    assert note.from_email == "priya.raman@corp.example.com"
    assert note.attachments == ["field_list.csv"]
    assert "customer_demographics" in note.body


# --------------------------------------------------------------------------
# The test that holds all of this together
# --------------------------------------------------------------------------


def test_the_same_email_gives_the_same_fields_uploaded_or_pasted() -> None:
    uploaded = read_upload("notice.eml", _sample_eml_bytes())
    pasted = read_pasted(SAMPLE_BODY)

    assert uploaded.source_kind == "eml"
    assert uploaded.from_email == "priya.raman@corp.example.com"

    from_file = extract_by_rules(uploaded, CATALOGUE)
    from_paste = extract_by_rules(pasted, CATALOGUE)

    for field_name in (
        "source",
        "pocName",
        "pocTeam",
        "changeKind",
        "effectiveDate",
    ):
        assert from_file[field_name] == from_paste[field_name], field_name

    assert from_file["upstream"] == from_paste["upstream"]
    assert from_file["source"] == "C360"
    assert from_file["pocName"] == "Priya Raman"
    assert from_file["pocTeam"] == "C360 Data Governance"
    assert from_file["changeKind"] == "removal"
    assert from_file["effectiveDate"] == "2026-09-18"
    assert [entry["table"] for entry in from_file["upstream"]] == [
        "customer_demographics",
        "ACCOUNT_MASTER",
    ]
    assert from_file["extractedBy"] == "rules"


def test_a_plain_text_upload_reads_the_same_words() -> None:
    note = read_upload("notice.txt", SAMPLE_BODY.encode("utf-8"))
    assert note.source_kind == "txt"
    result = extract_by_rules(note, CATALOGUE)
    assert result["pocName"] == "Priya Raman"
    assert result["pocTeam"] == "C360 Data Governance"
    assert result["source"] == "C360"
    assert result["effectiveDate"] == "2026-09-18"
