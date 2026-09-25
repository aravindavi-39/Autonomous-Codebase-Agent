"""AnalysisContext encapsulating repository metadata, AST indexes, graph, and cached file contents."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Optional

from analysis.graph_models import CodeGraph
from analysis.models import FileAnalysis, RepositoryCodeIndex
from ingestion.models import RepositoryManifest
from ingestion.reader import read_file_text
from utils.logger import setup_logger

logger = setup_logger(__name__)


class AnalysisContext:
    """Provides unified, cached access to repository files, AST nodes, and graph relationships."""

    def __init__(
        self,
        manifest: RepositoryManifest,
        code_index: RepositoryCodeIndex,
        code_graph: Optional[CodeGraph] = None,
        root_path: Optional[Path] = None,
    ) -> None:
        self.manifest = manifest
        self.code_index = code_index
        self.code_graph = code_graph
        self.root_path = root_path or Path(manifest.root_path)

        # Caches
        self._analyses_by_path: dict[str, FileAnalysis] = {
            fa.file_path.replace("\\", "/"): fa for fa in code_index.file_analyses
        }
        self._ast_cache: dict[str, Optional[ast.AST]] = {}
        self._content_cache: dict[str, Optional[str]] = {}
        self._lines_cache: dict[str, list[str]] = {}

    def get_analysis(self, file_path: str) -> Optional[FileAnalysis]:
        """Return pre-computed FileAnalysis from code index."""
        norm = file_path.replace("\\", "/")
        return self._analyses_by_path.get(norm)

    def get_content(self, file_path: str) -> Optional[str]:
        """Read and cache text content of a file."""
        norm = file_path.replace("\\", "/")
        if norm in self._content_cache:
            return self._content_cache[norm]

        abs_path = self.root_path / norm
        content = read_file_text(abs_path)
        self._content_cache[norm] = content
        return content

    def get_lines(self, file_path: str) -> list[str]:
        """Return cached lines of text for a file."""
        norm = file_path.replace("\\", "/")
        if norm in self._lines_cache:
            return self._lines_cache[norm]

        content = self.get_content(norm)
        if content is None:
            self._lines_cache[norm] = []
        else:
            self._lines_cache[norm] = content.splitlines()
        return self._lines_cache[norm]

    def get_ast(self, file_path: str) -> Optional[ast.AST]:
        """Parse and cache Python AST for a file."""
        norm = file_path.replace("\\", "/")
        if norm in self._ast_cache:
            return self._ast_cache[norm]

        content = self.get_content(norm)
        if content is None:
            self._ast_cache[norm] = None
            return None

        try:
            tree = ast.parse(content, filename=norm)
            self._ast_cache[norm] = tree
            return tree
        except SyntaxError as exc:
            logger.debug("Syntax error parsing AST for %s: %s", norm, exc)
            self._ast_cache[norm] = None
            return None
        except Exception as exc:
            logger.warning("Failed to parse AST for %s: %s", norm, exc)
            self._ast_cache[norm] = None
            return None
