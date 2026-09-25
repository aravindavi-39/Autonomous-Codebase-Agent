"""DiffGenerator: produces unified diffs from ChangeProposal objects."""

from __future__ import annotations

import difflib
from pathlib import Path
from typing import Optional

from analysis.findings.context import AnalysisContext
from refactoring.models import ChangeProposal, DiffResult, FileChange, TextEdit
from utils.logger import setup_logger

logger = setup_logger(__name__)


class DiffGenerator:
    """Generates unified diffs from change proposals."""

    def generate(
        self,
        proposal: ChangeProposal,
        context: AnalysisContext,
    ) -> list[DiffResult]:
        """Generate unified diffs for all file changes in a proposal.

        Args:
            proposal: The change proposal containing file edits.
            context: The analysis context for reading source files.

        Returns:
            A list of DiffResult objects, one per changed file.
        """
        results: list[DiffResult] = []

        if not proposal.file_changes:
            logger.debug("Proposal %s has no file changes.", proposal.finding_id)
            return results

        for file_change in proposal.file_changes:
            try:
                diff_result = self._generate_file_diff(file_change, context)
                if diff_result:
                    results.append(diff_result)
            except Exception as exc:
                logger.warning(
                    "Failed to generate diff for %s: %s",
                    file_change.file_path,
                    exc,
                )

        return results

    def _generate_file_diff(
        self,
        file_change: FileChange,
        context: AnalysisContext,
    ) -> Optional[DiffResult]:
        """Generate a unified diff for a single file change."""
        original_content = context.get_content(file_change.file_path)
        if original_content is None:
            logger.warning("Cannot read file %s for diff generation.", file_change.file_path)
            return None

        original_lines = original_content.splitlines(keepends=True)
        # Ensure last line has newline
        if original_lines and not original_lines[-1].endswith("\n"):
            original_lines[-1] += "\n"

        modified_lines = list(original_lines)
        modified_lines = self._apply_edits(modified_lines, file_change.edits)

        modified_content = "".join(modified_lines)

        # Generate unified diff
        diff_lines = difflib.unified_diff(
            original_lines,
            modified_lines,
            fromfile=f"a/{file_change.file_path}",
            tofile=f"b/{file_change.file_path}",
            lineterm="\n",
        )
        unified_diff = "".join(diff_lines)

        if not unified_diff.strip():
            logger.debug("No changes detected for %s.", file_change.file_path)
            return None

        return DiffResult(
            file_path=file_change.file_path,
            unified_diff=unified_diff,
            original_content=original_content,
            modified_content=modified_content,
        )

    def _apply_edits(
        self,
        lines: list[str],
        edits: list[TextEdit],
    ) -> list[str]:
        """Apply text edits to lines, processing from bottom to top to preserve line numbers."""
        # Sort edits from bottom to top so earlier edits don't shift later line numbers
        sorted_edits = sorted(edits, key=lambda e: e.start_line, reverse=True)

        result = list(lines)
        for edit in sorted_edits:
            s_idx = edit.start_line - 1  # 0-indexed
            e_idx = edit.end_line  # exclusive

            if s_idx < 0 or e_idx > len(result):
                logger.warning(
                    "Edit line range [%d, %d] out of bounds (file has %d lines).",
                    edit.start_line,
                    edit.end_line,
                    len(result),
                )
                continue

            # Build replacement lines
            if edit.replacement_text == "":
                # Deletion: remove the lines entirely
                del result[s_idx:e_idx]
            else:
                replacement_lines = edit.replacement_text.splitlines(keepends=True)
                # Ensure last replacement line has newline
                if replacement_lines and not replacement_lines[-1].endswith("\n"):
                    replacement_lines[-1] += "\n"
                result[s_idx:e_idx] = replacement_lines

        return result
