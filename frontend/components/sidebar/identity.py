import datetime
import uuid
import streamlit as st
from frontend.api_client import (
    fetch_user_sessions,
    save_user_sessions_to_backend,
)

def render_user_identity_section() -> str:
    """
    Render user profile & identity selector.
    Supports:
      1. Isolated Guest: unique per-visitor session with fresh conversation on arrival.
      2. Custom Username: saves & loads all past conversations for that user from Upstash Redis.
    """
    if "username" not in st.session_state:
        st.session_state.username = f"guest_{uuid.uuid4().hex[:6]}"

    current_user = st.session_state.username
    is_guest = current_user.startswith("guest_") or current_user == "default_user"

    st.sidebar.markdown(
        """
        <div style="display:flex; align-items:center; gap:8px; margin-bottom: 8px;">
            <span style="font-size: 18px;">👤</span>
            <span style="font-size: 14px; font-weight: 600; color: #ffffff;">User Profile & Memory</span>
        </div>
        """,
        unsafe_allow_html=True
    )

    badge_class = "user-badge user-badge-default" if is_guest else "user-badge user-badge-custom"
    user_label = "Guest User" if is_guest else f"User: {current_user}"

    st.sidebar.markdown(
        f"""
        <div class="user-profile-card">
            <div class="user-profile-header">
                <span class="{badge_class}">● {user_label}</span>
            </div>
            <div style="font-size: 11px; color: #71717a; margin-top: 4px;">
                {'Guest mode (fresh conversation). Enter a username below to save & sync your personal chats across devices.' if is_guest else 'Private profile active. Conversations are synced to Upstash Redis.'}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    with st.sidebar.expander("⚙ Switch / Set User Profile", expanded=False):
        new_user_input = st.text_input(
            "Enter Username",
            value="" if is_guest else current_user,
            placeholder="e.g. Aryan, John, ResearchLab...",
            key="username_switch_input"
        )

        col_btn1, col_btn2 = st.columns([1, 1])
        with col_btn1:
            if st.button("Set User", use_container_width=True, key="btn_apply_user"):
                clean = new_user_input.strip().lower() if new_user_input else f"guest_{uuid.uuid4().hex[:6]}"
                if clean != current_user:
                    st.session_state.username = clean
                    loaded_sessions = fetch_user_sessions(clean)
                    init_id = f"session_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}"
                    fresh_session = {
                        "title": "New Research Chat",
                        "messages": [],
                        "created_at": datetime.datetime.now().strftime("%b %d, %H:%M")
                    }
                    if loaded_sessions:
                        st.session_state.sessions = loaded_sessions
                        st.session_state.sessions[init_id] = fresh_session
                        st.session_state.current_session_id = init_id
                    else:
                        st.session_state.sessions = {init_id: fresh_session}
                        st.session_state.current_session_id = init_id
                        save_user_sessions_to_backend(clean, st.session_state.sessions)
                    st.rerun()

        with col_btn2:
            if st.button("New Guest", use_container_width=True, key="btn_reset_default"):
                new_guest = f"guest_{uuid.uuid4().hex[:6]}"
                st.session_state.username = new_guest
                init_id = f"session_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}"
                st.session_state.sessions = {
                    init_id: {
                        "title": "New Research Chat",
                        "messages": [],
                        "created_at": datetime.datetime.now().strftime("%b %d, %H:%M")
                    }
                }
                st.session_state.current_session_id = init_id
                st.rerun()

    return st.session_state.username

