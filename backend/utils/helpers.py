import asyncio
import concurrent.futures
import logging
from typing import List, Dict, Any, Coroutine, TypeVar
from langchain_core.documents import Document
from langchain_core.prompts import PromptTemplate, format_document

logger = logging.getLogger(__name__)

T = TypeVar("T")
DOC_TEMPLATE = PromptTemplate.from_template("[{title}]\n{page_content}")

def format_docs_to_context(docs: List[Document]) -> str:
    """Format Document objects into readable context blocks for LLM prompts."""
    formatted = []
    for d in docs:
        meta = d.metadata or {}
        title = meta.get("title") or meta.get("source_name") or meta.get("source") or "Document"
        d_copy = Document(page_content=d.page_content, metadata={"title": title})
        formatted.append(format_document(d_copy, DOC_TEMPLATE))
    return "\n\n---\n\n".join(formatted)

def extract_sources_metadata(docs: List[Document]) -> List[Dict[str, Any]]:
    """
    Extract citation metadata with document titles, page numbers, and snippet excerpts
    for client verification.
    """
    sources = []
    seen = set()
    for d in docs:
        meta = d.metadata or {}
        title = meta.get("title") or meta.get("source_name") or meta.get("source", "Document")
        source_name = meta.get("source_name") or meta.get("source", "")
        page_idx = meta.get("page")
        page_number = meta.get("page_number")
        if page_number is None and page_idx is not None:
            page_number = int(page_idx) + 1

        clean_text = d.page_content.strip()
        if clean_text.startswith("[Document:"):
            parts = clean_text.split("]\n", 1)
            if len(parts) > 1:
                clean_text = parts[1].strip()

        snippet = clean_text[:280].replace("\n", " ").strip()
        if len(clean_text) > 280:
            snippet += "..."

        dedup_key = (source_name or title, page_number, snippet[:60])
        if dedup_key not in seen:
            seen.add(dedup_key)
            sources.append({
                "title": title,
                "source_name": source_name or title,
                "page": page_idx,
                "page_number": page_number,
                "url": meta.get("url") or meta.get("link", ""),
                "source_type": meta.get("doc_type", meta.get("source", "doc")),
                "snippet": snippet,
                "full_text": clean_text[:800]
            })
    return sources

def run_async_safe(coro: Coroutine[Any, Any, T]) -> T:
    """Safely execute async coroutine in synchronous contexts."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(lambda: asyncio.run(coro)).result()
    return asyncio.run(coro)
