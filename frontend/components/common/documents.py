import streamlit as st

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
