"""FastAPI application entrypoint.

Run locally:
    uvicorn backend.app.main:app --reload
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool

from backend.app.api.routes import router
from backend.app.api.search import router as search_router
from backend.app.config import get_settings
from backend.app.extractor_loader import LOAD_ERRORS, get_extractor_once

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Load the model once at startup so the first upload isn't slow.

    A failed load is logged, not fatal: /api/health keeps working and /api/extract
    returns 503 until the model can load (e.g. torch not installed).
    """
    if get_settings().preload_model:
        try:
            await run_in_threadpool(get_extractor_once())
            logger.info("Attribute model loaded")
        except LOAD_ERRORS:
            logger.warning("Could not preload the attribute model", exc_info=True)
    yield


app = FastAPI(title="Thrift Searcher", version="0.1.0", lifespan=lifespan)
app.include_router(router)
app.include_router(search_router)
