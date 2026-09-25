"""Repository code analysis orchestrator.

Coordinates ingestion and Python AST analysis to produce a ``RepositoryCodeIndex``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from analysis.ast_analyzer import PythonASTAnalyzer
from analysis.models import (
    AnalysisSummary,
    FileAnalysis,
    RepositoryCodeIndex,
)
from ingestion.models import Language, RepositoryManifest
from ingestion.pipeline import IngestionPipeline
from utils.logger import setup_logger

logger = setup_logger(__name__)


class RepositoryAnalyzer:
    """Orchestrates code parsing and structural analysis across a repository."""

    def __init__(self) -> None:
        self.analyzer = PythonASTAnalyzer()

    def analyze_repository(
        self,
        source: str,
        manifest: Optional[RepositoryManifest] = None,
    ) -> RepositoryCodeIndex:
        """Run repository ingestion (if needed) and perform AST analysis.

        Args:
            source: Path to the local repository.
            manifest: Optional already-ingested ``RepositoryManifest``.

        Returns:
            A populated ``RepositoryCodeIndex``.
        """
        logger.info("Starting code analysis for repository at: %s", source)

        if manifest is None:
            pipeline = IngestionPipeline()
            manifest = pipeline.ingest(source)

        root = Path(manifest.root_path)

        # 1. Identify local module names for import classification
        local_modules = self._discover_local_modules(manifest)
        self.analyzer.local_modules = local_modules

        # 2. Filter Python files from the manifest
        python_files = [
            f for f in manifest.files
            if f.language == Language.PYTHON or f.extension.lower() in {".py", ".pyi", ".pyw"}
        ]

        logger.info("Found %d Python files to analyze", len(python_files))

        file_analyses: list[FileAnalysis] = []
        total_classes = 0
        total_functions = 0
        total_methods = 0
        total_imports = 0
        total_calls = 0
        parse_errors = 0

        # 3. Analyze each Python file safely
        for f in python_files:
            abs_path = root / Path(f.relative_path)
            try:
                fa = self.analyzer.analyze_file(
                    abs_path,
                    relative_path=f.relative_path,
                    local_modules=local_modules,
                )
            except Exception as exc:  # Defensive catch to never crash entire analysis
                logger.error("Failed to analyze %s: %s", f.relative_path, exc)
                fa = FileAnalysis(
                    file_path=f.relative_path,
                    status="parse_error",
                    error_message=str(exc),
                )

            file_analyses.append(fa)

            if fa.status != "ok":
                parse_errors += 1
                continue

            total_classes += len(fa.classes)
            total_functions += len(fa.functions)
            total_methods += sum(len(c.methods) for c in fa.classes)
            total_imports += len(fa.imports)

            # Sum calls inside functions, methods, and at module level
            file_calls = len(fa.calls)
            for fn in fa.functions:
                file_calls += len(fn.calls)
                for n_fn in fn.nested_functions:
                    file_calls += len(n_fn.calls)
            for cls in fa.classes:
                for m in cls.methods:
                    file_calls += len(m.calls)
            total_calls += file_calls

        summary = AnalysisSummary(
            python_files_analyzed=len(python_files),
            parse_errors=parse_errors,
            total_classes=total_classes,
            total_functions=total_functions,
            total_methods=total_methods,
            total_imports=total_imports,
            total_calls=total_calls,
        )

        logger.info(
            "Analysis complete: %d files, %d classes, %d functions, %d methods, %d calls",
            summary.python_files_analyzed,
            summary.total_classes,
            summary.total_functions,
            summary.total_methods,
            summary.total_calls,
        )

        return RepositoryCodeIndex(
            manifest=manifest,
            file_analyses=file_analyses,
            summary=summary,
        )

    def _discover_local_modules(self, manifest: RepositoryManifest) -> set[str]:
        """Derive top-level package and module names from repository files."""
        local_modules: set[str] = set()
        for f in manifest.files:
            rel = Path(f.relative_path)
            parts = rel.parts
            if parts:
                top = parts[0]
                if top.endswith(".py"):
                    local_modules.add(top[:-3])
                else:
                    local_modules.add(top)
            if f.file_name.endswith(".py"):
                local_modules.add(f.file_name[:-3])
        return local_modules
