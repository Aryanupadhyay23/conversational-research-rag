import logging
from typing import List
from fastapi import APIRouter, UploadFile, File, HTTPException

from backend.services import get_agent_service
from backend.ingestion.pipeline import ingest_documents_async

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Documents & Ingestion"])


class SyncUploadWrapper:
    """Wrapper to support synchronous readers on asynchronous upload file bytes."""
    def __init__(self, name: str, content: bytes):
        self.name = name
        self.content = content

    def read(self):
        return self.content


@router.post("/upload")
async def upload_documents(files: List[UploadFile] = File(...)):
    """
    Ingest uploaded research paper PDFs into vectorstore asynchronously.
    Returns chunk count and indexed document filenames.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided for upload.")

    try:
        wrapped_files = []
        filenames = []
        for file in files:
            content = await file.read()
            wrapped_files.append(SyncUploadWrapper(file.filename, content))
            filenames.append(file.filename)

        retriever, chunk_count = await ingest_documents_async(wrapped_files)
        get_agent_service().set_retriever(retriever)
        return {
            "status": "success",
            "chunks_indexed": chunk_count,
            "files": filenames,
        }
    except Exception as e:
        logger.error(f"Error during document ingestion: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
