"""Structured models for codebase relationship graph and dependency analysis.

Defines node types, relationship types, graph edges, and queryable CodeGraph.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field


class RelationshipType(str, Enum):
    """Types of directed relationships between codebase entities."""

    IMPORTS = "IMPORTS"
    DEFINES = "DEFINES"
    CALLS = "CALLS"
    INHERITS = "INHERITS"
    CONTAINS = "CONTAINS"
    TESTS = "TESTS"
    DEPENDS_ON = "DEPENDS_ON"


class NodeType(str, Enum):
    """Types of nodes in the codebase graph."""

    REPOSITORY = "repository"
    DIRECTORY = "directory"
    FILE = "file"
    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"


class GraphNode(BaseModel):
    """A node in the code relationship graph."""

    id: str = Field(..., description="Unique node identifier, e.g. 'file:src/app.py'")
    name: str = Field(..., description="Human-readable name of the entity")
    type: NodeType = Field(..., description="Category of entity")
    file: str = Field("", description="Source file relative to repository root")
    start_line: int = Field(0, description="Start line in source file (if applicable)")
    end_line: Optional[int] = Field(None, description="End line in source file (if applicable)")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Arbitrary extra metadata")


class RelationshipEdge(BaseModel):
    """A directed edge representing a relationship between two entities."""

    source: str = Field(..., description="Source entity ID or identifier")
    target: str = Field(..., description="Target entity ID or identifier")
    type: RelationshipType = Field(..., description="Type of relationship")
    file: str = Field("", description="Source file where relationship occurs")
    line: int = Field(0, description="Source line number where relationship occurs")
    resolved: bool = Field(True, description="Whether the target entity was definitely resolved in repo")
    confidence: float = Field(1.0, description="Confidence score from 0.0 to 1.0")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional context or properties")


class CircularDependency(BaseModel):
    """A detected cycle in module dependencies."""

    cycle: list[str] = Field(..., description="Ordered list of module names forming the cycle")
    edges: list[RelationshipEdge] = Field(default_factory=list, description="Dependency edges forming the cycle")

    @property
    def cycle_str(self) -> str:
        """Return human-readable 'A -> B -> C -> A' string representation."""
        return " -> ".join(self.cycle)


class InheritanceRelation(BaseModel):
    """Inheritance link between two classes."""

    subclass: str
    base_class: str
    file: str = ""
    line: int = 0


class GraphStatistics(BaseModel):
    """Aggregate statistics and architectural metrics for the code graph."""

    total_nodes: int = 0
    total_edges: int = 0
    nodes_by_type: dict[str, int] = Field(default_factory=dict)
    relationships_by_type: dict[str, int] = Field(default_factory=dict)
    most_imported_modules: list[tuple[str, int]] = Field(default_factory=list)
    most_depended_on_modules: list[tuple[str, int]] = Field(default_factory=list)
    modules_with_many_dependencies: list[tuple[str, int]] = Field(default_factory=list)
    circular_dependencies: list[CircularDependency] = Field(default_factory=list)
    inheritance_relationships: list[InheritanceRelation] = Field(default_factory=list)


class CodeGraph(BaseModel):
    """Complete codebase relationship graph with fast lookup and query methods."""

    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[RelationshipEdge] = Field(default_factory=list)
    statistics: GraphStatistics = Field(default_factory=GraphStatistics)

    # ------------------------------------------------------------------
    # Query methods
    # ------------------------------------------------------------------

    def get_node(self, identifier: str) -> Optional[GraphNode]:
        """Find a node by its exact id, or by exact name."""
        for n in self.nodes:
            if n.id == identifier or n.name == identifier:
                return n
        return None

    def get_dependencies(self, file_or_module: str) -> list[str]:
        """Return target files/modules that *file_or_module* depends on via DEPENDS_ON or IMPORTS."""
        targets: set[str] = set()
        clean = _clean_identifier(file_or_module)
        for e in self.edges:
            if e.type in (RelationshipType.DEPENDS_ON, RelationshipType.IMPORTS):
                src_clean = _clean_identifier(e.source)
                if src_clean == clean or e.file == file_or_module:
                    targets.add(_clean_identifier(e.target))
        return sorted(list(targets))

    def get_dependents(self, file_or_module: str) -> list[str]:
        """Return files/modules that depend on *file_or_module*."""
        sources: set[str] = set()
        clean = _clean_identifier(file_or_module)
        for e in self.edges:
            if e.type in (RelationshipType.DEPENDS_ON, RelationshipType.IMPORTS):
                tgt_clean = _clean_identifier(e.target)
                if tgt_clean == clean:
                    sources.add(_clean_identifier(e.source))
        return sorted(list(sources))

    def get_callers(self, function_name: str) -> list[str]:
        """Return names or IDs of functions/callers that invoke *function_name*."""
        callers: set[str] = set()
        clean = _clean_identifier(function_name)
        for e in self.edges:
            if e.type == RelationshipType.CALLS:
                tgt_clean = _clean_identifier(e.target)
                if tgt_clean == clean or e.target.endswith(f".{clean}") or e.target.endswith(f":{clean}"):
                    callers.add(e.source)
        return sorted(list(callers))

    def get_callees(self, function_name: str) -> list[str]:
        """Return names or IDs of entities called by *function_name*."""
        callees: set[str] = set()
        clean = _clean_identifier(function_name)
        for e in self.edges:
            if e.type == RelationshipType.CALLS:
                src_clean = _clean_identifier(e.source)
                if src_clean == clean or e.source.endswith(f".{clean}") or e.source.endswith(f":{clean}"):
                    callees.add(e.target)
        return sorted(list(callees))

    def get_subclasses(self, class_name: str) -> list[str]:
        """Return names or IDs of classes that inherit from *class_name*."""
        subclasses: set[str] = set()
        clean = _clean_identifier(class_name)
        for e in self.edges:
            if e.type == RelationshipType.INHERITS:
                tgt_clean = _clean_identifier(e.target)
                if tgt_clean == clean or e.target.endswith(f".{clean}") or e.target.endswith(f":{clean}"):
                    subclasses.add(e.source)
        return sorted(list(subclasses))

    def get_importers(self, module_name: str) -> list[str]:
        """Return files or modules that import *module_name*."""
        return self.get_dependents(module_name)

    def get_definitions(self, name: str) -> list[GraphNode]:
        """Return GraphNodes defining the given name (class, function, method, variable)."""
        matching: list[GraphNode] = []
        for n in self.nodes:
            if n.name == name or n.name.endswith(f".{name}"):
                if n.type in (NodeType.CLASS, NodeType.FUNCTION, NodeType.METHOD):
                    matching.append(n)
        return matching

    def get_tests_for_file(self, file_path: str) -> list[str]:
        """Return test files or test functions that test *file_path*."""
        tests: set[str] = set()
        clean = _clean_identifier(file_path)
        for e in self.edges:
            if e.type == RelationshipType.TESTS:
                tgt_clean = _clean_identifier(e.target)
                if tgt_clean == clean or e.target.endswith(f":{clean}") or e.target.endswith(f"/{clean}"):
                    tests.add(e.source)
        return sorted(list(tests))

    def get_related_entities(self, entity: str) -> list[GraphNode]:
        """Return all nodes connected to *entity* by either incoming or outgoing edges."""
        clean = _clean_identifier(entity)
        neighbor_ids: set[str] = set()

        for e in self.edges:
            s_clean = _clean_identifier(e.source)
            t_clean = _clean_identifier(e.target)
            if s_clean == clean or e.source == entity:
                neighbor_ids.add(e.target)
            elif t_clean == clean or e.target == entity:
                neighbor_ids.add(e.source)

        results: list[GraphNode] = []
        for nid in neighbor_ids:
            node = self.get_node(nid)
            if node:
                results.append(node)
        return results

    def export_json(self, output_path: Optional[str | Path] = None) -> str:
        """Export the graph as deterministic, formatted JSON with nodes, edges, and statistics."""
        data = {
            "nodes": [n.model_dump() for n in self.nodes],
            "edges": [e.model_dump() for e in self.edges],
            "statistics": self.statistics.model_dump(),
        }
        import json
        json_str = json.dumps(data, indent=2, sort_keys=False)
        if output_path:
            p = Path(output_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json_str, encoding="utf-8")
        return json_str


def _clean_identifier(ident: str) -> str:
    """Normalize identifiers by removing type prefixes like 'file:', 'func:', 'module:'."""
    if ":" in ident:
        parts = ident.split(":", 1)
        if parts[0] in ("file", "module", "class", "func", "method", "dir", "repo"):
            return parts[1]
    return ident
