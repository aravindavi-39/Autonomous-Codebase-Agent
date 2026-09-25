"""Citation verification and validation against codebase structure."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Union

from analysis.models import RepositoryCodeIndex
from citations.models import Citation, CitationValidationResult
from ingestion.models import RepositoryManifest
from utils.logger import setup_logger

logger = setup_logger(__name__)

# Regex patterns to parse citations from LLM output:
# Examples:
# - src/auth/service.py:31-58
# - `src/auth/service.py:31-58`
# - 📄 src/auth/service.py:31-58 (AuthService.authenticate)
CITATION_PATTERN = re.compile(
    r"(?:📄\s*)?`?([a-zA-Z0-9_\-./\\]+\.[a-zA-Z0-9_]+):(\d+)(?:-(\d+))?`?(?:\s*\(([^)]+)\))?"
)


class CitationValidator:
    """Validates citations against the repository files, AST index, and retrieved context."""

    def __init__(
        self,
        manifest: RepositoryManifest,
        code_index: Optional[RepositoryCodeIndex] = None,
    ) -> None:
        self.manifest = manifest
        self.code_index = code_index

        # Index files for quick existence and line count checks
        self._file_records = {
            f.relative_path.replace("\\", "/"): f for f in manifest.files
        }

    def validate_citation(
        self,
        citation: Citation,
        allowed_sources: Optional[Union[list[Citation], set[str], list[str]]] = None,
    ) -> Citation:
        """Validate a single Citation against the codebase and retrieval context.

        Checks:
        1. File exists in repository manifest
        2. Line numbers are within physical file bounds
        3. If entity is specified, entity must be defined in file AST (when code_index is present)
        4. If allowed_sources is provided, cited file must correspond to actually retrieved context
        """
        norm_path = citation.file.replace("\\", "/")

        # 1. File existence
        if norm_path not in self._file_records:
            citation.valid = False
            citation.reason = f"File '{citation.file}' does not exist in repository"
            return citation

        file_rec = self._file_records[norm_path]
        max_lines = file_rec.metadata.line_count

        # 2. Line number bounds
        if citation.start_line < 1:
            citation.valid = False
            citation.reason = f"Start line {citation.start_line} is less than 1"
            return citation

        if citation.end_line < citation.start_line:
            citation.valid = False
            citation.reason = (
                f"End line {citation.end_line} is before start line {citation.start_line}"
            )
            return citation

        # If file is empty (0 lines) or line is beyond bounds
        if max_lines > 0 and citation.start_line > max_lines:
            citation.valid = False
            citation.reason = (
                f"Start line {citation.start_line} exceeds file length ({max_lines} lines)"
            )
            return citation

        # 3. Entity check (when entity specified and code_index is available)
        if citation.entity and self.code_index:
            entity_found = self._check_entity_exists(norm_path, citation.entity)
            if not entity_found:
                citation.valid = False
                citation.reason = (
                    f"Entity '{citation.entity}' not found in '{citation.file}'"
                )
                return citation

        # 4. Retrieval grounding check (citation corresponds to actually retrieved context)
        if allowed_sources is not None:
            allowed_files: set[str] = set()
            for item in allowed_sources:
                if isinstance(item, Citation):
                    allowed_files.add(item.file.replace("\\", "/"))
                elif isinstance(item, str):
                    allowed_files.add(item.replace("\\", "/"))

            if norm_path not in allowed_files:
                citation.valid = False
                citation.reason = f"File '{citation.file}' was not retrieved in context"
                return citation

        citation.valid = True
        citation.reason = None
        return citation

    def validate_citations(
        self,
        citations: list[Citation],
        fallback_citations: Optional[list[Citation]] = None,
        allowed_sources: Optional[Union[list[Citation], set[str], list[str]]] = None,
    ) -> CitationValidationResult:
        """Validate a list of citations, rejecting ungrounded or hallucinated citations."""
        valid_list: list[Citation] = []
        invalid_list: list[Citation] = []

        seen: set[str] = set()

        for c in citations:
            val_c = self.validate_citation(c, allowed_sources=allowed_sources)
            key = f"{val_c.file}:{val_c.start_line}-{val_c.end_line}"
            if val_c.valid:
                if key not in seen:
                    seen.add(key)
                    valid_list.append(val_c)
            else:
                invalid_list.append(val_c)

        fallback_used = False
        # If no valid citations were generated by LLM, use verified retrieved citations
        if not valid_list and fallback_citations:
            for fc in fallback_citations:
                val_fc = self.validate_citation(fc, allowed_sources=None)
                if val_fc.valid:
                    key = f"{val_fc.file}:{val_fc.start_line}-{val_fc.end_line}"
                    if key not in seen:
                        seen.add(key)
                        valid_list.append(val_fc)
            if valid_list:
                fallback_used = True

        return CitationValidationResult(
            valid_citations=valid_list,
            invalid_citations=invalid_list,
            fallback_used=fallback_used,
        )

    def extract_citations_from_text(self, text: str) -> list[Citation]:
        """Extract citation references from LLM-generated text using regex."""
        if not text:
            return []

        citations: list[Citation] = []
        for match in CITATION_PATTERN.finditer(text):
            file_path = match.group(1).replace("\\", "/")
            start_line = int(match.group(2))
            end_line = int(match.group(3)) if match.group(3) else start_line
            entity = match.group(4) if match.group(4) else None

            citations.append(
                Citation(
                    file=file_path,
                    start_line=start_line,
                    end_line=end_line,
                    entity=entity,
                )
            )
        return citations

    def _check_entity_exists(self, file_path: str, entity_name: str) -> bool:
        """Check whether named entity exists in the analyzed file's AST."""
        if not self.code_index:
            return True
        for fa in self.code_index.file_analyses:
            if fa.file_path.replace("\\", "/") == file_path:
                # Check class names
                for c in fa.classes:
                    if c.name == entity_name:
                        return True
                    for m in c.methods:
                        if m.name == entity_name or f"{c.name}.{m.name}" == entity_name:
                            return True
                # Check function names
                for fn in fa.functions:
                    if fn.name == entity_name:
                        return True
        return False
