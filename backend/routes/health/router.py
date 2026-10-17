from fastapi import APIRouter
from backend.services import get_agent_service

router = APIRouter(tags=["Health"])


@router.get("/")
async def read_root():
    """Root health check confirmation."""
    return {"detail": "Research Paper RAG API is running."}


@router.get("/health")
async def health_check():
    """Detailed health check endpoint for frontend, Docker, and uptime monitoring."""
    service = get_agent_service()
    return {
        "status": "healthy",
        "service": "Research Paper RAG Project API",
        "has_retriever": service.retriever is not None,
    }
