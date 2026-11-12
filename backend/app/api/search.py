"""S3-4: resolve cached image/text queries to ranked local clothing listings.

The standalone eBay client is not required here: the Phase 2 local index works
without marketplace credentials and never invents purchase prices or links.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Annotated
from urllib.parse import quote

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse

from backend.app.cache import EmbeddingKind, QueryCache, get_query_cache
from backend.app.data.local_dataset import PROJECT_ROOT, load_listings
from backend.app.ml.rerank import Match, search_listings
from backend.app.schemas import Attributes, SearchRequest, SearchResponse, SearchResult

logger = logging.getLogger(__name__)
router = APIRouter()

SearchRunner = Callable[
    [np.ndarray, EmbeddingKind, Attributes, Attributes], list[Match]
]
LOCAL_IMAGE_DIR = (PROJECT_ROOT / "data" / "images").resolve()


def get_search_runner() -> SearchRunner:
    """Overrideable model/index entrypoint; CI can test without loading FashionCLIP."""
    return search_listings


@router.post("/api/search", response_model=SearchResponse)
async def search(
    request: SearchRequest,
    cache: Annotated[QueryCache, Depends(get_query_cache)],
    runner: Annotated[SearchRunner, Depends(get_search_runner)],
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

    try:
        matches = await run_in_threadpool(
            runner,
            cached.embedding,
            cached.kind,
            request.original_attributes,
            request.edited_attributes,
        )
    except (ImportError, OSError, RuntimeError, ValueError) as exc:
        logger.exception("Local clothing search unavailable")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search isn't available right now. Please try again later.",
        ) from exc

    # The local archive is not a marketplace: no fabricated USD prices or purchase links.
    results = [
        SearchResult(
            id=str(match.listing["id"]),
            title=str(match.listing["title"]),
            price=None,
            image_url=f"/api/local-images/{quote(str(match.listing['id']), safe='')}",
            listing_url=None,
            source="local",
            match_score=match.match_score,
        )
        for match in matches[:10]
    ]
    return SearchResponse(results=results)


def _listing_image(listing_id: str) -> Path | None:
    """Find an indexed local item's photo, never using client input as a file path."""
    for item in load_listings(require_image=False):
        if item["id"] == listing_id:
            path = (PROJECT_ROOT / item["image_path"]).resolve()
            return path if path.is_relative_to(LOCAL_IMAGE_DIR) else None
    return None


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
