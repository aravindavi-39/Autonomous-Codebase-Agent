"""Tests for programming language detection."""

import pytest

from ingestion.languages import detect_language, EXTENSION_MAP, FILENAME_MAP
from ingestion.models import Language


class TestLanguageDetection:
    """Test detect_language with various extensions and filenames."""

    @pytest.mark.parametrize(
        "ext, expected",
        [
            (".py", Language.PYTHON),
            (".pyi", Language.PYTHON),
            (".js", Language.JAVASCRIPT),
            (".jsx", Language.JAVASCRIPT),
            (".mjs", Language.JAVASCRIPT),
            (".ts", Language.TYPESCRIPT),
            (".tsx", Language.TYPESCRIPT),
            (".java", Language.JAVA),
            (".c", Language.C),
            (".h", Language.C),
            (".cpp", Language.CPP),
            (".cc", Language.CPP),
            (".hpp", Language.CPP),
            (".cs", Language.CSHARP),
            (".go", Language.GO),
            (".rs", Language.RUST),
            (".html", Language.HTML),
            (".htm", Language.HTML),
            (".css", Language.CSS),
            (".scss", Language.CSS),
            (".json", Language.JSON),
            (".yaml", Language.YAML),
            (".yml", Language.YAML),
            (".md", Language.MARKDOWN),
            (".sql", Language.SQL),
            (".sh", Language.SHELL),
            (".toml", Language.TOML),
        ],
    )
    def test_extension_detection(self, ext: str, expected: Language) -> None:
        """Each known extension should map to the correct language."""
        result = detect_language(f"file{ext}", ext)
        assert result == expected

    def test_unknown_extension(self) -> None:
        """An unknown extension should return Language.UNKNOWN."""
        assert detect_language("file.xyz", ".xyz") == Language.UNKNOWN

    def test_no_extension(self) -> None:
        """A file with no extension and no special name returns UNKNOWN."""
        assert detect_language("somefile", "") == Language.UNKNOWN

    def test_dockerfile(self) -> None:
        """'Dockerfile' should be detected by filename."""
        assert detect_language("Dockerfile", "") == Language.DOCKERFILE

    def test_makefile(self) -> None:
        """'Makefile' should be detected by filename."""
        assert detect_language("Makefile", "") == Language.SHELL

    def test_case_insensitive_extension(self) -> None:
        """Extension matching should be case-insensitive."""
        assert detect_language("FILE.PY", ".PY") == Language.PYTHON
        assert detect_language("APP.Js", ".Js") == Language.JAVASCRIPT

    def test_filename_takes_priority_over_extension(self) -> None:
        """Filename-based detection should take priority over extension."""
        # Dockerfile has no extension but is in FILENAME_MAP
        assert detect_language("Dockerfile", "") == Language.DOCKERFILE

    def test_all_required_languages_have_extensions(self) -> None:
        """The 15 required languages must each have at least one extension."""
        required = {
            Language.PYTHON, Language.JAVASCRIPT, Language.TYPESCRIPT,
            Language.JAVA, Language.C, Language.CPP, Language.CSHARP,
            Language.GO, Language.RUST, Language.HTML, Language.CSS,
            Language.JSON, Language.YAML, Language.MARKDOWN, Language.SQL,
        }
        covered = set(EXTENSION_MAP.values())
        assert required.issubset(covered)
