"""What the engine is doing this second.

The page asks this while it waits. Reading a real repository takes minutes and
a scan about a minute, and a spinner with one fixed sentence for that long is
indistinguishable from a program that has hung.

Nothing in here invents a number. "done" is what a scanner said it had really
finished, "total" is a denominator a scanner really knew, and where a scanner
cannot know one - a chain looks at as many statements as it turns out to need -
it stays 0 so the page prints a count and no fraction. A fraction would need a
denominator nobody could check.

The three job names - "reading", "parsing", "scanning" - are a contract with the
page, which is built in another window and turns each one into a sentence. A
fourth name would leave the page showing the single word "Working" for the whole
wait, so api.py passes only those three.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Callable


@dataclass(frozen=True)
class _Job:
    """One slow call, exactly as the page is allowed to see it."""

    job: str = ""
    label: str = ""
    done: int = 0
    total: int = 0


# The web service answers /api/progress on one worker thread while a scan runs on
# another, so every read and every write of the current job goes through this
# lock. Without it the page can catch a half-written job - a new name against the
# previous count - and print a number that was never true.
_lock = Lock()
_current = _Job()


def _count(value: object) -> int:
    """A number the page can print, or 0.

    A scanner that hands over None for the total means "there is no denominator
    here". That has to arrive as 0, not as an exception thrown inside a callback
    nobody is watching, which would take the whole scan down over a display
    detail.
    """
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0
    return number if number > 0 else 0


def reader(job: str) -> Callable[..., None]:
    """Return the on_progress(done, total, label) callback the scanners expect.

    Asking for the callback is itself the start of the job, so the page has
    something to show between the call starting and the first count arriving.
    """
    name = str(job or "")

    global _current
    with _lock:
        _current = _Job(job=name)

    def on_progress(done: int, total: int = 0, label: str = "") -> None:
        global _current
        with _lock:
            if _current.job != name:
                # A callback that arrives after finish(), or after the next job
                # has taken over, must not put a finished job back on the screen
                # and leave the line counting for ever.
                return
            _current = _Job(
                job=name,
                # A call that passes no label keeps the last one rather than
                # blanking the sentence the reader is halfway through.
                label=str(label) if label else _current.label,
                done=_count(done),
                total=_count(total),
            )

    return on_progress


def finish() -> None:
    """Nothing is happening now.

    job goes back to an empty string, which is what makes the line disappear on
    its own instead of sticking at a number for ever. api.py calls this in a
    finally, so a scan that FAILS clears the line too.
    """
    global _current
    with _lock:
        _current = _Job()


def snapshot() -> dict[str, object]:
    """The current state, as the /api/progress route sends it."""
    with _lock:
        now = _current
    return {"job": now.job, "label": now.label, "done": now.done, "total": now.total}
