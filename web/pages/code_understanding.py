"""AST Code Understanding and symbol exploration page for the Autonomous Codebase Agent Web UI."""

from __future__ import annotations

try:
    import streamlit as st
except ImportError:
    st = None  # type: ignore

import web.components as components
import web.state as state


def render() -> None:
    """Render the AST analysis, classes, functions, imports, and calls view."""
    if st is None:
        return

    st.header("🧠 Code Understanding & AST Exploration")
    st.caption("Inspect parsed Python code constructs including classes, functions, imports, and invocations.")

    if not state.is_repo_loaded():
        components.render_not_loaded_warning("Code Understanding")
        return

    code_index = state.get_code_index()
    if not code_index:
        st.info("Code index is not available. Please re-run Load & Analyze.")
        return

    summary = code_index.summary

    # Summary metric cards
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Python Files", summary.python_files_analyzed)
    c2.metric("Classes", summary.total_classes)
    c3.metric("Functions", summary.total_functions)
    c4.metric("Methods", summary.total_methods)
    c5.metric("Imports", summary.total_imports)
    c6.metric("Calls", summary.total_calls)

    if summary.parse_errors > 0:
        st.warning(f"⚠️ {summary.parse_errors} file(s) encountered AST parsing errors.")

    st.divider()

    # Sub-tabs for detailed construct exploration
    tab_classes, tab_funcs, tab_imports, tab_calls = st.tabs(
        ["🏛️ Classes", "⚙️ Functions & Methods", "📦 Imports", "📞 Invocations (Calls)"]
    )

    # 1. Classes Tab
    with tab_classes:
        classes = code_index.get_classes()
        st.subheader(f"Discovered Classes ({len(classes)})")
        class_search = st.text_input("Filter classes by name:", value="", key="class_search")

        filtered_classes = [c for c in classes if class_search.lower() in c.name.lower()] if class_search else classes

        if not filtered_classes:
            st.info("No classes match the search criteria.")
        else:
            for cls in filtered_classes:
                bases_str = f"({', '.join(cls.base_classes)})" if cls.base_classes else ""
                with st.expander(f"class **{cls.name}**{bases_str} — `{cls.file}:{cls.start_line}`"):
                    st.write(f"**File:** `{cls.file}:{cls.start_line}-{cls.end_line}`")
                    if cls.base_classes:
                        st.write(f"**Bases:** {', '.join(f'`{b}`' for b in cls.base_classes)}")
                    if cls.decorators:
                        dec_names = [getattr(d, 'name', str(d)) for d in cls.decorators]
                        st.write(f"**Decorators:** {', '.join(f'`@{d}`' for d in dec_names)}")
                    if cls.docstring:
                        st.markdown(f"**Docstring:**\n> {cls.docstring.strip()}")
                    if cls.methods:
                        st.markdown(f"**Methods ({len(cls.methods)}):**")
                        for m in cls.methods:
                            params = [getattr(p, 'name', str(p)) for p in m.parameters]
                            st.write(f"- `def {m.name}({', '.join(params)})` (Line {m.start_line})")

    # 2. Functions Tab
    with tab_funcs:
        all_funcs = code_index.get_functions(include_methods=True)
        st.subheader(f"Discovered Functions & Methods ({len(all_funcs)})")

        fcol1, fcol2 = st.columns([2, 1])
        func_search = fcol1.text_input("Filter functions by name:", value="", key="func_search")
        func_type = fcol2.selectbox("Type:", ["All", "Standalone Functions Only", "Methods Only"])

        filtered_funcs = all_funcs
        if func_type == "Standalone Functions Only":
            filtered_funcs = [f for f in filtered_funcs if not f.is_method]
        elif func_type == "Methods Only":
            filtered_funcs = [f for f in filtered_funcs if f.is_method]

        if func_search:
            filtered_funcs = [f for f in filtered_funcs if func_search.lower() in f.name.lower()]

        if not filtered_funcs:
            st.info("No functions match the criteria.")
        else:
            for fn in filtered_funcs:
                async_prefix = "async " if fn.is_async else ""
                kind_str = "Method" if fn.is_method else "Function"
                params = [getattr(p, 'name', str(p)) for p in fn.parameters]
                ret_str = f" -> {fn.return_annotation}" if fn.return_annotation else ""

                with st.expander(f"{kind_str}: **{async_prefix}def {fn.name}({', '.join(params)})**{ret_str} — `{fn.file}:{fn.start_line}`"):
                    st.write(f"**Location:** `{fn.file}:{fn.start_line}-{fn.end_line}`")
                    st.write(f"**Parameters:** `{', '.join(params) if params else 'None'}`")
                    if fn.return_annotation:
                        st.write(f"**Return Type:** `{fn.return_annotation}`")
                    if fn.docstring:
                        st.markdown(f"**Docstring:**\n> {fn.docstring.strip()}")
                    if fn.calls:
                        call_targets = [getattr(c, 'target', str(c)) for c in fn.calls]
                        st.write(f"**Calls made:** {', '.join(f'`{t}`' for t in call_targets)}")

    # 3. Imports Tab
    with tab_imports:
        st.subheader("Discovered Imports")
        all_imports = []
        for fa in code_index.file_analyses:
            for imp in fa.imports:
                all_imports.append({
                    "File": fa.file_path,
                    "Module": imp.module,
                    "Name": imp.name or "*",
                    "Category": imp.category,
                    "Line": imp.start_line or imp.line,
                })

        if all_imports:
            st.dataframe(all_imports, use_container_width=True, hide_index=True)
        else:
            st.info("No import statements recorded.")

    # 4. Invocations / Calls Tab
    with tab_calls:
        st.subheader("Discovered Function Invocations")
        all_calls = []
        for fa in code_index.file_analyses:
            for call in fa.calls:
                all_calls.append({
                    "File": fa.file_path,
                    "Target / Callee": call.target,
                    "Line": call.start_line or call.line,
                })

        if all_calls:
            st.dataframe(all_calls, use_container_width=True, hide_index=True)
        else:
            st.info("No cross-function invocations recorded.")
