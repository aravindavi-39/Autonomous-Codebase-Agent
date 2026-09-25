"""Deterministic refactoring strategies mapping findings to change proposals.

Each strategy handles a specific finding type and produces a ChangeProposal
with the appropriate SafetyClassification. No LLM calls — all transformations
are purely AST-based or text-based.
"""

from __future__ import annotations

import ast
import re
from abc import ABC, abstractmethod
from typing import Optional

from analysis.findings.context import AnalysisContext
from analysis.findings.models import Finding
from refactoring.models import (
    ChangeProposal,
    FileChange,
    SafetyClassification,
    TextEdit,
)
from utils.logger import setup_logger

logger = setup_logger(__name__)


# ---------------------------------------------------------------------------
# Base Strategy
# ---------------------------------------------------------------------------


class BaseStrategy(ABC):
    """Abstract base class for refactoring strategies."""

    strategy_name: str
    handled_finding_types: list[str]
    safety: SafetyClassification

    def can_handle(self, finding: Finding) -> bool:
        """Return True if this strategy can handle the given finding."""
        return finding.type in self.handled_finding_types

    @abstractmethod
    def propose(self, finding: Finding, context: AnalysisContext) -> ChangeProposal:
        """Generate a ChangeProposal for the finding."""
        pass

    def _make_proposal(
        self,
        finding: Finding,
        description: str,
        rationale: str,
        file_changes: Optional[list[FileChange]] = None,
    ) -> ChangeProposal:
        """Helper to build a ChangeProposal with standard fields."""
        return ChangeProposal(
            finding_id=finding.id,
            finding_type=finding.type,
            strategy=self.strategy_name,
            safety=self.safety,
            file_changes=file_changes or [],
            description=description,
            rationale=rationale,
            source_file=finding.file,
            source_start_line=finding.start_line,
            source_end_line=finding.end_line,
        )


# ---------------------------------------------------------------------------
# Strategy A: Mutable Default Argument → None initialization
# ---------------------------------------------------------------------------


class MutableDefaultStrategy(BaseStrategy):
    """Replace mutable default arguments ([], {}, set()) with None + body guard."""

    strategy_name = "MutableDefaultStrategy"
    handled_finding_types = ["PAT-003"]
    safety = SafetyClassification.SAFE_AUTOMATIC_PROPOSAL

    def propose(self, finding: Finding, context: AnalysisContext) -> ChangeProposal:
        lines = context.get_lines(finding.file)
        if not lines:
            return self._make_proposal(
                finding,
                description="Cannot read source file to fix mutable default.",
                rationale="File content unavailable.",
            )

        tree = context.get_ast(finding.file)
        if not tree:
            return self._make_proposal(
                finding,
                description="Cannot parse AST to fix mutable default.",
                rationale="AST parsing failed.",
            )

        # Find the function definition that contains the finding
        target_func = None
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.lineno <= finding.start_line:
                    end = getattr(node, "end_lineno", node.lineno)
                    if end >= finding.start_line:
                        if finding.entity and node.name == finding.entity:
                            target_func = node
                            break
                        elif not finding.entity:
                            target_func = node

        if not target_func:
            return self._make_proposal(
                finding,
                description="Could not locate function definition for mutable default fix.",
                rationale="AST function lookup failed.",
            )

        # Identify which defaults are mutable and their corresponding parameter names
        edits: list[TextEdit] = []
        guards: list[str] = []

        func_args = target_func.args

        # Map positional defaults to parameter names
        # defaults align to the END of the args list
        pos_args = func_args.posonlyargs + func_args.args
        num_defaults = len(func_args.defaults)
        offset = len(pos_args) - num_defaults

        for i, default in enumerate(func_args.defaults):
            if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                param_name = pos_args[offset + i].arg
                mutable_type = {ast.List: "[]", ast.Dict: "{}", ast.Set: "set()"}[type(default)]
                guards.append((param_name, mutable_type))

        # Also check kw_defaults
        for i, default in enumerate(func_args.kw_defaults):
            if default is not None and isinstance(default, (ast.List, ast.Dict, ast.Set)):
                param_name = func_args.kwonlyargs[i].arg
                mutable_type = {ast.List: "[]", ast.Dict: "{}", ast.Set: "set()"}[type(default)]
                guards.append((param_name, mutable_type))

        if not guards:
            return self._make_proposal(
                finding,
                description="No mutable defaults found in function.",
                rationale="Pattern not matched.",
            )

        # Replace the def line: substitute each mutable default with None
        func_start = target_func.lineno
        func_end_sig = func_start
        # Find where the function signature ends (the colon line)
        for li in range(func_start - 1, min(func_start + 20, len(lines))):
            if lines[li].rstrip().endswith(":"):
                func_end_sig = li + 1  # 1-indexed
                break

        original_sig_lines = lines[func_start - 1: func_end_sig]
        original_sig = "\n".join(original_sig_lines)
        modified_sig = original_sig

        for param_name, mutable_type in guards:
            # Replace param=[] / param={} / param=set() with param=None
            # Handle whitespace around the = sign
            pattern = re.compile(
                rf'(\b{re.escape(param_name)}\s*=\s*)' + re.escape(mutable_type)
            )
            modified_sig = pattern.sub(rf'\g<1>None', modified_sig)

        if modified_sig != original_sig:
            edits.append(TextEdit(
                start_line=func_start,
                end_line=func_end_sig,
                original_text=original_sig,
                replacement_text=modified_sig,
            ))

        # Now add guard clauses at the start of the function body
        # If the function has a docstring, insert guards after the docstring so docstring remains first
        has_docstring = (
            target_func.body
            and isinstance(target_func.body[0], ast.Expr)
            and isinstance(getattr(target_func.body[0], "value", None), ast.Constant)
            and isinstance(target_func.body[0].value.value, str)
        )
        if has_docstring and len(target_func.body) > 1:
            body_start = target_func.body[1].lineno
        elif target_func.body:
            body_start = target_func.body[0].lineno
        else:
            body_start = func_end_sig + 1

        if body_start - 1 < len(lines):
            body_line = lines[body_start - 1]
            indent = len(body_line) - len(body_line.lstrip())
            indent_str = body_line[:indent]
        else:
            indent_str = "    "

        guard_lines = []
        for param_name, mutable_type in guards:
            guard_lines.append(f"{indent_str}if {param_name} is None:")
            guard_lines.append(f"{indent_str}    {param_name} = {mutable_type}")

        # Insert guard before the first body line
        if guard_lines:
            first_body = lines[body_start - 1] if body_start - 1 < len(lines) else ""
            replacement = "\n".join(guard_lines) + "\n" + first_body
            edits.append(TextEdit(
                start_line=body_start,
                end_line=body_start,
                original_text=first_body,
                replacement_text=replacement,
            ))

        file_change = FileChange(file_path=finding.file, edits=edits)
        param_names = ", ".join(p for p, _ in guards)

        return self._make_proposal(
            finding,
            description=f"Replace mutable default argument(s) ({param_names}) with None + guard clause.",
            rationale="Mutable defaults are evaluated once at module load time. Using None with a body guard prevents leaked state across calls.",
            file_changes=[file_change],
        )


# ---------------------------------------------------------------------------
# Strategy B: Wildcard Import → Review Required
# ---------------------------------------------------------------------------


class WildcardImportStrategy(BaseStrategy):
    """Flag wildcard imports for manual review."""

    strategy_name = "WildcardImportStrategy"
    handled_finding_types = ["PAT-002"]
    safety = SafetyClassification.REVIEW_REQUIRED

    def propose(self, finding: Finding, context: AnalysisContext) -> ChangeProposal:
        return self._make_proposal(
            finding,
            description=f"Wildcard import detected at {finding.file}:{finding.start_line}. "
                        "Cannot safely determine which symbols are used — manual review required.",
            rationale="Wildcard imports hide symbol origins and can introduce name collisions. "
                      "A developer must identify actually used symbols and replace with explicit imports.",
        )


# ---------------------------------------------------------------------------
# Strategy C: Broad Exception → Review Required
# ---------------------------------------------------------------------------


class BroadExceptionStrategy(BaseStrategy):
    """Flag broad exception handlers for manual review."""

    strategy_name = "BroadExceptionStrategy"
    handled_finding_types = ["PAT-001"]
    safety = SafetyClassification.REVIEW_REQUIRED

    def propose(self, finding: Finding, context: AnalysisContext) -> ChangeProposal:
        return self._make_proposal(
            finding,
            description=f"Broad exception handler at {finding.file}:{finding.start_line}. "
                        "The correct exception type depends on context — manual review required.",
            rationale="Catching bare except or Exception suppresses unexpected errors. "
                      "A developer must determine the specific exceptions that should be caught.",
        )


# ---------------------------------------------------------------------------
# Strategy D: Long Function → Unsupported
# ---------------------------------------------------------------------------


class LongFunctionStrategy(BaseStrategy):
    """Long functions cannot be safely auto-refactored."""

    strategy_name = "LongFunctionStrategy"
    handled_finding_types = ["SMELL-001"]
    safety = SafetyClassification.UNSUPPORTED

    def propose(self, finding: Finding, context: AnalysisContext) -> ChangeProposal:
        return self._make_proposal(
            finding,
            description=f"Function '{finding.entity or '?'}' at {finding.file}:{finding.start_line} "
                        "is too long. Automated decomposition is not supported — manual refactoring recommended.",
            rationale="Decomposing long functions requires understanding the semantic purpose of each block. "
                      "This is a creative task unsuitable for deterministic automation.",
        )


# ---------------------------------------------------------------------------
# Strategy E: High Parameter Count → Unsupported
# ---------------------------------------------------------------------------


class HighParameterCountStrategy(BaseStrategy):
    """High parameter count cannot be safely auto-refactored."""

    strategy_name = "HighParameterCountStrategy"
    handled_finding_types = ["SMELL-002"]
    safety = SafetyClassification.UNSUPPORTED

    def propose(self, finding: Finding, context: AnalysisContext) -> ChangeProposal:
        return self._make_proposal(
            finding,
            description=f"Function '{finding.entity or '?'}' at {finding.file}:{finding.start_line} "
                        "has too many parameters. Introducing a parameter object requires manual design.",
            rationale="Bundling parameters into a dataclass or Pydantic model requires understanding "
                      "which parameters are logically related. This cannot be reliably inferred.",
        )


# ---------------------------------------------------------------------------
# Strategy F: Unused Import → Safe deletion
# ---------------------------------------------------------------------------


class UnusedImportStrategy(BaseStrategy):
    """Remove proven unused import lines."""

    strategy_name = "UnusedImportStrategy"
    handled_finding_types = ["PAT-005"]
    safety = SafetyClassification.SAFE_AUTOMATIC_PROPOSAL

    def propose(self, finding: Finding, context: AnalysisContext) -> ChangeProposal:
        lines = context.get_lines(finding.file)
        if not lines:
            return self._make_proposal(
                finding,
                description="Cannot read source file to remove unused import.",
                rationale="File content unavailable.",
            )

        s_line = finding.start_line
        e_line = finding.end_line

        if s_line < 1 or e_line > len(lines):
            return self._make_proposal(
                finding,
                description="Import line range is out of bounds.",
                rationale="Line range validation failed.",
            )

        original_text = "\n".join(lines[s_line - 1: e_line])

        # For multi-name imports (from x import a, b, c), only remove the unused one
        tree = context.get_ast(finding.file)
        if tree and finding.entity:
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    if node.lineno == s_line:
                        names = node.names
                        if len(names) > 1:
                            # Multi-import: remove just the unused symbol
                            remaining = [
                                alias for alias in names
                                if (alias.asname or alias.name) != finding.entity
                            ]
                            if remaining and len(remaining) < len(names):
                                if isinstance(node, ast.ImportFrom):
                                    remaining_str = ", ".join(
                                        f"{a.name} as {a.asname}" if a.asname else a.name
                                        for a in remaining
                                    )
                                    replacement = f"from {node.module} import {remaining_str}"
                                else:
                                    remaining_str = ", ".join(
                                        f"{a.name} as {a.asname}" if a.asname else a.name
                                        for a in remaining
                                    )
                                    replacement = f"import {remaining_str}"

                                # Preserve original indentation
                                orig_line = lines[s_line - 1]
                                indent = len(orig_line) - len(orig_line.lstrip())
                                replacement = " " * indent + replacement

                                edit = TextEdit(
                                    start_line=s_line,
                                    end_line=e_line,
                                    original_text=original_text,
                                    replacement_text=replacement,
                                )
                                return self._make_proposal(
                                    finding,
                                    description=f"Remove unused import '{finding.entity}' from multi-import statement.",
                                    rationale="Unused imports clutter source code and introduce unnecessary module coupling.",
                                    file_changes=[FileChange(file_path=finding.file, edits=[edit])],
                                )

        # Single import: remove the entire line(s)
        edit = TextEdit(
            start_line=s_line,
            end_line=e_line,
            original_text=original_text,
            replacement_text="",
        )
        file_change = FileChange(file_path=finding.file, edits=[edit])

        return self._make_proposal(
            finding,
            description=f"Remove unused import '{finding.entity or 'unknown'}' at {finding.file}:{s_line}.",
            rationale="Unused imports clutter source code, introduce unnecessary module coupling, and slow down module loading.",
            file_changes=[file_change],
        )


# ---------------------------------------------------------------------------
# Strategy G: debug=True → debug=False
# ---------------------------------------------------------------------------


class DebugTrueStrategy(BaseStrategy):
    """Replace debug=True with debug=False."""

    strategy_name = "DebugTrueStrategy"
    handled_finding_types = ["SEC-010"]
    safety = SafetyClassification.SAFE_AUTOMATIC_PROPOSAL

    def propose(self, finding: Finding, context: AnalysisContext) -> ChangeProposal:
        lines = context.get_lines(finding.file)
        if not lines:
            return self._make_proposal(
                finding,
                description="Cannot read source file to fix debug setting.",
                rationale="File content unavailable.",
            )

        s_line = finding.start_line
        e_line = finding.end_line

        if s_line < 1 or e_line > len(lines):
            return self._make_proposal(
                finding,
                description="Finding line range out of bounds.",
                rationale="Line range validation failed.",
            )

        original_text = "\n".join(lines[s_line - 1: e_line])

        # Replace debug=True with debug=False
        modified = original_text.replace("debug=True", "debug=False")
        modified = modified.replace("DEBUG = True", "DEBUG = False")

        if modified == original_text:
            return self._make_proposal(
                finding,
                description="Could not locate debug=True pattern in source lines.",
                rationale="Pattern not matched in source text.",
            )

        edit = TextEdit(
            start_line=s_line,
            end_line=e_line,
            original_text=original_text,
            replacement_text=modified,
        )
        file_change = FileChange(file_path=finding.file, edits=[edit])

        return self._make_proposal(
            finding,
            description=f"Replace debug=True with debug=False at {finding.file}:{s_line}.",
            rationale="Debug mode in production exposes interactive consoles, sensitive variables, and stack traces.",
            file_changes=[file_change],
        )


# ---------------------------------------------------------------------------
# Strategy H: Weak MD5/SHA1 → Review Required
# ---------------------------------------------------------------------------


class WeakCryptoStrategy(BaseStrategy):
    """Flag weak cryptographic hash usage for manual review."""

    strategy_name = "WeakCryptoStrategy"
    handled_finding_types = ["SEC-008"]
    safety = SafetyClassification.REVIEW_REQUIRED

    def propose(self, finding: Finding, context: AnalysisContext) -> ChangeProposal:
        return self._make_proposal(
            finding,
            description=f"Weak cryptographic hash ({finding.entity or 'MD5/SHA1'}) detected at "
                        f"{finding.file}:{finding.start_line}. Replacing may change behavior — "
                        "manual review required to determine if used in a security context.",
            rationale="MD5 and SHA-1 have known collision vulnerabilities. However, they may be used "
                      "for non-security purposes (cache keys, checksums). Automatic replacement to SHA-256 "
                      "could change hash output length and break downstream consumers.",
        )


# ---------------------------------------------------------------------------
# Strategy Registry
# ---------------------------------------------------------------------------


class StrategyRegistry:
    """Registry mapping finding types to refactoring strategies."""

    def __init__(self) -> None:
        self._strategies: dict[str, BaseStrategy] = {}

    def register(self, strategy: BaseStrategy) -> None:
        """Register a strategy for its handled finding types."""
        for ft in strategy.handled_finding_types:
            self._strategies[ft] = strategy

    def get_strategy(self, finding: Finding) -> Optional[BaseStrategy]:
        """Look up the strategy for a finding type."""
        return self._strategies.get(finding.type)

    def all_strategies(self) -> list[BaseStrategy]:
        """Return all unique registered strategies."""
        seen = set()
        result = []
        for s in self._strategies.values():
            if s.strategy_name not in seen:
                seen.add(s.strategy_name)
                result.append(s)
        return result


def get_default_strategy_registry() -> StrategyRegistry:
    """Create and populate the default strategy registry."""
    registry = StrategyRegistry()
    registry.register(MutableDefaultStrategy())     # A: PAT-003 → SAFE
    registry.register(WildcardImportStrategy())      # B: PAT-002 → REVIEW
    registry.register(BroadExceptionStrategy())      # C: PAT-001 → REVIEW
    registry.register(LongFunctionStrategy())        # D: SMELL-001 → UNSUPPORTED
    registry.register(HighParameterCountStrategy())  # E: SMELL-002 → UNSUPPORTED
    registry.register(UnusedImportStrategy())        # F: PAT-005 → SAFE
    registry.register(DebugTrueStrategy())           # G: SEC-010 → SAFE
    registry.register(WeakCryptoStrategy())          # H: SEC-008 → REVIEW
    return registry
