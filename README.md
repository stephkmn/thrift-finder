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
confirm the attribute card renders a response whose `query_id` starts with
`stub-` (backend) rather than `mock-` (frontend-only fixture).

## Configuration

All config is via environment variables. Nothing secret lives in the repo.

| Variable | Scope | Values | Purpose |
|---|---|---|---|
| `DATA_SOURCE` | backend | `local` (default) · `ebay` | Where listings come from |
| `MODEL_NAME` | backend | HF repo id | ML model; default `patrickjohncyh/fashion-clip` |
| `EBAY_CLIENT_ID` | backend | string | Required only when `DATA_SOURCE=ebay` |
| `EBAY_CLIENT_SECRET` | backend | string | Required only when `DATA_SOURCE=ebay` |
| `VITE_USE_MOCKS` | frontend | `true` (default) · `false` | Call backend vs. in-browser mock |
| `VITE_MOCK_DELAY_MS` | frontend | int | Fake latency for the mock |

See [`.env.example`](.env.example) and [`frontend/.env.example`](frontend/.env.example).

## Run

- **Backend only:** `uvicorn backend.app.main:app --reload` → serves `/api/health`, `/api/extract` on `:8000`.
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
│   │   ├── api/routes.py      # /api/health, /api/extract (stub), /api/search (planned)
│   │   ├── cache.py           # (planned S2-1) query_id → upload embedding, short TTL
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
├── scripts/                   # (planned S4) ingest, build_embeddings, reproduce_sample, evaluate
├── samples/                   # (planned S4) 3 team-owned sample images + expected_output.json
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
| `POST /api/extract` — real CLIP/FashionCLIP model | Planned (S2-1, Member A) |
| Ingestion pipeline (eBay + local) | Planned (S2-2, Member B) |
| `POST /api/search` with re-ranker | Planned (S2-5) |
| Attribute editor + results grid in UI | Planned (S2-6, S2-7) |
| Pinterest/polaroid board + details page | Planned (S3-5, S3-6) |
| Preliminary results + evaluation | Planned (S3-1…3) |
| `scripts/reproduce_sample.py` + samples | Planned (S4) |

## Limitations

- The current `/api/extract` is a deterministic stub, not a real model. Member A
  replaces the handler body in S2-1.
- No eBay traffic yet; `DATA_SOURCE=ebay` is accepted by config but not honored
  until S2-2 lands the client.
- Outerwear only (jackets, coats). Non-outerwear categories are explicitly out
  of scope for Phase 2.
- No user accounts, saved boards, or persistent storage. Uploaded images are
  held in memory and discarded after each request.
