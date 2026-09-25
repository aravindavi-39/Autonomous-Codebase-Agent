"""Tests for the CLI ask command, answer quality, and target repository safety."""

import hashlib
from pathlib import Path
import pytest
from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()


@pytest.fixture
def sample_repo() -> str:
    return str(Path("tests/fixtures/sample_repo"))


def _snapshot_repo(repo_path: Path) -> dict[str, str]:
    """Capture relative paths and SHA-256 hashes of all files in a repository."""
    snapshot: dict[str, str] = {}
    for p in repo_path.rglob("*"):
        if p.is_file():
            rel = str(p.relative_to(repo_path)).replace("\\", "/")
            h = hashlib.sha256(p.read_bytes()).hexdigest()
            snapshot[rel] = h
    return snapshot


class TestCLIAskCommand:
    """Verify CLI ask command execution with mock mode, grounding, and repo immutability."""

    def test_ask_mock_mode_what_classes_exist_grounded(self, sample_repo: str) -> None:
        result = runner.invoke(app, ["ask", sample_repo, "What classes exist?", "--mock"])
        assert result.exit_code == 0
        assert "Question:" in result.output
        assert "What classes exist?" in result.output
        assert "Answer:" in result.output
        # Check 4: Must name real classes discovered in the repository
        assert "User" in result.output
        assert "Post" in result.output
        # Must cite real locations
        assert "src/models.py" in result.output

    def test_ask_mock_mode_authentication_no_fabrication(self, sample_repo: str) -> None:
        result = runner.invoke(app, ["ask", sample_repo, "How does authentication work?", "--mock"])
        assert result.exit_code == 0
        assert "Answer:" in result.output
        # Check 4: Must NOT fabricate authentication architecture
        assert "insufficient" in result.output.lower() or "no authentication" in result.output.lower()

    def test_ask_mock_mode_with_flags(self, sample_repo: str) -> None:
        result = runner.invoke(
            app,
            [
                "ask",
                sample_repo,
                "How does hash_file work?",
                "--mock",
                "--top-k", "2",
                "--no-graph",
            ],
        )
        assert result.exit_code == 0
        assert "Answer:" in result.output
        assert "Sources:" in result.output

    def test_ask_mock_mode_no_semantic(self, sample_repo: str) -> None:
        result = runner.invoke(
            app,
            [
                "ask",
                sample_repo,
                "What classes exist?",
                "--mock",
                "--no-semantic",
            ],
        )
        assert result.exit_code == 0
        assert "Answer:" in result.output
        assert "User" in result.output or "Post" in result.output

    def test_ask_mock_mode_no_graph(self, sample_repo: str) -> None:
        result = runner.invoke(
            app,
            [
                "ask",
                sample_repo,
                "What classes exist?",
                "--mock",
                "--no-graph",
            ],
        )
        assert result.exit_code == 0
        assert "Answer:" in result.output

    def test_ask_without_api_key_shows_configuration_error(
        self, sample_repo: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        result = runner.invoke(app, ["ask", sample_repo, "How does user creation work?"])
        assert result.exit_code == 1
        assert "Configuration error:" in result.output or "Error:" in result.output
        assert "OPENAI_API_KEY" in result.output

    def test_ask_invalid_path(self) -> None:
        result = runner.invoke(app, ["ask", "/nonexistent/repo", "any question", "--mock"])
        assert result.exit_code == 1
        assert "Error:" in result.output

    def test_target_repository_completely_unchanged(self, sample_repo: str) -> None:
        """Check 7: Target repository must remain strictly immutable across ask operations."""
        repo_path = Path(sample_repo)
        before_snapshot = _snapshot_repo(repo_path)

        # Run multiple questions with various flags
        runner.invoke(app, ["ask", sample_repo, "What classes exist?", "--mock"])
        runner.invoke(app, ["ask", sample_repo, "How does authentication work?", "--mock", "--no-semantic"])
        runner.invoke(app, ["ask", sample_repo, "Tell me about create_app", "--mock", "--no-graph"])

        after_snapshot = _snapshot_repo(repo_path)

        # Assert no files created, deleted, or changed
        assert set(before_snapshot.keys()) == set(after_snapshot.keys())
        for file_rel, h_before in before_snapshot.items():
            assert after_snapshot[file_rel] == h_before, f"File {file_rel} was modified during ask!"
