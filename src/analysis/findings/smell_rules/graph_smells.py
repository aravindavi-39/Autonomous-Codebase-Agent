"""Graph-based code smell rules: circular dependencies, dead code, excessive dependencies."""

from __future__ import annotations

from analysis.cycles import detect_cycles
from analysis.findings.base_rule import BaseRule
from analysis.findings.context import AnalysisContext
from analysis.findings.models import Confidence, Finding, FindingCategory, Severity


class CircularDependencyRule(BaseRule):
    """Detects circular import dependencies between repository modules."""

    rule_id = "SMELL-007"
    category = FindingCategory.CODE_SMELL
    title = "Circular dependency"
    default_severity = Severity.HIGH
    default_confidence = Confidence.HIGH
    description = "A circular dependency exists among repository modules."
    rationale = "Circular dependencies cause initialization deadlocks, tight architectural coupling, and import errors."
    recommendation = "Extract shared dependencies into a separate common module or apply dependency inversion."

    def check(self, context: AnalysisContext) -> list[Finding]:
        if not context.code_graph:
            return []

        cycles = context.code_graph.statistics.circular_dependencies
        findings: list[Finding] = []

        for cycle in cycles:
            path_str = cycle.cycle_str
            # Locate first file in the cycle
            first_module = cycle.cycle[0] if cycle.cycle else ""
            first_node = context.code_graph.get_node(first_module)
            f_path = first_node.file if first_node and first_node.file else (first_module.replace("module:", "").replace(".", "/") + ".py")
            start_l = first_node.start_line if first_node and first_node.start_line else 1

            findings.append(
                self.create_finding(
                    file=f_path,
                    start_line=start_l,
                    end_line=start_l,
                    entity=first_module,
                    evidence=path_str,
                    description=f"Circular dependency detected: {path_str}",
                )
            )
        return findings


class DeadFunctionRule(BaseRule):
    """Detects private or standalone functions that appear unused and unreferenced."""

    rule_id = "SMELL-006"
    category = FindingCategory.CODE_SMELL
    title = "Potential dead function"
    default_severity = Severity.INFO
    default_confidence = Confidence.LOW
    description = "Function has no known calls or references within the codebase."
    rationale = "Unreferenced code clutters the codebase, increases cognitive load, and can mislead developers."
    recommendation = "Verify if this function is used dynamically or part of an external API; if not, safely remove it."

    def check(self, context: AnalysisContext) -> list[Finding]:
        # Collect all called function names across repository
        called_names: set[str] = set()
        for fa in context.code_index.file_analyses:
            for call in fa.calls:
                target_name = call.target.split(".")[-1]
                called_names.add(target_name)

        findings: list[Finding] = []
        for fa in context.code_index.file_analyses:
            # Skip test files and init files
            f_low = fa.file_path.lower()
            if "test" in f_low or f_low.endswith("__init__.py"):
                continue

            for fn in fa.functions:
                # Ignore magic methods, entrypoints, and test functions
                if (
                    fn.name.startswith("__")
                    or fn.name in ("main", "app", "cli", "run", "handler")
                    or fn.name.startswith("test_")
                ):
                    continue

                # Check if called
                if fn.name not in called_names:
                    findings.append(
                        self.create_finding(
                            file=fa.file_path,
                            start_line=fn.start_line,
                            end_line=fn.end_line or fn.start_line,
                            entity=fn.name,
                            evidence=f"def {fn.name}(...):",
                            description=f"Function '{fn.name}' is defined but has no observed call references in the repository.",
                        )
                    )
        return findings


class ExcessiveDependenciesRule(BaseRule):
    """Detects files that import an excessive number of modules."""

    rule_id = "SMELL-008"
    category = FindingCategory.CODE_SMELL
    title = "Excessive module dependencies"
    default_severity = Severity.LOW
    default_confidence = Confidence.HIGH
    description = "File imports too many distinct modules, indicating high architectural coupling."
    rationale = "Modules with high fan-out coupling are fragile, harder to test in isolation, and prone to ripple-effect bugs."
    recommendation = "Review file responsibilities and decouple by splitting duties or using facades."

    def __init__(self, max_imports: int = 15) -> None:
        self.max_imports = max_imports

    def check(self, context: AnalysisContext) -> list[Finding]:
        findings: list[Finding] = []
        for fa in context.code_index.file_analyses:
            distinct_modules = {imp.module for imp in fa.imports if imp.module}
            if len(distinct_modules) > self.max_imports:
                start_l = fa.imports[0].line if fa.imports and fa.imports[0].line else 1
                findings.append(
                    self.create_finding(
                        file=fa.file_path,
                        start_line=start_l,
                        end_line=start_l,
                        evidence=f"{len(distinct_modules)} distinct imported modules",
                        description=f"File '{fa.file_path}' imports {len(distinct_modules)} modules (threshold is {self.max_imports}).",
                    )
                )
        return findings
