import json
import asyncio
import logging
from typing import List, Optional, Tuple
from fastapi import APIRouter, UploadFile, File, Form, Query, HTTPException
from fastapi.responses import StreamingResponse

from backend.config import MAX_UPLOAD_FILES, MAX_UPLOAD_MB_PER_FILE
from backend.services import get_agent_service
from backend.database import sanitize_username
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


def _thread_key(username: Optional[str], session_id: Optional[str]) -> str:
    """Build the same user-scoped thread key used by the chat endpoints."""
    clean_user = sanitize_username(username)
    clean_session = (session_id or "default_session").strip()
    prefix = f"{clean_user}:"
    return clean_session if clean_session.startswith(prefix) else f"{prefix}{clean_session}"


async def _validate_and_read_files(files: List[UploadFile]) -> Tuple[List[SyncUploadWrapper], List[str]]:
    """Validate uploaded file count, extensions, content-types, and sizes."""
    if not files:
        raise HTTPException(status_code=400, detail="No files provided for upload.")

    if len(files) > MAX_UPLOAD_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"Upload file count limit exceeded: received {len(files)} files, maximum allowed is {MAX_UPLOAD_FILES}."
        )

    max_bytes = MAX_UPLOAD_MB_PER_FILE * 1024 * 1024
    wrapped_files = []
    filenames = []

    for file in files:
        filename = file.filename or ""
        if not filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type for '{filename}'. Only PDF documents (.pdf) are supported."
            )

        content_type = (file.content_type or "").lower()
        if content_type and content_type not in ("application/pdf", "application/x-pdf", "application/octet-stream"):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid content type '{content_type}' for '{filename}'. Only PDF documents are allowed."
            )

        content = await file.read()
        if len(content) > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"File '{filename}' exceeds maximum allowed size of {MAX_UPLOAD_MB_PER_FILE}MB (file size: {len(content) / (1024 * 1024):.1f}MB)."
            )

        wrapped_files.append(SyncUploadWrapper(filename, content))
        filenames.append(filename)

    return wrapped_files, filenames


@router.get("/documents/status")
@router.get("/status")
async def get_document_status(
    username: Optional[str] = Query(None),
    session_id: Optional[str] = Query(None),
):
    """
    Return whether an active retriever exists for the given user/session thread.
    """
    has_retriever = get_agent_service().has_retriever(
        thread_id=_thread_key(username, session_id)
    )
    return {
        "status": "success",
        "has_retriever": has_retriever,
        "username": username,
        "session_id": session_id,
    }


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
    wrapped_files, filenames = await _validate_and_read_files(files)

    try:
        retriever, chunk_count = await ingest_documents_async(wrapped_files)
        thread_key = _thread_key(username, session_id)
        service = get_agent_service()
        service.set_retriever(retriever, session_id=thread_key)

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
    wrapped_files, filenames = await _validate_and_read_files(files)

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
            thread_key = _thread_key(username, session_id)
            service = get_agent_service()
            service.set_retriever(retriever, session_id=thread_key)

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
