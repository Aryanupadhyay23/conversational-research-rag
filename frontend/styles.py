def get_black_major_theme_css() -> str:
    """Return polished custom CSS styling for high-contrast obsidian black major aesthetic."""
    return """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    /* Global Typography and Base Styling */
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    /* Main Container Background - Pure Obsidian Black */
    .stApp {
        background: radial-gradient(circle at 50% 0%, #121212 0%, #080808 45%, #000000 100%) !important;
        color: #f4f4f5 !important;
    }

    /* Header & Top Bar */
    header[data-testid="stHeader"] {
        background: rgba(5, 5, 5, 0.9) !important;
        backdrop-filter: blur(14px) !important;
        border-bottom: 1px solid rgba(255, 255, 255, 0.08) !important;
    }

    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background: #080808 !important;
        border-right: 1px solid rgba(255, 255, 255, 0.09) !important;
    }

    section[data-testid="stSidebar"] .stMarkdown h1,
    section[data-testid="stSidebar"] .stMarkdown h2,
    section[data-testid="stSidebar"] .stMarkdown h3 {
        color: #ffffff !important;
        font-weight: 600 !important;
        letter-spacing: -0.02em !important;
    }

    /* Custom Scrollbar */
    ::-webkit-scrollbar {
        width: 6px;
        height: 6px;
    }
    ::-webkit-scrollbar-track {
        background: #000000;
    }
    ::-webkit-scrollbar-thumb {
        background: #27272a;
        border-radius: 4px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: #52525b;
    }

    /* Hero Banner */
    .hero-banner {
        background: linear-gradient(135deg, rgba(20, 20, 20, 0.95) 0%, rgba(10, 10, 10, 0.98) 100%);
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 16px;
        padding: 24px 28px;
        margin-bottom: 24px;
        box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.9), 0 0 20px -5px rgba(255, 255, 255, 0.04);
    }
    .hero-title {
        font-size: 26px;
        font-weight: 700;
        background: linear-gradient(135deg, #ffffff 0%, #e4e4e7 60%, #a1a1aa 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 6px;
        letter-spacing: -0.03em;
    }
    .hero-subtitle {
        color: #a1a1aa;
        font-size: 14px;
        line-height: 1.5;
        font-weight: 400;
        margin: 0;
    }

    /* User Profile & Identity Box in Sidebar */
    .user-profile-card {
        background: rgba(18, 18, 18, 0.85);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 12px 14px;
        margin-bottom: 14px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
    }
    .user-profile-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 6px;
    }
    .user-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        font-size: 12px;
        font-weight: 600;
        color: #ffffff;
        background: #18181b;
        border: 1px solid rgba(255, 255, 255, 0.15);
        border-radius: 20px;
        padding: 3px 10px;
    }
    .user-badge-default {
        color: #a1a1aa;
        border-color: rgba(255, 255, 255, 0.08);
    }
    .user-badge-custom {
        color: #67e8f9;
        border-color: rgba(103, 232, 249, 0.35);
        background: rgba(6, 182, 212, 0.08);
    }

    /* Session List Item */
    .session-card {
        background: rgba(18, 18, 18, 0.7);
        border: 1px solid rgba(255, 255, 255, 0.07);
        border-radius: 10px;
        padding: 10px 14px;
        margin-bottom: 8px;
        cursor: pointer;
        transition: all 0.2s ease;
    }
    .session-card:hover {
        background: rgba(32, 32, 32, 0.85);
        border-color: rgba(255, 255, 255, 0.22);
        transform: translateX(2px);
    }
    .session-card-active {
        background: linear-gradient(90deg, rgba(38, 38, 38, 0.95) 0%, rgba(18, 18, 18, 0.9) 100%) !important;
        border-left: 3px solid #ffffff !important;
        border-color: rgba(255, 255, 255, 0.35) !important;
    }
    .session-card-title {
        color: #ffffff;
        font-size: 13px;
        font-weight: 500;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .session-card-date {
        color: #71717a;
        font-size: 11px;
        margin-top: 2px;
    }

    /* Document Capsule Badge */
    .doc-pill {
        display: inline-flex;
        align-items: center;
        background: rgba(24, 24, 27, 0.85);
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 20px;
        padding: 4px 12px;
        margin: 4px 4px 4px 0;
        font-size: 12px;
        color: #e4e4e7;
    }
    .doc-pill-ready {
        background: rgba(16, 185, 129, 0.12);
        border-color: rgba(16, 185, 129, 0.35);
        color: #6ee7b7;
    }

    /* Welcome / Empty Screen */
    .welcome-container {
        text-align: center;
        padding: 40px 20px;
        margin: 20px 0;
        background: rgba(14, 14, 14, 0.6);
        border: 1px dashed rgba(255, 255, 255, 0.15);
        border-radius: 16px;
    }
    .welcome-icon {
        font-size: 38px;
        margin-bottom: 12px;
        display: inline-block;
    }
    .welcome-heading {
        font-size: 18px;
        font-weight: 600;
        color: #ffffff;
        margin-bottom: 8px;
    }
    .welcome-desc {
        font-size: 13px;
        color: #a1a1aa;
        max-width: 480px;
        margin: 0 auto 20px auto;
        line-height: 1.6;
    }

    /* Chat Messages - Deep Obsidian Cards */
    div[data-testid="stChatMessage"] {
        background: rgba(12, 12, 12, 0.88) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 14px !important;
        padding: 16px 20px !important;
        margin-bottom: 14px !important;
        box-shadow: 0 4px 20px -5px rgba(0, 0, 0, 0.7) !important;
        color: #f4f4f5 !important;
    }

    /* Distinct Chat User vs Assistant */
    div[data-testid="stChatMessage"][data-role="user"] {
        background: rgba(24, 24, 27, 0.8) !important;
        border: 1px solid rgba(255, 255, 255, 0.18) !important;
    }

    /* Chat Input Bar - Obsidian Black */
    div[data-testid="stChatInput"] {
        border-radius: 14px !important;
        border: 1px solid rgba(255, 255, 255, 0.18) !important;
        background: #0a0a0a !important;
        box-shadow: 0 0 25px -5px rgba(0, 0, 0, 0.9) !important;
    }
    div[data-testid="stChatInput"]:focus-within {
        border-color: #ffffff !important;
        box-shadow: 0 0 20px -2px rgba(255, 255, 255, 0.25) !important;
    }

    /* Buttons - Sleek Monochrome / Obsidian */
    .stButton>button {
        background: linear-gradient(135deg, #27272a 0%, #18181b 100%) !important;
        color: #ffffff !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
        border-radius: 8px !important;
        font-weight: 500 !important;
        font-size: 13px !important;
        transition: all 0.2s ease !important;
        box-shadow: 0 2px 8px -2px rgba(0, 0, 0, 0.5) !important;
    }
    .stButton>button:hover {
        background: linear-gradient(135deg, #3f3f46 0%, #27272a 100%) !important;
        border-color: rgba(255, 255, 255, 0.45) !important;
        box-shadow: 0 4px 14px 0 rgba(255, 255, 255, 0.1) !important;
        transform: translateY(-1px) !important;
    }

    /* Secondary / Ghost Buttons */
    .stButton>button[kind="secondary"] {
        background: rgba(18, 18, 18, 0.9) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        color: #d4d4d4 !important;
    }
    .stButton>button[kind="secondary"]:hover {
        background: rgba(32, 32, 32, 0.9) !important;
        border-color: rgba(255, 255, 255, 0.3) !important;
        color: #ffffff !important;
    }

    /* TextInput / Inputs */
    div[data-testid="stTextInput"] input {
        background: #101010 !important;
        border: 1px solid rgba(255, 255, 255, 0.15) !important;
        color: #ffffff !important;
        border-radius: 8px !important;
    }
    div[data-testid="stTextInput"] input:focus {
        border-color: #ffffff !important;
        box-shadow: 0 0 10px rgba(255, 255, 255, 0.2) !important;
    }

    /* Expanders */
    div[data-testid="stExpander"] {
        background: rgba(14, 14, 14, 0.8) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 10px !important;
    }
    div[data-testid="stExpander"] summary {
        color: #e4e4e7 !important;
        font-weight: 500 !important;
    }

    /* Verdict Badge Cards */
    .verdict-badge {
        display: inline-flex;
        align-items: center;
        border-radius: 8px;
        padding: 6px 14px;
        font-size: 13px;
        font-weight: 600;
        margin-bottom: 12px;
    }
    .verdict-supported {
        background: rgba(16, 185, 129, 0.12);
        border: 1px solid rgba(16, 185, 129, 0.4);
        color: #34d399;
    }
    .verdict-refuted {
        background: rgba(239, 68, 68, 0.12);
        border: 1px solid rgba(239, 68, 68, 0.4);
        color: #f87171;
    }
    .verdict-inconclusive {
        background: rgba(245, 158, 11, 0.12);
        border: 1px solid rgba(245, 158, 11, 0.4);
        color: #fbbf24;
    }

    /* Source Citation Cards */
    .citation-card {
        background: rgba(15, 15, 15, 0.85);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 8px;
        padding: 10px 14px;
        margin-top: 8px;
    }
    .citation-title {
        color: #f4f4f5;
        font-size: 13px;
        font-weight: 600;
        text-decoration: none;
    }
    .citation-title:hover {
        color: #ffffff;
        text-decoration: underline;
    }
    .citation-snippet {
        color: #a1a1aa;
        font-size: 12px;
        margin-top: 4px;
    }

    /* Grounding & Faithfulness Badges */
    .grounding-badge {
        display: inline-flex;
        align-items: center;
        border-radius: 6px;
        padding: 4px 10px;
        font-size: 12px;
        font-weight: 500;
        margin-bottom: 8px;
        margin-right: 8px;
    }
    .grounding-badge-grounded {
        background: rgba(16, 185, 129, 0.1);
        border: 1px solid rgba(16, 185, 129, 0.3);
        color: #34d399;
    }
    .grounding-badge-low {
        background: rgba(245, 158, 11, 0.1);
        border: 1px solid rgba(245, 158, 11, 0.3);
        color: #fbbf24;
    }

    /* Quote Highlight Block & Page Badges */
    .quote-highlight {
        background: rgba(24, 24, 27, 0.7);
        border-left: 3px solid #ffffff;
        padding: 8px 12px;
        border-radius: 4px;
        margin: 6px 0;
        font-size: 13px;
        color: #e4e4e7;
        font-style: italic;
    }
    .page-badge {
        display: inline-block;
        background: rgba(255, 255, 255, 0.12);
        color: #f4f4f5;
        border-radius: 4px;
        padding: 2px 6px;
        font-size: 11px;
        font-weight: 600;
        margin-left: 6px;
    }

    /* Markdown Tables - Dark Obsidian Styling */
    .stMarkdown table {
        border-collapse: collapse !important;
        width: 100% !important;
        margin: 16px 0 !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        border-radius: 8px !important;
        overflow: hidden !important;
        font-size: 13.5px !important;
    }
    .stMarkdown th {
        background: #18181b !important;
        color: #ffffff !important;
        padding: 10px 14px !important;
        text-align: left !important;
        font-weight: 600 !important;
        border-bottom: 2px solid rgba(255, 255, 255, 0.18) !important;
    }
    .stMarkdown td {
        padding: 9px 14px !important;
        border-bottom: 1px solid rgba(255, 255, 255, 0.07) !important;
        color: #e4e4e7 !important;
    }
    .stMarkdown tr:nth-child(even) {
        background: rgba(255, 255, 255, 0.02) !important;
    }
    .stMarkdown tr:hover {
        background: rgba(255, 255, 255, 0.04) !important;
    }

    /* KaTeX LaTeX Mathematical Equations Styling */
    .katex {
        color: #ffffff !important;
        font-size: 1.05em !important;
    }
    .katex-display {
        background: rgba(18, 18, 18, 0.75) !important;
        border: 1px solid rgba(255, 255, 255, 0.09) !important;
        border-radius: 8px !important;
        padding: 14px 18px !important;
        margin: 14px 0 !important;
        overflow-x: auto !important;
        overflow-y: hidden !important;
        color: #ffffff !important;
    }
    .katex-display::-webkit-scrollbar {
        height: 4px;
    }
    .katex-display::-webkit-scrollbar-thumb {
        background: #3f3f46;
        border-radius: 2px;
    }

    /* Markdown Code Blocks & Inline Code */
    .stMarkdown pre {
        background: #0c0c0e !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        border-radius: 8px !important;
        padding: 12px 16px !important;
    }
    .stMarkdown code {
        color: #f4f4f5 !important;
        background: rgba(255, 255, 255, 0.08) !important;
        padding: 2px 6px !important;
        border-radius: 4px !important;
        font-size: 0.9em !important;
    }
    .stMarkdown pre code {
        background: transparent !important;
        padding: 0 !important;
    }

    /* Markdown Blockquotes */
    .stMarkdown blockquote {
        border-left: 3px solid #71717a !important;
        background: rgba(24, 24, 27, 0.4) !important;
        padding: 8px 16px !important;
        margin: 12px 0 !important;
        border-radius: 0 8px 8px 0 !important;
        color: #d4d4d4 !important;
        font-style: italic !important;
    }
    </style>
    """


