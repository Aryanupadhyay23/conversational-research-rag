import streamlit as st
import os
import sys
import datetime
import uuid

# Ensure project root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from frontend.api_client import (
    check_backend_health,
    upload_documents,
    upload_documents_stream,
    stream_chat,
    compute_files_hash,
    fetch_user_sessions,
    save_user_sessions_to_backend,
)
from frontend.components import (
    inject_custom_theme,
    render_header,
    render_session_sidebar,
    render_document_management_card,
    render_welcome_screen,
    render_chat_history,
    render_message_turn,
    render_formatted_markdown,
    render_verdict_badge,
    render_grounding_badge,
    render_sources_section,
)

# Streamlit Page Setup
st.set_page_config(
    page_title="Research Paper RAG Project",
    layout="wide",
    page_icon="📄"
)

# Inject obsidian black styling
inject_custom_theme()

# Initialize User & Multi-Session Conversation History
# Generate unique guest identity per visitor so new arrivals always get a fresh conversation
if "username" not in st.session_state:
    st.session_state.username = f"guest_{uuid.uuid4().hex[:6]}"

if "sessions" not in st.session_state:
    init_id = f"session_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}"
    fresh_session = {
        "title": "New Research Chat",
        "messages": [],
        "created_at": datetime.datetime.now().strftime("%b %d, %H:%M")
    }
    loaded = fetch_user_sessions(st.session_state.username)
    if loaded:
        st.session_state.sessions = loaded
        st.session_state.sessions[init_id] = fresh_session
    else:
        st.session_state.sessions = {init_id: fresh_session}
    st.session_state.current_session_id = init_id

if "uploaded_hash" not in st.session_state:
    st.session_state.uploaded_hash = None
if "pdf_bytes_map" not in st.session_state:
    st.session_state.pdf_bytes_map = {}

# Sidebar Conversation History Navigation
active_session_id = render_session_sidebar()
if active_session_id not in st.session_state.sessions:
    st.session_state.sessions[active_session_id] = {
        "title": "New Research Chat",
        "messages": [],
        "created_at": datetime.datetime.now().strftime("%b %d, %H:%M")
    }
active_session = st.session_state.sessions[active_session_id]


# Main Header Banner
render_header()

# Check FastAPI Backend Connectivity (cached with 10s TTL to avoid blocking reruns)
@st.cache_data(ttl=10)
def cached_backend_health():
    return check_backend_health()

is_backend_online, backend_msg = cached_backend_health()
if not is_backend_online:
    st.warning(
        f"⚠️ **FastAPI Backend Offline:** {backend_msg}\n\n"
        "Start the backend server in your terminal: `uvicorn api:app --reload --port 8000`"
    )

# Multiple PDF Document Uploader Section
with st.container():
    uploaded_files = st.file_uploader(
        "Upload Research Papers (Multiple PDF Support)",
        type=["pdf"],
        accept_multiple_files=True,
        help="Upload one or multiple research papers to query and cross-examine."
    )

    if uploaded_files:
        current_hash = compute_files_hash(uploaded_files)
        # Cache raw bytes for interactive visual page rendering and citation previews
        st.session_state.pdf_bytes_map = {
            f.name: (f.getvalue() if hasattr(f, "getvalue") else f.read())
            for f in uploaded_files
        }

        if st.session_state.uploaded_hash != current_hash:
            if not is_backend_online:
                st.error("Cannot upload documents: FastAPI backend is unreachable. Start the backend first.")
            else:
                progress_container = st.empty()
                indexing_successful = False
                completed_chunks = 0
                completed_requests_cnt = 0
                total_requests_cnt = 0

                try:
                    for event in upload_documents_stream(
                        uploaded_files,
                        session_id=st.session_state.current_session_id,
                        username=st.session_state.username,
                    ):
                        ev_type = event.get("type")

                        if ev_type == "progress":
                            stage = event.get("stage", "parsing")
                            pct = float(event.get("percent", 0.0)) / 100.0
                            pct_clamped = min(1.0, max(0.0, pct))

                            with progress_container.container():
                                if stage == "parsing":
                                    st.markdown("### ⚡ **Generating embeddings…**")
                                    st.progress(pct_clamped)
                                    col1, col2 = st.columns(2)
                                    col1.markdown("**Progress:** Calculating estimated time…")
                                    col2.markdown("**Estimated time remaining:** Calculating…")
                                    st.caption(
                                        "ℹ️ *Extracting text & layout from research papers. Request counts and dynamic estimates will appear once chunking completes.*"
                                    )
                                else:
                                    completed = event.get("completed_requests", 0)
                                    total_reqs = event.get("total_requests", 1)
                                    est_rem = event.get("estimated_remaining_seconds", 0.0)
                                    elapsed = event.get("elapsed_seconds", 0.0)
                                    rate = event.get("rate_seconds_per_req", 1.07)
                                    chunks = event.get("total_chunks", 0)
                                    chunk_size = event.get("chunk_size", 10)

                                    completed_requests_cnt = completed
                                    total_requests_cnt = total_reqs

                                    st.markdown("### ⚡ **Generating embeddings…**")
                                    st.progress(pct_clamped)
                                    col1, col2, col3 = st.columns(3)
                                    col1.metric(
                                        label="Embedding Requests",
                                        value=f"{completed} of {total_reqs} completed",
                                        delta=f"{pct * 100:.0f}%"
                                    )
                                    col2.metric(
                                        label="Estimated time remaining",
                                        value=f"~{est_rem:.1f}s" if est_rem > 0 else "Finishing...",
                                        delta=f"Elapsed: {elapsed:.1f}s" if elapsed > 0 else f"~{rate:.2f}s/req"
                                    )
                                    col3.metric(
                                        label="Document Chunks",
                                        value=f"{chunks} chunks",
                                        delta=f"{chunk_size} chunks/req"
                                    )
                                    st.caption(
                                        "ℹ️ **Note:** *Completion time is an estimate based on tested Nomic Embed Text v1.5 API latency (~1.07s/request baseline at ~0.93 req/s). "
                                        "Network delays, document length, server load, retries, and concurrent users can affect actual duration.*"
                                    )

                        elif ev_type == "completed":
                            indexing_successful = True
                            completed_chunks = event.get("chunks_indexed", 0)
                            st.session_state.uploaded_hash = current_hash
                            with progress_container.container():
                                st.progress(1.0)
                                st.success(
                                    f"✅ **Indexing complete!** Successfully generated embeddings and indexed {completed_chunks} chunks "
                                    f"({total_requests_cnt or completed_requests_cnt} requests) using Nomic Embed Text v1.5."
                                )
                                st.toast(f"Indexed {len(uploaded_files)} paper(s) ({completed_chunks} chunks)", icon="📄")

                        elif ev_type == "error":
                            err_msg = event.get("error", "Unknown ingestion error")
                            with progress_container.container():
                                st.error(f"❌ **Embedding Error:** {err_msg}")
                            break

                except Exception as ingest_err:
                    with progress_container.container():
                        st.error(f"❌ **Unable to process uploaded PDFs:** {ingest_err}")

        render_document_management_card(uploaded_files, is_indexed=True)

st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)

# Conversation Turns Render
current_messages = active_session.get("messages", [])

if not current_messages:
    render_welcome_screen()
else:
    render_chat_history(current_messages, pdf_bytes_map=st.session_state.get("pdf_bytes_map"))

# Chat Input Bar
query_to_run = st.chat_input("Ask a research question or verify an academic claim...")

if query_to_run:
    if not is_backend_online:
        st.error("Cannot send query: FastAPI backend is offline. Please start it with: `uvicorn api:app --reload --port 8000`")
    else:
        # Update session title if default
        if active_session.get("title") == "New Research Chat":
            clean_title = query_to_run.strip()
            if len(clean_title) > 32:
                clean_title = clean_title[:32] + "..."
            active_session["title"] = clean_title

        # Append user turn to history & render
        active_session["messages"].append({"role": "user", "content": query_to_run})
        save_user_sessions_to_backend(st.session_state.username, st.session_state.sessions)
        render_message_turn(role="user", content=query_to_run)

        # Stream assistant response live from FastAPI SSE stream
        with st.chat_message("assistant"):
            meta = {
                "sources": None,
                "claim_analysis": None,
                "groundedness": None,
                "answer": ""
            }

            status_placeholder = st.empty()
            with status_placeholder.container():
                st.markdown("🔍 *Analyzing query and planning research retrieval...*")

            def stream_tokens():
                for event in stream_chat(
                    query_to_run,
                    session_id=active_session_id,
                    username=st.session_state.username
                ):
                    ev_type = event.get("type")
                    if ev_type == "status":
                        node = event.get("node")
                        if node == "router":
                            with status_placeholder.container():
                                st.markdown("🧭 *Routing query: evaluating claim and paper context...*")
                        elif node in ("agent_node", "new_query_to_agent"):
                            with status_placeholder.container():
                                st.markdown("🤖 *Planning retrieval strategy...*")
                        elif node in ("execute_tools", "retrieve"):
                            with status_placeholder.container():
                                st.markdown("📚 *Searching indexed paper passages & literature...*")
                        elif node in ("relevancy_check", "grade_documents"):
                            with status_placeholder.container():
                                st.markdown("🔍 *Evaluating retrieved paper passages for relevance...*")
                        elif node == "query_rewrite":
                            with status_placeholder.container():
                                st.markdown("🔄 *Reformulating query with academic nomenclature...*")
                        elif node in ("claim_verification", "claim_web_search", "claim_analysis"):
                            with status_placeholder.container():
                                st.markdown("⚖️ *Verifying factual claim against scientific literature...*")
                        elif node == "generate_answer":
                            with status_placeholder.container():
                                st.markdown("✍️ *Synthesizing verified response with academic citations...*")
                        elif node == "format_answer":
                            with status_placeholder.container():
                                st.markdown("✨ *Compiling citations and evidence badges...*")
                    elif ev_type == "token":
                        status_placeholder.empty()
                        yield event.get("content", "")
                    elif ev_type == "final":
                        status_placeholder.empty()
                        meta["sources"] = event.get("sources")
                        meta["claim_analysis"] = event.get("claim_analysis")
                        metadata_dict = event.get("metadata", {})
                        meta["groundedness"] = event.get("groundedness") or metadata_dict.get("groundedness")
                        meta["answer"] = event.get("answer", "")
                    elif ev_type == "error":
                        status_placeholder.empty()
                        st.error(f"Backend Streaming Error: {event.get('error')}")

            response_placeholder = st.empty()
            try:
                full_response = response_placeholder.write_stream(stream_tokens())
                if not full_response and meta.get("answer"):
                    full_response = meta["answer"]
                
                # Re-render with full LaTeX normalization and markdown styling
                if full_response:
                    response_placeholder.empty()
                    with response_placeholder.container():
                        render_formatted_markdown(full_response)
            except Exception as stream_err:
                st.error(f"Stream error: {stream_err}")
                full_response = ""

            # Render claim verification verdict if present
            if meta.get("claim_analysis"):
                render_verdict_badge(meta["claim_analysis"])

            # Render Self-RAG Groundedness badge if present
            if meta.get("groundedness"):
                render_grounding_badge(meta["groundedness"])

            # Render source citations with quote highlights and interactive page previews
            if meta.get("sources"):
                render_sources_section(meta["sources"], pdf_bytes_map=st.session_state.get("pdf_bytes_map"))

            # Persist assistant turn to active session messages & Upstash Redis
            if full_response:
                active_session["messages"].append({
                    "role": "assistant",
                    "content": full_response,
                    "sources": meta.get("sources"),
                    "claim_analysis": meta.get("claim_analysis"),
                    "groundedness": meta.get("groundedness")
                })
                save_user_sessions_to_backend(st.session_state.username, st.session_state.sessions)


