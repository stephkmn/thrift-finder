"""Contract tests for SearchResult: price and listing_url are required keys with nullable values."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.app.schemas import SearchResponse, SearchResult

EBAY_RESULT = {
    "id": "ebay-1",
    "title": "Black denim jacket",
    "price": 45.0,
    "image_url": "https://example.com/1.jpg",
    "listing_url": "https://example.com/listing/1",
    "source": "ebay",
    "match_score": 87.5,
}

LOCAL_RESULT = {
    **EBAY_RESULT,
    "id": "local-1",
    "price": None,
    "listing_url": None,
    "source": "local",
}


def test_search_result_accepts_a_priced_listing():
    parsed = SearchResult.model_validate(EBAY_RESULT)
    assert parsed.price == 45.0
    assert parsed.listing_url == "https://example.com/listing/1"


def test_search_result_accepts_null_price_and_listing_url():
    parsed = SearchResult.model_validate(LOCAL_RESULT)
    assert parsed.price is None
    assert parsed.listing_url is None
    # Nulls survive serialization as explicit keys, matching the TypeScript contract.
    dumped = parsed.model_dump()
    assert dumped["price"] is None
    assert dumped["listing_url"] is None


@pytest.mark.parametrize("key", ["price", "listing_url"])
def test_search_result_rejects_a_missing_nullable_key(key):
    payload = {k: v for k, v in LOCAL_RESULT.items() if k != key}
    with pytest.raises(ValidationError, match=key):
        SearchResult.model_validate(payload)


def test_search_result_still_requires_image_url():
    payload = {k: v for k, v in LOCAL_RESULT.items() if k != "image_url"}
    with pytest.raises(ValidationError, match="image_url"):
        SearchResult.model_validate(payload)
    with pytest.raises(ValidationError, match="image_url"):
        SearchResult.model_validate({**LOCAL_RESULT, "image_url": None})


def test_search_response_mixes_sources():
    response = SearchResponse.model_validate({"results": [EBAY_RESULT, LOCAL_RESULT]})
    assert [r.source for r in response.results] == ["ebay", "local"]
