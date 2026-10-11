import logging
from concurrent.futures import ThreadPoolExecutor
from typing import List
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

from backend.config import RETRIEVER_K, get_embeddings

logger = logging.getLogger(__name__)
EMBEDDING_BATCH_SIZE = 100
MAX_EMBEDDING_WORKERS = 4

def build_semantic_retriever(splits: List[Document]) -> BaseRetriever:
    """Build dense Chroma retriever with concurrent parallel embedding generation."""
    from langchain_chroma import Chroma
    embeddings = get_embeddings()

    if not splits:
        raise ValueError("Cannot build semantic retriever from empty document list.")

    # Partition splits into batches of EMBEDDING_BATCH_SIZE (100)
    batches = [splits[i:i + EMBEDDING_BATCH_SIZE] for i in range(0, len(splits), EMBEDDING_BATCH_SIZE)]

    def _embed_single_batch(batch_tuple):
        batch_idx, batch_docs = batch_tuple
        texts = [doc.page_content for doc in batch_docs]
        metadatas = [doc.metadata for doc in batch_docs]
        ids = [doc.metadata.get("chunk_id") or f"doc_{batch_idx}_{i}" for i, doc in enumerate(batch_docs)]
        vectors = embeddings.embed_documents(texts)
        return texts, metadatas, ids, vectors

    # Execute embedding requests concurrently across multiple worker threads
    workers = min(MAX_EMBEDDING_WORKERS, len(batches))
    if workers > 1:
        logger.info(f"Generating embeddings for {len(splits)} chunks in {len(batches)} batches across {workers} parallel threads...")
        with ThreadPoolExecutor(max_workers=workers) as executor:
            batch_results = list(executor.map(_embed_single_batch, enumerate(batches)))
    else:
        batch_results = [_embed_single_batch((0, batches[0]))]

    all_texts = []
    all_metas = []
    all_ids = []
    all_vectors = []
    for texts, metadatas, ids, vectors in batch_results:
        all_texts.extend(texts)
        all_metas.extend(metadatas)
        all_ids.extend(ids)
        all_vectors.extend(vectors)

    # Initialize Chroma and populate vectors in one single atomic write
    vectorstore = Chroma(embedding_function=embeddings)
    vectorstore.add_texts(
        texts=all_texts,
        metadatas=all_metas,
        embeddings=all_vectors,
        ids=all_ids
    )

    return vectorstore.as_retriever(search_kwargs={"k": RETRIEVER_K})

def build_bm25_retriever(splits: List[Document]) -> BaseRetriever:
    """Build sparse BM25 lexical retriever."""
    from langchain_community.retrievers.bm25 import BM25Retriever
    bm25 = BM25Retriever.from_documents(splits)
    bm25.k = RETRIEVER_K
    return bm25

def build_hybrid_retriever(splits: List[Document]) -> BaseRetriever:
    """Construct hybrid EnsembleRetriever fusing BM25 and Chroma via RRF."""
    from langchain_classic.retrievers.ensemble import EnsembleRetriever  

    dense = build_semantic_retriever(splits)
    sparse = build_bm25_retriever(splits)
    return EnsembleRetriever(retrievers=[sparse, dense], weights=[0.5, 0.5])
