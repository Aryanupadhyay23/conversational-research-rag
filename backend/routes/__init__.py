from backend.routes.health.router import router as health_router
from backend.routes.documents.router import router as documents_router
from backend.routes.chat.router import router as chat_router
from backend.routes.sessions.router import router as sessions_router

__all__ = [
    "health_router",
    "documents_router",
    "chat_router",
    "sessions_router",
]
