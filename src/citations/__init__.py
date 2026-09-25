"""Citation package — structured models and verification for codebase source citations."""

from citations.models import Citation, CitationValidationResult
from citations.validator import CitationValidator

__all__ = [
    "Citation",
    "CitationValidationResult",
    "CitationValidator",
]
