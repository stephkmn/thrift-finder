"""Read-only, in-memory eBay Browse API client for feasibility testing.

No tokens or item responses are written to disk. This module is intentionally
not connected to /api/search until the backend owner reviews integration.
"""

from __future__ import annotations

import base64
import json
import math
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Literal

SCOPE = "https://api.ebay.com/oauth/api_scope"
ENVIRONMENTS = {
    "sandbox": "https://api.sandbox.ebay.com",
    "production": "https://api.ebay.com",
}


class EbayAPIError(RuntimeError):
    """eBay authentication, networking, or response failure (no secrets included)."""


class EbayBrowseClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        *,
        environment: Literal["sandbox", "production"] = "production",
        timeout: int = 20,
    ) -> None:
        if environment not in ENVIRONMENTS:
            raise ValueError("Environment must be 'sandbox' or 'production'.")
        if not client_id or not client_secret:
            raise ValueError("Client ID and secret are required.")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self._client_id = client_id
        self._client_secret = client_secret
        self._base_url = ENVIRONMENTS[environment]
        self._timeout = timeout

    def _request_json(self, request: urllib.request.Request, operation: str) -> dict[str, Any]:
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as exc:
            # Never surface request headers, bearer token, or raw response bodies.
            raise EbayAPIError(f"{operation} failed (HTTP {exc.code})") from None
        except (urllib.error.URLError, TimeoutError):
            raise EbayAPIError(f"{operation} connection failed") from None
        except (UnicodeError, json.JSONDecodeError):
            raise EbayAPIError(f"{operation} returned invalid JSON") from None
        if not isinstance(payload, dict):
            raise EbayAPIError(f"{operation} returned an unexpected response")
        return payload

    def _application_token(self) -> str:
        raw = f"{self._client_id}:{self._client_secret}".encode()
        encoded = base64.b64encode(raw).decode("ascii")
        data = urllib.parse.urlencode(
            {"grant_type": "client_credentials", "scope": SCOPE}
        ).encode("ascii")
        request = urllib.request.Request(
            f"{self._base_url}/identity/v1/oauth2/token",
            data=data,
            headers={
                "Authorization": f"Basic {encoded}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )
        payload = self._request_json(request, "OAuth")
        token = payload.get("access_token")
        if not isinstance(token, str) or not token:
            raise EbayAPIError("OAuth did not return an access token")
        return token

    def search(
        self, query: str, *, limit: int = 5, used_only: bool = True
    ) -> list[dict[str, Any]]:
        """Search listings without storing response data or caching tokens.

        Results intentionally omit match_score: eBay keyword search does not provide
        a FashionCLIP similarity value. The backend must supply that when integrating.
        """
        query = query.strip()
        if not query:
            raise ValueError("Search query cannot be empty")
        if not 1 <= limit <= 20:
            raise ValueError("limit must be between 1 and 20")

        params: dict[str, str | int] = {"q": query, "limit": limit}
        if used_only:
            params["filter"] = "conditions:{USED}"
        url = f"{self._base_url}/buy/browse/v1/item_summary/search?"
        url += urllib.parse.urlencode(params)
        request = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {self._application_token()}",
                "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
            },
        )
        payload = self._request_json(request, "Browse search")
        items = payload.get("itemSummaries", [])
        if not isinstance(items, list):
            raise EbayAPIError("Browse search returned unexpected items")
        return [self._normalize(item) for item in items if isinstance(item, dict)]

    @staticmethod
    def _normalize(item: dict[str, Any]) -> dict[str, Any]:
        price = item.get("price")
        if not isinstance(price, dict):
            price = {}
        image = item.get("image")
        if not isinstance(image, dict):
            image = {}
        amount = price.get("value")
        try:
            numeric_price = float(amount) if amount is not None else None
            if numeric_price is not None and (
                not math.isfinite(numeric_price) or numeric_price < 0
            ):
                numeric_price = None
        except (ValueError, TypeError, OverflowError):
            numeric_price = None
        return {
            "id": item.get("itemId"),
            "title": item.get("title"),
            "price": numeric_price,
            "currency": price.get("currency"),
            "condition": item.get("condition"),
            "image_url": image.get("imageUrl"),
            "listing_url": item.get("itemWebUrl"),
            "source": "ebay",
        }
