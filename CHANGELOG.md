# Changelog

Notable changes in each tagged version of Thrift Searcher, grouped by pull request. Dates are when
the tagged commit was merged. `v0.1-poc` and `v0.3-mvp` were tagged after the fact (Nov 20) on the
commits listed, following the plan in `docs/PHASE2_SPRINT_PLAN.md` §7.

## v1.0-phase2 (2026-11-20)

Phase 2 submission: the full MVP.

### Added

- Polaroid results board: tilted frames with title, price and match score, hover overlay, five
  columns on wide screens (S3-5, #22).
- Details page and `GET /api/item/{id}`: dataset labels and a "why it matched" comparison for
  archive items, eBay details from the search result, browser Back support; paste a photo from the
  clipboard; dataset credit under the board (S3-6, #23).
- Results on all 38 evaluation queries, the tuning decision and `docs/AI_MODEL.md` (S3-1, S3-8, #24).
- `scripts/reproduce_sample.py` with `samples/expected_output.json` (S4, #25).

### Changed

- Fit reports a value other than "regular fit" only at 0.99 confidence, up from 0.9 (#24).
- README, ARCHITECTURE, DATA and EVALUATION describe the current code (#25).
- `frontend/.env.example` sets `VITE_USE_MOCKS=false`, so the frontend calls the backend by default
  (221f450).

## v0.3-mvp (2026-11-13)

Live eBay search and the evaluation harness.

### Added

- Live eBay search in `/api/search` (`DATA_SOURCE=ebay`): up to 20 used listings re-ranked in
  memory with FashionCLIP, with fallback to the local index; nothing from eBay is stored (S3-7, #20).
- `scripts/evaluate.py` with keyword-only and image-only baselines, label-based P@10 and a tuning
  sweep (S3-2, S3-3, #21).
- Read-only eBay Browse client and `scripts/ebay_preview.py`, with verified API access (S1-1, #15).
- Data pipeline, preprocessing and privacy documentation in `docs/DATA.md` (S3-9, #18).

### Changed

- Fit defaults to "regular fit"; dataset materials are normalized (e.g. "bomull" → cotton); the
  index refuses to load when it is stale (#21).

### Fixed

- `scripts/ebay_preview.py` loads credentials from the local `.env` (#19).

## v0.2-mvp-alpha (2026-11-12)

Thin MVP: photo → attributes → edited search over the local index, end to end.

### Added

- Ingestion of 500 outerwear listings from the Second-Hand Fashion dataset (S2-2, #4).
- Attribute → keyword query builder for eBay retrieval (S2-4, #5).
- Attribute editor and results grid with loading, empty and error states (S2-6, S2-7, #6).
- Real `POST /api/extract` with FashionCLIP, an in-memory query cache and model preload (S2-1, #7).
- Edit arithmetic, the listing embedding index and the calibrated re-ranker (S2-3, S2-4, S2-5, #8).
- The 38-query evaluation set and separate test-split ingestion (S1-11, #9, #10, #13).
- eBay developer access notes (S1-1, #11) and the keyword-only baseline (S3-3, #12).
- Text-only search, the `POST /api/search` route and local image serving (S3-4, #16).
- Reusable eBay → local fallback logic (S3-7, #17).

### Fixed

- iPhone "Most Compatible" photos (MPO) are accepted by `/api/extract` (#14).

## v0.1-poc (2026-11-06)

Proof of concept: a photo goes in, attributes and similar images come out.

### Added

- Frontend skeleton: upload page, draft API contract types and the in-browser mock (S1-9, #1).
- FastAPI scaffold with `/api/health` and a stubbed `/api/extract`, CI (ruff, pytest, gitleaks),
  pull request template, README and `docs/ARCHITECTURE.md` v1 (S1-3, S1-8, S1-10, S2-8, #2).
- FashionCLIP zero-shot attribute extraction, the attribute vocabulary and the command-line proof
  of concept `scripts/poc_search.py` (S1-5, S1-6, S1-7, #3).
