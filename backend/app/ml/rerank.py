"""Multimodal re-ranker (S2-5; docs/PHASE2_SPRINT_PLAN.md §4.3).

    score(c) = w1·cos(q_img, E_img(c)) + w2·cos(q_txt, E_img(c)) + w3·cos(q_txt, E_txt(c))

Each cosine is first mapped onto a shared scale (0 = a typical unrelated listing, 1 = the
closest match we measured) because the three terms live on very different ranges: image-to-image
cosines sit around 0.4–0.7 while text-to-image ones sit around 0.15–0.35, so raw sums would
let the image term drown out the weights. The weighted result, clipped to 0–1 and × 100,
is the match score shown to users.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from backend.app.cache import EmbeddingKind
from backend.app.config import get_settings
from backend.app.ml.encoder import get_encoder
from backend.app.ml.index import ListingIndex, get_index
from backend.app.ml.query import Query, build_query
from backend.app.schemas import Attributes

# (w1 image->image, w2 text->image, w3 text->text): the plan's starting point, tuned in S3-1.
WEIGHTS = (0.5, 0.3, 0.2)
TOP_K = 10

# (typical unrelated, closest match) cosine per term, measured with FashionCLIP on the
# 500-listing local index over 21 queries (16 Openverse photos + 5 text descriptions): the
# median over all listings, and the highest value seen. Anchoring 1 at the typical top-1
# instead saturated every edited result at 100. Re-measure if the model or data changes.
CALIBRATION = {
    "image_image": (0.37, 0.74),
    "text_image": (0.17, 0.37),
    "text_text": (0.48, 0.91),
}


@dataclass(frozen=True)
class Match:
    listing: dict[str, Any]
    match_score: float  # 0-100


def _calibrate(cosines: np.ndarray, term: str) -> np.ndarray:
    unrelated, best = CALIBRATION[term]
    return (cosines - unrelated) / (best - unrelated)


def score(
    query: Query, index: ListingIndex, weights: tuple[float, float, float] = WEIGHTS
) -> np.ndarray:
    """Calibrated score per listing (unclipped, so ranking keeps its full resolution).

    Text-only queries have no image side, so w1 is dropped and the rest renormalized.
    """
    w_image, w_text_image, w_text_text = weights
    total = w_text_image * _calibrate(index.image_embeddings @ query.text, "text_image")
    total += w_text_text * _calibrate(index.text_embeddings @ query.text, "text_text")
    weight_sum = w_text_image + w_text_text
    if query.image is not None:
        total += w_image * _calibrate(index.image_embeddings @ query.image, "image_image")
        weight_sum += w_image
    return total / weight_sum


def rank(
    query: Query,
    index: ListingIndex,
    top_k: int = TOP_K,
    weights: tuple[float, float, float] = WEIGHTS,
) -> list[Match]:
    scores = score(query, index, weights)
    best = np.argsort(-scores, kind="stable")[:top_k]
    return [
        Match(index.listings[i], round(float(np.clip(scores[i], 0.0, 1.0)) * 100, 1)) for i in best
    ]


def search_listings(
    embedding: np.ndarray,
    kind: EmbeddingKind,
    original: Attributes,
    edited: Attributes,
    top_k: int = TOP_K,
) -> list[Match]:
    """Entry point for POST /api/search (S2-5): a cached upload embedding plus the user's
    attribute edits in, the top matches out. The model and index load once per process."""
    settings = get_settings()
    encoder = get_encoder(settings.model_name, settings.model_dtype)
    query = build_query(encoder, embedding, kind, original, edited)
    return rank(query, get_index(), top_k)
