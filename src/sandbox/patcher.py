"""SandboxPatcher: validates and applies proposed refactoring diffs strictly inside the sandbox."""

from __future__ import annotations

import ast
import difflib
from pathlib import Path
from typing import Optional

from refactoring.models import ChangeProposal, SafetyClassification
from sandbox.models import PatchApplicationResult, redact_secrets
from utils.logger import setup_logger

logger = setup_logger(__name__)


class SandboxPatcher:
    """Safely applies validated change proposals strictly inside an isolated sandbox directory."""

    def apply_proposal(
        self,
        proposal: ChangeProposal,
        sandbox_path: Path,
    ) -> PatchApplicationResult:
        """Validate and apply a ChangeProposal to files inside sandbox_path.

        Args:
            proposal: The change proposal to apply.
            sandbox_path: Isolated sandbox root directory.

        Returns:
            PatchApplicationResult with status, applied files, and diff.
        """
        errors: list[str] = []
        warnings: list[str] = []
        applied_files: list[str] = []
        applied_diff_parts: list[str] = []

        resolved_sandbox = sandbox_path.resolve()

        # 1. Safety Classification Gate
        if proposal.safety != SafetyClassification.SAFE_AUTOMATIC_PROPOSAL:
            errors.append(
                f"Proposal safety classification is '{proposal.safety.value}'. "
                "Only 'SAFE_AUTOMATIC_PROPOSAL' can be applied to sandbox."
            )
            return PatchApplicationResult(
                success=False,
                finding_id=proposal.finding_id,
                strategy=proposal.strategy,
                applied_files=[],
                diff_applied="",
                errors=errors,
                warnings=warnings,
            )

        if not proposal.file_changes:
            warnings.append("Proposal contains no file changes to apply.")
            return PatchApplicationResult(
                success=True,
                finding_id=proposal.finding_id,
                strategy=proposal.strategy,
                applied_files=[],
                diff_applied="",
                errors=errors,
                warnings=warnings,
            )

        # 2. Pre-Application Validation on All Files
        file_plans: list[tuple[Path, list[str], list[str]]] = []  # (target_file, orig_lines, new_lines)

        for fc in proposal.file_changes:
            raw_path = fc.file_path.replace("\\", "/")

            # Path traversal and security checks
            if Path(raw_path).is_absolute() or raw_path.startswith("/") or raw_path.startswith("\\"):
                errors.append(f"Rejected absolute path in proposal: {raw_path}")
                continue

            if ".." in Path(raw_path).parts:
                errors.append(f"Rejected path traversal in proposal: {raw_path}")
                continue

            target_file = (resolved_sandbox / raw_path).resolve()
            try:
                if not target_file.is_relative_to(resolved_sandbox):
                    errors.append(f"File path escapes sandbox root: {raw_path}")
                    continue
            except AttributeError:
                # Python < 3.9 compatibility
                if not str(target_file).startswith(str(resolved_sandbox)):
                    errors.append(f"File path escapes sandbox root: {raw_path}")
                    continue

            if not target_file.exists() or not target_file.is_file():
                errors.append(f"Target file does not exist in sandbox: {raw_path}")
                continue

            # Read original lines
            try:
                content = target_file.read_text(encoding="utf-8")
            except Exception as exc:
                errors.append(f"Cannot read target file {raw_path}: {exc}")
                continue

            lines = content.splitlines(keepends=True)
            if lines and not lines[-1].endswith("\n"):
                lines[-1] += "\n"

            # Check Stale Source: verify lines at edit positions match original_text
            is_stale = False
            for edit in fc.edits:
                s_idx = edit.start_line - 1
                e_idx = edit.end_line
                if s_idx < 0 or e_idx > len(lines):
                    errors.append(
                        f"STALE_PROPOSAL: Line range [{edit.start_line}, {edit.end_line}] "
                        f"out of bounds in {raw_path} (has {len(lines)} lines)."
                    )
                    is_stale = True
                    break

                current_text = "".join(lines[s_idx:e_idx]).strip()
                expected_text = edit.original_text.strip()
                if current_text != expected_text:
                    errors.append(
                        f"STALE_PROPOSAL: Expected source text in {raw_path} does not match current file.\n"
                        f"Expected:\n{expected_text}\nActual:\n{current_text}"
                    )
                    is_stale = True
                    break

            if is_stale:
                continue

            # Calculate modified lines (sort edits bottom-to-top)
            sorted_edits = sorted(fc.edits, key=lambda e: e.start_line, reverse=True)
            modified_lines = list(lines)

            for edit in sorted_edits:
                s_idx = edit.start_line - 1
                e_idx = edit.end_line
                if edit.replacement_text == "":
                    del modified_lines[s_idx:e_idx]
                else:
                    rep_lines = edit.replacement_text.splitlines(keepends=True)
                    if rep_lines and not rep_lines[-1].endswith("\n"):
                        rep_lines[-1] += "\n"
                    modified_lines[s_idx:e_idx] = rep_lines

            # Syntactic check if python file
            if raw_path.endswith(".py"):
                mod_content = "".join(modified_lines)
                try:
                    ast.parse(mod_content, filename=raw_path)
                except SyntaxError as syn_err:
                    errors.append(f"Syntax error introduced in {raw_path}: {syn_err}")
                    continue

            file_plans.append((target_file, lines, modified_lines))

        # If any validation errors occurred, abort before modifying anything
        if errors:
            logger.warning("Pre-application validation failed for proposal %s: %s", proposal.finding_id, errors)
            return PatchApplicationResult(
                success=False,
                finding_id=proposal.finding_id,
                strategy=proposal.strategy,
                applied_files=[],
                diff_applied="",
                errors=errors,
                warnings=warnings,
            )

        # 3. Apply changes to files in sandbox
        for target_file, orig_lines, mod_lines in file_plans:
            rel_name = str(target_file.relative_to(resolved_sandbox)).replace("\\", "/")
            try:
                target_file.write_text("".join(mod_lines), encoding="utf-8")
                applied_files.append(rel_name)

                # Generate unified diff
                diff_lines = list(difflib.unified_diff(
                    orig_lines,
                    mod_lines,
                    fromfile=f"a/{rel_name}",
                    tofile=f"b/{rel_name}",
                    lineterm="\n",
                ))
                applied_diff_parts.append("".join(diff_lines))
            except Exception as exc:
                errors.append(f"Failed to write modifications to {rel_name}: {exc}")

        total_diff = "\n".join(applied_diff_parts)

        return PatchApplicationResult(
            success=len(errors) == 0,
            finding_id=proposal.finding_id,
            strategy=proposal.strategy,
            applied_files=applied_files,
            diff_applied=redact_secrets(total_diff),
            errors=errors,
            warnings=warnings,
        )
