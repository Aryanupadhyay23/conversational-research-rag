import asyncio
import json
import logging
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.service import AgentService
from backend.ingestion.pipeline import ingest_documents_async

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Research Paper RAG Project API",
    description="Headless streaming REST & SSE API for the Agentic Self-RAG Research Chatbot",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_service: Optional[AgentService] = None

def get_agent_service() -> AgentService:
    """Lazy initialize AgentService singleton."""
    global _service
    if _service is None:
        _service = AgentService()
    return _service

class SyncUploadWrapper:
    def __init__(self, name: str, content: bytes):
        self.name = name
        self.content = content

    def read(self):
        return self.content

class ChatRequest(BaseModel):
    query: str
    session_id: str = "default_session"

@app.get("/health")
def health_check():
    """Health check endpoint for frontend, Docker, and uptime monitoring."""
    return {
        "status": "healthy",
        "service": "Research Paper RAG Project API",
        "has_retriever": get_agent_service().retriever is not None
    }

@app.post("/upload")
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
            "files": filenames
        }
    except Exception as e:
        logger.error(f"Error during document ingestion: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

async def _extract_query_and_session(
    request: Request,
    query: Optional[str] = None,
    session_id: Optional[str] = None
) -> tuple[str, str]:
    """Helper to flexibly extract query and session_id from either JSON or Form data."""
    if query:
        return query, session_id or "default_session"

    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            body = await request.json()
            q = body.get("query", "").strip()
            s = body.get("session_id", "default_session").strip()
            if q:
                return q, s
        except Exception:
            pass

    try:
        form = await request.form()
        q = form.get("query", "")
        s = form.get("session_id", "default_session")
        if q:
            return str(q).strip(), str(s).strip()
    except Exception:
        pass

    raise HTTPException(status_code=422, detail="Missing 'query' in request body or form.")

@app.post("/chat")
async def chat_query(
    request: Request,
    query: Optional[str] = Form(None),
    session_id: Optional[str] = Form(None)
):
    """Non-streaming JSON response endpoint."""
    user_query, s_id = await _extract_query_and_session(request, query, session_id)
    service = get_agent_service()
    try:
        res = await service.aexecute_query(user_query, session_id=s_id)
        return {
            "answer": res.answer,
            "route": res.route,
            "reflection_logs": res.reflection_logs,
            "sources": res.sources,
            "claim_analysis": res.claim_analysis,
            "metadata": res.metadata,
        }
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat/stream")
async def chat_stream(
    request: Request,
    query: Optional[str] = Form(None),
    session_id: Optional[str] = Form(None)
):
    """
    Stream agent response, reasoning status, tokens, and final citations/metadata
    using Server-Sent Events (SSE).
    """
    user_query, s_id = await _extract_query_and_session(request, query, session_id)
    service = get_agent_service()

    async def event_generator():
        try:
            async for event in service.astream_query(user_query, session_id=s_id):
                yield f"data: {json.dumps(event)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error(f"Error during SSE streaming: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@app.post("/session/{session_id}/clear")
async def clear_session_memory(session_id: str):
    """Clear conversational memory checkpointer for the specified session."""
    service = get_agent_service()
    service.clear_memory()
    return {"status": "success", "session_id": session_id, "message": "Memory checkpointer cleared."}
