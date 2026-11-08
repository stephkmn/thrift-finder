"""HTTP routes. Business logic stays in app/ml/ (Member A) and app/data/ (Member B)."""

from __future__ import annotations

import io
import logging
from collections.abc import Callable
from typing import Annotated, Protocol

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from PIL import Image, UnidentifiedImageError

from backend.app.cache import QueryCache, get_query_cache
from backend.app.ml.attributes import Extraction, get_extractor
from backend.app.schemas import ExtractResponse

logger = logging.getLogger(__name__)

router = APIRouter()

# 10 MiB cap — re-tune once Member A knows the model's input ceiling.
MAX_IMAGE_BYTES = 10 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


class Extractor(Protocol):
    def extract(self, image: Image.Image | None = None, text: str | None = None) -> Extraction: ...


MODEL_UNAVAILABLE = "The attribute model isn't available right now. Please try again shortly."


def get_extractor_loader() -> Callable[[], Extractor]:
    """Returns the loader for the model-backed extractor; tests override it so CI never loads torch.

    A loader rather than the extractor itself, so request validation (413/415/422) runs
    before any model loading and stays fast even when the model is unavailable.
    """
    return get_extractor


@router.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/api/extract", response_model=ExtractResponse)
async def extract(
    load_extractor: Annotated[Callable[[], Extractor], Depends(get_extractor_loader)],
    cache: Annotated[QueryCache, Depends(get_query_cache)],
    image: Annotated[UploadFile | None, File()] = None,
    text: Annotated[str | None, Form()] = None,
) -> ExtractResponse:
    """Photo and/or description in; model attributes, confidences, and a query_id out.

    The query embedding is cached under query_id so /api/search can reuse it.
    """
    cleaned_text = text.strip() if text else None
    if image is None and not cleaned_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide an image, text, or both.",
        )

    decoded: Image.Image | None = None
    if image is not None:
        if image.content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Unsupported image type: {image.content_type}. Use JPEG, PNG, or WebP.",
            )
        # Read in memory only; per sprint plan §4.2 nothing is persisted to disk.
        payload = await image.read()
        if len(payload) > MAX_IMAGE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Image exceeds 10 MiB limit.",
            )
        decoded = _decode_image(payload)

    try:
        # Both steps run in worker threads: a first-time model load and inference are
        # slow, synchronous work that must not block the event loop.
        extractor = await run_in_threadpool(load_extractor)
        extraction = await run_in_threadpool(extractor.extract, image=decoded, text=cleaned_text)
    except (ImportError, RuntimeError, OSError) as exc:
        logger.exception("Attribute extraction failed")
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, MODEL_UNAVAILABLE) from exc

    query_id = cache.put(extraction.embedding, "image" if decoded is not None else "text")
    return ExtractResponse(
        attributes=extraction.attributes,
        confidences=extraction.confidences,
        query_id=query_id,
    )


def _decode_image(payload: bytes) -> Image.Image:
    try:
        decoded = Image.open(io.BytesIO(payload))
        decoded.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Couldn't read that image. Try a JPEG, PNG, or WebP photo.",
        ) from exc
    return decoded
