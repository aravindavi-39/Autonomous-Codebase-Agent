"""Repository inspection and file browsing page for the Autonomous Codebase Agent Web UI."""

from __future__ import annotations

from pathlib import Path
try:
    import streamlit as st
except ImportError:
    st = None  # type: ignore

import web.components as components
import web.state as state


def render() -> None:
    """Render the repository ingestion and file explorer view."""
    if st is None:
        return

    st.header("📁 Repository Ingestion & File Browser")
    st.caption("Inspect repository structure, language composition, metadata, and individual file contents.")

    if not state.is_repo_loaded():
        components.render_not_loaded_warning("the Repository Browser")
        return

    manifest = state.get_manifest()
    repo_path = state.get_repo_path()
    if not manifest:
        return

    stats = manifest.statistics
    total_bytes = sum(f.metadata.size_bytes for f in manifest.files)

    # High-level statistics
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total Files", f"{stats.total_files:,}")
    col2.metric("Directories", f"{stats.total_directories:,}")
    col3.metric("Total Size", components.format_file_size(total_bytes))
    col4.metric("Test Files", len(stats.test_files))
    col5.metric("Config Files", len(stats.configuration_files))

    st.divider()

    # Discovered Files Table & Filter
    st.subheader("📑 Discovered Files")

    col_filter, col_lang_filter = st.columns([2, 1])
    search_query = col_filter.text_input("Filter by path keyword:", value="", placeholder="e.g. calculator, test, config")
    
    available_langs = ["ALL"] + sorted(list(stats.files_by_language.keys()))
    selected_lang = col_lang_filter.selectbox("Filter by language:", options=available_langs, index=0)

    filtered_files = manifest.files
    if search_query.strip():
        filtered_files = [f for f in filtered_files if search_query.lower() in f.relative_path.lower()]
    if selected_lang != "ALL":
        filtered_files = [
            f for f in filtered_files 
            if (hasattr(f.language, "value") and f.language.value == selected_lang) or str(f.language) == selected_lang
        ]

    st.caption(f"Showing **{len(filtered_files)}** of **{len(manifest.files)}** files")

    table_data = [
        {
            "Relative Path": f.relative_path,
            "Language": f.language.value if hasattr(f.language, "value") else str(f.language),
            "Lines": f.metadata.line_count,
            "Size": components.format_file_size(f.metadata.size_bytes),
            "Binary": "Yes" if f.metadata.is_binary else "No",
        }
        for f in filtered_files
    ]
    st.dataframe(table_data, use_container_width=True, hide_index=True)

    st.divider()

    # Interactive File Content Viewer
    st.subheader("🔍 Interactive File Viewer")
    file_options = [f.relative_path for f in manifest.files if not f.metadata.is_binary]
    if file_options:
        selected_file_path = st.selectbox("Select file to view content:", options=file_options, index=0)
        file_record = next((f for f in manifest.files if f.relative_path == selected_file_path), None)

        if file_record:
            col_meta1, col_meta2, col_meta3 = st.columns(3)
            col_meta1.write(f"**Path:** `{file_record.relative_path}`")
            col_meta2.write(f"**Language:** `{file_record.language.value if hasattr(file_record.language, 'value') else file_record.language}`")
            col_meta3.write(f"**Lines:** `{file_record.metadata.line_count}` | **Size:** `{components.format_file_size(file_record.metadata.size_bytes)}`")

            # Content display from disk
            content = ""
            if manifest.root_path:
                try:
                    full_p = Path(manifest.root_path) / file_record.relative_path
                    if full_p.exists() and full_p.is_file():
                        content = full_p.read_text(encoding="utf-8", errors="replace")
                except Exception as e:
                    content = f"Error reading file content: {e}"

            lang_syntax = "python"
            if file_record.extension in [".toml", ".ini", ".cfg"]:
                lang_syntax = "toml"
            elif file_record.extension in [".json"]:
                lang_syntax = "json"
            elif file_record.extension in [".yaml", ".yml"]:
                lang_syntax = "yaml"
            elif file_record.extension in [".md"]:
                lang_syntax = "markdown"

            st.code(content or "# (Empty file or content not available)", language=lang_syntax)
    else:
        st.info("No text files available to display.")
