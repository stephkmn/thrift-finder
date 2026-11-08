"""Contract tests for POST /api/extract.

Asserts the response matches ExtractResponse exactly, that the upload's embedding is
cached under query_id, and that frontend-expected error codes (413 / 415 / 422 / 503)
fire on the right inputs. A fake extractor stands in for the model, so CI needs no torch.
"""

from __future__ import annotations

import io

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.app.api.routes import get_extractor_loader
from backend.app.cache import QueryCache, get_query_cache
from backend.app.main import app
from backend.app.ml.attributes import Extraction
from backend.app.schemas import Attributes, Confidences, ExtractResponse

EMBEDDING = np.linspace(0.0, 1.0, 8, dtype=np.float32)


def _png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), "black").save(buffer, format="PNG")
    return buffer.getvalue()


PNG = _png_bytes()


class FakeExtractor:
    """Records each call and returns a fixed, contract-valid extraction."""

    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[dict] = []
        self.error = error

    def extract(self, image=None, text=None) -> Extraction:
        self.calls.append({"image": image, "text": text})
        if self.error is not None:
            raise self.error
        return Extraction(
            Attributes(
                category="jacket", color="black", fabric="denim", fit="regular fit", others=["hood"]
            ),
            Confidences(category=0.9, color=0.8, fabric=0.7, fit=0.6, others={"hood": 0.85}),
            EMBEDDING,
        )


@pytest.fixture
def extractor():
    return FakeExtractor()


@pytest.fixture
def cache():
    return QueryCache(ttl_seconds=60, max_entries=16)


@pytest.fixture
def client(extractor, cache):
    app.dependency_overrides[get_extractor_loader] = lambda: lambda: extractor
    app.dependency_overrides[get_query_cache] = lambda: cache
    yield TestClient(app)
    app.dependency_overrides.clear()


def _post(client, files=None, data=None):
    return client.post("/api/extract", files=files, data=data)


def _image(content=PNG, content_type="image/png"):
    return {"image": ("photo.png", io.BytesIO(content), content_type)}


def test_extract_with_image_returns_valid_contract_and_caches_image_embedding(
    client, extractor, cache
):
    response = _post(client, files=_image())
    assert response.status_code == 200
    parsed = ExtractResponse.model_validate(response.json())
    assert parsed.attributes.fit == "regular fit"
    assert set(parsed.confidences.others or {}) == set(parsed.attributes.others or [])

    assert isinstance(extractor.calls[0]["image"], Image.Image)
    assert extractor.calls[0]["text"] is None

    entry = cache.get(parsed.query_id)
    assert entry is not None
    assert entry.kind == "image"
    np.testing.assert_array_equal(entry.embedding, EMBEDDING)


def test_extract_with_text_only_caches_text_embedding(client, extractor, cache):
    response = _post(client, data={"text": "  a black denim hooded jacket  "})
    assert response.status_code == 200
    parsed = ExtractResponse.model_validate(response.json())

    assert extractor.calls[0] == {"image": None, "text": "a black denim hooded jacket"}
    entry = cache.get(parsed.query_id)
    assert entry is not None
    assert entry.kind == "text"


def test_extract_with_image_and_text_passes_both(client, extractor, cache):
    response = _post(client, files=_image(), data={"text": "brown suede"})
    assert response.status_code == 200
    call = extractor.calls[0]
    assert isinstance(call["image"], Image.Image)
    assert call["text"] == "brown suede"
    assert cache.get(response.json()["query_id"]).kind == "image"


def test_extract_without_image_or_text_returns_422(client, extractor):
    response = _post(client)
    assert response.status_code == 422
    assert extractor.calls == []


def test_extract_with_blank_text_and_no_image_returns_422(client):
    response = _post(client, data={"text": "   "})
    assert response.status_code == 422


def test_extract_rejects_unsupported_media_type(client):
    response = _post(client, files=_image(b"\x00\x01", "application/octet-stream"))
    assert response.status_code == 415


def test_extract_rejects_oversized_image(client):
    big = b"\x00" * (10 * 1024 * 1024 + 1)
    response = _post(client, files=_image(big))
    assert response.status_code == 413


def test_extract_rejects_undecodable_image_with_422(client, extractor):
    response = _post(client, files=_image(b"definitely not a png"))
    assert response.status_code == 422
    assert extractor.calls == []


@pytest.mark.parametrize("error", [ImportError("no torch"), RuntimeError("NaN embeddings")])
def test_extract_returns_503_when_model_fails(client, extractor, error):
    extractor.error = error
    response = _post(client, data={"text": "red peacoat"})
    assert response.status_code == 503


def test_extract_returns_503_when_model_cannot_load(cache):
    def broken_loader():
        raise ImportError("No module named 'torch'")

    app.dependency_overrides[get_extractor_loader] = lambda: broken_loader
    app.dependency_overrides[get_query_cache] = lambda: cache
    try:
        response = TestClient(app).post("/api/extract", data={"text": "red peacoat"})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 503
    assert len(cache) == 0


def test_query_id_is_unique_per_request(client):
    first = _post(client, data={"text": "red peacoat"}).json()["query_id"]
    second = _post(client, data={"text": "red peacoat"}).json()["query_id"]
    assert first != second
