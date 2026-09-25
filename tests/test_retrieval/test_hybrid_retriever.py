"""Tests for HybridRetriever combining vector search with graph traversal (Check 2 compliance)."""

from pathlib import Path
import pytest

from analysis.analyzer import RepositoryAnalyzer
from analysis.graph_builder import CodeGraphBuilder
from analysis.graph_models import RelationshipType
from llm.fake_provider import FakeLLMProvider
from retrieval.chunker import SemanticChunker
from retrieval.context_builder import ContextBuilder
from retrieval.retriever import HybridRetriever
from retrieval.vector_store import LocalVectorStore


@pytest.fixture
def sample_repo_path() -> Path:
    return Path(__file__).resolve().parent.parent / "fixtures" / "sample_repo"


@pytest.fixture
def retriever_setup(sample_repo_path: Path):
    analyzer = RepositoryAnalyzer()
    code_index = analyzer.analyze_repository(str(sample_repo_path))
    builder = CodeGraphBuilder()
    graph = builder.build_graph(code_index)

    chunker = SemanticChunker(root_path=sample_repo_path)
    chunks = chunker.chunk_repository(manifest=code_index.manifest, code_index=code_index)

    provider = FakeLLMProvider()
    store = LocalVectorStore()
    store.index(chunks, provider=provider)

    retriever = HybridRetriever(
        vector_store=store,
        code_graph=graph,
        code_index=code_index,
    )
    return retriever, provider, graph


class TestHybridRetriever:
    """Verify hybrid retrieval functionality and flags."""

    def test_semantic_retrieval_flag(self, retriever_setup) -> None:
        retriever, provider, _ = retriever_setup
        result = retriever.retrieve(
            "How does user model work?",
            provider=provider,
            top_k=3,
            enable_semantic=True,
            enable_graph=False,
        )
        assert len(result.semantic_chunks) > 0
        assert len(result.structural_nodes) == 0
        assert len(result.structural_edges) == 0

    def test_structural_retrieval_flag(self, retriever_setup) -> None:
        retriever, provider, _ = retriever_setup
        result = retriever.retrieve(
            "Tell me about create_app",
            provider=provider,
            top_k=3,
            enable_semantic=False,
            enable_graph=True,
        )
        assert len(result.semantic_chunks) == 0
        assert len(result.structural_nodes) > 0
        node_names = [n.name for n in result.structural_nodes]
        assert any("create_app" in name for name in node_names)

    def test_hybrid_both_contribute(self, retriever_setup) -> None:
        retriever, provider, _ = retriever_setup
        result = retriever.retrieve(
            "hash_file SHA-256 digest utility",
            provider=provider,
            top_k=3,
            enable_semantic=True,
            enable_graph=True,
        )
        # Both semantic and structural contribute
        assert len(result.semantic_chunks) > 0
        assert len(result.structural_nodes) > 0

        # ContextBuilder contains sections from both
        builder = ContextBuilder()
        built = builder.build_context(result)
        assert "[Code and Documentation Chunks]:" in built.context_text
        assert len(built.citations) > 0

    def test_class_intent_structural_retrieval(self, retriever_setup) -> None:
        retriever, provider, _ = retriever_setup
        result = retriever.retrieve(
            "What classes exist?",
            provider=provider,
            top_k=5,
            enable_semantic=False,
            enable_graph=True,
        )
        assert len(result.structural_nodes) > 0
        names = [n.name for n in result.structural_nodes]
        assert "User" in names or "Post" in names

    def test_structural_expansion_does_not_invent_relationships(self, retriever_setup) -> None:
        retriever, provider, graph = retriever_setup
        result = retriever.retrieve(
            "create_app",
            provider=provider,
            top_k=5,
            enable_semantic=True,
            enable_graph=True,
        )
        # Every edge in result.structural_edges must be a real edge from graph
        graph_edge_set = {(e.source, e.target, e.type) for e in graph.edges}
        for edge in result.structural_edges:
            assert (edge.source, edge.target, edge.type) in graph_edge_set

    def test_unresolved_graph_relationships_remain_unresolved(self, retriever_setup) -> None:
        retriever, provider, graph = retriever_setup
        result = retriever.retrieve(
            "import os sys json",
            provider=provider,
            enable_semantic=False,
            enable_graph=True,
        )
        # Standard library or external imports do not create fake internal nodes
        for node in result.structural_nodes:
            assert graph.get_node(node.id) is not None

    def test_retrieval_deduplication(self, retriever_setup) -> None:
        retriever, provider, _ = retriever_setup
        result = retriever.retrieve(
            "create_app Flask application",
            provider=provider,
            top_k=10,
            enable_semantic=True,
            enable_graph=True,
        )
        # Chunks are deduplicated by file, start_line, end_line
        seen_chunks = set()
        for chunk, _ in result.semantic_chunks:
            key = (chunk.file, chunk.start_line, chunk.end_line)
            assert key not in seen_chunks
            seen_chunks.add(key)

    def test_unrelated_query(self, retriever_setup) -> None:
        retriever, provider, _ = retriever_setup
        result = retriever.retrieve(
            "quantum teleportation warp drive",
            provider=provider,
            top_k=2,
            enable_semantic=True,
            enable_graph=True,
        )
        assert len(result.structural_nodes) == 0
