# ============================================================
# database/redis_cache.py — Redis Cache with In-Memory Fallback
# ============================================================
# Tries to connect to Redis. If unavailable, falls back to an
# in-process LRU cache. The interface is identical either way.
# ============================================================

from __future__ import annotations

import hashlib
import json
import time
from collections import OrderedDict
from typing import Any, Optional

from backend.config import settings
from utils.logger import logger

__all__ = ["get_cache", "CacheProtocol"]


# ------------------------------------------------------------------
# Type protocol so callers can type-hint either implementation
# ------------------------------------------------------------------
class CacheProtocol:
    def get(self, key: str) -> Optional[Any]: ...
    def set(self, key: str, value: Any, ttl: int = 3600) -> None: ...
    def delete(self, key: str) -> bool: ...
    def exists(self, key: str) -> bool: ...
    def make_key(self, *parts: str) -> str: ...
    def ping(self) -> bool: ...


# ------------------------------------------------------------------
# Redis-backed cache
# ------------------------------------------------------------------
class RedisCache(CacheProtocol):
    """Redis cache implementation."""

    def __init__(self, redis_url: str):
        import redis  # type: ignore

        self._redis = redis.Redis.from_url(
            redis_url, decode_responses=True, socket_connect_timeout=3
        )
        self._redis.ping()  # raises if unreachable
        logger.event("cache_init", backend="redis", url=redis_url)

    def get(self, key: str) -> Optional[Any]:
        raw = self._redis.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        self._redis.setex(key, ttl, json.dumps(value, default=str))

    def delete(self, key: str) -> bool:
        return bool(self._redis.delete(key))

    def exists(self, key: str) -> bool:
        return bool(self._redis.exists(key))

    def make_key(self, *parts: str) -> str:
        raw = "|".join(parts)
        digest = hashlib.sha256(raw.encode()).hexdigest()
        return f"resume:{digest}"

    def ping(self) -> bool:
        try:
            return self._redis.ping()
        except Exception:
            return False


# ------------------------------------------------------------------
# In-memory LRU fallback
# ------------------------------------------------------------------
class MemoryCache(CacheProtocol):
    """Thread-safe-ish in-memory LRU cache (fallback when Redis is down)."""

    def __init__(self, max_size: int = 500):
        self._store: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._max_size = max_size
        logger.event("cache_init", backend="memory", max_size=max_size)

    def _cleanup_expired(self) -> None:
        now = time.time()
        expired = [k for k, (_, exp) in self._store.items() if exp <= now]
        for k in expired:
            self._store.pop(k, None)

    def get(self, key: str) -> Optional[Any]:
        self._cleanup_expired()
        entry = self._store.get(key)
        if entry is None:
            return None
        value, _exp = entry
        self._store.move_to_end(key)  # LRU touch
        return value

    def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        self._store[key] = (value, time.time() + ttl)
        self._store.move_to_end(key)
        while len(self._store) > self._max_size:
            self._store.popitem(last=False)

    def delete(self, key: str) -> bool:
        return self._store.pop(key, None) is not None

    def exists(self, key: str) -> bool:
        self._cleanup_expired()
        return key in self._store

    def make_key(self, *parts: str) -> str:
        raw = "|".join(parts)
        digest = hashlib.sha256(raw.encode()).hexdigest()
        return f"resume:{digest}"

    def ping(self) -> bool:
        return True


# ------------------------------------------------------------------
# Singleton accessor
# ------------------------------------------------------------------
_cache_instance: Optional[CacheProtocol] = None


def get_cache() -> CacheProtocol:
    """Return the cache singleton (Redis if available, else memory)."""
    global _cache_instance
    if _cache_instance is not None:
        return _cache_instance

    if not settings.cache_enabled:
        _cache_instance = MemoryCache()
        return _cache_instance

    # Try Redis first
    try:
        _cache_instance = RedisCache(settings.redis_url)
    except Exception as exc:
        logger.event(
            "cache_fallback",
            level=30,
            reason=f"Redis unavailable: {exc}",
        )
        _cache_instance = MemoryCache()

    return _cache_instance
