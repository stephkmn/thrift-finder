"""Unit tests for zero-shot attribute extraction (S1-5, S1-6).

A one-hot word fake encoder (backend/tests/fakes.py) stands in for CLIP so these run in CI without torch. Set
RUN_MODEL_TESTS=1 to also run the real-model smoke test (downloads ~600 MB on first run).
"""

from __future__ import annotations

import os
from collections import Counter
from dataclasses import replace

import numpy as np
import pytest

from backend.app.ml.attributes import AttributeExtractor, load_vocabulary
from backend.app.schemas import ExtractResponse
from backend.tests.fakes import FakeEncoder, FakeImage


@pytest.fixture(scope="module")
def extractor() -> AttributeExtractor:
    return AttributeExtractor(FakeEncoder())


def _response(attributes, confidences) -> ExtractResponse:
    return ExtractResponse(attributes=attributes, confidences=confidences, query_id="test")


def test_vocabulary_is_well_formed():
    vocabulary = load_vocabulary()
    assert set(vocabulary.scalars) == {"category", "color", "fabric", "fit"}
    for name, spec in vocabulary.scalars.items():
        assert len(spec.values) == len(set(spec.values)), f"duplicate {name} values"
        assert all("{value}" in template for template in spec.templates)
    assert "hood" in vocabulary.features
    assert 0.0 < vocabulary.others_threshold < 1.0
    terms = Counter(t for f, spec in vocabulary.features.items() for t in [f, *spec.synonyms])
    assert not [t for t, n in terms.items() if n > 1], "a word maps to two features"


def test_image_extraction_picks_matching_values(extractor):
    image = FakeImage("black leather bomber jacket with a hood, slim fit")
    attributes, confidences, _ = extractor.extract(image=image)
    assert attributes.category == "bomber jacket"
    assert attributes.color == "black"
    assert attributes.fabric == "leather"
    assert attributes.fit == "slim fit"
    assert attributes.others == ["hood"]
    assert 0.5 < confidences.others["hood"] <= 1.0
    _response(attributes, confidences)


def test_no_features_found_is_null_not_empty(extractor):
    attributes, confidences, _ = extractor.extract(image=FakeImage("navy wool peacoat"))
    assert attributes.others is None
    assert confidences.others is None
    _response(attributes, confidences)


def test_text_overrides_image_with_full_confidence(extractor):
    image = FakeImage("black denim jacket")
    attributes, confidences, _ = extractor.extract(image=image, text="Brown suede, please")
    assert (attributes.color, confidences.color) == ("brown", 1.0)
    assert (attributes.fabric, confidences.fabric) == ("suede", 1.0)
    assert attributes.category == "jacket"


def test_text_synonyms_map_to_vocabulary(extractor):
    attributes, *_ = extractor.extract(text="grey puffer with faux fur")
    assert attributes.color == "gray"
    assert attributes.category == "puffer jacket"
    assert attributes.others == ["fur trim"]


def test_longest_stated_value_wins(extractor):
    attributes, *_ = extractor.extract(text="a tan trench coat")
    assert attributes.category == "trench coat"


def test_generic_text_keeps_more_specific_guess(extractor):
    image = FakeImage("black leather bomber jacket")
    attributes, confidences, _ = extractor.extract(image=image, text="black jacket")
    assert attributes.category == "bomber jacket"
    assert confidences.color == 1.0


def test_common_words_do_not_trigger_synonyms(extractor):
    image = FakeImage("navy cotton jacket, regular fit")
    attributes, *_ = extractor.extract(image=image, text="long sleeves and a drawstring cord")
    assert attributes.fit == "regular fit"
    assert attributes.fabric == "cotton"


def test_negated_feature_is_removed(extractor):
    image = FakeImage("black jacket with a hood")
    assert extractor.extract(image=image)[0].others == ["hood"]
    attributes, confidences, _ = extractor.extract(image=image, text="same jacket but no hood")
    assert attributes.others is None
    _response(attributes, confidences)


def test_negated_value_is_not_applied(extractor):
    attributes, *_ = extractor.extract(image=FakeImage("black wool coat"), text="not black")
    assert attributes.color == "black"
    assert attributes.fabric == "wool"


def test_dont_and_instead_of_negate_a_value(extractor):
    image = FakeImage("black denim jacket with a hood")
    for text in ["I don't want black, brown instead", "I don\u2019t want black, brown instead"]:
        assert extractor.extract(image=image, text=text).attributes.color == "brown"
    assert extractor.extract(image=image, text="brown instead of black").attributes.color == "brown"


@pytest.mark.parametrize(
    "text",
    [
        "I don't want a hood",
        "it doesn't have a hood",
        "isn't hooded",
        "won't need a hood",
        "no hood please",
        "same jacket but without the hood",
    ],
)
def test_negation_reaches_a_few_words_back(extractor, text):
    image = FakeImage("black denim jacket with a hood")
    assert extractor.extract(image=image, text=text).attributes.others is None


@pytest.mark.parametrize(
    "text",
    [
        "no zip, keep the hood",
        "no zipper but a hood",
        "no stains on this hooded jacket",
    ],
)
def test_negation_stops_at_the_clause_and_window(extractor, text):
    image = FakeImage("black denim jacket with a hood")
    assert "hood" in (extractor.extract(image=image, text=text).attributes.others or [])


def test_negation_carries_through_an_or_list(extractor):
    image = FakeImage("black denim jacket with a hood")
    others = extractor.extract(image=image, text="without a hood or zipper").attributes.others
    assert others is None


def test_instead_of_reaches_past_a_word(extractor):
    image = FakeImage("black denim jacket with a hood")
    assert extractor.extract(image=image, text="brown instead of the black").attributes.color == (
        "brown"
    )


def test_plural_feature_is_matched_and_negated(extractor):
    image = FakeImage("black denim jacket with a hood")
    assert extractor.extract(image=image, text="no hoods please").attributes.others is None
    assert extractor.extract(text="a coat with zippers").attributes.others == ["zipper"]


class WithLeaningEncoder(FakeEncoder):
    """Counts the word "with", like CLIP does: any description saying "with" then sits
    closer to every "a jacket with X" prompt than to its "without X" partner."""

    stopwords = FakeEncoder.stopwords - {"with"}


def test_text_only_reports_only_the_features_it_names():
    extractor = AttributeExtractor(WithLeaningEncoder())
    image_result = extractor.extract(image=FakeImage("black jacket with a hood"))
    assert len(image_result.attributes.others or []) > 1  # the bias this guards against
    text_result = extractor.extract(text="brown suede bomber jacket with a hood")
    assert text_result.attributes.others == ["hood"]
    assert text_result.confidences.others == {"hood": 1.0}


def test_text_only_extraction_returns_valid_contract(extractor):
    attributes, confidences, _ = extractor.extract(text="olive canvas parka with a hood")
    assert attributes.category == "parka"
    assert attributes.others == ["hood"]
    _response(attributes, confidences)


def test_per_feature_threshold_overrides_shared_one():
    vocabulary = load_vocabulary()
    strict_hood = replace(vocabulary.features["hood"], threshold=1.0)
    vocabulary = replace(vocabulary, features={**vocabulary.features, "hood": strict_hood})
    image = FakeImage("black jacket with a hood")
    assert (
        AttributeExtractor(FakeEncoder(), vocabulary).extract(image=image).attributes.others is None
    )


def test_extraction_returns_normalized_query_embedding(extractor):
    result = extractor.extract(image=FakeImage("red wool coat"))
    assert abs(float(np.linalg.norm(result.embedding)) - 1.0) < 1e-5


def test_extract_requires_image_or_text(extractor):
    with pytest.raises(ValueError):
        extractor.extract(text="   ")


@pytest.mark.skipif(os.environ.get("RUN_MODEL_TESTS") != "1", reason="set RUN_MODEL_TESTS=1")
def test_real_model_reads_a_solid_color():
    from PIL import Image

    from backend.app.ml.attributes import extract_attributes

    result = extract_attributes(image=Image.new("RGB", (224, 224), (200, 20, 20)))
    assert result.attributes.color == "red"
    assert result.embedding.shape == (512,)
    _response(result.attributes, result.confidences)
