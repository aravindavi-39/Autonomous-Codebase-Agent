"""Structured models for source code citations."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class Citation(BaseModel):
    """Source citation identifying an exact file and line range."""

    file: str = Field(..., description="Repository-relative file path")
    start_line: int = Field(..., description="Starting line number (1-indexed)")
    end_line: int = Field(..., description="Ending line number (inclusive)")
    entity: Optional[str] = Field(None, description="Optional entity name (e.g. 'AuthService.authenticate')")
    snippet: Optional[str] = Field(None, description="Optional code snippet or context text")
    valid: bool = Field(True, description="Whether this citation has been verified against repository")
    reason: Optional[str] = Field(None, description="Validation failure reason if invalid")

    def format_citation(self, show_entity: bool = True) -> str:
        """Return formatted citation string e.g. '📄 src/models.py:8-13 (User)'."""
        loc = f"{self.file}:{self.start_line}-{self.end_line}"
        if self.start_line == self.end_line:
            loc = f"{self.file}:{self.start_line}"
        if show_entity and self.entity:
            return f"📄 {loc} ({self.entity})"
        return f"📄 {loc}"

    def to_compact_str(self) -> str:
        """Return clean citation string e.g. 'src/models.py:8-13'."""
        if self.start_line == self.end_line:
            return f"{self.file}:{self.start_line}"
        return f"{self.file}:{self.start_line}-{self.end_line}"


class CitationValidationResult(BaseModel):
    """Result of citation verification against repository structure."""

    valid_citations: list[Citation] = Field(default_factory=list)
    invalid_citations: list[Citation] = Field(default_factory=list)
    fallback_used: bool = Field(False, description="Whether fallback retrieved citations were injected")
