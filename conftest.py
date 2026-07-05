# ============================================================
# conftest.py — Pytest configuration
# ============================================================
# Ensures the project root is on sys.path so tests can import
# backend, parser, ai, database, scheduler, utils regardless of
# the directory pytest is invoked from.
# ============================================================

import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
