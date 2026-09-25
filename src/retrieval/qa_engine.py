"""Question-Answering Engine coordinating hybrid retrieval, LLM generation, and citation validation."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from citations.models import Citation
from citations.validator import CitationValidator
from llm.base import LLMProvider
from retrieval.context_builder import ContextBuilder
from retrieval.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from retrieval.retriever import HybridRetriever
from utils.logger import setup_logger
from utils.secrets import redact_secrets

logger = setup_logger(__name__)


class QAResponse(BaseModel):
    """Grounded answer to a codebase question with verified source citations."""

    question: str
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    fallback_citations_used: bool = False

    def clean_answer_text(self) -> str:
        """Return answer text without any trailing raw Sources: block."""
        parts = self.answer.split("Sources:")
        return parts[0].strip()

    def format_output(self) -> str:
        """Format the complete output for display."""
        clean_text = self.clean_answer_text()
        lines = [
            f"Question:\n{self.question}\n",
            f"Answer:\n\n{clean_text}\n",
        ]

        if self.citations:
            lines.append("Sources:")
            for c in self.citations:
                lines.append(c.format_citation())
        else:
            lines.append("Sources: None")

        return "\n".join(lines)


class QAEngine:
    """Orchestrates hybrid retrieval, LLM response generation, and citation verification."""

    def __init__(
        self,
        retriever: HybridRetriever,
        llm_provider: LLMProvider,
        citation_validator: CitationValidator,
        context_builder: Optional[ContextBuilder] = None,
    ) -> None:
        self.retriever = retriever
        self.llm_provider = llm_provider
        self.citation_validator = citation_validator
        self.context_builder = context_builder or ContextBuilder()

    def ask(
        self,
        question: str,
        top_k: int = 5,
        max_context_chars: int = 12000,
        enable_semantic: bool = True,
        enable_graph: bool = True,
    ) -> QAResponse:
        """Answer a natural language question about the repository with verified citations."""
        logger.info("Answering question: '%s'", question)
        self.context_builder.max_context_chars = max_context_chars

        # 1. Hybrid Retrieval
        retrieval_result = self.retriever.retrieve(
            question=question,
            provider=self.llm_provider,
            top_k=top_k,
            enable_semantic=enable_semantic,
            enable_graph=enable_graph,
        )

        # 2. Context Building
        built_context = self.context_builder.build_context(retrieval_result)

        # 3. Prompt Construction
        prompt = USER_PROMPT_TEMPLATE.format(
            context=built_context.context_text,
            question=question,
        )

        # 4. LLM Generation
        raw_answer = self.llm_provider.generate(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
        )

        # Redact any secrets from raw answer to ensure no leaked keys/tokens
        safe_answer = redact_secrets(raw_answer)

        # 5. Citation Extraction and Validation against retrieved context
        extracted_citations = self.citation_validator.extract_citations_from_text(safe_answer)
        validation_result = self.citation_validator.validate_citations(
            citations=extracted_citations,
            fallback_citations=built_context.citations,
            allowed_sources=built_context.citations,
        )

        return QAResponse(
            question=question,
            answer=safe_answer,
            citations=validation_result.valid_citations,
            fallback_citations_used=validation_result.fallback_used,
        )
