"""End-to-end tests for the ingestion pipeline and manifest export."""

import json
from pathlib import Path

import pytest

from ingestion.pipeline import IngestionPipeline
from ingestion.validator import ValidationError


class TestIngestionPipeline:
    """Test the IngestionPipeline orchestrator."""

    def test_ingest_sample_repo(self, sample_repo_path: Path) -> None:
        """Ingesting the sample repo should produce a valid manifest."""
        pipeline = IngestionPipeline()
        manifest = pipeline.ingest(str(sample_repo_path))

        assert manifest.name == "sample_repo"
        assert len(manifest.files) > 10
        assert len(manifest.directories) > 3
        assert manifest.statistics.total_files == len(manifest.files)
        assert manifest.statistics.total_lines > 0

    def test_ingest_invalid_path(self) -> None:
        """Ingesting a nonexistent path should raise ValidationError."""
        pipeline = IngestionPipeline()
        with pytest.raises(ValidationError):
            pipeline.ingest("/nonexistent/path/xyz")

    def test_manifest_property(self, sample_repo_path: Path) -> None:
        """The manifest property should return None before ingest, and the
        manifest after."""
        pipeline = IngestionPipeline()
        assert pipeline.manifest is None
        pipeline.ingest(str(sample_repo_path))
        assert pipeline.manifest is not None

    def test_export_json_string(self, sample_repo_path: Path) -> None:
        """export_json() should return valid JSON."""
        pipeline = IngestionPipeline()
        pipeline.ingest(str(sample_repo_path))
        json_str = pipeline.export_json()
        data = json.loads(json_str)
        assert data["name"] == "sample_repo"
        assert "files" in data
        assert "statistics" in data

    def test_export_json_to_file(self, sample_repo_path: Path, tmp_path: Path) -> None:
        """export_json(path) should write the manifest to a file."""
        pipeline = IngestionPipeline()
        pipeline.ingest(str(sample_repo_path))
        out = tmp_path / "manifest.json"
        pipeline.export_json(str(out))

        assert out.exists()
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["name"] == "sample_repo"
        assert len(data["files"]) > 0

    def test_export_before_ingest_raises(self) -> None:
        """Calling export_json before ingest should raise RuntimeError."""
        pipeline = IngestionPipeline()
        with pytest.raises(RuntimeError, match="No manifest"):
            pipeline.export_json()

    def test_manifest_json_has_statistics(self, sample_repo_path: Path) -> None:
        """The JSON manifest should contain statistics with expected keys."""
        pipeline = IngestionPipeline()
        pipeline.ingest(str(sample_repo_path))
        data = json.loads(pipeline.export_json())
        stats = data["statistics"]
        assert "total_files" in stats
        assert "total_directories" in stats
        assert "total_lines" in stats
        assert "files_by_language" in stats
        assert "test_files" in stats
        assert "documentation_files" in stats
        assert "configuration_files" in stats

    def test_original_repo_not_modified(self, sample_repo_path: Path) -> None:
        """Ingestion must not create or modify any files in the original repo."""
        # Snapshot file listing before ingestion
        before = set()
        for p in sample_repo_path.rglob("*"):
            if p.is_file():
                before.add((str(p.relative_to(sample_repo_path)), p.stat().st_size))

        pipeline = IngestionPipeline()
        pipeline.ingest(str(sample_repo_path))

        # Snapshot after
        after = set()
        for p in sample_repo_path.rglob("*"):
            if p.is_file():
                after.add((str(p.relative_to(sample_repo_path)), p.stat().st_size))

        assert before == after, "Ingestion modified the original repository!"


class TestIngestionWithTempRepo:
    """Edge-case tests using temporary repositories."""

    def test_max_file_size_respected(self, tmp_path: Path) -> None:
        """Files exceeding max_file_size_kb should be excluded."""
        (tmp_path / "small.py").write_text("x = 1\n")
        (tmp_path / "big.py").write_text("y = 2\n" * 200)  # ~1200 bytes

        pipeline = IngestionPipeline(max_file_size_kb=1)  # 1 KB limit
        manifest = pipeline.ingest(str(tmp_path))

        names = {f.file_name for f in manifest.files}
        assert "small.py" in names
        assert "big.py" not in names

    def test_nested_ignored_dirs(self, tmp_path: Path) -> None:
        """Nested ignored directories should also be skipped."""
        (tmp_path / "src" / "node_modules" / "pkg").mkdir(parents=True)
        (tmp_path / "src" / "node_modules" / "pkg" / "index.js").write_text("x")
        (tmp_path / "src" / "app.py").write_text("pass")

        pipeline = IngestionPipeline()
        manifest = pipeline.ingest(str(tmp_path))
        paths = {f.relative_path for f in manifest.files}
        assert "src/app.py" in paths
        assert "src/node_modules/pkg/index.js" not in paths

    def test_env_files_excluded(self, tmp_path: Path) -> None:
        """.env and .env.* files must be excluded from ingestion."""
        (tmp_path / ".env").write_text("SECRET=abc")
        (tmp_path / ".env.local").write_text("KEY=val")
        (tmp_path / "app.py").write_text("pass")

        pipeline = IngestionPipeline()
        manifest = pipeline.ingest(str(tmp_path))
        names = {f.file_name for f in manifest.files}
        assert ".env" not in names
        assert ".env.local" not in names
        assert "app.py" in names
