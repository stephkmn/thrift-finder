<!-- Title format per sprint plan §9: "S<sprint>-<id>: <short description>" e.g. "S2-5: search endpoint v1" -->

## Summary
<!-- 1-3 bullets describing the change. Link to the backlog ID in docs/PHASE2_SPRINT_PLAN.md. -->

- Backlog ID:
- Sprint:

## Changes


## Test plan
<!-- How you verified this locally. Check all that apply. -->

- [ ] `pytest backend/tests -q` passes
- [ ] `ruff check backend/` passes
- [ ] Frontend integration smoke: set `VITE_USE_MOCKS=false`, upload a photo, confirm the UI renders the backend response
- [ ] New or changed behavior is covered by a unit test
- [ ] Documentation updated where relevant (README, ARCHITECTURE, AI_MODEL, DATA, EVALUATION)

## Safety checklist

- [ ] No API keys, secrets, or private data in code, tests, fixtures, or history
- [ ] `.env` is gitignored; new env vars are added to `.env.example` with no real values
- [ ] If the API contract (`frontend/src/api/types.ts` / `backend/app/schemas.py`) changed, the other side was updated in the same PR

## Reviewer notes
