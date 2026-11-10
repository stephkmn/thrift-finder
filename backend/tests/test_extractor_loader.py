"""Unit tests for OnceLoader: one load under concurrency, and a back-off after failures."""

from __future__ import annotations

import threading
import time

import pytest

from backend.app.extractor_loader import OnceLoader


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_loads_once_and_caches_the_result():
    calls = []
    loader = OnceLoader(lambda: calls.append(1) or "model")
    assert loader() == "model"
    assert loader() == "model"
    assert calls == [1]


def test_concurrent_first_calls_load_only_once():
    calls = []
    started = threading.Event()

    def slow_load():
        calls.append(1)
        started.set()
        time.sleep(0.05)
        return "model"

    loader = OnceLoader(slow_load)
    results = []
    threads = [threading.Thread(target=lambda: results.append(loader())) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert calls == [1]
    assert results == ["model"] * 8


def test_failure_is_remembered_then_retried_after_the_window():
    clock = FakeClock()
    attempts = []

    def load():
        attempts.append(clock.now)
        if len(attempts) == 1:
            raise ImportError("No module named 'torch'")
        return "model"

    loader = OnceLoader(load, retry_after_seconds=30, clock=clock)
    with pytest.raises(ImportError):
        loader()

    clock.now = 10
    with pytest.raises(RuntimeError, match="failed to load recently"):
        loader()
    assert attempts == [0]  # no second load inside the back-off window

    clock.now = 31
    assert loader() == "model"
    assert attempts == [0, 31]


def test_unexpected_errors_are_not_swallowed_or_remembered():
    attempts = []

    def load():
        attempts.append(1)
        raise ValueError("bug")

    loader = OnceLoader(load)
    for _ in range(2):
        with pytest.raises(ValueError):
            loader()
    assert attempts == [1, 1]
