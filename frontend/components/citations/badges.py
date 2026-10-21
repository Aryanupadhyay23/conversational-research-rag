import html
from typing import Dict, Any, Optional
import streamlit as st

def render_verdict_badge(claim_analysis: Optional[Dict[str, Any]]):
    """Render a clean verification verdict badge for claims."""
    if not claim_analysis:
        return

    verdict = str(claim_analysis.get("verdict", "UNVERIFIED")).upper()
    confidence = float(claim_analysis.get("confidence", 0.8))

    if verdict == "SUPPORTED":
        badge_class = "verdict-supported"
        verdict_label = "Verified Finding"
    elif verdict == "REFUTED":
        badge_class = "verdict-refuted"
        verdict_label = "Contradicted by Literature"
    elif verdict == "PARTIALLY_SUPPORTED":
        badge_class = "verdict-partial"
        verdict_label = "Partially Supported"
    else:
        badge_class = "verdict-inconclusive"
        verdict_label = "Inconclusive / Unverified Evidence"

    escaped_label = html.escape(verdict_label)
    st.markdown(
        f"""
        <div class="verdict-badge {badge_class}">
            <span>{escaped_label}</span>
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
                link = p.get("arxiv_id_or_url", "")
                finding = p.get("finding", "")
                safe_link = link if str(link).startswith(("http://", "https://")) else None
                if safe_link:
                    st.markdown(f"- **[{title}]({safe_link})**\n  _{finding}_")
                else:
                    st.markdown(f"- **{title}**\n  _{finding}_")

def render_grounding_badge(groundedness: Optional[Dict[str, Any]]):
    """Render Self-RAG groundedness/hallucination verification badge."""
    if not groundedness:
        return

    is_grounded = groundedness.get("is_grounded", True)
    confidence = html.escape(str(groundedness.get("confidence", "HIGH")))
    reason = html.escape(str(groundedness.get("reason", "")))

    if is_grounded:
        badge_class = "grounding-badge-grounded"
        icon = "🛡️"
        label = "Grounded in Document"
    else:
        badge_class = "grounding-badge-low"
        icon = "⚠️"
        label = "Generalized Synthesis"

    escaped_label = html.escape(label)
    st.markdown(
        f"""
        <div class="grounding-badge {badge_class}" title="{reason}">
            <span>{icon} {escaped_label}</span>
            <span style="opacity: 0.8; margin-left: 6px; font-weight: 400;">({confidence} confidence)</span>
        </div>
        """,
        unsafe_allow_html=True
    )

