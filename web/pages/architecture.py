"""Architecture and CodeGraph dependency relationship page for the Autonomous Codebase Agent Web UI."""

from __future__ import annotations

try:
    import streamlit as st
except ImportError:
    st = None  # type: ignore

import web.components as components
import web.state as state


def render() -> None:
    """Render the CodeGraph relationships, dependency structure, and cycles view."""
    if st is None:
        return

    st.header("🕸️ Architecture & CodeGraph Dependency Analysis")
    st.caption("Explore codebase relationships, circular dependency risks, and modular architecture.")

    if not state.is_repo_loaded():
        components.render_not_loaded_warning("Architecture & CodeGraph")
        return

    code_graph = state.get_code_graph()
    code_index = state.get_code_index()

    if not code_graph:
        st.info("CodeGraph is not available. Please re-run Load & Analyze.")
        return

    # Bug Fix 1: Use code_graph.statistics directly instead of code_graph.compute_statistics()
    graph_stats = code_graph.statistics

    # Bug Fixes 2 & 3: Use code_index.get_classes() and get_functions()
    total_classes = len(code_index.get_classes()) if code_index else 0
    total_functions = len(code_index.get_functions()) if code_index else 0

    col_g1, col_g2, col_g3, col_g4 = st.columns(4)
    col_g1.metric("Graph Nodes", graph_stats.total_nodes)
    col_g2.metric("Graph Edges", graph_stats.total_edges)
    col_g3.metric("Classes", total_classes)
    col_g4.metric("Functions", total_functions)

    st.divider()

    col_rel, col_hot = st.columns([1, 1])
    with col_rel:
        st.markdown("### 🔗 Relationship Types")
        if graph_stats.relationships_by_type:
            rel_data = [
                {"Relationship": rel, "Count": count}
                for rel, count in sorted(graph_stats.relationships_by_type.items())
            ]
            st.dataframe(rel_data, use_container_width=True, hide_index=True)
        else:
            st.info("No inter-module relationships found.")

    with col_hot:
        st.markdown("### 🔁 Circular Dependencies & Hotspots")
        if graph_stats.circular_dependencies:
            for cycle in graph_stats.circular_dependencies:
                st.error(f"Cycle Detected: `{cycle.cycle_str}`")
        else:
            st.success("✅ Zero circular dependencies detected.")

        if graph_stats.most_depended_on_modules:
            st.markdown("**Top Depended-On Modules:**")
            for mod, count in graph_stats.most_depended_on_modules[:5]:
                st.write(f"- `{mod}` ({count} references)")

    st.divider()

    # Interactive Entity Dependency Explorer
    st.subheader("🔍 Interactive Entity & Module Explorer")
    node_options = [n.id for n in code_graph.nodes] if code_graph.nodes else []
    if node_options:
        selected_node_id = st.selectbox("Select node / entity to inspect:", options=node_options, index=0)
        selected_node = code_graph.get_node(selected_node_id)

        if selected_node:
            st.write(f"**Name:** `{selected_node.name}` | **Type:** `{selected_node.type.value}` | **File:** `{selected_node.file}`")

            col_dep1, col_dep2 = st.columns(2)
            with col_dep1:
                st.markdown("**Depends On (Outgoing):**")
                deps = code_graph.get_dependencies(selected_node.name) or code_graph.get_dependencies(selected_node.file)
                if deps:
                    for d in deps:
                        st.write(f"- `{d}`")
                else:
                    st.caption("No outgoing dependencies.")

            with col_dep2:
                st.markdown("**Dependents (Incoming):**")
                dependents = code_graph.get_dependents(selected_node.name) or code_graph.get_dependents(selected_node.file)
                if dependents:
                    for d in dependents:
                        st.write(f"- `{d}`")
                else:
                    st.caption("No dependents reference this entity.")
    else:
        st.info("No nodes available in CodeGraph.")
