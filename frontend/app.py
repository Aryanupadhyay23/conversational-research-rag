import streamlit as st
import os
import sys
import datetime

# Ensure project root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from frontend.api_client import (
    check_backend_health,
    upload_documents,
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
if "username" not in st.session_state:
    st.session_state.username = "default_user"

if "sessions" not in st.session_state:
    loaded = fetch_user_sessions(st.session_state.username)
    if loaded:
        st.session_state.sessions = loaded
        st.session_state.current_session_id = list(loaded.keys())[0]
    else:
        init_id = f"session_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        st.session_state.sessions = {
            init_id: {
                "title": "New Research Chat",
                "messages": [],
                "created_at": datetime.datetime.now().strftime("%b %d, %H:%M")
            }
        }
        st.session_state.current_session_id = init_id
        save_user_sessions_to_backend(st.session_state.username, st.session_state.sessions)

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

# Check FastAPI Backend Connectivity
is_backend_online, backend_msg = check_backend_health()
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
                with st.spinner("Uploading to FastAPI backend & indexing (Layout & Table Extraction)..."):
                    try:
                        resp = upload_documents(uploaded_files)
                        chunks_indexed = resp.get("chunks_indexed", 0)
                        st.session_state.uploaded_hash = current_hash
                        st.toast(f"Successfully indexed {len(uploaded_files)} paper(s) ({chunks_indexed} chunks) via backend.", icon="📄")
                    except Exception as ingest_err:
                        st.error(f"Unable to process uploaded PDFs via backend: {ingest_err}")

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

            def stream_tokens():
                for event in stream_chat(
                    query_to_run,
                    session_id=active_session_id,
                    username=st.session_state.username
                ):
                    ev_type = event.get("type")
                    if ev_type == "token":
                        yield event.get("content", "")
                    elif ev_type == "final":
                        meta["sources"] = event.get("sources")
                        meta["claim_analysis"] = event.get("claim_analysis")
                        metadata_dict = event.get("metadata", {})
                        meta["groundedness"] = metadata_dict.get("groundedness")
                        meta["answer"] = event.get("answer", "")
                    elif ev_type == "error":
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

