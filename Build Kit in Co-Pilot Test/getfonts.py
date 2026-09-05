"""Fetch the two typefaces Ripple's screens use, once, into web/fonts/.

Run this once and then never again:

    python getfonts.py

Public Sans and IBM Plex Mono are binary files. No chat window can hand them
over, so this script goes and gets them. Both are published under the SIL Open
Font License, which allows exactly this - no licence, account or purchase.

Afterwards Ripple needs no network at all, ever: index.html loads
/static/fonts/fonts.css and every src in it points at a local file.

Standard library only.
"""

from __future__ import annotations

import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

# The stylesheet that lists every font file. Weights are the ones the screens
# actually use: five for the sans, three for the mono.
CSS_URL = (
    "https://fonts.googleapis.com/css2"
    "?family=Public+Sans:wght@400;500;600;700;800"
    "&family=IBM+Plex+Mono:wght@400;500;600"
    "&display=swap"
)

# WHY a browser User-Agent: Google decides the format from this header alone.
# With urllib's default agent it answers with .ttf files, which are several
# times larger and which the @font-face rules here do not name. This one line
# is the difference between 306 KB of .woff2 and about a megabyte of .ttf.
BROWSER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

# WHY only these two: Google now answers with cyrillic, greek and vietnamese as
# well - thirty files rather than sixteen, and nearly a third more to download.
# Ripple's screens never show a word in any of them.
WANTED_SUBSETS = ("latin", "latin-ext")

# Where the files land. Taken from this script's own folder rather than the
# working directory, so running it from somewhere else cannot scatter fonts
# into an unrelated folder.
ROOT = Path(__file__).resolve().parent
FONT_DIR = ROOT / "web" / "fonts"

# Google writes a /* subset */ comment immediately before each @font-face block.
# That comment is the only place the subset name appears, so the block and its
# comment have to be read together.
BLOCK_RE = re.compile(r"/\*\s*([a-z0-9\-\[\]]+)\s*\*/\s*(@font-face\s*\{.*?\})", re.DOTALL)
FAMILY_RE = re.compile(r"font-family:\s*'([^']+)'")
WEIGHT_RE = re.compile(r"font-weight:\s*(\d+)")
URL_RE = re.compile(r"url\((https://[^)]+)\)")


@dataclass
class Face:
    """One @font-face block, and the local file it will become."""

    family: str
    weight: str
    subset: str
    remote_url: str
    block: str

    @property
    def filename(self) -> str:
        """public-sans-600-latin.woff2 - family, weight, subset, lower case."""
        slug = self.family.lower().replace(" ", "-")
        return f"{slug}-{self.weight}-{self.subset}.woff2"


def fetch(url: str) -> bytes:
    """Fetch one URL with the browser agent set."""
    request = urllib.request.Request(url, headers={"User-Agent": BROWSER_AGENT})
    with urllib.request.urlopen(request) as response:
        return response.read()


def read_faces(stylesheet: str) -> list[Face]:
    """Pull every wanted @font-face out of the stylesheet Google returned."""
    faces: list[Face] = []
    for subset, block in BLOCK_RE.findall(stylesheet):
        if subset not in WANTED_SUBSETS:
            continue
        family = FAMILY_RE.search(block)
        weight = WEIGHT_RE.search(block)
        url = URL_RE.search(block)
        if not (family and weight and url):
            # A block missing any of the three is one this script does not
            # understand. Skipping it silently would leave a gap nobody sees,
            # so say which one and carry on.
            print(f"  skipped a {subset} block that had no family, weight or url")
            continue
        faces.append(
            Face(
                family=family.group(1),
                weight=weight.group(1),
                subset=subset,
                remote_url=url.group(1),
                block=block,
            )
        )
    return faces


def local_block(face: Face) -> str:
    """The same @font-face rule, pointing at the local file.

    Only the src url is rewritten. The unicode-range is left exactly as Google
    wrote it, because that is what makes a browser fetch the latin-ext file
    only when a page actually needs a character from it.
    """
    return URL_RE.sub(f"url(/static/fonts/{face.filename})", face.block, count=1)


def main() -> int:
    print("Asking Google Fonts for the stylesheet ...")
    try:
        stylesheet = fetch(CSS_URL).decode("utf-8")
    except urllib.error.URLError as error:
        print(f"Could not reach Google Fonts: {error}")
        print("Run this script on a machine that can, and carry web/fonts across.")
        return 1

    faces = read_faces(stylesheet)
    if not faces:
        print("The stylesheet came back with no latin or latin-ext font files in it.")
        print("Nothing was saved.")
        return 1

    FONT_DIR.mkdir(parents=True, exist_ok=True)

    saved = 0
    total_bytes = 0
    written: list[Face] = []
    for face in faces:
        try:
            data = fetch(face.remote_url)
        except urllib.error.URLError as error:
            print(f"  failed  {face.filename}: {error}")
            continue
        (FONT_DIR / face.filename).write_bytes(data)
        written.append(face)
        saved += 1
        total_bytes += len(data)
        print(f"  saved   {face.filename}  {len(data) / 1024:.1f} KB")

    if saved == 0:
        # WHY exit with an error: a run that saved nothing must not be able to
        # look like a run that worked. Ripple would then load a fonts.css
        # naming sixteen files that are not there.
        print("No font files were saved.")
        return 1

    rules = "\n\n".join(f"/* {face.subset} */\n{local_block(face)}" for face in written)
    header = (
        "/* Written by getfonts.py. Do not edit by hand.\n"
        "   Public Sans and IBM Plex Mono, SIL Open Font License.\n"
        "   Every src points at a local file, so Ripple needs no network. */\n\n"
    )
    (FONT_DIR / "fonts.css").write_text(header + rules + "\n", encoding="utf-8")

    print("")
    print(f"{saved} font files, {total_bytes / 1024:.0f} KB in total.")
    print(f"Written to {FONT_DIR}")
    print("Also written: fonts.css, which index.html loads as /static/fonts/fonts.css")
    return 0


if __name__ == "__main__":
    sys.exit(main())
