"""Live eBay retrieval + FashionCLIP re-ranking (S2-5 / S3-7; PHASE2_SPRINT_PLAN.md §4.3).

    edited attributes -> keywords -> eBay Browse (used only) -> thumbnails + titles
    embedded in memory -> the same calibrated score() as the local index -> top 10

eBay keyword search has no notion of visual similarity, so every candidate is embedded
per request and ranked against the cached upload embedding, with the user's edits applied.
Nothing here is written to disk or logged (eBay data-deletion exemption, EBAY_FEASIBILITY.md).
"""

from __future__ import annotations

import io
import logging
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any, Protocol

import numpy as np

from backend.app.cache import EmbeddingKind
from backend.app.data.ebay_client import EbayAPIError, fetch_listing_image
from backend.app.data.query_keywords import build_keywords
from backend.app.ml.encoder import Encoder
from backend.app.ml.index import ListingIndex
from backend.app.ml.query import build_query
from backend.app.ml.rerank import TOP_K, Match, rank
from backend.app.schemas import Attributes

if TYPE_CHECKING:
    from PIL import Image

logger = logging.getLogger(__name__)

# The Browse API allows up to 20 per call in our client; more candidates = better re-ranking
# but more thumbnails to download and encode per request.
CANDIDATE_LIMIT = 20
IMAGE_WORKERS = 8


class ListingSearcher(Protocol):
    def search(self, query: str, *, limit: int = ..., used_only: bool = ...) -> list[dict]: ...


ImageLoader = Callable[[str], "Image.Image"]


def load_listing_image(url: str) -> Image.Image:
    """Download a thumbnail and decode it in memory."""
    from PIL import Image, UnidentifiedImageError

    data = fetch_listing_image(url)
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except (UnidentifiedImageError, OSError, ValueError):
        raise EbayAPIError("Listing image could not be decoded") from None
    return image


def _usable(listing: dict[str, Any]) -> bool:
    """Only show listings a shopper can actually see and open."""
    return all(isinstance(listing.get(key), str) and listing[key] for key in (
        "id", "title", "image_url", "listing_url"
    ))


def _load_images(
    listings: Sequence[dict[str, Any]], load_image: ImageLoader
) -> list[Image.Image | None]:
    def load(listing: dict[str, Any]) -> Image.Image | None:
        try:
            return load_image(listing["image_url"])
        except EbayAPIError:
            return None  # a broken thumbnail drops that listing, not the whole search

    with ThreadPoolExecutor(max_workers=IMAGE_WORKERS) as pool:
        return list(pool.map(load, listings))


def search_live_listings(
    client: ListingSearcher,
    encoder: Encoder,
    embedding: np.ndarray,
    kind: EmbeddingKind,
    original: Attributes,
    edited: Attributes,
    *,
    load_image: ImageLoader = load_listing_image,
    top_k: int = TOP_K,
) -> list[Match]:
    """Rank live eBay listings against a cached upload embedding plus attribute edits.

    Returns [] when there's nothing to search for or nothing usable comes back, so the
    caller can fall back to the local index. eBay API failures raise EbayAPIError.
    """
    keywords = build_keywords(edited)
    if not keywords:
        return []
    candidates = [
        listing
        for listing in client.search(keywords, limit=CANDIDATE_LIMIT, used_only=True)
        if _usable(listing)
    ]
    if not candidates:
        return []

    images = _load_images(candidates, load_image)
    kept = [
        (listing, image)
        for listing, image in zip(candidates, images, strict=True)
        if image is not None
    ]
    if not kept:
        logger.warning("No eBay thumbnails could be loaded for %d candidates", len(candidates))
        return []

    listings = [listing for listing, _ in kept]
    index = ListingIndex(
        listings=listings,
        image_embeddings=encoder.encode_images([image for _, image in kept]),
        text_embeddings=encoder.encode_texts([listing["title"] for listing in listings]),
        model_name=getattr(encoder, "model_name", "unknown"),
    )
    query = build_query(encoder, embedding, kind, original, edited)
    return rank(query, index, top_k)
