"""Repository manifest generation and JSON export."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ingestion.models import RepositoryManifest
from utils.logger import setup_logger

logger = setup_logger(__name__)


def export_manifest_json(
    manifest: RepositoryManifest,
    output_path: Optional[Path] = None,
) -> str:
    """Serialise *manifest* to a JSON string.

    If *output_path* is given the JSON is also written to that file.
    """
    json_str = manifest.model_dump_json(indent=2)
    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json_str, encoding="utf-8")
        logger.info("Manifest exported to: %s", output_path)
    return json_str
