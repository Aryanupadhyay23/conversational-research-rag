import logging
from typing import List
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

from backend.config import RETRIEVER_K, get_embeddings

logger = logging.getLogger(__name__)
EMBEDDING_BATCH_SIZE = 50

def build_semantic_retriever(splits: List[Document]) -> BaseRetriever:
    """Build dense Chroma retriever with batched embedding generation."""
    from langchain_chroma import Chroma
    embeddings = get_embeddings()
    first_batch = splits[:EMBEDDING_BATCH_SIZE]
    vectorstore = Chroma.from_documents(documents=first_batch, embedding=embeddings)

    for i in range(EMBEDDING_BATCH_SIZE, len(splits), EMBEDDING_BATCH_SIZE):
        batch = splits[i:i + EMBEDDING_BATCH_SIZE]
        vectorstore.add_documents(documents=batch)

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
