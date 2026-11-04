"""HTTP routes. Business logic stays in app/ml/ (Member A) and app/data/ (Member B)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from backend.app.schemas import Attributes, Confidences, ExtractResponse

router = APIRouter()

# 10 MiB cap — re-tune once Member A knows the model's input ceiling.
MAX_IMAGE_BYTES = 10 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


@router.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/api/extract", response_model=ExtractResponse)
async def extract(
    image: UploadFile | None = File(default=None),
    text: str | None = Form(default=None),
) -> ExtractResponse:
    """Stub implementation (S1-8). Member A replaces the body with a real model call in S2-1.

    Validates the request shape and returns a deterministic fixture so the frontend
    can flip VITE_USE_MOCKS=false and exercise the real network path today.
    """
    cleaned_text = text.strip() if text else None
    if image is None and not cleaned_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide an image, text, or both.",
        )

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

    return ExtractResponse(
        attributes=Attributes(
            category="jacket",
            color="black",
            fabric="denim",
            fit="regular",
            others=["hood"],
        ),
        confidences=Confidences(
            category=0.94,
            color=0.88,
            fabric=0.71,
            fit=0.55,
            others={"hood": 0.82},
        ),
        query_id=f"stub-{uuid.uuid4()}",
    )
