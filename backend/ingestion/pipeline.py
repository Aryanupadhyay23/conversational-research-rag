import asyncio
from typing import Sequence, Tuple
from langchain_core.retrievers import BaseRetriever

from backend.ingestion.loader import load_uploaded_pdfs
from backend.ingestion.splitter import split_documents
from backend.ingestion.retriever import build_hybrid_retriever

def ingest_documents(uploaded_files: Sequence) -> Tuple[BaseRetriever, int]:
    """Ingest PDF documents synchronously and return hybrid retriever and chunk count."""
    raw_docs = load_uploaded_pdfs(uploaded_files)
    if not raw_docs:
        raise ValueError("Could not extract any text from uploaded PDFs.")

    splits = split_documents(raw_docs)
    if not splits:
        raise ValueError("Could not create text splits from uploaded PDFs.")

    retriever = build_hybrid_retriever(splits)
    return retriever, len(splits)

async def ingest_documents_async(uploaded_files: Sequence) -> Tuple[BaseRetriever, int]:
    """Ingest PDF documents asynchronously using non-blocking thread execution."""
    return await asyncio.to_thread(ingest_documents, uploaded_files)
