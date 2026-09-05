"""Ripple, packaged for a machine where nothing can be installed.

A snapshot, not the product's own offline build. The product keeps ONE engine
and reaches back into it; this folder carries its own copy because there is
nothing here to reach back to. See engine.py for what that costs.

What lives in this package is only what genuinely differs when Ripple has to run
with no internet and no installs: settings chosen on screen instead of in
environment variables, a web service built out of Python's own library, and a
front end with nothing on it that reaches out.
"""
from __future__ import annotations

from .engine import ensure_engine_importable

ensure_engine_importable()
