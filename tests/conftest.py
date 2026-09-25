"""Shared pytest fixtures for the Autonomous Codebase Agent test suite."""

import sys
from pathlib import Path

import pytest

# Ensure src/ is on the path so imports resolve correctly during testing.
_src_dir = Path(__file__).resolve().parent.parent / "src"
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

# Ensure config/ is also importable (it lives alongside src/, not inside it).
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
