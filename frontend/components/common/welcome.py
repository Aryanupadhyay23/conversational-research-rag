import streamlit as st

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
