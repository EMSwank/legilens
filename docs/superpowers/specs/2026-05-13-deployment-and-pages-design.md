# Sprint 4 — Deployment + Missing Pages

**Date:** 2026-05-13
**Scope:** Deploy backend to Railway, deploy frontend to Vercel, add two backend API endpoints, build three missing frontend pages.

---

## 1. Deployment

### Backend → Railway (two services from one repo)

Create **two Railway services**, both deploying from the same GitHub repo with `backend/` as root. Separating services keeps the worker's MinHash memory footprint out of the web request path.

**Service A — Web**
- Start command (Railway dashboard): `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Handles all FastAPI traffic

**Service B — Worker**
- Start command override: `python -m worker.scheduler`
- Runs the nightly ingest / match / evidence pipeline via APScheduler
- Without this service, MinHash and snippet extraction never run in production

**Cost note:** APScheduler in `scheduler.py` is itself the scheduler — the worker process stays running 24/7 to dispatch nightly jobs, not just during the jobs themselves. Worker isn't free when idle. Estimated ~$5/mo on Railway Hobby plan with both services running. A Railway Cron alternative exists (one-shot script triggered nightly) but requires rewriting `scheduler.py` to drop APScheduler — skip for MVP, revisit if cost becomes a pain point.

Railway auto-detects Python via existing `requirements.txt`. Both services share env vars (set independently per service, or via a Railway shared env group):

- `DATABASE_URL` — Neon Postgres connection string
- `REDIS_URL` — Redis connection (worker state)
- `LEGISCAN_API_KEY` — LegiScan API key
- `ALLOWED_ORIGINS` — comma-separated Vercel production URL(s)
- `PYTHONPATH=.` — required so Railway resolves `worker.*` and `app.*` imports

### Alembic migrations

Folded into the web service's start command (`alembic upgrade head && uvicorn ...`). Alembic checks `alembic_version` before applying — idempotent and safe on every boot. Adds ~1–2s to cold start.

**Known limitation:** If the web service ever scales beyond a single replica, multiple instances will run `alembic upgrade head` simultaneously on boot. Alembic uses Postgres advisory locks so the schema won't corrupt, but expect startup delays and noisy logs on subsequent replicas. For single-replica MVP this is fine. Flag this and migrate to a dedicated Railway pipeline step (or a one-shot migrate service) before scaling out.

### CORS — Vercel preview URLs

Vercel generates dynamic preview URLs per PR. A static `ALLOWED_ORIGINS` list breaks them.

Update `backend/app/main.py` to use FastAPI's `allow_origin_regex` (Starlette CORSMiddleware):

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_methods=["GET"],
    allow_headers=["*"],
)
```

Blast radius is zero — all data is public read-only. **This pattern is scoped to the current public read-only API. Do NOT carry the same wildcard into any future authenticated endpoint without revisiting** — that regex matches every Vercel deployment on the internet, not just LegiLens deployments.

### Frontend → Vercel

- Connect GitHub repo in Vercel dashboard (new account — walk through interactively)
- Root directory: `frontend/`
- Required env var: `NEXT_PUBLIC_API_URL` = Railway web service public URL
- No `vercel.json` — Next.js auto-detected

### Pre-deploy checklist

- [ ] Run `pip freeze > requirements.txt` in `backend/` so Railway's build environment matches local
- [ ] Run `npm run build` in `frontend/` locally to catch TypeScript strict null issues and any `lucide-react` icon naming mismatches before Vercel does

### Auto-deploy

Push to `main` → both Railway services rebuild, Vercel rebuilds frontend. Existing CI workflows (backend pytest, frontend lint/unit/E2E) continue to run on `pull_request`.

---

## 2. Backend Additions

Both additions are read-only, require no schema migrations, no new models.

### 2a. `GET /bills/sessions`

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

Must be registered **before** `GET /{bill_id}` in the router — FastAPI tries to parse path segments as UUID; "sessions" returns 422 otherwise.

No caching. CO has ~3–10 distinct sessions; DISTINCT on an indexed short string column is sub-millisecond. Revisit only if metrics show >10ms on 1M+ rows.

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

### 3a. `/about` — Methodology with proof-of-work

File: `frontend/app/about/page.tsx`. Static TSX, no API calls.

Goal: **technical authority**. Journalists must be able to cite the methodology and trust the numbers. Don't just describe MinHash — show enough of the mechanics that a skeptical reader sees this is measurement, not opinion.

Sections:

1. **What LegiLens measures** — Friction Gap definition, what the IST score represents.
2. **How MinHash works — proof of work:**
   - **Shingling diagram** — inline SVG showing how a sentence is broken into overlapping k-shingles (3-word windows). Hand-authored SVG, no new dependency.
   - **Jaccard similarity formula** — rendered as plain monospace (no KaTeX dependency for MVP): `J(A, B) = |A ∩ B| / |A ∪ B|`
   - **Why MinHash** — exact Jaccard is O(n²) across the corpus; MinHash estimates Jaccard with 128 hash permutations, enabling LSH bucketing for sub-linear lookup.
   - **The 0.70 threshold** — chosen Jaccard cutoff and rationale (calibrated against known ALEC-style model bills).
3. **Score interpretation** — 0–30: copycat alert / 31–69: partial overlap / 70–100: likely original.
4. **Friction tag glossary** — all 6 tags (Technical Conflict, Spatial Inconsistency, Expert Defiance, Regressive Burden, Source-Cloned, Legal Hallucination) with definition + example.
5. **Data sources** — LegiScan attribution, nightly sync cadence, corpus scope.

Styling: matches existing dark theme. No new dependencies.

### 3b. `/tags` — Tags browser

File: `frontend/app/tags/page.tsx`

- Fetches `GET /tags` (existing endpoint) via TanStack Query
- Renders one card per tag type: tag name (`TagBadge`) + bill count + description
- Each card links to `/?tag_type=<encoded tag name>` (dashboard pre-filtered)
- Tag descriptions hardcoded (6 types, stable)
- Loading/error states consistent with dashboard pattern

New entry in `lib/api.ts`: `api.tags()` → `GET /tags`.
New type in `lib/types.ts`: `TagCount { tag_type: string; count: number }`.

**Accessibility:** All `TagBadge` instances use `font-semibold` to maintain contrast on the dark slate background, particularly the red-tinted variants ("Regressive Burden", "Source-Cloned").

### 3c. Dashboard filter additions (`/`)

File: `frontend/app/page.tsx` (extend existing)

The dashboard gains filter state driven by URL params, but no in-page setters for tag filters — `/tags` remains the canonical place to discover and enter a tag filter. Filters are made visible and dismissible via a chip row that renders only when filters are active.

**Session dropdown:**
- Fetches `GET /bills/sessions` (new) via TanStack Query
- `<select>` renders "All sessions" + one option per session string
- Selection writes `?session=` to URL

**Tag filter (no in-page setter):**
- Reads `?tag_type=` from URL params (set by `/tags` page card links, or by direct deep-link from a journalist's article)
- Passed as filter param to `api.bills()` call

**Active filter chips:**
- Chip row renders only when `session` or `tag_type` is present in URL params
- One chip per active filter, e.g. `[Tag: Source-Cloned ×] [Session: 2025A ×]`
- Clicking × removes only that filter from the URL (others remain)
- No separate "Clear Filters" button — each chip is independently dismissible
- Replaces both the standalone Clear Filters button and the need for a redundant dashboard tag dropdown

**Why chips over dropdowns:**
- `/tags` stays the canonical discovery surface (counts + descriptions), avoiding redundant UI
- Symmetric escape hatch — any active filter is dismissible from the same surface regardless of how it was set
- Common, well-understood pattern (Algolia, Linear, etc.)

**API client update:**
- `api.bills()` accepts `{ session?, tag_type? }` options, appended as query params

Filter state lives in URL — shareable, bookmarkable, supports deep-linking from journalist articles.

---

## 4. Testing

Test cases below are explicit so they don't need to be inferred during implementation. Each bullet = one test.

### 4a. Backend (pytest-asyncio, using `dependency_overrides`)

**`GET /bills/sessions`:**
- Returns distinct session strings from non-corpus-only bills
- Returns `[]` when DB has zero non-corpus-only bills
- Returns sessions sorted descending (most recent first)
- Excludes bills where `is_corpus_only=True`
- Returns 400 when User-Agent header is missing (consistent with other endpoints)

**`tag_type` filter on `GET /bills`:**
- Happy path: passing `tag_type` returns only bills with that friction tag
- No matches: returns `[]` when no bills have the requested tag
- Compound filter: `tag_type` + `session` filters AND-combine correctly
- Compound filter: `tag_type` + `status` filters AND-combine correctly
- Pagination still works: `tag_type` + `page=2&size=10` returns the second page
- `copycat_alert` still propagates: outer join on `ISTScore` not broken by the new inner join
- Invalid `tag_type` (unknown string) returns `[]`, not 500

**Regression coverage (existing `list_bills` behavior):**
- Existing tests for `list_bills` without `tag_type` still pass after the query change
- Existing UUID-based `GET /bills/{bill_id}` route still works (route ordering didn't shadow it)

**CORS middleware:**
- Production URL listed in `ALLOWED_ORIGINS` receives `Access-Control-Allow-Origin` header
- A `https://legilens-abc123.vercel.app` preview URL receives the header (regex match)
- An unrelated origin (e.g., `https://evil.example.com`) does NOT receive the header

### 4b. Frontend unit (jest + jest-axe + React Testing Library)

**`/about` page (`__tests__/about.test.tsx`):**
- Renders without axe violations
- Shingling SVG diagram is in the DOM
- All 5 section headings render in order
- Jaccard formula text is present

**`/tags` page (`__tests__/tags.test.tsx`):**
- Renders without axe violations
- All 6 tag types render as cards when API returns them
- Each card's link points to `/?tag_type=<URL-encoded tag name>`
- Tag bill count displays correctly
- Loading state (`isPending`) shows skeleton/spinner
- Error state (`isError`) shows `role="alert"` message
- Empty state (API returns `[]`) shows "no tags yet" message

**Filter chip row (`__tests__/FilterChips.test.tsx`):**
- Does not render when neither `session` nor `tag_type` is in URL
- Renders one chip when only `session` is set
- Renders one chip when only `tag_type` is set
- Renders two chips when both are set
- Clicking × on a chip removes only that filter from URL (other filter preserved)
- Chip × button is keyboard accessible (Tab focuses, Enter/Space dismisses)
- No axe violations in any state

**Session dropdown (`__tests__/SessionDropdown.test.tsx`):**
- Renders "All sessions" + one option per fetched session
- Selecting an option writes `?session=` to URL
- Selecting "All sessions" removes `?session=` from URL
- Preserves other URL params (`?q=`, `?tag_type=`) when selection changes
- No axe violations

**API client (`__tests__/api.test.ts`):**
- `api.bills({session: '2025A'})` requests `/bills?session=2025A`
- `api.bills({tag_type: 'Source-Cloned'})` requests `/bills?tag_type=Source-Cloned`
- `api.bills({session: '2025A', tag_type: 'Source-Cloned'})` requests both params
- URL-encodes tag values containing spaces (`Technical Conflict` → `Technical+Conflict` or `Technical%20Conflict`)
- `api.tags()` requests `/tags`
- `api.sessions()` requests `/bills/sessions`

**Dashboard integration (`__tests__/dashboard.test.tsx`):**
- Reads `?tag_type=` from URL on mount and passes to `api.bills()`
- Reads `?session=` from URL on mount and passes to `api.bills()`
- URL param change triggers TanStack Query refetch
- Deep-link `/?tag_type=Source-Cloned&session=2025A` renders filtered list

### 4c. End-to-end (Playwright)

**Full filter journey:**
- Visit `/`, click "Tags" nav link → land on `/tags`
- Click a tag card → land on `/?tag_type=...` with filtered list
- Dismiss the chip → URL clears `tag_type`, full list returns

**Compound filtering:**
- From `/?tag_type=Source-Cloned`, select session "2025A" from dropdown → URL becomes `/?tag_type=Source-Cloned&session=2025A`
- Two chips visible; dismiss the tag chip → only `session` remains

**Bookmarkable / deep-link:**
- Direct navigation to `/?tag_type=Source-Cloned&session=2025A` renders correctly filtered list (proves URL is source of truth)

**About page:**
- Loads at `/about`, all sections render, shingling SVG visible

**Mobile viewport:**
- Filter chips remain dismissible on a 375px-wide viewport (touch targets ≥ 44px per WCAG 2.5.5)

### 4d. Deployment smoke tests (manual, post-deploy checklist)

Document these as required checks after each Railway/Vercel deploy. Not automated CI yet; can become a GitHub Action later.

**Backend (Railway web service):**
- `curl https://<railway-web-url>/stats -H 'User-Agent: smoke-test'` returns 200 with non-empty JSON
- `curl https://<railway-web-url>/bills/sessions -H 'User-Agent: smoke-test'` returns 200 with a list

**Backend (Railway worker service):**
- Railway logs show APScheduler "Scheduler started" line at boot
- After first scheduled run, `bills` table row count > 0 (verify via Neon SQL editor)

**Database:**
- `alembic_version` table contains the latest revision hash matching `backend/alembic/versions/`

**Frontend (Vercel):**
- Production URL loads dashboard, stats grid populated (proves end-to-end CORS + API connectivity)
- Navigate to `/about` and `/tags`, both render
- Click a tag card, confirm dashboard filters and chip is dismissible

---

## 5. Sequence

1. Verify Railway Hobby plan / resource headroom for two services
2. Deploy backend to Railway (web + worker, migrations folded into web start command)
3. Deploy frontend to Vercel (interactive walkthrough — new account)
4. Feature branch: backend additions (`GET /bills/sessions` + `tag_type` filter on `GET /bills`) → PR
5. Feature branch: `/about` page with shingling SVG + Jaccard formula → PR
6. Feature branch: `/tags` page + dashboard filter additions (session dropdown + filter chips) → PR
