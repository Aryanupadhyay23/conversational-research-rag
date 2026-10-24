from fastapi import APIRouter, Query
from backend.services import get_agent_service, get_cluster_status, ping_qdrant_batch

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


@router.get("/health/qdrant")
async def qdrant_health():
    """Inspect Qdrant Cloud cluster status, collections, and connection latency."""
    return await get_cluster_status()


@router.api_route("/health/qdrant/ping", methods=["GET", "POST"])
async def qdrant_ping(
    count: int = Query(default=10, ge=1, le=50, description="Number of pings to send (1-50, default 10)"),
    delay_seconds: float = Query(default=0.2, ge=0.0, le=5.0, description="Delay between pings in seconds"),
):
    """
    Keep-alive multi-ping endpoint for Qdrant Cloud.
    Pings the cluster N times (default 10) to keep free-tier clusters active and prevent auto-sleep.
    """
    return await ping_qdrant_batch(count=count, delay_seconds=delay_seconds)
