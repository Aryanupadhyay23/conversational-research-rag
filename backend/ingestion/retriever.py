import time
import math
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional, Callable
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

from backend.config import (
    RETRIEVER_K,
    get_embeddings,
    EMBEDDING_MAX_WORKERS,
    EMBEDDING_CHUNK_SIZE,
    BASELINE_EMBEDDING_LATENCY,
)

logger = logging.getLogger(__name__)
MAX_EMBEDDING_WORKERS = EMBEDDING_MAX_WORKERS

def build_semantic_retriever(
    splits: List[Document],
    progress_callback: Optional[Callable[[dict], None]] = None
) -> BaseRetriever:
    """
    Build dense Chroma retriever with dynamic real-time progress tracking
    and estimated completion time calculation.
    """
    from langchain_chroma import Chroma
    embeddings = get_embeddings()

    if not splits:
        raise ValueError("Cannot build semantic retriever from empty document list.")

    # Each batch of EMBEDDING_CHUNK_SIZE texts corresponds to exactly 1 embedding API request
    request_batch_size = max(1, EMBEDDING_CHUNK_SIZE)
    total_chunks = len(splits)
    total_requests = math.ceil(total_chunks / request_batch_size)
    batches = [splits[i:i + request_batch_size] for i in range(0, total_chunks, request_batch_size)]

    start_time = time.time()
    initial_est_remaining = round(total_requests * BASELINE_EMBEDDING_LATENCY, 1)

    if progress_callback:
        progress_callback({
            "stage": "started",
            "message": "Generating embeddings...",
            "completed_requests": 0,
            "total_requests": total_requests,
            "total_chunks": total_chunks,
            "chunk_size": request_batch_size,
            "elapsed_seconds": 0.0,
            "estimated_remaining_seconds": initial_est_remaining,
            "rate_seconds_per_req": BASELINE_EMBEDDING_LATENCY,
            "percent": 0.0,
            "disclaimer": "Estimate based on tested Nomic v1.5 API latency (~1.07s/req baseline). Network latency and server load may affect completion time."
        })

    all_texts = []
    all_metas = []
    all_ids = []
    all_vectors = []

    for req_idx, batch_docs in enumerate(batches):
        clean_texts = [doc.page_content for doc in batch_docs]
        metadatas = [doc.metadata for doc in batch_docs]
        ids = [doc.metadata.get("chunk_id") or f"doc_{req_idx}_{i}" for i, doc in enumerate(batch_docs)]
        prefixed_texts = [
            t if t.startswith("search_document: ") else f"search_document: {t}"
            for t in clean_texts
        ]
        try:
            vectors = embeddings.embed_documents(prefixed_texts)
        except Exception as e:
            logger.error(f"Embedding generation failed on batch {req_idx}: {type(e).__name__}")
            raise

        all_texts.extend(clean_texts)
        all_metas.extend(metadatas)
        all_ids.extend(ids)
        all_vectors.extend(vectors)

        completed_requests = req_idx + 1
        elapsed = time.time() - start_time
        actual_rate = elapsed / completed_requests
        remaining_requests = total_requests - completed_requests
        dynamic_est_remaining = round(remaining_requests * actual_rate, 1)
        percent = round((completed_requests / total_requests) * 100, 1)

        if progress_callback:
            progress_callback({
                "stage": "embedding",
                "message": f"Generating embeddings... {completed_requests} of {total_requests} requests",
                "completed_requests": completed_requests,
                "total_requests": total_requests,
                "total_chunks": total_chunks,
                "chunk_size": request_batch_size,
                "elapsed_seconds": round(elapsed, 1),
                "estimated_remaining_seconds": dynamic_est_remaining,
                "rate_seconds_per_req": round(actual_rate, 2),
                "percent": percent,
                "disclaimer": "Estimate based on measured processing rate. Actual completion time may vary with network conditions."
            })

    # Initialize Chroma and directly populate pre-computed batched vectors
    vectorstore = Chroma(embedding_function=embeddings)
    vectorstore._collection.upsert(
        ids=all_ids,
        embeddings=all_vectors,
        documents=all_texts,
        metadatas=all_metas
    )

    return vectorstore.as_retriever(search_kwargs={"k": RETRIEVER_K})

def build_bm25_retriever(splits: List[Document]) -> BaseRetriever:
    """Build sparse BM25 lexical retriever."""
    from langchain_community.retrievers.bm25 import BM25Retriever
    bm25 = BM25Retriever.from_documents(splits)
    bm25.k = RETRIEVER_K
    return bm25

def build_hybrid_retriever(
    splits: List[Document],
    progress_callback: Optional[Callable[[dict], None]] = None
) -> BaseRetriever:
    """Construct hybrid EnsembleRetriever fusing BM25 and Chroma via RRF."""
    from langchain_classic.retrievers.ensemble import EnsembleRetriever  

    dense = build_semantic_retriever(splits, progress_callback=progress_callback)
    sparse = build_bm25_retriever(splits)
    return EnsembleRetriever(retrievers=[sparse, dense], weights=[0.5, 0.5])
