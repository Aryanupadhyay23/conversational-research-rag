import logging
from fastapi import APIRouter, Request

from backend.services import get_agent_service
from backend.database import (
    sanitize_username,
    aget_user_sessions_from_redis,
    asave_user_sessions_to_redis,
    adelete_user_session_from_redis,
    aclear_user_all_sessions_from_redis,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Sessions & Redis Memory"])


@router.get("/user/{username}/sessions")
async def get_user_sessions_endpoint(username: str):
    """Fetch stored conversation sessions for a given user from Upstash Redis asynchronously."""
    clean_user = sanitize_username(username)
    sessions = await aget_user_sessions_from_redis(clean_user)
    return {"status": "success", "username": clean_user, "sessions": sessions}


@router.post("/user/{username}/sessions")
async def save_user_sessions_endpoint(username: str, request: Request):
    """Save or update conversation sessions list for a user in Upstash Redis asynchronously."""
    clean_user = sanitize_username(username)
    payload = await request.json()
    if isinstance(payload, dict) and "sessions" in payload and isinstance(payload["sessions"], dict):
        sessions = payload["sessions"]
    elif isinstance(payload, dict):
        sessions = payload
    else:
        sessions = {}
    success = await asave_user_sessions_to_redis(clean_user, sessions)
    return {"status": "success" if success else "error", "username": clean_user}


@router.delete("/user/{username}/session/{session_id}")
async def delete_user_session_endpoint(username: str, session_id: str):
    """Delete a single session and its checkpointer memory from Upstash Redis asynchronously."""
    clean_user = sanitize_username(username)
    service = get_agent_service()
    success = await adelete_user_session_from_redis(clean_user, session_id, checkpointer=service.checkpointer)
    return {"status": "success" if success else "error", "username": clean_user, "session_id": session_id}


@router.post("/user/{username}/clear")
async def clear_user_sessions_endpoint(username: str):
    """Clear all conversation sessions and checkpointer memory for a user from Upstash Redis asynchronously."""
    clean_user = sanitize_username(username)
    service = get_agent_service()
    success = await aclear_user_all_sessions_from_redis(clean_user, checkpointer=service.checkpointer)
    return {"status": "success" if success else "error", "username": clean_user}


@router.post("/session/{session_id}/clear")
async def clear_session_memory(session_id: str):
    """Clear conversational memory checkpointer for the specified session asynchronously."""
    service = get_agent_service()
    await service.aclear_memory(session_id=session_id)
    return {"status": "success", "session_id": session_id, "message": "Memory checkpointer cleared."}
