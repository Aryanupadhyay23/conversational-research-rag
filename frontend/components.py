from typing import List, Dict, Any, Optional
import streamlit as st
import datetime
from frontend.styles import get_dark_blue_black_theme_css
from frontend.api_client import render_pdf_page_image, clear_session_memory

def inject_custom_theme():
    """Inject polished dark blue black theme CSS into the Streamlit app."""
    st.markdown(get_dark_blue_black_theme_css(), unsafe_allow_html=True)

def render_header():
    """Render the project header banner."""
    st.markdown(
        """
        <div class="hero-banner">
            <div class="hero-title">Research Paper RAG Project</div>
            <p class="hero-subtitle">
                Intelligent Conversational Research Assistant with Document Analysis & Evidence Verification
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

def render_session_sidebar(service) -> str:
    """
    Render conversation history sidebar with multi-session management.
    Returns active session_id.
    """
    st.sidebar.markdown("### Conversation History")

    # New Chat Button
    if st.sidebar.button("＋ New Research Chat", use_container_width=True):
        new_id = f"session_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        st.session_state.sessions[new_id] = {
            "title": "New Research Chat",
            "messages": [],
            "created_at": datetime.datetime.now().strftime("%b %d, %H:%M")
        }
        st.session_state.current_session_id = new_id
        st.rerun()

    st.sidebar.markdown("---")

    # List of Previous Conversations
    sessions_keys = list(st.session_state.sessions.keys())

    for s_id in reversed(sessions_keys):
        s_data = st.session_state.sessions[s_id]
        title = s_data.get("title", "Research Chat")
        msg_count = len(s_data.get("messages", []))
        is_active = (s_id == st.session_state.current_session_id)

        col1, col2 = st.sidebar.columns([0.82, 0.18])
        with col1:
            button_label = f"💬 {title}" if not is_active else f"▶ {title}"
            if st.button(
                button_label,
                key=f"btn_{s_id}",
                use_container_width=True,
                help=f"{msg_count} messages | Created {s_data.get('created_at', '')}"
            ):
                st.session_state.current_session_id = s_id
                st.rerun()

        with col2:
            if st.button("✕", key=f"del_{s_id}", help="Delete this conversation"):
                del st.session_state.sessions[s_id]
                if st.session_state.current_session_id == s_id:
                    remaining = list(st.session_state.sessions.keys())
                    if remaining:
                        st.session_state.current_session_id = remaining[-1]
                    else:
                        init_id = f"session_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
                        st.session_state.sessions[init_id] = {
                            "title": "New Research Chat",
                            "messages": [],
                            "created_at": datetime.datetime.now().strftime("%b %d, %H:%M")
                        }
                        st.session_state.current_session_id = init_id
                st.rerun()

    st.sidebar.markdown("---")

    # Options: Export Conversation & Clear History
    current_messages = st.session_state.sessions[st.session_state.current_session_id].get("messages", [])
    if current_messages:
        # Build markdown transcript
        transcript_lines = ["# Research Paper RAG Project - Chat Transcript\n"]
        for msg in current_messages:
            sender = "User" if msg["role"] == "user" else "Research Assistant"
            transcript_lines.append(f"### {sender}:\n{msg['content']}\n")
        transcript_text = "\n".join(transcript_lines)

        st.sidebar.download_button(
            label="📥 Export Chat (Markdown)",
            data=transcript_text,
            file_name=f"research_chat_{st.session_state.current_session_id}.md",
            mime="text/markdown",
            use_container_width=True
        )

    if st.sidebar.button("🗑 Clear All Conversations", use_container_width=True):
        init_id = f"session_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        st.session_state.sessions = {
            init_id: {
                "title": "New Research Chat",
                "messages": [],
                "created_at": datetime.datetime.now().strftime("%b %d, %H:%M")
            }
        }
        st.session_state.current_session_id = init_id
        try:
            clear_session_memory(init_id)
        except Exception:
            pass
        st.rerun()

    return st.session_state.current_session_id

def render_document_management_card(uploaded_files, is_indexed: bool):
    """Render a clean card displaying uploaded documents without technical vector jargon."""
    if not uploaded_files:
        return

    st.markdown("#### Uploaded Research Papers")
    pills_html = []
    for f in uploaded_files:
        size_kb = len(f.getvalue()) / 1024
        size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.2f} MB"
        pills_html.append(
            f'<span class="doc-pill doc-pill-ready">📄 {f.name} ({size_str}) • Ready</span>'
        )
    st.markdown("".join(pills_html), unsafe_allow_html=True)

def render_welcome_screen():
    """Render modern welcome state when conversation has no messages."""
    st.markdown(
        """
        <div class="welcome-container">
            <div class="welcome-icon">📑</div>
            <div class="welcome-heading">Welcome to Research Paper RAG</div>
            <div class="welcome-desc">
                Upload one or multiple research papers above, or ask any academic question below.
                The assistant will synthesize literature findings and verify claims against scientific evidence.
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

def render_verdict_badge(claim_analysis: Optional[Dict[str, Any]]):
    """Render a clean verification verdict badge for claims."""
    if not claim_analysis:
        return

    verdict = claim_analysis.get("verdict", "UNVERIFIED")
    confidence = claim_analysis.get("confidence", 0.8)

    if verdict == "SUPPORTED":
        badge_class = "verdict-supported"
        verdict_label = "Verified Finding"
    elif verdict == "REFUTED":
        badge_class = "verdict-refuted"
        verdict_label = "Contradicted by Literature"
    else:
        badge_class = "verdict-inconclusive"
        verdict_label = "Inconclusive Evidence"

    st.markdown(
        f"""
        <div class="verdict-badge {badge_class}">
            <span>{verdict_label}</span>
            <span style="opacity: 0.8; margin-left: 8px; font-weight: 400;">({confidence:.0%} confidence)</span>
        </div>
        """,
        unsafe_allow_html=True
    )

    superseding = claim_analysis.get("superseding_papers", [])
    if superseding:
        with st.expander("Referenced Counter-Evidence & Literature", expanded=False):
            for p in superseding:
                title = p.get("title", "Research Paper")
                link = p.get("arxiv_id_or_url")
                finding = p.get("finding", "")
                if link:
                    st.markdown(f"- **[{title}]({link})**\n  _{finding}_")
                else:
                    st.markdown(f"- **{title}**\n  _{finding}_")

def render_grounding_badge(groundedness: Optional[Dict[str, Any]]):
    """Render Self-RAG groundedness/hallucination verification badge."""
    if not groundedness:
        return

    is_grounded = groundedness.get("is_grounded", True)
    confidence = groundedness.get("confidence", "HIGH")
    reason = groundedness.get("reason", "")

    if is_grounded:
        badge_class = "grounding-badge-grounded"
        icon = "🛡️"
        label = "Grounded in Document"
    else:
        badge_class = "grounding-badge-low"
        icon = "⚠️"
        label = "Generalized Synthesis"

    st.markdown(
        f"""
        <div class="grounding-badge {badge_class}" title="{reason}">
            <span>{icon} {label}</span>
            <span style="opacity: 0.8; margin-left: 6px; font-weight: 400;">({confidence} confidence)</span>
        </div>
        """,
        unsafe_allow_html=True
    )

def render_sources_section(
    sources: Optional[List[Dict[str, Any]]],
    pdf_bytes_map: Optional[Dict[str, bytes]] = None
):
    """
    Render referenced papers and citations with exact page badges,
    quote highlighting, and interactive visual PDF page previews.
    """
    if not sources:
        return

    with st.expander(f"📚 Verified Sources & Citations ({len(sources)})", expanded=False):
        for idx, src in enumerate(sources):
            title = src.get("title", "Referenced Research Source")
            source_name = src.get("source_name") or title
            url = src.get("url", "")
            page_num = src.get("page_number")
            page_idx = src.get("page")
            snippet = src.get("snippet", "")

            # Title & Page Badge Header
            page_badge_html = f"<span class='page-badge'>📄 Page {page_num}</span>" if page_num else ""
            if url:
                header_html = f"<div style='margin-bottom: 4px;'><strong><a href='{url}' target='_blank' style='color: #93c5fd; text-decoration: none;'>{idx+1}. {title}</a></strong> {page_badge_html}</div>"
            else:
                header_html = f"<div style='margin-bottom: 4px;'><strong style='color: #e2e8f0;'>{idx+1}. {title}</strong> {page_badge_html}</div>"
            st.markdown(header_html, unsafe_allow_html=True)

            # Highlighted Quote Block
            if snippet:
                st.markdown(
                    f"""<div class="quote-highlight">"{snippet}"</div>""",
                    unsafe_allow_html=True
                )

            # Visual PDF Page Preview if file bytes are cached
            if pdf_bytes_map and page_idx is not None:
                file_bytes = pdf_bytes_map.get(source_name) or pdf_bytes_map.get(title)
                if not file_bytes:
                    for fname, b in pdf_bytes_map.items():
                        if fname.lower() in source_name.lower() or source_name.lower() in fname.lower():
                            file_bytes = b
                            break

                if file_bytes:
                    preview_key = f"preview_toggle_{source_name}_{page_idx}_{idx}"
                    if st.checkbox(f"🔍 Preview Page {page_num} in Document", key=preview_key):
                        img_bytes = render_pdf_page_image(file_bytes, page_idx)
                        if img_bytes:
                            st.image(
                                img_bytes,
                                caption=f"{source_name} — Page {page_num}",
                                use_container_width=True
                            )
                        else:
                            st.caption("Page visual preview unavailable for this page.")

            st.markdown("<hr style='border: none; border-top: 1px solid rgba(59, 130, 246, 0.1); margin: 8px 0;'>", unsafe_allow_html=True)

def render_message_turn(
    role: str,
    content: str,
    sources: Optional[List[Dict[str, Any]]] = None,
    claim_analysis: Optional[Dict[str, Any]] = None,
    groundedness: Optional[Dict[str, Any]] = None,
    pdf_bytes_map: Optional[Dict[str, bytes]] = None
):
    """Render a clean conversation turn with claim verdict, groundedness, and citations."""
    with st.chat_message(role):
        if role == "assistant":
            if claim_analysis:
                render_verdict_badge(claim_analysis)
            if groundedness:
                render_grounding_badge(groundedness)

        st.markdown(content)

        if role == "assistant" and sources:
            render_sources_section(sources, pdf_bytes_map=pdf_bytes_map)

def render_chat_history(
    session_messages: List[Dict[str, Any]],
    pdf_bytes_map: Optional[Dict[str, bytes]] = None
):
    """Render historical chat turns for active session."""
    for msg in session_messages:
        render_message_turn(
            role=msg["role"],
            content=msg["content"],
            sources=msg.get("sources"),
            claim_analysis=msg.get("claim_analysis"),
            groundedness=msg.get("groundedness"),
            pdf_bytes_map=pdf_bytes_map
        )
