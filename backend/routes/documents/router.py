import json
import asyncio
import logging
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse

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
async def upload_documents(
    files: List[UploadFile] = File(...),
    session_id: Optional[str] = Form(None),
    username: Optional[str] = Form(None),
):
    """
    Ingest uploaded research paper PDFs into vectorstore asynchronously (standard non-streaming).
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
        thread_key = f"{username}:{session_id}" if username and session_id else (session_id or None)
        get_agent_service().set_retriever(retriever, session_id=thread_key)
        return {
            "status": "success",
            "chunks_indexed": chunk_count,
            "files": filenames,
        }
    except Exception as e:
        logger.error(f"Error during document ingestion: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload/stream")
async def upload_documents_stream(
    files: List[UploadFile] = File(...),
    session_id: Optional[str] = Form(None),
    username: Optional[str] = Form(None),
):
    """
    Stream real-time embedding progress and dynamic remaining-time estimates
    for uploaded research paper PDFs using Server-Sent Events (SSE).
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided for upload.")

    wrapped_files = []
    filenames = []
    for file in files:
        content = await file.read()
        wrapped_files.append(SyncUploadWrapper(file.filename, content))
        filenames.append(file.filename)

    queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def sync_progress_callback(info: dict):
        loop.call_soon_threadsafe(queue.put_nowait, {"type": "progress", **info})

    async def run_ingestion():
        try:
            loop.call_soon_threadsafe(
                queue.put_nowait,
                {
                    "type": "progress",
                    "stage": "parsing",
                    "message": "Extracting text and structure from research papers...",
                    "percent": 5.0,
                }
            )
            retriever, chunk_count = await ingest_documents_async(
                wrapped_files,
                progress_callback=sync_progress_callback
            )
            thread_key = f"{username}:{session_id}" if username and session_id else (session_id or None)
            get_agent_service().set_retriever(retriever, session_id=thread_key)
            loop.call_soon_threadsafe(
                queue.put_nowait,
                {
                    "type": "completed",
                    "status": "success",
                    "chunks_indexed": chunk_count,
                    "files": filenames,
                    "percent": 100.0,
                }
            )
        except Exception as e:
            logger.error("Error during streaming ingestion: %s", e, exc_info=True)
            loop.call_soon_threadsafe(
                queue.put_nowait,
                {"type": "error", "error": str(e)}
            )
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, None)

    asyncio.create_task(run_ingestion())

    async def event_generator():
        while True:
            item = await queue.get()
            if item is None:
                yield "data: [DONE]\n\n"
                break
            yield f"data: {json.dumps(item)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
