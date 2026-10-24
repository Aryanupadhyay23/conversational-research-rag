"""SQLite-backed registry for the persistent document index."""
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional

from backend.config import DOCUMENTS_DB_PATH

PROCESSING = "processing"
COMPLETED = "completed"
FAILED = "failed"


def calculate_document_hash(pdf_bytes: bytes) -> str:
    """Return the SHA-256 fingerprint of a non-empty uploaded PDF."""
    import hashlib
    if not pdf_bytes:
        raise ValueError("Uploaded PDF is empty.")
    return hashlib.sha256(pdf_bytes).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DocumentRegistry:
    def __init__(self, path: str = DOCUMENTS_DB_PATH):
        self.path = path
        parent = os.path.dirname(os.path.abspath(path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        self.initialize()

    @contextmanager
    def _connection(self):
        connection = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        with self._connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    document_hash TEXT PRIMARY KEY,
                    document_id TEXT UNIQUE NOT NULL,
                    filename TEXT,
                    status TEXT NOT NULL CHECK(status IN ('processing', 'completed', 'failed')),
                    chunk_count INTEGER,
                    embedding_model TEXT,
                    collection_name TEXT,
                    config_signature TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    error_message TEXT
                )
            """)
            # Migration for registries created by early versions of this feature.
            columns = {r[1] for r in conn.execute("PRAGMA table_info(documents)")}
            if "config_signature" not in columns:
                conn.execute("ALTER TABLE documents ADD COLUMN config_signature TEXT")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status)")

    def get(self, document_hash: str) -> Optional[dict]:
        with self._connection() as conn:
            row = conn.execute("SELECT * FROM documents WHERE document_hash = ?", (document_hash,)).fetchone()
            return dict(row) if row else None

    def claim(self, document_hash: str, filename: str, embedding_model: str,
              collection_name: str, config_signature: str, force: bool = False) -> tuple[dict, bool]:
        """Atomically claim a document. Returns (record, should_index)."""
        now = _now()
        with self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM documents WHERE document_hash = ?", (document_hash,)).fetchone()
            if row is None:
                document_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"pdf:{document_hash}"))
                conn.execute("""INSERT INTO documents
                    (document_hash, document_id, filename, status, embedding_model, collection_name,
                     config_signature, created_at, updated_at, error_message)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)""",
                    (document_hash, document_id, filename, PROCESSING, embedding_model,
                     collection_name, config_signature, now, now))
                row = conn.execute("SELECT * FROM documents WHERE document_hash = ?", (document_hash,)).fetchone()
                conn.execute("COMMIT")
                return dict(row), True

            record = dict(row)
            compatible = (record.get("embedding_model") == embedding_model and
                          record.get("collection_name") == collection_name and
                          record.get("config_signature") == config_signature)
            if record["status"] == PROCESSING:
                conn.execute("COMMIT")
                return record, False
            if record["status"] == COMPLETED and compatible and not force:
                conn.execute("COMMIT")
                return record, False

            # Failed records and configuration changes can safely be retried.
            conn.execute("""UPDATE documents SET filename=?, status=?, chunk_count=NULL,
                         embedding_model=?, collection_name=?, config_signature=?, updated_at=?, error_message=NULL
                         WHERE document_hash=?""",
                         (filename, PROCESSING, embedding_model, collection_name, config_signature, now, document_hash))
            row = conn.execute("SELECT * FROM documents WHERE document_hash = ?", (document_hash,)).fetchone()
            conn.execute("COMMIT")
            return dict(row), True

    def set_chunk_count(self, document_hash: str, chunk_count: int) -> None:
        with self._connection() as conn:
            conn.execute("UPDATE documents SET chunk_count=?, updated_at=? WHERE document_hash=?",
                         (chunk_count, _now(), document_hash))

    def complete(self, document_hash: str) -> None:
        with self._connection() as conn:
            conn.execute("UPDATE documents SET status=?, updated_at=?, error_message=NULL WHERE document_hash=?",
                         (COMPLETED, _now(), document_hash))

    def fail(self, document_hash: str, error: Exception | str) -> None:
        with self._connection() as conn:
            conn.execute("UPDATE documents SET status=?, updated_at=?, error_message=? WHERE document_hash=?",
                         (FAILED, _now(), str(error)[:4000], document_hash))


_registry: Optional[DocumentRegistry] = None

def get_document_registry() -> DocumentRegistry:
    global _registry
    if _registry is None:
        _registry = DocumentRegistry()
    return _registry
