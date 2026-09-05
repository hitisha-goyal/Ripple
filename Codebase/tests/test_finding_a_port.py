"""Ripple has to find a port it can really use, and say the right thing if it cannot.

It used to listen on 8000, full stop. It printed "open http://localhost:8000",
opened the browser, and only then asked the machine for the port. On a managed
work laptop on 27 Aug 2026 Windows refused it -- WinError 10013, which means the
port is RESERVED by the machine, not occupied by a program -- so the browser was
already sitting on a dead address before anything knew the start had failed.

Two things are guarded here.

The search has to BIND. Asking whether something is listening on a port answers
a different question from whether this machine will let you have it, and the
whole failure was the gap between those two.

And the message has to tell the two causes apart. "They are all in use, close
whatever is using them" is confident, actionable and wrong when the real cause is
a Windows reservation: nothing is holding the port, so there is nothing to close.
Ripple does not get to give an answer like that.
"""
from __future__ import annotations

import errno
import socket
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import run as runner                                             # noqa: E402


def test_it_takes_a_port_it_can_actually_bind():
    port, _ = runner.take_a_port()
    assert port > 0
    # Proof it is real: bind it again now that the probe has let go.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", port))


def test_it_steps_over_a_port_something_else_is_holding():
    """The ordinary case, with a real socket rather than a pretend one."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as held:
        held.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
        try:
            held.bind(("127.0.0.1", runner.FIRST_PORT))
        except OSError:
            pytest.skip(f"port {runner.FIRST_PORT} is not available to hold on this machine")
        held.listen(1)
        port, _ = runner.take_a_port()
        assert port != runner.FIRST_PORT, "it handed back a port already being held"


def _refuse(codes: dict[int, int]):
    """A socket that refuses the given ports with the given error numbers."""
    real = socket.socket

    class Fake(real):                                            # noqa: D401
        def bind(self, address):
            code = codes.get(address[1])
            if code is not None:
                raise OSError(code, "refused by this test")
            return super().bind(address)

    return Fake


def test_a_port_windows_reserves_is_stepped_over_like_a_busy_one(monkeypatch):
    """WinError 10013 is not "in use" and not a crash. It is one more port to skip.

    Nothing is listening on a reserved port, so every check that asks "is anyone
    there" says it is free. Only binding finds out.
    """
    reserved = {p: runner._WSAEACCES for p in range(runner.FIRST_PORT, runner.FIRST_PORT + 5)}
    monkeypatch.setattr(socket, "socket", _refuse(reserved))
    port, refused = runner.take_a_port()
    assert port not in reserved, "it handed back a port Windows had reserved"
    assert len(refused) >= 5, f"it did not record what it stepped over: {refused}"


def test_when_every_port_is_reserved_it_does_not_blame_other_programs(monkeypatch):
    """The one that matters. Telling somebody to close whatever is using the
    port, when nothing is, sends them looking for a program that is not there."""
    every = {p: runner._WSAEACCES for p in list(range(runner.FIRST_PORT, runner.LAST_PORT + 1)) + [0]}
    monkeypatch.setattr(socket, "socket", _refuse(every))
    with pytest.raises(OSError) as caught:
        runner.take_a_port()
    said = str(caught.value)
    assert "RESERVED" in said, "it never says the ports are reserved rather than busy"
    assert "closing things will not free them" in said, (
        "it does not tell somebody that closing programs is not the fix"
    )
    assert "in use by something else" not in said, (
        "it blamed another program for a port nothing is holding"
    )
    assert "set PORT=" in said, "it gives no way out"
    assert "excludedportrange" in said, "it does not say how to see the reserved ranges"


def test_when_every_port_is_busy_it_says_so_and_not_the_other_thing(monkeypatch):
    """And the opposite mistake: calling a genuinely occupied port reserved."""
    every = {p: errno.EADDRINUSE for p in list(range(runner.FIRST_PORT, runner.LAST_PORT + 1)) + [0]}
    monkeypatch.setattr(socket, "socket", _refuse(every))
    with pytest.raises(OSError) as caught:
        runner.take_a_port()
    said = str(caught.value)
    assert "in use by something else" in said, "it does not say the ports are busy"
    assert "RESERVED" not in said, "it called a busy port reserved"


def test_a_port_somebody_typed_is_never_quietly_stepped_over(monkeypatch):
    """Searching past a PORT somebody set starts Ripple somewhere they did not
    ask for, and the printed address is then the only clue anything happened."""
    monkeypatch.setenv("PORT", str(runner.FIRST_PORT))
    monkeypatch.setattr(socket, "socket", _refuse({runner.FIRST_PORT: runner._WSAEACCES}))
    with pytest.raises(OSError) as caught:
        runner.chosen_port()
    said = str(caught.value)
    assert str(runner.FIRST_PORT) in said, "it does not say which port it was asked for"
    assert "reserved" in said.lower(), "it does not say why that port could not be used"


def test_nothing_is_announced_before_the_port_is_secured():
    """The browser opened on a dead address because the address was printed, and
    the browser opened, before anything had asked for the port. Whatever else
    main() does, it must take the port first."""
    body = (Path(runner.__file__)).read_text(encoding="utf-8")
    inside = body.split("def main(", 1)[1]
    assert "chosen_port()" in inside, (
        "main() no longer asks for a port before starting. It is back to naming "
        "one and hoping, which is what put a browser on a dead address."
    )
    took = inside.index("chosen_port()")
    for announced in ("open http://localhost", "webbrowser.open"):
        assert announced in inside, f"main() no longer does `{announced}` at all"
        assert inside.index(announced) > took, (
            f"main() does `{announced}` before it has a port. That is how somebody "
            f"ends up looking at a browser tab that will never load."
        )
