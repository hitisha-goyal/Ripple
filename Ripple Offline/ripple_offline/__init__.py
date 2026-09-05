"""Ripple Offline — the same Ripple, packaged for a machine with no internet.

This package is a wrapper, not a copy. The analysis engine lives in
``D:\\Apps\\Ripple\\Codebase\\ripple`` and stays there: importing anything from
here puts that folder on the import path first, so there is exactly one copy of
the scanner, the SQL reader, the lineage tracer and the writer. What lives here
is only what genuinely differs offline — settings chosen on screen instead of
in environment variables, and a front end with nothing on it that reaches out.
"""
from __future__ import annotations

from .engine import ensure_engine_importable

ensure_engine_importable()
