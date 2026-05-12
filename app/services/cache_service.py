import json
import time
import logging
from typing import Any, Optional
from app.core.database import engine
from app.models.cache import SearchCache
from sqlmodel import Session, select, delete

logger = logging.getLogger(__name__)

class CacheService:
    def __init__(self):
        # SQLModel handles table creation via init_db() in main.py
        pass

    def get(self, key: str) -> Optional[Any]:
        try:
            with Session(engine) as session:
                statement = select(SearchCache).where(SearchCache.key == key)
                row = session.exec(statement).first()
                if row:
                    if row.expires_at > time.time():
                        return json.loads(row.value)
                    else:
                        # Expired
                        session.delete(row)
                        session.commit()
        except Exception as e:
            logger.error(f"Cache get error: {e}")
        return None

    def set(self, key: str, value: Any, ttl: int = 86400):
        """Set cache value with TTL in seconds (default 24h)."""
        try:
            value_json = json.dumps(value)
            expires_at = time.time() + ttl
            with Session(engine) as session:
                # SQLModel Insert or Replace equivalent
                existing = session.get(SearchCache, key)
                if existing:
                    existing.value = value_json
                    existing.expires_at = expires_at
                    session.add(existing)
                else:
                    new_cache = SearchCache(key=key, value=value_json, expires_at=expires_at)
                    session.add(new_cache)
                session.commit()
        except Exception as e:
            logger.error(f"Cache set error: {e}")

    def clear(self):
        try:
            with Session(engine) as session:
                session.exec(delete(SearchCache))
                session.commit()
        except Exception as e:
            logger.error(f"Cache clear error: {e}")

# Global singleton
cache_service = CacheService()
