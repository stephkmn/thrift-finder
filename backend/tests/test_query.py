"""Unit tests for attribute-edit query embeddings (S2-4), using the fake encoder."""

from __future__ import annotations

import numpy as np
import pytest

from backend.app.ml.attributes import load_vocabulary
from backend.app.ml.query import build_query, describe, photo_caption
from backend.app.schemas import Attributes
from backend.tests.fakes import FakeEncoder, FakeImage

ORIGINAL = Attributes(
    category="jacket", color="black", fabric="denim", fit="regular fit", others=["hood"]
)


@pytest.fixture
def encoder() -> FakeEncoder:
    return FakeEncoder()


def _cos_to_word(encoder: FakeEncoder, vector: np.ndarray, word: str) -> float:
    return float(vector @ encoder.encode_texts([word])[0])


def test_photo_caption_picks_the_article_and_skips_blanks():
    assert photo_caption(["orange", "", "parka"]) == "a photo of an orange parka."
    assert photo_caption(["black", "coat"]) == "a photo of a black coat."


def test_describe_uses_feature_phrases():
    vocabulary = load_vocabulary()
    edited = ORIGINAL.model_copy(update={"others": ["hood", "zipper", "glitter"]})
    assert describe(edited, vocabulary) == (
        "a photo of a black denim regular fit jacket with a hood, a front zipper and glitter."
    )
    plain = ORIGINAL.model_copy(update={"others": None})
    assert describe(plain, vocabulary) == "a photo of a black denim regular fit jacket."


def test_no_edit_leaves_the_upload_embedding_unchanged(encoder):
    upload = encoder.encode_images([FakeImage("black denim jacket with a hood")])[0]
    query = build_query(encoder, upload, "image", ORIGINAL, ORIGINAL)
    np.testing.assert_allclose(query.image, upload, atol=1e-6)
    expected_text = encoder.encode_texts([describe(ORIGINAL, load_vocabulary())])[0]
    np.testing.assert_allclose(query.text, expected_text, atol=1e-6)


def test_color_edit_moves_the_query_towards_the_new_color(encoder):
    upload = encoder.encode_images([FakeImage("black denim jacket with a hood")])[0]
    edited = ORIGINAL.model_copy(update={"color": "brown"})
    query = build_query(encoder, upload, "image", ORIGINAL, edited)

    assert _cos_to_word(encoder, query.image, "brown") > _cos_to_word(encoder, upload, "brown")
    assert _cos_to_word(encoder, query.image, "black") < _cos_to_word(encoder, upload, "black")
    # Unedited attributes keep their weight.
    assert _cos_to_word(encoder, query.image, "denim") > 0
    assert abs(float(np.linalg.norm(query.image)) - 1.0) < 1e-5


def test_removing_a_feature_moves_the_query_away_from_it(encoder):
    upload = encoder.encode_images([FakeImage("black denim jacket with a hood")])[0]
    edited = ORIGINAL.model_copy(update={"others": None})
    query = build_query(encoder, upload, "image", ORIGINAL, edited)
    assert _cos_to_word(encoder, query.image, "hood") < _cos_to_word(encoder, upload, "hood")


def test_text_only_upload_has_no_image_side(encoder):
    description = encoder.encode_texts(["black denim jacket"])[0]
    edited = ORIGINAL.model_copy(update={"color": "brown"})
    query = build_query(encoder, description, "text", ORIGINAL, edited)

    assert query.image is None
    assert _cos_to_word(encoder, query.text, "brown") > 0
    assert _cos_to_word(encoder, query.text, "black") < _cos_to_word(encoder, description, "black")
