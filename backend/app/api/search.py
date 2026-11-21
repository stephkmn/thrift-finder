"""S2-5 / S3-4 / S3-7: resolve cached image/text queries to ranked clothing listings.

With DATA_SOURCE=ebay and credentials set, results are live used eBay listings with real
prices and purchase links, re-ranked by FashionCLIP (backend/app/ml/live_search.py). If
eBay is rate-limited, down, or returns nothing usable, the licensed local index answers
instead (backend/app/data/retrieval_fallback.py). Local items never get invented prices
or purchase links. eBay responses are kept in memory only, never persisted or logged.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from functools import lru_cache, partial
from pathlib import Path
from typing import Annotated, Any, Literal
from urllib.parse import quote

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse

from backend.app.cache import EmbeddingKind, QueryCache, get_query_cache
from backend.app.config import get_settings
from backend.app.data.ebay_client import EbayAPIError, EbayBrowseClient
from backend.app.data.local_dataset import PROJECT_ROOT, load_listings
from backend.app.data.preprocess import DATASET_ID, clean_text, parse_colors
from backend.app.data.retrieval_fallback import FallbackReason, search_with_local_fallback
from backend.app.ml.encoder import get_encoder
from backend.app.ml.evaluation import edit_satisfied, type_matches
from backend.app.ml.index import listing_labels
from backend.app.ml.live_search import search_live_listings
from backend.app.ml.rerank import Match, search_listings
from backend.app.schemas import (
    AttributeComparison,
    Attributes,
    DatasetLabels,
    ItemCredit,
    ItemDetails,
    SearchRequest,
    SearchResponse,
    SearchResult,
)

logger = logging.getLogger(__name__)
router = APIRouter()

SearchRunner = Callable[
    [np.ndarray, EmbeddingKind, Attributes, Attributes], list[Match]
]
LOCAL_IMAGE_DIR = (PROJECT_ROOT / "data" / "images").resolve()


def get_search_runner() -> SearchRunner:
    """Overrideable model/index entrypoint; CI can test without loading FashionCLIP."""
    return search_listings


@lru_cache(maxsize=2)
def _ebay_client(
    client_id: str, client_secret: str, environment: Literal["sandbox", "production"]
) -> EbayBrowseClient:
    """One client per credential set, so its OAuth token is reused from memory."""
    return EbayBrowseClient(client_id, client_secret, environment=environment)


def get_live_search() -> SearchRunner | None:
    """Live eBay search, or None when DATA_SOURCE=local or credentials are missing."""
    settings = get_settings()
    if settings.data_source != "ebay":
        return None
    if not settings.ebay_client_id or not settings.ebay_client_secret:
        logger.warning("DATA_SOURCE=ebay but eBay credentials are missing; using local data")
        return None
    client = _ebay_client(
        settings.ebay_client_id, settings.ebay_client_secret, settings.ebay_environment
    )

    def run(
        embedding: np.ndarray, kind: EmbeddingKind, original: Attributes, edited: Attributes
    ) -> list[Match]:
        encoder = get_encoder(settings.model_name, settings.model_dtype)
        return search_live_listings(client, encoder, embedding, kind, original, edited)

    return run


def classify_ebay_error(exc: Exception) -> FallbackReason | None:
    """Expected eBay failures fall back to local data; anything else is a real bug."""
    if not isinstance(exc, EbayAPIError):
        return None
    return "rate_limited" if exc.status_code == 429 else "unavailable"


def _to_result(match: Match, source: str) -> SearchResult:
    listing = match.listing
    if source == "ebay":
        # The frontend formats prices as USD; don't show other currencies as dollars.
        price = listing.get("price") if listing.get("currency") == "USD" else None
        return SearchResult(
            id=str(listing["id"]),
            title=str(listing["title"]),
            price=price,
            image_url=str(listing["image_url"]),
            listing_url=str(listing["listing_url"]),
            source="ebay",
            match_score=match.match_score,
        )
    # The local archive is not a marketplace: no fabricated USD prices or purchase links.
    return SearchResult(
        id=str(listing["id"]),
        title=str(listing["title"]),
        price=None,
        image_url=f"/api/local-images/{quote(str(listing['id']), safe='')}",
        listing_url=None,
        source="local",
        match_score=match.match_score,
    )


@router.post("/api/search", response_model=SearchResponse)
async def search(
    request: SearchRequest,
    cache: Annotated[QueryCache, Depends(get_query_cache)],
    runner: Annotated[SearchRunner, Depends(get_search_runner)],
    live: Annotated[SearchRunner | None, Depends(get_live_search)],
) -> SearchResponse:
    """Reuse the embedding produced by /api/extract (including text-only input).

    Optional text has already affected attributes during extraction, and text-only
    requests have a cached text embedding. Re-sending that text is not required.
    """
    cached = cache.get(request.query_id)
    if cached is None:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="This search session expired. Please submit your description or photo again.",
        )

    args = (
        cached.embedding,
        cached.kind,
        request.original_attributes,
        request.edited_attributes,
    )
    try:
        outcome = await run_in_threadpool(
            search_with_local_fallback,
            local_search=partial(runner, *args),
            live_search=partial(live, *args) if live is not None else None,
            classify_live_error=classify_ebay_error,
        )
    except (ImportError, OSError, RuntimeError, ValueError) as exc:
        logger.exception("Local clothing search unavailable")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search isn't available right now. Please try again later.",
        ) from exc

    if outcome.fallback_reason is not None:
        logger.warning("eBay search fell back to local results: %s", outcome.fallback_reason)
    return SearchResponse(results=[_to_result(m, outcome.source) for m in outcome.results])


def _find_listing(listing_id: str) -> dict[str, Any] | None:
    """The indexed local record with this id, matched exactly (never used as a path)."""
    for item in load_listings(require_image=False):
        if item["id"] == listing_id:
            return item
    return None


def _listing_image(listing_id: str) -> Path | None:
    """Find an indexed local item's photo, never using client input as a file path."""
    item = _find_listing(listing_id)
    if item is None:
        return None
    path = (PROJECT_ROOT / item["image_path"]).resolve()
    return path if path.is_relative_to(LOCAL_IMAGE_DIR) else None


@router.get("/api/local-images/{listing_id}")
async def local_image(listing_id: str) -> FileResponse:
    """Serve the local archive's JPEGs for the React results grid."""
    try:
        path = await run_in_threadpool(_listing_image, listing_id)
    except (OSError, ValueError) as exc:
        logger.exception("Local clothing data unavailable")
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Local images unavailable"
        ) from exc
    if path is None or not path.is_file() or path.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Clothing image not found")
    media_type = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return FileResponse(path, media_type=media_type)


# CC BY 4.0 requires crediting the dataset wherever its photos are shown (docs/DATA.md).
DATASET_CREDIT = "Second-Hand Fashion dataset, Nauman (2024), CC BY 4.0. Photo resized."
SearchedValue = Annotated[str | None, Query(max_length=50)]


def _compare(
    listing: dict[str, Any], searched: dict[str, str | None]
) -> list[AttributeComparison]:
    """Searched attributes next to the listing's labels, judged the way evaluation.py scores
    search results, so the page and the reported metrics agree on what counts as a match."""
    labels = listing_labels(listing)
    shown = {
        "category": labels.garment,
        "color": ", ".join(labels.colors) or None,
        "fabric": labels.fabric,
        "fit": ", ".join(labels.fits) or None,
    }
    rows = []
    for name, value in searched.items():
        if not value:
            continue
        match = (
            type_matches(listing, value)
            if name == "category"
            else edit_satisfied(listing, name, value)
        )
        rows.append(
            AttributeComparison(attribute=name, yours=value, listing=shown[name], match=match)
        )
    return rows


def _item_details(listing: dict[str, Any], searched: dict[str, str | None]) -> ItemDetails:
    raw = listing.get("attributes") or {}
    cut = ", ".join(parse_colors(raw.get("cut")))  # cut cells look like "['Regular']"
    return ItemDetails(
        id=str(listing["id"]),
        title=str(listing["title"]),
        image_url=f"/api/local-images/{quote(str(listing['id']), safe='')}",
        source="local",
        dataset_labels=DatasetLabels(
            type=clean_text(raw.get("type")),
            category=clean_text(raw.get("category")),
            colors=[c for c in (clean_text(c) for c in raw.get("colors") or []) if c],
            material=clean_text(raw.get("material")),
            cut=cut or None,
            pattern=clean_text(raw.get("pattern")),
            brand=clean_text(raw.get("brand")),
        ),
        comparison=_compare(listing, searched),
        credit=ItemCredit(
            text=DATASET_CREDIT,
            url=f"https://huggingface.co/datasets/{listing.get('dataset_id') or DATASET_ID}",
        ),
    )


@router.get("/api/item/{listing_id}", response_model=ItemDetails)
async def item_details(
    listing_id: str,
    category: SearchedValue = None,
    color: SearchedValue = None,
    fabric: SearchedValue = None,
    fit: SearchedValue = None,
) -> ItemDetails:
    """Details for one archive listing (S3-6). Pass the searched attributes to get the
    "why it matched" comparison. eBay ids are never stored, so they always return 404."""
    try:
        listing = await run_in_threadpool(_find_listing, listing_id)
    except (OSError, ValueError) as exc:
        logger.exception("Local clothing data unavailable")
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Listing details unavailable"
        ) from exc
    if listing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Listing not found")
    searched = {"category": category, "color": color, "fabric": fabric, "fit": fit}
    return _item_details(listing, searched)
