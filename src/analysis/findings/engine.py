"""AnalysisEngine coordinating rule execution, citation validation, and report generation."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from analysis.findings.context import AnalysisContext
from analysis.findings.models import AnalysisReport, Finding, FindingCategory, Severity
from analysis.findings.registry import RuleRegistry, get_default_registry
from analysis.graph_models import CodeGraph
from analysis.models import RepositoryCodeIndex
from ingestion.models import RepositoryManifest
from utils.logger import setup_logger

logger = setup_logger(__name__)


class AnalysisEngine:
    """Orchestrates static analysis rules across codebase AST, index, and graph."""

    def __init__(self, registry: Optional[RuleRegistry] = None) -> None:
        self.registry = registry or get_default_registry()

    def analyze(
        self,
        manifest: RepositoryManifest,
        code_index: RepositoryCodeIndex,
        code_graph: Optional[CodeGraph] = None,
        root_path: Optional[Path] = None,
        enable_security: bool = True,
        enable_smells: bool = True,
        enable_patterns: bool = True,
        min_severity: Optional[Severity] = None,
        category: Optional[FindingCategory] = None,
    ) -> AnalysisReport:
        """Run all enabled analysis rules and produce an AnalysisReport."""
        logger.info(
            "Starting codebase findings analysis (sec=%s, smell=%s, pat=%s)",
            enable_security,
            enable_smells,
            enable_patterns,
        )

        context = AnalysisContext(
            manifest=manifest,
            code_index=code_index,
            code_graph=code_graph,
            root_path=root_path,
        )

        rules = self.registry.get_rules(
            enable_security=enable_security,
            enable_smells=enable_smells,
            enable_patterns=enable_patterns,
            category=category,
        )

        raw_findings: list[Finding] = []
        for rule in rules:
            try:
                findings = rule.check(context)
                raw_findings.extend(findings)
            except Exception as exc:
                logger.warning("Rule %s failed with exception: %s", rule.rule_id, exc)

        # File validation map for citation verification
        file_map = {f.relative_path.replace("\\", "/"): f for f in manifest.files}

        # Validate source locations and deduplicate
        validated_findings: list[Finding] = []
        seen_keys: set[tuple[str, str, int, int]] = set()

        for f in raw_findings:
            norm_file = f.file.replace("\\", "/")

            # Verify file exists in manifest (allow graph/synthetic root paths if in manifest)
            if norm_file not in file_map:
                logger.debug("Dropping finding with unmapped file: %s", norm_file)
                continue

            file_rec = file_map[norm_file]
            max_lines = file_rec.metadata.line_count

            # Verify line ranges
            if f.start_line < 1:
                continue
            if f.end_line < f.start_line:
                continue
            if max_lines > 0 and f.start_line > max_lines:
                continue

            # Deduplicate by (rule_type, file, start_line, end_line)
            dedup_key = (f.type, norm_file, f.start_line, f.end_line)
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            # Apply severity filter if requested
            if min_severity and f.severity.level < min_severity.level:
                continue

            validated_findings.append(f)

        # Sort findings by severity (descending) and location
        validated_findings.sort(
            key=lambda x: (-x.severity.level, x.file, x.start_line)
        )

        # Summary statistics
        summary = {
            "total": len(validated_findings),
            "critical": sum(1 for f in validated_findings if f.severity == Severity.CRITICAL),
            "high": sum(1 for f in validated_findings if f.severity == Severity.HIGH),
            "medium": sum(1 for f in validated_findings if f.severity == Severity.MEDIUM),
            "low": sum(1 for f in validated_findings if f.severity == Severity.LOW),
            "info": sum(1 for f in validated_findings if f.severity == Severity.INFO),
            "security": sum(1 for f in validated_findings if f.category == FindingCategory.SECURITY),
            "code_smell": sum(1 for f in validated_findings if f.category == FindingCategory.CODE_SMELL),
            "pattern": sum(1 for f in validated_findings if f.category == FindingCategory.PATTERN),
        }

        logger.info(
            "Analysis complete: %d findings (%d security, %d smells, %d patterns)",
            len(validated_findings),
            summary["security"],
            summary["code_smell"],
            summary["pattern"],
        )

        return AnalysisReport(
            repository=manifest.name,
            files_analyzed=len(manifest.files),
            total_findings=len(validated_findings),
            findings=validated_findings,
            summary=summary,
        )
