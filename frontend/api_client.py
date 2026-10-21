import os
import json
import hashlib
import logging
from typing import Generator, Dict, Any, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

def get_backend_url() -> str:
    """Return normalized backend URL from environment or default."""
    return os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")

def check_backend_health(base_url: Optional[str] = None) -> Tuple[bool, str]:
    """
    Check if the FastAPI backend is running and healthy.
    Returns (is_healthy, message).
    """
    url = (base_url or get_backend_url()).rstrip("/")
    try:
        resp = requests.get(f"{url}/health", timeout=3.0)
        if resp.status_code == 200 and resp.json().get("status") == "healthy":
            return True, "FastAPI Backend Online"
        return False, f"Backend returned HTTP {resp.status_code}"
    except requests.exceptions.ConnectionError:
        return False, f"Cannot connect to backend at {url}. Make sure FastAPI is running (uvicorn api:app --port 8000)."
    except Exception as e:
        return False, f"Backend health check error: {e}"

def upload_documents(
    uploaded_files: list,
    session_id: Optional[str] = None,
    username: Optional[str] = None,
    base_url: Optional[str] = None
) -> dict:
    """
    Upload PDF files to FastAPI /upload endpoint for layout extraction and indexing.
    """
    url = (base_url or get_backend_url()).rstrip("/")
    files = []
    for f in uploaded_files:
        content = f.getvalue() if hasattr(f, "getvalue") else f.read()
        files.append(("files", (f.name, content, "application/pdf")))

    data = {}
    if session_id:
        data["session_id"] = session_id
    if username:
        data["username"] = username

    try:
        resp = requests.post(
            f"{url}/upload",
            files=files,
            data=data,
            timeout=300.0
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        error_detail = ""
        if hasattr(e, "response") and e.response is not None:
            try:
                error_detail = e.response.json().get("detail", "")
            except Exception:
                error_detail = e.response.text
        raise RuntimeError(error_detail or str(e))

def upload_documents_stream(
    uploaded_files: list,
    session_id: Optional[str] = None,
    username: Optional[str] = None,
    base_url: Optional[str] = None
) -> Generator[Dict[str, Any], None, None]:
    """
    Upload PDF files to FastAPI /upload/stream endpoint and stream live embedding progress,
    remaining-time estimates, and request counters via Server-Sent Events (SSE).
    """
    url = (base_url or get_backend_url()).rstrip("/")
    files = []
    for f in uploaded_files:
        content = f.getvalue() if hasattr(f, "getvalue") else f.read()
        files.append(("files", (f.name, content, "application/pdf")))

    data = {}
    if session_id:
        data["session_id"] = session_id
    if username:
        data["username"] = username

    try:
        with requests.post(
            f"{url}/upload/stream",
            files=files,
            data=data,
            stream=True,
            timeout=300.0
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines(decode_unicode=True):
                if not line:
                    continue
                if line.startswith("data: "):
                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        event = json.loads(data_str)
                        yield event
                    except json.JSONDecodeError:
                        continue
    except requests.exceptions.RequestException as e:
        error_detail = ""
        if hasattr(e, "response") and e.response is not None:
            try:
                error_detail = e.response.json().get("detail", "")
            except Exception:
                error_detail = e.response.text
        yield {
            "type": "error",
            "error": error_detail or f"Failed to upload documents via stream to {url}: {e}"
        }

def stream_chat(
    query: str,
    session_id: str = "default_session",
    username: str = "default_user",
    base_url: Optional[str] = None
) -> Generator[Dict[str, Any], None, None]:
    """
    Stream agent tokens, intermediate status, and final citations from FastAPI /chat/stream.
    Yields parsed event dictionaries:
      - {"type": "status", "node": "..."}
      - {"type": "token", "content": "..."}
      - {"type": "final", "answer": "...", "sources": [...], "claim_analysis": {...}, "metadata": {...}}
    """
    url = (base_url or get_backend_url()).rstrip("/")
    payload = {"query": query, "session_id": session_id, "username": username}

    try:
        with requests.post(
            f"{url}/chat/stream",
            json=payload,
            stream=True,
            timeout=180.0
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines(decode_unicode=True):
                if not line:
                    continue
                if line.startswith("data: "):
                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        event = json.loads(data_str)
                        yield event
                    except json.JSONDecodeError:
                        continue
    except requests.exceptions.RequestException as e:
        error_detail = ""
        if hasattr(e, "response") and e.response is not None:
            try:
                error_detail = e.response.json().get("detail", "")
            except Exception:
                error_detail = e.response.text
        yield {
            "type": "error",
            "error": error_detail or f"Failed to communicate with FastAPI backend at {url}: {e}"
        }

def fetch_user_sessions(
    username: str,
    base_url: Optional[str] = None
) -> Dict[str, Any]:
    """Fetch stored conversation sessions for a given user from FastAPI backend / Upstash Redis."""
    url = (base_url or get_backend_url()).rstrip("/")
    try:
        resp = requests.get(
            f"{url}/user/{username}/sessions",
            timeout=5.0
        )
        if resp.status_code == 200:
            return resp.json().get("sessions", {})
    except Exception as e:
        logger.debug(f"Failed to fetch sessions for user {username}: {e}")
    return {}

def save_user_sessions_to_backend(
    username: str,
    sessions: Dict[str, Any],
    base_url: Optional[str] = None
) -> bool:
    """Save conversation sessions dictionary for a user to FastAPI backend / Upstash Redis."""
    url = (base_url or get_backend_url()).rstrip("/")
    try:
        resp = requests.post(
            f"{url}/user/{username}/sessions",
            json={"sessions": sessions},
            timeout=5.0
        )
        return resp.status_code == 200
    except Exception as e:
        logger.debug(f"Failed to save sessions for user {username}: {e}")
        return False

def delete_session_from_backend(
    username: str,
    session_id: str,
    base_url: Optional[str] = None
) -> bool:
    """Delete a single session and its checkpointer memory from backend / Upstash Redis."""
    url = (base_url or get_backend_url()).rstrip("/")
    try:
        resp = requests.delete(
            f"{url}/user/{username}/session/{session_id}",
            timeout=5.0
        )
        return resp.status_code == 200
    except Exception as e:
        logger.debug(f"Failed to delete session {session_id} for user {username}: {e}")
        return False

def clear_user_history_on_backend(
    username: str,
    base_url: Optional[str] = None
) -> bool:
    """Clear all conversation sessions and checkpointer memory for a user on backend / Upstash Redis."""
    url = (base_url or get_backend_url()).rstrip("/")
    try:
        resp = requests.post(
            f"{url}/user/{username}/clear",
            timeout=5.0
        )
        return resp.status_code == 200
    except Exception as e:
        logger.debug(f"Failed to clear all sessions for user {username}: {e}")
        return False

def clear_session_memory(
    session_id: str,
    username: Optional[str] = None,
    base_url: Optional[str] = None
) -> bool:
    """Clear conversational memory checkpointer on the FastAPI backend."""
    url = (base_url or get_backend_url()).rstrip("/")
    params = {"username": username} if username else {}
    try:
        resp = requests.post(f"{url}/session/{session_id}/clear", params=params, timeout=5.0)
        return resp.status_code == 200
    except Exception as e:
        logger.warning(f"Failed to clear backend memory for {session_id}: {e}")
        return False


def compute_files_hash(files: list) -> str:
    """Compute an MD5 hash of uploaded files including content samples to detect edits of identical size."""
    hasher = hashlib.md5()
    for f in files:
        hasher.update(f.name.encode())
        raw = f.getvalue() if hasattr(f, "getvalue") else (f.read() if hasattr(f, "read") else b"")
        hasher.update(str(len(raw)).encode())
        hasher.update(raw[:4096])
        hasher.update(raw[-4096:])
        if hasattr(f, "seek"):
            f.seek(0)
    return hasher.hexdigest()

def render_pdf_page_image(pdf_bytes: bytes, page_idx: int) -> Optional[bytes]:
    """
    Render a specific page of a PDF into high-resolution PNG image bytes
    using PyMuPDF for visual citation verification.
    """
    if not pdf_bytes:
        return None
    try:
        import pymupdf
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        if page_idx < 0 or page_idx >= len(doc):
            return None
        page = doc[page_idx]
        pix = page.get_pixmap(dpi=140)
        return pix.tobytes("png")
    except Exception as e:
        logger.error(f"Failed to render PDF page {page_idx} to image: {e}")
        return None
