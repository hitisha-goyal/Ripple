"""This machine's own "choose a folder" window.

A browser cannot hand a web page the real path of a folder — that is a security
rule, not an oversight — and a real path is exactly what the scanner needs. But
Ripple Offline is not really a website: it is a program running on the same
machine as the browser looking at it. So the window it opens is this machine's
own folder picker, and the path comes back the normal way.

Typing or pasting a path always works and is never taken away. This only saves
the typing, and when there is no picker to open the screen does not offer the
button at all — a button that does nothing is worse than no button.
"""
from __future__ import annotations


def available() -> bool:
    """Can this machine open a folder picker at all?"""
    try:
        import tkinter                       # noqa: F401
        from tkinter import filedialog       # noqa: F401
    except Exception:
        return False
    return True


def choose_folder(title: str = "Choose the repository folder to scan") -> str:
    """Open the picker and return what was chosen, or "" if it was cancelled."""
    try:
        import tkinter
        from tkinter import filedialog
    except Exception:
        return ""
    root = None
    try:
        root = tkinter.Tk()
        root.withdraw()
        # Otherwise the window opens behind the browser and looks like a hang.
        root.attributes("-topmost", True)
        root.update()
        chosen = filedialog.askdirectory(title=title, mustexist=True, parent=root)
        return str(chosen or "")
    except Exception:
        # A machine with no desktop session, or a locked-down one. Typing the
        # path still works, so this is a shrug rather than a failure.
        return ""
    finally:
        if root is not None:
            try:
                root.destroy()
            except Exception:
                pass
