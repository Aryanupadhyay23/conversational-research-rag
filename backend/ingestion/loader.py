import io
import logging
from typing import List, Sequence, Any
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

    # 1. Primary Strategy: pdfplumber for layout & markdown table extraction
    try:
        import pdfplumber
        docs = []
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page_idx, page in enumerate(pdf.pages):
                page_text = page.extract_text(layout=False) or ""
                
                # Extract and format tables into Markdown
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
            logger.info(f"Loaded {len(docs)} pages from '{filename}' with pdfplumber.")
            return docs
    except Exception as e:
        logger.warning(f"pdfplumber failed for '{filename}', trying PyMuPDF fallback: {e}")

    # 2. Secondary Strategy: PyMuPDF (fitz)
    try:
        import pymupdf
        docs = []
        doc = pymupdf.open(stream=file_bytes, filetype="pdf")
        for page_idx, page in enumerate(doc):
            text = page.get_text() or ""
            if text.strip():
                docs.append(Document(
                    page_content=text.strip(),
                    metadata={
                        "source_name": filename,
                        "page": page_idx,
                        "has_tables": False
                    }
                ))
        if docs:
            logger.info(f"Loaded {len(docs)} pages from '{filename}' with PyMuPDF.")
            return docs
    except Exception as e:
        logger.warning(f"PyMuPDF failed for '{filename}', trying pypdf fallback: {e}")

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

def load_uploaded_pdfs(uploaded_files: Sequence) -> List[Document]:
    """Extract text and tables from uploaded PDF file objects."""
    all_docs = []
    for f in uploaded_files:
        try:
            data = f.getvalue() if hasattr(f, "getvalue") else f.read()
            name = getattr(f, "name", "document.pdf")
            all_docs.extend(load_pdf_from_bytes(data, name))
        except Exception as e:
            logger.error(f"Error reading file {getattr(f, 'name', 'unknown')}: {e}")
    return all_docs
