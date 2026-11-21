# Architecture — Thrift Searcher (v1)

This document is the v1 architecture per Sprint 1 task S1-10. It will be refined
in Sprint 3 (S3-10) once the ML and data modules are integrated. The authoritative
diagram is also embedded in `docs/PHASE2_SPRINT_PLAN.md` §4.2; keep the two in sync.

## System diagram

```mermaid
flowchart LR
  U[User] -->|photo + optional text| FE[React UI<br/>frontend/src/]

  ENC[CLIP / FashionCLIP encoder<br/>backend/app/ml/encoder.py<br/>image + text towers]

  subgraph EXTRACT["① POST /api/extract — backend/app/api/routes.py"]
    ATTR[Zero-shot attribute extractor<br/>backend/app/ml/attributes.py]
    CACHE[(Query cache, short TTL<br/>query_id → E_img upload<br/>backend/app/cache.py)]
  end

  subgraph SEARCH["② POST /api/search — backend/app/api/routes.py"]
    QB[Query builder<br/>backend/app/ml/query.py<br/>keywords: backend/app/data/query_keywords.py]
    RET[Candidate retrieval<br/>backend/app/data/]
    RR[Multimodal re-ranker<br/>backend/app/ml/rerank.py]
  end

  FE -->|"① image + text"| ENC
  ENC -->|"E_img, E_txt"| ATTR
  ENC -->|E_img upload| CACHE
  ATTR -->|"attributes + confidences + query_id"| FE

  FE -->|"② query_id + original & edited attrs + text"| QB
  CACHE -->|E_img upload| QB
  QB <-.->|"E_txt(edited), E_txt(original)"| ENC
  QB -->|"keywords (eBay only)"| RET
  RET -->|live| EBAY[(eBay Browse API<br/>backend/app/data/ebay_client.py)]
  RET -->|"local fallback: every listing"| DS[(Local listings + precomputed embeddings<br/>backend/app/data/local_dataset.py<br/>backend/app/ml/index.py)]
  RET <-.->|embed new live listings| ENC
  RET -->|candidates + embeddings| RR
  QB -->|"q_img, q_txt"| RR
  RR -->|top 10 + match scores| FE
```

## Components

| Component | Path | Owner | Status (Nov 10) |
|---|---|---|---|
| React UI | `frontend/src/` | D | Done (S1-9, S2-6, S2-7, S3-5 polaroid board, S3-6 details page); mock mode (`VITE_USE_MOCKS`) still available |
| FastAPI app | `backend/app/main.py` | C | Done (this PR) |
| API contract (schemas) | `backend/app/schemas.py` ↔ `frontend/src/api/types.ts` | C + D | Done (this PR) |
| Encoder (CLIP / FashionCLIP) | `backend/app/ml/encoder.py` | A | Done (S1-5); wired into `/api/extract` (S2-1) |
| Zero-shot attribute extractor | `backend/app/ml/attributes.py` + `attributes.yaml` | A | Done (S1-5, S1-6); wired into `/api/extract` (S2-1) |
| Query builder | `backend/app/ml/query.py` (edit arithmetic) + `backend/app/data/query_keywords.py` (keywords) | A + B | Done (S2-4); keywords are for eBay retrieval only |
| eBay Browse client | `backend/app/data/ebay_client.py` | B | Done (S1-1) |
| Live eBay re-ranking + fallback | `backend/app/ml/live_search.py`, `backend/app/data/retrieval_fallback.py`, `backend/app/api/search.py` | C + B | Done (S3-7) |
| Local dataset loader | `backend/app/data/local_dataset.py` | B | Done (S2-2): 500 CC BY 4.0 listings, see `docs/DATA.md` |
| Listing embedding index | `backend/app/ml/index.py` + `scripts/build_embeddings.py` | A | Done (S2-3) |
| Re-ranker | `backend/app/ml/rerank.py` | A | Done (S2-5, ML side): `search_listings()`; the `/api/search` route is pending (C) |
| Embedding cache | `backend/app/cache.py` | C | Done (S2-1): in-memory, TTL + size cap, records `image`/`text` embedding kind |

## Request flow

1. **`POST /api/extract`** — multipart form (`image` + optional `text`). FastAPI validates size/MIME, streams the image into memory (never to disk per privacy commitment in sprint plan §4.2), calls `ml.attributes.extract_attributes(...)`, stores the query embedding in a short-lived in-memory cache keyed by a freshly generated `query_id`, and returns `ExtractResponse`.
2. **`POST /api/search`** — `SearchRequest` with `query_id` + `original_attributes` + `edited_attributes` + optional `text`. The query builder derives a text embedding from the edits (`q_img = normalize(E_img(upload) + λ · (E_txt(edited) − E_txt(original)))`), candidates come from eBay (`DATA_SOURCE=ebay`: up to 20 used listings retrieved with keywords from `backend/app/data/query_keywords.py`, their thumbnails and titles embedded in memory per request, ~2–3 s; if eBay is rate-limited, down or returns nothing, the local index answers instead) or, for the local fallback (`DATA_SOURCE=local`), are every listing in the precomputed embedding index with no keyword filter (500 listings rank in ~60 ms), and the re-ranker returns up to 10 `SearchResult`s with `match_score` rescaled to 0–100.
3. **`GET /api/item/{id}`** — details for the frontend details page (S3-6), archive items only: the dataset's labels, the CC BY 4.0 credit, and, when the searched `category`/`color`/`fabric`/`fit` are passed as query parameters, a "why it matched" row per attribute. Matches are judged with `backend/app/ml/evaluation.py` (`type_matches`, `edit_satisfied`) on `listing_labels()`, so the page and the evaluation agree. eBay ids return 404 because eBay data is never stored; the frontend builds eBay details from the search result.
4. **`GET /api/health`** — liveness probe for CI and local smoke tests.

## Privacy & secrets

- Uploaded images are read into a `bytes` buffer and discarded after the handler returns. No disk writes, no logging of image bytes.
- `query_id` maps to an ephemeral in-memory embedding entry with a short TTL; nothing is persisted across process restarts.
- Credentials (`EBAY_CLIENT_ID`, `EBAY_CLIENT_SECRET`) come from environment variables via `backend/app/config.py` (pydantic-settings). `.env` is gitignored; `.env.example` lists the variable names only.

## Dev proxy

The Vite dev server proxies `/api/*` → `http://localhost:8000` (see `frontend/vite.config.ts`), so FastAPI does **not** need CORS middleware during development.
