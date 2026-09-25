"""Ingestion pipeline orchestrator."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ingestion.discoverer import discover_files
from ingestion.manifest import export_manifest_json
from ingestion.models import RepositoryManifest
from ingestion.statistics import calculate_statistics
from ingestion.validator import validate_repository_path
from utils.logger import setup_logger

logger = setup_logger(__name__)


class IngestionPipeline:
    """Orchestrates the full repository ingestion process."""

    def __init__(self, max_file_size_kb: int = 500) -> None:
        self.max_file_size: int = max_file_size_kb * 1024
        self._manifest: Optional[RepositoryManifest] = None

    @property
    def manifest(self) -> Optional[RepositoryManifest]:
        """The most recently generated manifest, or ``None``."""
        return self._manifest

    def ingest(self, source: str) -> RepositoryManifest:
        """Run the ingestion pipeline on a local repository at *source*.

        Returns:
            A fully populated :class:`RepositoryManifest`.
        """
        logger.info("Starting ingestion for: %s", source)

        # 1. Validate
        root = validate_repository_path(source)

        # 2. Discover
        files, directories = discover_files(root, max_file_size=self.max_file_size)

        # 3. Statistics
        stats = calculate_statistics(files, total_directories=len(directories))

        # 4. Build manifest
        self._manifest = RepositoryManifest(
            name=root.name,
            root_path=str(root),
            files=files,
            directories=directories,
            statistics=stats,
        )

        logger.info(
            "Ingestion complete: %d files, %d dirs, %d lines",
            stats.total_files,
            stats.total_directories,
            stats.total_lines,
        )
        return self._manifest

    def export_json(self, output_path: Optional[str] = None) -> str:
        """Export the current manifest as JSON."""
        if self._manifest is None:
            raise RuntimeError("No manifest available. Run ingest() first.")
        path = Path(output_path) if output_path else None
        return export_manifest_json(self._manifest, path)
