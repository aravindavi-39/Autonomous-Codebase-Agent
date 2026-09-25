"""Tests for CodeGraph models and query methods."""

import json
from pathlib import Path
import pytest

from analysis.graph_models import (
    CircularDependency,
    CodeGraph,
    GraphNode,
    GraphStatistics,
    NodeType,
    RelationshipEdge,
    RelationshipType,
)


@pytest.fixture
def sample_graph() -> CodeGraph:
    """Construct an in-memory sample graph for query tests."""
    nodes = [
        GraphNode(id="repo:my_project", name="my_project", type=NodeType.REPOSITORY),
        GraphNode(id="file:src/auth.py", name="auth.py", type=NodeType.FILE, file="src/auth.py"),
        GraphNode(id="file:src/user.py", name="user.py", type=NodeType.FILE, file="src/user.py"),
        GraphNode(id="file:tests/test_auth.py", name="test_auth.py", type=NodeType.FILE, file="tests/test_auth.py"),
        GraphNode(id="class:src/user.py:BaseUser", name="BaseUser", type=NodeType.CLASS, file="src/user.py", start_line=5),
        GraphNode(id="class:src/user.py:AdminUser", name="AdminUser", type=NodeType.CLASS, file="src/user.py", start_line=15),
        GraphNode(id="func:src/auth.py:login", name="login", type=NodeType.FUNCTION, file="src/auth.py", start_line=10),
        GraphNode(id="func:src/user.py:find_user", name="find_user", type=NodeType.FUNCTION, file="src/user.py", start_line=25),
        GraphNode(id="func:tests/test_auth.py:test_login", name="test_login", type=NodeType.FUNCTION, file="tests/test_auth.py", start_line=8),
    ]

    edges = [
        RelationshipEdge(source="file:src/auth.py", target="file:src/user.py", type=RelationshipType.DEPENDS_ON, file="src/auth.py", line=2),
        RelationshipEdge(source="file:src/auth.py", target="file:src/user.py", type=RelationshipType.IMPORTS, file="src/auth.py", line=2),
        RelationshipEdge(source="file:src/user.py", target="class:src/user.py:BaseUser", type=RelationshipType.DEFINES, file="src/user.py", line=5),
        RelationshipEdge(source="file:src/user.py", target="class:src/user.py:AdminUser", type=RelationshipType.DEFINES, file="src/user.py", line=15),
        RelationshipEdge(source="file:src/auth.py", target="func:src/auth.py:login", type=RelationshipType.DEFINES, file="src/auth.py", line=10),
        RelationshipEdge(source="class:src/user.py:AdminUser", target="class:src/user.py:BaseUser", type=RelationshipType.INHERITS, file="src/user.py", line=15),
        RelationshipEdge(source="func:src/auth.py:login", target="func:src/user.py:find_user", type=RelationshipType.CALLS, file="src/auth.py", line=12, resolved=True),
        RelationshipEdge(source="func:src/auth.py:login", target="db.query", type=RelationshipType.CALLS, file="src/auth.py", line=13, resolved=False),
        RelationshipEdge(source="file:tests/test_auth.py", target="file:src/auth.py", type=RelationshipType.TESTS, file="tests/test_auth.py", line=1),
        RelationshipEdge(source="func:tests/test_auth.py:test_login", target="func:src/auth.py:login", type=RelationshipType.TESTS, file="tests/test_auth.py", line=8),
    ]

    return CodeGraph(
        nodes=nodes,
        edges=edges,
        statistics=GraphStatistics(total_nodes=len(nodes), total_edges=len(edges)),
    )


class TestCodeGraphQueries:
    """Verify CodeGraph query API."""

    def test_get_node(self, sample_graph: CodeGraph) -> None:
        node = sample_graph.get_node("file:src/auth.py")
        assert node is not None
        assert node.name == "auth.py"
        assert node.type == NodeType.FILE

        by_name = sample_graph.get_node("AdminUser")
        assert by_name is not None
        assert by_name.id == "class:src/user.py:AdminUser"

    def test_get_dependencies_and_dependents(self, sample_graph: CodeGraph) -> None:
        deps = sample_graph.get_dependencies("src/auth.py")
        assert "src/user.py" in deps

        dependents = sample_graph.get_dependents("src/user.py")
        assert "src/auth.py" in dependents

    def test_get_callers_and_callees(self, sample_graph: CodeGraph) -> None:
        callers = sample_graph.get_callers("find_user")
        assert "func:src/auth.py:login" in callers

        callees = sample_graph.get_callees("login")
        assert "func:src/user.py:find_user" in callees
        assert "db.query" in callees

    def test_get_subclasses(self, sample_graph: CodeGraph) -> None:
        subclasses = sample_graph.get_subclasses("BaseUser")
        assert "class:src/user.py:AdminUser" in subclasses

    def test_get_importers(self, sample_graph: CodeGraph) -> None:
        importers = sample_graph.get_importers("src/user.py")
        assert "src/auth.py" in importers

    def test_get_definitions(self, sample_graph: CodeGraph) -> None:
        defs = sample_graph.get_definitions("login")
        assert len(defs) == 1
        assert defs[0].id == "func:src/auth.py:login"

        cls_defs = sample_graph.get_definitions("AdminUser")
        assert len(cls_defs) == 1
        assert cls_defs[0].id == "class:src/user.py:AdminUser"

    def test_get_tests_for_file(self, sample_graph: CodeGraph) -> None:
        tests = sample_graph.get_tests_for_file("src/auth.py")
        assert "file:tests/test_auth.py" in tests

    def test_get_related_entities(self, sample_graph: CodeGraph) -> None:
        related = sample_graph.get_related_entities("src/auth.py")
        names = {n.name for n in related}
        assert "user.py" in names
        assert "login" in names
        assert "test_auth.py" in names

    def test_export_json(self, sample_graph: CodeGraph, tmp_path: Path) -> None:
        out_file = tmp_path / "graph.json"
        json_str = sample_graph.export_json(out_file)
        assert out_file.exists()

        data = json.loads(json_str)
        assert "nodes" in data
        assert "edges" in data
        assert "statistics" in data
        assert len(data["nodes"]) == len(sample_graph.nodes)
        assert len(data["edges"]) == len(sample_graph.edges)
