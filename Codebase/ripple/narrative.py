"""Writing the summary and the reply without any AI.

This is what runs when there is no key, when the key stops working, or when
someone decides no data may leave the network. It is plainer than the AI
version, but it says exactly the same things -- the facts come from the scan
either way.
"""
from __future__ import annotations

from datetime import date


def _plural(n: int, one: str, many: str | None = None) -> str:
    return f"{n} {one}" if n == 1 else f"{n} {many or one + 's'}"


def days_until(iso: str) -> int | None:
    if not iso:
        return None
    try:
        y, m, d = (int(x) for x in iso.split("-"))
        return (date(y, m, d) - date.today()).days
    except (ValueError, TypeError):
        return None


def _names(items: list[str], limit: int = 6) -> str:
    """A readable list of table names, however many there really are.

    On a real repository one key column reaches hundreds of tables. Joining
    them all into a sentence produces a paragraph nobody reads, in the one place
    on the screen written to be read -- and the count, which is the fact that
    matters, disappears into the middle of it.
    """
    if len(items) <= limit:
        return ", ".join(items)
    return ", ".join(items[:limit]) + f" and {len(items) - limit} more"


def _unique(groups: list[dict]) -> list[dict]:
    """Rows across groups, listed once. A finding upstream of two tables appears
    in both groups; counting it twice makes the actions read like a stutter."""
    rows, seen = [], set()
    for g in groups:
        for r in g["rows"]:
            k = (r.get("file"), r.get("attr"), r.get("alias"), r.get("logic"))
            if k not in seen:
                seen.add(k)
                rows.append(r)
    return rows


def _subject_of(vals: dict) -> str:
    """What is changing, in words: the attributes, or the whole of a table.

    A table with no attribute used to print as an empty name in the middle of
    a sentence -- "No usage of  was found" -- in a letter ready to send.
    """
    bits: list[str] = []
    for u in vals.get("upstream", []):
        if u.get("whole") or not u.get("attrs"):
            bits.append(f"the whole of {u.get('table') or 'the table'}")
        else:
            bits.extend(u.get("attrs", []))
    return ", ".join(bits) or "the changed attributes"


def _whole_only(scan: dict) -> bool:
    """Was every item asked about a whole table rather than a column?"""
    asked = scan.get("attributes", [])
    return bool(asked) and all(a.get("whole") for a in asked)


def _row_phrase(r: dict) -> str:
    """A finding as a short phrase. A whole-table row has no alias to name."""
    if r.get("whole"):
        return f"{r['inter']} - {r['logic'].lower()}"
    return f"{r['inter']} - {r['logic'].lower()} on {r['alias']}"


def _row_action(r: dict) -> str:
    if r.get("whole"):
        return f"Change the statement that {r['logic'].lower()} in {r['file']}."
    return f"Fix the {r['logic'].lower()} on {r['alias']} in {r['file']}."


def summarise(scan: dict, vals: dict) -> dict:
    stats = scan.get("stats", {})
    groups = scan.get("groups", [])
    # Chains that end somewhere that is not on the production list, and usages
    # in code that builds no table at all. Both are real usages of the
    # attribute, and saying "no impact" while holding them would be a lie the
    # person then forwards to the upstream team in writing.
    reached = scan.get("reached", [])
    other = scan.get("other", [])
    unreadable = scan.get("unreadable", [])
    prod_names = [g["prod"] for g in groups]
    rows = _unique(groups)
    elsewhere = _unique(reached) + other
    breaking = [r for r in rows if r.get("breaking")]
    no_fix = [r for r in rows if r.get("noLocalFix")]
    attrs = _subject_of(vals)
    whole_only = _whole_only(scan)
    when = vals.get("effectiveLabel") or "the effective date"

    # How much of the repository this answer does NOT cover. A headline is a
    # sentence somebody quotes in a meeting and pastes into a reply, so it must
    # never claim more than was read: "no impact" over four hundred files that
    # were never opened is the exact answer this tool exists to stop anybody
    # giving, and so is "all fixable in code" over a list of files nobody could
    # follow -- the fix that is missing may well be in one of them.
    files_scanned = scan.get("filesScanned", 0)
    never_opened = stats.get("neverOpened", 0)
    # Two more ways this answer covers less than the whole picture, and both used
    # to be silent. A trail Ripple stopped following at its hop limit, and a
    # table built with SELECT * whose column list is nowhere in the code. Either
    # one makes "no impact" a sentence about how far Ripple looked rather than
    # about the pipeline -- and this is the paragraph that gets forwarded.
    cut_short = scan.get("cutShort", [])
    # Only the stars whose column list really is nowhere. One filled in from
    # the table it copies was read, and a letter that says "could not be read"
    # about it is a letter saying something false.
    star_tables = [s for s in scan.get("starTables", []) if not s.get("known")]
    # Facts this letter used to be written without, every one of them measured
    # as a letter that said the opposite of the screen it was written from.
    feeds = scan.get("feeds", [])
    stops = scan.get("stopsLoading", [])
    referenced = [r for r in scan.get("referencedHere", []) if r.get("namesColumns")]
    lookup_failed = bool(scan.get("lookupFailed"))
    # Code files walked past because of the folder they sit in. Measured: the
    # whole chain from the source table to the published one sat in build/, and
    # this file wrote "Please proceed as planned".
    skipped = len(scan.get("skippedInFolders", []))
    folder_names = scan.get("skippedFolderNames", [])
    # A whole file type Ripple does not open is exactly as unread as a folder it
    # was told to skip. Measured: the middle hop of the chain sat in a notebook,
    # and this letter said "Please proceed as planned" over it.
    unopened_types = scan.get("fileTypesUnopened", [])
    unopened = sum(t.get("count", 0) for t in unopened_types)
    blind = never_opened + len(unreadable) + len(cut_short) + skipped + unopened

    def _blind_phrase() -> str:
        bits = []
        if never_opened:
            bits.append(f"{_plural(never_opened, 'file')} could not be opened at all")
        if unreadable:
            bits.append(f"{_plural(len(unreadable), 'file')} could not be followed")
        if skipped:
            bits.append(f"{_plural(skipped, 'code file')} "
                        f"{'sits' if skipped == 1 else 'sit'} in a folder Ripple is told to "
                        f"skip ({_names(folder_names)}) and "
                        f"{'was' if skipped == 1 else 'were'} never read")
        if unopened:
            bits.append(f"{_plural(unopened, 'file')} "
                        f"{'is' if unopened == 1 else 'are'} of a type Ripple does not open "
                        f"({_names([t.get('ext', '') for t in unopened_types])})")
        if cut_short:
            bits.append(f"{_plural(len(cut_short), 'trail')} was stopped at "
                        f"{scan.get('maxHops', 4)} renames deep and was still going"
                        if len(cut_short) == 1 else
                        f"{len(cut_short)} trails were stopped at "
                        f"{scan.get('maxHops', 4)} renames deep and were still going")
        return " and ".join(bits)

    def _inferred_phrase() -> str:
        if not star_tables:
            return ""
        return (f" {_plural(len(star_tables), 'table')} on the way "
                f"{'is' if len(star_tables) == 1 else 'are'} built with SELECT *, so the column "
                f"list could not be read and the steps past "
                f"{'it' if len(star_tables) == 1 else 'them'} are worked out rather than read.")

    if not groups and elsewhere:
        # Found, and consumed -- but nothing it feeds is on the list of tables
        # this team publishes. That is either a genuinely internal chain or a
        # production naming rule that does not match this repository, and only
        # a person can tell which. So the wording says exactly that.
        # A chain that Ripple stopped following has not ended, so it must not be
        # described with the word "end". That sentence used to be printed on the
        # screen where somebody decides whether to worry, about a chain that was
        # still going when the hop limit stopped the walk.
        cut_names = [c["table"] for c in cut_short]
        end_names = [g["prod"] for g in reached if not g.get("cut")]
        # Two things Ripple DID name, one line earlier on the same screen, while
        # this paragraph said "none of them reaching a table on your published
        # list" and sent the reader off to fix a rule that had worked perfectly.
        stop_names = [s["prod"] for s in stops]
        feed_names = [f["uri"] for f in feeds if f.get("uri")]
        if stop_names:
            headline = (f"{_plural(len(stop_names), 'published table')} "
                        f"{'stops' if len(stop_names) == 1 else 'stop'} being refreshed")
        elif feed_names:
            headline = (f"{_plural(len(feed_names), 'delivery')} out of the warehouse "
                        f"{'breaks' if len(feed_names) == 1 else 'break'}")
        else:
            headline = (f"{_plural(len(elsewhere), 'usage')} found - none of them reaching "
                        f"a table on your published list")
        narrative = (
            f"{attrs} is used in {_plural(len({r.get('file') for r in elsewhere}), 'file')} "
            f"of the {scan.get('filesScanned', 0)} scanned. "
            + (f"Those chains end at {_names(end_names)}. " if end_names else "")
            + (f"Ripple stopped following {_names(cut_names)} at "
               f"{scan.get('maxHops', 4)} renames deep - "
               f"{'that trail was' if len(cut_names) == 1 else 'those trails were'} still going, "
               f"so nothing past that point has been looked at. " if cut_names else "")
            + (f"{_names(stop_names)} "
               f"{'is on your published list and stops' if len(stop_names) == 1 else 'are on your published list and stop'}"
               f" being refreshed: no column of "
               f"{'it' if len(stop_names) == 1 else 'them'} changes, the job that fills "
               f"{'it' if len(stop_names) == 1 else 'them'} stops running. " if stop_names else "")
            + (f"The data also leaves the warehouse: {_names(feed_names)} is written by one of "
               f"these statements, and whoever reads that file is outside this repository. "
               if feed_names else "")
            + ("" if stop_names or feed_names else
               "None of those names match the rule Ripple has been given for a table this "
               "team publishes, so this is not a clean result - it is an unfinished one. "
               "Check the rule on the settings screen before replying.")
            + _inferred_phrase()
        )
        bullets = [_row_phrase(r) for r in elsewhere[:4]]
        if stop_names:
            bullets.insert(0, f"{_names(stop_names)} stops being refreshed on the day of the "
                              f"change. Nothing fails on screen; the numbers go stale.")
        if feed_names:
            bullets.insert(0, f"The delivery at {_names(feed_names)} carries this attribute out "
                              f"of the warehouse. Whoever reads it has to be told.")
        if not stop_names and not feed_names:
            bullets.append("Nothing here matched the production naming rule, so Ripple cannot say "
                           "whether these tables are ones anybody outside the team reads.")
        if cut_names:
            bullets.append(f"{_plural(len(cut_names), 'trail')} was cut short by the hop limit "
                           f"rather than by the code. Run the scan again, deeper, before "
                           f"treating this as the whole answer.")
        actions = ([f"Follow the trails Ripple stopped at - they were still going at "
                    f"{scan.get('maxHops', 4)} renames deep."] if cut_names else [])
        if feed_names:
            actions.append(f"Tell whoever reads {_names(feed_names)} - they are outside this "
                           f"repository and no scan of it will find them.")
        if stop_names:
            actions.append(f"Fix the job that fills {_names(stop_names)} before the date, or it "
                           f"quietly serves yesterday's data.")
        if not stop_names and not feed_names:
            actions.append("Check the production table rule on the settings screen against how "
                           "your tables are really named, then run the scan again.")
        actions.append("Until then, treat the tables listed above as impacted.")
    elif not files_scanned:
        # Nothing was read at all. "No impact" here is a statement about an
        # empty folder dressed up as a statement about a pipeline.
        headline = "Nothing was scanned - there was no code to search"
        narrative = (
            f"Ripple read no files at all, so it has looked for {attrs} in nothing. This is not "
            f"a result about your pipeline; it is a result about an empty repository. Choose the "
            f"folder holding the code on the settings screen and run the scan again."
        )
        bullets = ["No file was read, so nothing can be said about the change either way."]
        actions = [
            "Point Ripple at the folder holding the code, on the settings screen.",
            "Run the scan again once files have been read.",
        ]
    elif lookup_failed:
        # Not "no impact". Ripple never met this name as a column on any table
        # it read, so it has not answered the question -- and this paragraph is
        # the one that gets pasted into a reply. Measured: a mistyped attribute
        # produced "No impact - nothing in this repository consumes the
        # attribute" and a letter reading "Please proceed as planned."
        known = [c for a in scan.get("attributes", []) for c in a.get("tableColumns", [])]
        table = (scan.get("attributes") or [{}])[0].get("table", "that table")
        if whole_only:
            # The table itself was never met: nothing here reads it and
            # nothing here builds it. Not "nothing reads it" -- that would be
            # an answer, and this is the question not having been asked.
            headline = f"{table} was not found - nothing has been checked"
            narrative = (
                f"Ripple read {_plural(files_scanned, 'file')} and never met a table called "
                f"{table}: nothing here reads it and nothing here builds it. That is not the "
                f"same as the change being safe - the question has not been answered. Check "
                f"the spelling, and check that this table is used in this repository at all, "
                f"before replying."
            )
            bullets = [
                f"No answer either way about {table} - the name was not found as a table.",
                "Nothing in this repository reads or builds a table of that name.",
            ]
            actions = [
                f"Check the spelling of {table}, then run the scan again.",
                "Do not reply to the upstream team on the strength of this scan.",
            ]
        else:
            headline = f"{attrs} was not found - nothing has been checked"
            narrative = (
                f"Ripple read {_plural(files_scanned, 'file')} and never met a column called "
                f"{attrs} on {table}, or on anything else in this repository. That is not the "
                f"same as the change being safe: the question has not been answered. Check the "
                f"spelling before replying."
                + (f" The columns Ripple did read on {table} are {_names(known, 12)}."
                   if known else
                   f" Ripple has no column list for {table} either, because nothing in this "
                   f"repository writes one down.")
            )
            bullets = [
                f"No answer either way about {attrs} - the name was not found as a column.",
                (f"What Ripple did read on {table}: {_names(known, 12)}." if known else
                 f"Nothing in this repository states the columns of {table}."),
            ]
            actions = [
                f"Check the spelling of {attrs} against the list above, then run the scan again.",
                "Do not reply to the upstream team on the strength of this scan.",
            ]
    elif not groups:
        if referenced:
            # Nothing carries the column anywhere, and something names it
            # outright and stops working without it. That is not "no impact".
            headline = (f"No lineage, but {_plural(len(referenced), 'statement')} "
                        f"{'names' if len(referenced) == 1 else 'name'} {attrs} directly")
        elif blind:
            headline = (f"No usage found in the {_plural(files_scanned, 'file')} that could be "
                        f"read - {_plural(blind, 'other file')} could not be")
        else:
            headline = "No impact - nothing in this repository consumes the attribute"
        narrative = (
            f"The scan read {_plural(files_scanned, 'file')} looking for {attrs}, and found no "
            f"path from it to any production table this team publishes."
            + (f" {_plural(len(referenced), 'statement')} does name it and carries it nowhere: "
               f"{_names([r['kind'] + ' on ' + r['table'] for r in referenced])}. "
               f"{'That stops' if len(referenced) == 1 else 'Those stop'} working on the day "
               f"the column changes." if referenced else "")
            + (f" It is not a clean result for the whole repository: {_blind_phrase()}, "
               f"so nothing in those is covered either way." if blind else "")
            + _inferred_phrase()
        )
        bullets = [
            f"No production table depends on {attrs}.",
            f"{_plural(scan.get('filesMatched', 0), 'file')} mentioned the name, none of them in a way that carries it downstream.",
        ]
        if referenced:
            bullets.insert(0, f"{_plural(len(referenced), 'statement')} names {attrs} without "
                              f"carrying it anywhere - "
                              f"{_names([r['kind'] + ' on ' + r['table'] for r in referenced])}.")
        actions = (["Read the files below by hand before replying - this result does not cover them."]
                   if blind else [])
        if referenced:
            actions.append(f"Update the "
                           f"{_names([r['kind'] for r in referenced])} that names {attrs}.")
        actions += [
            "Reply to the upstream team confirming no impact." if not blind and not referenced
            else "Reply only once those have been checked.",
            "Re-run the scan if this repository takes on the table later.",
        ]
    else:
        if no_fix:
            headline = "Ranking logic has no replacement - escalate before the date"
        elif breaking and blind:
            # "All fixable in code" is a promise about the whole repository. The
            # fix that has no substitute may well be inside one of the files
            # nobody could follow, and that is not a promise to make on a
            # headline somebody forwards.
            headline = (f"{_plural(len(prod_names), 'production table')} at risk, and "
                        f"{_plural(blind, 'file')} Ripple could not follow")
        elif breaking:
            headline = f"{_plural(len(prod_names), 'production table')} at risk, all fixable in code"
        elif blind:
            headline = (f"Labels change - and {_plural(blind, 'file')} could not be checked")
        else:
            headline = "Labels change, but nothing breaks"
        narrative = (
            f"{attrs} changes on {when}. "
            f"{_plural(len(rows), 'pipeline object')} consume it across "
            f"{_plural(stats.get('filesWithImpact', 0), 'file')}, feeding "
            f"{_names(prod_names)}. "
            + (
                f"{_plural(len(breaking), 'of those usages breaks', 'of those usages break')} outright."
                if breaking
                else "None of those usages break outright - the values simply change shape."
            )
        )
        bullets = []
        for r in breaking[:4]:
            bullets.append(f"{_row_phrase(r)} - {r['impact']}")
        if no_fix:
            bullets.append(
                "At least one usage has no local fix: a replacement must come from the upstream team."
            )
        if not bullets:
            bullets.append("Every usage carries the value through unchanged; only labels move.")
        actions = []
        for r in breaking[:4]:
            actions.append(_row_action(r))
        if no_fix:
            actions.insert(0, "Ask the upstream team for a replacement attribute - this one has no substitute.")
        actions.append("Re-run the scan once the fixes are in, and confirm the findings clear.")

    if unreadable:
        bullets.append(
            f"{_plural(len(unreadable), 'file')} could not be followed and must be checked by hand."
        )
        actions.append(
            f"Read the {_plural(len(unreadable), 'file')} in the 'check by hand' list yourself - "
            f"Ripple could not read them, or found the name somewhere it cannot follow."
        )

    # Files that were never opened go first among the caveats and are worded
    # harder, because every other number on the page is a number about the files
    # that WERE opened. Left unsaid, this reads as an answer about the whole
    # repository when it is an answer about part of one.
    if never_opened:
        bullets.insert(0, (
            f"{_plural(never_opened, 'file')} in this repository could not even be opened, so "
            f"nothing in them was read - this result covers the rest."
        ))
        actions.insert(0, (
            f"Make the {_plural(never_opened, 'file')} that could not be opened available on this "
            f"machine and read the repository again before trusting this result."
        ))

    return {
        "headline": headline,
        "narrative": narrative,
        "bullets": bullets[:6],
        "actions": actions[:6],
        "writtenBy": "rules",
    }


def draft_reply(scan: dict, vals: dict, summary: dict) -> dict:
    groups = scan.get("groups", [])
    reached = scan.get("reached", [])
    other = scan.get("other", [])
    # The same rows the summary counted. A finding upstream of two published
    # tables appears in both groups, so counting them raw made the letter say
    # "9 pipeline objects" one click after the summary said 8 -- two numbers for
    # the same thing, and the wrong one is the one that leaves the building.
    rows = _unique(groups)
    elsewhere = _unique(reached) + other
    no_fix = [r for r in rows if r.get("noLocalFix")]
    poc = vals.get("pocName") or "there"
    first = poc.split()[0] if poc and poc != "there" else "there"
    attrs = _subject_of(vals)
    whole_only = _whole_only(scan)
    subject_base = vals.get("subject") or f"{attrs} change"

    if not groups and elsewhere:
        # This draft is a letter somebody sends. It must never say "no impact"
        # while the analysis behind it is holding a list of usages.
        end_names = _names([g["prod"] for g in reached], 10) or "tables in our own pipeline"
        # Two things Ripple named that this letter used to leave out entirely,
        # while telling the reader the data feeds "tables in our own pipeline".
        stops = scan.get("stopsLoading", [])
        feeds = [f["uri"] for f in scan.get("feeds", []) if f.get("uri")]
        subject = f"RE: {subject_base} - assessment in progress"
        lines = [
            f"Hi {first},", "",
            "We have run our impact analysis and are still confirming the result.", "",
            f"{attrs} is used in {_plural(len({r.get('file') for r in elsewhere}), 'file')} "
            f"in our repository, feeding {end_names}.",
        ]
        if stops:
            lines += ["", f"One thing is already confirmed: "
                          f"{_names([s['prod'] for s in stops], 10)} stops being refreshed on "
                          f"the day of the change. No column of it changes - the job that fills "
                          f"it stops running, so it quietly serves stale data."]
        if feeds:
            lines += ["", f"This data also leaves the warehouse. {_names(feeds, 10)} is written "
                          f"from one of these statements and read by somebody outside our "
                          f"repository, so we are tracing who consumes it."]
        if not stops:
            lines += ["", "We are confirming which of those tables are published outside our "
                          "team before we can tell you whether this is impacting."]
        lines += ["", "We will come back to you with a firm answer before the effective date.",
                  "", "Thanks,", "Data Engineering"]
        body = "\n".join(lines)
    elif not scan.get("filesScanned", 0):
        # There was nothing to read. A letter saying "no impact" here is a
        # letter about an empty folder, sent to somebody who will act on it.
        subject = f"RE: {subject_base} - assessment not yet run"
        body = (
            f"Hi {first},\n\n"
            f"We are not able to give you an answer yet. Our impact analysis read no files at "
            f"all, so nothing has actually been checked.\n\n"
            f"We will come back to you with a firm answer before the effective date.\n\n"
            f"Thanks,\nData Engineering"
        )
    elif scan.get("lookupFailed"):
        # The question was never answered. Ripple never met this name as a
        # column anywhere it read, so there is nothing to report either way --
        # and this letter used to say "No impact... Please proceed as planned."
        table = (scan.get("attributes") or [{}])[0].get("table", "that table")
        subject = (f"RE: {subject_base} - we need to check the table name" if whole_only
                   else f"RE: {subject_base} - we need to check the attribute name")
        body = (
            f"Hi {first},\n\n"
            f"We cannot answer this one yet.\n\n"
            + (f"Our repository scan could not find a table called {table} anywhere in our "
               f"code - nothing reads it and nothing builds it - so nothing has actually been "
               f"checked against it. That is most likely a difference in how the table is "
               f"named on our side.\n\n"
               f"Could you confirm the exact table name? "
               if whole_only else
               f"Our repository scan could not find a column called {attrs} anywhere in our "
               f"code, so nothing has actually been checked against it. That is most likely a "
               f"difference in how the attribute is named on our side.\n\n"
               f"Could you confirm the exact column name? ")
            + f"We will re-run the analysis and come back "
            f"to you with a firm answer before the effective date.\n\n"
            f"Thanks,\nData Engineering"
        )
    elif not groups:
        # "No impact, proceed as planned" is the single most consequential
        # sentence this tool writes. It is only ever sent when the whole
        # repository really was read -- and a trail Ripple stopped following at
        # its own hop limit is not the whole repository having been read, any
        # more than a folder Ripple was told to skip is.
        referenced = [r for r in scan.get("referencedHere", []) if r.get("namesColumns")]
        # A folder Ripple was told to skip is exactly as unread as a file it
        # could not open, and this letter used to count neither.
        blind = (scan.get("stats", {}).get("neverOpened", 0)
                 + len(scan.get("unreadable", []))
                 + len(scan.get("cutShort", []))
                 + len(scan.get("skippedInFolders", []))
                 # ... and a file type Ripple does not open at all is neither
                 # read nor followed nor reached. See fileTypesUnopened.
                 + sum(t.get("count", 0) for t in scan.get("fileTypesUnopened", [])))
        if blind or referenced:
            subject = f"RE: {subject_base} - no impact found so far"
            lines = [
                f"Hi {first},", "",
                "We have run our impact analysis and are still confirming the result.", "",
                f"No usage of {attrs} was found in the "
                f"{_plural(scan.get('filesScanned', 0), 'file')} we were able to read, and no "
                f"production table traces back to it.",
            ]
            if blind:
                lines += ["", f"{_plural(blind, 'further file')} could not be read, followed or "
                              f"reached automatically and "
                              f"{'is' if blind == 1 else 'are'} being checked by hand, so we are "
                              f"not confirming no impact yet."]
            if referenced:
                # Read, understood, and carrying the column nowhere -- so it is
                # not on any chain, and it stops working all the same.
                lines += ["", f"Separately, {_plural(len(referenced), 'statement')} in our "
                              f"repository names {attrs} without carrying it into another table "
                              f"- {_names([r['kind'] + ' on ' + r['table'] for r in referenced])}. "
                              f"{'That has' if len(referenced) == 1 else 'Those have'} to be "
                              f"updated on our side before the date."]
            lines += ["", "We will come back to you with a firm answer before the effective "
                          "date.", "", "Thanks,", "Data Engineering"]
            body = "\n".join(lines)
        else:
            subject = f"RE: {subject_base} - no impact"
            body = (
                f"Hi {first},\n\n"
                f"We have completed our impact analysis.\n\n"
                f"No impact. Our repository scan found no usage of {attrs} in any SQL, Spark job, "
                f"view or ETL script, and no production table traces back to it.\n\n"
                f"No action required from our side. Please proceed as planned.\n\n"
                f"Thanks,\nData Engineering"
            )
    else:
        # Capped like every other list of table names here: this is a letter
        # somebody sends, and a paragraph of two hundred names is not read.
        prod = _names([g["prod"] for g in groups], 10)
        lines = [f"Hi {first},", "", "We have completed our impact analysis.", ""]
        lines.append(
            f"Impact confirmed. {attrs} is consumed by {_plural(len(rows), 'pipeline object')} "
            f"feeding {_plural(len(groups), 'production table')}: {prod}."
        )
        lines.append("")
        lines.append("What we will do before the effective date:")
        for a in summary.get("actions", [])[:4]:
            lines.append(f"  - {a}")
        if no_fix:
            lines += [
                "",
                "One ask of your team: at least one of these usages orders or deduplicates on the "
                "attribute, and has no local substitute. Can you confirm a replacement attribute, "
                "or retain this one, before the effective date?",
            ]
        unreadable = scan.get("unreadable", [])
        if unreadable:
            lines += [
                "",
                f"For transparency: {_plural(len(unreadable), 'file')} in our repository could not be "
                f"read automatically and are being checked by hand, so this assessment may still grow.",
            ]
        never_opened = scan.get("stats", {}).get("neverOpened", 0)
        if never_opened:
            lines += [
                "",
                f"Also for transparency: {_plural(never_opened, 'file')} could not be opened at all "
                f"on the machine this was run on, so this assessment does not cover them.",
            ]
        lines += ["", "Thanks,", "Data Engineering"]
        subject = f"RE: {subject_base} - impact confirmed"
        body = "\n".join(lines)

    return {"subject": subject, "body": body, "writtenBy": "rules"}
