from typing import List, Dict, Any, Optional
import streamlit as st
from frontend.components.citations.badges import render_verdict_badge, render_grounding_badge
from frontend.components.citations.sources import render_sources_section
from frontend.components.chat.formatter import render_formatted_markdown

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

        render_formatted_markdown(content)

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
