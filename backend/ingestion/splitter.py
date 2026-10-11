import uuid
from typing import List
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.config import CHUNK_SIZE, CHUNK_OVERLAP

def split_documents(documents: List[Document]) -> List[Document]:
    """
    Split loaded documents into chunks with unique IDs and contextual headers.
    Prepends [Document: {name} | Page {page}] to anchor semantic vector representations.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    chunks = splitter.split_documents(documents)

    enriched_chunks = []
    for idx, c in enumerate(chunks):
        meta = dict(c.metadata)
        source_name = meta.get("source_name") or meta.get("source", "Document")
        page_idx = meta.get("page", 0)
        page_number = page_idx + 1

        chunk_id = str(uuid.uuid4())
        meta["chunk_id"] = chunk_id
        meta["chunk_index"] = idx
        meta["source_name"] = source_name
        meta["page"] = page_idx
        meta["page_number"] = page_number

        # Contextual prefix for superior dense retrieval and keyword matching
        header = f"[Document: {source_name} | Page {page_number}]\n"
        contextual_content = header + c.page_content.strip()

        enriched_chunks.append(Document(
            page_content=contextual_content,
            metadata=meta
        ))

    return enriched_chunks
