"""Unit tests for the multimodal re-ranker (S2-5), using the fake encoder."""

from __future__ import annotations

import numpy as np
import pytest

from backend.app.ml import rerank
from backend.app.ml.index import build_index
from backend.app.ml.query import Query, build_query
from backend.app.schemas import Attributes
from backend.tests.fakes import FakeEncoder, FakeImage

ORIGINAL = Attributes(category="jacket", color="black", fabric="denim", fit="regular fit")
TITLES = [
    "black denim regular fit jacket",
    "brown denim regular fit jacket",
    "red nylon parka",
    "gray wool overcoat",
]


@pytest.fixture
def encoder() -> FakeEncoder:
    return FakeEncoder()


@pytest.fixture
def index(encoder):
    listings = [
        {"id": f"item-{i}", "title": title, "image_path": f"data/images/{i}.jpg"}
        for i, title in enumerate(TITLES)
    ]
    return build_index(
        encoder, listings, "fake/model", open_image=lambda item: FakeImage(item["title"])
    )


def _upload(encoder):
    return encoder.encode_images([FakeImage("black denim regular fit jacket")])[0]


def _titles(matches):
    return [match.listing["title"] for match in matches]


def test_rank_returns_top_k_sorted_with_scores_in_range(encoder, index):
    query = build_query(encoder, _upload(encoder), "image", ORIGINAL, ORIGINAL)
    matches = rerank.rank(query, index, top_k=3)
    assert len(matches) == 3
    scores = [match.match_score for match in matches]
    assert scores == sorted(scores, reverse=True)
    assert all(0.0 <= score <= 100.0 for score in scores)
    assert _titles(matches)[0] == "black denim regular fit jacket"


def test_color_edit_changes_the_top_result(encoder, index):
    edited = ORIGINAL.model_copy(update={"color": "brown"})
    query = build_query(encoder, _upload(encoder), "image", ORIGINAL, edited)
    assert _titles(rerank.rank(query, index))[0] == "brown denim regular fit jacket"


def test_text_only_query_drops_the_image_term(encoder, index):
    description = encoder.encode_texts(["gray wool overcoat"])[0]
    query = build_query(encoder, description, "text", ORIGINAL, ORIGINAL)
    assert query.image is None
    assert _titles(rerank.rank(query, index))[0] == "gray wool overcoat"

    w_image, w_text_image, w_text_text = rerank.WEIGHTS
    expected = (
        w_text_image * rerank._calibrate(index.image_embeddings @ query.text, "text_image")
        + w_text_text * rerank._calibrate(index.text_embeddings @ query.text, "text_text")
    ) / (w_text_image + w_text_text)
    np.testing.assert_allclose(rerank.score(query, index), expected, rtol=1e-6)


def test_calibration_maps_anchors_to_zero_and_one():
    for term, (unrelated, best) in rerank.CALIBRATION.items():
        calibrated = rerank._calibrate(np.array([unrelated, best]), term)
        np.testing.assert_allclose(calibrated, [0.0, 1.0], atol=1e-9)


def test_scores_are_clipped_for_display(index):
    far = np.zeros(index.image_embeddings.shape[1], dtype=np.float32)
    matches = rerank.rank(Query(image=far, text=far), index)
    assert all(match.match_score == 0.0 for match in matches)


def test_search_listings_wires_query_and_index(monkeypatch, encoder, index):
    monkeypatch.setattr(rerank, "get_encoder", lambda *args: encoder)
    monkeypatch.setattr(rerank, "get_index", lambda: index)
    edited = ORIGINAL.model_copy(update={"color": "brown"})
    matches = rerank.search_listings(_upload(encoder), "image", ORIGINAL, edited, top_k=2)
    assert len(matches) == 2
    assert matches[0].listing["id"] == "item-1"
