"""Codebase Q&A with grounded retrieval and source citations for the Web UI."""

from __future__ import annotations

from pathlib import Path
try:
    import streamlit as st
except ImportError:
    st = None  # type: ignore

from citations.validator import CitationValidator
from llm.base import LLMConfigurationError, LLMError
from llm.fake_provider import FakeLLMProvider
from llm.openai_provider import OpenAIProvider
from retrieval.chunker import SemanticChunker
from retrieval.context_builder import ContextBuilder
from retrieval.qa_engine import QAEngine
from retrieval.retriever import HybridRetriever
from retrieval.vector_store import create_vector_store
import web.components as components
import web.state as state


def render() -> None:
    """Render the grounded codebase question answering page."""
    if st is None:
        return

    st.header("💬 Codebase Q&A with Grounded Citations")
    st.caption("Ask architectural or implementation questions backed by hybrid semantic/structural retrieval and verified source citations.")

    if not state.is_repo_loaded():
        components.render_not_loaded_warning("Codebase Q&A")
        return

    manifest = state.get_manifest()
    code_index = state.get_code_index()
    code_graph = state.get_code_graph()

    if not manifest:
        return

    llm_cfg = state.get_llm_config()
    retrieval_cfg = state.get_retrieval_config()

    # Query Input Section
    sample_questions = [
        "What does this codebase do and what are its entry points?",
        "What functions are defined in this repository and how are they implemented?",
        "Are there any mutable default arguments or potential bugs in this codebase?",
        "How do modules in this codebase depend on each other?",
    ]
    selected_sample = st.selectbox("Sample Questions:", ["(Select a question...)"] + sample_questions)
    default_q = selected_sample if selected_sample != "(Select a question...)" else ""

    user_question = st.text_input("Your Question:", value=default_q, placeholder="Ask how a module or function works...")

    # Retrieval settings expander
    with st.expander("⚙️ Query Retrieval Settings", expanded=False):
        c1, c2 = st.columns(2)
        top_k = c1.slider("Top Chunks (k):", min_value=1, max_value=15, value=retrieval_cfg.get("top_k", 5))
        max_context = c2.slider("Max Context Chars:", min_value=2000, max_value=30000, value=retrieval_cfg.get("max_context", 12000), step=1000)
        c3, c4 = st.columns(2)
        use_semantic = c3.checkbox("Semantic Vector Search", value=retrieval_cfg.get("use_semantic", True))
        use_graph = c4.checkbox("Structural Graph Traversal", value=retrieval_cfg.get("use_graph", True))

    ask_btn = st.button("🔎 Submit Question", type="primary")

    if ask_btn and user_question.strip():
        with st.spinner("Searching codebase and synthesizing grounded answer..."):
            try:
                # LLM Provider setup
                if llm_cfg.get("mock_mode", True):
                    provider = FakeLLMProvider()
                else:
                    api_key = llm_cfg.get("api_key") or None
                    provider = OpenAIProvider(api_key=api_key, model=llm_cfg.get("model", "gpt-4o-mini"))
                    provider._get_client()

                root_path = Path(manifest.root_path)
                chunker = SemanticChunker(root_path=root_path)
                chunks = chunker.chunk_repository(manifest=manifest, code_index=code_index)

                vector_store = create_vector_store()
                if use_semantic:
                    vector_store.index(chunks, provider=provider)

                citation_validator = CitationValidator(manifest=manifest, code_index=code_index)
                retriever = HybridRetriever(
                    vector_store=vector_store,
                    code_graph=code_graph,
                    code_index=code_index,
                )
                context_builder = ContextBuilder(max_chunks=top_k, max_context_chars=max_context)
                qa_engine = QAEngine(
                    retriever=retriever,
                    llm_provider=provider,
                    citation_validator=citation_validator,
                    context_builder=context_builder,
                )

                response = qa_engine.ask(
                    question=user_question,
                    top_k=top_k,
                    max_context_chars=max_context,
                    enable_semantic=use_semantic,
                    enable_graph=use_graph,
                )

                # Store into history
                state.add_qa_history_entry({
                    "question": user_question,
                    "answer": response.answer,
                    "citations": [components.format_citation_markdown(c) for c in response.citations],
                    "is_grounded": getattr(response, "is_grounded", bool(response.citations)),
                })

                # Display Current Answer
                st.markdown("### Answer")
                st.markdown(response.answer)

                st.markdown("### Verified Source Citations")
                if response.citations:
                    for cit in response.citations:
                        st.markdown(components.format_citation_markdown(cit))
                else:
                    st.info("No specific source citations matched.")

                is_grounded = getattr(response, "is_grounded", bool(response.citations))
                if is_grounded:
                    st.success("✅ Answer is verified and grounded in repository source code.")
                else:
                    st.warning("⚠️ Insufficient evidence in retrieved chunks. Answer may be incomplete.")

            except LLMConfigurationError as exc:
                st.error(f"Configuration Error: {exc}. Toggle 'Offline / Mock Mode' in Settings to run offline.")
            except Exception as exc:
                st.error(f"Q&A Execution Error: {exc}")

    # Display Session Q&A History
    history = state.get_qa_history()
    if history:
        st.divider()
        st.subheader(f"📜 Session Q&A History ({len(history)})")
        for i, item in enumerate(reversed(history), 1):
            with st.expander(f"Q: {item['question']}", expanded=(i == 1)):
                st.markdown(item["answer"])
                if item["citations"]:
                    st.markdown("**Citations:**")
                    for c in item["citations"]:
                        st.markdown(c)
