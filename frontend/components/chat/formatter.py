import re
import streamlit as st


def _strip_html_tags(text: str) -> str:
    """
    Strip dangerous executable HTML elements and raw HTML markup from text.
    Preserves text contents of non-script tags while eliminating tags and malicious scripts.
    """
    if not text:
        return ""
    # 1. Completely remove script, style, iframe, object, embed tags and their contents
    text = re.sub(r"<(script|style|iframe|object|embed)[\s\S]*?</\1>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<(script|style|iframe|object|embed)[^>]*/>", "", text, flags=re.IGNORECASE)
    # 2. Strip remaining opening, closing, and self-closing HTML tags
    text = re.sub(r"</?[a-zA-Z][a-zA-Z0-9:-]*(?:\s+[^<>]*)*/?>", "", text)
    return text


def normalize_markdown_and_latex(text: str) -> str:
    """
    Standardize Markdown and LaTeX mathematical notations for rendering in Streamlit (KaTeX)
    while safely stripping raw HTML tags outside of code blocks and math environments.

    Handles:
    - Normalizing LaTeX display delimiters: \\[ ... \\] -> $$ ... $$
    - Normalizing LaTeX inline delimiters: \\( ... \\) -> $ ... $
    - Wrapping standalone LaTeX environments (align, equation, matrix, cases, etc.) in $$ ... $$
    - Cleaning internal whitespace in inline math (e.g. '$ \\mu = 0 $' -> '$\\mu = 0$')
    - Protecting code blocks (``` and `) from delimiter replacement and tag stripping
    - Protecting display ($$...$$) and inline ($...$) math from HTML stripping
    - Stripping dangerous script/style tags and raw HTML outside code/math blocks
    - Protecting escaped dollar signs (\\$50)
    - Formatting Markdown tables with appropriate spacing
    """
    if not text or not isinstance(text, str):
        return ""

    # Normalize line endings
    text = text.replace("\r\n", "\n")

    # 1. Protect code blocks (fenced ```...``` and inline `...`)
    fenced_blocks = []
    def save_fenced(match):
        fenced_blocks.append(match.group(0))
        return f"@@FENCED_CODE_{len(fenced_blocks)-1}@@"

    inline_blocks = []
    def save_inline(match):
        inline_blocks.append(match.group(0))
        return f"@@INLINE_CODE_{len(inline_blocks)-1}@@"

    text = re.sub(r"```[\s\S]*?```", save_fenced, text)
    text = re.sub(r"`[^`\n]+?`", save_inline, text)

    # 2. Protect escaped dollars
    text = text.replace(r"\$", "@@ESCAPED_DOLLAR@@")

    # 3. Standard LaTeX display math: \[ ... \] -> $$ ... $$
    text = re.sub(r"\\\[\s*([\s\S]*?)\s*\\\]", r"\n\n$$\n\1\n$$\n\n", text)

    # 4. Standard LaTeX inline math: \( ... \) -> $...$
    text = re.sub(r"\\\(\s*([\s\S]*?)\s*\\\)", r"$\1$", text)

    # 5. Standalone LaTeX environments (align, equation, matrix, cases, etc.)
    math_envs = [
        r"equation", r"equation\*", r"align", r"align\*", r"alignat", r"alignat\*",
        r"gather", r"gather\*", r"multline", r"multline\*",
        r"matrix", r"pmatrix", r"bmatrix", r"Bmatrix", r"vmatrix", r"Vmatrix", r"cases"
    ]
    env_pattern = "|".join(math_envs)

    # Protect existing $$ display blocks
    display_blocks = []
    def save_display_math(match):
        display_blocks.append(match.group(0))
        return f"@@DISPLAY_MATH_{len(display_blocks)-1}@@"

    text = re.sub(r"\$\$[\s\S]*?\$\$", save_display_math, text)

    # Wrap un-enclosed \begin{env}...\end{env}
    def wrap_env(match):
        full_match = match.group(0).strip()
        return f"\n\n$$\n{full_match}\n$$\n\n"

    text = re.sub(rf"(\\begin\{{(?:{env_pattern})\}}[\s\S]*?\\end\{{(?:{env_pattern})\}})", wrap_env, text)

    # Protect newly wrapped display math blocks
    text = re.sub(r"\$\$[\s\S]*?\$\$", save_display_math, text)

    # 6. Fix and protect inline math with leading/trailing spaces: '$ \mu = 0 $' -> '$\mu = 0$'
    def clean_inline_math(match):
        inner = match.group(1).strip()
        return f"${inner}$"

    text = re.sub(r"(?<!\$)\$(?!\$)\s+([^$\n]+?[\\_\^=\+\-\*\/\<\>][^$\n]*?)\s+\$(?!\$)", clean_inline_math, text)
    text = re.sub(r"(?<!\$)\$(?!\$)\s+([^$\n]+?[\\_\^=\+\-\*\/\<\>][^$\n]*?)\$(?!\$)", clean_inline_math, text)
    text = re.sub(r"(?<!\$)\$(?!\$)([^$\n]+?[\\_\^=\+\-\*\/\<\>][^$\n]*?)\s+\$(?!\$)", clean_inline_math, text)

    inline_math_blocks = []
    def save_inline_math(match):
        inline_math_blocks.append(match.group(0))
        return f"@@INLINE_MATH_{len(inline_math_blocks)-1}@@"

    text = re.sub(r"(?<!\$)\$(?!\$)[^$\n]+?(?<!\$)\$(?!\$)", save_inline_math, text)

    # 7. Strip raw HTML tags on text outside of code fences and math blocks
    text = _strip_html_tags(text)

    # 8. Ensure markdown tables have empty line before them
    lines = text.split("\n")
    new_lines = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            if i > 0 and new_lines and new_lines[-1].strip() and not (new_lines[-1].strip().startswith("|") and new_lines[-1].strip().endswith("|")):
                new_lines.append("")
        new_lines.append(line)
    text = "\n".join(new_lines)

    # 9. Clean up excess newlines
    text = re.sub(r"\n{3,}", "\n\n", text)

    # 10. Restore math, code blocks, and escaped dollars in reverse order
    for idx, block in enumerate(inline_math_blocks):
        text = text.replace(f"@@INLINE_MATH_{idx}@@", block)

    for idx, block in enumerate(display_blocks):
        content = block[2:-2].strip()
        formatted = f"\n\n$$\n{content}\n$$\n\n"
        text = text.replace(f"@@DISPLAY_MATH_{idx}@@", formatted)

    for idx, block in enumerate(inline_blocks):
        text = text.replace(f"@@INLINE_CODE_{idx}@@", block)

    for idx, block in enumerate(fenced_blocks):
        text = text.replace(f"@@FENCED_CODE_{idx}@@", block)

    text = text.replace("@@ESCAPED_DOLLAR@@", r"\$")

    return text.strip()


def render_formatted_markdown(content: str):
    """Render markdown with normalized LaTeX math and table formatting safely without raw HTML injection."""
    normalized = normalize_markdown_and_latex(content)
    st.markdown(normalized, unsafe_allow_html=False)
