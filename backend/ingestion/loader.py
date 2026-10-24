import io
import logging
from typing import List, Any
from langchain_core.documents import Document

logger = logging.getLogger(__name__)

def _format_table_to_markdown(table: List[List[Any]]) -> str:
    """Convert extracted 2D table grid into a clean Markdown table."""
    if not table:
        return ""
    cleaned_rows = []
    for row in table:
        cleaned = [str(cell or "").replace("\n", " ").strip() for cell in row]
        if any(cleaned):
            cleaned_rows.append(cleaned)
    if not cleaned_rows:
        return ""

    col_count = max(len(r) for r in cleaned_rows)
    header = cleaned_rows[0] + [""] * (col_count - len(cleaned_rows[0]))
    separator = ["---"] * col_count
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(separator) + " |"
    ]
    for row in cleaned_rows[1:]:
        padded = row + [""] * (col_count - len(row))
        lines.append("| " + " | ".join(padded) + " |")
    return "\n".join(lines)

def load_pdf_from_bytes(file_bytes: bytes, filename: str) -> List[Document]:
    """
    Parse PDF from in-memory byte buffer using layout-aware pdfplumber with table extraction.
    Falls back gracefully to PyMuPDF and pypdf if specialized parsers encounter errors.
    """
    if not file_bytes:
        return []

    # 1. Primary Strategy: PyMuPDF (fitz) - high-speed C++ parsing with native table extraction
    try:
        import pymupdf
        docs = []
        doc = pymupdf.open(stream=file_bytes, filetype="pdf")
        for page_idx, page in enumerate(doc):
            page_text = page.get_text() or ""
            tables_md = []
            try:
                tabs = page.find_tables()
                if tabs and tabs.tables:
                    for t in tabs:
                        md = t.to_markdown()
                        if md and md.strip():
                            tables_md.append(md.strip())
            except Exception as tbl_err:
                logger.debug(f"PyMuPDF table extraction on page {page_idx}: {tbl_err}")

            content_parts = []
            if page_text.strip():
                content_parts.append(page_text.strip())
            if tables_md:
                content_parts.append("### Extracted Tables:\n" + "\n\n".join(tables_md))

            full_content = "\n\n".join(content_parts).strip()
            if full_content:
                docs.append(Document(
                    page_content=full_content,
                    metadata={
                        "source_name": filename,
                        "page": page_idx,
                        "has_tables": len(tables_md) > 0
                    }
                ))
        if docs:
            logger.info(f"Loaded {len(docs)} pages from '{filename}' with high-speed PyMuPDF.")
            return docs
    except Exception as e:
        logger.warning(f"PyMuPDF failed for '{filename}', falling back to pdfplumber: {e}")

    # 2. Secondary Strategy: pdfplumber fallback
    try:
        import pdfplumber
        docs = []
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page_idx, page in enumerate(pdf.pages):
                page_text = page.extract_text(layout=False) or ""
                tables_md = []
                try:
                    tables = page.extract_tables() or []
                    for t in tables:
                        md = _format_table_to_markdown(t)
                        if md:
                            tables_md.append(md)
                except Exception as tbl_err:
                    logger.debug(f"Table extraction error on page {page_idx}: {tbl_err}")

                content_parts = []
                if page_text.strip():
                    content_parts.append(page_text.strip())
                if tables_md:
                    content_parts.append("### Extracted Tables:\n" + "\n\n".join(tables_md))

                full_content = "\n\n".join(content_parts).strip()
                if full_content:
                    docs.append(Document(
                        page_content=full_content,
                        metadata={
                            "source_name": filename,
                            "page": page_idx,
                            "has_tables": len(tables_md) > 0
                        }
                    ))
        if docs:
            logger.info(f"Loaded {len(docs)} pages from '{filename}' with pdfplumber fallback.")
            return docs
    except Exception as e:
        logger.warning(f"pdfplumber failed for '{filename}', trying pypdf fallback: {e}")

    # 3. Final Fallback: pypdf
    try:
        import pypdf
        docs = []
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        for page_idx, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            if text.strip():
                docs.append(Document(
                    page_content=text.strip(),
                    metadata={
                        "source_name": filename,
                        "page": page_idx,
                        "has_tables": False
                    }
                ))
        return docs
    except Exception as e:
        logger.error(f"All PDF extractors failed for '{filename}': {e}")
        return []
