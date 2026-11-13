"""Unit tests for the listing embedding index (S2-3), using the fake encoder."""

from __future__ import annotations

import json

import numpy as np
import pytest

from backend.app.ml.index import (
    build_index,
    listing_labels,
    listing_text,
    load_index,
    save_index,
)
from backend.tests.fakes import FakeEncoder, FakeImage

MODEL = "fake/model"


def _listing(listing_id: str, title: str) -> dict:
    return {"id": listing_id, "title": title, "image_path": f"data/images/{listing_id}.jpg"}


LISTINGS = [
    _listing("a", "black denim jacket"),
    _listing("b", "brown suede jacket"),
    _listing("c", "red puffer jacket"),
]


def _build(listings=LISTINGS, **kwargs):
    return build_index(
        FakeEncoder(), listings, MODEL, open_image=lambda item: FakeImage(item["title"]), **kwargs
    )


def _write_listings(path, listings=LISTINGS):
    path.write_text("".join(json.dumps(item) + "\n" for item in listings), encoding="utf-8")
    return path


def test_listing_text_uses_vocabulary_words():
    listing = {
        "title": "Grey Winter Jacket",
        "attributes": {
            "type": "Winter Jacket",
            "colors": ["Grey", "Beige"],
            "material": "34%polyester 66%viscose",
            "cut": "['Regular', 'Long']",
            "pattern": "Other",
        },
    }
    assert listing_text(listing) == "a photo of a gray and tan viscose regular fit winter jacket."


def test_listing_text_maps_synthetic_leather_and_uses_an():
    listing = {
        "title": "Orange Jacket",
        "attributes": {"type": "Jacket", "colors": ["Orange"], "material": "PU leather"},
    }
    assert listing_text(listing) == "a photo of an orange leather jacket."


@pytest.mark.parametrize(
    ("material", "fabric"),
    [
        ("100% bomull", "cotton"),
        ("80% ull 20% polyamid", "wool"),
        ("61% Cotton 39% Poly", "cotton"),
        ("100% polyster", "polyester"),
        ("unknown no match", None),
        (None, None),
    ],
)
def test_listing_labels_normalize_dataset_materials(material, fabric):
    assert listing_labels({"attributes": {"material": material}}).fabric == fabric


def test_load_index_rejects_an_index_built_from_older_texts(tmp_path):
    save_index(_build(), tmp_path / "embeddings.npz")
    renamed = [{**LISTINGS[0], "title": "green denim jacket"}, *LISTINGS[1:]]
    listings_path = _write_listings(tmp_path / "listings.jsonl", renamed)
    with pytest.raises(ValueError, match="older listing texts"):
        load_index(MODEL, tmp_path / "embeddings.npz", listings_path)


def test_listing_text_falls_back_to_title_when_labels_are_missing():
    assert listing_text({"title": "Coat", "attributes": {}}) == "a photo of a coat."


def test_build_index_encodes_every_listing_in_batches():
    progress = []
    index = _build(batch_size=2, on_progress=lambda done, total: progress.append((done, total)))
    assert progress == [(2, 3), (3, 3)]
    assert index.image_embeddings.shape == index.text_embeddings.shape == (3, FakeEncoder.dim)
    assert index.image_embeddings.dtype == np.float32
    assert [item["id"] for item in index.listings] == ["a", "b", "c"]


def test_build_index_rejects_empty_listings():
    with pytest.raises(ValueError, match="ingest"):
        _build(listings=[])


def test_saved_index_loads_back_in_the_same_order(tmp_path):
    index = _build()
    save_index(index, tmp_path / "embeddings.npz")
    listings_path = _write_listings(tmp_path / "listings.jsonl", list(reversed(LISTINGS)))

    loaded = load_index(MODEL, tmp_path / "embeddings.npz", listings_path)
    assert [item["id"] for item in loaded.listings] == ["a", "b", "c"]
    np.testing.assert_array_equal(loaded.image_embeddings, index.image_embeddings)
    np.testing.assert_array_equal(loaded.text_embeddings, index.text_embeddings)
    assert not (tmp_path / "embeddings.npz.tmp").exists()


def test_load_index_rejects_an_index_from_another_model(tmp_path):
    save_index(_build(), tmp_path / "embeddings.npz")
    listings_path = _write_listings(tmp_path / "listings.jsonl")
    with pytest.raises(ValueError, match="rebuild"):
        load_index("other/model", tmp_path / "embeddings.npz", listings_path)


def test_load_index_rejects_a_stale_index(tmp_path):
    save_index(_build(), tmp_path / "embeddings.npz")
    listings_path = _write_listings(tmp_path / "listings.jsonl", LISTINGS[:2])
    with pytest.raises(ValueError, match="does not match"):
        load_index(MODEL, tmp_path / "embeddings.npz", listings_path)


def test_load_index_explains_a_missing_index(tmp_path):
    with pytest.raises(FileNotFoundError, match="build_embeddings"):
        load_index(MODEL, tmp_path / "missing.npz")
