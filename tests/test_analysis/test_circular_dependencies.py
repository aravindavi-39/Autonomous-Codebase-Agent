"""Tests for circular dependency detection."""

import pytest

from analysis.cycles import detect_cycles
from analysis.graph_models import RelationshipEdge, RelationshipType


def _make_edge(src: str, tgt: str, file: str = "src/a.py", line: int = 1) -> RelationshipEdge:
    return RelationshipEdge(
        source=src,
        target=tgt,
        type=RelationshipType.DEPENDS_ON,
        file=file,
        line=line,
    )


class TestCircularDependencyDetection:
    """Verify cycle detection on module dependency graphs."""

    def test_no_cycle_in_dag(self) -> None:
        adj = {
            "A": [("B", _make_edge("A", "B")), ("C", _make_edge("A", "C"))],
            "B": [("D", _make_edge("B", "D"))],
            "C": [("D", _make_edge("C", "D"))],
            "D": [],
        }
        cycles = detect_cycles(adj)
        assert len(cycles) == 0

    def test_direct_two_node_cycle(self) -> None:
        edge_ab = _make_edge("A", "B", "src/a.py", 5)
        edge_ba = _make_edge("B", "A", "src/b.py", 10)
        adj = {
            "A": [("B", edge_ab)],
            "B": [("A", edge_ba)],
        }
        cycles = detect_cycles(adj)
        assert len(cycles) == 1
        cycle = cycles[0]
        assert cycle.cycle == ["A", "B", "A"] or cycle.cycle == ["B", "A", "B"]
        assert len(cycle.edges) == 2
        assert " -> " in cycle.cycle_str

    def test_three_node_cycle(self) -> None:
        edge_ab = _make_edge("A", "B", "src/a.py", 3)
        edge_bc = _make_edge("B", "C", "src/b.py", 7)
        edge_ca = _make_edge("C", "A", "src/c.py", 12)
        adj = {
            "A": [("B", edge_ab)],
            "B": [("C", edge_bc)],
            "C": [("A", edge_ca)],
        }
        cycles = detect_cycles(adj)
        assert len(cycles) == 1
        assert len(cycles[0].cycle) == 4
        assert cycles[0].cycle[0] == cycles[0].cycle[-1]
        assert len(cycles[0].edges) == 3

    def test_multiple_cycles(self) -> None:
        # A <-> B and C <-> D
        adj = {
            "A": [("B", _make_edge("A", "B"))],
            "B": [("A", _make_edge("B", "A"))],
            "C": [("D", _make_edge("C", "D"))],
            "D": [("C", _make_edge("D", "C"))],
        }
        cycles = detect_cycles(adj)
        assert len(cycles) == 2

    def test_self_dependency_cycle(self) -> None:
        edge = _make_edge("A", "A", "src/a.py", 1)
        adj = {"A": [("A", edge)]}
        cycles = detect_cycles(adj)
        assert len(cycles) == 1
        assert cycles[0].cycle == ["A", "A"]
