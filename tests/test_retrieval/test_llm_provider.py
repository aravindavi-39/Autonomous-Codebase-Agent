"""Tests for LLM provider abstraction, fake provider, and configuration handling."""

import pytest

from llm.base import LLMConfigurationError, LLMProvider
from llm.fake_provider import FakeLLMProvider
from llm.openai_provider import OpenAIProvider


class TestLLMProviders:
    """Verify provider abstractions and error handling without external API calls."""

    def test_fake_llm_provider_generate(self) -> None:
        provider = FakeLLMProvider()
        assert isinstance(provider, LLMProvider)

        # Grounded generation from context
        prompt = "Repository Context:\n- src/models.py:8-13 (User)\nQuestion: What is User?"
        answer = provider.generate(prompt)
        assert "User" in answer
        assert "src/models.py:8-13" in answer
        assert provider.call_count == 1

    def test_fake_llm_provider_empty_context(self) -> None:
        provider = FakeLLMProvider()
        prompt = "Question: What is secret sauce?"
        answer = provider.generate(prompt)
        assert "does not contain enough information" in answer

    def test_fake_llm_provider_default_response(self) -> None:
        provider = FakeLLMProvider(default_response="Custom mock answer with citations")
        answer = provider.generate("any prompt")
        assert answer == "Custom mock answer with citations"

    def test_fake_llm_provider_embeddings(self) -> None:
        provider = FakeLLMProvider(dimensions=32)
        texts = ["create user account", "user authentication", "hash password"]
        vecs = provider.embed(texts)
        assert len(vecs) == 3
        for v in vecs:
            assert len(v) == 32
            # Check L2 normalization
            norm = sum(x * x for x in v)
            assert abs(norm - 1.0) < 1e-4

        # Empty texts
        assert provider.embed([]) == []

    def test_openai_provider_missing_key_raises_configuration_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        provider = OpenAIProvider(api_key="")
        with pytest.raises(LLMConfigurationError) as exc_info:
            provider.generate("Hello")
        assert "OpenAI API key is not configured" in str(exc_info.value)
        assert "--mock" in str(exc_info.value)

    def test_openai_provider_embed_missing_key_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        provider = OpenAIProvider(api_key="")
        with pytest.raises(LLMConfigurationError):
            provider.embed(["test"])
