"""Tests for semantic code and documentation chunking."""

from pathlib import Path
import pytest

from analysis.analyzer import RepositoryAnalyzer
from ingestion.pipeline import IngestionPipeline
from retrieval.chunker import CodeChunk, SemanticChunker


@pytest.fixture
def sample_repo_path() -> Path:
    return Path(__file__).resolve().parent.parent / "fixtures" / "sample_repo"


class TestSemanticChunker:
    """Verify semantic code chunking and metadata preservation."""

    def test_chunking_sample_repo(self, sample_repo_path: Path) -> None:
        pipeline = IngestionPipeline()
        manifest = pipeline.ingest(str(sample_repo_path))
        analyzer = RepositoryAnalyzer()
        code_index = analyzer.analyze_repository(str(sample_repo_path), manifest=manifest)

        chunker = SemanticChunker(root_path=sample_repo_path)
        chunks = chunker.chunk_repository(manifest=manifest, code_index=code_index)

        assert len(chunks) > 0

        # Check metadata preservation on all chunks
        for c in chunks:
            assert isinstance(c, CodeChunk)
            assert c.file != ""
            assert c.start_line >= 1
            assert c.end_line >= c.start_line
            assert c.type in ("function", "method", "class", "module", "documentation")
            assert c.text.strip() != ""

    def test_class_and_function_chunks(self, sample_repo_path: Path) -> None:
        pipeline = IngestionPipeline()
        manifest = pipeline.ingest(str(sample_repo_path))
        analyzer = RepositoryAnalyzer()
        code_index = analyzer.analyze_repository(str(sample_repo_path), manifest=manifest)

        chunker = SemanticChunker(root_path=sample_repo_path)
        chunks = chunker.chunk_repository(manifest=manifest, code_index=code_index)

        entities = {c.entity: c for c in chunks if c.entity}
        assert "User" in entities
        user_chunk = entities["User"]
        assert user_chunk.type == "class"
        assert user_chunk.file == "src/models.py"
        assert user_chunk.start_line == 8
        assert user_chunk.end_line == 13

        assert "hash_file" in entities
        hash_chunk = entities["hash_file"]
        assert hash_chunk.type == "function"
        assert hash_chunk.file == "src/utils.py"
        assert hash_chunk.start_line == 7
        assert hash_chunk.end_line == 13

    def test_documentation_chunks(self, sample_repo_path: Path) -> None:
        pipeline = IngestionPipeline()
        manifest = pipeline.ingest(str(sample_repo_path))

        chunker = SemanticChunker(root_path=sample_repo_path)
        chunks = chunker.chunk_repository(manifest=manifest)

        doc_chunks = [c for c in chunks if c.type == "documentation"]
        assert len(doc_chunks) > 0
        assert any("guide.md" in c.file or "README.md" in c.file for c in doc_chunks)

    def test_empty_repository(self, tmp_path: Path) -> None:
        pipeline = IngestionPipeline()
        manifest = pipeline.ingest(str(tmp_path))
        chunker = SemanticChunker(root_path=tmp_path)
        chunks = chunker.chunk_repository(manifest=manifest)
        assert chunks == []
