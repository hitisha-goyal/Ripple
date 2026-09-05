"""Start Ripple on this machine.

    python run.py

It finds a port it can actually use, prints the address, and opens your browser.
Nothing else to install or set up.

WHY THERE IS A PORT SEARCH HERE AT ALL. This used to be one line: listen on 8000.
It printed "open http://localhost:8000", opened the browser, and only then asked
Windows for the port. On a managed work laptop, 27 Aug 2026, Windows refused it
-- WinError 10013, a port reserved by the machine rather than used by a program
-- so the browser was already sitting on a dead address before anything knew the
start had failed. Announce nothing until the door is actually open.
"""
from __future__ import annotations

import errno
import os
import socket
import sys
import webbrowser

import uvicorn

from ripple.config import settings

FIRST_PORT = 8000
LAST_PORT = 8020

# Windows says this when a port is reserved rather than occupied -- Hyper-V, WSL
# and Docker each reserve whole ranges, and a work laptop often has several. The
# two need different advice: nothing is holding the port, so closing programs
# cannot free it, and "they are all in use" would send somebody hunting for a
# program that does not exist.
_WSAEACCES = 10013


def take_a_port() -> tuple[int, list[tuple[int, int]]]:
    """The first port this machine will actually let Ripple listen on.

    Binding is the only honest test. Asking whether anything is listening says
    nothing about whether Windows will allow the bind, which is exactly the case
    that failed.

    Returns the port, and what went wrong on the ones that did not work, so the
    message afterwards can tell "in use" and "reserved" apart.
    """
    refused: list[tuple[int, int]] = []
    for port in list(range(FIRST_PORT, LAST_PORT + 1)) + [0]:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
            try:
                probe.bind(("127.0.0.1", port))
            except OSError as e:
                refused.append((port, e.errno or 0))
                continue
            # port 0 means "any free one" -- ask which one that turned out to be
            return probe.getsockname()[1], refused
    raise OSError(_no_port_message(refused))


def _no_port_message(refused: list[tuple[int, int]]) -> str:
    """Say which of the two problems this is, because the fixes differ."""
    reserved = any(code in (_WSAEACCES, errno.EACCES) for _, code in refused)
    lines = [
        "",
        "  Ripple could not open a door for your browser to talk to.",
        "",
    ]
    if reserved:
        lines += [
            f"  Ports {FIRST_PORT} to {LAST_PORT} were all refused by Windows itself.",
            "  That means they are RESERVED on this machine, not in use by a program,",
            "  so closing things will not free them. It is common on a work laptop.",
            "",
            "  Pick a port outside the reserved range and tell Ripple to use it:",
            "",
            "      set PORT=8850",
            "      python run.py",
            "",
            "  To see which ranges Windows has reserved:",
            "",
            "      netsh interface ipv4 show excludedportrange protocol=tcp",
        ]
    else:
        lines += [
            f"  Ports {FIRST_PORT} to {LAST_PORT} are all in use by something else on",
            "  this machine. Close whatever is using them, or choose another:",
            "",
            "      set PORT=8850",
            "      python run.py",
        ]
    return "\n".join(lines + [""])


def chosen_port() -> tuple[int, list[tuple[int, int]]]:
    """PORT if somebody set it, otherwise whichever one this machine allows.

    A PORT somebody typed is never quietly stepped over. Searching past it would
    start Ripple somewhere they did not ask for and never say why.
    """
    asked = os.environ.get("PORT")
    if not asked:
        return take_a_port()
    port = int(asked)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
        try:
            probe.bind(("127.0.0.1", port))
        except OSError as e:
            code = e.errno or 0
            why = ("Windows has that port reserved on this machine"
                   if code in (_WSAEACCES, errno.EACCES)
                   else "something else on this machine is already using it")
            raise OSError(
                f"\n  PORT is set to {port}, and Ripple cannot listen there:\n"
                f"  {why}.\n\n"
                f"  Set PORT to a different number, or clear it and let Ripple\n"
                f"  find one for itself.\n"
            ) from None
    return port, []


def main() -> int:
    try:
        port, _ = chosen_port()
    except OSError as e:
        print(e)
        return 1

    print("\n  Ripple")
    print(f"  repository : {settings.repo_path}")
    print(f"  SQL read as: {settings.sql_dialect or 'generic'}")
    print(f"  AI         : {'on (' + (settings.ai_model or 'model chosen on connect') + ')' if settings.ai_available() else 'off - rules only'}")
    if not settings.repo_path.exists():
        print(f"\n  WARNING: the repository folder does not exist: {settings.repo_path}")
    print(f"\n  open http://localhost:{port}\n")
    if "--no-browser" not in sys.argv:
        try:
            webbrowser.open(f"http://localhost:{port}")
        except Exception:
            pass
    uvicorn.run("ripple.api:app", host="127.0.0.1", port=port, reload="--reload" in sys.argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
