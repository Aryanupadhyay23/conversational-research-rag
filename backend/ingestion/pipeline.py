import asyncio
from typing import Callable, Optional, Sequence, Tuple

from langchain_core.retrievers import BaseRetriever

from backend.config import EMBEDDING_MODEL_NAME
from backend.database.documents import COMPLETED, PROCESSING, calculate_document_hash, get_document_registry
from backend.ingestion.loader import load_pdf_from_bytes
from backend.ingestion.retriever import (build_hybrid_retriever, configured_collection_name,
    index_document_chunks, indexing_signature, load_document_chunks, verify_document_points)
from backend.ingestion.splitter import split_documents

def _file_bytes(uploaded_file) -> bytes:
    return uploaded_file.getvalue() if hasattr(uploaded_file, "getvalue") else uploaded_file.read()

def ingest_documents(uploaded_files: Sequence, progress_callback: Optional[Callable[[dict], None]] = None) -> Tuple[BaseRetriever, int]:
    """Index only missing/incompatible PDFs and reconstruct a session retriever."""
    registry = get_document_registry()
    collection_name, signature = configured_collection_name(), indexing_signature()
    all_chunks, document_hashes = [], []
    for uploaded_file in uploaded_files:
        content = _file_bytes(uploaded_file)
        filename = getattr(uploaded_file, "name", "document.pdf")
        document_hash = calculate_document_hash(content)
        record, claimed = registry.claim(document_hash, filename, EMBEDDING_MODEL_NAME, collection_name, signature)
        if not claimed and record["status"] == PROCESSING:
            raise RuntimeError(f"Document '{filename}' is already being indexed; please retry shortly.")
        usable = (not claimed and record["status"] == COMPLETED and
                  verify_document_points(document_hash, record.get("chunk_count"), collection_name))
        if usable:
            chunks = load_document_chunks(document_hash, collection_name)
        else:
            if not claimed:
                record, claimed = registry.claim(document_hash, filename, EMBEDDING_MODEL_NAME, collection_name, signature, force=True)
            try:
                pages = load_pdf_from_bytes(content, filename)
                if not pages:
                    raise ValueError("Could not extract any text from uploaded PDF.")
                for page in pages:
                    page.metadata.update({"document_hash": document_hash, "document_id": record["document_id"], "source_name": filename})
                chunks = split_documents(pages)
                if not chunks:
                    raise ValueError("Could not create text splits from uploaded PDF.")
                registry.set_chunk_count(document_hash, len(chunks))
                index_document_chunks(chunks, document_hash, record["document_id"], collection_name, progress_callback)
                if not verify_document_points(document_hash, len(chunks), collection_name):
                    raise RuntimeError("Qdrant did not confirm all indexed document chunks.")
                registry.complete(document_hash)
            except Exception as exc:
                registry.fail(document_hash, exc)
                raise
        if not chunks:
            raise RuntimeError("Persistent index contained no chunks for this document.")
        all_chunks.extend(chunks)
        document_hashes.append(document_hash)
    return build_hybrid_retriever(all_chunks, document_hashes, collection_name), len(all_chunks)

async def ingest_documents_async(uploaded_files: Sequence, progress_callback: Optional[Callable[[dict], None]] = None) -> Tuple[BaseRetriever, int]:
    return await asyncio.to_thread(ingest_documents, uploaded_files, progress_callback)
