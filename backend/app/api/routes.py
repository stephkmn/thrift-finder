"""HTTP routes. Business logic stays in app/ml/ (Member A) and app/data/ (Member B)."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
