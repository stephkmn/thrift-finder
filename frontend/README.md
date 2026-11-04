# Thrift Searcher — Frontend

React + TypeScript + Vite app for Thrift Searcher (CECS 451, Group 7). Owner: Member D (Frontend & Report Lead).

## Overview

**Built in S1-9 (this skeleton):**

- Upload page: add a photo (drag-and-drop or file picker), an optional text description, or both.
- Client-side photo checks: JPG, PNG, or WebP only, 10 MB max, with a specific hint for iPhone HEIC photos.
- `extract()` API client for `POST /api/extract`, with a mock mode so the UI works before the backend exists.
- Loading, error (with Retry), and success states. On success, a read-only card lists the extracted
  attributes (category, color, fabric, fit) with confidence bars and percentages, plus any other
  features found (`others`, e.g. hood) as chips with their own scores, or "None detected".

**Planned next** (see `docs/PHASE2_SPRINT_PLAN.md`): attribute editor (S2-6), results grid (S2-7), polaroid
results board (S3-5), details page (S3-6).

The request/response types in `src/api/types.ts` are a **draft** of the S1-4 API contract and must be confirmed
against the backend's Pydantic schemas.

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

Open the URL Vite prints (usually http://localhost:5173). With `VITE_USE_MOCKS=true`, every submission returns
the fixture in `src/api/mocks/extract.json` after the configured delay, with a fresh `query_id`.

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

## Mock error scenario

In mock mode, submit the description text **`__error__`** (exactly, with nothing else) to make the mock API fail
with a 500. The page shows the error message and a **Retry** button. Use this to demo or test the error state.

## File map

| Path                          | Contents                                                                    |
| ----------------------------- | --------------------------------------------------------------------------- |
| `src/main.tsx`, `src/App.tsx` | Entry point and app shell (header + upload page)                            |
| `src/api/`                    | Draft contract types, `ApiError`, and `extract()` with the live/mock switch |
| `src/api/mocks/`              | Fixture response and the mock API (fake delay, `__error__` scenario)        |
| `src/components/`             | `UploadForm`, `DropZone`, `AttributeCard`, each with its CSS Module         |
| `src/pages/`                  | `UploadPage`, which owns request state (idle, loading, success, error)      |
| `src/lib/`                    | `validateImage` (type and size checks)                                      |
| `src/styles/`                 | `global.css`: design tokens (colors, spacing, type) and resets              |
| `src/test/`                   | Vitest setup and tests                                                      |

## Privacy

The selected photo exists only in memory: as a `File` in React state and as a temporary object URL for the
preview, which is revoked when the photo is replaced, removed, or the page unmounts. It is never written to
`localStorage`, `sessionStorage`, IndexedDB, or the console.

## Known limitations

- Mock data only: every mock submission returns the same black denim jacket attributes, whatever you upload.
- HEIC/HEIF photos (the iPhone default) are rejected. Export them as JPG first.
- No attribute editing, search, or results yet (Sprint 2).
- The contract types are a draft until Members A and C confirm them.
- TypeScript is pinned to 6.0 because `typescript-eslint` does not support TypeScript 7 yet.
