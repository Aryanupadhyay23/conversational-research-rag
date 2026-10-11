def get_dark_blue_black_theme_css() -> str:
    """Return polished custom CSS styling for dark blue black aesthetic."""
    return """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    /* Global Typography and Base Styling */
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    /* Main Container Background */
    .stApp {
        background: radial-gradient(circle at 50% 0%, #0d172e 0%, #080c14 65%, #05080f 100%) !important;
        color: #f8fafc !important;
    }

    /* Header & Top Bar */
    header[data-testid="stHeader"] {
        background: rgba(8, 12, 20, 0.85) !important;
        backdrop-filter: blur(12px) !important;
        border-bottom: 1px solid rgba(59, 130, 246, 0.15) !important;
    }

    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background: #090e1a !important;
        border-right: 1px solid rgba(59, 130, 246, 0.18) !important;
    }

    section[data-testid="stSidebar"] .stMarkdown h1,
    section[data-testid="stSidebar"] .stMarkdown h2,
    section[data-testid="stSidebar"] .stMarkdown h3 {
        color: #e2e8f0 !important;
        font-weight: 600 !important;
        letter-spacing: -0.02em !important;
    }

    /* Custom Scrollbar */
    ::-webkit-scrollbar {
        width: 6px;
        height: 6px;
    }
    ::-webkit-scrollbar-track {
        background: #080c14;
    }
    ::-webkit-scrollbar-thumb {
        background: #1e293b;
        border-radius: 4px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: #3b82f6;
    }

    /* Hero Banner */
    .hero-banner {
        background: linear-gradient(135deg, rgba(13, 23, 46, 0.9) 0%, rgba(18, 32, 64, 0.8) 100%);
        border: 1px solid rgba(59, 130, 246, 0.25);
        border-radius: 16px;
        padding: 24px 28px;
        margin-bottom: 24px;
        box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.5), 0 0 20px -5px rgba(59, 130, 246, 0.15);
    }
    .hero-title {
        font-size: 26px;
        font-weight: 700;
        background: linear-gradient(135deg, #ffffff 0%, #93c5fd 60%, #3b82f6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 6px;
        letter-spacing: -0.03em;
    }
    .hero-subtitle {
        color: #94a3b8;
        font-size: 14px;
        line-height: 1.5;
        font-weight: 400;
        margin: 0;
    }

    /* Session List Item */
    .session-card {
        background: rgba(15, 23, 42, 0.65);
        border: 1px solid rgba(59, 130, 246, 0.12);
        border-radius: 10px;
        padding: 10px 14px;
        margin-bottom: 8px;
        cursor: pointer;
        transition: all 0.2s ease;
    }
    .session-card:hover {
        background: rgba(30, 58, 138, 0.25);
        border-color: rgba(59, 130, 246, 0.4);
        transform: translateX(2px);
    }
    .session-card-active {
        background: linear-gradient(90deg, rgba(37, 99, 235, 0.25) 0%, rgba(15, 23, 42, 0.9) 100%) !important;
        border-left: 3px solid #3b82f6 !important;
        border-color: rgba(59, 130, 246, 0.5) !important;
    }
    .session-card-title {
        color: #f1f5f9;
        font-size: 13px;
        font-weight: 500;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .session-card-date {
        color: #64748b;
        font-size: 11px;
        margin-top: 2px;
    }

    /* Document Capsule Badge */
    .doc-pill {
        display: inline-flex;
        align-items: center;
        background: rgba(30, 58, 138, 0.35);
        border: 1px solid rgba(59, 130, 246, 0.3);
        border-radius: 20px;
        padding: 4px 12px;
        margin: 4px 4px 4px 0;
        font-size: 12px;
        color: #93c5fd;
    }
    .doc-pill-ready {
        background: rgba(16, 185, 129, 0.15);
        border-color: rgba(16, 185, 129, 0.35);
        color: #6ee7b7;
    }

    /* Welcome / Empty Screen */
    .welcome-container {
        text-align: center;
        padding: 40px 20px;
        margin: 20px 0;
        background: rgba(13, 21, 39, 0.4);
        border: 1px dashed rgba(59, 130, 246, 0.2);
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
        color: #e2e8f0;
        margin-bottom: 8px;
    }
    .welcome-desc {
        font-size: 13px;
        color: #94a3b8;
        max-width: 480px;
        margin: 0 auto 20px auto;
        line-height: 1.6;
    }

    /* Chat Messages */
    div[data-testid="stChatMessage"] {
        background: rgba(13, 21, 39, 0.75) !important;
        border: 1px solid rgba(59, 130, 246, 0.15) !important;
        border-radius: 14px !important;
        padding: 16px 20px !important;
        margin-bottom: 14px !important;
        box-shadow: 0 4px 20px -5px rgba(0, 0, 0, 0.3) !important;
    }

    /* Distinct Chat User vs Assistant */
    div[data-testid="stChatMessage"][data-role="user"] {
        background: rgba(26, 41, 74, 0.5) !important;
        border: 1px solid rgba(59, 130, 246, 0.25) !important;
    }

    /* Chat Input Bar */
    div[data-testid="stChatInput"] {
        border-radius: 14px !important;
        border: 1px solid rgba(59, 130, 246, 0.3) !important;
        background: #0a101f !important;
        box-shadow: 0 0 25px -5px rgba(37, 99, 235, 0.2) !important;
    }
    div[data-testid="stChatInput"]:focus-within {
        border-color: #3b82f6 !important;
        box-shadow: 0 0 25px -2px rgba(59, 130, 246, 0.4) !important;
    }

    /* Buttons */
    .stButton>button {
        background: linear-gradient(135deg, #1e3a8a 0%, #2563eb 100%) !important;
        color: #ffffff !important;
        border: 1px solid rgba(96, 165, 250, 0.4) !important;
        border-radius: 8px !important;
        font-weight: 500 !important;
        font-size: 13px !important;
        transition: all 0.2s ease !important;
        box-shadow: 0 2px 8px -2px rgba(37, 99, 235, 0.3) !important;
    }
    .stButton>button:hover {
        background: linear-gradient(135deg, #2563eb 0%, #3b82f6 100%) !important;
        border-color: #93c5fd !important;
        box-shadow: 0 4px 14px 0 rgba(37, 99, 235, 0.5) !important;
        transform: translateY(-1px) !important;
    }

    /* Secondary / Ghost Buttons */
    .stButton>button[kind="secondary"] {
        background: rgba(15, 23, 42, 0.8) !important;
        border: 1px solid rgba(59, 130, 246, 0.2) !important;
        color: #cbd5e1 !important;
    }
    .stButton>button[kind="secondary"]:hover {
        background: rgba(30, 58, 138, 0.4) !important;
        border-color: #3b82f6 !important;
        color: #ffffff !important;
    }

    /* Expanders */
    div[data-testid="stExpander"] {
        background: rgba(10, 16, 31, 0.6) !important;
        border: 1px solid rgba(59, 130, 246, 0.15) !important;
        border-radius: 10px !important;
    }
    div[data-testid="stExpander"] summary {
        color: #cbd5e1 !important;
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
        background: rgba(16, 185, 129, 0.15);
        border: 1px solid rgba(16, 185, 129, 0.4);
        color: #34d399;
    }
    .verdict-refuted {
        background: rgba(239, 68, 68, 0.15);
        border: 1px solid rgba(239, 68, 68, 0.4);
        color: #f87171;
    }
    .verdict-inconclusive {
        background: rgba(245, 158, 11, 0.15);
        border: 1px solid rgba(245, 158, 11, 0.4);
        color: #fbbf24;
    }

    /* Source Citation Cards */
    .citation-card {
        background: rgba(15, 23, 42, 0.8);
        border: 1px solid rgba(59, 130, 246, 0.15);
        border-radius: 8px;
        padding: 10px 14px;
        margin-top: 8px;
    }
    .citation-title {
        color: #93c5fd;
        font-size: 13px;
        font-weight: 600;
        text-decoration: none;
    }
    .citation-title:hover {
        color: #bfdbfe;
        text-decoration: underline;
    }
    .citation-snippet {
        color: #94a3b8;
        font-size: 12px;
        margin-top: 4px;
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
        background: rgba(16, 185, 129, 0.12);
        border: 1px solid rgba(16, 185, 129, 0.35);
        color: #34d399;
    }
    .grounding-badge-low {
        background: rgba(245, 158, 11, 0.12);
        border: 1px solid rgba(245, 158, 11, 0.35);
        color: #fbbf24;
    }

    /* Quote Highlight Block & Page Badges */
    .quote-highlight {
        background: rgba(30, 41, 59, 0.5);
        border-left: 3px solid #3b82f6;
        padding: 8px 12px;
        border-radius: 4px;
        margin: 6px 0;
        font-size: 13px;
        color: #cbd5e1;
        font-style: italic;
    }
    .page-badge {
        display: inline-block;
        background: rgba(59, 130, 246, 0.2);
        color: #93c5fd;
        border-radius: 4px;
        padding: 2px 6px;
        font-size: 11px;
        font-weight: 600;
        margin-left: 6px;
    }
    </style>
    """
