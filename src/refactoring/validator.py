"""DiffValidator: validates generated diffs for safety and consistency.

Validation happens against temporary copies only — the original repository
is never modified.
"""

from __future__ import annotations

import ast
import shutil
import tempfile
from pathlib import Path
from typing import Optional

from refactoring.models import (
    ChangeProposal,
    DiffResult,
    FileChange,
    ValidationResult,
)
from utils.logger import setup_logger

logger = setup_logger(__name__)


class DiffValidator:
    """Validates that generated diffs are safe and internally consistent."""

    def validate(
        self,
        proposal: ChangeProposal,
        diff_results: list[DiffResult],
        root_path: Path,
    ) -> ValidationResult:
        """Validate a proposal's diffs for safety and consistency.

        Validation is performed against a temporary copy. The original
        repository at root_path is NEVER modified.

        Args:
            proposal: The change proposal.
            diff_results: The generated diffs.
            root_path: Path to the original repository (read-only).

        Returns:
            A ValidationResult with validity status, errors, and warnings.
        """
        errors: list[str] = []
        warnings: list[str] = []

        # 1. Check that there are actual changes
        if not diff_results:
            if proposal.file_changes:
                errors.append("Proposal has file changes but no diffs were generated.")
            else:
                warnings.append("Proposal has no file changes (advisory-only).")
            return ValidationResult(
                valid=len(errors) == 0,
                errors=errors,
                warnings=warnings,
                proposal_id=proposal.finding_id,
            )

        # 2. Validate each diff result
        for diff_result in diff_results:
            self._validate_diff_result(diff_result, errors, warnings)

        # 3. Check for edit overlaps within each file change
        for file_change in proposal.file_changes:
            self._check_edit_overlaps(file_change, errors)

        # 4. Validate on a temporary copy (never modify original)
        if diff_results and not errors:
            self._validate_on_temp_copy(diff_results, root_path, errors, warnings)

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            proposal_id=proposal.finding_id,
        )

    def _validate_diff_result(
        self,
        diff_result: DiffResult,
        errors: list[str],
        warnings: list[str],
    ) -> None:
        """Validate a single diff result."""
        # Check non-empty diff
        if not diff_result.unified_diff.strip():
            errors.append(f"Empty diff for {diff_result.file_path}.")
            return

        # Check valid unified diff format (should start with --- or contain ---)
        lines = diff_result.unified_diff.strip().split("\n")
        has_header = any(line.startswith("---") for line in lines)
        if not has_header:
            errors.append(f"Invalid unified diff format for {diff_result.file_path}: missing --- header.")

        # If Python file, check that modified content is valid Python
        if diff_result.file_path.endswith(".py") and diff_result.modified_content:
            try:
                ast.parse(diff_result.modified_content, filename=diff_result.file_path)
            except SyntaxError as exc:
                errors.append(
                    f"Modified content for {diff_result.file_path} has syntax error: {exc}"
                )

    def _check_edit_overlaps(
        self,
        file_change: FileChange,
        errors: list[str],
    ) -> None:
        """Check that no two edits in the same file overlap."""
        edits = sorted(file_change.edits, key=lambda e: e.start_line)
        for i in range(len(edits) - 1):
            if edits[i].end_line >= edits[i + 1].start_line:
                errors.append(
                    f"Overlapping edits in {file_change.file_path}: "
                    f"edit ending at line {edits[i].end_line} overlaps with "
                    f"edit starting at line {edits[i + 1].start_line}."
                )

    def _validate_on_temp_copy(
        self,
        diff_results: list[DiffResult],
        root_path: Path,
        errors: list[str],
        warnings: list[str],
    ) -> None:
        """Validate diffs by writing modified content to a temporary copy.

        The original repository is NEVER modified. A temporary directory
        is created, only the affected files are copied and modified there.
        """
        temp_dir = None
        try:
            temp_dir = Path(tempfile.mkdtemp(prefix="codebase_agent_validate_"))

            for diff_result in diff_results:
                src_file = root_path / diff_result.file_path
                dst_file = temp_dir / diff_result.file_path

                # Create parent directories
                dst_file.parent.mkdir(parents=True, exist_ok=True)

                # Copy original to temp
                if src_file.exists():
                    shutil.copy2(str(src_file), str(dst_file))
                else:
                    warnings.append(f"Original file {diff_result.file_path} not found — skipping temp validation.")
                    continue

                # Write modified content to temp
                try:
                    dst_file.write_text(diff_result.modified_content, encoding="utf-8")
                except Exception as exc:
                    errors.append(f"Failed to write modified content for {diff_result.file_path}: {exc}")
                    continue

                # Re-verify the temp file is valid Python if applicable
                if diff_result.file_path.endswith(".py"):
                    try:
                        ast.parse(dst_file.read_text(encoding="utf-8"), filename=str(dst_file))
                    except SyntaxError as exc:
                        errors.append(
                            f"Temp copy validation failed for {diff_result.file_path}: {exc}"
                        )

            logger.info("Temp-copy validation complete in %s", temp_dir)

        except Exception as exc:
            errors.append(f"Temp-copy validation failed: {exc}")
        finally:
            # Clean up temporary directory
            if temp_dir and temp_dir.exists():
                try:
                    shutil.rmtree(str(temp_dir))
                except Exception:
                    logger.warning("Failed to clean up temp directory: %s", temp_dir)
