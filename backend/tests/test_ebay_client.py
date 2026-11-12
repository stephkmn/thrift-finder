"""Mocked eBay integration tests: never call real services or use real credentials."""

from __future__ import annotations

import io
import json
import urllib.error
import urllib.parse
import urllib.request

import pytest

from backend.app.data.ebay_client import EbayAPIError, EbayBrowseClient


class Response(io.BytesIO):
    def __init__(self, payload):
        super().__init__(json.dumps(payload).encode("utf-8"))

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


@pytest.fixture
def api(monkeypatch):
    seen = []
    payloads = [
        {"access_token": "test-token", "expires_in": 7200},
        {
            "itemSummaries": [
                {
                    "itemId": "v1|1|0",
                    "title": "Pre-owned brown jacket",
                    "price": {"value": "49.99", "currency": "USD"},
                    "condition": "Pre-owned - Good",
                    "image": {"imageUrl": "https://example.com/img.jpg"},
                    "itemWebUrl": "https://example.com/item",
                }
            ]
        },
    ]

    def fake_open(request, *, timeout):
        seen.append((request, timeout))
        return Response(payloads[len(seen) - 1])

    monkeypatch.setattr(urllib.request, "urlopen", fake_open)
    return seen


def test_used_only_filter_is_url_encoded_and_maps_fields(api):
    client = EbayBrowseClient("client", "secret")
    result = client.search(" brown leather jacket ", limit=5)
    assert len(result) == 1
    assert result[0] == {
        "id": "v1|1|0",
        "title": "Pre-owned brown jacket",
        "price": 49.99,
        "currency": "USD",
        "condition": "Pre-owned - Good",
        "image_url": "https://example.com/img.jpg",
        "listing_url": "https://example.com/item",
        "source": "ebay",
    }
    request, timeout = api[1]
    parsed = urllib.parse.parse_qs(urllib.parse.urlparse(request.full_url).query)
    assert parsed["q"] == ["brown leather jacket"]
    assert parsed["limit"] == ["5"]
    assert parsed["filter"] == ["conditions:{USED}"]
    assert request.get_header("Authorization") == "Bearer test-token"
    assert timeout == 20


def test_client_credentials_and_oauth_scope(api):
    EbayBrowseClient("client", "secret").search("coat")
    request, _ = api[0]
    assert request.full_url == "https://api.ebay.com/identity/v1/oauth2/token"
    assert request.get_method() == "POST"
    assert request.get_header("Authorization").startswith("Basic ")
    assert urllib.parse.parse_qs(request.data.decode())["scope"] == [
        "https://api.ebay.com/oauth/api_scope"
    ]


def test_sandbox_environment_and_all_conditions(api):
    EbayBrowseClient("id", "secret", environment="sandbox").search("coat", used_only=False)
    assert api[0][0].full_url.startswith("https://api.sandbox.ebay.com/")
    assert api[1][0].full_url.startswith("https://api.sandbox.ebay.com/")
    assert "filter" not in urllib.parse.parse_qs(
        urllib.parse.urlparse(api[1][0].full_url).query
    )


@pytest.mark.parametrize("query,limit", [("", 5), ("   ", 5), ("coat", 0), ("coat", 21)])
def test_invalid_search_rejected_without_network(query, limit, monkeypatch):
    def fail(*_args, **_kwargs):
        raise AssertionError("Network should not be called")

    monkeypatch.setattr(urllib.request, "urlopen", fail)
    with pytest.raises(ValueError):
        EbayBrowseClient("id", "secret").search(query, limit=limit)


def test_missing_optional_listing_fields_do_not_get_fabricated():
    result = EbayBrowseClient._normalize({"itemId": "1", "title": "Jacket"})
    assert result["price"] is None
    assert result["image_url"] is None
    assert result["listing_url"] is None
    assert "match_score" not in result


def test_ebay_http_error_does_not_echo_credentials(monkeypatch):
    def fail(_request, *, timeout):
        raise urllib.error.HTTPError("https://example.com", 403, "Forbidden", None, None)

    monkeypatch.setattr(urllib.request, "urlopen", fail)
    with pytest.raises(EbayAPIError, match=r"OAuth failed \(HTTP 403\)") as err:
        EbayBrowseClient("private-id", "private-secret").search("coat")
    assert "private-secret" not in str(err.value)


def test_missing_access_token_rejected(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", lambda *_a, **_kw: Response({}))
    with pytest.raises(EbayAPIError, match="did not return an access token"):
        EbayBrowseClient("id", "secret").search("coat")


def test_malformed_response_items_rejected(monkeypatch):
    responses = iter([Response({"access_token": "token"}), Response({"itemSummaries": {}})])
    monkeypatch.setattr(urllib.request, "urlopen", lambda *_a, **_kw: next(responses))
    with pytest.raises(EbayAPIError, match="unexpected items"):
        EbayBrowseClient("id", "secret").search("coat")

@pytest.mark.parametrize(
    "value",
    ["NaN", "Infinity", "-Infinity", "-10", "invalid"],
)
def test_normalize_rejects_invalid_prices(value):
    item = {
        "itemId": "test-item",
        "title": "Test Jacket",
        "price": {"value": value, "currency": "USD"},
    }

    result = EbayBrowseClient._normalize(item)

    assert result["price"] is None