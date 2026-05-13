# Sprint 4 — Deployment + Missing Pages

**Date:** 2026-05-13
**Scope:** Deploy to Railway (backend) + Vercel (frontend), add three missing frontend pages, add two backend API endpoints.

---

## 1. Deployment

### Backend → Railway

- Add `railway.toml` at repo root, pointing build root to `backend/`
- Add `Procfile` in `backend/`: `web: uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Railway auto-detects Python via existing `requirements.txt`
- Required env vars (set in Railway dashboard):
  - `DATABASE_URL` — Neon Postgres connection string
  - `LEGISCAN_API_KEY` — LegiScan API key
  - `ALLOWED_ORIGINS` — comma-separated Vercel URL(s) for CORS

### Frontend → Vercel

- Connect GitHub repo in Vercel dashboard (new account)
- Root directory: `frontend/`
- Required env var: `NEXT_PUBLIC_API_URL` = Railway backend URL
- No `vercel.json` needed — Next.js auto-detected

### Auto-deploy

Push to `main` → Railway rebuilds backend, Vercel rebuilds frontend. Both CI workflows (backend pytest, frontend lint/unit/E2E) already wired to `pull_request`.

---

## 2. Backend Additions

Both additions are read-only, require no migrations, no new models.

### 2a. `GET /sessions`

New endpoint in `backend/app/routers/bills.py`:

```python
@router.get("/sessions", response_model=list[str])
async def list_sessions(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Bill.session)
        .where(Bill.is_corpus_only.is_(False))
        .distinct()
        .order_by(Bill.session.desc())
    )
    return [row[0] for row in result.all()]
```

Must be registered **before** `GET /{bill_id}` in the router — FastAPI tries to parse path segments as UUID first; "sessions" would return 422 otherwise.

Tests: happy path (returns list), empty DB (returns `[]`).

### 2b. `tag_type` filter on `GET /bills`

Add `tag_type: str | None = None` parameter to `list_bills`. When set, inner join `friction_tags`:

```python
if tag_type:
    q = q.join(FrictionTag, FrictionTag.bill_id == Bill.id).where(
        FrictionTag.tag_type == tag_type
    )
```

Response schema unchanged (`BillListItem`). Tests: happy path with tag filter, no match returns `[]`.

---

## 3. Frontend Pages

### 3a. `/about` — Static methodology page

File: `frontend/app/about/page.tsx`

Sections (static TSX, no API calls):
1. **What LegiLens measures** — Friction Gap definition, what the IST score means
2. **How MinHash works** — plain-English explanation: shingling → hashing → Jaccard similarity, 128 permutations, 0.70 threshold
3. **Score interpretation** — 0–30: copycat alert / 31–69: partial overlap / 70–100: likely original
4. **Friction tag glossary** — all 6 tags from CLAUDE.md with definition and example
5. **Data sources** — LegiScan attribution, update cadence (nightly)

Styling: matches existing dark theme. No new dependencies.

### 3b. `/tags` — Tags browser

File: `frontend/app/tags/page.tsx`

- Fetches `GET /tags` (existing endpoint) via TanStack Query
- Renders one card per tag type: tag name (colored `TagBadge`) + count + description
- Each card links to `/?tag_type=<encoded tag name>` (dashboard pre-filtered)
- Tag descriptions hardcoded (6 types defined, stable)
- Loading/error states consistent with dashboard pattern

New entry in `lib/api.ts`: `api.tags()` fetching `GET /tags`.
New type in `lib/types.ts`: `TagCount { tag_type: string; count: number }`.

### 3c. Dashboard filter additions (`/`)

File: `frontend/app/page.tsx` (extend existing)

**Session dropdown:**
- Fetches `GET /sessions` (new) via TanStack Query
- `<select>` renders "All sessions" + one option per session string
- Selection writes `?session=` to URL (alongside existing `?q=`)

**Tag filter:**
- Reads `?tag_type=` from URL params (set by `/tags` page links, or manually)
- Passed as filter param to `api.bills()` call
- No UI control on dashboard for tag filter — it's set by navigating from `/tags`

**API client update:**
- `api.bills()` accepts `{ session?, tag_type? }` options, appends as query params

Filter state lives in URL — shareable and bookmarkable.

---

## 4. Testing

| Area | What to add |
|------|------------|
| Backend | 2 tests for `GET /sessions`, 2 tests for `tag_type` filter |
| Frontend unit | jest-axe tests for `/about` page, `/tags` page, session dropdown |
| E2E | Playwright: tag filter navigation (tags page → dashboard), session dropdown, about page renders |

---

## 5. Sequence

1. Deploy backend to Railway
2. Deploy frontend to Vercel (step-by-step with user)
3. Feature branch: backend additions (`GET /sessions` + `tag_type` filter) → PR
4. Feature branch: `/about` page → PR
5. Feature branch: `/tags` page + dashboard filter additions → PR
