# S3-7 — Local retrieval fallback (Member B component)

**Owners:** Members B (data-source fallback) and C (API integration). **Status:** wired into
`POST /api/search` (`backend/app/api/search.py`). Showing a fallback notice in the UI is
still open (Member D).

To use live eBay results, set `DATA_SOURCE=ebay` plus `EBAY_CLIENT_ID` /
`EBAY_CLIENT_SECRET` (and optionally `EBAY_ENVIRONMENT=sandbox`) in `.env`. With
`DATA_SOURCE=local` or missing credentials, the local index is used directly.

## Scope and approach

`backend/app/data/retrieval_fallback.py` exposes `search_with_local_fallback`.
The backend can inject two providers:

1. A live eBay Browse search, if enabled and authorized. This provider is optional.
2. A local search over the existing licensed 500-item FashionCLIP embedding index.

The local index is the **precomputed fallback**, not a cache of eBay data. The
helper never persists marketplace responses, tokens, or listing records, which
is important because the eBay keyset received an exemption for **not persisting
eBay data**.

| Case | Behavior | Reason in outcome |
|---|---|---|
| Live search works | Return live results | `None` |
| Live HTTP 429 / provider rate limit | Return local results | `rate_limited` |
| Live timeout / gateway unavailable | Return local results | `unavailable` |
| Live returns zero listings | Return local results | `no_live_results` |
| Live integration disabled | Use local results directly | `None` |
| Local returns no listings | Return `[]` (valid empty state) | Case-dependent |
| Unexpected coding error | Propagate for diagnosis | No fallback |
| Both providers unavailable | Propagate local failure to API layer | Existing safe 503 |

`search.classify_ebay_error` maps `EbayAPIError.status_code`: 429 → `rate_limited`;
any other eBay HTTP, connection or malformed-response error → `unavailable`. Other
exceptions are not hidden and end in the safe 503. The fallback reason is logged
(reason only, never the eBay response). Do not parse or persist raw OAuth response bodies.

The UI can already tell live and fallback results apart by each result's `source`
(`"ebay"` vs `"local"`). A dedicated fallback notice would need a new response field
in `schemas.py` and `types.ts`; not added yet.

Bad-image errors (413/415/422) are already validated by `POST /api/extract`;
expired query IDs (410) and local model/index failures (503) are handled by the
S3-4 `/api/search` implementation. UI wording and manual end-to-end verification
remain shared S3-7 tasks.

## Run the tests

```bash
python -m pytest backend/tests/test_retrieval_fallback.py -q
python -m pytest backend/tests -q
python -m ruff check backend/ scripts/
```

Tests use fake providers and do not need eBay credentials, live requests, or
FashionCLIP model downloads. `backend/tests/test_live_search_api.py` covers the endpoint
fallback cases, and `backend/tests/conftest.py` forces `DATA_SOURCE=local` so tests never
call eBay even if your `.env` enables it.
