"""S3-7: read-only fallback from live marketplace retrieval to the local index.

Neither marketplace listings nor tokens are cached here. The caller supplies
``local_search`` backed by the separate, licensed FashionCLIP index; that is
our fallback dataset, not a persisted copy of eBay's response.

This module is deliberately independent of the not-yet-merged eBay client and
search endpoint. The Backend Lead wires the providers and status mapping later.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, Literal, TypeVar

T = TypeVar("T")
FallbackReason = Literal["rate_limited", "unavailable", "no_live_results"]
Source = Literal["ebay", "local"]


@dataclass(frozen=True)
class RetrievalOutcome(Generic[T]):
    """Ranked records and their actual source, plus why fallback happened."""

    results: list[T]
    source: Source
    fallback_reason: FallbackReason | None = None


def search_with_local_fallback(
    *,
    local_search: Callable[[], list[T]],
    live_search: Callable[[], list[T]] | None = None,
    classify_live_error: Callable[[Exception], FallbackReason | None] | None = None,
    limit: int = 10,
) -> RetrievalOutcome[T]:
    """Prefer the live provider, falling back only on expected provider failures.

    ``live_search=None`` uses local retrieval directly. A provided classifier
    determines whether an exception is recoverable: e.g., eBay HTTP 429 ->
    ``rate_limited``, gateway timeout -> ``unavailable``. Unexpected coding
    errors are never silently hidden. When live search returns nothing, we
    search the local precomputed index instead.

    Local failures propagate to the backend for its existing safe 503 response.
    No raw marketplace data or exception details are logged or persisted here.
    """
    if not 1 <= limit <= 10:
        raise ValueError("limit must be between 1 and 10")

    if live_search is None:
        return RetrievalOutcome(local_search()[:limit], "local")

    try:
        live_results = live_search()
    except Exception as exc:
        reason = classify_live_error(exc) if classify_live_error is not None else None
        if reason not in ("rate_limited", "unavailable"):
            raise
        return RetrievalOutcome(local_search()[:limit], "local", reason)

    if live_results:
        return RetrievalOutcome(live_results[:limit], "ebay")
    return RetrievalOutcome(local_search()[:limit], "local", "no_live_results")
