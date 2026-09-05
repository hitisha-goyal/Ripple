"""What Ripple is doing right now, so a screen can say so while it waits.

On a repository the size of the one this was built for -- a couple of thousand
files, single statements six hundred lines long -- reading takes minutes and a
scan takes about a minute. A screen that says nothing for that long looks
broken, and the honest answer to "is it still going?" is a number that is
actually going up.

Two rules this file keeps, and they are the whole reason it is this small:

* Every number here is counted, never estimated. ``done`` is files that have
  really been read. Nothing is smoothed, nothing is extrapolated, and nothing
  moves on a timer.
* ``total`` is zero when there genuinely is no total. Following a chain looks at
  as many statements as it turns out to need, so there is no denominator, and
  inventing one to fill a progress bar would be inventing the one number on the
  screen nobody could check.
"""
from __future__ import annotations

_state: dict = {"job": "", "label": "", "done": 0, "total": 0}


def start(job: str, label: str = "") -> None:
    _replace({"job": job, "label": label, "done": 0, "total": 0})


def step(done: int, total: int, label: str = "") -> None:
    _replace({"job": _state.get("job", ""), "label": label or _state.get("label", ""),
              "done": done, "total": total})


def finish() -> None:
    _replace({"job": "", "label": "", "done": 0, "total": 0})


def snapshot() -> dict:
    """What to show. A copy, so a read cannot catch a half-written update."""
    now = _state
    return {
        "job": now.get("job", ""),
        "label": now.get("label", ""),
        "done": now.get("done", 0),
        # Zero means "not known", and the screen says so rather than drawing a bar.
        "total": now.get("total", 0),
    }


def _replace(new: dict) -> None:
    # Swapped whole rather than edited in place: another request can be reading
    # this at any moment, and half of one update and half of the next would put
    # a number on screen that was never true.
    global _state
    _state = new


def reader(job: str):
    """A callback to hand to the engine, and the job name it reports under."""
    start(job)

    def on_progress(done: int, total: int, label: str = "") -> None:
        step(done, total, label)

    return on_progress
