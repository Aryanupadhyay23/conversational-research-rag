"""
Upstash Redis Checkpointer and Session Management.
Enables distributed and persistent conversation history across session turns
using Upstash Redis REST API. Supports both synchronous and asynchronous operations.
"""

import logging
import asyncio
import re
from typing import Optional, AsyncIterator, Iterator, Sequence, Tuple, Any, Dict
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    ChannelVersions,
)
from langgraph.checkpoint.memory import MemorySaver

from backend.config import UPSTASH_REDIS_REST_URL, UPSTASH_REDIS_REST_TOKEN

logger = logging.getLogger(__name__)


class UpstashRedisCheckpointer(BaseCheckpointSaver):
    """
    Unified LangGraph Checkpointer backed by Upstash Redis.
    Uses Upstash REST API for serverless-ready, robust state persistence without requiring
    Redis Stack modules (RediSearch / RedisJSON). Supports both synchronous (.invoke)
    and asynchronous (.ainvoke, .astream_events, .aget_state) executions.
    """

    def __init__(self, url: str, token: str):
        super().__init__()
        from langgraph.checkpoint.upstash_redis import UpstashRedisSaver
        from langgraph.checkpoint.upstash_redis.aio import AsyncUpstashRedisSaver

        self.url = url
        self.token = token
        self._sync_saver = UpstashRedisSaver.from_conn_info(url=url, token=token)
        self._async_saver = AsyncUpstashRedisSaver.from_conn_info(url=url, token=token)
        self.serde = self._sync_saver.serde

    def get_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        return self._sync_saver.get_tuple(config)

    def list(
        self,
        config: Optional[RunnableConfig],
        *,
        filter: Optional[Dict[str, Any]] = None,
        before: Optional[RunnableConfig] = None,
        limit: Optional[int] = None,
    ) -> Iterator[CheckpointTuple]:
        return self._sync_saver.list(config, filter=filter, before=before, limit=limit)

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        return self._sync_saver.put(config, checkpoint, metadata, new_versions)

    def put_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[Tuple[str, Any]],
        task_id: str,
    ) -> None:
        return self._sync_saver.put_writes(config, writes, task_id)

    async def aget_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        return await self._async_saver.aget_tuple(config)

    async def alist(
        self,
        config: Optional[RunnableConfig],
        *,
        filter: Optional[Dict[str, Any]] = None,
        before: Optional[RunnableConfig] = None,
        limit: Optional[int] = None,
    ) -> AsyncIterator[CheckpointTuple]:
        async for item in self._async_saver.alist(config, filter=filter, before=before, limit=limit):
            yield item

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        return await self._async_saver.aput(config, checkpoint, metadata, new_versions)

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[Tuple[str, Any]],
        task_id: str,
    ) -> None:
        return await self._async_saver.aput_writes(config, writes, task_id)

    def delete_thread(self, thread_id: str) -> None:
        """Delete conversation history checkpoints for a given session/thread from Upstash Redis."""
        try:
            self._sync_saver.delete_thread(thread_id)
            logger.info("Successfully deleted conversation history for session '%s' from Upstash Redis.", thread_id)
        except Exception as e:
            logger.warning("Failed to delete session '%s' from Upstash Redis: %s", thread_id, e)

    async def adelete_thread(self, thread_id: str) -> None:
        """Asynchronously delete conversation history checkpoints for a given session/thread from Upstash Redis."""
        try:
            await self._async_saver.adelete_thread(thread_id)
            logger.info("Successfully deleted conversation history for session '%s' from Upstash Redis.", thread_id)
        except Exception as e:
            logger.warning("Failed to async delete session '%s' from Upstash Redis: %s", thread_id, e)


def get_checkpointer(
    url: Optional[str] = None,
    token: Optional[str] = None
) -> BaseCheckpointSaver:
    """
    Factory function returning the LangGraph checkpointer.
    Uses Upstash Redis when UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN are available,
    falling back to in-memory MemorySaver if unavailable or upon connection error.
    """
    redis_url = url or UPSTASH_REDIS_REST_URL
    redis_token = token or UPSTASH_REDIS_REST_TOKEN

    if redis_url and redis_token:
        try:
            logger.info("Initializing LangGraph Upstash Redis checkpointer (%s)...", redis_url)
            return UpstashRedisCheckpointer(url=redis_url, token=redis_token)
        except Exception as e:
            logger.error(
                "Failed to initialize Upstash Redis checkpointer (%s). Falling back to in-memory MemorySaver.",
                e,
                exc_info=True
            )
            return MemorySaver()

    logger.warning("Upstash Redis credentials not configured. Falling back to in-memory MemorySaver.")
    return MemorySaver()


def get_redis_client():
    """Return Upstash Redis client instance if credentials configured, else None."""
    if UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN:
        try:
            from upstash_redis import Redis
            return Redis(url=UPSTASH_REDIS_REST_URL, token=UPSTASH_REDIS_REST_TOKEN)
        except Exception as e:
            logger.warning("Failed to initialize Upstash Redis client: %s", e)
    return None


_IN_MEMORY_USER_SESSIONS: Dict[str, Dict[str, Any]] = {}


def is_guest_user(username: Optional[str]) -> bool:
    """Return True if user is in guest mode."""
    if not username:
        return True
    u = username.strip().lower()
    return u.startswith("guest_") or u in ("guest", "default_user", "")


def sanitize_username(username: Optional[str]) -> str:
    """Sanitize username or return default, preserving words by replacing spaces with underscores."""
    if not username:
        return "default_user"
    cleaned = re.sub(r"\s+", "_", username.strip().lower())
    clean = "".join(c for c in cleaned if c.isalnum() or c in ("_", "-", "."))
    return clean if clean else "default_user"


def get_user_sessions_from_redis(username: str) -> Dict[str, Any]:
    """Fetch stored conversation sessions for a given user from Upstash Redis or in-memory fallback."""
    clean_user = sanitize_username(username)
    client = get_redis_client()
    if client:
        try:
            import json
            key = f"rag:user_sessions:{clean_user}"
            raw = client.get(key)
            if raw:
                data = json.loads(raw) if isinstance(raw, str) else raw
                _IN_MEMORY_USER_SESSIONS[clean_user] = data
                return data
        except Exception as e:
            logger.warning("Error fetching sessions for user '%s' from Redis: %s", clean_user, e)
    return _IN_MEMORY_USER_SESSIONS.get(clean_user, {})


def save_user_sessions_to_redis(username: str, sessions: Dict[str, Any]) -> bool:
    """Persist conversation sessions dictionary for a user to Upstash Redis and in-memory cache."""
    clean_user = sanitize_username(username)
    _IN_MEMORY_USER_SESSIONS[clean_user] = dict(sessions)
    client = get_redis_client()
    if not client:
        return True
    try:
        import json
        key = f"rag:user_sessions:{clean_user}"
        payload = json.dumps(sessions)
        client.set(key, payload)
        return True
    except Exception as e:
        logger.warning("Error saving sessions for user '%s' to Redis: %s", clean_user, e)
        return False


def delete_user_session_from_redis(username: str, session_id: str, checkpointer: Optional[BaseCheckpointSaver] = None) -> bool:
    """Delete a single session from user's session list and checkpointer memory."""
    clean_user = sanitize_username(username)
    # 1. Update session list
    current = get_user_sessions_from_redis(clean_user)
    if session_id in current:
        del current[session_id]
        save_user_sessions_to_redis(clean_user, current)

    # 2. Delete thread in checkpointer
    thread_key = f"{clean_user}:{session_id}"
    cp = checkpointer or get_checkpointer()
    if hasattr(cp, "delete_thread"):
        try:
            cp.delete_thread(thread_key)
            cp.delete_thread(session_id)  # Also clean un-prefixed if any
        except Exception as e:
            logger.warning("Error deleting thread '%s' from checkpointer: %s", thread_key, e)
    return True


def clear_user_all_sessions_from_redis(username: str, checkpointer: Optional[BaseCheckpointSaver] = None) -> bool:
    """Clear all session metadata and checkpointer threads for a user from Upstash Redis."""
    clean_user = sanitize_username(username)
    client = get_redis_client()
    current = get_user_sessions_from_redis(clean_user)
    cp = checkpointer or get_checkpointer()

    if hasattr(cp, "delete_thread"):
        for s_id in current.keys():
            try:
                cp.delete_thread(f"{clean_user}:{s_id}")
                cp.delete_thread(s_id)
            except Exception:
                pass

    if client:
        try:
            client.delete(f"rag:user_sessions:{clean_user}")
            return True
        except Exception as e:
            logger.warning("Error clearing sessions for user '%s' from Redis: %s", clean_user, e)
    return True


def get_async_redis_client():
    """Return async Upstash Redis client instance if credentials configured, else None."""
    if UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN:
        try:
            from upstash_redis.asyncio import Redis
            return Redis(url=UPSTASH_REDIS_REST_URL, token=UPSTASH_REDIS_REST_TOKEN)
        except Exception as e:
            logger.warning("Failed to initialize async Upstash Redis client: %s", e)
    return None


async def aget_user_sessions_from_redis(username: str) -> Dict[str, Any]:
    """Asynchronously fetch stored conversation sessions for a given user from Upstash Redis or in-memory fallback."""
    clean_user = sanitize_username(username)
    client = get_async_redis_client()
    if client:
        try:
            import json
            key = f"rag:user_sessions:{clean_user}"
            raw = await client.get(key)
            if raw:
                data = json.loads(raw) if isinstance(raw, str) else raw
                _IN_MEMORY_USER_SESSIONS[clean_user] = data
                return data
        except Exception as e:
            logger.warning("Error fetching sessions for user '%s' from async Redis: %s", clean_user, e)
        finally:
            try:
                await client.close()
            except Exception:
                pass
    return _IN_MEMORY_USER_SESSIONS.get(clean_user, {})


async def asave_user_sessions_to_redis(username: str, sessions: Dict[str, Any]) -> bool:
    """Asynchronously persist conversation sessions dictionary for a user to Upstash Redis and in-memory cache."""
    clean_user = sanitize_username(username)
    _IN_MEMORY_USER_SESSIONS[clean_user] = dict(sessions)
    client = get_async_redis_client()
    if not client:
        return True
    try:
        import json
        key = f"rag:user_sessions:{clean_user}"
        payload = json.dumps(sessions)
        await client.set(key, payload)
        return True
    except Exception as e:
        logger.warning("Error saving sessions for user '%s' to async Redis: %s", clean_user, e)
        return False
    finally:
        try:
            await client.close()
        except Exception:
            pass


async def adelete_user_session_from_redis(username: str, session_id: str, checkpointer: Optional[BaseCheckpointSaver] = None) -> bool:
    """Asynchronously delete a single session from user's session list and checkpointer memory."""
    clean_user = sanitize_username(username)
    # 1. Update session list
    current = await aget_user_sessions_from_redis(clean_user)
    if session_id in current:
        del current[session_id]
        await asave_user_sessions_to_redis(clean_user, current)

    # 2. Delete thread in checkpointer
    thread_key = f"{clean_user}:{session_id}"
    cp = checkpointer or get_checkpointer()
    if hasattr(cp, "adelete_thread"):
        try:
            await cp.adelete_thread(thread_key)
            await cp.adelete_thread(session_id)
        except Exception as e:
            logger.warning("Error async deleting thread '%s' from checkpointer: %s", thread_key, e)
    elif hasattr(cp, "delete_thread"):
        try:
            await asyncio.to_thread(cp.delete_thread, thread_key)
            await asyncio.to_thread(cp.delete_thread, session_id)
        except Exception as e:
            logger.warning("Error deleting thread '%s' from checkpointer: %s", thread_key, e)
    return True


async def aclear_user_all_sessions_from_redis(username: str, checkpointer: Optional[BaseCheckpointSaver] = None) -> bool:
    """Asynchronously clear all session metadata and checkpointer threads for a user from Upstash Redis."""
    clean_user = sanitize_username(username)
    client = get_async_redis_client()
    current = await aget_user_sessions_from_redis(clean_user)
    _IN_MEMORY_USER_SESSIONS.pop(clean_user, None)
    cp = checkpointer or get_checkpointer()

    for s_id in current.keys():
        thread_key = f"{clean_user}:{s_id}"
        if hasattr(cp, "adelete_thread"):
            try:
                await cp.adelete_thread(thread_key)
                await cp.adelete_thread(s_id)
            except Exception:
                pass
        elif hasattr(cp, "delete_thread"):
            try:
                await asyncio.to_thread(cp.delete_thread, thread_key)
                await asyncio.to_thread(cp.delete_thread, s_id)
            except Exception:
                pass

    if client:
        try:
            await client.delete(f"rag:user_sessions:{clean_user}")
            return True
        except Exception as e:
            logger.warning("Error clearing sessions for user '%s' from async Redis: %s", clean_user, e)
        finally:
            try:
                await client.close()
            except Exception:
                pass
    return True
