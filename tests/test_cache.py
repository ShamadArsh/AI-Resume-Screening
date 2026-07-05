# ============================================================
# tests/test_cache.py — Unit tests for Redis/Memory cache
# ============================================================

import time

from database.redis_cache import MemoryCache


class TestMemoryCache:
    def test_set_and_get(self):
        cache = MemoryCache()
        cache.set("key1", {"data": "value"})
        assert cache.get("key1") == {"data": "value"}

    def test_get_missing(self):
        cache = MemoryCache()
        assert cache.get("nonexistent") is None

    def test_delete(self):
        cache = MemoryCache()
        cache.set("key1", "val")
        assert cache.delete("key1") is True
        assert cache.get("key1") is None

    def test_exists(self):
        cache = MemoryCache()
        cache.set("key1", "val")
        assert cache.exists("key1") is True
        assert cache.exists("key2") is False

    def test_ttl_expiry(self):
        cache = MemoryCache()
        cache.set("key1", "val", ttl=1)
        assert cache.get("key1") == "val"
        time.sleep(1.5)
        assert cache.get("key1") is None

    def test_lru_eviction(self):
        cache = MemoryCache(max_size=3)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.set("d", 4)  # should evict "a"
        assert cache.get("a") is None
        assert cache.get("d") == 4

    def test_make_key_consistent(self):
        cache = MemoryCache()
        k1 = cache.make_key("resume_parse", "same text")
        k2 = cache.make_key("resume_parse", "same text")
        assert k1 == k2

    def test_make_key_different(self):
        cache = MemoryCache()
        k1 = cache.make_key("resume_parse", "text A")
        k2 = cache.make_key("resume_parse", "text B")
        assert k1 != k2

    def test_ping(self):
        cache = MemoryCache()
        assert cache.ping() is True
