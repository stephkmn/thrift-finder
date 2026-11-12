"""HTTP routes. Business logic stays in app/ml/ (Member A) and app/data/ (Member B)."""

from __future__ import annotations

import io
import logging
import warnings
from collections.abc import Callable
from typing import Annotated, Protocol

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from PIL import Image, UnidentifiedImageError

from backend.app.cache import QueryCache, get_query_cache
from backend.app.extractor_loader import LOAD_ERRORS, get_extractor_once
from backend.app.ml.attributes import Extraction
from backend.app.schemas import ExtractResponse

logger = logging.getLogger(__name__)

router = APIRouter()

# 10 MiB cap — re-tune once Member A knows the model's input ceiling.
MAX_IMAGE_BYTES = 10 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
# The format Pillow actually finds in the bytes; the declared content type is only a claim.
# "MPO" is a JPEG with extra embedded images (depth or HDR data): iPhones save their
# "Most Compatible" photos this way. Pillow decodes the main image, the same as any JPEG.
# HEIC (the iPhone default) stays unsupported; the frontend asks users to export as JPEG.
ALLOWED_IMAGE_FORMATS = {"JPEG", "MPO", "PNG", "WEBP"}
# The 10 MiB cap is on the file, not the pixels: a small PNG can decode to hundreds of
# megapixels. CLIP resizes to 224 px, so anything near this many pixels is a mistake or abuse.
MAX_IMAGE_PIXELS = 40_000_000


class Extractor(Protocol):
    def extract(self, image: Image.Image | None = None, text: str | None = None) -> Extraction: ...


MODEL_UNAVAILABLE = "The attribute model isn't available right now. Please try again shortly."


def get_extractor_loader() -> Callable[[], Extractor]:
    """Returns the loader for the model-backed extractor; tests override it so CI never loads torch.

    A loader rather than the extractor itself, so request validation (413/415/422) runs
    before any model loading and stays fast even when the model is unavailable.
    """
    return get_extractor_once()


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
        # Decoding a large photo is slow, synchronous work: keep it off the event loop too.
        decoded = await run_in_threadpool(_decode_image, payload)

    try:
        # Both steps run in worker threads: a first-time model load and inference are
        # slow, synchronous work that must not block the event loop.
        extractor = await run_in_threadpool(load_extractor)
        extraction = await run_in_threadpool(extractor.extract, image=decoded, text=cleaned_text)
    except LOAD_ERRORS as exc:
        logger.exception("Attribute extraction failed")
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, MODEL_UNAVAILABLE) from exc

    query_id = cache.put(extraction.embedding, "image" if decoded is not None else "text")
    return ExtractResponse(
        attributes=extraction.attributes,
        confidences=extraction.confidences,
        query_id=query_id,
    )


TOO_MANY_PIXELS = "That image's dimensions are too large. Try a smaller photo."


def _decode_image(payload: bytes) -> Image.Image:
    """Decode in memory, checking the real format and pixel count before decoding pixels."""
    try:
        with warnings.catch_warnings():
            # Pillow only warns between ~89 and ~179 megapixels; treat that as an error too.
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            decoded = Image.open(io.BytesIO(payload))  # reads the header only
            if decoded.format not in ALLOWED_IMAGE_FORMATS:
                raise HTTPException(
                    status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    detail="Unsupported image type. Use JPEG, PNG, or WebP.",
                )
            if decoded.width * decoded.height > MAX_IMAGE_PIXELS:
                raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, TOO_MANY_PIXELS)
            decoded.load()
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, TOO_MANY_PIXELS) from exc
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Couldn't read that image. Try a JPEG, PNG, or WebP photo.",
        ) from exc
    return decoded
