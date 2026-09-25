"""Tests for repository-level code indexing and query functionality."""

import json
from pathlib import Path
import pytest

from analysis.analyzer import RepositoryAnalyzer
from analysis.models import RepositoryCodeIndex
from ingestion.pipeline import IngestionPipeline


@pytest.fixture
def sample_repo_path() -> Path:
    return Path(__file__).resolve().parent.parent / "fixtures" / "sample_repo"


@pytest.fixture
def code_index(sample_repo_path: Path) -> RepositoryCodeIndex:
    analyzer = RepositoryAnalyzer()
    return analyzer.analyze_repository(str(sample_repo_path))


class TestRepositoryCodeIndex:
    """Verify repository-level code index queries."""

    def test_analyzed_python_files_count(self, code_index: RepositoryCodeIndex) -> None:
        """sample_repo has 7 Python files."""
        assert code_index.summary.python_files_analyzed == 7
        assert code_index.summary.parse_errors == 0

    def test_classes_exist_query(self, code_index: RepositoryCodeIndex) -> None:
        """Verify get_classes() returns User and Post."""
        classes = code_index.get_classes()
        class_names = [c.name for c in classes]
        assert "User" in class_names
        assert "Post" in class_names

    def test_find_class(self, code_index: RepositoryCodeIndex) -> None:
        """Verify find_class() retrieves class with accurate line citations."""
        matches = code_index.find_class("User")
        assert len(matches) == 1
        user_cls = matches[0]
        assert user_cls.name == "User"
        assert user_cls.file == "src/models.py"
        assert user_cls.start_line == 8
        assert user_cls.end_line == 13

    def test_functions_exist_query(self, code_index: RepositoryCodeIndex) -> None:
        """Verify get_functions() finds top-level functions."""
        functions = code_index.get_functions(include_methods=False)
        fn_names = [f.name for f in functions]
        assert "create_app" in fn_names
        assert "hash_file" in fn_names
        assert "format_size" in fn_names

    def test_find_function(self, code_index: RepositoryCodeIndex) -> None:
        """Verify find_function() retrieves function and its accurate line numbers."""
        matches = code_index.find_function("hash_file")
        assert len(matches) == 1
        fn = matches[0]
        assert fn.name == "hash_file"
        assert fn.file == "src/utils.py"
        assert fn.start_line == 7
        assert fn.end_line == 13
        assert fn.return_annotation == "str"

    def test_get_calls_for_function(self, code_index: RepositoryCodeIndex) -> None:
        """Verify what a function calls."""
        calls = code_index.get_calls_for_function("hash_file")
        targets = [c.target for c in calls]
        assert "hashlib.sha256" in targets
        assert "open" in targets
        assert "sha.hexdigest" in targets

    def test_get_modules_importing(self, code_index: RepositoryCodeIndex) -> None:
        """Verify finding which modules import a package."""
        importers = code_index.get_modules_importing("flask")
        assert "src/app.py" in importers

    def test_get_subclasses(self, tmp_path: Path) -> None:
        """Verify subclass lookup across files."""
        (tmp_path / "base.py").write_text("class Animal:\n    pass\n")
        (tmp_path / "dog.py").write_text("from base import Animal\nclass Dog(Animal):\n    pass\n")
        (tmp_path / "cat.py").write_text("from base import Animal\nclass Cat(Animal):\n    pass\n")

        analyzer = RepositoryAnalyzer()
        index = analyzer.analyze_repository(str(tmp_path))

        subclasses = index.get_subclasses("Animal")
        names = [c.name for c in subclasses]
        assert "Dog" in names
        assert "Cat" in names

    def test_export_json_deterministic(self, code_index: RepositoryCodeIndex, tmp_path: Path) -> None:
        """Verify export_json() generates valid, deterministic JSON with required fields."""
        json_file = tmp_path / "analysis.json"
        exported_str = code_index.export_json(json_file)

        assert json_file.exists()
        data = json.loads(exported_str)
        assert "manifest" in data
        assert "file_analyses" in data
        assert "summary" in data

        # Check citation fields exist
        first_fa = next(fa for fa in data["file_analyses"] if fa["status"] == "ok" and fa["functions"])
        fn = first_fa["functions"][0]
        assert "name" in fn
        assert "file" in fn
        assert "start_line" in fn
        assert "end_line" in fn

    def test_resilience_to_syntax_error_files(self, tmp_path: Path) -> None:
        """Verify that a syntax error in one file does not stop analysis of other files."""
        (tmp_path / "good1.py").write_text("def hello(): return 1\n")
        (tmp_path / "broken.py").write_text("def broken(:\n")
        (tmp_path / "good2.py").write_text("def world(): return 2\n")

        analyzer = RepositoryAnalyzer()
        index = analyzer.analyze_repository(str(tmp_path))

        assert index.summary.python_files_analyzed == 3
        assert index.summary.parse_errors == 1
        assert index.summary.total_functions == 2

        # Check statuses
        statuses = {fa.file_path: fa.status for fa in index.file_analyses}
        assert statuses["good1.py"] == "ok"
        assert statuses["broken.py"] == "parse_error"
        assert statuses["good2.py"] == "ok"

    def test_target_repository_not_modified(self, sample_repo_path: Path) -> None:
        """Ensure analyzer never writes or modifies anything in the target repository."""
        before = set()
        for p in sample_repo_path.rglob("*"):
            if p.is_file():
                before.add((str(p.relative_to(sample_repo_path)), p.stat().st_size, p.stat().st_mtime_ns))

        analyzer = RepositoryAnalyzer()
        analyzer.analyze_repository(str(sample_repo_path))

        after = set()
        for p in sample_repo_path.rglob("*"):
            if p.is_file():
                after.add((str(p.relative_to(sample_repo_path)), p.stat().st_size, p.stat().st_mtime_ns))

        assert before == after, "Repository was modified during analysis!"
