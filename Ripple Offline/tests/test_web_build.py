"""Building the offline front end out of the online one.

The offline screens are not a second copy of the online ones — they are made
from them, with the parts that reach out deleted. These tests hold the build to
two promises: what comes out really is free of those parts, and if the markers
that say which parts are ever lost, the build stops instead of quietly shipping
a key box onto a locked-down machine.
"""
from __future__ import annotations

import shutil
import subprocess

import pytest

from ripple_offline import webbuild
from ripple_offline.engine import SHARED_WEB


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    return webbuild.build(out_dir=tmp_path_factory.mktemp("web"))


def test_the_front_end_is_built(built):
    for name in ("index.html", "app.js", "styles.css"):
        assert (built / name).is_file()
    assert (built / "fonts").is_dir()


def test_the_fonts_come_with_it(built):
    """Bundled on purpose: a font loaded from the internet is a blank page on a
    machine that has none."""
    woff2 = list((built / "fonts").glob("*.woff2"))
    assert len(woff2) > 8


@pytest.mark.parametrize("word", webbuild.BANNED)
def test_nothing_that_reaches_out_survives(built, word):
    for name in ("app.js", "index.html"):
        assert word not in (built / name).read_text(encoding="utf-8").lower(), \
            f"{name} still mentions {word}"


@pytest.mark.parametrize("name", webbuild.REMOVED)
def test_the_forms_that_reach_out_are_gone(built, name):
    """Gone, not merely unused: the GitHub connect form and the AI key form are
    not in the file at all."""
    assert f"function {name}" not in (built / "app.js").read_text(encoding="utf-8")


@pytest.mark.parametrize("name", webbuild.REPLACED)
def test_the_screens_that_differ_are_replaced_exactly_once(built, name):
    text = (built / "app.js").read_text(encoding="utf-8")
    assert text.count(f"function {name}") == 1


def test_there_is_no_source_switch_on_the_repository_screen(built):
    html = (built / "index.html").read_text(encoding="utf-8")
    assert "data-src" not in html
    assert "This machine" not in html


def test_no_box_asks_for_a_secret(built):
    """The plainest version of the promise: nothing on screen takes a key."""
    js = (built / "app.js").read_text(encoding="utf-8")
    assert "type: 'password'" not in js and 'type: "password"' not in js


def test_the_settings_screen_asks_for_the_two_things_that_matter(built):
    js = (built / "app.js").read_text(encoding="utf-8")
    assert "Repository folder" in js and "How the SQL is read" in js


def test_the_built_page_can_close_the_program(built):
    """Without this the only way to stop Ripple is Task Manager, and until it is
    stopped its own folder cannot be deleted. Both halves have to be in the page
    that actually ships: the repeating "still here", and the goodbye."""
    js = (built / "app.js").read_text(encoding="utf-8")
    assert "/api/alive" in js, "nothing tells the program a page is open"
    assert "/api/leaving" in js, "nothing tells it the tab was closed"
    assert "sendBeacon" in js, "a goodbye sent with fetch does not survive the tab closing"
    assert "/api/quit" in js and "Close Ripple" in js, "no visible way to stop it"


def test_the_page_says_which_edition_it_is(built):
    assert "Ripple Offline" in (built / "index.html").read_text(encoding="utf-8")


def test_the_built_script_is_valid_javascript(built):
    """A stripped block that left broken JavaScript would be a blank page, and
    a blank page is the one failure nobody can debug from a screenshot."""
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed on this machine")
    done = subprocess.run([node, "--check", str(built / "app.js")],
                          capture_output=True, text=True)
    assert done.returncode == 0, done.stderr


def test_the_shared_front_end_is_still_valid_javascript():
    """The markers are comments, so they must not change the online app at all."""
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed on this machine")
    done = subprocess.run([node, "--check", str(SHARED_WEB / "app.js")],
                          capture_output=True, text=True)
    assert done.returncode == 0, done.stderr


# ── the build must fail rather than ship something wrong ───────────────────
def test_a_marker_left_open_stops_the_build():
    with pytest.raises(webbuild.BuildError, match="never closed"):
        webbuild.strip_blocks("a\n//<online-only>\nb\n", webbuild.JS_START, webbuild.JS_END, "x.js")


def test_a_marker_closed_twice_stops_the_build():
    with pytest.raises(webbuild.BuildError, match="never opened"):
        webbuild.strip_blocks("//</online-only>\n", webbuild.JS_START, webbuild.JS_END, "x.js")


def test_a_shared_file_with_no_markers_at_all_stops_the_build(tmp_path):
    """If the markers were ever stripped out of the shared front end, building
    without them would ship every part that reaches out."""
    fake = tmp_path / "web"
    fake.mkdir()
    for name in ("app.js", "index.html", "styles.css"):
        shutil.copyfile(SHARED_WEB / name, fake / name)
    plain = (fake / "app.js").read_text(encoding="utf-8").replace(webbuild.JS_START, "//")
    (fake / "app.js").write_text(plain.replace(webbuild.JS_END, "//"), encoding="utf-8")
    with pytest.raises(webbuild.BuildError):
        webbuild.build(out_dir=tmp_path / "out", shared_web=fake)


def _copy_shared(tmp_path):
    fake = tmp_path / "web"
    fake.mkdir()
    for name in ("app.js", "index.html", "styles.css"):
        shutil.copyfile(SHARED_WEB / name, fake / name)
    return fake


def test_a_lost_marker_around_the_key_form_stops_the_build(tmp_path):
    """The real safeguard. Somebody edits the online front end, the markers
    around the AI key form go missing, and the build stops rather than shipping
    the form onto a locked-down machine."""
    fake = _copy_shared(tmp_path)
    lines = (SHARED_WEB / "app.js").read_text(encoding="utf-8").splitlines()
    # The marker pair that encloses aiCard, found by walking back from aiCard
    # rather than by looking a fixed number of lines forward from a marker.
    # Editing anything above it used to push aiCard out of that window, and the
    # test then failed for a reason that had nothing to do with the markers.
    at = next(i for i, l in enumerate(lines) if "function aiCard" in l)
    opens = max(i for i in range(at) if lines[i].strip() == webbuild.JS_START)
    closes = next(i for i in range(at, len(lines)) if lines[i].strip() == webbuild.JS_END)
    (fake / "app.js").write_text(
        "\n".join(l for i, l in enumerate(lines) if i not in (opens, closes)), encoding="utf-8")
    with pytest.raises(webbuild.BuildError, match="aiCard"):
        webbuild.build(out_dir=tmp_path / "out", shared_web=fake)


def test_something_new_that_reaches_out_stops_the_build(tmp_path):
    """And the backstop for anything the build does not know the name of: a way
    out added to shared code fails with the word and the line it found.

    The line is found by the function's name rather than by its whole signature.
    Adding one argument to runScan used to leave this test injecting nothing at
    all -- so it passed, while testing nothing, which is the worst way for a
    safeguard's own test to fail.
    """
    fake = _copy_shared(tmp_path)
    lines = (fake / "app.js").read_text(encoding="utf-8").splitlines()
    at = next(i for i, l in enumerate(lines) if l.startswith("function runScan("))
    lines.insert(at + 1, "  fetch('https://api.groq.com/ping');")
    (fake / "app.js").write_text("\n".join(lines), encoding="utf-8")
    with pytest.raises(webbuild.BuildError, match="groq"):
        webbuild.build(out_dir=tmp_path / "out", shared_web=fake)


def test_the_build_refuses_a_front_end_that_is_not_there(tmp_path):
    with pytest.raises(webbuild.BuildError, match="missing"):
        webbuild.build(out_dir=tmp_path / "out", shared_web=tmp_path / "nothing-here")


# ── a new provider must not be able to slip through ────────────────────────
# The online copy grew from one AI provider to three. Each one is a different
# company, a different address and a different key box, and every one of them
# has to be barred from a build whose whole promise is that it cannot reach
# anywhere. Adding a provider online and forgetting this list is exactly how a
# key box arrives on a locked-down laptop.
@pytest.mark.parametrize("leak", [
    "  fetch('https://api.openai.com/v1/models');",
    "  fetch('https://generativelanguage.googleapis.com/v1beta/openai/models');",
    "  fetch('https://api.groq.com/ping');",
    "  const label = 'Google Gemini';",
    "  const hint = 'Paste your API key';",
])
def test_no_provider_can_reach_the_offline_build(tmp_path, leak):
    fake = _copy_shared(tmp_path)
    lines = (fake / "app.js").read_text(encoding="utf-8").splitlines()
    at = next(i for i, l in enumerate(lines) if l.startswith("function runScan("))
    lines.insert(at + 1, leak)
    (fake / "app.js").write_text("\n".join(lines), encoding="utf-8")
    with pytest.raises(webbuild.BuildError):
        webbuild.build(out_dir=tmp_path / "out", shared_web=fake)


def test_the_real_build_carries_no_provider_at_all(built):
    """Not disabled, not behind a flag — absent. Checked on what is actually
    produced, not on what the ban list says it would catch."""
    js = (built / "app.js").read_text(encoding="utf-8").lower()
    for word in ("openai", "gemini", "groq", "googleapis", "aicard", "api key"):
        assert word not in js, word


def test_a_local_variable_that_shadows_a_shared_helper_stops_the_build(tmp_path,
                                                                       monkeypatch):
    """Found by hitting it. offline.js had a `const why = ...` inside one of its
    cards, and `why` is the name of the shared information button. A local const
    shadows the shared function for the whole surrounding function, so calling
    it there throws — and only here, on the copy nobody can check.

    The function-clash test above does not catch this: a local const is not a
    declaration, so the two files declare no name in common.
    """
    spoiled = webbuild.OFFLINE_JS.read_text(encoding="utf-8").replace(
        "function settingsView(root) {",
        "function settingsView(root) {\n  const why = el('div', {});", 1)
    fake = tmp_path / "offline.js"
    fake.write_text(spoiled, encoding="utf-8")
    monkeypatch.setattr(webbuild, "OFFLINE_JS", fake)
    with pytest.raises(webbuild.BuildError, match="local variable"):
        webbuild.build(out_dir=tmp_path / "out")


def test_the_information_button_is_in_the_offline_build(built):
    """It is the pattern every screen uses. If it were stripped out with the
    online-only parts, every card would say the fact and lose the explanation
    with nothing on screen to say so."""
    js = (built / "app.js").read_text(encoding="utf-8")
    assert js.count("\nfunction why(") == 1, "the information button is not in this build"
    assert "aria-expanded" in js and "aria-controls" in js
    css = (built / "styles.css").read_text(encoding="utf-8").replace(" ", "")
    assert "button.i{" in css, "the information button has no style rule here"
    # It must be used by the offline-only screens too, not only the shared ones.
    at = js.index("function settingsView(")
    assert "why(" in js[at:at + 4000], "the offline settings screen never uses it"
