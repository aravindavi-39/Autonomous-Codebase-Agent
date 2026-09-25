"""FindingDeltaEngine: evidence-based comparison of baseline vs post-patch analysis findings."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from analysis.analyzer import RepositoryAnalyzer
from analysis.findings.context import AnalysisContext
from analysis.findings.engine import AnalysisEngine
from analysis.findings.models import AnalysisReport, Finding
from analysis.graph_builder import CodeGraphBuilder
from ingestion.pipeline import IngestionPipeline
from utils.logger import setup_logger
from verification.models import FindingDelta

logger = setup_logger(__name__)


def findings_match(f1: Finding, f2: Finding) -> bool:
    """Determine whether two findings refer to the same logical issue across edits.

    Handles line number shifts that naturally occur when patches insert or delete lines.
    """
    # 1. Exact ID match
    if f1.id == f2.id:
        return True

    # 2. Must share same rule type and relative file
    f1_file = f1.file.replace("\\", "/")
    f2_file = f2.file.replace("\\", "/")
    if f1.type != f2.type or f1_file != f2_file:
        return False

    # 3. If both reference an entity, matching entity confirms identity
    if f1.entity and f2.entity and f1.entity == f2.entity:
        return True

    # 4. If evidence is identical, confirm identity
    if f1.evidence and f2.evidence and f1.evidence.strip() == f2.evidence.strip():
        return True

    # 5. Proximity match if lines shifted by a small offset (within 15 lines)
    if abs(f1.start_line - f2.start_line) <= 15:
        # Check if titles or descriptions match
        if f1.title == f2.title:
            return True

    return False


class FindingDeltaEngine:
    """Calculates evidence-based finding deltas between baseline and post-patch repository states."""

    def __init__(self, analysis_engine: Optional[AnalysisEngine] = None) -> None:
        self.analysis_engine = analysis_engine or AnalysisEngine()

    def analyze_repository_findings(self, repo_path: Path) -> list[Finding]:
        """Run standard ingestion, AST indexing, graph building, and findings analysis on a directory."""
        resolved = repo_path.resolve()
        pipeline = IngestionPipeline()
        manifest = pipeline.ingest(str(resolved))

        analyzer = RepositoryAnalyzer()
        code_index = analyzer.analyze_repository(str(resolved), manifest=manifest)

        try:
            builder = CodeGraphBuilder()
            code_graph = builder.build_graph(code_index)
        except Exception:
            code_graph = None

        report = self.analysis_engine.analyze(
            manifest=manifest,
            code_index=code_index,
            code_graph=code_graph,
        )
        return report.findings

    def compute_delta(
        self,
        baseline_findings: list[Finding],
        post_patch_findings: list[Finding],
        target_finding_id: Optional[str] = None,
    ) -> FindingDelta:
        """Compute the findings delta between baseline and post-patch findings.

        Args:
            baseline_findings: Findings present prior to patch application.
            post_patch_findings: Findings present after patch application.
            target_finding_id: Specific finding ID targeted for refactoring.

        Returns:
            FindingDelta containing resolved, remaining, and genuinely new findings.
        """
        # Find target finding in baseline if specified
        target_in_baseline: Optional[Finding] = None
        if target_finding_id:
            for bf in baseline_findings:
                if bf.id == target_finding_id:
                    target_in_baseline = bf
                    break

        matched_post_indices: set[int] = set()
        resolved_findings: list[Finding] = []
        remaining_findings: list[Finding] = []

        # For every baseline finding, find if it still exists in post-patch
        for bf in baseline_findings:
            found_match = False
            for idx, pf in enumerate(post_patch_findings):
                if idx in matched_post_indices:
                    continue

                if findings_match(bf, pf):
                    found_match = True
                    matched_post_indices.add(idx)
                    remaining_findings.append(pf)
                    break

            if not found_match:
                resolved_findings.append(bf)

        # Any post-patch findings that did NOT match a baseline finding are genuinely new
        new_findings: list[Finding] = [
            pf for idx, pf in enumerate(post_patch_findings) if idx not in matched_post_indices
        ]

        # Target resolution verification
        target_resolved = False
        if target_in_baseline:
            target_existed = True
            # Verified eliminated if target is in resolved_findings and NOT matched in post-patch
            target_still_exists = any(findings_match(target_in_baseline, pf) for pf in post_patch_findings)
            target_resolved = not target_still_exists
        else:
            target_existed = False
            target_resolved = False

        summary_parts = [
            f"Baseline: {len(baseline_findings)} finding(s)",
            f"Post-patch: {len(post_patch_findings)} finding(s)",
            f"Resolved: {len(resolved_findings)}",
            f"Remaining: {len(remaining_findings)}",
            f"Newly introduced: {len(new_findings)}",
        ]
        if target_finding_id:
            res_str = "RESOLVED" if target_resolved else "UNRESOLVED"
            summary_parts.append(f"Target '{target_finding_id}': {res_str}")

        return FindingDelta(
            target_finding_id=target_finding_id,
            target_existed_in_baseline=target_existed,
            target_resolved=target_resolved,
            baseline_findings_count=len(baseline_findings),
            post_patch_findings_count=len(post_patch_findings),
            resolved_findings=resolved_findings,
            remaining_findings=remaining_findings,
            new_findings=new_findings,
            summary=" | ".join(summary_parts),
        )
