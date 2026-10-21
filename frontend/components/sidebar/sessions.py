import datetime
import uuid
import streamlit as st
from frontend.api_client import (
    save_user_sessions_to_backend,
    delete_session_from_backend,
    clear_user_history_on_backend,
)
from frontend.components.sidebar.identity import render_user_identity_section

def render_session_sidebar(service=None) -> str:
    """
    Render conversation history sidebar with user identity & Upstash Redis persistence.
    Returns active session_id.
    """
    # 1. Render User Identity Section at top
    username = render_user_identity_section()

    st.sidebar.markdown(
        """
        <div style="margin-top: 14px; margin-bottom: 8px;">
            <span style="font-size: 14px; font-weight: 600; color: #ffffff;">Conversation History</span>
        </div>
        """,
        unsafe_allow_html=True
    )

    # 2. New Chat Button
    if st.sidebar.button("＋ New Research Chat", use_container_width=True, key="btn_new_chat"):
        new_id = f"session_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        st.session_state.sessions[new_id] = {
            "title": "New Research Chat",
            "messages": [],
            "created_at": datetime.datetime.now().strftime("%b %d, %H:%M")
        }
        st.session_state.current_session_id = new_id
        save_user_sessions_to_backend(username, st.session_state.sessions)
        st.rerun()

    st.sidebar.markdown("<hr style='border: none; border-top: 1px solid rgba(255, 255, 255, 0.08); margin: 10px 0;'>", unsafe_allow_html=True)

    # 3. List of Previous Conversations for Active User
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
                key=f"btn_{username}_{s_id}",
                use_container_width=True,
                help=f"{msg_count} messages | Created {s_data.get('created_at', '')} | User: {username}"
            ):
                st.session_state.current_session_id = s_id
                st.rerun()

        with col2:
            if st.button("✕", key=f"del_{username}_{s_id}", help="Delete this conversation"):
                del st.session_state.sessions[s_id]
                delete_session_from_backend(username, s_id)
                if st.session_state.current_session_id == s_id:
                    remaining = list(st.session_state.sessions.keys())
                    if remaining:
                        st.session_state.current_session_id = remaining[-1]
                    else:
                        init_id = f"session_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
                        st.session_state.sessions[init_id] = {
                            "title": "New Research Chat",
                            "messages": [],
                            "created_at": datetime.datetime.now().strftime("%b %d, %H:%M")
                        }
                        st.session_state.current_session_id = init_id
                        save_user_sessions_to_backend(username, st.session_state.sessions)
                st.rerun()

    st.sidebar.markdown("<hr style='border: none; border-top: 1px solid rgba(255, 255, 255, 0.08); margin: 12px 0;'>", unsafe_allow_html=True)

    # 4. Export Conversation & Clear History
    active_session_data = st.session_state.sessions.get(st.session_state.current_session_id, {})
    current_messages = active_session_data.get("messages", [])
    if current_messages:
        transcript_lines = [
            f"# Research Paper RAG Project - Chat Transcript",
            f"**User:** {username} | **Session:** {st.session_state.current_session_id}\n"
        ]
        for msg in current_messages:
            sender = "User" if msg["role"] == "user" else "Research Assistant"
            transcript_lines.append(f"### {sender}:\n{msg['content']}\n")
        transcript_text = "\n".join(transcript_lines)

        st.sidebar.download_button(
            label="📥 Export Chat (Markdown)",
            data=transcript_text,
            file_name=f"research_chat_{username}_{st.session_state.current_session_id}.md",
            mime="text/markdown",
            use_container_width=True
        )

    if st.sidebar.button("🗑 Clear All User Chats", use_container_width=True, key=f"btn_clear_all_{username}"):
        clear_user_history_on_backend(username)
        init_id = f"session_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        st.session_state.sessions = {
            init_id: {
                "title": "New Research Chat",
                "messages": [],
                "created_at": datetime.datetime.now().strftime("%b %d, %H:%M")
            }
        }
        st.session_state.current_session_id = init_id
        save_user_sessions_to_backend(username, st.session_state.sessions)
        st.rerun()

    return st.session_state.current_session_id
