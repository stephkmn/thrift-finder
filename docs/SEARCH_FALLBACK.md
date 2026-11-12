# S3-7 — Local retrieval fallback (Member B component)

**Owners:** Members B (data-source fallback) and C (API integration). **Status:** isolated
helper implemented; real `/api/search` and browser fallback handling still require
coordination with Members C and D.

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

The API owner must supply a `classify_live_error` callback for known eBay error
conditions. The pending S1-1 `EbayAPIError` currently carries a safe message but
not a structured `status_code`, so **HTTP 429 classification needs a small
adapter or typed error update** when both PRs are merged. Do not parse or
persist raw OAuth response bodies.

The client should show a friendly notice when falling back. This helper returns
`fallback_reason` for that purpose, but does not yet modify the API response
schema or UI. The Backend/Frontend owners should agree on how to convey it.

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
FashionCLIP model downloads. The helper should be integrated only after the
search endpoint and eBay client branches are merged or with a coordinated PR.
