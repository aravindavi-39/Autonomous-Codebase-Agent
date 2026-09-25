"""Builds bounded, structured context for LLM question-answering with secret redaction."""

from __future__ import annotations

from typing import Optional

from citations.models import Citation
from retrieval.chunker import CodeChunk
from retrieval.retriever import RetrievalResult
from utils.logger import setup_logger
from utils.secrets import redact_secrets

logger = setup_logger(__name__)


class BuiltContext:
    """Formatted prompt context accompanied by verified source citations."""

    def __init__(
        self,
        context_text: str,
        citations: list[Citation],
        total_chunks: int,
    ) -> None:
        self.context_text = context_text
        self.citations = citations
        self.total_chunks = total_chunks


class ContextBuilder:
    """Assembles retrieved semantic and structural information within strict token/character bounds."""

    def __init__(
        self,
        max_chunks: int = 5,
        max_context_chars: int = 12000,
        max_relationships: int = 15,
        max_entities: int = 20,
    ) -> None:
        self.max_chunks = max_chunks
        self.max_context_chars = max_context_chars
        self.max_relationships = max_relationships
        self.max_entities = max_entities

    def build_context(self, result: RetrievalResult) -> BuiltContext:
        """Construct prompt context string and extract verified source citations."""
        sections: list[str] = ["=== Repository Context ==="]
        raw_citations: list[Citation] = []
        chars_remaining = self.max_context_chars - 500

        # 1. Structural Code Entities section
        if result.structural_nodes:
            entity_lines = ["\n[Structural Code Entities]:"]
            for node in result.structural_nodes[: self.max_entities]:
                if not node.file or not node.start_line:
                    continue
                end_l = node.end_line or node.start_line
                entity_lines.append(
                    f"- {node.type.value.upper()}: {node.name} (📄 {node.file}:{node.start_line}-{end_l})"
                )
                raw_citations.append(
                    Citation(
                        file=node.file,
                        start_line=node.start_line,
                        end_line=end_l,
                        entity=node.name,
                    )
                )

            entity_block = "\n".join(entity_lines)
            if len(entity_block) < chars_remaining:
                sections.append(entity_block)
                chars_remaining -= len(entity_block)

        # 2. Structural Graph Relationships section
        if result.structural_edges:
            rel_lines = ["\n[Code Relationships]:"]
            for edge in result.structural_edges[: self.max_relationships]:
                src = edge.source.split(":")[-1]
                tgt = edge.target.split(":")[-1]
                line_info = f" (at {edge.file}:{edge.line})" if edge.line else ""
                rel_lines.append(f"- {src} --[{edge.type.value}]--> {tgt}{line_info}")
                if edge.file and edge.line > 0:
                    raw_citations.append(
                        Citation(
                            file=edge.file,
                            start_line=edge.line,
                            end_line=edge.line,
                            entity=src,
                        )
                    )

            rel_block = "\n".join(rel_lines)
            if len(rel_block) < chars_remaining:
                sections.append(rel_block)
                chars_remaining -= len(rel_block)

        # 3. Semantic Code & Documentation Chunks section
        if result.semantic_chunks:
            sections.append("\n[Code and Documentation Chunks]:")
            for chunk, score in result.semantic_chunks[: self.max_chunks]:
                header = chunk.to_citation_str()
                block = f"\n--- {header} (Relevance: {score:.2f}) ---\n{chunk.text}\n"

                if chars_remaining <= 50:
                    break

                if len(block) > chars_remaining:
                    block = block[:chars_remaining] + "\n[... truncated ...]\n"

                sections.append(block)
                chars_remaining -= len(block)

                raw_citations.append(
                    Citation(
                        file=chunk.file,
                        start_line=chunk.start_line,
                        end_line=chunk.end_line,
                        entity=chunk.entity,
                        snippet=chunk.text[:200],
                    )
                )

        full_context = "\n".join(sections)
        # Redact any residual secrets from the assembled context before sending to LLM
        full_context = redact_secrets(full_context)

        # Deduplicate citations preserving first-seen order
        deduped_citations: list[Citation] = []
        seen_keys: set[tuple[str, int, int, Optional[str]]] = set()
        for c in raw_citations:
            norm_file = c.file.replace("\\", "/")
            key = (norm_file, c.start_line, c.end_line, c.entity)
            if key not in seen_keys:
                seen_keys.add(key)
                deduped_citations.append(c)

        logger.debug(
            "Built context with %d characters, %d citations",
            len(full_context),
            len(deduped_citations),
        )

        return BuiltContext(
            context_text=full_context,
            citations=deduped_citations,
            total_chunks=len(result.semantic_chunks),
        )
