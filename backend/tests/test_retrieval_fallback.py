"""S3-7 fallback tests: no credentials, network access, or FashionCLIP required."""

from __future__ import annotations

import pytest

from backend.app.data.retrieval_fallback import search_with_local_fallback


class MarketplaceError(Exception):
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


def classify(error: Exception):
    if isinstance(error, MarketplaceError) and error.status_code == 429:
        return "rate_limited"
    if isinstance(error, MarketplaceError) and error.status_code in (502, 503, 504):
        return "unavailable"
    return None


def test_no_live_provider_uses_local_only():
    outcome = search_with_local_fallback(local_search=lambda: ["local jacket"])
    assert outcome.results == ["local jacket"]
    assert outcome.source == "local"
    assert outcome.fallback_reason is None


def test_successful_live_results_do_not_run_local():
    def local():
        pytest.fail("local provider must not run when live succeeds")

    outcome = search_with_local_fallback(
        local_search=local,
        live_search=lambda: ["used eBay jacket"],
        classify_live_error=classify,
    )
    assert outcome.results == ["used eBay jacket"]
    assert outcome.source == "ebay"
    assert outcome.fallback_reason is None


@pytest.mark.parametrize(
    ("status_code", "reason"),
    [(429, "rate_limited"), (502, "unavailable"), (503, "unavailable"), (504, "unavailable")],
)
def test_expected_live_errors_fall_back_to_local(status_code, reason):
    def live():
        raise MarketplaceError(status_code)

    outcome = search_with_local_fallback(
        local_search=lambda: ["cached local jacket"],
        live_search=live,
        classify_live_error=classify,
    )
    assert outcome.results == ["cached local jacket"]
    assert outcome.source == "local"
    assert outcome.fallback_reason == reason


def test_no_live_results_fall_back_to_local():
    outcome = search_with_local_fallback(
        local_search=lambda: ["local coat"], live_search=lambda: []
    )
    assert (outcome.results, outcome.source, outcome.fallback_reason) == (
        ["local coat"], "local", "no_live_results"
    )


def test_no_local_results_are_an_empty_success_not_an_error():
    outcome = search_with_local_fallback(local_search=lambda: [], live_search=lambda: [])
    assert outcome.results == []
    assert outcome.source == "local"
    assert outcome.fallback_reason == "no_live_results"


def test_unexpected_marketplace_error_is_not_silently_hidden():
    def live():
        raise ValueError("bug in our integration")

    with pytest.raises(ValueError, match="bug in our integration"):
        search_with_local_fallback(
            local_search=lambda: ["should not be used"],
            live_search=live,
            classify_live_error=classify,
        )


def test_local_fallback_failure_propagates_to_api_layer():
    def live():
        raise MarketplaceError(429)

    def local():
        raise OSError("missing local embeddings")

    with pytest.raises(OSError, match="missing local embeddings"):
        search_with_local_fallback(
            local_search=local,
            live_search=live,
            classify_live_error=classify,
        )


def test_both_providers_limit_results():
    for live in (None, lambda: list(range(20))):
        outcome = search_with_local_fallback(
            local_search=lambda: list(range(20)),
            live_search=live,
            limit=3,
        )
        assert outcome.results == [0, 1, 2]


@pytest.mark.parametrize("limit", [0, -1, 11])
def test_invalid_limit_is_rejected(limit):
    with pytest.raises(ValueError, match="limit must be"):
        search_with_local_fallback(local_search=list, limit=limit)


def test_invalid_classifier_reason_does_not_mask_error():
    def live():
        raise MarketplaceError(429)

    with pytest.raises(MarketplaceError):
        search_with_local_fallback(
            local_search=list,
            live_search=live,
            classify_live_error=lambda _: "unexpected",
        )
