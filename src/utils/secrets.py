"""Secret detection and sanitization utilities for safe ingestion and retrieval."""

from __future__ import annotations

import re
from typing import Any

# Regular expression patterns for common sensitive credentials and tokens
SECRET_PATTERNS: list[re.Pattern] = [
    # OpenAI API keys
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_\-]{20,}"),
    # AWS access keys
    re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    # Private RSA / EC / OpenSSH keys
    re.compile(r"-----BEGIN [A-Z ]+ PRIVATE KEY-----[\s\S]*?-----END [A-Z ]+ PRIVATE KEY-----"),
    # Bearer tokens
    re.compile(r"\bBearer\s+[A-Za-z0-9_.\-]{20,}\b"),
    # Generic key / secret / password assignments: key = "value"
    re.compile(
        r"""(?i)(?P<prefix>(?:api[_-]?key|access[_-]?token|auth[_-]?token|secret[_-]?key|secret|password|passwd|client[_-]?secret)\s*[:=]\s*['"])(?P<secret>[^\s'"]{8,})(?P<suffix>['"])"""
    ),
]


def contains_secrets(text: str) -> bool:
    """Return True if text appears to contain sensitive credentials or keys."""
    if not text:
        return False
    for pat in SECRET_PATTERNS:
        if pat.search(text):
            return True
    return False


def redact_secrets(text: str) -> str:
    """Replace sensitive keys, tokens, and passwords with '[REDACTED_SECRET]'."""
    if not text:
        return text

    redacted = text
    # 1. Private keys
    redacted = re.sub(
        r"-----BEGIN [A-Z ]+ PRIVATE KEY-----[\s\S]*?-----END [A-Z ]+ PRIVATE KEY-----",
        "[REDACTED_PRIVATE_KEY]",
        redacted,
    )
    # 2. OpenAI keys
    redacted = re.sub(r"sk-(?:proj-)?[A-Za-z0-9_\-]{20,}", "[REDACTED_API_KEY]", redacted)
    # 3. AWS keys
    redacted = re.sub(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b", "[REDACTED_AWS_KEY]", redacted)
    # 4. Bearer tokens
    redacted = re.sub(r"\bBearer\s+[A-Za-z0-9_.\-]{20,}\b", "Bearer [REDACTED_TOKEN]", redacted)
    # 5. Key/Password assignments
    def _sub_assign(match: re.Match) -> str:
        return f"{match.group('prefix')}[REDACTED_SECRET]{match.group('suffix')}"

    redacted = re.sub(
        r"""(?i)(?P<prefix>(?:api[_-]?key|access[_-]?token|auth[_-]?token|secret[_-]?key|secret|password|passwd|client[_-]?secret)\s*[:=]\s*['"])(?P<secret>[^\s'"]{8,})(?P<suffix>['"])""",
        _sub_assign,
        redacted,
    )

    return redacted


def sanitize_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Sanitize all string values within metadata dict to ensure no secrets are stored."""
    clean: dict[str, Any] = {}
    for k, v in metadata.items():
        if isinstance(v, str):
            clean[k] = redact_secrets(v)
        elif isinstance(v, dict):
            clean[k] = sanitize_metadata(v)
        else:
            clean[k] = v
    return clean
