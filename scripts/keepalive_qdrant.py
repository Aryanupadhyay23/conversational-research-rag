#!/usr/bin/env python3
"""
Keep-alive ping script for Qdrant Cloud.
Pings the Qdrant Cloud cluster multiple times (default 10) to prevent cluster auto-sleep / idle suspension.
Can be run on-demand, in GitHub Actions CI/CD cron, or in an hourly loop.
"""

import argparse
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Dict, List


def load_env_fallbacks():
    """Attempt to load .env.rag or .env if python-dotenv is available or parse simply."""
    for filename in [".env.rag", ".env"]:
        filepath = os.path.join(os.getcwd(), filename)
        if os.path.isfile(filepath):
            try:
                from dotenv import load_dotenv
                load_dotenv(filepath, override=False)
                break
            except ImportError:
                # Basic parser if dotenv is not installed
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if not line or line.startswith("#") or "=" not in line:
                                continue
                            k, v = line.split("=", 1)
                            k, v = k.strip(), v.strip().strip("'\"")
                            if k not in os.environ and v:
                                os.environ[k] = v
                except Exception:
                    pass
                break


def resolve_qdrant_config():
    """Retrieve URL and API Key from environment variables."""
    load_env_fallbacks()
    url = os.getenv("QDRANT_URL") or os.getenv("QDRANT_CLUSTER_ENDPOINT") or ""
    url = url.strip().strip("'\"")
    if url and not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    url = url.rstrip("/")
    api_key = (os.getenv("QDRANT_API_KEY") or "").strip().strip("'\"")
    return url, api_key


def ping_once(base_url: str, api_key: str, endpoint: str = "/collections", timeout: float = 10.0) -> Dict:
    """Execute a single ping against Qdrant Cloud."""
    url = f"{base_url}{endpoint}"
    req = urllib.request.Request(url, method="GET")
    if api_key:
        req.add_header("api-key", api_key)
    req.add_header("User-Agent", "QdrantCloudKeepAlive/1.0")

    start_time = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            latency_ms = round((time.time() - start_time) * 1000, 2)
            status_code = response.getcode()
            body = response.read().decode("utf-8", errors="ignore")
            return {
                "success": 200 <= status_code < 300,
                "status_code": status_code,
                "latency_ms": latency_ms,
                "endpoint": endpoint,
                "error": None,
                "response_snippet": body[:120],
            }
    except urllib.error.HTTPError as e:
        latency_ms = round((time.time() - start_time) * 1000, 2)
        return {
            "success": False,
            "status_code": e.code,
            "latency_ms": latency_ms,
            "endpoint": endpoint,
            "error": str(e),
            "response_snippet": "",
        }
    except Exception as e:
        latency_ms = round((time.time() - start_time) * 1000, 2)
        return {
            "success": False,
            "status_code": 0,
            "latency_ms": latency_ms,
            "endpoint": endpoint,
            "error": str(e),
            "response_snippet": "",
        }


def run_ping_batch(base_url: str, api_key: str, count: int = 10, delay_seconds: float = 1.0) -> List[Dict]:
    """Execute count pings to keep Qdrant Cloud cluster actively awake."""
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Starting {count} keep-alive pings to {base_url}...")
    results = []
    for i in range(1, count + 1):
        # Alternate between /collections (which touches the vector index engine) and /healthz
        target_endpoint = "/collections" if i % 2 == 1 else "/healthz"
        res = ping_once(base_url, api_key, endpoint=target_endpoint)
        results.append(res)
        
        status_tag = "OK" if res["success"] else "FAIL"
        print(
            f"  Ping {i:02d}/{count:02d} -> {res['endpoint']} [{status_tag} {res['status_code']}] "
            f"in {res['latency_ms']}ms"
            + (f" | Error: {res['error']}" if res['error'] else "")
        )
        if i < count and delay_seconds > 0:
            time.sleep(delay_seconds)

    successes = sum(1 for r in results if r["success"])
    avg_latency = (
        round(sum(r["latency_ms"] for r in results) / len(results), 2)
        if results
        else 0
    )
    print(
        f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Completed batch: "
        f"{successes}/{count} succeeded. Average latency: {avg_latency}ms."
    )
    return results


def main():
    parser = argparse.ArgumentParser(description="Qdrant Cloud Free-Tier Keep-Alive Ping Tool")
    parser.add_argument("--count", type=int, default=10, help="Number of pings per batch (default: 10)")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between pings in seconds (default: 1.0)")
    parser.add_argument("--loop", action="store_true", help="Run continuously in a loop")
    parser.add_argument(
        "--interval",
        type=int,
        default=3600,
        help="Interval between batches in seconds when using --loop (default: 3600 = 1 hour)",
    )
    parser.add_argument("--url", type=str, default="", help="Override Qdrant Cloud endpoint URL")
    parser.add_argument("--api-key", type=str, default="", help="Override Qdrant Cloud API Key")

    args = parser.parse_args()

    url, api_key = resolve_qdrant_config()
    if args.url:
        url = args.url.strip()
    if args.api_key:
        api_key = args.api_key.strip()

    if not url:
        print("[ERROR] Neither QDRANT_URL nor QDRANT_CLUSTER_ENDPOINT is configured.", file=sys.stderr)
        print("Please set them in environment or in .env.rag", file=sys.stderr)
        sys.exit(1)

    masked_key = f"{api_key[:6]}...{api_key[-4:]}" if len(api_key) > 10 else ("present" if api_key else "none")
    print(f"Target Cluster: {url}")
    print(f"API Key: {masked_key}")

    if args.loop:
        print(f"Loop mode active: running {args.count} pings every {args.interval}s (~{args.interval / 3600:.1f} hours).")
        while True:
            try:
                run_ping_batch(url, api_key, count=args.count, delay_seconds=args.delay)
            except Exception as e:
                print(f"[ERROR] Exception during batch: {e}", file=sys.stderr)
            print(f"Sleeping for {args.interval} seconds until next batch...\n")
            time.sleep(args.interval)
    else:
        results = run_ping_batch(url, api_key, count=args.count, delay_seconds=args.delay)
        failures = sum(1 for r in results if not r["success"])
        sys.exit(1 if failures > 0 else 0)


if __name__ == "__main__":
    main()
