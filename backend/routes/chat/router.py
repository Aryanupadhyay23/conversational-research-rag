import json
import logging
from typing import Optional
from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import StreamingResponse

from backend.services import get_agent_service
from backend.database import sanitize_username

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Chat & Streaming"])


async def _extract_query_and_session(
    request: Request,
    query: Optional[str] = None,
    session_id: Optional[str] = None,
    username: Optional[str] = None,
) -> tuple[str, str, str, str]:
    """Helper to flexibly extract query, session_id, username, and prefixed thread_id."""
    clean_user = sanitize_username(username or request.query_params.get("username"))

    if query:
        s = session_id or "default_session"
        thread_id = f"{clean_user}:{s}" if not s.startswith(f"{clean_user}:") else s
        return query, s, clean_user, thread_id

    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            body = await request.json()
            q = body.get("query", "").strip()
            s = body.get("session_id", "default_session").strip()
            u = sanitize_username(body.get("username") or clean_user)
            if q:
                thread_id = f"{u}:{s}" if not s.startswith(f"{u}:") else s
                return q, s, u, thread_id
        except Exception:
            pass

    try:
        form = await request.form()
        q = form.get("query", "")
        s = form.get("session_id", "default_session")
        u = sanitize_username(form.get("username") or clean_user)
        if q:
            thread_id = f"{u}:{s}" if not str(s).startswith(f"{u}:") else str(s)
            return str(q).strip(), str(s).strip(), u, thread_id
    except Exception:
        pass

    raise HTTPException(status_code=422, detail="Missing 'query' in request body or form.")


@router.post("/chat")
async def chat_query(
    request: Request,
    query: Optional[str] = Form(None),
    session_id: Optional[str] = Form(None),
    username: Optional[str] = Form(None),
):
    """Non-streaming JSON response endpoint."""
    user_query, s_id, user, thread_id = await _extract_query_and_session(request, query, session_id, username)
    service = get_agent_service()
    try:
        res = await service.aexecute_query(user_query, session_id=thread_id)
        return {
            "answer": res.answer,
            "route": res.route,
            "reflection_logs": res.reflection_logs,
            "sources": res.sources,
            "claim_analysis": res.claim_analysis,
            "metadata": res.metadata,
            "username": user,
            "session_id": s_id,
        }
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/stream")
async def chat_stream(
    request: Request,
    query: Optional[str] = Form(None),
    session_id: Optional[str] = Form(None),
    username: Optional[str] = Form(None),
):
    """
    Stream agent response, reasoning status, tokens, and final citations/metadata
    using Server-Sent Events (SSE).
    """
    user_query, s_id, user, thread_id = await _extract_query_and_session(request, query, session_id, username)
    service = get_agent_service()

    async def event_generator():
        try:
            async for event in service.astream_query(user_query, session_id=thread_id):
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
