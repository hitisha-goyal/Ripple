"""Start Ripple.

TAKE THE PORT BEFORE YOU ANNOUNCE IT. The obvious version of this file names
port 8000, prints "open http://localhost:8000", opens the browser and only then
hands the number to uvicorn. Measured on a managed work laptop on 27 August
2026: Windows refused 8000, and by the time anyone knew, the browser was already
sitting on an address that would never load. So this file binds first and prints
second, and reports the port it actually got rather than the one it hoped for.

It BINDS to test each candidate. Whether anything is listening on a port and
whether this machine will allow the bind are different questions, and the gap
between them is the bug: nothing was listening on 8000, and the machine still
would not allow it.
"""

from __future__ import annotations

import argparse
import errno
import os
import socket
import webbrowser

import uvicorn

from ripple import paths

# The app OBJECT, never the string "ripple.api:app". Both work while running from
# source. Only the object still works once this is packaged, because a packaged
# program has no importable module of that name to look up, and the string form
# exits immediately with "Could not import module".
from ripple.api import app

# config.py holds ONE settings object rather than handing out fresh ones, and it
# is the same object the web service reads, so the folder printed here is really
# the folder that will be scanned.
from ripple.config import settings

# 127.0.0.1 is this machine talking to itself and cannot be reached from outside
# it. 0.0.0.0 would offer an analysis of internal source code to everyone on the
# office network, on a port with no password on it. Tutorials are full of 0.0.0.0
# because they are written for containers. This is a laptop.
HOST = "127.0.0.1"

FIRST_PORT = 8000
LAST_PORT = 8020

# Windows reports a port RESERVED by the machine itself - Hyper-V, WSL and Docker
# each reserve whole ranges - as error 10013, which is a different problem from a
# port held by a program and has the opposite fix.
WINDOWS_RESERVED = 10013

RESERVED_COMMAND = "netsh interface ipv4 show excludedportrange protocol=tcp"


def _is_reserved(exc: OSError | None) -> bool:
    """Reserved by this machine rather than held by a program."""
    if exc is None:
        return False
    if getattr(exc, "winerror", None) == WINDOWS_RESERVED:
        return True
    # On Windows Python also maps that refusal onto EACCES. Elsewhere EACCES on a
    # port in this range means the same thing in practice: the machine will not
    # allow the bind and there is no program to close.
    return getattr(exc, "errno", None) == errno.EACCES


def _try_bind(port: int) -> tuple[bool, OSError | None]:
    """Really bind the port, then let it go.

    No SO_REUSEADDR is set. On Windows that flag lets a second program bind a
    port another one is already holding, which would make this test say yes to a
    port the first copy of Ripple is on - and both copies would print the same
    address.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind((HOST, port))
    except OSError as exc:
        return False, exc
    return True, None


def _bind_any() -> tuple[int, OSError | None]:
    """Port 0 means "any free one you like".

    This is what saves a machine where the whole range above is refused.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind((HOST, 0))
            return int(sock.getsockname()[1]), None
    except OSError as exc:
        return 0, exc


def _refusal(exc: OSError | None) -> str:
    """Which of the two problems this is, in words somebody can act on."""
    if _is_reserved(exc):
        return (
            "This machine has RESERVED that port (error 10013). Nothing is "
            "listening on it, so closing programs will not help. To see which "
            "ranges are reserved, run:\n    " + RESERVED_COMMAND
        )
    if exc is None:
        return "The machine would not allow it, and gave no reason."
    return "Another program is holding it: " + str(exc)


def _port_from_environment() -> int:
    """PORT was set, so use that one and no other.

    Quietly searching past a number somebody typed starts Ripple somewhere they
    did not ask for, and the printed address is the only clue it happened.
    """
    asked = os.environ.get("PORT", "").strip()
    try:
        wanted = int(asked)
    except ValueError:
        print("PORT is set to '" + asked + "', which is not a port number.")
        print("Unset it, or set it to a number, and start Ripple again.")
        raise SystemExit(2)
    taken, exc = _try_bind(wanted)
    if taken:
        return wanted
    print("PORT is set to " + str(wanted) + " and this machine will not allow it.")
    print(_refusal(exc))
    print(
        "Ripple will not quietly start on a different port, because the address "
        "printed here would be the only clue that it had. Unset PORT, or set it "
        "to a port this machine allows."
    )
    raise SystemExit(2)


def choose_port() -> int:
    """The port Ripple really has, bound before anything is printed."""
    if os.environ.get("PORT", "").strip():
        return _port_from_environment()

    refusals: list[OSError | None] = []
    for port in range(FIRST_PORT, LAST_PORT + 1):
        taken, exc = _try_bind(port)
        if taken:
            return port
        refusals.append(exc)

    port, exc = _bind_any()
    if port:
        return port
    refusals.append(exc)

    print(
        "None of the ports from "
        + str(FIRST_PORT)
        + " to "
        + str(LAST_PORT)
        + ", nor any port this machine would choose itself, could be used."
    )
    if any(_is_reserved(refusal) for refusal in refusals):
        print(
            "They are RESERVED by this machine (error 10013) rather than held by "
            "programs. There is nothing to close, so closing things will not "
            "help. To see which ranges are reserved, run:"
        )
        print("    " + RESERVED_COMMAND)
    else:
        print("They really are in use. Close whatever is on them and try again.")
    raise SystemExit(2)


def _running_packaged() -> bool:
    """A packaged copy carries its own Python and says so.

    paths.frozen() is the one place in Ripple that answers this. Asking the
    interpreter again here would be a second answer that could drift from the
    one every path is worked out from.
    """
    return paths.frozen()


def announce(port: int) -> str:
    """Print what Ripple will read, and the address it really has."""
    address = "http://" + HOST + ":" + str(port)
    print("Ripple")
    print("  Repository   " + str(settings.repo_path))
    print("  SQL dialect  " + str(settings.sql_dialect or "generic"))
    print("  Running      " + ("packaged" if _running_packaged() else "from source"))
    print("  Address      " + address)
    print("  Hold Ctrl and press C to stop.")
    return address


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Start Ripple and open it in a browser."
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="do not open a browser window",
    )
    args = parser.parse_args()

    port = choose_port()
    address = announce(port)
    if not args.no_browser:
        webbrowser.open(address)
    uvicorn.run(app, host=HOST, port=port)


if __name__ == "__main__":
    main()
