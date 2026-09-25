"""Hybrid retrieval combining semantic vector search and structural graph traversal."""

from __future__ import annotations

import re
from typing import Optional

from analysis.graph_models import CodeGraph, GraphNode, NodeType, RelationshipEdge, RelationshipType
from analysis.models import RepositoryCodeIndex
from llm.base import LLMProvider
from retrieval.chunker import CodeChunk
from retrieval.vector_store import BaseVectorStore
from utils.logger import setup_logger

logger = setup_logger(__name__)

# Common stop words to ignore when extracting concept keywords
STOP_WORDS = {
    "a", "an", "the", "in", "on", "at", "to", "for", "of", "with", "by",
    "from", "about", "into", "through", "during", "before", "after", "above",
    "below", "under", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "can", "could", "should",
    "would", "may", "might", "must", "shall", "will", "what", "which",
    "who", "whom", "this", "that", "these", "those", "how", "why", "where",
    "when", "work", "explain", "describe", "show", "tell", "me", "give",
    "all", "exist", "any", "some", "code", "application", "project",
}


class RetrievalResult:
    """Container holding results from both semantic and structural retrieval."""

    def __init__(
        self,
        query: str,
        semantic_chunks: list[tuple[CodeChunk, float]],
        structural_nodes: list[GraphNode],
        structural_edges: list[RelationshipEdge],
    ) -> None:
        self.query = query
        self.semantic_chunks = semantic_chunks
        self.structural_nodes = structural_nodes
        self.structural_edges = structural_edges


class HybridRetriever:
    """Coordinates semantic search and graph-based structural retrieval."""

    def __init__(
        self,
        vector_store: BaseVectorStore,
        code_graph: Optional[CodeGraph] = None,
        code_index: Optional[RepositoryCodeIndex] = None,
    ) -> None:
        self.vector_store = vector_store
        self.code_graph = code_graph
        self.code_index = code_index

    def retrieve(
        self,
        question: str,
        provider: LLMProvider,
        top_k: int = 5,
        enable_semantic: bool = True,
        enable_graph: bool = True,
    ) -> RetrievalResult:
        """Perform hybrid retrieval on user question with deduplication and source locations."""
        logger.info(
            "Retrieving context for query: '%s' (semantic=%s, graph=%s)",
            question,
            enable_semantic,
            enable_graph,
        )

        semantic_results: list[tuple[CodeChunk, float]] = []
        if enable_semantic:
            raw_semantic = self.vector_store.search(question, provider, top_k=top_k)
            # Deduplicate semantic results
            seen_chunks: set[tuple[str, int, int]] = set()
            for chunk, score in raw_semantic:
                key = (chunk.file, chunk.start_line, chunk.end_line)
                if key not in seen_chunks:
                    seen_chunks.add(key)
                    semantic_results.append((chunk, score))

        structural_nodes: list[GraphNode] = []
        structural_edges: list[RelationshipEdge] = []
        if enable_graph and self.code_graph:
            structural_nodes, structural_edges = self._retrieve_structural(question)

        return RetrievalResult(
            query=question,
            semantic_chunks=semantic_results,
            structural_nodes=structural_nodes,
            structural_edges=structural_edges,
        )

    def _retrieve_structural(
        self, question: str
    ) -> tuple[list[GraphNode], list[RelationshipEdge]]:
        """Query CodeGraph for nodes and relationships matching question concepts."""
        if not self.code_graph:
            return [], []

        keywords = self._extract_keywords(question)
        low_q = question.lower()
        matching_nodes: set[str] = set()

        # Check for entity-type intent
        match_classes = "class" in low_q or "classes" in low_q
        match_funcs = "function" in low_q or "functions" in low_q or "def" in low_q
        match_methods = "method" in low_q or "methods" in low_q
        match_files = "file" in low_q or "files" in low_q or "module" in low_q

        # 1. Direct name, type, and keyword matching on graph nodes
        for node in self.code_graph.nodes:
            # Type-level matches
            if match_classes and node.type == NodeType.CLASS:
                matching_nodes.add(node.id)
                continue
            if match_funcs and node.type == NodeType.FUNCTION:
                matching_nodes.add(node.id)
                continue
            if match_methods and node.type == NodeType.METHOD:
                matching_nodes.add(node.id)
                continue
            if match_files and node.type in (NodeType.FILE, NodeType.MODULE):
                matching_nodes.add(node.id)
                continue

            low_name = node.name.lower()
            low_file = (node.file or "").lower()

            if any(kw in low_name or (kw in low_file and len(kw) > 3) for kw in keywords):
                matching_nodes.add(node.id)

        # 2. Graph expansion along key verified relationships (never invent edges)
        expanded_nodes: set[str] = set(matching_nodes)
        relevant_edges: list[RelationshipEdge] = []
        seen_edges: set[tuple[str, str, str]] = set()

        for edge in self.code_graph.edges:
            s_match = edge.source in matching_nodes
            t_match = edge.target in matching_nodes

            # Expand calls, definitions, inheritance, dependencies, tests
            if s_match or t_match:
                if edge.type in (
                    RelationshipType.CALLS,
                    RelationshipType.DEFINES,
                    RelationshipType.INHERITS,
                    RelationshipType.DEPENDS_ON,
                    RelationshipType.TESTS,
                    RelationshipType.IMPORTS,
                ):
                    edge_key = (edge.source, edge.target, edge.type.value)
                    if edge_key not in seen_edges:
                        seen_edges.add(edge_key)
                        relevant_edges.append(edge)
                        expanded_nodes.add(edge.source)
                        expanded_nodes.add(edge.target)

        # Gather real internal node objects; unresolved external references stay unresolved
        nodes_result: list[GraphNode] = []
        for nid in expanded_nodes:
            n = self.code_graph.get_node(nid)
            if n:
                nodes_result.append(n)

        # Limit structural size to avoid overwhelming context
        return nodes_result[:25], relevant_edges[:30]

    def _extract_keywords(self, question: str) -> list[str]:
        """Extract meaningful alphanumeric search tokens from question."""
        tokens = re.findall(r"\w+", question.lower())
        keywords = [t for t in tokens if t not in STOP_WORDS and len(t) > 2]
        return keywords
