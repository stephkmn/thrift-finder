"""FastAPI application entrypoint.

Run locally:
    uvicorn backend.app.main:app --reload
"""

from __future__ import annotations

from fastapi import FastAPI

from backend.app.api.routes import router

app = FastAPI(title="Thrift Searcher", version="0.1.0")
app.include_router(router)
