"""Start Ripple Offline.

    python run.py

The built executable runs this same code, so what is tested here is what ships.
There is nothing to install and nothing to configure first: the browser opens,
and if no repository folder has been chosen yet the first screen asks for one.
"""
from __future__ import annotations

import socket
import sys
import traceback
import webbrowser
from pathlib import Path

# Blocking the network is the first thing that happens, before any other part
# of Ripple is imported -- so anything that reaches out at import time is
# caught too, not just anything that reaches out during a request.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ripple_offline import nonet                                    # noqa: E402

nonet.install()

from ripple_offline import paths, prefs                             # noqa: E402
from ripple_offline.engine import frozen                            # noqa: E402

FIRST_PORT = 8000
LAST_PORT = 8020


def log_path() -> Path:
    return paths.app_dir() / "ripple-log.txt"


class _Nowhere:
    """Somewhere for writes to go when there is genuinely nowhere to put them."""

    def write(self, _text: str) -> int:
        return 0

    def flush(self) -> None:
        pass

    def isatty(self) -> bool:
        return False


def start_logging() -> None:
    """With no terminal there is nowhere for a message to go, so make one.

    The built executable opens without a console window on purpose -- a black
    box beside the browser looks like something went wrong. That leaves nothing
    to print to, so everything goes to a file beside the program instead, which
    is also the thing to ask for when someone says it did not start.

    A locked-down machine may not let the program write beside itself: a folder
    under Program Files, or a network share somebody opened it from. Failing to
    open a log file must never be the reason the program does not start, so it
    falls back to the temporary folder, and then to nowhere at all.
    """
    if not frozen():
        return
    import tempfile

    for candidate in (log_path(), Path(tempfile.gettempdir()) / "ripple-log.txt"):
        try:
            handle = open(candidate, "a", encoding="utf-8", buffering=1)
        except OSError:
            continue
        sys.stdout = handle
        sys.stderr = handle
        return
    # Nothing writable anywhere. Carry on silently rather than not starting --
    # but never leave these as None, which some logging setups will fall over on.
    sys.stdout = _Nowhere()
    sys.stderr = _Nowhere()


# Windows says this when a port is RESERVED rather than occupied. Hyper-V, WSL
# and Docker each reserve whole ranges, and a managed work laptop often has
# several. Nothing is listening on such a port, so telling somebody to close
# whatever is using it sends them hunting for a program that does not exist.
_WSAEACCES = 10013


def free_port() -> int:
    """The first port this machine will actually let Ripple listen on.

    A fixed port is fine until the day something else on the machine has it,
    and then Ripple simply fails to start with no explanation anyone can act on.

    Binding is the only honest test. Whether anything is LISTENING on a port is
    a different question from whether this machine will allow the bind, and on
    27 Aug 2026 a work laptop refused 8000 with nothing listening on it at all.
    """
    refused: list[int] = []
    for port in list(range(FIRST_PORT, LAST_PORT + 1)) + [0]:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
            try:
                probe.bind(("127.0.0.1", port))
            except OSError as e:
                refused.append(e.errno or 0)
                continue
            # port 0 means "any free one" -- ask which it turned out to be
            return probe.getsockname()[1]
    if any(code == _WSAEACCES for code in refused):
        raise RuntimeError(
            f"Ports {FIRST_PORT} to {LAST_PORT} were all refused by Windows itself, so "
            f"Ripple has nowhere to listen. They are RESERVED on this machine rather "
            f"than in use by a program, which is common on a work laptop - closing "
            f"things will not free them. Somebody who can run commands on this machine "
            f"can see the reserved ranges with:\n\n"
            f"    netsh interface ipv4 show excludedportrange protocol=tcp")
    raise RuntimeError(
        f"Ports {FIRST_PORT} to {LAST_PORT} are all in use on this machine, so Ripple "
        f"has nowhere to listen. Close whatever is using them and start Ripple again.")


def show_failure(message: str) -> None:
    """Say so on screen when there is no terminal to say it in."""
    print(message)
    if not frozen():
        return
    try:
        import tkinter
        from tkinter import messagebox
        root = tkinter.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        messagebox.showerror("Ripple could not start", message)
        root.destroy()
    except Exception:
        pass


def main() -> int:
    start_logging()
    try:
        values = prefs.load()
        prefs.apply(values)

        if not frozen():
            # Running from source, the offline front end is rebuilt from the
            # shared one every time, so it can never be a stale copy.
            from ripple_offline import webbuild
            webbuild.build()

        from ripple_offline.app import app

        port = free_port()
        folder = prefs.check_folder(values["repoPath"])
        print("\n  Ripple Offline")
        print(f"  repository : {values['repoPath'] or '(not chosen yet)'}")
        print(f"  folder     : {folder['message']}")
        print(f"  SQL read as: {values['sqlDialect'] or 'generic'}")
        print(f"  settings   : {paths.settings_file()}")
        print(f"  history    : {paths.history_file()}")
        print("  network    : blocked - loopback only")
        print(f"\n  open http://localhost:{port}\n")

        if "--no-browser" not in sys.argv:
            try:
                webbrowser.open(f"http://localhost:{port}")
            except Exception:
                pass

        # Built as a windowed program, this has no console: no Ctrl-C, and no
        # window to close. Closing the browser used to leave it running where
        # nobody could see it, holding its own folder open so the folder could
        # not be deleted. The open page now says it is there every few seconds,
        # and when it stops saying so, this stops.
        import uvicorn
        from ripple_offline import lifecycle

        lifecycle.reset()
        config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
        server = uvicorn.Server(config)
        lifecycle.attach(server)
        lifecycle.watch()
        server.run()
        print("\n  Ripple has stopped. You can close the browser tab.\n")
        return 0
    except SystemExit:
        raise
    except Exception as exc:
        detail = f"{exc}\n\nThe full details are in:\n{log_path()}"
        print(traceback.format_exc())
        show_failure(detail)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
