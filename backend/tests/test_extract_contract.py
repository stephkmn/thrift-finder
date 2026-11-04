"""Contract tests for POST /api/extract.

Asserts the response matches ExtractResponse exactly and that frontend-expected
error codes (413 / 415 / 422) fire on the right inputs.
"""

from __future__ import annotations

import io

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.schemas import ExtractResponse

client = TestClient(app)

TINY_PNG = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\rIDATx\x9cc\xf8\xcf\xc0\x00\x00\x00\x03\x00\x01\x5a\x6a\x0b\xb3"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _post(files=None, data=None):
    return client.post("/api/extract", files=files, data=data)


def test_extract_with_image_returns_valid_contract():
    response = _post(files={"image": ("tiny.png", io.BytesIO(TINY_PNG), "image/png")})
    assert response.status_code == 200
    parsed = ExtractResponse.model_validate(response.json())
    assert parsed.query_id.startswith("stub-")
    assert parsed.attributes.others is not None
    assert set(parsed.confidences.others or {}) == set(parsed.attributes.others)


def test_extract_with_text_only_returns_valid_contract():
    response = _post(data={"text": "a black denim hooded jacket"})
    assert response.status_code == 200
    ExtractResponse.model_validate(response.json())


def test_extract_without_image_or_text_returns_422():
    response = _post()
    assert response.status_code == 422


def test_extract_with_blank_text_and_no_image_returns_422():
    response = _post(data={"text": "   "})
    assert response.status_code == 422


def test_extract_rejects_unsupported_media_type():
    response = _post(files={"image": ("garbage.bin", io.BytesIO(b"\x00\x01"), "application/octet-stream")})
    assert response.status_code == 415


def test_extract_rejects_oversized_image():
    big = b"\x00" * (10 * 1024 * 1024 + 1)
    response = _post(files={"image": ("big.png", io.BytesIO(big), "image/png")})
    assert response.status_code == 413


def test_query_id_is_unique_per_request():
    first = _post(data={"text": "red peacoat"}).json()["query_id"]
    second = _post(data={"text": "red peacoat"}).json()["query_id"]
    assert first != second
