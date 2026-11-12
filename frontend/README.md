# Thrift Searcher — Frontend

React + TypeScript + Vite app for Thrift Searcher (CECS 451, Group 7). Owner: Member D (Frontend & Report Lead).

## Overview

**Built in S1-9:**

- Upload page: add a photo (drag-and-drop or file picker), an optional text description, or both.
- Client-side photo checks: JPG, PNG, or WebP only, 10 MB max, with a specific hint for iPhone HEIC photos.
- `extract()` API client for `POST /api/extract`, with a mock mode so the UI works before the backend exists.

**Built in S2-6 and S2-7:** the whole Sprint 2 flow on one page: upload → see attributes → edit → top 10.

- **Upload summary.** After a successful extract the form collapses into a summary (photo thumbnail and/or
  the description, plus the query ID). **Edit upload** re-opens the form pre-filled with the same photo and
  text (**Cancel** goes back); submitting runs extract again, which gives a new `query_id`, resets the editor,
  and runs a new search. **Start over** clears everything.
- **Attribute editor** (`AttributeEditor`): native selects for category, fabric, and fit; a color swatch
  picker built on radio buttons (arrow keys work, and the color name is always shown next to the swatch);
  other features as chips with a remove (×) button and an **Add feature** picker that offers only the
  features not already present. Removing the last feature sends `others: null`, never `[]`.
  - An edited attribute shows what the model said (e.g. "was black") with a **Reset** link; **Reset all**
    restores every model value.
  - **Double-check** marks an attribute whose model confidence is below 0.6, but only while it still holds
    the model's value. Confidence numbers are not shown in the editor.
  - Values the API returns that are not in the vocabulary are kept and shown as they are.
- **Search trigger: automatic first, then a button.** The first search runs as soon as extract succeeds,
  with `edited_attributes` equal to `original_attributes`. After that, edits do not search on their own:
  **Update results** sends the current edits. It is enabled only when the edits differ from the last
  successful search, and disabled while a search is running. The request carries the extract `query_id`,
  the model's attributes, the edited attributes, and the original description as `text` (left out when
  there was none). Responses from superseded searches are ignored.
- **Results grid** (`ResultsGrid`; a polaroid board since S3-5, below): up to 10 cards with the image (title
  as alt text), title, USD price or "Price unavailable" ("No price" since S3-5), a match-score bar with the
  rounded number, a source badge ("eBay" or "Archive (not for sale)"), and **View listing**, which opens the
  original listing in a new tab (`rel="noopener noreferrer"`). Cards with no `listing_url` have no link. While searching, skeleton cards
  show and "Finding matches…" is announced politely; zero results show a friendly empty message; errors
  show an alert with **Retry**, which resends the same request.

**Built in S3-5:** the results are a polaroid board, as the Phase 1 report describes it ("polaroid frames,
some details written on frame, hover to blur image for more details, clicking on picture takes you to details
page").

- **Layout.** On screens 60rem (960px) and wider, the board fills the left and the upload summary and
  attribute editor form a sidebar on the right, both starting on the same line. The board shows 5 polaroids
  per row once it is 46rem wide, so the top 10 is two rows. Narrower screens stack the summary, the editor,
  then the results, as before; the sidebar comes first in the page either way, so keyboard and screen-reader
  order don't change. The page is up to 90rem wide; the upload form keeps a 60rem cap.
- **Compact editor.** Colors are in three columns and Fabric and Fit share a line. **Update results** (with the
  "Your results don't include these edits yet" note) sticks to the bottom of the window whenever the editor
  runs past it, so it is always on screen; checked at 1280×800, 1366×768, 1440×900, 1920×1080, and on a phone.
- **Polaroids.** Each result is a white instant-photo frame taped to the board at a slight tilt (seven angles in
  rotation, so no polaroid matches the one beside or above it). The title, the price ("No price" for archive
  items), and the match score are written on the frame. Rank order still reads left to right, top to bottom. The loading
  skeletons use the same frame.
- **Hover to blur.** With a mouse, hovering a polaroid (or tabbing into it) straightens and lifts it, blurs the
  photo, and shows an overlay with the source badge, a match bar, and **View listing**. Touch screens have no
  hover, so there the source badge and **View listing** sit under the caption instead. The switch is CSS only
  (`@media (hover: hover) and (pointer: fine)`): the details exist once in the page, and screen readers read
  them in the same order either way. The match bar is decorative; the number on the frame is what gets read.
- **Click → details page.** `ResultsGrid` takes an optional `onOpenDetails(id)`. When it is passed, each photo
  becomes a button ("See details: <title>") and the overlay shows a "Click for details" hint. `UploadPage` does
  not pass it yet, so photos are not clickable until S3-6 adds the details page.

Screenshots (mock data): `docs/screenshots/s3-5-board-desktop.png` (1440×900 window),
`s3-5-board-hover.png`, and `s3-5-board-phone.png`.

**Planned next** (see `docs/PHASE2_SPRINT_PLAN.md`): details page (S3-6), which passes `onOpenDetails`.

The request/response types in `src/api/types.ts` are a **draft** of the S1-4 API contract and must be confirmed
against the backend's Pydantic schemas. `price` and `listing_url` are always present but `null` for local
archive items, which have no verified price or purchase link (`docs/DATA.md`).

## Prerequisites

- Node.js 20 or newer (`node -v`)
- npm (bundled with Node). Use npm only, so `package-lock.json` stays the single lockfile.

## Install

```sh
cd frontend
npm install
```

## Configure

```sh
cp .env.example .env
```

| Variable             | Default in `.env.example` | Meaning                                                                              |
| -------------------- | ------------------------- | ------------------------------------------------------------------------------------ |
| `VITE_USE_MOCKS`     | `true`                    | `true` serves API calls from `src/api/mocks/`. Anything else calls the real backend. |
| `VITE_MOCK_DELAY_MS` | `600`                     | Fake network latency for mock responses, in milliseconds.                            |

Never put secrets in frontend env files. Every `VITE_*` variable ends up in the public JavaScript bundle.
`.env` is gitignored; only `.env.example` is committed.

## Run with mocks

```sh
npm run dev
```

Open the URL Vite prints (usually http://localhost:5173). With `VITE_USE_MOCKS=true`, every extract returns
the fixture in `src/api/mocks/extract.json` (a black denim regular-fit jacket with a hood) after the configured
delay, with a fresh `query_id`, and every search is answered by the mock search below. `fetch` is never called.

## Mock search

`POST /api/search` is not built yet (S2-5, Members C and A), so search runs against a mock in
`src/api/mocks/`:

- **Pool** (`searchPool.ts`): 28 fake listings. Every attribute value comes from `attributes.yaml`. Titles are
  built from the attributes (e.g. "Brown suede trucker jacket") and images are generated SVG placeholders
  showing the item's color and category. No real photos, no external image hosts.
  - `source: "ebay"` items have a made-up USD price and a link to `https://example.com/mock-listing/<id>`.
  - `source: "local"` items have `price: null` and `listing_url: null`, like the real archive dataset.
- **Ranking** (`mockApi.ts`, equal-weight overlap, 0–100): 20 points each when `category`, `color`, `fabric`,
  and `fit` match the edited attributes, plus 20 × the Jaccard similarity of the `others` features (`null`
  counts as no features; two empty sets count as a full match). Sorted by score, ties by `id`; top 10
  returned. The mock-only `attributes` field is stripped, so responses match `SearchResponse` exactly.
- The pool is built around the extract fixture, so a single edit (black → brown, or removing the hood)
  visibly changes the top 10.

This only stands in for the real re-ranker (CLIP embeddings with edit arithmetic, plan §4.3).

## Attribute vocabulary (build step)

The editor's options come from the ML team's vocabulary file, `backend/app/ml/attributes.yaml`, read **at build
time**: a small inline plugin in `vite.config.ts` turns `*.yaml` imports into JSON modules (parsed with the
`yaml` package) for `npm run dev`, `npm run build`, and Vitest. `src/lib/vocabulary.ts` checks the shape and
exports the `values` lists for category, color, fabric, and fit plus the feature names (keys of
`others.features`), in file order. If the file's shape changes, the app fails to load with an error naming
the missing key. The dev server's file access (`server.fs.allow`) is widened by that one file only.

A change to `attributes.yaml` needs a frontend rebuild (or a dev-server reload). Every vocabulary color also
needs a swatch in `src/lib/colorSwatches.ts`; a test fails if one is missing.

## Run against the backend

1. Set `VITE_USE_MOCKS=false` in `.env`.
2. Start the FastAPI service on port 8000 (see the root `README.md`).
3. Run `npm run dev`. The Vite dev server proxies every `/api/*` request to `http://localhost:8000`, so no CORS
   setup is needed during development.

## Test, lint, format

| Command                | What it does                                      |
| ---------------------- | ------------------------------------------------- |
| `npm test`             | Vitest in watch mode (`npx vitest run` runs once) |
| `npm run typecheck`    | TypeScript project check, no output files         |
| `npm run lint`         | ESLint (with `eslint-config-prettier`)            |
| `npm run format`       | Prettier, rewrite files                           |
| `npm run format:check` | Prettier, report only                             |
| `npm run build`        | Typecheck, then production build into `dist/`     |

## Mock error scenarios

In mock mode, type one of these as the description (exactly, with nothing else):

| Description        | What happens                                                                                                                  |
| ------------------ | ----------------------------------------------------------------------------------------------------------------------------- |
| `__error__`        | Extract fails with a 500. The form shows the error and **Retry**.                                                             |
| `__search_error__` | Extract succeeds, then the search fails with a 500. The results show an alert with **Retry**, which resends the same request. |

## File map

| Path                          | Contents                                                                                 |
| ----------------------------- | ---------------------------------------------------------------------------------------- |
| `src/main.tsx`, `src/App.tsx` | Entry point and app shell (header + upload page)                                         |
| `src/api/`                    | Draft contract types, `ApiError`, and `extract()` / `search()` with the live/mock switch |
| `src/api/mocks/`              | Extract fixture, mock search pool and ranking, error triggers                            |
| `src/components/`             | `UploadForm`, `DropZone`, `UploadSummary`, `AttributeEditor`, `ResultsGrid`              |
| `src/pages/`                  | `UploadPage`: extract, editor, and search state (one page, no router)                    |
| `src/lib/`                    | Vocabulary loader, color swatches, attribute comparison, `useObjectUrl`, image checks    |
| `src/styles/`                 | `global.css`: design tokens (colors, spacing, type) and resets                           |
| `src/test/`                   | Vitest setup and tests                                                                   |

## Privacy

The selected photo exists only in memory: as a `File` in React state and as temporary object URLs for the
form preview and the summary thumbnail, each revoked when that view stops showing the photo (replace, remove,
Edit upload, Start over, or unmount). It is never written to `localStorage`, `sessionStorage`, IndexedDB, or
the console.

## Known limitations

- **Mock search only** until S2-5 lands `POST /api/search`. Results come from the 28-item fake pool and a
  simple overlap score, not CLIP re-ranking. Mock listings, prices, links, and images are all fake.
- Mock extract returns the same black denim jacket attributes, whatever you upload.
- Local archive items have no price and no listing link (shown as "No price" and "Archive (not for
  sale)"), because the fallback dataset has neither (`docs/DATA.md`).
- The description is sent with every search but cannot be edited in the editor; use **Edit upload**.
- HEIC/HEIF photos (the iPhone default) are rejected. Export them as JPG first.
- Polaroid photos are not clickable until S3-6 adds the details page. Until then, an archive item has nothing
  to focus with the keyboard, so keyboard users can't open its hover overlay; the only detail it hides is the
  "Archive (not for sale)" badge, which screen readers still read.
- The contract types are a draft until Members A and C confirm them.
- TypeScript is pinned to 6.0 because `typescript-eslint` does not support TypeScript 7 yet.
