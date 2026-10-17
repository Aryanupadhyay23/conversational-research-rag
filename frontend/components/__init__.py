"""
Frontend UI Components Package.
Organized into domain-specific modules:
- common: Header, welcome screen, document management card
- sidebar: User identity and session management
- citations: Badges, evidence verdicts, and visual PDF sources
- chat: Markdown/KaTeX normalization and chat turns
"""

from frontend.components.common.header import inject_custom_theme, render_header
from frontend.components.common.welcome import render_welcome_screen
from frontend.components.common.documents import render_document_management_card

from frontend.components.sidebar.identity import render_user_identity_section
from frontend.components.sidebar.sessions import render_session_sidebar

from frontend.components.citations.badges import render_verdict_badge, render_grounding_badge
from frontend.components.citations.sources import render_sources_section

from frontend.components.chat.formatter import (
    normalize_markdown_and_latex,
    render_formatted_markdown,
)
from frontend.components.chat.messages import (
    render_message_turn,
    render_chat_history,
)

__all__ = [
    # Common
    "inject_custom_theme",
    "render_header",
    "render_welcome_screen",
    "render_document_management_card",
    # Sidebar
    "render_user_identity_section",
    "render_session_sidebar",
    # Citations
    "render_verdict_badge",
    "render_grounding_badge",
    "render_sources_section",
    # Chat
    "normalize_markdown_and_latex",
    "render_formatted_markdown",
    "render_message_turn",
    "render_chat_history",
]
