"""Short-lived, in-memory query cache: query_id -> the upload's embedding (S2-1).

/api/extract stores the embedding here so /api/search can reuse it without the photo
being sent again. Memory only; nothing is written to disk (sprint plan §4.2).
"""

from __future__ import annotations

import threading
import time
import uuid
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

import numpy as np

from backend.app.config import get_settings

EmbeddingKind = Literal["image", "text"]


@dataclass(frozen=True)
class CachedQuery:
    embedding: np.ndarray
    # "text" when there was no photo: the embedding came from the description, so search
    # must not treat it as an image embedding.
    kind: EmbeddingKind
    created_at: float


class QueryCache:
    """Thread-safe TTL cache with a size cap; the oldest entry is evicted first."""

    def __init__(
        self, ttl_seconds: float, max_entries: int, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._ttl = ttl_seconds
        self._max_entries = max_entries
        self._clock = clock
        self._entries: OrderedDict[str, CachedQuery] = OrderedDict()
        self._lock = threading.Lock()

    def put(self, embedding: np.ndarray, kind: EmbeddingKind) -> str:
        query_id = uuid.uuid4().hex
        with self._lock:
            self._drop_expired()
            self._entries[query_id] = CachedQuery(embedding, kind, self._clock())
            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)
        return query_id

    def get(self, query_id: str) -> CachedQuery | None:
        with self._lock:
            self._drop_expired()
            return self._entries.get(query_id)

    def __len__(self) -> int:
        with self._lock:
            self._drop_expired()
            return len(self._entries)

    def _drop_expired(self) -> None:
        # Entries are stored in insertion order, so expired ones are always at the front.
        cutoff = self._clock() - self._ttl
        while self._entries:
            oldest = next(iter(self._entries.values()))
            if oldest.created_at > cutoff:
                break
            self._entries.popitem(last=False)


@lru_cache(maxsize=1)
def get_query_cache() -> QueryCache:
    settings = get_settings()
    return QueryCache(settings.query_cache_ttl_seconds, settings.query_cache_max_entries)
