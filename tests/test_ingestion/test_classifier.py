"""Tests for file classification (documentation, configuration, test)."""

import pytest

from ingestion.classifier import classify_file


class TestDocumentationDetection:
    """Tests for _is_documentation via classify_file."""

    @pytest.mark.parametrize(
        "fname",
        ["README.md", "readme.md", "CHANGELOG.md", "LICENSE", "CONTRIBUTING.md"],
    )
    def test_known_doc_names(self, fname: str) -> None:
        """Well-known documentation filenames should be detected."""
        is_doc, _, _ = classify_file(fname, ".md" if "." in fname else "", fname)
        assert is_doc is True

    def test_doc_in_docs_directory(self) -> None:
        """A markdown file inside a docs/ directory is documentation."""
        is_doc, _, _ = classify_file("guide.md", ".md", "docs/guide.md")
        assert is_doc is True

    def test_non_doc_python_file(self) -> None:
        """A regular Python source file is not documentation."""
        is_doc, _, _ = classify_file("app.py", ".py", "src/app.py")
        assert is_doc is False

    def test_non_doc_md_outside_docs(self) -> None:
        """A markdown file not matching known names or dirs is not doc."""
        is_doc, _, _ = classify_file("notes.md", ".md", "src/notes.md")
        assert is_doc is False


class TestConfigurationDetection:
    """Tests for _is_configuration via classify_file."""

    @pytest.mark.parametrize(
        "fname, ext",
        [
            ("pyproject.toml", ".toml"),
            ("requirements.txt", ".txt"),
            (".gitignore", ""),
            ("package.json", ".json"),
            ("tsconfig.json", ".json"),
            ("docker-compose.yml", ".yml"),
            ("Dockerfile", ""),
        ],
    )
    def test_known_config_names(self, fname: str, ext: str) -> None:
        """Well-known configuration filenames should be detected."""
        _, is_config, _ = classify_file(fname, ext, fname)
        assert is_config is True

    def test_toml_extension_is_config(self) -> None:
        """Files with .toml extension are configuration."""
        _, is_config, _ = classify_file("settings.toml", ".toml", "settings.toml")
        assert is_config is True

    def test_ini_extension_is_config(self) -> None:
        """Files with .ini extension are configuration."""
        _, is_config, _ = classify_file("app.ini", ".ini", "app.ini")
        assert is_config is True

    def test_python_source_not_config(self) -> None:
        """A regular Python source file is not configuration."""
        _, is_config, _ = classify_file("app.py", ".py", "src/app.py")
        assert is_config is False


class TestTestFileDetection:
    """Tests for _is_test_file via classify_file."""

    @pytest.mark.parametrize(
        "fname, rel_path",
        [
            ("test_app.py", "test_app.py"),
            ("test_app.py", "tests/test_app.py"),
            ("app_test.py", "app_test.py"),
            ("app.test.js", "app.test.js"),
            ("app.spec.ts", "app.spec.ts"),
            ("AppTest.java", "AppTest.java"),
            ("handler_test.go", "handler_test.go"),
            ("conftest.py", "tests/conftest.py"),
        ],
    )
    def test_known_test_patterns(self, fname: str, rel_path: str) -> None:
        """Files matching test naming patterns should be detected."""
        ext = "." + fname.rsplit(".", 1)[-1] if "." in fname else ""
        _, _, is_test = classify_file(fname, ext, rel_path)
        assert is_test is True

    def test_file_in_tests_directory(self) -> None:
        """Any file inside a tests/ directory should be a test file."""
        _, _, is_test = classify_file("helper.py", ".py", "tests/helper.py")
        assert is_test is True

    def test_regular_source_not_test(self) -> None:
        """A regular source file is not a test file."""
        _, _, is_test = classify_file("app.py", ".py", "src/app.py")
        assert is_test is False

    def test_file_in_underscore_tests_dir(self) -> None:
        """Files in __tests__/ directory (JS convention) are test files."""
        _, _, is_test = classify_file("utils.js", ".js", "__tests__/utils.js")
        assert is_test is True
