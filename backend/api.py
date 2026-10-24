import asyncio
import sys
import os
import logging
from logging.handlers import RotatingFileHandler
from contextlib import asynccontextmanager
import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Ensure project root is in sys.path regardless of working directory
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from backend.services import get_agent_service, keepalive_loop
from backend.routes import (
    health_router,
    documents_router,
    chat_router,
    sessions_router,
)

# 1. Create hidden .logs directory so watchfiles ignores log file modifications
os.makedirs(".logs", exist_ok=True)

# 2. Configure logging with rotation (10MB max size, keep 5 backups)
log_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
file_handler = RotatingFileHandler(".logs/app.log", maxBytes=10 * 1024 * 1024, backupCount=5)
file_handler.setFormatter(log_formatter)
file_handler.addFilter(lambda record: not record.name.startswith("watchfiles"))

# Apply to root logger so all app loggers inherit this
logging.basicConfig(level=logging.INFO, handlers=[file_handler])
watchfiles_logger = logging.getLogger("watchfiles")
watchfiles_logger.setLevel(logging.WARNING)
watchfiles_logger.propagate = False
watchfiles_main_logger = logging.getLogger("watchfiles.main")
watchfiles_main_logger.setLevel(logging.WARNING)
watchfiles_main_logger.propagate = False

logger = logging.getLogger(__name__)


# 3. Lifespan context manager for startup & shutdown resource lifecycle
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Research Paper RAG API lifespan...")
    try:
        # Pre-initialize AgentService singleton
        service = get_agent_service()
        logger.info("AgentService initialized successfully (has_retriever=%s).", service.retriever is not None)
    except Exception:
        logger.warning("AgentService warmup notice", exc_info=True)

    app.state.http_client = httpx.AsyncClient(timeout=10.0)

    # Start optional Qdrant Cloud keepalive background task (default: 10 pings every 3600s)
    keepalive_task = None
    enable_keepalive = os.getenv("ENABLE_QDRANT_KEEPALIVE", "true").lower() in ("true", "1", "yes")
    if enable_keepalive:
        interval = int(os.getenv("QDRANT_KEEPALIVE_INTERVAL", "3600"))
        pings = int(os.getenv("QDRANT_KEEPALIVE_COUNT", "10"))
        keepalive_task = asyncio.create_task(keepalive_loop(interval_seconds=interval, ping_count=pings))

    yield

    if keepalive_task:
        keepalive_task.cancel()
        try:
            await keepalive_task
        except asyncio.CancelledError:
            pass

    try:
        await app.state.http_client.aclose()
        logger.info("Application HTTP client closed cleanly.")
    except Exception:
        logger.warning("Error closing HTTP client", exc_info=True)


# 4. FastAPI Application Setup
app = FastAPI(
    title="Research Paper RAG Project API",
    description="Headless streaming REST & SSE API for the Agentic Self-RAG Research Chatbot",
    version="2.0.0",
    lifespan=lifespan,
)

cors_origins_raw = os.getenv("CORS_ALLOW_ORIGINS", "*").strip()
cors_origins = [o.strip() for o in cors_origins_raw.split(",") if o.strip()]
if not cors_origins:
    cors_origins = ["*"]
allow_credentials = False if "*" in cors_origins else True

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 5. Connect modular sub-routers
app.include_router(health_router)
app.include_router(documents_router)
app.include_router(chat_router)
app.include_router(sessions_router)

__all__ = ["app", "get_agent_service"]
