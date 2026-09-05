"""Finding the one copy of the analysis engine.

Ripple Offline deliberately has no ``ripple`` package of its own. Two copies
would drift: the online one has already grown BigQuery support, MERGE lineage
and honesty notices that a fork would quietly miss, and the fork would be the
one running on the locked-down machine where nobody can check it.

So there is one copy, in ``Codebase/ripple``, and two ways of reaching it:

* running from source, this adds ``Codebase`` to the import path;
* running as a built executable, the build script has already collected that
  same folder into the bundle, so ``import ripple`` simply works.

If the shared engine is not where it should be, this says so and stops. It
never falls back to a copy — a stale copy is the exact failure it exists to
prevent.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OFFLINE_DIR = HERE.parent                       # ...\Ripple\Ripple Offline
PROJECT_ROOT = OFFLINE_DIR.parent               # ...\Ripple
SHARED_DIR = PROJECT_ROOT / "Codebase"          # ...\Ripple\Codebase
SHARED_ENGINE = SHARED_DIR / "ripple"
SHARED_WEB = SHARED_DIR / "web"

MISSING = f"""
Ripple Offline could not find the shared Ripple engine.

It expects to find it at:
    {SHARED_ENGINE}

Ripple Offline does not carry its own copy on purpose — one copy means the
offline build can never fall behind the online one. Put this folder back
beside the Codebase folder, or check out the repository again, and re-run.
"""


def frozen() -> bool:
    """True when running as the built executable rather than from source."""
    return bool(getattr(sys, "frozen", False))


def ensure_engine_importable() -> Path | None:
    """Make ``import ripple`` work. Returns the folder used, or None if bundled."""
    if frozen():
        return None                              # the build collected it already
    if not (SHARED_ENGINE / "api.py").is_file():
        raise SystemExit(MISSING)
    shared = str(SHARED_DIR)
    if shared not in sys.path:
        sys.path.insert(0, shared)
    return SHARED_DIR
