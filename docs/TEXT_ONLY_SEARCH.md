# S3-4 — Text-only local search

**Base:** `thrift-finder-main (5).zip` (November 12, 2026).  **Owners:** Member B + Member C.

The frontend already accepts a text description without a photo, and posts that text to
`POST /api/extract`. The extractor creates an embedding tagged `kind="text"` in the in-memory
query cache. The new `POST /api/search` route retrieves that cached embedding and calls the
existing `search_listings` FashionCLIP ranker. It returns up to 10 local archival results,
with image URLs served through `GET /api/local-images/{listing_id}`.

## Why the request contains `text`

The UI sends the original optional description with its search request for parity with the
contract. The cached embedding and extracted attributes are authoritative; `text` is not
re-encoded at the search step. Edits are passed as `edited_attributes` to the existing
model's query builder, which handles text-only and image queries differently. A new text
query requires a new extract request.

## Run the backend and browser UI

From the project root, with `data/listings.jsonl`, `data/images/`, and `data/embeddings.npz`
already generated and compatible with `MODEL_NAME`:

```bash
python -m pip install -e '.[dev,ml]'
PYTHONPATH=. python -m uvicorn backend.app.main:app --port 8000 --reload
```

In another terminal:

```bash
cd frontend
npm ci
# Set VITE_USE_MOCKS=false in frontend/.env (frontend/.env.example defaults to true).
npm run dev
```

At `http://localhost:5173`, submit **brown leather jacket** with no image. The editor should
show extracted attributes and the results grid should show real local clothing photos.
Change **brown** to **black** and select **Update results**; ranking should be recalculated.

The local archive has no current sale prices or purchase links. Both fields are `null`
rather than invented. With `DATA_SOURCE=ebay`, the same text-only query is answered by live
eBay listings instead, with the local archive as the fallback (see `docs/SEARCH_FALLBACK.md`).

## Tests

```bash
python -m pytest backend/tests/test_text_search_api.py -q
python -m pytest backend/tests -q
python -m ruff check backend/ scripts/
```

Tests replace the model/index with an injected fake; they do not download FashionCLIP.

## Remaining S3-7 work

The route returns 410 for an expired query ID and 503 for an unavailable local index/model.
S3-7 still needs frontend-specific handling for those errors and any eBay API rate-limit
fallback, coordinated with Member C. This PR does not claim S3-7 is complete.
