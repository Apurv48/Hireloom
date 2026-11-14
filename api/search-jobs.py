"""Vercel serverless entry point for /api/search-jobs (logic lives in server.py)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server import Handler  # noqa: E402


class handler(Handler):
    """Vercel's Python runtime looks for a class named `handler`."""
