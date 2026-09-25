"""Tests for the CLI entry point and basic package imports."""

from typer.testing import CliRunner

from cli.main import app
from config.settings import get_settings


runner = CliRunner()


class TestCLIBanner:
    """Verify the CLI displays the correct banner."""

    def test_cli_shows_app_name(self) -> None:
        """Running with no args should display the application name."""
        result = runner.invoke(app)
        assert result.exit_code == 0
        assert "Autonomous Codebase Understanding & Refactor Agent" in result.output

    def test_cli_shows_version(self) -> None:
        """Running with no args should display the version."""
        result = runner.invoke(app)
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_cli_version_flag(self) -> None:
        """Running with --version should display the version."""
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_cli_help(self) -> None:
        """Running with --help should succeed."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0


class TestPackageImports:
    """Verify that all packages can be imported without errors."""

    def test_import_cli(self) -> None:
        import cli
        assert hasattr(cli, "app")

    def test_import_config(self) -> None:
        import config
        assert hasattr(config, "Settings")
        assert hasattr(config, "get_settings")

    def test_import_ingestion(self) -> None:
        import ingestion  # noqa: F401

    def test_import_analysis(self) -> None:
        import analysis  # noqa: F401

    def test_import_refactoring(self) -> None:
        import refactoring  # noqa: F401

    def test_import_verification(self) -> None:
        import verification  # noqa: F401

    def test_import_sandbox(self) -> None:
        import sandbox  # noqa: F401

    def test_import_llm(self) -> None:
        import llm  # noqa: F401

    def test_import_citations(self) -> None:
        import citations  # noqa: F401

    def test_import_utils(self) -> None:
        import utils  # noqa: F401


class TestSettings:
    """Verify settings load correctly."""

    def test_settings_defaults(self) -> None:
        settings = get_settings()
        assert settings.app_name == "Autonomous Codebase Understanding & Refactor Agent"
        assert settings.app_version == "0.1.0"
        assert settings.log_level == "INFO"
        assert settings.max_repo_size_mb == 500

    def test_settings_singleton_consistency(self) -> None:
        """Two calls to get_settings should return equivalent values."""
        s1 = get_settings()
        s2 = get_settings()
        assert s1.app_version == s2.app_version
