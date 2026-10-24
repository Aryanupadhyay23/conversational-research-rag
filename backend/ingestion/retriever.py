"""Persistent Qdrant dense retrieval plus in-memory BM25 for an active session."""
import hashlib
import logging
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, List, Optional, Sequence

from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

from backend.config import (BASELINE_EMBEDDING_LATENCY, CHUNK_OVERLAP, CHUNK_SIZE,
    EMBEDDING_CHUNK_SIZE, EMBEDDING_DIMENSION, EMBEDDING_MAX_WORKERS,
    EMBEDDING_MODEL_NAME, INDEXING_CONFIG_VERSION, QDRANT_API_KEY,
    QDRANT_COLLECTION_NAME, QDRANT_LOCAL_PATH, QDRANT_TIMEOUT, QDRANT_URL,
    RETRIEVER_K, get_embeddings)

logger = logging.getLogger(__name__)
_qdrant_client = None

def indexing_signature() -> str:
    raw = f"{INDEXING_CONFIG_VERSION}|{EMBEDDING_MODEL_NAME}|{EMBEDDING_DIMENSION}|{CHUNK_SIZE}|{CHUNK_OVERLAP}"
    return hashlib.sha256(raw.encode()).hexdigest()

def configured_collection_name() -> str:
    return f"{QDRANT_COLLECTION_NAME}__{indexing_signature()[:12]}"

def get_qdrant_client():
    """Return one process-local client, preferring Qdrant Cloud when configured."""
    global _qdrant_client
    if _qdrant_client is not None:
        return _qdrant_client
    from qdrant_client import QdrantClient
    if QDRANT_URL:
        client_kwargs = {"url": QDRANT_URL, "timeout": QDRANT_TIMEOUT}
        if QDRANT_API_KEY:
            client_kwargs["api_key"] = QDRANT_API_KEY
        _qdrant_client = QdrantClient(**client_kwargs)
        logger.info("Connected to Qdrant Cloud at %s", QDRANT_URL)
    else:
        os.makedirs(QDRANT_LOCAL_PATH, exist_ok=True)
        _qdrant_client = QdrantClient(path=QDRANT_LOCAL_PATH)
        logger.info("Using embedded Qdrant at %s", QDRANT_LOCAL_PATH)
    return _qdrant_client

def ensure_collection(client, collection_name: str) -> None:
    from qdrant_client.models import Distance, VectorParams
    if not client.collection_exists(collection_name):
        client.create_collection(collection_name=collection_name,
            vectors_config=VectorParams(size=EMBEDDING_DIMENSION, distance=Distance.COSINE))

def _point_id(document_hash: str, chunk_index: int) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"qdrant-pdf:{document_hash}:{chunk_index}"))

def _emit_progress(callback, completed: int, total: int, total_chunks: int, started: float):
    if not callback:
        return
    elapsed = time.time() - started
    rate = elapsed / completed if completed else BASELINE_EMBEDDING_LATENCY
    callback({"stage": "embedding", "message": f"Generating embeddings... {completed} of {total} requests",
        "completed_requests": completed, "total_requests": total, "total_chunks": total_chunks,
        "chunk_size": max(1, EMBEDDING_CHUNK_SIZE), "elapsed_seconds": round(elapsed, 1),
        "estimated_remaining_seconds": round((total - completed) * rate, 1),
        "rate_seconds_per_req": round(rate, 2), "percent": round(completed / total * 100, 1),
        "disclaimer": "Estimate based on measured embedding request time."})

def index_document_chunks(splits: List[Document], document_hash: str, document_id: str,
                          collection_name: str, progress_callback: Optional[Callable[[dict], None]] = None) -> None:
    """Embed chunks then idempotently upsert their deterministic Qdrant points."""
    if not splits:
        raise ValueError("Cannot index an empty document.")
    from qdrant_client.models import PointStruct
    client = get_qdrant_client()
    ensure_collection(client, collection_name)
    embeddings = get_embeddings()
    batch_size = max(1, EMBEDDING_CHUNK_SIZE)
    batches = [splits[i:i + batch_size] for i in range(0, len(splits), batch_size)]
    total = len(batches)
    if progress_callback:
        progress_callback({"stage": "started", "message": "Generating embeddings...", "completed_requests": 0,
            "total_requests": total, "total_chunks": len(splits), "chunk_size": batch_size,
            "elapsed_seconds": 0.0, "estimated_remaining_seconds": round(total * BASELINE_EMBEDDING_LATENCY, 1),
            "rate_seconds_per_req": BASELINE_EMBEDDING_LATENCY, "percent": 0.0})
    def embed_batch(pair):
        position, docs = pair
        texts = [d.page_content for d in docs]
        vectors = embeddings.embed_documents([t if t.startswith("search_document: ") else f"search_document: {t}" for t in texts])
        return position, docs, vectors
    results = [None] * total
    started = time.time()
    with ThreadPoolExecutor(max_workers=min(max(1, EMBEDDING_MAX_WORKERS), total)) as executor:
        futures = [executor.submit(embed_batch, item) for item in enumerate(batches)]
        for completed, future in enumerate(as_completed(futures), 1):
            position, docs, vectors = future.result()
            results[position] = (docs, vectors)
            _emit_progress(progress_callback, completed, total, len(splits), started)
    points = []
    for docs, vectors in results:
        for document, vector in zip(docs, vectors):
            metadata = dict(document.metadata)
            chunk_index = int(metadata["chunk_index"])
            metadata.update({"document_hash": document_hash, "document_id": document_id, "chunk_index": chunk_index})
            points.append(PointStruct(id=_point_id(document_hash, chunk_index), vector=vector,
                payload={"page_content": document.page_content, "metadata": metadata}))
    client.upsert(collection_name=collection_name, points=points, wait=True)

def verify_document_points(document_hash: str, chunk_count: Optional[int], collection_name: str) -> bool:
    if chunk_count is None or chunk_count < 1:
        return False
    client = get_qdrant_client()
    if not client.collection_exists(collection_name):
        return False
    ids = [_point_id(document_hash, i) for i in range(chunk_count)]
    return len(client.retrieve(collection_name=collection_name, ids=ids, with_payload=False, with_vectors=False)) == chunk_count

def load_document_chunks(document_hash: str, collection_name: str) -> List[Document]:
    """Read saved chunks to rebuild a session BM25 index without PDF parsing."""
    from qdrant_client.models import FieldCondition, Filter, MatchValue
    client = get_qdrant_client()
    if not client.collection_exists(collection_name):
        return []
    offset, docs = None, []
    query_filter = Filter(must=[FieldCondition(key="metadata.document_hash", match=MatchValue(value=document_hash))])
    while True:
        points, offset = client.scroll(collection_name=collection_name, scroll_filter=query_filter, limit=256,
                                       offset=offset, with_payload=True, with_vectors=False)
        for point in points:
            payload = point.payload or {}
            docs.append(Document(page_content=payload.get("page_content", ""), metadata=payload.get("metadata", {})))
        if offset is None:
            break
    return sorted(docs, key=lambda d: d.metadata.get("chunk_index", 0))

def build_semantic_retriever(document_hashes: Sequence[str], collection_name: str) -> BaseRetriever:
    from langchain_qdrant import QdrantVectorStore
    from qdrant_client.models import FieldCondition, Filter, MatchAny
    client = get_qdrant_client()
    ensure_collection(client, collection_name)
    # The collection is created with our configured dimension above. Skipping
    # LangChain's validation prevents it from embedding a dummy document every
    # time a persisted retriever is rebuilt after an upload or restart.
    vectorstore = QdrantVectorStore(client=client, collection_name=collection_name,
                                    embedding=get_embeddings(), validate_collection_config=False)
    query_filter = Filter(must=[FieldCondition(key="metadata.document_hash", match=MatchAny(any=list(document_hashes)))])
    return vectorstore.as_retriever(search_kwargs={"k": RETRIEVER_K, "filter": query_filter})

def build_bm25_retriever(splits: List[Document]) -> BaseRetriever:
    from langchain_community.retrievers.bm25 import BM25Retriever
    bm25 = BM25Retriever.from_documents(splits)
    bm25.k = RETRIEVER_K
    return bm25

def build_hybrid_retriever(splits: List[Document], document_hashes: Sequence[str], collection_name: str) -> BaseRetriever:
    """Construct the existing RRF hybrid retriever over persistent Qdrant points."""
    from langchain_classic.retrievers.ensemble import EnsembleRetriever
    if not splits:
        raise ValueError("Cannot build a retriever from empty document list.")
    return EnsembleRetriever(retrievers=[build_bm25_retriever(splits), build_semantic_retriever(document_hashes, collection_name)],
                             weights=[0.5, 0.5])
