# Thrift Searcher

Outerwear attribute extraction and visual search. Upload a photo, edit attributes
(e.g. change black → brown, remove the hood), and get the top 10 matching listings
from eBay or a local fallback dataset.

> CECS 451 Term Project — Group 7 (Achal Mohandas · John Marquez · Quan Pham ·
> Stephanie Noe). Phase 2 plan: [`docs/PHASE2_SPRINT_PLAN.md`](docs/PHASE2_SPRINT_PLAN.md).
> Architecture: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Quickstart

```bash
git clone https://github.com/<org>/thrift-finder.git
cd thrift-finder

# Backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env     # fill in values only if DATA_SOURCE=ebay
uvicorn backend.app.main:app --reload   # http://localhost:8000

# Frontend (in a second terminal)
cd frontend
cp .env.example .env
# edit VITE_USE_MOCKS=false to hit the real backend
npm install
npm run dev              # http://localhost:5173
```

Open the frontend URL in a browser, drop an image onto the upload zone, and
confirm the attributes come back with a `query_id` that does **not** start with
`mock-` (a `mock-` id means the frontend is still using its in-browser fixture).
The real model needs the `ml` extra; see [Run](#run).

## Configuration

All config is via environment variables. Nothing secret lives in the repo.

| Variable | Scope | Values | Purpose |
|---|---|---|---|
| `DATA_SOURCE` | backend | `local` (default) · `ebay` | Where listings come from |
| `MODEL_NAME` | backend | HF repo id | ML model; default `patrickjohncyh/fashion-clip` |
| `MODEL_DTYPE` | backend | `float32` (default) · `float64` | Use `float64` only if the model returns NaN (macOS 14.2) |
| `PRELOAD_MODEL` | backend | `true` (default) · `false` | Load the model at startup instead of on the first upload |
| `QUERY_CACHE_TTL_SECONDS` | backend | int (default 1800) | How long an upload's embedding stays available to `/api/search` |
| `QUERY_CACHE_MAX_ENTRIES` | backend | int (default 256) | Max cached uploads; oldest evicted first |
| `EBAY_CLIENT_ID` | backend | string | Required only when `DATA_SOURCE=ebay` |
| `EBAY_CLIENT_SECRET` | backend | string | Required only when `DATA_SOURCE=ebay` |
| `VITE_USE_MOCKS` | frontend | `true` (default) · `false` | Call backend vs. in-browser mock |
| `VITE_MOCK_DELAY_MS` | frontend | int | Fake latency for the mock |

See [`.env.example`](.env.example) and [`frontend/.env.example`](frontend/.env.example).

## Run

- **Backend only:** `uvicorn backend.app.main:app --reload` → serves `/api/health`, `/api/extract` on `:8000`.
- **Real model:** `/api/extract` runs FashionCLIP, which needs the `ml` extra: `pip install -e ".[dev,ml]"`.
  The first start downloads ~600 MB. Without it, the server still starts and `/api/extract` returns 503.
  If extraction fails with a NaN error, set `MODEL_DTYPE=float64` in `.env`.
- **Backend + frontend:** two terminals as in the Quickstart. Vite proxies `/api/*` → `localhost:8000` (`frontend/vite.config.ts`).
- **Tests:** `pytest backend/tests -q`
- **Lint:** `ruff check backend/`

## Reproduce a sample

> Scripted reproduction lands in Sprint 4 (S4 plan). For now the Quickstart flow
> above is the smoke test; it round-trips a photo through `POST /api/extract`
> and returns a schema-validated `ExtractResponse`.

Planned: `python scripts/reproduce_sample.py samples/jacket.jpg` compares output
against `samples/expected_output.json`.

## Repository map

```
thrift-finder/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI app factory
│   │   ├── api/routes.py      # /api/health, /api/extract, /api/search (planned)
│   │   ├── cache.py           # query_id → upload embedding, in memory, short TTL
│   │   ├── schemas.py         # Pydantic contract (mirrors frontend/src/api/types.ts)
│   │   ├── config.py          # env-var settings
│   │   ├── ml/                # Member A: encoder, attributes, query builder (query.py), rerank
│   │   └── data/              # Member B: eBay client, local dataset loader
│   └── tests/
├── frontend/                  # React + Vite + TypeScript UI (Member D)
├── docs/
│   ├── PHASE2_SPRINT_PLAN.md  # Sprint plan and backlog
│   ├── ARCHITECTURE.md        # System diagram and components
│   ├── AI_MODEL.md            # (planned S3-8) model, prompts, scoring
│   ├── DATA.md                # (planned S3-9) data sources and license
│   └── EVALUATION.md          # (planned S3-2) preliminary results
├── scripts/                   # ingest, build_embeddings, build_eval_set; (planned) reproduce_sample, evaluate
├── samples/                   # (planned S4) 3 photos of Member D's own jackets + expected_output.json
├── eval/                      # (planned S1-11) evaluation labels; see docs/EVALUATION.md
├── data/                      # gitignored except small README + sample set
├── pyproject.toml
├── .env.example
└── .github/workflows/ci.yml   # ruff + pytest + gitleaks
```

## Status

| Feature | Status |
|---|---|
| Frontend upload UI with attribute card | Done (S1-9) |
| API contract (TypeScript + Pydantic) | Done (S1-4, this PR) |
| `GET /api/health` | Done (S1-8) |
| `POST /api/extract` — stub returning contract-valid fixture | Done (S1-8) |
| CI (ruff + pytest + gitleaks) | Done (S2-8) |
| Architecture doc v1 | Done (S1-10) |
| `POST /api/extract` — real FashionCLIP model + query cache | Done (S2-1) |
| Ingestion pipeline (eBay + local) | Planned (S2-2, Member B) |
| `POST /api/search` with re-ranker | Planned (S2-5) |
| Attribute editor + results grid in UI | Partial (S2-6, S2-7 — UI done against mock search; real /api/search pending S2-5) |
| Pinterest/polaroid board (frames, hover-to-blur overlay, click → details page) | Done (S3-5, S3-6) |
| Details page + `GET /api/item/{id}` (archive details, "why it matched") | Done (S3-6) |
| Preliminary results + evaluation | Planned (S3-1…3) |
| `scripts/reproduce_sample.py` + samples | Planned (S4) |

## Limitations

- Attribute accuracy is preliminary (FashionCLIP zero-shot, untuned); see PR #3 for
  first numbers. Running the model needs the `ml` extra (see Run).
- No eBay traffic yet; `DATA_SOURCE=ebay` is accepted by config but not honored
  until S2-2 lands the client.
- Outerwear only (jackets, coats). Non-outerwear categories are explicitly out
  of scope for Phase 2.
- No user accounts, saved boards, or persistent storage. Uploaded images are
  held in memory and discarded after each request; only the upload's embedding is
  kept, in memory, for up to 30 minutes so `/api/search` can reuse it.
