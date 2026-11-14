"""Read-only, in-memory eBay Browse API client used by /api/search for live listings.

No tokens, item responses or thumbnails are written to disk or logs: eBay granted our
Marketplace Account Deletion exemption on the basis that we do not persist eBay data
(docs/EBAY_FEASIBILITY.md). The OAuth token is reused from memory until it expires.
"""

from __future__ import annotations

import base64
import json
import math
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Literal

SCOPE = "https://api.ebay.com/oauth/api_scope"
ENVIRONMENTS = {
    "sandbox": "https://api.sandbox.ebay.com",
    "production": "https://api.ebay.com",
}


# Listing thumbnails are only fetched from eBay's image CDN, never from arbitrary URLs.
IMAGE_HOST_SUFFIX = ".ebayimg.com"
MAX_IMAGE_BYTES = 5 * 1024 * 1024
# Refresh the token this many seconds before eBay says it expires.
TOKEN_EXPIRY_MARGIN = 60


class EbayAPIError(RuntimeError):
    """eBay authentication, networking, or response failure (no secrets included).

    ``status_code`` is the HTTP status when eBay answered with an error (e.g. 429 for
    rate limiting), or None for connection failures and malformed responses.
    """

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


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
        self._token: str | None = None
        self._token_expires_at = 0.0
        self._token_lock = threading.Lock()

    def _request_json(self, request: urllib.request.Request, operation: str) -> dict[str, Any]:
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as exc:
            # Never surface request headers, bearer token, or raw response bodies.
            raise EbayAPIError(f"{operation} failed (HTTP {exc.code})", exc.code) from None
        except (urllib.error.URLError, TimeoutError):
            raise EbayAPIError(f"{operation} connection failed") from None
        except (UnicodeError, json.JSONDecodeError):
            raise EbayAPIError(f"{operation} returned invalid JSON") from None
        if not isinstance(payload, dict):
            raise EbayAPIError(f"{operation} returned an unexpected response")
        return payload

    def _application_token(self) -> str:
        """Return a cached application token, fetching a new one shortly before expiry."""
        with self._token_lock:
            if self._token is None or time.monotonic() >= self._token_expires_at:
                self._token, lifetime = self._fetch_application_token()
                self._token_expires_at = time.monotonic() + max(
                    lifetime - TOKEN_EXPIRY_MARGIN, 0
                )
            return self._token

    def _fetch_application_token(self) -> tuple[str, float]:
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
        lifetime = payload.get("expires_in")
        if not isinstance(lifetime, int | float) or isinstance(lifetime, bool):
            lifetime = 0  # unknown lifetime: don't reuse the token
        return token, float(lifetime)

    def search(
        self, query: str, *, limit: int = 5, used_only: bool = True
    ) -> list[dict[str, Any]]:
        """Search listings in memory, without storing response data.

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


def fetch_listing_image(url: str, *, timeout: float = 5.0) -> bytes:
    """Download one listing thumbnail into memory (never to disk).

    Only HTTPS URLs on eBay's image CDN are allowed, so a listing can't make the
    backend fetch arbitrary hosts. Oversized or failed downloads raise EbayAPIError.
    """
    parsed = urllib.parse.urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not host.endswith(IMAGE_HOST_SUFFIX):
        raise EbayAPIError("Listing image is not hosted on eBay")
    request = urllib.request.Request(url, headers={"Accept": "image/*"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = response.read(MAX_IMAGE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise EbayAPIError(f"Listing image failed (HTTP {exc.code})", exc.code) from None
    except (urllib.error.URLError, TimeoutError):
        raise EbayAPIError("Listing image connection failed") from None
    if len(data) > MAX_IMAGE_BYTES:
        raise EbayAPIError("Listing image is too large")
    return data
