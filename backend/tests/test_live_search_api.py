"""S3-7 API tests: live eBay results through /api/search, and fallback to local data."""

from __future__ import annotations

import logging

import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.app.api import search as search_api
from backend.app.cache import QueryCache, get_query_cache
from backend.app.data.ebay_client import EbayAPIError
from backend.app.main import app
from backend.app.ml.rerank import Match

ATTRS = {"category": "jacket", "color": "brown", "fabric": "leather", "fit": "regular fit"}
LOCAL = Match({"id": "secondhand-0001", "title": "Brown Jacket"}, 70.0)
EBAY = Match(
    {
        "id": "v1|123|0",
        "title": "Vintage brown leather jacket",
        "price": 54.99,
        "currency": "USD",
        "image_url": "https://i.ebayimg.com/images/g/abc/s-l225.jpg",
        "listing_url": "https://www.ebay.com/itm/123",
        "source": "ebay",
    },
    88.4,
)


@pytest.fixture
def api():
    cache = QueryCache(ttl_seconds=60, max_entries=10)
    calls = {"local": 0, "live": 0}

    def local(*_args):
        calls["local"] += 1
        return [LOCAL]

    def use_live(behaviour):
        def live(*_args):
            calls["live"] += 1
            if isinstance(behaviour, Exception):
                raise behaviour
            return behaviour

        app.dependency_overrides[search_api.get_live_search] = lambda: live

    app.dependency_overrides[get_query_cache] = lambda: cache
    app.dependency_overrides[search_api.get_search_runner] = lambda: local
    try:
        yield TestClient(app), cache, calls, use_live
    finally:
        app.dependency_overrides.clear()


def _search(client, cache):
    query_id = cache.put(np.ones(2), "image")
    body = {"query_id": query_id, "original_attributes": ATTRS, "edited_attributes": ATTRS}
    return client.post("/api/search", json=body)


def test_live_ebay_results_have_prices_and_purchase_links(api):
    client, cache, calls, use_live = api
    use_live([EBAY])
    response = _search(client, cache)
    assert response.status_code == 200
    assert response.json() == {
        "results": [
            {
                "id": "v1|123|0",
                "title": "Vintage brown leather jacket",
                "price": 54.99,
                "image_url": "https://i.ebayimg.com/images/g/abc/s-l225.jpg",
                "listing_url": "https://www.ebay.com/itm/123",
                "source": "ebay",
                "match_score": 88.4,
            }
        ]
    }
    assert calls == {"local": 0, "live": 1}


def test_non_usd_price_is_not_shown_as_dollars(api):
    client, cache, _, use_live = api
    listing = {**EBAY.listing, "currency": "GBP"}
    use_live([Match(listing, 80.0)])
    result = _search(client, cache).json()["results"][0]
    assert result["price"] is None
    assert result["listing_url"] == "https://www.ebay.com/itm/123"


@pytest.mark.parametrize(
    "behaviour,reason",
    [
        (EbayAPIError("Browse search failed (HTTP 429)", 429), "rate_limited"),
        (EbayAPIError("Browse search failed (HTTP 500)", 500), "unavailable"),
        (EbayAPIError("OAuth connection failed"), "unavailable"),
        ([], "no_live_results"),
    ],
)
def test_ebay_failures_fall_back_to_local(api, caplog, behaviour, reason):
    client, cache, calls, use_live = api
    use_live(behaviour)
    with caplog.at_level(logging.WARNING):
        response = _search(client, cache)
    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["source"] == "local"
    assert result["price"] is None and result["listing_url"] is None
    assert result["image_url"] == "/api/local-images/secondhand-0001"
    assert calls == {"local": 1, "live": 1}
    assert reason in caplog.text


def test_unexpected_live_error_is_not_hidden_but_stays_user_safe(api):
    client, cache, calls, use_live = api
    use_live(ValueError("bug with private detail"))
    response = _search(client, cache)
    assert response.status_code == 503
    assert "private detail" not in response.text
    assert calls["local"] == 0


def test_local_failure_after_ebay_failure_returns_503(api):
    client, cache, _, use_live = api
    use_live(EbayAPIError("Browse search failed (HTTP 429)", 429))

    def broken(*_args):
        raise FileNotFoundError("data/embeddings.npz")

    app.dependency_overrides[search_api.get_search_runner] = lambda: broken
    assert _search(client, cache).status_code == 503


def test_live_search_disabled_for_local_data_source(monkeypatch):
    monkeypatch.setenv("DATA_SOURCE", "local")
    monkeypatch.setenv("EBAY_CLIENT_ID", "id")
    monkeypatch.setenv("EBAY_CLIENT_SECRET", "secret")
    assert search_api.get_live_search() is None


def test_live_search_disabled_without_credentials(monkeypatch):
    monkeypatch.setenv("DATA_SOURCE", "ebay")
    monkeypatch.setenv("EBAY_CLIENT_ID", "")
    monkeypatch.setenv("EBAY_CLIENT_SECRET", "")
    assert search_api.get_live_search() is None


def test_live_search_enabled_with_ebay_source_and_credentials(monkeypatch):
    monkeypatch.setenv("DATA_SOURCE", "ebay")
    monkeypatch.setenv("EBAY_CLIENT_ID", "test-id")
    monkeypatch.setenv("EBAY_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("EBAY_ENVIRONMENT", "sandbox")
    assert callable(search_api.get_live_search())
    client = search_api._ebay_client("test-id", "test-secret", "sandbox")
    assert client is search_api._ebay_client("test-id", "test-secret", "sandbox")


def test_error_classification():
    assert search_api.classify_ebay_error(EbayAPIError("x", 429)) == "rate_limited"
    assert search_api.classify_ebay_error(EbayAPIError("x", 503)) == "unavailable"
    assert search_api.classify_ebay_error(EbayAPIError("x")) == "unavailable"
    assert search_api.classify_ebay_error(RuntimeError("x")) is None
