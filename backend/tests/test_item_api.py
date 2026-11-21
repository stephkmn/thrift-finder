"""S3-6: GET /api/item/{id} returns archive listing details and the "why it matched" rows.

Listings are injected, so the tests need no downloaded data or model.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.api import search as search_api
from backend.app.main import app

BROWN_COAT = {
    "id": "secondhand-000123",
    "title": "Brown Jacket",
    "source": "local",
    "dataset_id": "fnauman/fashion-second-hand-front-only-rgb",
    "source_index": 123,
    "image_path": "data/images/secondhand-000123.jpg",
    "listing_url": None,
    "price": None,
    "price_band": "100-150",
    "attributes": {
        "type": "Jacket",
        "category": "Ladies",
        "colors": ["Brown"],
        "material": "100% bomull",
        "cut": "['Regular']",
        "pattern": "Plain",
        "brand": None,
    },
}
UNLABELED = {
    "id": "secondhand-000456",
    "title": "Blazer",
    "image_path": "data/images/secondhand-000456.jpg",
    "attributes": {"type": "Blazer"},
}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(
        search_api, "load_listings", lambda **_kwargs: [BROWN_COAT, UNLABELED]
    )
    return TestClient(app)


def test_details_have_photo_labels_and_credit_but_no_price_or_link(client):
    response = client.get("/api/item/secondhand-000123")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "secondhand-000123"
    assert body["title"] == "Brown Jacket"
    assert body["image_url"] == "/api/local-images/secondhand-000123"
    assert body["source"] == "local"
    assert body["dataset_labels"] == {
        "type": "Jacket",
        "category": "Ladies",
        "colors": ["Brown"],
        "material": "100% bomull",
        "cut": "Regular",
        "pattern": "Plain",
        "brand": None,
    }
    assert body["credit"]["url"] == (
        "https://huggingface.co/datasets/fnauman/fashion-second-hand-front-only-rgb"
    )
    assert "CC BY 4.0" in body["credit"]["text"]
    # The rough price band is not a verified price, and archive items can't be bought.
    assert not {"price", "price_band", "listing_url"} & body.keys()


def test_no_searched_attributes_means_no_comparison(client):
    assert client.get("/api/item/secondhand-000123").json()["comparison"] == []


def test_comparison_maps_dataset_labels_onto_our_vocabulary(client):
    response = client.get(
        "/api/item/secondhand-000123",
        params={"category": "jacket", "color": "brown", "fabric": "cotton", "fit": "slim fit"},
    )
    rows = {row["attribute"]: row for row in response.json()["comparison"]}
    assert rows["category"] == {
        "attribute": "category",
        "yours": "jacket",
        "listing": "jacket",
        "match": True,
    }
    assert rows["color"]["match"] is True
    # "bomull" is Swedish for cotton (index.MATERIAL_ALIASES).
    assert rows["fabric"] == {
        "attribute": "fabric",
        "yours": "cotton",
        "listing": "cotton",
        "match": True,
    }
    assert rows["fit"] == {
        "attribute": "fit",
        "yours": "slim fit",
        "listing": "regular fit",
        "match": False,
    }


def test_color_families_count_as_a_match(client):
    response = client.get("/api/item/secondhand-000123", params={"color": "tan"})
    assert response.json()["comparison"][0]["match"] is False
    response = client.get("/api/item/secondhand-000123", params={"color": "brown"})
    assert response.json()["comparison"][0]["match"] is True


def test_missing_labels_are_unknown_not_a_mismatch(client):
    response = client.get(
        "/api/item/secondhand-000456", params={"color": "black", "fabric": "wool", "fit": "cropped"}
    )
    rows = response.json()["comparison"]
    assert [(r["attribute"], r["listing"], r["match"]) for r in rows] == [
        ("color", None, None),
        ("fabric", None, None),
        ("fit", None, None),
    ]
    assert response.json()["dataset_labels"]["colors"] == []


def test_unknown_id_is_404(client):
    response = client.get("/api/item/secondhand-999999")
    assert response.status_code == 404
    assert response.json() == {"detail": "Listing not found"}


def test_ebay_ids_are_never_stored_so_they_are_404(client):
    assert client.get("/api/item/v1%7C123456789%7C0").status_code == 404


def test_overlong_searched_value_is_rejected(client):
    response = client.get("/api/item/secondhand-000123", params={"color": "x" * 51})
    assert response.status_code == 422


def test_unreadable_local_data_is_a_safe_503(monkeypatch):
    def broken(**_kwargs):
        raise OSError("listings.jsonl missing")

    monkeypatch.setattr(search_api, "load_listings", broken)
    response = TestClient(app).get("/api/item/secondhand-000123")
    assert response.status_code == 503
    assert response.json() == {"detail": "Listing details unavailable"}
    assert "listings.jsonl" not in response.text
