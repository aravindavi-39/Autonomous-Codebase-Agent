"""Base interface for LLM and embedding providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class LLMError(Exception):
    """Base exception for LLM provider errors."""


class LLMConfigurationError(LLMError):
    """Raised when an LLM provider is misconfigured (e.g. missing API key)."""


class LLMProvider(ABC):
    """Abstract interface for LLM text generation and vector embeddings."""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1000,
        temperature: float = 0.0,
    ) -> str:
        """Generate a text completion given a prompt and optional system prompt."""

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate vector embeddings for a list of text strings."""
