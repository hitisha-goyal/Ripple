"""Entry point for Vercel.

Vercel runs each request through this file. It simply hands over to the same
FastAPI application that `python run.py` uses locally, so there is exactly one
copy of the logic.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ripple.api import app  # noqa: E402

__all__ = ["app"]
