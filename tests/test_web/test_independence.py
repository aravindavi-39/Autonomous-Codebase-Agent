"""Test core module independence from Streamlit.

Ensures that core ingestion, analysis, refactoring, sandbox, verification,
and CLI modules never import or depend on Streamlit.
"""

from __future__ import annotations

import importlib
import sys
from unittest.mock import patch


def test_core_modules_importable_without_streamlit() -> None:
    """Core modules must import cleanly even when streamlit is unavailable."""
    core_modules = [
        "ingestion.discoverer",
        "ingestion.pipeline",
        "ingestion.validator",
        "analysis.analyzer",
        "analysis.graph_builder",
        "analysis.findings.engine",
        "analysis.findings.models",
        "refactoring.planner",
        "refactoring.generator",
        "refactoring.models",
        "sandbox.manager",
        "sandbox.copier",
        "sandbox.tester",
        "verification.engine",
        "verification.delta_engine",
        "verification.linter",
        "verification.policy",
        "cli.main",
    ]

    with patch.dict(sys.modules, {"streamlit": None}):
        for mod_name in core_modules:
            if mod_name in sys.modules:
                del sys.modules[mod_name]
            mod = importlib.import_module(mod_name)
            assert mod is not None, f"Failed to import {mod_name} without streamlit"


def test_cli_help_without_streamlit() -> None:
    """Typer CLI runner must execute --help successfully without Streamlit."""
    from typer.testing import CliRunner
    from cli.main import app

    with patch.dict(sys.modules, {"streamlit": None}):
        runner = CliRunner()
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Autonomous Codebase Understanding & Refactor Agent" in result.output
