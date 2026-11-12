"""Simple, reproducible keyword-only retrieval baseline (S3-3).

This baseline deliberately uses no FashionCLIP embeddings or model inference.
It ranks local listings by the fraction of unique query words found in the
listing's normalized metadata caption. Scores are query-term coverage, not
probabilities or directly comparable to FashionCLIP's match scores.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from backend.app.data.query_keywords import build_keywords
from backend.app.ml.index import listing_text
from backend.app.schemas import Attributes

_WORD = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class KeywordMatch:
    listing: dict[str, Any]
    coverage: float
    matched_terms: tuple[str, ...]


def _terms(value: str) -> set[str]:
    return set(_WORD.findall(value.casefold()))


def rank_keywords(
    keywords: str, listings: list[dict[str, Any]], *, top_k: int = 10
) -> list[KeywordMatch]:
    """Return local listings with at least one matching query token.

    Coverage = matching unique query tokens / all unique query tokens. Ties
    retain input-listing order, making baseline runs deterministic. No indexed
    images, model weights, or live marketplace results are used.
    """
    if top_k < 1:
        raise ValueError("top_k must be positive")
    query_terms = _terms(keywords)
    if not query_terms:
        return []

    matches: list[KeywordMatch] = []
    for listing in listings:
        overlap = tuple(sorted(query_terms & _terms(listing_text(listing))))
        if not overlap:
            continue
        matches.append(
            KeywordMatch(
                listing=listing,
                coverage=round(100.0 * len(overlap) / len(query_terms), 1),
                matched_terms=overlap,
            )
        )
    return sorted(matches, key=lambda match: -match.coverage)[:top_k]


def rank_edited_attributes(
    edited: Attributes, listings: list[dict[str, Any]], *, top_k: int = 10
) -> list[KeywordMatch]:
    """Use Member B's S2-4 attribute-to-keyword builder for the baseline."""
    return rank_keywords(build_keywords(edited), listings, top_k=top_k)
