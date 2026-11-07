"""Local dataset normalization and JSONL loader tests (no network access)."""

from __future__ import annotations

import json

import pytest

from backend.app.data.local_dataset import load_listings
from backend.app.data.preprocess import (
    clean_text,
    is_outerwear,
    normalize_record,
    parse_colors,
)


def test_outerwear_only():
    assert is_outerwear("Winter Jacket")
    assert is_outerwear("Blazer")
    assert not is_outerwear("T-shirt")
    assert not is_outerwear(None)


def test_colors_from_source_strings():
    assert parse_colors("['Blue', 'White']") == ["Blue", "White"]
    assert parse_colors(["Black", "black", "N/A"]) == ["Black"]
    assert clean_text(" Not Applicable ") is None


def test_normalizes_without_inventing_live_listing_details():
    record = normalize_record(
        {
            "type": "Winter jacket",
            "category": "Ladies",
            "colors": "['Brown']",
            "material": "100% wool",
            "price": "50-100",
            "cut": "Regular",
        },
        source_index=17,
        image_path="data/images/secondhand-000017.jpg",
    )
    assert record is not None
    assert record["id"] == "secondhand-000017"
    assert record["title"] == "Brown Winter jacket"
    assert record["attributes"]["material"] == "100% wool"
    assert record["price_band"] == "50-100"
    assert record["price"] is None
    assert record["listing_url"] is None
    assert normalize_record({"type": "Dress"}, source_index=0, image_path="x.jpg") is None


def test_loads_jsonl_and_deduplicates(tmp_path):
    item = {"id": "test-1", "title": "Blue Jacket", "image_path": "data/images/a.jpg"}
    metadata_path = tmp_path / "records.jsonl"
    metadata_path.write_text(json.dumps(item) + "\n" + json.dumps(item) + "\n")
    assert len(load_listings(metadata_path, require_image=False)) == 1


def test_rejects_bad_json_and_unsafe_paths(tmp_path):
    metadata_path = tmp_path / "records.jsonl"
    metadata_path.write_text("{not-json}\n")
    with pytest.raises(ValueError, match="Malformed JSON"):
        load_listings(metadata_path, require_image=False)
    metadata_path.write_text(
        json.dumps({"id": "test-2", "title": "Coat", "image_path": "../secret.jpg"})
        + "\n"
    )
    with pytest.raises(ValueError, match="Unsafe image path"):
        load_listings(metadata_path, require_image=False)
