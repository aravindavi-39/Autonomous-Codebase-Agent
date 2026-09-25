"""Retrieval package — semantic code chunking, vector storage, hybrid retrieval, and Q&A engine."""

from retrieval.chunker import CodeChunk, SemanticChunker
from retrieval.context_builder import BuiltContext, ContextBuilder
from retrieval.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from retrieval.qa_engine import QAEngine, QAResponse
from retrieval.retriever import HybridRetriever, RetrievalResult
from retrieval.vector_store import (
    BaseVectorStore,
    ChromaVectorStore,
    LocalVectorStore,
    create_vector_store,
)

__all__ = [
    "BaseVectorStore",
    "BuiltContext",
    "ChromaVectorStore",
    "CodeChunk",
    "ContextBuilder",
    "HybridRetriever",
    "LocalVectorStore",
    "create_vector_store",
    "QAEngine",
    "QAResponse",
    "RetrievalResult",
    "SYSTEM_PROMPT",
    "SemanticChunker",
    "USER_PROMPT_TEMPLATE",
]
