"""Cycle detection for codebase dependency graphs."""

from __future__ import annotations

from typing import Optional

from analysis.graph_models import CircularDependency, RelationshipEdge


def detect_cycles(
    adj_edges: dict[str, list[tuple[str, RelationshipEdge]]],
) -> list[CircularDependency]:
    """Find all simple circular dependency cycles in a directed graph of modules.

    Args:
        adj_edges: Dictionary mapping module_name -> list of (target_module, edge).

    Returns:
        List of unique :class:`CircularDependency` objects.
    """
    cycles: list[CircularDependency] = []
    visited: set[str] = set()
    rec_stack: list[str] = []
    edge_stack: list[RelationshipEdge] = []
    seen_cycles: set[frozenset[tuple[str, str]]] = set()

    def dfs(curr: str) -> None:
        visited.add(curr)
        rec_stack.append(curr)

        for neighbor, edge in adj_edges.get(curr, []):
            if neighbor not in visited:
                edge_stack.append(edge)
                dfs(neighbor)
                edge_stack.pop()
            elif neighbor in rec_stack:
                # Cycle found!
                cycle_start_idx = rec_stack.index(neighbor)
                cycle_nodes = rec_stack[cycle_start_idx:] + [neighbor]
                cycle_edges = edge_stack[cycle_start_idx:] + [edge]

                # Create normalized set of directed pairs to prevent duplicate cycles
                cycle_pairs = frozenset(
                    (cycle_nodes[i], cycle_nodes[i + 1])
                    for i in range(len(cycle_nodes) - 1)
                )

                if cycle_pairs not in seen_cycles:
                    seen_cycles.add(cycle_pairs)
                    cycles.append(
                        CircularDependency(
                            cycle=cycle_nodes,
                            edges=cycle_edges,
                        )
                    )

        rec_stack.pop()

    for node in sorted(adj_edges.keys()):
        if node not in visited:
            dfs(node)

    return cycles
