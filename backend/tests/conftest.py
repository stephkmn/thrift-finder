"""Shared test setup."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _never_call_live_ebay(monkeypatch):
    """Env vars beat a developer's .env, so tests never hit eBay with real credentials."""
    monkeypatch.setenv("DATA_SOURCE", "local")
