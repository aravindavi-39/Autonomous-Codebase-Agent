"""Vector store abstractions and implementations for semantic code retrieval.

Supports both in-memory/file-backed LocalVectorStore and persistent ChromaDB.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import json
import math
from pathlib import Path
from typing import Optional

from llm.base import LLMProvider
from retrieval.chunker import CodeChunk
from utils.logger import setup_logger
from utils.secrets import redact_secrets, sanitize_metadata

logger = setup_logger(__name__)


def _cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """Compute cosine similarity between two float vectors."""
    dot = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return dot / (norm1 * norm2)


class BaseVectorStore(ABC):
    """Abstract interface for code chunk vector stores."""

    @abstractmethod
    def index(self, chunks: list[CodeChunk], provider: LLMProvider) -> None:
        """Embed and index a list of CodeChunk objects."""
        pass

    @abstractmethod
    def search(
        self,
        query: str,
        provider: LLMProvider,
        top_k: int = 5,
    ) -> list[tuple[CodeChunk, float]]:
        """Search for top_k most similar chunks to query string."""
        pass

    @abstractmethod
    def persist(self) -> None:
        """Persist index to local storage if configured."""
        pass

    @abstractmethod
    def load(self) -> bool:
        """Load index from local storage if available."""
        pass


class LocalVectorStore(BaseVectorStore):
    """Lightweight in-memory vector store with optional JSON file persistence.

    Uses cosine similarity for semantic matching. Ideal for offline tests
    and fast in-memory indexing without heavy dependencies.
    """

    def __init__(self, persist_dir: Optional[Path] = None) -> None:
        self.persist_dir = persist_dir
        self.chunks: list[CodeChunk] = []
        self.embeddings: list[list[float]] = []

    def index(self, chunks: list[CodeChunk], provider: LLMProvider) -> None:
        """Embed and index a list of CodeChunk objects."""
        if not chunks:
            self.chunks.clear()
            self.embeddings.clear()
            return

        # Sanitize chunks to ensure no secrets enter vectors or metadata
        sanitized_chunks: list[CodeChunk] = []
        for c in chunks:
            clean_text = redact_secrets(c.text)
            clean_meta = sanitize_metadata(c.metadata)
            sanitized_chunks.append(
                CodeChunk(
                    text=clean_text,
                    file=c.file,
                    start_line=c.start_line,
                    end_line=c.end_line,
                    entity=c.entity,
                    type=c.type,
                    language=c.language,
                    metadata=clean_meta,
                )
            )

        self.chunks = sanitized_chunks
        texts = [c.text for c in self.chunks]
        logger.info("Generating embeddings for %d chunks...", len(texts))
        self.embeddings = provider.embed(texts)
        logger.info("Successfully indexed %d chunks in LocalVectorStore", len(self.chunks))

        if self.persist_dir:
            self.persist()

    def search(
        self,
        query: str,
        provider: LLMProvider,
        top_k: int = 5,
    ) -> list[tuple[CodeChunk, float]]:
        """Search for top_k most similar chunks using cosine similarity."""
        if not self.chunks or not self.embeddings:
            return []

        query_vecs = provider.embed([query])
        if not query_vecs:
            return []
        q_vec = query_vecs[0]

        scored: list[tuple[CodeChunk, float]] = []
        for chunk, emb in zip(self.chunks, self.embeddings):
            sim = _cosine_similarity(q_vec, emb)
            scored.append((chunk, sim))

        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:top_k]

    def persist(self) -> None:
        """Persist index to index.json in persist_dir."""
        if not self.persist_dir:
            return
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        file_path = self.persist_dir / "index.json"

        data = {
            "chunks": [c.model_dump() for c in self.chunks],
            "embeddings": self.embeddings,
        }
        file_path.write_text(json.dumps(data), encoding="utf-8")
        logger.debug("Persisted vector store to %s", file_path)

    def load(self) -> bool:
        """Load index from index.json if present."""
        if not self.persist_dir:
            return False
        file_path = self.persist_dir / "index.json"
        if not file_path.exists():
            return False

        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            self.chunks = [CodeChunk(**c) for c in data.get("chunks", [])]
            self.embeddings = data.get("embeddings", [])
            logger.info("Loaded %d chunks from %s", len(self.chunks), file_path)
            return True
        except Exception as exc:
            logger.warning("Failed to load cached vector store: %s", exc)
            return False


class ChromaVectorStore(BaseVectorStore):
    """Local, file-backed ChromaDB vector store.

    Stores embeddings, documents, and code location metadata in a local
    persistent or in-memory ChromaDB collection. Does not require external network access.
    """

    def __init__(
        self,
        persist_dir: Optional[Path] = None,
        collection_name: str = "codebase_chunks",
    ) -> None:
        self.persist_dir = persist_dir
        self.collection_name = collection_name
        self._chunks_cache: dict[str, CodeChunk] = {}

        try:
            import chromadb
            from chromadb.config import Settings as ChromaSettings

            if persist_dir:
                persist_dir.mkdir(parents=True, exist_ok=True)
                self.client = chromadb.PersistentClient(
                    path=str(persist_dir),
                    settings=ChromaSettings(anonymized_telemetry=False),
                )
            else:
                self.client = chromadb.EphemeralClient(
                    settings=ChromaSettings(anonymized_telemetry=False)
                )

            self.collection = self.client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        except Exception as exc:
            logger.error("Failed to initialize ChromaDB: %s", exc)
            raise

    def index(self, chunks: list[CodeChunk], provider: LLMProvider) -> None:
        """Embed chunks using provider and store in local ChromaDB collection."""
        if not chunks:
            return

        texts: list[str] = []
        ids: list[str] = []
        metadatas: list[dict[str, Any]] = []

        self._chunks_cache.clear()

        for idx, chunk in enumerate(chunks):
            chunk_id = f"chunk_{idx}_{chunk.file}:{chunk.start_line}-{chunk.end_line}"
            clean_text = redact_secrets(chunk.text)
            clean_meta = sanitize_metadata(chunk.metadata)

            meta: dict[str, Any] = {
                "file": chunk.file,
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
                "language": chunk.language,
                "chunk_type": chunk.type,
                "entity": chunk.entity or "",
            }
            # Add any extra scalar metadata
            for k, v in clean_meta.items():
                if isinstance(v, (str, int, float, bool)):
                    meta[k] = v

            sanitized_chunk = CodeChunk(
                text=clean_text,
                file=chunk.file,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
                entity=chunk.entity,
                type=chunk.type,
                language=chunk.language,
                metadata=clean_meta,
            )

            texts.append(clean_text)
            ids.append(chunk_id)
            metadatas.append(meta)
            self._chunks_cache[chunk_id] = sanitized_chunk

        logger.info("Generating embeddings for %d chunks with provider...", len(texts))
        embeddings = provider.embed(texts)

        # Upsert into Chroma collection
        self.collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )
        logger.info("Successfully indexed %d chunks in ChromaDB collection '%s'", len(chunks), self.collection_name)

    def search(
        self,
        query: str,
        provider: LLMProvider,
        top_k: int = 5,
    ) -> list[tuple[CodeChunk, float]]:
        """Search ChromaDB collection using cosine similarity with query embeddings."""
        total_items = self.collection.count()
        if total_items == 0:
            return []

        query_vecs = provider.embed([query])
        if not query_vecs:
            return []
        q_vec = query_vecs[0]

        n_results = min(top_k, total_items)
        results = self.collection.query(
            query_embeddings=[q_vec],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )

        scored: list[tuple[CodeChunk, float]] = []
        if not results or not results["ids"] or not results["ids"][0]:
            return []

        ret_ids = results["ids"][0]
        ret_docs = results["documents"][0] if results.get("documents") else []
        ret_metas = results["metadatas"][0] if results.get("metadatas") else []
        ret_dists = results["distances"][0] if results.get("distances") else []

        for chunk_id, doc, meta, dist in zip(ret_ids, ret_docs, ret_metas, ret_dists):
            # Chroma returns cosine distance in [0, 2], where 0 is identical
            similarity = max(0.0, min(1.0, 1.0 - float(dist)))

            if chunk_id in self._chunks_cache:
                chunk = self._chunks_cache[chunk_id]
            else:
                chunk = CodeChunk(
                    text=doc or "",
                    file=meta.get("file", ""),
                    start_line=int(meta.get("start_line", 1)),
                    end_line=int(meta.get("end_line", 1)),
                    entity=meta.get("entity") or None,
                    type=meta.get("chunk_type", "code"),
                    language=meta.get("language", "unknown"),
                    metadata=dict(meta),
                )
            scored.append((chunk, similarity))

        return scored

    def persist(self) -> None:
        """ChromaDB PersistentClient automatically persists data on write."""
        pass

    def load(self) -> bool:
        """Check if collection contains previously indexed chunks."""
        count = self.collection.count()
        return count > 0


def create_vector_store(
    persist_dir: Optional[Path] = None,
    backend: str = "chromadb",
) -> BaseVectorStore:
    """Factory creating vector store (ChromaVectorStore by default, falling back to LocalVectorStore)."""
    if backend.lower() == "chromadb":
        try:
            return ChromaVectorStore(persist_dir=persist_dir)
        except Exception as exc:
            logger.warning("ChromaDB initialization failed (%s), falling back to LocalVectorStore", exc)
            return LocalVectorStore(persist_dir=persist_dir)
    return LocalVectorStore(persist_dir=persist_dir)
