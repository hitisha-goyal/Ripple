"""Stopping the program when nobody is looking at it any more.

The built program opens without a console window, on purpose: a black box
sitting beside the browser looks like something went wrong. The cost of that is
there is no Ctrl-C and no window to close. Closing the browser tab does nothing
at all -- the server goes on running, invisible, holding its own folder open. So
the folder cannot be deleted, the port stays taken, a second copy starts on a
different port, and the only way out is Task Manager, which nobody should need
to know about to close a program.

This module is the way out. The page says "still here" every few seconds; when
it stops saying so, Ripple stops. There is also a button that stops it now.

Two things this has to get right, because both are ways to lose somebody's work:

* A refresh, or moving between screens, briefly has no page. That is why a page
  saying goodbye only shortens the deadline rather than stopping immediately --
  the new page arrives well inside that window and cancels it.
* A tab left open in the background is still somebody using Ripple. Browsers
  throttle timers in hidden tabs to about one a minute, so the quiet limit is
  minutes rather than seconds.

Everything here is decided by ``verdict()``, which is given the time rather than
reading the clock, so the whole of it can be tested without waiting.
"""
from __future__ import annotations

import os
import threading
import time
from typing import Any

# How often the page says it is still there. Also in web/offline.js -- if these
# two ever disagree, the smaller one is the one that matters.
BEAT_SECONDS = 10

# No word from any page for this long, so nobody is looking. Generous on
# purpose: a hidden tab may only manage one beat a minute.
QUIET_LIMIT = 300.0

# A page said it was going. Long enough for a refresh or a new tab to arrive
# and cancel it, short enough that closing the browser really does close Ripple.
LEAVING_GRACE = 12.0

# Nothing has ever said hello. The browser may still be starting, or may have
# failed to open at all -- and in that second case a program nobody can see is
# exactly what should not be left running.
STARTUP_GRACE = 600.0

_lock = threading.Lock()
_state: dict[str, Any] = {
    "server": None,      # the uvicorn Server, once it exists
    "started": None,     # when the watch began
    "last_beat": None,   # when a page last said it was there
    "leaving_at": None,  # when a page said it was going
    "stopping": False,   # a decision has been taken; do not take it twice
}


def reset(now: float | None = None) -> None:
    """Start again from nothing. Used at startup, and by the tests."""
    with _lock:
        _state.update({"server": None, "started": now if now is not None else time.time(),
                       "last_beat": None, "leaving_at": None, "stopping": False})


def attach(server: Any) -> None:
    """Remember the running server, so it can be asked to stop politely."""
    with _lock:
        _state["server"] = server


def beat(now: float | None = None) -> None:
    """A page is open and looking at Ripple."""
    with _lock:
        _state["last_beat"] = now if now is not None else time.time()
        # Whatever was leaving, something is here now.
        _state["leaving_at"] = None


def leaving(now: float | None = None) -> None:
    """A page said it was going away.

    Not a reason to stop on its own -- a refresh sends exactly this and then a
    new page appears a moment later. It starts the short clock instead.
    """
    with _lock:
        if _state["leaving_at"] is None:
            _state["leaving_at"] = now if now is not None else time.time()


def verdict(now: float) -> str:
    """'run', or why it is time to stop. Given the time; never reads the clock."""
    with _lock:
        if _state["stopping"]:
            return "stopping"
        started = _state["started"] or now
        last = _state["last_beat"]
        going = _state["leaving_at"]
    if going is not None and now - going >= LEAVING_GRACE:
        return "the browser was closed"
    if last is None:
        if now - started >= STARTUP_GRACE:
            return "no browser ever opened Ripple"
        return "run"
    if now - last >= QUIET_LIMIT:
        return "the browser has been gone for a while"
    return "run"


def stop(reason: str = "asked to close") -> str:
    """Bring the program down. Safe to call twice; the second call does nothing."""
    with _lock:
        if _state["stopping"]:
            return "already stopping"
        _state["stopping"] = True
        server = _state["server"]
    if server is not None:
        # Uvicorn's own way out: it finishes the request in hand, closes the
        # socket and returns from run(), so the process ends normally and lets
        # go of the folder. _exit would leave the reply half-written.
        server.should_exit = True
    else:
        # No server to ask -- running under a test, or something went wrong
        # early. Nothing to do; the caller decides.
        return reason
    return reason


def stopping() -> bool:
    with _lock:
        return bool(_state["stopping"])


def watch(interval: float = 2.0) -> threading.Thread:
    """Check every couple of seconds whether anybody is still there."""

    def loop() -> None:
        while True:
            time.sleep(interval)
            why = verdict(time.time())
            if why in ("run", "stopping"):
                continue
            stop(why)
            # Uvicorn returns from run() shortly after should_exit is set. If it
            # has not gone in a few seconds something is holding it, and leaving
            # an invisible program running is the failure this whole module
            # exists to prevent -- so it is ended the blunt way instead.
            time.sleep(8)
            os._exit(0)

    thread = threading.Thread(target=loop, name="ripple-lifecycle", daemon=True)
    thread.start()
    return thread


def facts(now: float | None = None) -> dict:
    """What the screen is told, so it can say this plainly rather than imply it."""
    now = now if now is not None else time.time()
    with _lock:
        last = _state["last_beat"]
    return {
        "beatSeconds": BEAT_SECONDS,
        "quietLimit": int(QUIET_LIMIT),
        "secondsSinceBeat": None if last is None else int(now - last),
        "stopping": stopping(),
    }
