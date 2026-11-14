"""Keyword-only baseline tests; no real model or image files required."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from backend.app.data.keyword_baseline import rank_edited_attributes, rank_keywords
from backend.app.schemas import Attributes


def _listing(listing_id, color, material, clothing_type="Jacket"):
    return {
        "id": listing_id,
        "title": f"{color} {clothing_type}",
        "image_path": f"data/images/{listing_id}.jpg",
        "attributes": {
            "type": clothing_type,
            "colors": [color],
            "material": material,
            "pattern": "plain",
        },
    }


LISTINGS = [
    _listing("a", "Black", "denim"),
    _listing("b", "Brown", "leather"),
    _listing("c", "Brown", "wool"),
    _listing("d", "Red", "polyester", "Vest"),
]


def test_keyword_only_prefers_matching_color_fabric_and_type():
    matches = rank_keywords("brown leather jacket", LISTINGS)
    assert matches[0].listing["id"] == "b"
    assert matches[0].coverage == 100.0
    assert matches[0].matched_terms == ("brown", "jacket", "leather")
    assert matches[1].listing["id"] == "c"
    assert matches[1].coverage == 66.7


def test_edited_attributes_reuse_keyword_builder():
    attributes = Attributes(category="jacket", color="brown", fabric="leather", fit="unknown")
    matches = rank_edited_attributes(attributes, LISTINGS)
    assert matches[0].listing["id"] == "b"


def test_negative_features_are_not_positive_search_terms():
    attributes = Attributes(
        category="jacket", color="brown", fabric="unknown", fit="unknown", others=["no hood"]
    )
    matches = rank_edited_attributes(attributes, LISTINGS)
    assert matches[0].listing["id"] == "b"
    assert matches[0].coverage == 100.0


def test_empty_query_returns_no_results_and_unrelated_listing_is_excluded():
    assert rank_keywords("", LISTINGS) == []
    assert rank_keywords("unknown", [_listing("x", "Black", "wool")]) == []
    assert rank_keywords("red vest", LISTINGS)[0].listing["id"] == "d"


def test_top_k_and_ties_preserve_input_order():
    matches = rank_keywords("jacket", LISTINGS, top_k=2)
    assert [match.listing["id"] for match in matches] == ["a", "b"]


@pytest.mark.parametrize("limit", [0, -1])
def test_invalid_top_k_rejected(limit):
    with pytest.raises(ValueError, match="top_k must be positive"):
        rank_keywords("jacket", LISTINGS, top_k=limit)


def test_cli_outputs_json_without_loading_model(tmp_path):
    data = tmp_path / "listings.jsonl"
    data.write_text("".join(json.dumps(row) + "\n" for row in LISTINGS), encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.keyword_baseline",
            "--listings",
            str(data),
            "--query",
            "brown leather jacket",
            "--top-k",
            "2",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    output = json.loads(result.stdout)
    assert output["method"] == "keyword_overlap_v1"
    assert output["listings_scanned"] == len(LISTINGS)
    assert len(output["results"]) == 2
    assert output["results"][0]["id"] == "b"
