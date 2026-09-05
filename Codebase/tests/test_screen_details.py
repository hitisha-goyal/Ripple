"""Small things on screen that were wrong, and that only a person ever notices.

Neither of these is a wrong answer. Both are the app looking broken or saying
something that is no longer true, which costs it exactly the trust the rest of
the work is spent earning.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

WEB = Path(__file__).resolve().parent.parent / "web"


def test_the_pulsing_dot_cannot_be_squashed_by_its_own_row():
    """Reported as "the dot that pulsates is halved", and measured in a browser:
    9 pixels tall, 5.61 wide.

    Every .spin sits in a flex row (.foot) beside a long sentence. Flex items
    shrink by default, so the browser squeezed the 9px dot sideways and left it
    9px tall -- and a round dot rendered as a narrow ellipse reads as half a dot
    that failed to draw. The neighbouring .dot rule already had this; .spin was
    simply missed.
    """
    css = (WEB / "styles.css").read_text(encoding="utf-8")
    rule = next(line for line in css.splitlines() if line.strip().startswith(".spin{"))
    # Gathered from the whole rule: it is written across two lines.
    at = css.index(".spin{")
    body = css[at:css.index("}", at)]
    assert "flex-shrink:0" in body.replace(" ", ""), rule


def test_the_dot_and_the_spinner_are_protected_the_same_way():
    """They sit in the same kind of row and are the same size. If one needs it
    and the other does not, one of them is wrong."""
    css = (WEB / "styles.css").read_text(encoding="utf-8").replace(" ", "").replace("\n", "")
    for name in (".dot{", ".spin{"):
        at = css.index(name)
        assert "flex-shrink:0" in css[at:css.index("}", at)], name


def test_the_repository_screen_no_longer_calls_a_select_star_table_a_dead_end():
    """That list is headed on the repository screen and read while somebody is
    deciding whether a scan result can be believed.

    It used to say Ripple "could not fully read" those tables, which was true
    when a scan stopped dead at them. A scan now follows the column straight
    through, so the old heading would send somebody looking for a gap that is
    not there.
    """
    js = (WEB / "app.js").read_text(encoding="utf-8")
    at = js.index("cat.gaps.length")
    # Comment lines are stripped: the note explaining WHY the old wording went
    # is allowed to quote it, and only what reaches the screen is being checked.
    card = "\n".join(line for line in js[at:at + 2400].splitlines()
                     if not line.strip().startswith("//"))
    # The negative is the load-bearing half: nothing here may read as a dead end.
    for dead_end in ("could not fully read", "stops here", "dead end", "goes no further"):
        assert dead_end not in card, dead_end
    assert "no column list written down" in card
    # And it has to say the scan carries on through. Pinned as any of the ways
    # that has been put rather than one exact sentence -- this copy is written
    # for somebody reading it for the first time, and it gets reworded.
    carries_on = ("does not stop here", "still travels through", "still follows",
                  "the scan follows it", "carries on")
    assert any(p in card for p in carries_on), card[:400]


# ── several contact addresses, in BOTH ways in ─────────────────────────────
# The reply goes to whoever sent the notification, and a notification is very
# often addressed to two or three people. One address means the other two never
# hear that their change breaks something.
#
# There are two ways into the app -- typing the change by hand, and uploading
# the email -- and the box only has to be forgotten on one of them for half the
# recipients to be dropped without anything on screen saying so.
def test_the_contact_box_reads_every_address_it_is_given():
    """Commas, semicolons, "Name <addr>", newlines, and the same address twice."""
    js = (WEB / "app.js").read_text(encoding="utf-8")
    line = next(l for l in js.splitlines() if l.strip().startswith("const EMAIL_RE"))
    pattern = line.split("=", 1)[1].strip().rstrip(";")
    # The screen's own regular expression, read out of the screen's own file, so
    # this cannot pass while the app uses a different one.
    body = pattern[1:pattern.rfind("/")]
    flags = pattern[pattern.rfind("/") + 1:]
    import re
    rx = re.compile(body.replace("\\d", "[0-9]"), re.I if "i" in flags else 0)

    def addresses(text: str) -> list[str]:
        return sorted({a.lower() for a in rx.findall(text)})

    assert addresses("priya@corp.com, marcus@corp.com") == \
        ["marcus@corp.com", "priya@corp.com"]
    assert addresses("Priya Raman <priya@corp.com>; Marcus <marcus@corp.com>") == \
        ["marcus@corp.com", "priya@corp.com"]
    assert addresses("a@x.com\nb@x.com") == ["a@x.com", "b@x.com"]
    assert addresses("one@x.com, One@X.com") == ["one@x.com"], "the same person once"
    assert addresses("nobody here") == []


def test_both_ways_in_collect_every_address():
    """Manual mode and a read email must both fill pocEmails. Forgetting one of
    them drops half the recipients with nothing on screen to show for it."""
    js = (WEB / "app.js").read_text(encoding="utf-8")
    assert "pocEmails: emailList(S.man.pocEmail)" in js, \
        "manual mode must read every address typed into the contact box"
    assert "pocEmails: emailList(out.pocEmail)" in js, \
        "a notification that was read must keep every address it named"


def test_the_reply_screen_uses_all_of_them():
    js = (WEB / "app.js").read_text(encoding="utf-8")
    assert "S.vals.pocEmails?.length ? S.vals.pocEmails" in js, \
        "the drafted reply must be addressed to everyone, not to the first one"


def test_the_clean_bill_of_health_cannot_print_over_a_file_type_never_opened():
    """Seen on the rendered screen and nowhere else: the green "Every file was
    opened and read. Nothing was skipped" note sat DIRECTLY ABOVE the card
    saying a notebook had never been looked inside.

    That note is the tool's clean bill of health for coverage, and it may not be
    printed while a whole file type went unread. Two things had to be true for
    the contradiction to survive: the unopened types were not counted into the
    "what this result does not cover" row, and the note's own condition did not
    mention them. Both are pinned here, because a JS change cannot be caught by
    a Python test any other way and this one only shows up in a picture.
    """
    js = (WEB / "app.js").read_text(encoding="utf-8")
    # Counted into the row, so a reader sees the number beside the other gaps.
    assert "'Types Ripple does not open'" in js, \
        "unopened file types are not counted into the coverage row"
    # ... and named in the note's own guard, so it cannot fire regardless.
    note = js.index("Every file was opened and read.")
    guard = js.rindex("if (", 0, note)
    condition = js[guard:note]
    assert "unopenedTypes" in condition, condition
    assert "couldNotRead" in condition, condition


# ── the information button ─────────────────────────────────────────────────
# One disclosure control, used on every screen. It exists so a card can say the
# fact and keep the reasoning out of the way -- and the whole product rests on
# which of those two a thing is. These two tests hold that line.


def _why_calls(js: str) -> list[list[tuple[int, int]]]:
    """Every why(...) call in the screen file, as the character range of each of
    its arguments.

    Ranges rather than the text itself: a panel argument can be a single letter
    of a longer expression, and deleting it by search-and-replace takes that
    letter out of the whole file. Written by walking parentheses rather than
    with a regular expression -- the arguments are nested calls holding strings
    holding brackets, and a pattern that survives that is one nobody can read.
    """
    import re
    calls = []
    for m in re.finditer(r"why\(", js):
        i, depth, cuts = m.end(), 1, [m.end()]
        while depth:
            c = js[i]
            if c in "([{":
                depth += 1
            elif c in ")]}":
                depth -= 1
                if depth == 0:
                    break
            elif c == "," and depth == 1:
                cuts.append(i + 1)
            elif c in "'\"`":
                q, i = c, i + 1
                while js[i] != q or js[i - 1] == "\\":
                    if js[i] == "\\":
                        i += 1
                    i += 1
            i += 1
        calls.append(list(zip(cuts, cuts[1:] + [i])))
    return calls


def test_there_is_one_information_button_and_every_screen_uses_it():
    """One helper, one style rule. A second one drifts from the first, and the
    two then behave differently on screens nobody compares side by side.

    It has to be a real button. A title= tooltip cannot be opened on a touch
    screen, cannot be reached from a keyboard, and disappears while it is being
    read -- which is why the browser's own is not good enough here.
    """
    js = (WEB / "app.js").read_text(encoding="utf-8")
    css = (WEB / "styles.css").read_text(encoding="utf-8")

    assert js.count("\nfunction why(") == 1, "there must be exactly one information button helper"
    body = js[js.index("\nfunction why("):]
    body = body[:body.index("\n}\n")]
    assert "'button'" in body, "it must be a real <button>, so Tab reaches it"
    assert "aria-expanded" in body, "a screen reader must be told whether it is open"
    assert "aria-controls" in body, "the button must point at the panel it opens"
    assert "aria-label" in body, "it must have a name a screen reader can read out"
    assert "'Escape'" in body, "Escape must close it, so a keyboard is never trapped"
    assert ".focus()" in body, "closing with Escape must hand the focus back"

    assert "button.i{" in css.replace(" ", ""), "the one style rule must exist"
    # Nothing may be fetched at runtime: the offline copy refuses outbound
    # connections and would simply show an empty panel.
    assert "http" not in body, "the information button must not reach the network"

    calls = _why_calls(js)
    assert len(calls) >= 30, f"only {len(calls)} cards use it; it is meant to be the one pattern"
    for c in calls:
        assert len(c) >= 3, f"why() needs a fact, a label and an explanation: {js[c[0][0]:c[-1][1]]}"


def test_no_count_and_no_warning_was_moved_behind_the_information_button():
    """The line the product rests on.

    Behind the button: why a fact matters, what Ripple did about it, what to do
    next. On the page, always: the fact, the number, and the names -- so
    somebody who never presses the button still sees everything Ripple knows it
    missed. They lose the reasoning, never the fact.

    Checked by deleting every explanation panel from the file and then looking
    for each of these in what is left. If one of them only survives inside a
    panel, it has been hidden.
    """
    js = (WEB / "app.js").read_text(encoding="utf-8")
    kept = list(js)
    for call in _why_calls(js):
        for start, end in call[2:]:
            for n in range(start, end):
                kept[n] = " "
    outside = "".join(kept)

    must_stay = [
        # every count, warning and named list from the screens
        ("never opened", "files that were never opened at all"),
        ("to check by hand", "the check-by-hand list"),
        ("carries it nowhere", "the mentions-only list"),
        ("table not stated", "the inferred-table marker"),
        ("stopped because of a setting", "trails cut short"),
        ("no column list to read", "tables not fully readable"),
        ("column list not visible", "the row badge for a SELECT * hop"),
        ("may stand for more than one table", "merged table names"),
        ("read through a wildcard", "the wildcard card"),
        ("written as text and run", "the run-as-text card"),
        ("run as text", "the run-as-text row badge"),
        ("being refreshed", "published tables that stop refreshing"),
        ("named after", "tables named after their file"),
        ("built from scratch in more than one file", "two definitions of one table"),
        ("in a skipped folder", "code not read because of the folder"),
        ("of a type Ripple does not open", "file types never opened"),
        ("files and nothing else", "the standing footer"),
        ("out of the warehouse", "deliveries out of the warehouse"),
        ("never met these column names", "the column-not-found headline"),
        ("in what Ripple could see", "the gap count beside the risk word"),
        ("Where Ripple could not see through", "the coverage card"),
        ("Every attribute you asked about", "the per-attribute panel"),
        ("Nothing is scanned until you confirm", "confirm before scanning"),
        ("Ripple needs to know which tables you publish", "the published-table gate"),
        ("Nothing can be scanned until this list is set", "the same gate on settings"),
        ("What Ripple did read on", "the columns Ripple did see"),
        # the stat cards
        ("'Production tables at risk'", "the production-tables stat"),
        ("'To check by hand'", "the check-by-hand stat"),
        ("'Never opened'", "the never-opened stat"),
        ("'Trails cut short'", "the trails-cut-short stat"),
        ("'Tables not fully readable'", "the not-fully-readable stat"),
        ("'Types Ripple does not open'", "the unopened-types stat"),
        ("'In folders Ripple skips'", "the skipped-folders stat"),
        ("'Deliveries out of the warehouse'", "the deliveries stat"),
        ("'Published tables that stop refreshing'", "the stops-refreshing stat"),
        ("'Breaking usages'", "the breaking-usages stat"),
    ]
    for needle, what in must_stay:
        assert needle in outside, (
            f"{what} now only exists inside an information panel. A count, a table name or a "
            f"warning that something was not read has to stay on the page: somebody who never "
            f"presses the button must still see everything Ripple knows it missed.")


def test_the_information_button_survives_into_the_offline_build():
    """The offline copy is the one running where nobody can check it. A pattern
    every screen depends on must not be one of the parts stripped out of it."""
    js = (WEB / "app.js").read_text(encoding="utf-8")
    at = js.index("\nfunction why(")
    before = js[:at]
    # It must not sit inside an online-only block, which the offline build deletes.
    assert before.count("//<online-only>") == before.count("//</online-only>"), \
        "the information button is inside an online-only block, so the offline build has none"


def test_the_scan_button_state_is_decided_in_exactly_one_place():
    """It was set twice in the same function, and the second assignment quietly
    undid the first -- so the published-table gate showed its own label on a
    button that was still pressable. Measured on the rendered screen: the text
    said "Add your published tables first" and disabled came back false.

    A control whose state is written twice is a control nobody can reason about
    by reading the code, which is how the second one got there."""
    js = (Path(__file__).resolve().parent.parent / "web" / "app.js").read_text(encoding="utf-8")
    sets = js.count("x(root, 'next').disabled")
    assert sets == 1, f"the scan button's state is assigned {sets} times, not once"
    where = js.index("x(root, 'next').disabled")
    line = js[where:js.index("\n", where)]
    assert "productionSet" in line, line
    assert "repoOk" in line, line


def test_the_screen_never_claims_a_fallback_the_engine_refuses():
    """The settings screen said Ripple would guess. It will not.

    Found on 28 Aug 2026 while following BUILD-KIT.md by hand. Paste a list that
    yields no table names and the screen printed:

        "Nothing in that box was read as a table name. Ripple falls back to its
        own guess - names ending _PROD, _PRD or _PUBLISHED"

    while the yellow banner directly beneath it said "Nothing can be scanned
    until this list is set", and /api/scan refuses outright with a 400. Two
    sentences on one screen saying opposite things, and the wrong one is the one
    that sounds reassuring.

    That fallback was taken out of the engine because it was, in the kit's own
    words, the most expensive thing this tool has ever done: on a warehouse that
    names its published tables anything else it matches NOTHING, and matching
    nothing reads as "no production table is affected", in green. The screen copy
    was simply left behind.

    So: config.py must still refuse an empty list, api.py must still block the
    scan, and no screen may describe a fallback that no longer happens.
    """
    js = (WEB / "app.js").read_text(encoding="utf-8")
    config = (WEB.parent / "ripple" / "config.py").read_text(encoding="utf-8")
    api = (WEB.parent / "ripple" / "api.py").read_text(encoding="utf-8")

    # The behaviour the copy has to agree with.
    assert "def has_production" in config, "the empty-list gate has gone from config.py"
    assert "if not settings.has_production():" in api, \
        "api.py no longer blocks a scan when nobody has said which tables are published"

    for claim in ("falls back to its own guess",
                  "Ripple falls back",
                  "falls back to the shipped default"):
        assert claim not in js, (
            f"web/app.js tells somebody {claim!r}. It does not fall back - "
            f"has_production() returns False and /api/scan refuses with a 400. "
            f"A screen describing a guess the engine will not make is the same "
            f"failure as the guess itself: the reader plans around it."
        )
