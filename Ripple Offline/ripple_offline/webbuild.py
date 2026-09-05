"""Building the offline front end out of the online one.

The same argument as the engine: two copies of a 60 KB screen would drift, and
the drifting one would be the copy running where nobody can check it. So there
is one front end, in ``Codebase/web``, and this makes the offline version of it.

Two things happen here.

*Lines are deleted.* The shared files mark the parts that reach out — the
GitHub source and the AI key form — between ``//<online-only>`` and
``//</online-only>``. Those lines are removed, so they are not merely unused in
the offline build, they are not in it. Then the result is checked for the words
that should no longer be there. That check is the real safeguard: if somebody
edits the online front end and loses a marker, the offline build fails with the
word it found rather than quietly shipping a key box onto a locked-down machine.

*One file is added.* ``web/offline.js`` holds the screens that only exist
offline — choosing the repository folder and the SQL dialect. It is appended to
the stripped script rather than loaded separately, because JavaScript hoists
every function declaration in a file before running any of it, which is what
lets it replace the online settings screen cleanly.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

from .engine import OFFLINE_DIR, SHARED_WEB

JS_START, JS_END = "//<online-only>", "//</online-only>"
HTML_START, HTML_END = "<!--<online-only>-->", "<!--</online-only>-->"

OFFLINE_JS = OFFLINE_DIR / "web" / "offline.js"

# Words that must not survive into the offline build. Each one is either a way
# out of the machine or a box asking for a secret.
BANNED = (
    "github", "/api/ai/", "api key", "apikey", "access token",
    # Every provider the online copy can talk to. Adding a provider online and
    # forgetting this line is exactly how a key box reaches a machine that is
    # meant to have no way out -- so each name, and each address, is listed.
    "groq", "console.groq", "api.groq",
    "openai", "api.openai", "platform.openai",
    "gemini", "aistudio.google", "generativelanguage", "googleapis",
)

# Functions the offline build takes over completely. They must be gone from the
# stripped script, and offline.js must define every one of them -- otherwise the
# page would load and then fail on a missing function.
REPLACED = ("settingsView", "repoAlert", "afterBoot")

# Functions that must not survive at all: these are the GitHub form and the AI
# key form themselves.
REMOVED = ("gitHubForm", "doConnect", "aiCard", "whoIssued", "anOrA", "fileUrl")

BANNER = """/* GENERATED — do not edit.
   Built from Codebase/web/app.js with the online-only parts removed, plus
   Ripple Offline's own screens appended. Edit those two files instead; this one
   is rewritten from them every time Ripple Offline starts or is built. */
"""

HTML_BANNER = """<!-- GENERATED — do not edit. Built from Codebase/web/index.html. -->
"""


_FUNCTION = re.compile(r"^\s*function\s+([A-Za-z_$][\w$]*)\s*\(", re.MULTILINE)

# Names from the shared front end that offline.js must not reuse for a local
# variable. A `const why = ...` inside a function shadows the shared helper of
# that name for the whole function, so calling it there throws -- and it throws
# only in the offline build, on the copy nobody can check. This is not caught by
# the function-clash test below: a local const is not a declaration.
SHADOWED = ("why", "el", "api", "run", "render", "esc")

_LOCAL = re.compile(
    r"^\s*(?:const|let|var)\s+(" + "|".join(SHADOWED) + r")\s*=", re.MULTILINE)


def _functions(text: str) -> set[str]:
    """Every function this script declares at the top level of a line."""
    return set(_FUNCTION.findall(text))


def _shadowed(text: str) -> list[str]:
    """Shared helper names offline.js reuses as a local variable."""
    return sorted(set(_LOCAL.findall(text)))


class BuildError(RuntimeError):
    """The front end could not be built, and the reason is worth reading."""


def strip_blocks(text: str, start: str, end: str, what: str) -> tuple[str, int]:
    """Delete every marked block. Unbalanced markers are an error, not a guess."""
    kept: list[str] = []
    depth = removed = 0
    for number, line in enumerate(text.splitlines(), start=1):
        bare = line.strip()
        if bare == start:
            depth += 1
            if depth == 1:
                removed += 1
            continue
        if bare == end:
            if depth == 0:
                raise BuildError(f"{what}, line {number}: a block is closed that was never opened.")
            depth -= 1
            continue
        if depth == 0:
            kept.append(line)
    if depth:
        raise BuildError(f"{what}: {depth} online-only block(s) were opened and never closed.")
    return "\n".join(kept) + "\n", removed


def check_clean(text: str, what: str) -> None:
    low = text.lower()
    for word in BANNED:
        if word in low:
            line = next((n for n, l in enumerate(text.splitlines(), 1) if word in l.lower()), 0)
            raise BuildError(
                f"{what} still mentions \"{word}\" at line {line} after the online-only parts "
                f"were removed. Ripple Offline must have nothing on it that reaches out, so "
                f"either that code needs an online-only marker around it, or it should not be "
                f"in the shared front end at all.")


def build(out_dir: Path | None = None, shared_web: Path | None = None) -> Path:
    """Write the offline front end. Returns the folder it was written to."""
    shared = Path(shared_web or SHARED_WEB)
    out = Path(out_dir or (OFFLINE_DIR / "build" / "web"))
    for needed in ("app.js", "index.html", "styles.css"):
        if not (shared / needed).is_file():
            raise BuildError(f"The shared front end is missing {needed}. Looked in {shared}.")
    if not OFFLINE_JS.is_file():
        raise BuildError(f"Ripple Offline's own screens are missing: {OFFLINE_JS}")

    js, js_blocks = strip_blocks((shared / "app.js").read_text(encoding="utf-8"),
                                 JS_START, JS_END, "app.js")
    html, html_blocks = strip_blocks((shared / "index.html").read_text(encoding="utf-8"),
                                     HTML_START, HTML_END, "index.html")
    if not js_blocks or not html_blocks:
        raise BuildError(
            "No online-only markers were found in the shared front end. They are what "
            "keeps the GitHub source and the AI key form out of the offline build, so "
            "building without them would ship both.")

    for name in REMOVED + REPLACED:
        if f"function {name}" in js:
            raise BuildError(
                f"{name}() survived the strip. It has to sit inside an online-only block: "
                f"offline it would either reach out or be replaced.")

    offline_js = OFFLINE_JS.read_text(encoding="utf-8")
    for name in REPLACED:
        if f"function {name}" not in offline_js:
            raise BuildError(
                f"offline.js does not define {name}(). The shared script calls it, so the "
                f"offline page would load and then fail on the first click.")

    # Anything defined in both files silently replaces the shared one, because
    # the offline file is appended and JavaScript keeps the last declaration.
    # That is the whole mechanism for the three above -- and a trap for every
    # other name, where the offline build would quietly run different code from
    # the one that can be checked. Only the deliberate three are allowed.
    shadow = [n for n in _shadowed(offline_js) if f"function {n}(" in js]
    if shadow:
        raise BuildError(
            f"offline.js uses {', '.join(shadow)} as a local variable, and the shared front "
            f"end has a helper of that name. A local const shadows it for the whole function, "
            f"so calling the helper there throws -- and only in this build, on the copy nobody "
            f"can check. Rename the local one.")

    clash = sorted(_functions(js) & _functions(offline_js) - set(REPLACED))
    if clash:
        raise BuildError(
            f"offline.js and the shared front end both define {', '.join(clash)}. "
            f"The offline copy would silently win, so the two editions would behave "
            f"differently with nothing on screen to say so. Rename it, or add it to "
            f"REPLACED in webbuild.py if replacing it is really the intention.")

    js = BANNER + js + "\n" + offline_js
    html = html.replace("<title>Ripple —", "<title>Ripple Offline —", 1)
    html = HTML_BANNER + html
    check_clean(js, "The offline app.js")
    check_clean(html, "The offline index.html")

    out.mkdir(parents=True, exist_ok=True)
    (out / "app.js").write_text(js, encoding="utf-8")
    (out / "index.html").write_text(html, encoding="utf-8")
    shutil.copyfile(shared / "styles.css", out / "styles.css")
    fonts_in, fonts_out = shared / "fonts", out / "fonts"
    if fonts_in.is_dir():
        fonts_out.mkdir(parents=True, exist_ok=True)
        for f in fonts_in.iterdir():
            if f.is_file():
                shutil.copyfile(f, fonts_out / f.name)
    return out
