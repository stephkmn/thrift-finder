"""S3-4 API tests: text-only search, attribute edits, response contract, image serving.

Fake model/index dependencies keep CI independent of torch and downloaded data.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.app.api import search as search_api
from backend.app.cache import QueryCache, get_query_cache
from backend.app.main import app
from backend.app.ml.rerank import Match
from backend.app.schemas import Attributes, SearchResponse

ATTRS = {
    "category": "jacket",
    "color": "brown",
    "fabric": "leather",
    "fit": "regular fit",
    "others": None,
}
LISTING = {"id": "secondhand-0001", "title": "Brown Jacket", "image_path": "data/images/a.jpg"}


@pytest.fixture
def setup_search():
    cache = QueryCache(ttl_seconds=60, max_entries=10)
    seen = []

    def fake_runner(embedding, kind, original, edited):
        seen.append((embedding.copy(), kind, original, edited))
        return [Match(LISTING, 83.2)]

    app.dependency_overrides[get_query_cache] = lambda: cache
    app.dependency_overrides[search_api.get_search_runner] = lambda: fake_runner
    try:
        yield TestClient(app), cache, seen
    finally:
        app.dependency_overrides.clear()


def _body(query_id, *, edited=None, text=None):
    body = {
        "query_id": query_id,
        "original_attributes": ATTRS,
        "edited_attributes": edited or ATTRS,
    }
    if text is not None:
        body["text"] = text
    return body


def test_text_only_returns_real_contract_and_uses_text_embedding(setup_search):
    client, cache, seen = setup_search
    embedding = np.array([0.2, 0.8], dtype=np.float32)
    query_id = cache.put(embedding, "text")
    response = client.post("/api/search", json=_body(query_id, text="brown leather jacket"))
    assert response.status_code == 200
    parsed = SearchResponse.model_validate(response.json())
    assert len(parsed.results) == 1
    result = parsed.results[0]
    assert (result.id, result.title, result.match_score) == (
        "secondhand-0001", "Brown Jacket", 83.2
    )
    assert result.source == "local"
    assert result.image_url == "/api/local-images/secondhand-0001"
    assert result.price is None and result.listing_url is None
    np.testing.assert_array_equal(seen[0][0], embedding)
    assert seen[0][1] == "text"


def test_text_only_attribute_edit_is_passed_to_ranker(setup_search):
    client, cache, seen = setup_search
    edited = {**ATTRS, "color": "black", "others": ["hood"]}
    response = client.post("/api/search", json=_body(cache.put(np.ones(2), "text"), edited=edited))
    assert response.status_code == 200
    assert seen[0][2] == Attributes(**ATTRS)
    assert seen[0][3] == Attributes(**edited)


def test_image_mode_is_retained(setup_search):
    client, cache, seen = setup_search
    response = client.post("/api/search", json=_body(cache.put(np.ones(2), "image")))
    assert response.status_code == 200
    assert seen[0][1] == "image"


def test_missing_or_expired_query_id_returns_410_without_search(setup_search):
    client, _, seen = setup_search
    response = client.post("/api/search", json=_body("expired"))
    assert response.status_code == 410
    assert "expired" in response.json()["detail"]
    assert not seen


def test_bad_request_returns_422(setup_search):
    client, _, seen = setup_search
    assert client.post("/api/search", json={"query_id": "abc"}).status_code == 422
    assert not seen


def test_search_failure_is_user_safe(setup_search):
    client, cache, _ = setup_search

    def broken_runner(*_args):
        raise FileNotFoundError("private path to embeddings.npz")

    app.dependency_overrides[search_api.get_search_runner] = lambda: broken_runner
    response = client.post("/api/search", json=_body(cache.put(np.ones(2), "text")))
    assert response.status_code == 503
    assert "private path" not in str(response.json())


def test_empty_results_are_valid(setup_search):
    client, cache, _ = setup_search
    app.dependency_overrides[search_api.get_search_runner] = lambda: lambda *_: []
    response = client.post("/api/search", json=_body(cache.put(np.ones(2), "text")))
    assert response.status_code == 200
    assert response.json() == {"results": []}


def test_response_is_limited_to_ten_results(setup_search):
    client, cache, _ = setup_search

    def many(*_args):
        return [Match({**LISTING, "id": f"item-{i}"}, 75) for i in range(15)]

    app.dependency_overrides[search_api.get_search_runner] = lambda: many
    response = client.post("/api/search", json=_body(cache.put(np.ones(2), "text")))
    assert response.status_code == 200
    assert len(response.json()["results"]) == 10


def test_local_images_are_served_when_record_exists(tmp_path: Path, monkeypatch):
    jpg = tmp_path / "example.jpg"
    jpg.write_bytes(b"fakejpeg")
    monkeypatch.setattr(search_api, "_listing_image", lambda _id: jpg)
    response = TestClient(app).get("/api/local-images/secondhand-0001")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/jpeg")
    assert response.content == b"fakejpeg"


def test_unknown_image_returns_404(monkeypatch):
    monkeypatch.setattr(search_api, "_listing_image", lambda _id: None)
    response = TestClient(app).get("/api/local-images/unknown")
    assert response.status_code == 404


def test_local_image_lookup_rejects_paths_outside_image_directory(tmp_path, monkeypatch):
    data = tmp_path / "data" / "images"
    data.mkdir(parents=True)
    monkeypatch.setattr(search_api, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(search_api, "LOCAL_IMAGE_DIR", data.resolve())
    monkeypatch.setattr(
        search_api,
        "load_listings",
        lambda *, require_image: [{"id": "escaped", "image_path": "../secret.jpg"}],
    )
    assert search_api._listing_image("escaped") is None
