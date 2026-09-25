"""Tests for ContextBuilder bounding context size and extracting citations."""

import pytest

from analysis.graph_models import RelationshipEdge, RelationshipType
from retrieval.chunker import CodeChunk
from retrieval.context_builder import ContextBuilder
from retrieval.retriever import RetrievalResult


class TestContextBuilder:
    """Verify context assembly within strict token/character limits."""

    def test_context_building_with_citations(self) -> None:
        chunk = CodeChunk(
            text="class User:\n    id: int",
            file="src/models.py",
            start_line=8,
            end_line=13,
            entity="User",
            type="class",
        )
        edge = RelationshipEdge(
            source="file:src/app.py",
            target="file:src/models.py",
            type=RelationshipType.DEPENDS_ON,
            file="src/app.py",
            line=5,
        )

        res = RetrievalResult(
            query="User model",
            semantic_chunks=[(chunk, 0.9)],
            structural_nodes=[],
            structural_edges=[edge],
        )

        builder = ContextBuilder(max_chunks=2, max_context_chars=5000)
        built = builder.build_context(res)

        assert "Repository Context" in built.context_text
        assert "src/models.py:8-13 (User)" in built.context_text
        assert "src/app.py --[DEPENDS_ON]--> src/models.py" in built.context_text
        assert len(built.citations) == 2

    def test_strict_character_limit_respected(self) -> None:
        long_chunk = CodeChunk(
            text="x" * 2000,
            file="src/large.py",
            start_line=1,
            end_line=100,
            type="module",
        )
        res = RetrievalResult(
            query="test",
            semantic_chunks=[(long_chunk, 0.8), (long_chunk, 0.7)],
            structural_nodes=[],
            structural_edges=[],
        )

        # Very small context limit
        builder = ContextBuilder(max_chunks=5, max_context_chars=1200)
        built = builder.build_context(res)
        assert len(built.context_text) <= 1500
