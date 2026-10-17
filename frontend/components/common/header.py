from frontend.styles import get_black_major_theme_css
import streamlit as st

def inject_custom_theme():
    """Inject polished obsidian black major theme CSS into the Streamlit app."""
    st.markdown(get_black_major_theme_css(), unsafe_allow_html=True)

def render_header():
    """Render the project header banner with obsidian black aesthetic."""
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
