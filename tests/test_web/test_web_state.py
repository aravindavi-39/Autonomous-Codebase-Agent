"""Tests for centralized Streamlit session state management."""

from __future__ import annotations

from unittest.mock import MagicMock
import pytest

import web.state as state


@pytest.fixture(autouse=True)
def clean_state():
    """Ensure clean state before and after each test."""
    state.reset_session_cache()
    yield
    state.reset_session_cache()


def test_is_repo_loaded_empty():
    """is_repo_loaded returns False when no manifest is loaded."""
    assert not state.is_repo_loaded()


def test_repo_path_and_fingerprint():
    """Test getting and setting repo path and initial SHA-256 fingerprint."""
    state.set_repo_path("/fake/path")
    assert state.get_repo_path() == "/fake/path"

    state.set_initial_sha256("abc123hash")
    assert state.get_initial_sha256() == "abc123hash"


def test_manifest_and_is_repo_loaded():
    """Setting manifest should make is_repo_loaded return True."""
    mock_manifest = MagicMock()
    state.set_manifest(mock_manifest)
    assert state.is_repo_loaded()
    assert state.get_manifest() is mock_manifest


def test_analysis_artifacts_state():
    """Test storing and retrieving code_index, code_graph, context, report, and plan."""
    mock_index = MagicMock()
    mock_graph = MagicMock()
    mock_ctx = MagicMock()
    mock_report = MagicMock()
    mock_plan = MagicMock()

    state.set_code_index(mock_index)
    state.set_code_graph(mock_graph)
    state.set_analysis_context(mock_ctx)
    state.set_analysis_report(mock_report)
    state.set_refactoring_plan(mock_plan)

    assert state.get_code_index() is mock_index
    assert state.get_code_graph() is mock_graph
    assert state.get_analysis_context() is mock_ctx
    assert state.get_analysis_report() is mock_report
    assert state.get_refactoring_plan() is mock_plan


def test_sandbox_and_verification_state():
    """Test storing and retrieving sandbox reports and verification reports."""
    mock_sb_report = MagicMock()
    mock_sb_session = MagicMock()
    mock_sb_report.session = mock_sb_session

    mock_v_report = MagicMock()

    state.set_sandbox_report(mock_sb_report)
    assert state.get_sandbox_report() is mock_sb_report
    assert state.get_sandbox_result() is mock_sb_session

    state.set_verification_report(mock_v_report)
    assert state.get_verification_report() is mock_v_report


def test_qa_history():
    """Test appending to and reading QA interaction history."""
    assert state.get_qa_history() == []
    entry = {"question": "What is this?", "answer": "A test.", "citations": []}
    state.add_qa_history_entry(entry)
    history = state.get_qa_history()
    assert len(history) == 1
    assert history[0]["question"] == "What is this?"


def test_llm_and_retrieval_configs():
    """Test getting and updating LLM and retrieval configurations."""
    llm_cfg = state.get_llm_config()
    assert "mock_mode" in llm_cfg

    state.set_llm_config({"mock_mode": False, "api_key": "secret-key", "model": "gpt-4o"})
    assert state.get_llm_config()["model"] == "gpt-4o"

    ret_cfg = state.get_retrieval_config()
    assert "top_k" in ret_cfg

    state.set_retrieval_config({"top_k": 10, "max_context": 5000})
    assert state.get_retrieval_config()["top_k"] == 10


def test_active_page():
    """Test setting and getting active navigation page."""
    assert state.get_active_page() == "Dashboard"
    state.set_active_page("Reports")
    assert state.get_active_page() == "Reports"


def test_reset_session_cache_clears_models():
    """Test that reset_session_cache clears artifacts but leaves configuration."""
    state.set_manifest(MagicMock())
    state.set_code_index(MagicMock())
    state.set_llm_config({"mock_mode": True})

    assert state.is_repo_loaded()
    state.reset_session_cache()
    assert not state.is_repo_loaded()
    assert state.get_code_index() is None
    # Config is preserved
    assert state.get_llm_config()["mock_mode"] is True
