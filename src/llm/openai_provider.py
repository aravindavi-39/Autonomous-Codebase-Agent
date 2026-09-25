"""OpenAI LLM and Embedding provider implementation."""

from __future__ import annotations

import os
from typing import Optional

from config.settings import get_settings
from llm.base import LLMConfigurationError, LLMError, LLMProvider
from utils.logger import setup_logger

logger = setup_logger(__name__)


class OpenAIProvider(LLMProvider):
    """OpenAI API integration for text generation and embeddings."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        embedding_model: str = "text-embedding-3-small",
    ) -> None:
        settings = get_settings()
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY") or settings.openai_api_key
        self.model = model
        self.embedding_model = embedding_model
        self._client = None

        if not self.api_key or not self.api_key.strip():
            logger.debug("OpenAI API key is not set.")

    def _get_client(self):
        if not self.api_key or not self.api_key.strip():
            raise LLMConfigurationError(
                "OpenAI API key is not configured. Please set the OPENAI_API_KEY environment "
                "variable in your environment or .env file, or run codebase-agent with --mock."
            )
        if self._client is None:
            try:
                import openai
                self._client = openai.OpenAI(api_key=self.api_key)
            except Exception as exc:
                raise LLMError(f"Failed to initialize OpenAI client: {exc}") from exc
        return self._client

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1000,
        temperature: float = 0.0,
    ) -> str:
        """Call OpenAI chat completion API."""
        client = self._get_client()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            choice = response.choices[0]
            return choice.message.content or ""
        except Exception as exc:
            raise LLMError(f"OpenAI completion failed: {exc}") from exc

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Call OpenAI embeddings API."""
        if not texts:
            return []

        client = self._get_client()
        try:
            response = client.embeddings.create(
                model=self.embedding_model,
                input=texts,
            )
            # Sort by index to maintain original order
            data = sorted(response.data, key=lambda item: item.index)
            return [item.embedding for item in data]
        except Exception as exc:
            raise LLMError(f"OpenAI embedding generation failed: {exc}") from exc
