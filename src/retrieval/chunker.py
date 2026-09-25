"""Semantic code and documentation chunker.

Produces meaningful chunks based on AST classes, functions, and documentation
sections while strictly preserving file and line range information and redacting secrets.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

from analysis.models import ClassInfo, FileAnalysis, FunctionInfo, RepositoryCodeIndex
from ingestion.discoverer import _is_secret_file
from ingestion.models import FileRecord, Language, RepositoryManifest
from ingestion.reader import read_file_text
from utils.logger import setup_logger
from utils.secrets import redact_secrets, sanitize_metadata

logger = setup_logger(__name__)


class CodeChunk(BaseModel):
    """A semantic chunk of code or documentation with exact source location."""

    text: str = Field(..., description="Text content of the chunk")
    file: str = Field(..., description="Repository-relative file path")
    start_line: int = Field(..., description="Starting line in file (1-indexed)")
    end_line: int = Field(..., description="Ending line in file (inclusive)")
    entity: Optional[str] = Field(None, description="Name of the entity (e.g. class or function)")
    type: str = Field(..., description="Chunk category: 'function' | 'method' | 'class' | 'module' | 'documentation'")
    language: str = Field("unknown", description="Programming or markup language")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional context")

    def to_citation_str(self) -> str:
        """Return citation header e.g. '📄 src/models.py:8-13 (User)'."""
        if self.entity:
            return f"📄 {self.file}:{self.start_line}-{self.end_line} ({self.entity})"
        return f"📄 {self.file}:{self.start_line}-{self.end_line}"


class SemanticChunker:
    """Extracts semantic code and documentation chunks from an analyzed repository."""

    def __init__(self, root_path: Path) -> None:
        self.root_path = root_path

    def chunk_repository(
        self,
        manifest: RepositoryManifest,
        code_index: Optional[RepositoryCodeIndex] = None,
    ) -> list[CodeChunk]:
        """Generate semantic chunks for all valid source and documentation files."""
        chunks: list[CodeChunk] = []

        # Map file analyses by relative path
        analyses_by_file: dict[str, FileAnalysis] = {}
        if code_index:
            for fa in code_index.file_analyses:
                analyses_by_file[fa.file_path] = fa

        for file_rec in manifest.files:
            # Skip ignored, binary, secret, or empty files
            if (
                file_rec.metadata.is_binary
                or file_rec.metadata.size_bytes == 0
                or _is_secret_file(file_rec.file_name, file_rec.extension)
            ):
                continue

            rel_path = file_rec.relative_path
            abs_path = self.root_path / rel_path

            # Read file lines
            content = read_file_text(abs_path)
            if content is None:
                continue
            lines = content.splitlines()

            # Python files with AST analysis
            if file_rec.language == Language.PYTHON and rel_path in analyses_by_file:
                fa = analyses_by_file[rel_path]
                if fa.status == "ok":
                    chunks.extend(self._chunk_python_file(fa, file_rec, lines))
                    continue

            # Documentation files
            if file_rec.is_documentation or file_rec.language == Language.MARKDOWN:
                chunks.extend(self._chunk_documentation_file(file_rec, lines))
                continue

            # Fallback for small configuration or source files
            clean_text = redact_secrets(content[:2000])
            chunks.append(
                CodeChunk(
                    text=clean_text,
                    file=rel_path,
                    start_line=1,
                    end_line=len(lines),
                    entity=file_rec.file_name,
                    type="module",
                    language=file_rec.language.value,
                )
            )

        logger.info("Generated %d semantic chunks across repository", len(chunks))
        return chunks

    def _chunk_python_file(
        self,
        fa: FileAnalysis,
        file_rec: FileRecord,
        lines: list[str],
    ) -> list[CodeChunk]:
        chunks: list[CodeChunk] = []
        fp = file_rec.relative_path

        # 1. Module overview chunk (if docstring or top-level imports exist)
        if fa.docstring or fa.imports:
            imp_summary = ", ".join(i.module for i in fa.imports[:8])
            doc = fa.docstring or "Python module"
            text = f"Module: {fp}\nDocstring: {doc}\nImports: {imp_summary}"
            chunks.append(
                CodeChunk(
                    text=redact_secrets(text),
                    file=fp,
                    start_line=1,
                    end_line=min(15, len(lines)),
                    entity=file_rec.file_name,
                    type="module",
                    language="Python",
                )
            )

        # 2. Classes
        for cls in fa.classes:
            end_line = cls.end_line or (cls.start_line + 5)
            class_slice = lines[cls.start_line - 1 : end_line]
            class_text = "\n".join(class_slice)
            method_names = [m.name for m in cls.methods]
            summary = f"Class: {cls.name}\nBases: {cls.base_classes}\nMethods: {method_names}\nCode:\n{class_text}"
            chunks.append(
                CodeChunk(
                    text=redact_secrets(summary),
                    file=fp,
                    start_line=cls.start_line,
                    end_line=end_line,
                    entity=cls.name,
                    type="class",
                    language="Python",
                )
            )

            # Class methods
            for m in cls.methods:
                m_end = m.end_line or (m.start_line + 5)
                m_text = "\n".join(lines[m.start_line - 1 : m_end])
                entity_name = f"{cls.name}.{m.name}"
                chunks.append(
                    CodeChunk(
                        text=redact_secrets(f"Method: {entity_name}\nDocstring: {m.docstring}\n{m_text}"),
                        file=fp,
                        start_line=m.start_line,
                        end_line=m_end,
                        entity=entity_name,
                        type="method",
                        language="Python",
                    )
                )

        # 3. Top-level Functions
        for fn in fa.functions:
            fn_end = fn.end_line or (fn.start_line + 5)
            fn_text = "\n".join(lines[fn.start_line - 1 : fn_end])
            chunks.append(
                CodeChunk(
                    text=redact_secrets(f"Function: {fn.name}\nDocstring: {fn.docstring}\n{fn_text}"),
                    file=fp,
                    start_line=fn.start_line,
                    end_line=fn_end,
                    entity=fn.name,
                    type="function",
                    language="Python",
                )
            )

        return chunks

    def _chunk_documentation_file(
        self,
        file_rec: FileRecord,
        lines: list[str],
    ) -> list[CodeChunk]:
        chunks: list[CodeChunk] = []
        fp = file_rec.relative_path

        header_indices: list[tuple[int, str]] = []
        for idx, line in enumerate(lines, 1):
            if re.match(r"^#{1,3}\s+", line):
                header_indices.append((idx, line.strip()))

        if not header_indices:
            # Single chunk for doc
            chunks.append(
                CodeChunk(
                    text=redact_secrets("\n".join(lines[:200])),
                    file=fp,
                    start_line=1,
                    end_line=min(200, len(lines)),
                    entity=file_rec.file_name,
                    type="documentation",
                    language=file_rec.language.value,
                )
            )
            return chunks

        for i, (start, title) in enumerate(header_indices):
            end = (header_indices[i + 1][0] - 1) if (i + 1 < len(header_indices)) else len(lines)
            section_text = "\n".join(lines[start - 1 : end])
            clean_title = title.lstrip("#").strip()
            chunks.append(
                CodeChunk(
                    text=redact_secrets(f"Section: {clean_title}\n{section_text}"),
                    file=fp,
                    start_line=start,
                    end_line=end,
                    entity=clean_title,
                    type="documentation",
                    language=file_rec.language.value,
                )
            )

        return chunks
