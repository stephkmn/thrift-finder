# Thrift Searcher

Outerwear attribute extraction and visual search. Upload a photo, edit attributes
(e.g. change black → brown, remove the hood), and get the top 10 matching listings
from eBay or a local fallback dataset.

> CECS 451 Term Project — Group 7 (Achal Mohandas · John Marquez · Quan Pham ·
> Stephanie Noe). Phase 2 plan: [`docs/PHASE2_SPRINT_PLAN.md`](docs/PHASE2_SPRINT_PLAN.md).
> Architecture: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Quickstart

```bash
git clone https://github.com/stephkmn/thrift-searcher.git
cd thrift-searcher

# Backend (Python 3.11)
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,ml,data]"   # ml = FashionCLIP (~600 MB download on first use)
cp .env.example .env              # defaults work; eBay keys only for DATA_SOURCE=ebay

# Local search index: 500 archive listings (train split) and their embeddings
python scripts/ingest.py --split train --limit 500
python scripts/build_embeddings.py     # ~50 s, once

uvicorn backend.app.main:app --reload  # http://localhost:8000

# Frontend (in a second terminal)
cd frontend
cp .env.example .env              # VITE_USE_MOCKS=false calls the backend
npm install
npm run dev                       # http://localhost:5173
```

Open the frontend URL, drop or paste a photo of a jacket, check the extracted attributes, edit one
(for example the color), and press **Update results**. The results come from the local archive and
show an **Archive** badge. For frontend work without the backend, set `VITE_USE_MOCKS=true` in
`frontend/.env` (mock `query_id`s start with `mock-`).

## Configuration

All config is via environment variables. Nothing secret lives in the repo.

| Variable | Scope | Values | Purpose |
|---|---|---|---|
| `DATA_SOURCE` | backend | `local` (default) · `ebay` | Search the local archive, or live used eBay listings with local fallback |
| `MODEL_NAME` | backend | HF repo id | ML model; default `patrickjohncyh/fashion-clip` |
| `MODEL_DTYPE` | backend | `float32` (default) · `float64` | Use `float64` only if the model returns NaN (macOS 14.2) |
| `PRELOAD_MODEL` | backend | `true` (default) · `false` | Load the model at startup instead of on the first upload |
| `QUERY_CACHE_TTL_SECONDS` | backend | int (default 1800) | How long an upload's embedding stays available to `/api/search` |
| `QUERY_CACHE_MAX_ENTRIES` | backend | int (default 256) | Max cached uploads; oldest evicted first |
| `EBAY_CLIENT_ID` | backend | string | Required only when `DATA_SOURCE=ebay` |
| `EBAY_CLIENT_SECRET` | backend | string | Required only when `DATA_SOURCE=ebay` |
| `EBAY_ENVIRONMENT` | backend | `production` (default) · `sandbox` | Live listings or eBay's test data |
| `VITE_USE_MOCKS` | frontend | `false` (in `.env.example`) · `true` | Call the backend, or use the in-browser mock |
| `VITE_MOCK_DELAY_MS` | frontend | int | Fake latency for the mock |

See [`.env.example`](.env.example) and [`frontend/.env.example`](frontend/.env.example).

## Run

- **Backend:** `uvicorn backend.app.main:app --reload` serves `/api/health`, `/api/extract`,
  `/api/search`, `/api/item/{id}` and `/api/local-images/{id}` on `:8000`.
- **Model:** `/api/extract` runs FashionCLIP, which needs the `ml` extra. Without it, the server still
  starts and `/api/extract` returns 503. If extraction fails with a NaN error, set `MODEL_DTYPE=float64`.
- **Index:** `/api/search` needs `data/listings.jsonl` and `data/embeddings.npz` (Quickstart); without
  them it returns 503. Rebuild the embeddings after re-ingesting or changing `MODEL_NAME`.
- **Backend + frontend:** two terminals as in the Quickstart. Vite proxies `/api/*` → `localhost:8000`
  (`frontend/vite.config.ts`).
- **Tests:** `pytest backend/tests -q` and, in `frontend/`, `npm test -- --run`
- **Lint:** `ruff check backend/ scripts/` and, in `frontend/`, `npm run lint` and `npm run format:check`

## Reproduce a sample

With the Quickstart's `ml` extra and local index in place:

```bash
python scripts/reproduce_sample.py
```

This runs the three photos in `samples/` through the same code as the app: attribute extraction,
the photo's scripted edit from `eval/queries.csv` (for example `shacket1-hung.JPG`: color red →
green), and edit-aware search over the local index. It prints the extracted attributes and the top
10 results, then compares them with `samples/expected_output.json`: the attributes must match
exactly and at least 8 of the 10 result titles must match (float32 and float64 can swap listings
with nearly tied scores). It exits with 0 when every sample matches. Pass one photo to run only
that one, e.g. `python scripts/reproduce_sample.py samples/shacket1-hung.JPG`.

To reproduce the evaluation numbers in [`docs/EVALUATION.md`](docs/EVALUATION.md) instead:

```bash
python scripts/ingest.py --split test --limit 300   # evaluation photos (test split)
python scripts/evaluate.py --sweep --out results.md --details details.csv
```

Five of the 38 evaluation photos are team photos kept out of the repository; without them the script
skips those queries and runs 33.

## Repository map

```
thrift-searcher/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI app (model preload at startup)
│   │   ├── api/routes.py      # /api/health, /api/extract
│   │   ├── api/search.py      # /api/search, /api/item/{id}, /api/local-images/{id}
│   │   ├── cache.py           # query_id → upload embedding, in memory, short TTL
│   │   ├── schemas.py         # Pydantic contract (mirrors frontend/src/api/types.ts)
│   │   ├── config.py          # env-var settings
│   │   ├── ml/                # Member A: encoder, attributes, query builder, re-ranker, index,
│   │   │                      #   evaluation; live eBay re-ranking (live_search.py)
│   │   └── data/              # Member B: local dataset, ingestion helpers, eBay client, keyword
│   │                          #   query builder and baseline, eBay → local fallback
│   └── tests/
├── frontend/                  # React + Vite + TypeScript UI (Member D); see frontend/README.md
├── docs/
│   ├── PHASE2_SPRINT_PLAN.md  # Sprint plan and backlog
│   ├── ARCHITECTURE.md        # System diagram, components, request flow
│   ├── AI_MODEL.md            # Model, prompts, edit arithmetic, re-ranker, limitations
│   ├── DATA.md                # Data sources, license, ingestion, eBay access
│   ├── EVALUATION.md          # Evaluation set and results
│   ├── DECISIONS.md           # Team decisions
│   ├── SEARCH_FALLBACK.md, TEXT_ONLY_SEARCH.md, KEYWORD_BASELINE.md, EBAY_FEASIBILITY.md
│   └── screenshots/
├── scripts/                   # ingest, build_embeddings, build_eval_set, evaluate,
│                              #   reproduce_sample, zero_shot_accuracy, keyword_baseline,
│                              #   ebay_preview, poc_search
├── samples/                   # 3 photos of Member D's own jackets + expected_output.json
├── eval/                      # Evaluation queries and labels; see docs/EVALUATION.md
├── data/                      # gitignored: listings.jsonl, images/, embeddings.npz, eval/
├── pyproject.toml
├── .env.example
└── .github/workflows/ci.yml   # ruff + pytest + gitleaks
```

## Status

| Feature | Status |
|---|---|
| Frontend upload UI with attribute card (photo and/or text, paste from clipboard) | Done (S1-9, S2-6, S3-6) |
| API contract (TypeScript + Pydantic) | Done (S1-4) |
| `GET /api/health` | Done (S1-8) |
| `POST /api/extract`: FashionCLIP zero-shot attributes + query cache | Done (S2-1) |
| CI (ruff + pytest + gitleaks) | Done (S2-8) |
| Local dataset ingestion (500 listings) + embedding index | Done (S2-2, S2-3) |
| `POST /api/search`: edit arithmetic + re-ranker over the local index, text-only search | Done (S2-4, S2-5, S3-4) |
| Live eBay search with fallback to the local index (`DATA_SOURCE=ebay`) | Done (S1-1, S3-7) |
| Attribute editor + results in UI | Done (S2-6, S2-7) |
| Pinterest/polaroid board (frames, hover-to-blur overlay, click → details page) | Done (S3-5, S3-6) |
| Details page + `GET /api/item/{id}` (archive details, "why it matched") | Done (S3-6) |
| Evaluation with baselines and tuning (`scripts/evaluate.py`, `docs/EVALUATION.md`) | Done (S3-1, S3-2, S3-3) |
| `scripts/reproduce_sample.py` + samples | Done (S4) |
| Architecture, model and data docs (`docs/`) | Done (S1-10, S3-8, S3-9) |

## Limitations

- **Zero-shot model, no training.** On the 38 evaluation queries: category 76%, color 63%,
  fabric 44%. Fit can't be read from photos (86%, the same as always answering "regular fit").
  See [`docs/EVALUATION.md`](docs/EVALUATION.md) and [`docs/AI_MODEL.md`](docs/AI_MODEL.md).
- **The local archive is small and unpriced.** 500 listings with no prices or purchase links; an
  edit can only find what the archive has (no suede, 9 cropped listings), and its "Blazer" label
  includes some non-outerwear (`docs/DATA.md`).
- **Live eBay needs your own keys** (`DATA_SOURCE=ebay`) and isn't evaluated: eBay results have
  no labels to score. Nothing from eBay is stored.
- Outerwear only (jackets, coats, blazers, parkas, vests). HEIC photos are rejected.
- No user accounts, saved boards, or persistent storage. Uploaded images are
  held in memory and discarded after each request; only the upload's embedding is
  kept, in memory, for up to 30 minutes so `/api/search` can reuse it.
