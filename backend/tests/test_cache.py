"""Unit tests for the in-memory query cache (S2-1)."""

from __future__ import annotations

import numpy as np

from backend.app.cache import QueryCache


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _vector(value: float) -> np.ndarray:
    return np.full(4, value, dtype=np.float32)


def test_put_then_get_returns_embedding_and_kind():
    cache = QueryCache(ttl_seconds=60, max_entries=10, clock=FakeClock())
    query_id = cache.put(_vector(1.0), "image")

    entry = cache.get(query_id)
    assert entry is not None
    assert entry.kind == "image"
    np.testing.assert_array_equal(entry.embedding, _vector(1.0))


def test_each_put_gets_a_new_query_id():
    cache = QueryCache(ttl_seconds=60, max_entries=10, clock=FakeClock())
    assert cache.put(_vector(1.0), "image") != cache.put(_vector(1.0), "image")


def test_unknown_query_id_returns_none():
    cache = QueryCache(ttl_seconds=60, max_entries=10, clock=FakeClock())
    assert cache.get("does-not-exist") is None


def test_entries_expire_after_ttl():
    clock = FakeClock()
    cache = QueryCache(ttl_seconds=60, max_entries=10, clock=clock)
    query_id = cache.put(_vector(1.0), "text")

    clock.now = 59.0
    assert cache.get(query_id) is not None
    clock.now = 60.0
    assert cache.get(query_id) is None
    assert len(cache) == 0


def test_oldest_entry_is_evicted_at_the_cap():
    cache = QueryCache(ttl_seconds=60, max_entries=2, clock=FakeClock())
    first = cache.put(_vector(1.0), "image")
    second = cache.put(_vector(2.0), "image")
    third = cache.put(_vector(3.0), "text")

    assert cache.get(first) is None
    assert cache.get(second) is not None
    assert cache.get(third) is not None
    assert len(cache) == 2
