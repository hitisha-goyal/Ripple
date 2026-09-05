"""Knowing when to stop.

The built program has no console window and no window of its own. Closing the
browser left it running where nobody could see it, holding its own folder open —
so the folder could not be deleted, the port stayed taken, and the only way out
was Task Manager. Reported from a real machine, and reproduced on this one: a
Ripple Offline process was still holding port 8000 long after everything that
started it had been closed.

Every decision here is made by ``verdict(now)``, which is handed the time, so
all of this runs instantly instead of sleeping through it.
"""
from __future__ import annotations

import pytest

from ripple_offline import lifecycle


@pytest.fixture(autouse=True)
def fresh():
    lifecycle.reset(now=1000.0)
    yield
    lifecycle.reset(now=1000.0)


def test_it_keeps_running_while_a_page_is_saying_it_is_there():
    lifecycle.beat(now=1000.0)
    assert lifecycle.verdict(1000.0) == "run"
    assert lifecycle.verdict(1000.0 + lifecycle.QUIET_LIMIT - 1) == "run"


def test_a_tab_left_open_in_the_background_is_not_treated_as_gone():
    """Browsers throttle a hidden tab to roughly one timer a minute. Being
    throttled must never look like being closed."""
    now = 1000.0
    for _ in range(5):
        now += 60.0                      # one beat a minute, the throttled case
        lifecycle.beat(now=now)
        assert lifecycle.verdict(now) == "run"
    assert lifecycle.QUIET_LIMIT > 60.0 * 2, "one slow beat must not be enough to stop"


def test_it_stops_once_no_page_has_spoken_for_a_long_time():
    lifecycle.beat(now=1000.0)
    assert lifecycle.verdict(1000.0 + lifecycle.QUIET_LIMIT) != "run"


def test_closing_the_browser_stops_it_shortly_afterwards():
    lifecycle.beat(now=1000.0)
    lifecycle.leaving(now=1001.0)
    assert lifecycle.verdict(1001.0) == "run", "not instantly — a refresh sends this too"
    why = lifecycle.verdict(1001.0 + lifecycle.LEAVING_GRACE)
    assert why != "run"
    assert "browser" in why


def test_a_refresh_does_not_stop_it():
    """A refresh sends exactly the same goodbye, then the new page arrives a
    moment later. Stopping on the goodbye alone would close Ripple every time
    somebody pressed F5."""
    lifecycle.beat(now=1000.0)
    lifecycle.leaving(now=1001.0)
    lifecycle.beat(now=1002.0)           # the new page
    assert lifecycle.verdict(1001.0 + lifecycle.LEAVING_GRACE) == "run"
    assert lifecycle.verdict(1100.0) == "run"


def test_a_second_tab_keeps_it_alive_when_the_first_one_closes():
    lifecycle.beat(now=1000.0)           # two tabs, both beating
    lifecycle.leaving(now=1005.0)        # one of them is closed
    lifecycle.beat(now=1006.0)           # the other one is still there
    assert lifecycle.verdict(1005.0 + lifecycle.LEAVING_GRACE) == "run"


def test_it_gives_the_browser_a_long_time_to_open_in_the_first_place():
    """A slow machine takes a while to open a browser. Stopping before it
    arrives would mean double-clicking the program and getting nothing."""
    assert lifecycle.verdict(1000.0 + 60.0) == "run"
    assert lifecycle.verdict(1000.0 + lifecycle.STARTUP_GRACE - 1) == "run"


def test_it_does_not_sit_there_for_ever_if_no_browser_ever_opens():
    why = lifecycle.verdict(1000.0 + lifecycle.STARTUP_GRACE)
    assert why != "run"
    assert "browser" in why


def test_the_button_stops_it_and_says_so_only_once():
    class FakeServer:
        should_exit = False

    server = FakeServer()
    lifecycle.attach(server)
    assert lifecycle.stopping() is False
    lifecycle.stop("closed from the screen")
    assert server.should_exit is True
    assert lifecycle.stopping() is True
    assert lifecycle.stop("again") == "already stopping"


def test_once_stopping_nothing_starts_it_again():
    class FakeServer:
        should_exit = False

    lifecycle.attach(FakeServer())
    lifecycle.stop()
    lifecycle.beat(now=2000.0)
    assert lifecycle.verdict(2000.0) == "stopping"


def test_the_page_beats_far_more_often_than_the_quiet_limit():
    """If these ever cross, a working tab would be treated as a closed one."""
    assert lifecycle.BEAT_SECONDS * 6 <= lifecycle.QUIET_LIMIT
