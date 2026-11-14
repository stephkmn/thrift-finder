"""Live eBay re-ranking (S3-7) with a fake client, fake images and the fake encoder."""

from __future__ import annotations

import pytest

from backend.app.data.ebay_client import EbayAPIError
from backend.app.ml import live_search
from backend.app.schemas import Attributes
from backend.tests.fakes import FakeEncoder, FakeImage

ORIGINAL = Attributes(category="jacket", color="black", fabric="denim", fit="regular fit")
EDITED = ORIGINAL.model_copy(update={"color": "brown"})


def _listing(i, title, **overrides):
    return {
        "id": f"v1|{i}|0",
        "title": title,
        "price": 40.0 + i,
        "currency": "USD",
        "condition": "Pre-owned",
        "image_url": f"https://i.ebayimg.com/{i}.jpg",
        "listing_url": f"https://www.ebay.com/itm/{i}",
        "source": "ebay",
        **overrides,
    }


class FakeClient:
    def __init__(self, listings=None, error=None):
        self.listings = listings or []
        self.error = error
        self.calls = []

    def search(self, query, *, limit=5, used_only=True):
        self.calls.append((query, limit, used_only))
        if self.error:
            raise self.error
        return self.listings


@pytest.fixture
def encoder():
    return FakeEncoder()


def _images_from(listings):
    by_url = {item["image_url"]: FakeImage(item["title"]) for item in listings}
    return lambda url: by_url[url]


def _run(client, encoder, load_image, edited=EDITED):
    upload = encoder.encode_images([FakeImage("black denim regular fit jacket")])[0]
    return live_search.search_live_listings(
        client, encoder, upload, "image", ORIGINAL, edited, load_image=load_image
    )


def test_edit_steers_live_ranking_and_keeps_listing_fields(encoder):
    listings = [
        _listing(1, "red nylon parka"),
        _listing(2, "brown denim regular fit jacket"),
        _listing(3, "black denim regular fit jacket"),
    ]
    client = FakeClient(listings)
    matches = _run(client, encoder, _images_from(listings))
    assert matches[0].listing["title"] == "brown denim regular fit jacket"
    assert matches[0].listing["listing_url"] == "https://www.ebay.com/itm/2"
    assert all(0 <= m.match_score <= 100 for m in matches)
    query, limit, used_only = client.calls[0]
    assert query == "brown denim jacket regular fit"
    assert (limit, used_only) == (live_search.CANDIDATE_LIMIT, True)


def test_listings_without_image_or_link_are_dropped(encoder):
    listings = [
        _listing(1, "brown denim jacket", image_url=None),
        _listing(2, "brown denim jacket", listing_url=None),
        _listing(3, "brown denim jacket"),
    ]
    matches = _run(FakeClient(listings), encoder, _images_from(listings[2:]))
    assert [m.listing["id"] for m in matches] == ["v1|3|0"]


def test_broken_thumbnail_drops_only_that_listing(encoder):
    listings = [_listing(1, "brown denim jacket"), _listing(2, "brown wool coat")]
    good = _images_from(listings[1:])

    def load(url):
        if url.endswith("/1.jpg"):
            raise EbayAPIError("Listing image failed (HTTP 404)", 404)
        return good(url)

    matches = _run(FakeClient(listings), encoder, load)
    assert [m.listing["id"] for m in matches] == ["v1|2|0"]


def test_all_thumbnails_failing_returns_empty_for_fallback(encoder):
    def load(_url):
        raise EbayAPIError("Listing image connection failed")

    assert _run(FakeClient([_listing(1, "brown jacket")]), encoder, load) == []


def test_no_live_results_returns_empty(encoder):
    assert _run(FakeClient([]), encoder, _images_from([])) == []


def test_no_usable_keywords_skips_ebay(encoder):
    blank = Attributes(category="unknown", color="unknown", fabric="unknown", fit="unknown")
    client = FakeClient([_listing(1, "jacket")])
    assert _run(client, encoder, _images_from([]), edited=blank) == []
    assert client.calls == []


def test_ebay_errors_propagate_for_fallback_classification(encoder):
    client = FakeClient(error=EbayAPIError("Browse search failed (HTTP 429)", 429))
    with pytest.raises(EbayAPIError):
        _run(client, encoder, _images_from([]))


def test_top_k_is_respected(encoder):
    listings = [_listing(i, f"brown denim jacket {i}") for i in range(15)]
    assert len(_run(FakeClient(listings), encoder, _images_from(listings))) == 10


def test_thumbnail_is_decoded_in_memory(monkeypatch):
    import io

    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), "brown").save(buffer, format="JPEG")
    monkeypatch.setattr(live_search, "fetch_listing_image", lambda _url: buffer.getvalue())
    assert live_search.load_listing_image("https://i.ebayimg.com/a.jpg").size == (4, 4)


def test_undecodable_thumbnail_raises_ebay_error(monkeypatch):
    monkeypatch.setattr(live_search, "fetch_listing_image", lambda _url: b"not an image")
    with pytest.raises(EbayAPIError, match="decoded"):
        live_search.load_listing_image("https://i.ebayimg.com/a.jpg")
