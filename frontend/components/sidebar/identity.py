import datetime
import uuid
import re
import streamlit as st
from frontend.api_client import (
    fetch_user_sessions,
    save_user_sessions_to_backend,
)

def render_user_identity_section() -> str:
    """
    Render user profile & identity selector.
    Users can simply type a username to load and store their chats easily,
    or use Guest Mode for a fresh isolated session without saving.
    """
    if "username" not in st.session_state:
        st.session_state.username = f"guest_{uuid.uuid4().hex[:6]}"

    current_user = st.session_state.username
    is_guest = current_user.startswith("guest_") or current_user == "default_user"

    st.sidebar.markdown(
        """
        <div style="display:flex; align-items:center; gap:8px; margin-bottom: 8px;">
            <span style="font-size: 18px;">👤</span>
            <span style="font-size: 14px; font-weight: 600; color: #ffffff;">User Profile</span>
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
                {'Guest mode active (temporary chat). Enter your username below to load or persist your chats.' if is_guest else 'Chats are saved and synced under your username in Upstash Redis.'}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    with st.sidebar.expander("⚙ Switch Username", expanded=False):
        new_user_input = st.text_input(
            "Enter Username",
            value="" if is_guest else current_user,
            placeholder="e.g. aryan, lab_team...",
            key="username_switch_input"
        )

        col_btn1, col_btn2 = st.columns([1.1, 0.9])
        with col_btn1:
            if st.button("Load Chats", use_container_width=True, key="btn_apply_user"):
                raw_user = new_user_input.strip()
                if not raw_user:
                    # Switch to a guest profile
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
                else:
                    # Clean username
                    clean = re.sub(r"\s+", "_", raw_user.lower())
                    clean = "".join(c for c in clean if c.isalnum() or c in ("_", "-", "."))
                    if not clean:
                        clean = "default_user"

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
                        st.session_state.current_session_id = list(loaded_sessions.keys())[-1]
                    else:
                        st.session_state.sessions = {init_id: fresh_session}
                        st.session_state.current_session_id = init_id
                        save_user_sessions_to_backend(clean, st.session_state.sessions)

                    st.sidebar.success(f"Loaded chats for '{clean}'!")
                    st.rerun()

        with col_btn2:
            if st.button("Guest Mode", use_container_width=True, key="btn_reset_default"):
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
