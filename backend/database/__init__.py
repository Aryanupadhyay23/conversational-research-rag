"""
Backend Database Package.
Exposes Upstash Redis persistence, checkpointers, and session state management.
"""

from backend.database.redis import (
    UpstashRedisCheckpointer,
    get_checkpointer,
    get_async_redis_client,
    sanitize_username,
    aget_user_sessions_from_redis,
    asave_user_sessions_to_redis,
    adelete_user_session_from_redis,
    aclear_user_all_sessions_from_redis,
)
from backend.database.documents import DocumentRegistry, calculate_document_hash, get_document_registry

__all__ = [
    "UpstashRedisCheckpointer",
    "get_checkpointer",
    "get_async_redis_client",
    "sanitize_username",
    "aget_user_sessions_from_redis",
    "asave_user_sessions_to_redis",
    "adelete_user_session_from_redis",
    "aclear_user_all_sessions_from_redis",
    "DocumentRegistry",
    "calculate_document_hash",
    "get_document_registry",
]
