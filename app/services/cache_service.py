import sqlite3
import json
import time
import os
from typing import Any, Optional
import logging

logger = logging.getLogger(__name__)

class CacheService:
    def __init__(self, db_path: str = "cache/search_cache.db"):
        self.db_path = db_path
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    expires_at REAL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_expires ON cache(expires_at)")

    def get(self, key: str) -> Optional[Any]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT value, expires_at FROM cache WHERE key = ?", (key,))
                row = cursor.fetchone()
                if row:
                    value_json, expires_at = row
                    if expires_at > time.time():
                        return json.loads(value_json)
                    else:
                        # Expired
                        conn.execute("DELETE FROM cache WHERE key = ?", (key,))
        except Exception as e:
            logger.error(f"Cache get error: {e}")
        return None

    def set(self, key: str, value: Any, ttl: int = 86400):
        """Set cache value with TTL in seconds (default 24h)."""
        try:
            value_json = json.dumps(value)
            expires_at = time.time() + ttl
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO cache (key, value, expires_at) VALUES (?, ?, ?)",
                    (key, value_json, expires_at)
                )
        except Exception as e:
            logger.error(f"Cache set error: {e}")

    def clear(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM cache")
        except Exception as e:
            logger.error(f"Cache clear error: {e}")

# Global singleton
cache_service = CacheService()
