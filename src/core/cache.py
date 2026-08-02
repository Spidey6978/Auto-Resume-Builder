import os
import json
import sqlite3
import hashlib
from datetime import datetime, timezone
from typing import Any, Optional, Tuple, Dict


class CacheManager:
    """
    SQLite-backed key-value cache manager.
    Caches arbitrary JSON-serializable payloads and optional ETag headers
    indexed by SHA256 hashes of input keys.
    """

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            # Default to .cache/build_cache.db relative to the project root
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            cache_dir = os.path.join(base_dir, ".cache")
            os.makedirs(cache_dir, exist_ok=True)
            db_path = os.path.join(cache_dir, "build_cache.db")

        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        """Creates or updates the cache table if it doesn't already exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS cache (
                    namespace TEXT NOT NULL,
                    key_hash TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    etag TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (namespace, key_hash)
                )
                """
            )
            # Ensure etag column exists for backward compatibility if database was created earlier
            cursor.execute("PRAGMA table_info(cache)")
            columns = [column[1] for column in cursor.fetchall()]
            if "etag" not in columns:
                cursor.execute("ALTER TABLE cache ADD COLUMN etag TEXT")

            conn.commit()

    @staticmethod
    def hash_key(raw_key: str) -> str:
        """Computes a SHA256 hash string for the given raw key."""
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    def get(self, namespace: str, raw_key: str) -> Optional[Any]:
        """
        Retrieves a cached payload value for the given namespace and raw_key.
        Returns None if not found or if decoding fails.
        """
        result = self.get_with_meta(namespace, raw_key)
        if result:
            return result[0]
        return None

    def get_with_meta(self, namespace: str, raw_key: str) -> Optional[Tuple[Any, Optional[str]]]:
        """
        Retrieves a tuple of (payload, etag) for the given namespace and raw_key.
        Returns None if not found.
        """
        key_hash = self.hash_key(raw_key)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT payload, etag FROM cache WHERE namespace = ? AND key_hash = ?",
                (namespace, key_hash),
            )
            row = cursor.fetchone()
            if row:
                payload_raw, etag = row[0], row[1]
                try:
                    payload = json.loads(payload_raw)
                except json.JSONDecodeError:
                    payload = payload_raw
                return payload, etag
        return None

    def set(self, namespace: str, raw_key: str, payload: Any, etag: Optional[str] = None) -> None:
        """
        Stores a payload and optional ETag in the cache under namespace and raw_key.
        Payload will be serialized to JSON.
        """
        key_hash = self.hash_key(raw_key)
        payload_str = json.dumps(payload) if not isinstance(payload, str) else payload
        now = datetime.now(timezone.utc).isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO cache (namespace, key_hash, payload, etag, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (namespace, key_hash, payload_str, etag, now),
            )
            conn.commit()

    def clear(self, namespace: Optional[str] = None) -> None:
        """Clears cached items. If namespace is provided, only items in that namespace are removed."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if namespace:
                cursor.execute("DELETE FROM cache WHERE namespace = ?", (namespace,))
            else:
                cursor.execute("DELETE FROM cache")
            conn.commit()

    def stats(self) -> Dict[str, int]:
        """Returns entry counts per namespace."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT namespace, COUNT(*) FROM cache GROUP BY namespace")
            rows = cursor.fetchall()
            return {row[0]: row[1] for row in rows}
