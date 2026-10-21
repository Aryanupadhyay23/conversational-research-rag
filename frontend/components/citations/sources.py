import html
from typing import List, Dict, Any, Optional
import streamlit as st
from frontend.api_client import render_pdf_page_image

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
            raw_title = src.get("title", "Referenced Research Source")
            source_name = src.get("source_name") or raw_title
            url = str(src.get("url", "")).strip()
            page_num = src.get("page_number")
            page_idx = src.get("page")
            snippet = src.get("snippet", "")

            title = html.escape(str(raw_title))
            clean_snippet = html.escape(str(snippet))
            safe_url = url if url.startswith(("http://", "https://")) else ""

            # Title & Page Badge Header
            page_badge_html = f"<span class='page-badge'>📄 Page {page_num}</span>" if page_num else ""
            if safe_url:
                escaped_url = html.escape(safe_url)
                header_html = f"<div style='margin-bottom: 4px;'><strong><a href='{escaped_url}' target='_blank' rel='noopener noreferrer' style='color: #ffffff; text-decoration: underline;'>{idx+1}. {title}</a></strong> {page_badge_html}</div>"
            else:
                header_html = f"<div style='margin-bottom: 4px;'><strong style='color: #f4f4f5;'>{idx+1}. {title}</strong> {page_badge_html}</div>"
            st.markdown(header_html, unsafe_allow_html=True)

            # Highlighted Quote Block
            if clean_snippet:
                st.markdown(
                    f"""<div class="quote-highlight">"{clean_snippet}"</div>""",
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

            st.markdown("<hr style='border: none; border-top: 1px solid rgba(255, 255, 255, 0.08); margin: 8px 0;'>", unsafe_allow_html=True)
