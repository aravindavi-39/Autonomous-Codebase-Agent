"""Tests for secret detection, exclusion, and redaction across retrieval and Q&A."""

from pathlib import Path
import pytest

from citations.models import Citation
from citations.validator import CitationValidator
from ingestion.models import FileMetadata, FileRecord, Language, RepositoryManifest
from llm.fake_provider import FakeLLMProvider
from retrieval.chunker import CodeChunk, SemanticChunker
from retrieval.context_builder import ContextBuilder
from retrieval.qa_engine import QAEngine
from retrieval.retriever import HybridRetriever, RetrievalResult
from retrieval.vector_store import LocalVectorStore
from utils.secrets import contains_secrets, redact_secrets, sanitize_metadata


class TestSecretExclusionAndRedaction:
    """Verify that credentials, API keys, and sensitive files are never exposed."""

    def test_secret_detection_patterns(self) -> None:
        assert contains_secrets("sk-proj-abc12345678901234567890") is True
        assert contains_secrets("api_key = 'super_secret_token_12345'") is True
        assert contains_secrets("password: 'MySecretPassword123'") is True
        assert contains_secrets("AKIAIOSFODNN7EXAMPLE") is True
        assert contains_secrets("regular benign python code: def add(a, b): return a + b") is False

    def test_secret_redaction(self) -> None:
        raw = "OpenAI key: sk-proj-123456789012345678901234567890 and api_key = 'my_top_secret_token'"
        cleaned = redact_secrets(raw)
        assert "sk-proj-1234567890" not in cleaned
        assert "my_top_secret_token" not in cleaned
        assert "[REDACTED_API_KEY]" in cleaned
        assert "[REDACTED_SECRET]" in cleaned

    def test_metadata_sanitization(self) -> None:
        raw_meta = {
            "file": "src/config.py",
            "token": "sk-proj-123456789012345678901234567890",
            "count": 42,
        }
        clean_meta = sanitize_metadata(raw_meta)
        assert "sk-proj-1234567890" not in clean_meta["token"]
        assert "[REDACTED_API_KEY]" in clean_meta["token"]
        assert clean_meta["count"] == 42

    def test_chunker_excludes_secret_files(self, tmp_path: Path) -> None:
        repo_dir = tmp_path / "mock_repo"
        repo_dir.mkdir()
        (repo_dir / "safe.py").write_text("print('safe')", encoding="utf-8")
        (repo_dir / ".env").write_text("OPENAI_API_KEY=sk-test1234567890", encoding="utf-8")
        (repo_dir / "server.key").write_text("PRIVATE KEY DATA", encoding="utf-8")

        manifest = RepositoryManifest(
            root_path=str(repo_dir),
            name="mock_repo",
            total_files=3,
            total_directories=1,
            total_lines=3,
            total_size_bytes=200,
            languages=[Language.PYTHON],
            files=[
                FileRecord(
                    path=str(repo_dir / "safe.py"),
                    relative_path="safe.py",
                    file_name="safe.py",
                    extension=".py",
                    language=Language.PYTHON,
                    metadata=FileMetadata(size_bytes=20, line_count=1),
                ),
                FileRecord(
                    path=str(repo_dir / ".env"),
                    relative_path=".env",
                    file_name=".env",
                    extension="",
                    language=Language.UNKNOWN,
                    metadata=FileMetadata(size_bytes=50, line_count=1),
                ),
                FileRecord(
                    path=str(repo_dir / "server.key"),
                    relative_path="server.key",
                    file_name="server.key",
                    extension=".key",
                    language=Language.UNKNOWN,
                    metadata=FileMetadata(size_bytes=50, line_count=1),
                ),
            ],
            directories=[],
        )

        chunker = SemanticChunker(root_path=repo_dir)
        chunks = chunker.chunk_repository(manifest=manifest)

        chunk_files = [c.file for c in chunks]
        assert "safe.py" in chunk_files
        assert ".env" not in chunk_files
        assert "server.key" not in chunk_files

    def test_context_builder_redacts_residual_secrets(self) -> None:
        chunk = CodeChunk(
            text="api_key = 'leaked_secret_value_12345'\ndef connect(): pass",
            file="src/db.py",
            start_line=1,
            end_line=2,
            type="function",
            language="Python",
        )
        res = RetrievalResult(
            query="test",
            semantic_chunks=[(chunk, 0.95)],
            structural_nodes=[],
            structural_edges=[],
        )
        builder = ContextBuilder()
        built = builder.build_context(res)
        assert "leaked_secret_value_12345" not in built.context_text
        assert "[REDACTED_SECRET]" in built.context_text

    def test_qa_engine_redacts_secrets_in_answer(self) -> None:
        # If an LLM returns text with a secret, QAEngine redacts it
        leaky_response = "Here is the key: sk-proj-123456789012345678901234567890"
        provider = FakeLLMProvider(default_response=leaky_response)

        manifest = RepositoryManifest(
            root_path=".",
            name="test",
            total_files=0,
            total_directories=0,
            total_lines=0,
            total_size_bytes=0,
            languages=[],
            files=[],
            directories=[],
        )
        validator = CitationValidator(manifest=manifest)
        store = LocalVectorStore()
        retriever = HybridRetriever(vector_store=store)
        engine = QAEngine(
            retriever=retriever,
            llm_provider=provider,
            citation_validator=validator,
        )

        resp = engine.ask("What is the key?")
        assert "sk-proj-12345678901234567890" not in resp.answer
        assert "[REDACTED_API_KEY]" in resp.answer
