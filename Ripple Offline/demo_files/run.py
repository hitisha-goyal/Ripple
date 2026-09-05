"""Start Ripple.

    python run.py

Nothing to install and nothing to configure first: the browser opens, and if no
repository folder has been chosen yet the first screen asks for one.

    python run.py --demo           point it at the pretend pipeline in mockrepo
    python run.py --no-browser     start it without opening a browser
    python run.py --check          prove it works and stop, printing what it found

This is the install-free build. It runs on Python's own library alone -- no
FastAPI, no uvicorn, no pydantic, nothing from the package site. The only thing
beside the standard library is the SQL parser, which is sitting in the sqlglot
folder next to this file as ordinary Python.
"""
from __future__ import annotations

import sys
import time
import traceback
import webbrowser
from pathlib import Path

HERE = Path(__file__).resolve().parent

# The parser and the code both have to be findable from wherever this was
# started, not from wherever the person happened to be standing.
sys.path.insert(0, str(HERE))

# Blocking the network is the first thing that happens, before any other part of
# Ripple is imported -- so anything that reaches out at import time is caught
# too, not just anything that reaches out during a request.
from ripple_offline import nonet                                    # noqa: E402

nonet.install()

from ripple_offline import lifecycle, paths, prefs                  # noqa: E402
from ripple_offline.webserver import free_port, serve               # noqa: E402


class _Stoppable:
    """What lifecycle stops when the Close button is pressed.

    It expects to set ``should_exit`` on something, because the packaged build
    hands it a uvicorn server. This is the same idea with nothing else in it, so
    the Close button and the "the page has gone" clock both work here exactly as
    they do there.
    """

    def __init__(self) -> None:
        self.should_exit = False


def _startup_report(values: dict, folder: dict, port: int) -> None:
    print("\n  Ripple")
    print(f"  repository : {values['repoPath'] or '(not chosen yet)'}")
    print(f"  folder     : {folder['message']}")
    print(f"  SQL read as: {values['sqlDialect'] or 'generic'}")
    print(f"  settings   : {paths.settings_file()}")
    print(f"  history    : {paths.history_file()}")
    print("  network    : blocked - loopback only")
    print(f"\n  open http://localhost:{port}\n")


def _self_check() -> int:
    """Prove the whole thing works, without a browser and without a person.

    Reads the folder, scans it, and prints what came back. This is what to run
    first on a machine you have just copied Ripple onto: if it prints a table
    name, everything underneath the screens is working, and anything wrong after
    that is the browser rather than Ripple.
    """
    from ripple_offline import app as service                       # noqa: PLC0415

    idx, parsed, cat = service.repo_state()
    print(f"  files read      : {len(idx.files)}")
    print(f"  statements read : {len(parsed.statements)}")
    print(f"  tables learned  : {len(cat.tables)}")
    if not idx.files:
        print("\n  No repository folder is chosen yet, so there was nothing to read.")
        print("  Start Ripple normally and choose one on the settings screen.")
        return 0
    table = next((t for t in cat.tables if cat.tables[t]), "")
    if not table:
        print("\n  Nothing readable was found in that folder.")
        return 1
    column = cat.tables[table][0]
    print(f"\n  scanning {table}.{column} ...")
    out = service.scan({"upstream": [{"table": table, "attrs": [column]}],
                        "changeKind": "removal"})
    print(f"  risk            : {out['risk']}")
    print(f"  published tables: {[g['prod'] for g in out['groups']] or 'none'}")
    print(f"  files with impact: {out['stats']['filesWithImpact']}")
    print("\n  Ripple works on this machine.\n")
    return 0


def _use_the_bundled_repo() -> None:
    """Point Ripple at the pretend pipeline that came with it.

    A settings file carries an absolute path, and a path from the machine this
    folder was assembled on means nothing on the machine it was carried to. So
    this copy ships with nothing chosen, and this works the folder out from
    where run.py actually is -- which is right wherever it has been put.
    """
    mockrepo = HERE / "mockrepo"
    if not mockrepo.is_dir():
        raise SystemExit(f"There is no mockrepo folder beside run.py ({mockrepo}).")
    prefs.apply(prefs.save({"repoPath": str(mockrepo), "repoLabel": "",
                            "sqlDialect": "bigquery", "maxHops": 4,
                            "prodTables": "_published"}))
    print(f"\n  Pointed at the pretend pipeline: {mockrepo}")
    print("  Change it on the settings screen when you want to scan real work.")


def main() -> int:
    try:
        values = prefs.load()
        prefs.apply(values)

        if "--demo" in sys.argv:
            _use_the_bundled_repo()
            values = prefs.load()

        from ripple_offline import app as service                   # noqa: PLC0415

        if "--check" in sys.argv:
            return _self_check()

        if not service.mount_web():
            print("The screens are missing. The web folder should sit beside run.py "
                  "and hold index.html, app.js and styles.css.")
            return 1

        port = free_port()
        folder = prefs.check_folder(values["repoPath"])
        _startup_report(values, folder, port)

        server = serve(service.router, port)
        if "--no-browser" not in sys.argv:
            try:
                webbrowser.open(f"http://localhost:{port}")
            except Exception:                                       # noqa: BLE001
                pass

        # Closing the browser used to leave this running where nobody could see
        # it, holding its own folder open so the folder could not be deleted.
        # The open page says it is there every few seconds, and when it stops
        # saying so, this stops.
        watched = _Stoppable()
        lifecycle.reset()
        lifecycle.attach(watched)
        lifecycle.watch()
        try:
            while not watched.should_exit:
                time.sleep(0.4)
        except KeyboardInterrupt:
            print("\n  Stopping.")
        server.shutdown()
        print("\n  Ripple has stopped. You can close the browser tab.\n")
        return 0
    except SystemExit:
        raise
    except Exception as exc:                                        # noqa: BLE001
        print(traceback.format_exc())
        print(f"\n  Ripple could not start: {exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
