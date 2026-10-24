"""
Qdrant Cloud keep-alive service.
Periodically pings Qdrant Cloud cluster endpoints to prevent cluster idle suspension/sleep on free tiers.
"""

import asyncio
import logging
import os
import time
from typing import Any, Dict, List

import httpx

from backend.config import QDRANT_API_KEY, QDRANT_URL

logger = logging.getLogger(__name__)


def get_target_url() -> str:
    url = (QDRANT_URL or os.getenv("QDRANT_CLUSTER_ENDPOINT") or "").strip().rstrip("/")
    if url and not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    return url


def get_headers() -> Dict[str, str]:
    headers = {"User-Agent": "QdrantCloudKeepAlive/1.0"}
    api_key = (QDRANT_API_KEY or os.getenv("QDRANT_API_KEY") or "").strip()
    if api_key:
        headers["api-key"] = api_key
    return headers


async def ping_qdrant_single(
    client: httpx.AsyncClient, endpoint: str = "/collections", timeout: float = 10.0
) -> Dict[str, Any]:
    """Execute a single asynchronous ping against Qdrant Cloud."""
    base_url = get_target_url()
    if not base_url:
        return {
            "success": False,
            "status_code": 0,
            "latency_ms": 0.0,
            "endpoint": endpoint,
            "error": "No Qdrant URL configured",
        }

    url = f"{base_url}{endpoint}"
    start = time.time()
    try:
        resp = await client.get(url, headers=get_headers(), timeout=timeout)
        latency = round((time.time() - start) * 1000, 2)
        return {
            "success": 200 <= resp.status_code < 300,
            "status_code": resp.status_code,
            "latency_ms": latency,
            "endpoint": endpoint,
            "error": None if 200 <= resp.status_code < 300 else f"HTTP {resp.status_code}",
        }
    except Exception as e:
        latency = round((time.time() - start) * 1000, 2)
        return {
            "success": False,
            "status_code": 0,
            "latency_ms": latency,
            "endpoint": endpoint,
            "error": str(e),
        }


async def ping_qdrant_batch(count: int = 10, delay_seconds: float = 0.2) -> Dict[str, Any]:
    """Execute count pings (default 10) against Qdrant Cloud."""
    base_url = get_target_url()
    count = max(1, min(count, 50))
    results: List[Dict[str, Any]] = []

    async with httpx.AsyncClient() as client:
        for i in range(1, count + 1):
            endpoint = "/collections" if i % 2 == 1 else "/healthz"
            res = await ping_qdrant_single(client, endpoint=endpoint)
            results.append(res)
            if i < count and delay_seconds > 0:
                await asyncio.sleep(delay_seconds)

    successes = sum(1 for r in results if r["success"])
    latencies = [r["latency_ms"] for r in results if r["latency_ms"] > 0]
    avg_latency = round(sum(latencies) / len(latencies), 2) if latencies else 0.0

    return {
        "target_url": base_url,
        "total_pings": count,
        "successful_pings": successes,
        "failed_pings": count - successes,
        "avg_latency_ms": avg_latency,
        "all_successful": successes == count,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "pings": results,
    }


async def get_cluster_status() -> Dict[str, Any]:
    """Check connectivity and inspect cluster collections/health."""
    base_url = get_target_url()
    if not base_url:
        return {"status": "unconfigured", "detail": "QDRANT_URL is not set"}

    start = time.time()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{base_url}/collections", headers=get_headers())
            latency = round((time.time() - start) * 1000, 2)
            if resp.status_code == 200:
                data = resp.json().get("result", {})
                collections = [c.get("name") for c in data.get("collections", [])]
                return {
                    "status": "connected",
                    "target_url": base_url,
                    "collections": collections,
                    "collection_count": len(collections),
                    "latency_ms": latency,
                }
            return {
                "status": "error",
                "target_url": base_url,
                "status_code": resp.status_code,
                "detail": resp.text[:200],
                "latency_ms": latency,
            }
    except Exception as e:
        latency = round((time.time() - start) * 1000, 2)
        return {
            "status": "unreachable",
            "target_url": base_url,
            "error": str(e),
            "latency_ms": latency,
        }


async def keepalive_loop(interval_seconds: int = 3600, ping_count: int = 10):
    """Background task loop that pings Qdrant every interval_seconds (default 1 hour)."""
    logger.info(
        "Started Qdrant Cloud keepalive background worker (every %ds, %d pings/batch).",
        interval_seconds,
        ping_count,
    )
    # Initial warmup ping after 10 seconds of server startup
    await asyncio.sleep(10)
    while True:
        try:
            res = await ping_qdrant_batch(count=ping_count, delay_seconds=0.5)
            logger.info(
                "Qdrant keepalive batch completed: %d/%d succeeded (avg: %sms).",
                res["successful_pings"],
                res["total_pings"],
                res["avg_latency_ms"],
            )
        except asyncio.CancelledError:
            logger.info("Qdrant keepalive worker cancelled.")
            break
        except Exception as e:
            logger.warning("Qdrant keepalive ping error: %s", e)

        try:
            await asyncio.sleep(interval_seconds)
        except asyncio.CancelledError:
            break
