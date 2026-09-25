"""Tests for LocalVectorStore and ChromaVectorStore indexing, search, and persistence."""

from pathlib import Path
import pytest

from llm.fake_provider import FakeLLMProvider
from retrieval.chunker import CodeChunk
from retrieval.vector_store import (
    BaseVectorStore,
    ChromaVectorStore,
    LocalVectorStore,
    create_vector_store,
)


@pytest.fixture
def fake_chunks() -> list[CodeChunk]:
    return [
        CodeChunk(
            text="def hash_file(path): calculate sha256 digest of file",
            file="src/utils.py",
            start_line=7,
            end_line=13,
            entity="hash_file",
            type="function",
            language="Python",
        ),
        CodeChunk(
            text="class User: dataclass representing user with id, username, email",
            file="src/models.py",
            start_line=8,
            end_line=13,
            entity="User",
            type="class",
            language="Python",
        ),
        CodeChunk(
            text="def create_app(): create and configure Flask web application",
            file="src/app.py",
            start_line=6,
            end_line=14,
            entity="create_app",
            type="function",
            language="Python",
        ),
    ]


class TestLocalVectorStore:
    """Verify LocalVectorStore indexing, similarity ranking, and persistence."""

    def test_indexing_and_search(self, fake_chunks: list[CodeChunk]) -> None:
        provider = FakeLLMProvider(dimensions=32)
        store = LocalVectorStore()
        assert isinstance(store, BaseVectorStore)
        store.index(fake_chunks, provider=provider)

        assert len(store.chunks) == 3
        assert len(store.embeddings) == 3

        # Search for user-related chunk
        results = store.search("user dataclass model", provider=provider, top_k=2)
        assert len(results) == 2
        top_chunk, score = results[0]
        assert top_chunk.entity == "User"
        assert score > 0.0

        # Search for hash digest chunk
        results2 = store.search("hash_file sha256 digest", provider=provider, top_k=1)
        assert len(results2) == 1
        assert results2[0][0].entity == "hash_file"

    def test_empty_search(self) -> None:
        provider = FakeLLMProvider()
        store = LocalVectorStore()
        results = store.search("anything", provider=provider)
        assert results == []

    def test_persistence_and_reload(self, fake_chunks: list[CodeChunk], tmp_path: Path) -> None:
        persist_dir = tmp_path / "vstore"
        provider = FakeLLMProvider()

        store1 = LocalVectorStore(persist_dir=persist_dir)
        store1.index(fake_chunks, provider=provider)
        assert (persist_dir / "index.json").exists()

        # Reload in a new store instance
        store2 = LocalVectorStore(persist_dir=persist_dir)
        loaded = store2.load()
        assert loaded is True
        assert len(store2.chunks) == 3
        assert len(store2.embeddings) == 3
        assert store2.chunks[0].entity == "hash_file"


class TestChromaVectorStore:
    """Verify ChromaDB vector store implementation (Check 1 compliance)."""

    def test_chroma_indexing_and_search(self, fake_chunks: list[CodeChunk]) -> None:
        provider = FakeLLMProvider(dimensions=64)
        store = ChromaVectorStore(collection_name="test_collection_inmemory")
        assert isinstance(store, BaseVectorStore)

        store.index(fake_chunks, provider=provider)

        # Search for User dataclass
        results = store.search("user dataclass model", provider=provider, top_k=2)
        assert len(results) >= 1
        top_chunk, score = results[0]
        assert top_chunk.entity == "User"
        assert top_chunk.file == "src/models.py"
        assert top_chunk.start_line == 8
        assert top_chunk.end_line == 13
        assert top_chunk.language == "Python"
        assert top_chunk.type == "class"

    def test_chroma_metadata_preservation(self, fake_chunks: list[CodeChunk]) -> None:
        provider = FakeLLMProvider(dimensions=64)
        store = ChromaVectorStore(collection_name="test_metadata_collection")
        store.index(fake_chunks, provider=provider)

        results = store.search("create_app Flask", provider=provider, top_k=1)
        assert len(results) == 1
        chunk, _ = results[0]
        assert chunk.file == "src/app.py"
        assert chunk.start_line == 6
        assert chunk.end_line == 14
        assert chunk.entity == "create_app"
        assert chunk.type == "function"

    def test_chroma_persistent_storage(self, fake_chunks: list[CodeChunk], tmp_path: Path) -> None:
        chroma_dir = tmp_path / "chroma_db"
        provider = FakeLLMProvider(dimensions=64)

        store1 = ChromaVectorStore(persist_dir=chroma_dir, collection_name="persistent_chunks")
        store1.index(fake_chunks, provider=provider)

        # Reopen collection from persistent storage
        store2 = ChromaVectorStore(persist_dir=chroma_dir, collection_name="persistent_chunks")
        assert store2.load() is True
        results = store2.search("hash_file", provider=provider, top_k=1)
        assert len(results) == 1
        assert results[0][0].entity == "hash_file"

    def test_factory_fallback(self, tmp_path: Path) -> None:
        # Factory returns ChromaVectorStore by default
        store = create_vector_store(backend="chromadb")
        assert isinstance(store, ChromaVectorStore)

        # Explicit local backend returns LocalVectorStore
        store_local = create_vector_store(backend="local")
        assert isinstance(store_local, LocalVectorStore)
