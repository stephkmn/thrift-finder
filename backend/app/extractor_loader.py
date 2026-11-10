"""Loads the attribute model once per process, shared by startup preload and /api/extract.

`get_extractor` (backend/app/ml/attributes.py) is an `lru_cache`, which neither stops two
racing first requests from both loading the ~600 MB model nor remembers a failure, so a
broken setup (torch missing, download error) would retry the full load on every upload.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from functools import lru_cache
from typing import Generic, TypeVar

from backend.app.ml.attributes import get_extractor

T = TypeVar("T")

# Errors that mean "the model can't be used right now"; /api/extract maps them to 503.
LOAD_ERRORS = (ImportError, RuntimeError, OSError)
# After a failed load, answer 503 straight away for this long before trying again.
RETRY_AFTER_SECONDS = 30.0


class OnceLoader(Generic[T]):
    """Calls `load` at most once at a time, caches the result, and backs off after a failure."""

    def __init__(
        self,
        load: Callable[[], T],
        retry_after_seconds: float = RETRY_AFTER_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._load = load
        self._retry_after = retry_after_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._value: T | None = None
        self._failed_at: float | None = None
        self._failure: BaseException | None = None

    def __call__(self) -> T:
        if self._value is not None:
            return self._value
        with self._lock:
            if self._value is not None:  # another thread finished loading while we waited
                return self._value
            if self._failed_at is not None and self._clock() - self._failed_at < self._retry_after:
                raise RuntimeError("The model failed to load recently; not retrying yet.") from (
                    self._failure
                )
            try:
                self._value = self._load()
            except LOAD_ERRORS as exc:
                self._failed_at, self._failure = self._clock(), exc
                raise
            self._failed_at = self._failure = None
            return self._value


@lru_cache(maxsize=1)
def get_extractor_once() -> OnceLoader:
    """The process-wide loader for the configured attribute model."""
    return OnceLoader(get_extractor)
