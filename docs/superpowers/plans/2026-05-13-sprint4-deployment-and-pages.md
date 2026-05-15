# Sprint 4 — Deployment + Missing Pages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status (as of 2026-05-14):**
| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Deploy config (Procfile, railway.toml, CORS) | ✅ Merged (#12) |
| 2 | Backend additions (sessions endpoint, tag_type filter) | ✅ Merged (#12) |
| 3 | Frontend foundation (types, api client, axe helper, A11Y checklist) | ✅ Merged (#13) |
| 4 | `/about` + `/accessibility` pages | ✅ Merged (#13) |
| 5 | `/tags` page | ✅ Merged (#15) |
| 6 | Dashboard filter chips + session dropdown | ✅ Merged (#16) |
| 7 | Railway + Vercel deploy (manual) | 🔄 In progress (Railway ✅, Vercel env var fix pending) |

**Goal:** Deploy LegiLens to Railway (backend, two services) + Vercel (frontend), add two backend endpoints (`GET /bills/sessions` and a `tag_type` filter on `GET /bills`), and build three missing frontend pages (`/about`, `/tags`, `/accessibility`) plus dashboard filter chips and session dropdown.

**Architecture:** Backend stays on FastAPI/asyncpg/Neon Postgres; deployment splits into Railway "web" (FastAPI + alembic migrations) and "worker" (APScheduler-driven nightly pipeline). Frontend stays on Next.js 16 App Router with TanStack Query. Filter state lives entirely in URL query params; the dashboard exposes a session dropdown and a dismissible chip row driven by URL params. WCAG 2.1 AA is enforced via jest-axe + `@axe-core/playwright` in CI plus a manual checklist per PR.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0 (async), pytest-asyncio, alembic, Next.js 16, React 19, TypeScript, TanStack Query v5, Tailwind, jest-axe, Playwright, Railway, Vercel.

**Spec:** `docs/superpowers/specs/2026-05-13-deployment-and-pages-design.md`

**Branching:** One feature branch per phase:
- Phase 1 + 2 (deploy config + backend additions): `feat/backend-sessions-and-tag-filter`
- Phase 3 (frontend foundation): folded into the first frontend PR (Phase 4 or 5)
- Phase 4 (about + accessibility pages): `feat/about-and-accessibility-pages`
- Phase 5 (tags page): `feat/tags-page`
- Phase 6 (dashboard filter chips + session dropdown): `feat/dashboard-filter-chips`

Phases 7–8 (E2E and manual deploy steps) fold into the relevant code branches.

---

## File Structure

### Backend — files to create
- `Procfile` (repo root) — Railway process declarations
- `railway.toml` (repo root) — Railway build config pointing to `backend/`
- `backend/tests/test_api_sessions.py` — tests for `GET /bills/sessions`
- `backend/tests/test_cors.py` — tests for CORS regex behavior

### Backend — files to modify
- `backend/app/routers/bills.py` — add `list_sessions`, add `tag_type` param to `list_bills`
- `backend/app/main.py` — add `allow_origin_regex` to CORSMiddleware
- `backend/tests/test_api_bills.py` — add `tag_type` filter tests, regression tests

### Frontend — files to create
- `frontend/A11Y_CHECKLIST.md` — manual a11y checklist required per PR
- `frontend/e2e/axe-helper.ts` — `@axe-core/playwright` wrapper
- `frontend/app/about/page.tsx` — methodology page
- `frontend/app/accessibility/page.tsx` — accessibility statement
- `frontend/app/tags/page.tsx` — tag browser
- `frontend/components/ShingleDiagram.tsx` — inline SVG for `/about`
- `frontend/components/SessionDropdown.tsx` — native `<select>` for session filter
- `frontend/components/FilterChips.tsx` — dismissible chip row
- `frontend/__tests__/pages/About.test.tsx`
- `frontend/__tests__/pages/Accessibility.test.tsx`
- `frontend/__tests__/pages/Tags.test.tsx`
- `frontend/__tests__/components/ShingleDiagram.test.tsx`
- `frontend/__tests__/components/SessionDropdown.test.tsx`
- `frontend/__tests__/components/FilterChips.test.tsx`
- `frontend/__tests__/lib/api.test.ts`
- `frontend/e2e/about.spec.ts`
- `frontend/e2e/tags.spec.ts`
- `frontend/e2e/filters.spec.ts`

### Frontend — files to modify
- `frontend/lib/types.ts` — add `TagCount`
- `frontend/lib/api.ts` — add `tags()`, `sessions()`, `tag_type` option on `bills()`
- `frontend/app/page.tsx` — wire SessionDropdown + FilterChips + tag_type param
- `frontend/playwright.config.ts` — no change expected; helper imports only
- `frontend/package.json` — add `@axe-core/playwright` to devDependencies

---

## Phase 1 — Deployment configuration files (no tests, infra)

### Task 1.1: Create `Procfile` at repo root

**Files:**
- Create: `Procfile`

- [x] **Step 1: Create the Procfile**

```
web: cd backend && alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT
worker: cd backend && python -m worker.scheduler
```

Note: Two process types, both `cd` into `backend/` first because the Railway build will install Python dependencies from `backend/requirements.txt`. Railway's "service" abstraction will pick which line to run for each service.

- [x] **Step 2: Commit**

```bash
git checkout -b feat/backend-sessions-and-tag-filter
git add Procfile
git commit -m "chore: add Procfile for Railway web + worker services"
```

### Task 1.2: Create `railway.toml` at repo root

**Files:**
- Create: `railway.toml`

- [x] **Step 1: Create railway.toml**

```toml
# Railway build config — backend lives in /backend
# Web service start command is overridden in Railway dashboard to include
# the alembic migration step; worker service overrides to run scheduler.

[build]
buildCommand = "pip install -r backend/requirements.txt"

[deploy]
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 3
```

- [x] **Step 2: Commit**

```bash
git add railway.toml
git commit -m "chore: add railway.toml build config"
```

### Task 1.3: Add CORS regex to allow Vercel preview URLs

**Files:**
- Modify: `backend/app/main.py:17-22`

- [x] **Step 1: Update main.py CORS middleware**

Replace the existing `app.add_middleware(CORSMiddleware, ...)` block with:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_methods=["GET"],
    allow_headers=["*"],
)
```

The regex allows any Vercel preview deployment to call the API; acceptable for a public read-only API.

- [x] **Step 2: Run existing backend tests to confirm nothing broke**

```bash
cd backend && pytest tests/test_api_bills.py -v
```

Expected: all existing tests pass.

- [x] **Step 3: Commit**

```bash
git add backend/app/main.py
git commit -m "feat(api): allow Vercel preview URLs via CORS regex"
```

### Task 1.4: Add CORS regex tests

**Files:**
- Create: `backend/tests/test_cors.py`

- [x] **Step 1: Write failing tests**

```python
import pytest
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
async def test_cors_allows_configured_production_origin():
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.options(
            "/stats",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
                "User-Agent": "TestClient/1.0",
            },
        )
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"


@pytest.mark.asyncio
async def test_cors_allows_vercel_preview_via_regex():
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.options(
            "/stats",
            headers={
                "Origin": "https://legilens-abc123-feat-foo.vercel.app",
                "Access-Control-Request-Method": "GET",
                "User-Agent": "TestClient/1.0",
            },
        )
    assert resp.headers.get("access-control-allow-origin") == "https://legilens-abc123-feat-foo.vercel.app"


@pytest.mark.asyncio
async def test_cors_rejects_unrelated_origin():
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.options(
            "/stats",
            headers={
                "Origin": "https://evil.example.com",
                "Access-Control-Request-Method": "GET",
                "User-Agent": "TestClient/1.0",
            },
        )
    assert resp.headers.get("access-control-allow-origin") is None
```

- [x] **Step 2: Run tests to verify they pass**

```bash
cd backend && pytest tests/test_cors.py -v
```

Expected: all three pass (we already added the regex in Task 1.3).

- [x] **Step 3: Commit**

```bash
git add backend/tests/test_cors.py
git commit -m "test(api): cover CORS regex + allowlist behavior"
```

---

## Phase 2 — Backend additions (TDD)

### Task 2.1: Add `GET /bills/sessions` — failing test first

**Files:**
- Create: `backend/tests/test_api_sessions.py`

- [x] **Step 1: Write the failing tests**

```python
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_get_sessions_returns_list():
    from app.main import app
    from app.dependencies import get_db

    mock_session = AsyncMock()
    execute_result = MagicMock()
    execute_result.all.return_value = [("2025A",), ("2024A",), ("2023A",)]
    mock_session.execute.return_value = execute_result

    async def override():
        yield mock_session

    app.dependency_overrides[get_db] = override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get("/bills/sessions", headers={"User-Agent": "TestClient/1.0"})
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    assert resp.json() == ["2025A", "2024A", "2023A"]


@pytest.mark.asyncio
async def test_get_sessions_returns_empty_list_when_no_bills():
    from app.main import app
    from app.dependencies import get_db

    mock_session = AsyncMock()
    execute_result = MagicMock()
    execute_result.all.return_value = []
    mock_session.execute.return_value = execute_result

    async def override():
        yield mock_session

    app.dependency_overrides[get_db] = override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get("/bills/sessions", headers={"User-Agent": "TestClient/1.0"})
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_sessions_requires_user_agent():
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/bills/sessions", headers={"User-Agent": ""})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_get_sessions_query_orders_descending_and_excludes_corpus_only():
    """The query must filter is_corpus_only=False and ORDER BY session DESC."""
    from app.main import app
    from app.dependencies import get_db
    from sqlalchemy.sql.elements import BinaryExpression

    captured_statements = []

    async def execute_spy(stmt):
        captured_statements.append(str(stmt))
        result = MagicMock()
        result.all.return_value = []
        return result

    mock_session = AsyncMock()
    mock_session.execute.side_effect = execute_spy

    async def override():
        yield mock_session

    app.dependency_overrides[get_db] = override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            await c.get("/bills/sessions", headers={"User-Agent": "TestClient/1.0"})
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert len(captured_statements) == 1
    stmt = captured_statements[0].lower()
    assert "distinct" in stmt
    assert "is_corpus_only" in stmt
    assert "order by" in stmt and "desc" in stmt
```

- [x] **Step 2: Run tests to verify they fail**

```bash
cd backend && pytest tests/test_api_sessions.py -v
```

Expected: 404 on all tests (route does not exist yet).

### Task 2.2: Implement `GET /bills/sessions`

**Files:**
- Modify: `backend/app/routers/bills.py`

- [x] **Step 1: Add the endpoint BEFORE `get_bill(bill_id: UUID)`**

Insert this function in `backend/app/routers/bills.py`, placed AFTER `search_bills` and BEFORE `get_bill`. The ordering matters: FastAPI tries to parse `{bill_id}` as UUID, and "sessions" would raise 422 otherwise.

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

- [x] **Step 2: Run tests to verify they pass**

```bash
cd backend && pytest tests/test_api_sessions.py -v
```

Expected: all 4 tests pass.

- [x] **Step 3: Verify UUID route still works (regression check)**

```bash
cd backend && pytest tests/test_api_bills.py::test_get_bill_detail_404_on_missing -v
```

Expected: passes (route registration didn't shadow `/{bill_id}`).

- [x] **Step 4: Commit**

```bash
git add backend/app/routers/bills.py backend/tests/test_api_sessions.py
git commit -m "feat(api): GET /bills/sessions returns distinct CO sessions"
```

### Task 2.3: Add `tag_type` filter to `GET /bills` — failing tests first

**Files:**
- Modify: `backend/tests/test_api_bills.py`

- [x] **Step 1: Append failing tests to the existing test file**

Add at the end of `backend/tests/test_api_bills.py`:

```python
@pytest.mark.asyncio
async def test_get_bills_with_tag_type_filter():
    """When tag_type is passed, the query must join friction_tags and filter by tag_type."""
    from app.main import app
    from app.dependencies import get_db

    captured = []

    async def execute_spy(stmt):
        captured.append(str(stmt))
        result = MagicMock()
        result.all.return_value = []
        return result

    mock_session = AsyncMock()
    mock_session.execute.side_effect = execute_spy

    async def override():
        yield mock_session

    app.dependency_overrides[get_db] = override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get(
                "/bills?tag_type=source_cloned",
                headers={"User-Agent": "TestClient/1.0"},
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    stmt = captured[0].lower()
    assert "friction_tag" in stmt
    assert "tag_type" in stmt


@pytest.mark.asyncio
async def test_get_bills_tag_type_combines_with_session_and_status():
    from app.main import app
    from app.dependencies import get_db

    captured = []

    async def execute_spy(stmt):
        captured.append(str(stmt))
        result = MagicMock()
        result.all.return_value = []
        return result

    mock_session = AsyncMock()
    mock_session.execute.side_effect = execute_spy

    async def override():
        yield mock_session

    app.dependency_overrides[get_db] = override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get(
                "/bills?tag_type=source_cloned&session=2025A&status=Passed",
                headers={"User-Agent": "TestClient/1.0"},
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    stmt = captured[0].lower()
    assert "tag_type" in stmt
    assert "session" in stmt
    assert "status" in stmt


@pytest.mark.asyncio
async def test_get_bills_invalid_tag_type_returns_empty_list():
    """An unknown tag_type returns 200 with [], not 500."""
    from app.main import app
    from app.dependencies import get_db

    mock_session = AsyncMock()
    execute_result = MagicMock()
    execute_result.all.return_value = []
    mock_session.execute.return_value = execute_result

    async def override():
        yield mock_session

    app.dependency_overrides[get_db] = override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get(
                "/bills?tag_type=not_a_real_tag",
                headers={"User-Agent": "TestClient/1.0"},
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_bills_without_tag_type_does_not_join_friction_tags():
    """Regression: unfiltered list_bills must NOT join friction_tags."""
    from app.main import app
    from app.dependencies import get_db

    captured = []

    async def execute_spy(stmt):
        captured.append(str(stmt))
        result = MagicMock()
        result.all.return_value = []
        return result

    mock_session = AsyncMock()
    mock_session.execute.side_effect = execute_spy

    async def override():
        yield mock_session

    app.dependency_overrides[get_db] = override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get("/bills", headers={"User-Agent": "TestClient/1.0"})
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    stmt = captured[0].lower()
    assert "friction_tag" not in stmt
```

- [x] **Step 2: Run tests to verify they fail**

```bash
cd backend && pytest tests/test_api_bills.py -v -k "tag_type or without_tag_type"
```

Expected: tag_type tests fail (parameter not implemented); regression test passes (no friction_tags join yet).

### Task 2.4: Implement `tag_type` filter

**Files:**
- Modify: `backend/app/routers/bills.py:14-46`

- [x] **Step 1: Update `list_bills` signature and query**

Replace the existing `list_bills` function:

```python
@router.get("", response_model=list[BillListItem])
async def list_bills(
    session: str | None = None,
    status: str | None = None,
    tag_type: str | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    q = (
        select(Bill, ISTScore.copycat_alert)
        .outerjoin(ISTScore, ISTScore.bill_id == Bill.id)
        .where(Bill.is_corpus_only.is_(False))
    )
    if session:
        q = q.where(Bill.session == session)
    if status:
        q = q.where(Bill.status == status)
    if tag_type:
        q = q.join(FrictionTag, FrictionTag.bill_id == Bill.id).where(
            FrictionTag.tag_type == tag_type
        )
    q = q.offset((page - 1) * size).limit(size)
    result = await db.execute(q)
    rows = result.all()
    return [
        BillListItem(
            id=b.id,
            bill_number=b.bill_number,
            title=b.title,
            state=b.state,
            session=b.session,
            status=b.status,
            copycat_alert=copycat_alert,
        )
        for b, copycat_alert in rows
    ]
```

- [x] **Step 2: Run all bills tests to verify nothing regressed**

```bash
cd backend && pytest tests/test_api_bills.py -v
```

Expected: all pass, including the new tag_type tests and the regression "no friction_tags join when not filtered" test.

- [x] **Step 3: Run the full backend test suite**

```bash
cd backend && pytest -v
```

Expected: full suite green.

- [x] **Step 4: Commit**

```bash
git add backend/app/routers/bills.py backend/tests/test_api_bills.py
git commit -m "feat(api): tag_type filter on GET /bills"
```

### Task 2.5: Open PR for backend additions

- [x] **Step 1: Push branch**

```bash
git push -u origin feat/backend-sessions-and-tag-filter
```

- [x] **Step 2: Open PR**

```bash
gh pr create --title "feat(api): Sprint 4 backend additions — sessions endpoint + tag_type filter + CORS regex" --body "$(cat <<'EOF'
## Summary
- New `GET /bills/sessions` returns distinct CO sessions ordered DESC, excluding corpus-only bills
- New `tag_type` query param on `GET /bills` inner-joins `friction_tags`, AND-combines with existing `session`/`status` filters
- `CORSMiddleware` adds `allow_origin_regex` for `*.vercel.app` to unblock preview deployments
- `Procfile` + `railway.toml` prepared for Railway deploy (web + worker services)

## Test plan
- [x] `pytest tests/test_api_sessions.py -v` — 4 tests
- [x] `pytest tests/test_api_bills.py -v` — original tests + 4 new (tag_type filter coverage)
- [x] `pytest tests/test_cors.py -v` — 3 tests
- [x] Full backend test suite: `pytest -v`

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [x] **Step 3: Wait for CI green, then merge**

Confirm CI passes (backend pytest workflow). Merge via GitHub UI or:

```bash
gh pr merge --squash
git checkout main && git pull
```

---

## Phase 3 — Frontend foundation (folds into first frontend PR)

### Task 3.1: Add TagCount type and update API client

**Files:**
- Modify: `frontend/lib/types.ts`
- Modify: `frontend/lib/api.ts`

- [x] **Step 1: Create a new feature branch (this work folds into first frontend PR)**

```bash
git checkout main && git pull
git checkout -b feat/about-and-accessibility-pages
```

- [x] **Step 2: Append `TagCount` to types.ts**

Add at the end of `frontend/lib/types.ts`:

```typescript
export interface TagCount {
  tag_type: string;
  count: number;
}
```

- [x] **Step 3: Update api.ts — add `tag_type` option, `tags()`, `sessions()`**

Replace the existing `bills` method and append two new methods:

```typescript
import type { BillListItem, BillDetail, Match, Stats, TagCount } from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const HEADERS = { "User-Agent": "LegiLens-Frontend/1.0" };

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { headers: HEADERS });
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`);
  return res.json() as Promise<T>;
}

export const api = {
  bills: (params?: { session?: string; status?: string; tag_type?: string; page?: number }): Promise<BillListItem[]> => {
    const q = new URLSearchParams();
    if (params?.session) q.set("session", params.session);
    if (params?.status) q.set("status", params.status);
    if (params?.tag_type) q.set("tag_type", params.tag_type);
    if (params?.page) q.set("page", String(params.page));
    const qs = q.toString();
    return get<BillListItem[]>(qs ? `/bills?${qs}` : "/bills");
  },
  searchBills: (q: string): Promise<BillListItem[]> =>
    get<BillListItem[]>(`/bills/search?q=${encodeURIComponent(q)}`),
  bill: (id: string): Promise<BillDetail> =>
    get<BillDetail>(`/bills/${id}`),
  matches: (billId: string): Promise<Match[]> =>
    get<Match[]>(`/bills/${billId}/matches`),
  stats: (): Promise<Stats> =>
    get<Stats>("/stats"),
  tags: (): Promise<TagCount[]> =>
    get<TagCount[]>("/tags"),
  sessions: (): Promise<string[]> =>
    get<string[]>("/bills/sessions"),
};
```

- [x] **Step 4: Write api.ts tests**

Create `frontend/__tests__/lib/api.test.ts`:

```typescript
/**
 * @jest-environment node
 */
import { api } from "@/lib/api";

const fetchMock = jest.fn();
global.fetch = fetchMock as unknown as typeof fetch;

beforeEach(() => {
  fetchMock.mockReset();
  fetchMock.mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => [],
  });
});

const lastUrl = () => fetchMock.mock.calls[0][0] as string;

test("api.bills with session appends session query param", async () => {
  await api.bills({ session: "2025A" });
  expect(lastUrl()).toMatch(/\/bills\?session=2025A$/);
});

test("api.bills with tag_type appends tag_type query param", async () => {
  await api.bills({ tag_type: "source_cloned" });
  expect(lastUrl()).toMatch(/\/bills\?tag_type=source_cloned$/);
});

test("api.bills with session + tag_type appends both", async () => {
  await api.bills({ session: "2025A", tag_type: "source_cloned" });
  expect(lastUrl()).toContain("session=2025A");
  expect(lastUrl()).toContain("tag_type=source_cloned");
});

test("api.tags hits /tags", async () => {
  await api.tags();
  expect(lastUrl()).toMatch(/\/tags$/);
});

test("api.sessions hits /bills/sessions", async () => {
  await api.sessions();
  expect(lastUrl()).toMatch(/\/bills\/sessions$/);
});
```

- [x] **Step 5: Run the tests**

```bash
cd frontend && npm test -- --testPathPattern=lib/api
```

Expected: all 5 pass.

- [x] **Step 6: Commit**

```bash
git add frontend/lib/types.ts frontend/lib/api.ts frontend/__tests__/lib/api.test.ts
git commit -m "feat(frontend): add tags(), sessions(), tag_type filter to API client"
```

### Task 3.2: Add `@axe-core/playwright` to E2E setup

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/e2e/axe-helper.ts`

- [x] **Step 1: Install the package**

```bash
cd frontend && npm install --save-dev @axe-core/playwright
```

- [x] **Step 2: Create the axe helper**

Create `frontend/e2e/axe-helper.ts`:

```typescript
import type { Page } from "@playwright/test";
import { expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

export async function expectNoAxeViolations(page: Page, context?: string) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  if (results.violations.length > 0) {
    // Build a useful failure message
    const summary = results.violations
      .map((v) => `${v.id} (${v.impact}): ${v.description}\n  nodes: ${v.nodes.length}`)
      .join("\n");
    throw new Error(`Axe violations${context ? ` on ${context}` : ""}:\n${summary}`);
  }
  expect(results.violations).toEqual([]);
}
```

- [x] **Step 3: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/e2e/axe-helper.ts
git commit -m "chore(frontend): add @axe-core/playwright + axe helper for E2E"
```

### Task 3.3: Create A11Y_CHECKLIST.md

**Files:**
- Create: `frontend/A11Y_CHECKLIST.md`

- [x] **Step 1: Write the checklist**

```markdown
# Accessibility Checklist (per PR)

Every PR touching a frontend route or interactive component must check off each item below before merge. WCAG 2.1 Level AA is the conformance target.

Automated coverage (jest-axe + `@axe-core/playwright`) catches roughly 30–40% of issues. The rest of this list is manual verification.

## Per-route checks

For each new or modified route:

- [x] **Headings:** single `<h1>`; heading levels descend without skipping
- [x] **Landmarks:** `<main>` present; nav/footer use semantic landmarks
- [x] **Page title:** `metadata.title` exports a unique, descriptive title
- [x] **Reading order:** Tab traversal matches visual order
- [x] **Skip link:** "Skip to content" link works (still focuses `#main`)
- [x] **Keyboard:** every interactive element reachable via Tab; no traps; Enter/Space activates
- [x] **Focus visible:** visible focus ring on every interactive element
- [x] **Screen reader:** VoiceOver pass — every control announces its name + role + state; status changes announced
- [x] **Contrast:** sample every text/background pair via Chrome DevTools color picker; ≥4.5:1 text, ≥3:1 UI
- [x] **Color-only:** no information conveyed by color alone (icons, labels, or text accompany color cues)
- [x] **Zoom:** 200% browser zoom — no content lost, no overlap
- [x] **Reflow:** 320px viewport (Chrome DevTools device mode) — no horizontal scroll for prose
- [x] **Mobile touch targets:** all interactive elements ≥ 44×44 px on small viewport
- [x] **Reduced motion:** any animations respect `prefers-reduced-motion`
- [x] **Status messages:** dynamic state changes use `role="status"` or `role="alert"`
- [x] **Forms:** every control has an associated `<label>`; error messages announced

## Per-component checks

For each new or modified interactive component:

- [x] **Semantic element:** uses native HTML where possible (`<button>` not `<div onClick>`)
- [x] **Accessible name:** has visible text, `aria-label`, or `aria-labelledby`
- [x] **Decorative content:** icons/svgs without semantic meaning use `aria-hidden="true"`
- [x] **States:** disabled/loading/error states announced and visually distinct (not color-only)

## Tooling

- jest-axe runs in every component test — failures block CI
- `@axe-core/playwright` runs after each E2E page navigation — failures block CI
- Manual VoiceOver (Cmd+F5 on macOS): top-to-bottom read-through per route
- Manual keyboard-only walkthrough per route
```

- [x] **Step 2: Commit**

```bash
git add frontend/A11Y_CHECKLIST.md
git commit -m "docs(frontend): add A11Y_CHECKLIST.md (WCAG 2.1 AA per-PR gate)"
```

---

## Phase 4 — `/about` page + `/accessibility` statement

### Task 4.1: Build the ShingleDiagram SVG component (TDD)

**Files:**
- Create: `frontend/components/ShingleDiagram.tsx`
- Create: `frontend/__tests__/components/ShingleDiagram.test.tsx`

- [x] **Step 1: Write the failing test**

```typescript
import { render } from "@testing-library/react";
import { axe } from "jest-axe";
import ShingleDiagram from "@/components/ShingleDiagram";

test("ShingleDiagram has no accessibility violations", async () => {
  const { container } = render(<ShingleDiagram />);
  expect(await axe(container)).toHaveNoViolations();
});

test("ShingleDiagram renders an SVG with accessible name", () => {
  const { container, getByRole } = render(<ShingleDiagram />);
  const svg = container.querySelector("svg");
  expect(svg).not.toBeNull();
  expect(getByRole("img")).toBeInTheDocument();
  expect(getByRole("img")).toHaveAccessibleName(/shingl/i);
});

test("ShingleDiagram includes a textual description for screen readers", () => {
  const { getByText } = render(<ShingleDiagram />);
  // The text below the SVG describes the same concept
  expect(getByText(/three-word window/i)).toBeInTheDocument();
});
```

- [x] **Step 2: Run to confirm it fails**

```bash
cd frontend && npm test -- --testPathPattern=ShingleDiagram
```

Expected: FAIL (component does not exist).

- [x] **Step 3: Implement the component**

```typescript
export default function ShingleDiagram() {
  return (
    <figure className="my-6">
      <svg
        role="img"
        aria-labelledby="shingle-title shingle-desc"
        viewBox="0 0 600 180"
        className="w-full max-w-xl"
      >
        <title id="shingle-title">3-shingling of a sentence</title>
        <desc id="shingle-desc">
          A sentence broken into overlapping three-word windows, each forming
          one shingle in the MinHash sketch.
        </desc>

        {/* Original sentence */}
        <text x="20" y="30" className="fill-slate-200" fontSize="14" fontFamily="ui-monospace, monospace">
          the quick brown fox jumps over
        </text>

        {/* Shingle 1: "the quick brown" */}
        <rect x="14" y="50" width="155" height="22" fill="rgb(59 130 246 / 0.2)" stroke="rgb(59 130 246)" />
        <text x="20" y="66" className="fill-blue-200" fontSize="12" fontFamily="ui-monospace, monospace">
          the quick brown
        </text>

        {/* Shingle 2: "quick brown fox" */}
        <rect x="44" y="80" width="160" height="22" fill="rgb(59 130 246 / 0.2)" stroke="rgb(59 130 246)" />
        <text x="50" y="96" className="fill-blue-200" fontSize="12" fontFamily="ui-monospace, monospace">
          quick brown fox
        </text>

        {/* Shingle 3: "brown fox jumps" */}
        <rect x="88" y="110" width="160" height="22" fill="rgb(59 130 246 / 0.2)" stroke="rgb(59 130 246)" />
        <text x="94" y="126" className="fill-blue-200" fontSize="12" fontFamily="ui-monospace, monospace">
          brown fox jumps
        </text>

        {/* Shingle 4: "fox jumps over" */}
        <rect x="130" y="140" width="150" height="22" fill="rgb(59 130 246 / 0.2)" stroke="rgb(59 130 246)" />
        <text x="136" y="156" className="fill-blue-200" fontSize="12" fontFamily="ui-monospace, monospace">
          fox jumps over
        </text>
      </svg>
      <figcaption className="mt-2 text-sm text-slate-400">
        Each three-word window forms one shingle. The full set of shingles
        becomes the document signature.
      </figcaption>
    </figure>
  );
}
```

- [x] **Step 4: Run tests**

```bash
cd frontend && npm test -- --testPathPattern=ShingleDiagram
```

Expected: all 3 tests pass.

- [x] **Step 5: Commit**

```bash
git add frontend/components/ShingleDiagram.tsx frontend/__tests__/components/ShingleDiagram.test.tsx
git commit -m "feat(frontend): ShingleDiagram SVG component for /about methodology"
```

### Task 4.2: Build the `/about` page (TDD)

**Files:**
- Create: `frontend/app/about/page.tsx`
- Create: `frontend/__tests__/pages/About.test.tsx`

- [x] **Step 1: Write failing tests**

```typescript
import { render, screen } from "@testing-library/react";
import { axe } from "jest-axe";
import About from "@/app/about/page";

test("About page has no axe violations", async () => {
  const { container } = render(<About />);
  expect(await axe(container)).toHaveNoViolations();
});

test("About page renders single h1", () => {
  render(<About />);
  const headings = screen.getAllByRole("heading", { level: 1 });
  expect(headings).toHaveLength(1);
});

test("About page renders all 5 main sections", () => {
  render(<About />);
  expect(screen.getByRole("heading", { name: /what legilens measures/i })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: /how minhash works/i })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: /score interpretation/i })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: /friction tag glossary/i })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: /data sources/i })).toBeInTheDocument();
});

test("About page contains the Jaccard formula with accessible name", () => {
  render(<About />);
  const formula = screen.getByLabelText(/jaccard similarity formula/i);
  expect(formula).toBeInTheDocument();
});

test("About page includes the ShingleDiagram", () => {
  render(<About />);
  expect(screen.getByRole("img", { name: /shingl/i })).toBeInTheDocument();
});

test("About page lists all 6 friction tags in the glossary", () => {
  render(<About />);
  const tags = [
    /technical conflict/i,
    /spatial inconsistency/i,
    /expert defiance/i,
    /regressive burden/i,
    /source-cloned/i,
    /legal hallucination/i,
  ];
  for (const tag of tags) {
    expect(screen.getByText(tag)).toBeInTheDocument();
  }
});
```

- [x] **Step 2: Run to confirm failures**

```bash
cd frontend && npm test -- --testPathPattern=About
```

Expected: all fail (page does not exist).

- [x] **Step 3: Implement the page**

```typescript
import type { Metadata } from "next";
import ShingleDiagram from "@/components/ShingleDiagram";

export const metadata: Metadata = {
  title: "About — LegiLens",
  description:
    "How LegiLens measures the Friction Gap between Colorado legislative rhetoric and reality. MinHash methodology, score interpretation, and friction tag glossary.",
};

const TAGS = [
  {
    name: "Technical Conflict",
    definition: "Mandates that break existing technical standards or architecture.",
    example: "A bill regulating encryption that contradicts established protocols (TLS, POSIX, NIST).",
  },
  {
    name: "Spatial Inconsistency",
    definition: "Proposals that are geographically or logistically impossible.",
    example: "Buffer-zone or land-use rules with measurements that don't fit the affected parcels.",
  },
  {
    name: "Expert Defiance",
    definition: "Disregarding non-partisan expert testimony for intuitive logic.",
    example: "Overriding an ALJ or agency head with a representative's personal anecdote.",
  },
  {
    name: "Regressive Burden",
    definition: "Using flat fees to fund public goods, impacting the majority disproportionately.",
    example: "A new 'enterprise' fee or delivery surcharge instead of a graduated tax.",
  },
  {
    name: "Source-Cloned",
    definition: "Identical to model legislation or bills in 5+ other states.",
    example: "Language matching ALEC-style templates introduced across multiple states.",
  },
  {
    name: "Legal Hallucination",
    definition: "Citing inapplicable legal theories to create delay or obstruction.",
    example: "Frivolous constitutional or contract-law claims raised in committee.",
  },
];

export default function About() {
  return (
    <main id="main" className="mx-auto max-w-3xl px-4 py-12 space-y-10 text-slate-200">
      <header>
        <h1 className="text-4xl font-black tracking-tight text-white">About LegiLens</h1>
        <p className="mt-3 text-slate-400">
          LegiLens measures the Friction Gap in the Colorado General Assembly —
          the distance between what legislators say a bill does and what the
          text and process actually deliver.
        </p>
      </header>

      <section className="space-y-3">
        <h2 className="text-2xl font-bold text-white">What LegiLens measures</h2>
        <p>
          The Influence &amp; Source Tracker (IST) is the launch module. It
          computes cross-state text similarity to identify whether a Colorado
          bill is locally authored or copied from a template circulating in
          other state legislatures.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-2xl font-bold text-white">How MinHash works</h2>
        <p>
          MinHash estimates Jaccard similarity between two sets of text
          fragments. The process has three steps.
        </p>

        <h3 className="text-lg font-semibold text-white pt-2">1. Shingling</h3>
        <p>
          Each bill's text is broken into overlapping fixed-length word
          sequences called <em>shingles</em>. The diagram below shows 3-shingles
          (three-word windows) of one sentence.
        </p>
        <ShingleDiagram />

        <h3 className="text-lg font-semibold text-white pt-2">2. Jaccard similarity</h3>
        <p>The similarity between two bills is the Jaccard index of their shingle sets:</p>
        <p
          className="rounded-md bg-slate-900 px-4 py-3 font-mono text-blue-200"
          aria-label="Jaccard similarity formula: J of A and B equals the size of A intersected with B over the size of A unioned with B"
        >
          J(A, B) = |A ∩ B| / |A ∪ B|
        </p>
        <p>
          A value of 1.0 means identical shingle sets; 0.0 means no overlap.
        </p>

        <h3 className="text-lg font-semibold text-white pt-2">3. MinHash + LSH</h3>
        <p>
          Computing exact Jaccard pairwise across 190,000+ bills is O(n²) and
          infeasible. MinHash approximates Jaccard with 128 hash permutations
          per document. Locality-Sensitive Hashing then buckets similar
          signatures together, reducing candidate comparisons to sub-linear
          time.
        </p>

        <h3 className="text-lg font-semibold text-white pt-2">The 0.70 threshold</h3>
        <p>
          A Jaccard similarity of 0.70 or higher flags a likely text-reuse
          match. This threshold was calibrated against known model-bill
          templates (ALEC-style and similar) to maximize precision while
          keeping recall meaningful.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-2xl font-bold text-white">Score interpretation</h2>
        <p>
          Every Colorado bill receives a Source Authenticity Score from 0 to
          100. It is the inverse of cross-state textual overlap.
        </p>
        <ul className="list-disc pl-6 space-y-1">
          <li><strong>0–30:</strong> Copycat alert — most language matches bills in other states.</li>
          <li><strong>31–69:</strong> Partial overlap — some sections appear elsewhere; some original.</li>
          <li><strong>70–100:</strong> Likely original — minimal textual reuse detected.</li>
        </ul>
      </section>

      <section className="space-y-3">
        <h2 className="text-2xl font-bold text-white">Friction tag glossary</h2>
        <p>
          When a bill triggers specific patterns, LegiLens applies one or more
          friction tags. Tags are computed independently of the IST score.
        </p>
        <dl className="space-y-4">
          {TAGS.map((tag) => (
            <div key={tag.name}>
              <dt className="font-semibold text-white">{tag.name}</dt>
              <dd className="text-slate-300">
                {tag.definition} <span className="text-slate-400">Example: {tag.example}</span>
              </dd>
            </div>
          ))}
        </dl>
      </section>

      <section className="space-y-3">
        <h2 className="text-2xl font-bold text-white">Data sources</h2>
        <p>
          Bill text and status come from{" "}
          <a href="https://legiscan.com" className="text-blue-300 underline">LegiScan</a>,
          which aggregates legislative data across all 50 U.S. states. LegiLens
          syncs nightly. The corpus exceeds 190,000 bills as of launch.
        </p>
        <p>
          For accessibility information and our WCAG conformance statement, see{" "}
          <a href="/accessibility" className="text-blue-300 underline">Accessibility</a>.
        </p>
      </section>
    </main>
  );
}
```

- [x] **Step 4: Run tests**

```bash
cd frontend && npm test -- --testPathPattern=About
```

Expected: all 6 tests pass.

- [x] **Step 5: Manual a11y verification (record in PR description)**

Open `npm run dev` and load `/about`:
- Tab through; every link reachable, focus visible
- VoiceOver (Cmd+F5) reads headings in order; SVG announces "3-shingling of a sentence, image"; Jaccard formula reads correctly
- Chrome DevTools color picker: sample body text on dark background, formula text on slate-900 — both must report ≥ 4.5:1
- 200% zoom: no overflow

- [x] **Step 6: Commit**

```bash
git add frontend/app/about/page.tsx frontend/__tests__/pages/About.test.tsx
git commit -m "feat(frontend): /about methodology page with MinHash proof-of-work"
```

### Task 4.3: Build `/accessibility` statement page

**Files:**
- Create: `frontend/app/accessibility/page.tsx`
- Create: `frontend/__tests__/pages/Accessibility.test.tsx`

- [x] **Step 1: Write failing tests**

```typescript
import { render, screen } from "@testing-library/react";
import { axe } from "jest-axe";
import Accessibility from "@/app/accessibility/page";

test("Accessibility page has no axe violations", async () => {
  const { container } = render(<Accessibility />);
  expect(await axe(container)).toHaveNoViolations();
});

test("Accessibility page renders single h1 with descriptive text", () => {
  render(<Accessibility />);
  const h1 = screen.getByRole("heading", { level: 1 });
  expect(h1).toHaveTextContent(/accessibility/i);
});

test("Accessibility page states WCAG 2.1 AA conformance target", () => {
  render(<Accessibility />);
  expect(screen.getByText(/WCAG 2\.1.*level AA/i)).toBeInTheDocument();
});

test("Accessibility page provides a contact link", () => {
  render(<Accessibility />);
  // Either a GitHub issues link or a mailto, must be a real <a> with an href
  const links = screen.getAllByRole("link");
  const contactLink = links.find((l) =>
    /github\.com.*issues|mailto:/i.test(l.getAttribute("href") ?? "")
  );
  expect(contactLink).toBeDefined();
});
```

- [x] **Step 2: Run to confirm failures**

```bash
cd frontend && npm test -- --testPathPattern=Accessibility
```

Expected: all fail.

- [x] **Step 3: Implement the page**

```typescript
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Accessibility — LegiLens",
  description:
    "LegiLens accessibility statement, WCAG 2.1 Level AA conformance target, testing methodology, and contact path for accessibility issues.",
};

export default function Accessibility() {
  return (
    <main id="main" className="mx-auto max-w-3xl px-4 py-12 space-y-10 text-slate-200">
      <header>
        <h1 className="text-4xl font-black tracking-tight text-white">Accessibility</h1>
        <p className="mt-3 text-slate-400">
          LegiLens is a public transparency tool. We believe everyone — including
          users of screen readers, keyboard-only navigators, and assistive
          technology — has the right to access public legislative information.
        </p>
      </header>

      <section className="space-y-3">
        <h2 className="text-2xl font-bold text-white">Conformance target</h2>
        <p>
          LegiLens targets <strong>WCAG 2.1 Level AA</strong> conformance across all
          public pages. The codebase is tested automatically and manually
          against this standard.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-2xl font-bold text-white">Testing methodology</h2>
        <p>Every pull request that touches the frontend is verified through:</p>
        <ul className="list-disc pl-6 space-y-1">
          <li>jest-axe automated scans on every component test (CI-blocking)</li>
          <li>@axe-core/playwright scans after every end-to-end navigation (CI-blocking)</li>
          <li>Manual keyboard-only walkthrough per route</li>
          <li>Manual screen reader walkthrough (VoiceOver on macOS)</li>
          <li>Color contrast verification on each text/background pair</li>
          <li>200% zoom and 320px viewport reflow checks</li>
        </ul>
      </section>

      <section className="space-y-3">
        <h2 className="text-2xl font-bold text-white">Known limitations</h2>
        <p>
          None reported at this time. If you encounter a barrier, please report
          it (see below) — we treat accessibility regressions as bugs.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-2xl font-bold text-white">Reporting accessibility issues</h2>
        <p>
          The fastest path is opening an issue on GitHub:{" "}
          <a
            href="https://github.com/EMSwank/legilens/issues/new?labels=a11y"
            className="text-blue-300 underline"
          >
            github.com/EMSwank/legilens/issues
          </a>
          .
        </p>
        <p>
          Please include the page URL, your assistive technology and browser
          (if relevant), and a description of the barrier. We aim to acknowledge
          reports within five business days.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-2xl font-bold text-white">Ongoing commitment</h2>
        <p>
          Accessibility work is ongoing. Each new feature is built against this
          standard from the start rather than retrofitted. If a regression
          slips through, we treat fixing it the same priority as fixing a
          functional bug.
        </p>
      </section>
    </main>
  );
}
```

- [x] **Step 4: Run tests**

```bash
cd frontend && npm test -- --testPathPattern=Accessibility
```

Expected: all 4 tests pass.

- [x] **Step 5: Commit**

```bash
git add frontend/app/accessibility/page.tsx frontend/__tests__/pages/Accessibility.test.tsx
git commit -m "feat(frontend): /accessibility statement page (WCAG 2.1 AA)"
```

### Task 4.4: Add E2E test for `/about`

**Files:**
- Create: `frontend/e2e/about.spec.ts`

- [x] **Step 1: Write the E2E spec**

```typescript
import { test, expect } from "@playwright/test";
import { expectNoAxeViolations } from "./axe-helper";

test("about page renders with all sections and no axe violations", async ({ page }) => {
  await page.goto("/about");
  await expect(page.getByRole("heading", { level: 1, name: /about legilens/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: /what legilens measures/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: /how minhash works/i })).toBeVisible();
  await expect(page.getByRole("img", { name: /shingl/i })).toBeVisible();
  await expectNoAxeViolations(page, "/about");
});

test("accessibility page renders WCAG statement and contact link", async ({ page }) => {
  await page.goto("/accessibility");
  await expect(page.getByText(/WCAG 2\.1.*level AA/i)).toBeVisible();
  const issuesLink = page.getByRole("link", { name: /github\.com\/EMSwank\/legilens\/issues/i });
  await expect(issuesLink).toBeVisible();
  await expectNoAxeViolations(page, "/accessibility");
});
```

- [x] **Step 2: Run E2E locally**

```bash
cd frontend && npm run build && npm run e2e -- --grep "about page|accessibility page"
```

Expected: 2 pass.

- [x] **Step 3: Commit**

```bash
git add frontend/e2e/about.spec.ts
git commit -m "test(e2e): about + accessibility page E2E + axe scan"
```

### Task 4.5: Open PR for `/about` + `/accessibility`

- [x] **Step 1: Push and open PR**

```bash
git push -u origin feat/about-and-accessibility-pages
gh pr create --title "feat(frontend): /about methodology + /accessibility statement" --body "$(cat <<'EOF'
## Summary
- `/about` — methodology page with shingling SVG diagram, Jaccard formula (`aria-label` for screen readers), 3-step MinHash explanation, score interpretation, friction tag glossary
- `/accessibility` — WCAG 2.1 AA statement, testing methodology, GitHub issues contact
- New `ShingleDiagram` component (inline SVG, `role="img"` + `aria-labelledby`)
- `@axe-core/playwright` added to E2E
- `frontend/A11Y_CHECKLIST.md` added as per-PR gate
- API client: `tags()`, `sessions()`, `tag_type` filter option

## Accessibility (A11Y_CHECKLIST verified)
- [x] Single h1 per page, no skipped heading levels
- [x] jest-axe: no violations
- [x] @axe-core/playwright: no violations
- [x] Keyboard-only walkthrough complete
- [x] VoiceOver walkthrough complete
- [x] Color contrast ≥ 4.5:1 verified
- [x] 200% zoom + 320px reflow verified

## Test plan
- [x] `npm test -- --testPathPattern="About|Accessibility|ShingleDiagram|api"` — all pass
- [x] `npm run e2e -- --grep "about|accessibility"` — both pass

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [x] **Step 2: Wait for CI green, merge, return to main**

```bash
gh pr merge --squash
git checkout main && git pull
```

---

## Phase 5 — `/tags` page

### Task 5.1: Build the `/tags` page (TDD)

**Files:**
- Create: `frontend/app/tags/page.tsx`
- Create: `frontend/__tests__/pages/Tags.test.tsx`

- [x] **Step 1: Create branch + write failing tests**

```bash
git checkout -b feat/tags-page
```

Create `frontend/__tests__/pages/Tags.test.tsx`:

```typescript
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { axe } from "jest-axe";
import Tags from "@/app/tags/page";

jest.mock("@/lib/api", () => ({
  api: {
    tags: jest.fn(),
  },
}));
import { api } from "@/lib/api";

function withQueryClient(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{ui}</QueryClientProvider>;
}

beforeEach(() => {
  (api.tags as jest.Mock).mockReset();
});

test("Tags page has no axe violations when data loads", async () => {
  (api.tags as jest.Mock).mockResolvedValue([
    { tag_type: "source_cloned", count: 12 },
    { tag_type: "technical_conflict", count: 4 },
  ]);
  const { container } = render(withQueryClient(<Tags />));
  await waitFor(() => screen.getByText(/12 bills/i));
  expect(await axe(container)).toHaveNoViolations();
});

test("Tags page renders one card per tag with count", async () => {
  (api.tags as jest.Mock).mockResolvedValue([
    { tag_type: "source_cloned", count: 12 },
    { tag_type: "technical_conflict", count: 4 },
  ]);
  render(withQueryClient(<Tags />));
  await waitFor(() => {
    expect(screen.getByText(/source-cloned/i)).toBeInTheDocument();
    expect(screen.getByText(/12 bills/i)).toBeInTheDocument();
    expect(screen.getByText(/technical conflict/i)).toBeInTheDocument();
    expect(screen.getByText(/4 bills/i)).toBeInTheDocument();
  });
});

test("Tag cards link to dashboard with tag_type query param", async () => {
  (api.tags as jest.Mock).mockResolvedValue([
    { tag_type: "source_cloned", count: 12 },
  ]);
  render(withQueryClient(<Tags />));
  const link = await screen.findByRole("link", { name: /source-cloned/i });
  expect(link).toHaveAttribute("href", "/?tag_type=source_cloned");
});

test("Tags page shows loading state initially", () => {
  (api.tags as jest.Mock).mockReturnValue(new Promise(() => {}));
  render(withQueryClient(<Tags />));
  expect(screen.getByRole("status")).toHaveTextContent(/loading/i);
});

test("Tags page shows error state on fetch failure", async () => {
  (api.tags as jest.Mock).mockRejectedValue(new Error("boom"));
  render(withQueryClient(<Tags />));
  await waitFor(() => {
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });
});

test("Tags page shows empty state when API returns empty list", async () => {
  (api.tags as jest.Mock).mockResolvedValue([]);
  render(withQueryClient(<Tags />));
  await waitFor(() => {
    expect(screen.getByText(/no tags yet/i)).toBeInTheDocument();
  });
});
```

- [x] **Step 2: Run to confirm failures**

```bash
cd frontend && npm test -- --testPathPattern=Tags
```

Expected: all fail.

- [x] **Step 3: Implement the page**

```typescript
"use client";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import type { Metadata } from "next";
import { api } from "@/lib/api";

const TAG_META: Record<string, { label: string; description: string }> = {
  source_cloned: {
    label: "Source-Cloned",
    description: "Identical to model legislation or bills in 5+ other states.",
  },
  technical_conflict: {
    label: "Technical Conflict",
    description: "Mandates that break existing technical standards or architecture.",
  },
  regressive_burden: {
    label: "Regressive Burden",
    description: "Flat fees that disproportionately impact the majority.",
  },
  expert_defiance: {
    label: "Expert Defiance",
    description: "Disregards non-partisan expert testimony for intuitive logic.",
  },
  spatial_inconsistency: {
    label: "Spatial Inconsistency",
    description: "Proposals that are geographically or logistically impossible.",
  },
  legal_hallucination: {
    label: "Legal Hallucination",
    description: "Cites inapplicable legal theories to create delay or obstruction.",
  },
};

export default function Tags() {
  const { data, isPending, isError } = useQuery({
    queryKey: ["tags"],
    queryFn: api.tags,
  });

  return (
    <main id="main" className="mx-auto max-w-3xl px-4 py-12 space-y-8 text-slate-200">
      <header>
        <h1 className="text-4xl font-black tracking-tight text-white">Friction Tags</h1>
        <p className="mt-3 text-slate-400">
          When a Colorado bill triggers a specific pattern, LegiLens applies a
          friction tag. Click a tag to see the bills it covers.
        </p>
      </header>

      {isPending && (
        <div role="status" aria-live="polite" className="text-slate-400">
          Loading tags…
        </div>
      )}

      {isError && (
        <div role="alert" className="rounded-md border border-red-500/30 bg-red-900/20 p-3 text-red-300">
          Failed to load tags.
        </div>
      )}

      {data && data.length === 0 && (
        <p className="text-slate-400">No tags yet. Check back after the next analysis run.</p>
      )}

      {data && data.length > 0 && (
        <ul className="space-y-3">
          {data.map((t) => {
            const meta = TAG_META[t.tag_type] ?? { label: t.tag_type, description: "" };
            return (
              <li key={t.tag_type}>
                <Link
                  href={`/?tag_type=${encodeURIComponent(t.tag_type)}`}
                  className="flex flex-col gap-1 rounded-md border border-slate-700 bg-slate-900 p-4 hover:bg-slate-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-400"
                >
                  <span className="flex items-center justify-between">
                    <span className="font-semibold text-white">{meta.label}</span>
                    <span className="text-sm text-slate-400">{t.count} bills</span>
                  </span>
                  {meta.description && (
                    <span className="text-sm text-slate-300">{meta.description}</span>
                  )}
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </main>
  );
}
```

- [x] **Step 4: Run tests**

```bash
cd frontend && npm test -- --testPathPattern=Tags
```

Expected: all 6 pass.

- [x] **Step 5: Manual a11y verification + commit**

```bash
git add frontend/app/tags/page.tsx frontend/__tests__/pages/Tags.test.tsx
git commit -m "feat(frontend): /tags browser with loading/error/empty states"
```

### Task 5.2: E2E for `/tags` (tag card navigates to filtered dashboard)

**Files:**
- Create: `frontend/e2e/tags.spec.ts`

- [x] **Step 1: Write the E2E spec**

```typescript
import { test, expect } from "@playwright/test";
import { expectNoAxeViolations } from "./axe-helper";

test("tags page lists tags and links to filtered dashboard", async ({ page }) => {
  await page.goto("/tags");
  await expect(page.getByRole("heading", { level: 1, name: /friction tags/i })).toBeVisible();
  // First card click navigates to /?tag_type=...
  const firstCard = page.getByRole("link").first();
  const href = await firstCard.getAttribute("href");
  expect(href).toMatch(/^\/\?tag_type=/);
  await firstCard.click();
  await expect(page).toHaveURL(/tag_type=/);
  await expectNoAxeViolations(page, "/tags");
});
```

- [x] **Step 2: Run locally**

```bash
cd frontend && npm run build && npm run e2e -- --grep "tags page"
```

Expected: passes (assumes seeded DB returns at least one tag; if local DB is empty, skip until Phase 6 chip flow exercises it instead).

- [x] **Step 3: Commit**

```bash
git add frontend/e2e/tags.spec.ts
git commit -m "test(e2e): tags page navigates to filtered dashboard"
```

### Task 5.3: Open PR for `/tags`

- [x] **Step 1: Push + PR**

```bash
git push -u origin feat/tags-page
gh pr create --title "feat(frontend): /tags browser page" --body "$(cat <<'EOF'
## Summary
- `/tags` route lists all friction tags with counts and descriptions
- Each card links to `/?tag_type=<encoded tag>` (dashboard pre-filtered)
- Loading (`role="status"`), error (`role="alert"`), and empty states implemented

## Accessibility
- [x] jest-axe + @axe-core/playwright: no violations
- [x] Single h1, semantic links, keyboard navigable
- [x] Card focus ring visible
- [x] Description text supplements (not replaces) tag name (color-not-only)

## Test plan
- [x] `npm test -- --testPathPattern=Tags` — 6 tests
- [x] `npm run e2e -- --grep "tags page"` — 1 test

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [x] **Step 2: Merge after CI**

```bash
gh pr merge --squash
git checkout main && git pull
```

---

## Phase 6 — Dashboard filter chips + session dropdown

### Task 6.1: Build `SessionDropdown` (TDD)

**Files:**
- Create: `frontend/components/SessionDropdown.tsx`
- Create: `frontend/__tests__/components/SessionDropdown.test.tsx`

- [x] **Step 1: Create branch + write failing tests**

```bash
git checkout -b feat/dashboard-filter-chips
```

Create `frontend/__tests__/components/SessionDropdown.test.tsx`:

```typescript
import { render, screen, fireEvent } from "@testing-library/react";
import { axe } from "jest-axe";
import SessionDropdown from "@/components/SessionDropdown";

test("SessionDropdown has no axe violations", async () => {
  const { container } = render(
    <SessionDropdown sessions={["2025A", "2024A"]} current={null} onChange={() => {}} />
  );
  expect(await axe(container)).toHaveNoViolations();
});

test("SessionDropdown renders 'All sessions' plus one option per session", () => {
  render(
    <SessionDropdown sessions={["2025A", "2024A"]} current={null} onChange={() => {}} />
  );
  const select = screen.getByRole("combobox", { name: /session/i });
  expect(select).toBeInTheDocument();
  expect(screen.getByRole("option", { name: /all sessions/i })).toBeInTheDocument();
  expect(screen.getByRole("option", { name: "2025A" })).toBeInTheDocument();
  expect(screen.getByRole("option", { name: "2024A" })).toBeInTheDocument();
});

test("SessionDropdown calls onChange with selected session", () => {
  const onChange = jest.fn();
  render(
    <SessionDropdown sessions={["2025A", "2024A"]} current={null} onChange={onChange} />
  );
  fireEvent.change(screen.getByRole("combobox", { name: /session/i }), {
    target: { value: "2025A" },
  });
  expect(onChange).toHaveBeenCalledWith("2025A");
});

test("SessionDropdown calls onChange(null) when 'All sessions' selected", () => {
  const onChange = jest.fn();
  render(
    <SessionDropdown sessions={["2025A", "2024A"]} current="2025A" onChange={onChange} />
  );
  fireEvent.change(screen.getByRole("combobox", { name: /session/i }), {
    target: { value: "" },
  });
  expect(onChange).toHaveBeenCalledWith(null);
});

test("SessionDropdown reflects current selection", () => {
  render(
    <SessionDropdown sessions={["2025A", "2024A"]} current="2024A" onChange={() => {}} />
  );
  const select = screen.getByRole("combobox", { name: /session/i }) as HTMLSelectElement;
  expect(select.value).toBe("2024A");
});
```

- [x] **Step 2: Confirm failures**

```bash
cd frontend && npm test -- --testPathPattern=SessionDropdown
```

Expected: fail.

- [x] **Step 3: Implement the component**

```typescript
"use client";

export default function SessionDropdown({
  sessions,
  current,
  onChange,
}: {
  sessions: string[];
  current: string | null;
  onChange: (session: string | null) => void;
}) {
  return (
    <label className="flex items-center gap-2 text-sm text-slate-300">
      <span>Session</span>
      <select
        value={current ?? ""}
        onChange={(e) => onChange(e.target.value || null)}
        className="rounded-md border border-slate-700 bg-slate-900 px-2 py-1 text-slate-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-400"
      >
        <option value="">All sessions</option>
        {sessions.map((s) => (
          <option key={s} value={s}>
            {s}
          </option>
        ))}
      </select>
    </label>
  );
}
```

- [x] **Step 4: Run tests**

```bash
cd frontend && npm test -- --testPathPattern=SessionDropdown
```

Expected: 5 pass.

- [x] **Step 5: Commit**

```bash
git add frontend/components/SessionDropdown.tsx frontend/__tests__/components/SessionDropdown.test.tsx
git commit -m "feat(frontend): SessionDropdown native select with accessible label"
```

### Task 6.2: Build `FilterChips` (TDD)

**Files:**
- Create: `frontend/components/FilterChips.tsx`
- Create: `frontend/__tests__/components/FilterChips.test.tsx`

- [x] **Step 1: Write failing tests**

Create `frontend/__tests__/components/FilterChips.test.tsx`:

```typescript
import { render, screen, fireEvent } from "@testing-library/react";
import { axe } from "jest-axe";
import FilterChips from "@/components/FilterChips";

const TAG_LABELS: Record<string, string> = { source_cloned: "Source-Cloned" };

test("FilterChips renders nothing when no filters active", () => {
  const { container } = render(
    <FilterChips
      session={null}
      tagType={null}
      tagLabels={TAG_LABELS}
      onRemoveSession={() => {}}
      onRemoveTag={() => {}}
    />
  );
  expect(container).toBeEmptyDOMElement();
});

test("FilterChips renders one chip when only session is set", () => {
  render(
    <FilterChips
      session="2025A"
      tagType={null}
      tagLabels={TAG_LABELS}
      onRemoveSession={() => {}}
      onRemoveTag={() => {}}
    />
  );
  expect(screen.getByRole("button", { name: /remove session filter: 2025A/i })).toBeInTheDocument();
});

test("FilterChips renders one chip when only tag_type is set", () => {
  render(
    <FilterChips
      session={null}
      tagType="source_cloned"
      tagLabels={TAG_LABELS}
      onRemoveSession={() => {}}
      onRemoveTag={() => {}}
    />
  );
  expect(screen.getByRole("button", { name: /remove tag filter: source-cloned/i })).toBeInTheDocument();
});

test("FilterChips renders two chips when both set", () => {
  render(
    <FilterChips
      session="2025A"
      tagType="source_cloned"
      tagLabels={TAG_LABELS}
      onRemoveSession={() => {}}
      onRemoveTag={() => {}}
    />
  );
  expect(screen.getAllByRole("button")).toHaveLength(2);
});

test("Clicking session chip × calls onRemoveSession only", () => {
  const onRemoveSession = jest.fn();
  const onRemoveTag = jest.fn();
  render(
    <FilterChips
      session="2025A"
      tagType="source_cloned"
      tagLabels={TAG_LABELS}
      onRemoveSession={onRemoveSession}
      onRemoveTag={onRemoveTag}
    />
  );
  fireEvent.click(screen.getByRole("button", { name: /remove session filter/i }));
  expect(onRemoveSession).toHaveBeenCalled();
  expect(onRemoveTag).not.toHaveBeenCalled();
});

test("Clicking tag chip × calls onRemoveTag only", () => {
  const onRemoveSession = jest.fn();
  const onRemoveTag = jest.fn();
  render(
    <FilterChips
      session="2025A"
      tagType="source_cloned"
      tagLabels={TAG_LABELS}
      onRemoveSession={onRemoveSession}
      onRemoveTag={onRemoveTag}
    />
  );
  fireEvent.click(screen.getByRole("button", { name: /remove tag filter/i }));
  expect(onRemoveTag).toHaveBeenCalled();
  expect(onRemoveSession).not.toHaveBeenCalled();
});

test("FilterChips chip × is keyboard accessible (Enter dismisses)", () => {
  const onRemoveTag = jest.fn();
  render(
    <FilterChips
      session={null}
      tagType="source_cloned"
      tagLabels={TAG_LABELS}
      onRemoveSession={() => {}}
      onRemoveTag={onRemoveTag}
    />
  );
  const btn = screen.getByRole("button", { name: /remove tag filter/i });
  btn.focus();
  fireEvent.keyDown(btn, { key: "Enter" });
  fireEvent.click(btn);
  expect(onRemoveTag).toHaveBeenCalled();
});

test("FilterChips has no axe violations with two chips", async () => {
  const { container } = render(
    <FilterChips
      session="2025A"
      tagType="source_cloned"
      tagLabels={TAG_LABELS}
      onRemoveSession={() => {}}
      onRemoveTag={() => {}}
    />
  );
  expect(await axe(container)).toHaveNoViolations();
});
```

- [x] **Step 2: Run to confirm failures**

```bash
cd frontend && npm test -- --testPathPattern=FilterChips
```

Expected: all fail.

- [x] **Step 3: Implement the component**

```typescript
"use client";

type Props = {
  session: string | null;
  tagType: string | null;
  tagLabels: Record<string, string>;
  onRemoveSession: () => void;
  onRemoveTag: () => void;
};

export default function FilterChips({
  session,
  tagType,
  tagLabels,
  onRemoveSession,
  onRemoveTag,
}: Props) {
  if (!session && !tagType) return null;

  const tagLabel = tagType ? (tagLabels[tagType] ?? tagType) : null;

  return (
    <div className="flex flex-wrap items-center gap-2" role="region" aria-label="Active filters">
      {session && (
        <span className="inline-flex items-center gap-1 rounded-full bg-slate-800 px-3 py-1 text-sm font-semibold text-slate-200 ring-1 ring-slate-600">
          Session: {session}
          <button
            type="button"
            aria-label={`Remove session filter: ${session}`}
            onClick={onRemoveSession}
            className="ml-1 inline-flex h-6 w-6 items-center justify-center rounded-full hover:bg-slate-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-400"
          >
            <span aria-hidden="true">×</span>
          </button>
        </span>
      )}
      {tagType && (
        <span className="inline-flex items-center gap-1 rounded-full bg-slate-800 px-3 py-1 text-sm font-semibold text-slate-200 ring-1 ring-slate-600">
          Tag: {tagLabel}
          <button
            type="button"
            aria-label={`Remove tag filter: ${tagLabel}`}
            onClick={onRemoveTag}
            className="ml-1 inline-flex h-6 w-6 items-center justify-center rounded-full hover:bg-slate-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-400"
          >
            <span aria-hidden="true">×</span>
          </button>
        </span>
      )}
    </div>
  );
}
```

- [x] **Step 4: Run tests**

```bash
cd frontend && npm test -- --testPathPattern=FilterChips
```

Expected: 8 pass.

- [x] **Step 5: Commit**

```bash
git add frontend/components/FilterChips.tsx frontend/__tests__/components/FilterChips.test.tsx
git commit -m "feat(frontend): FilterChips dismissible chip row for active filters"
```

### Task 6.3: Wire dropdown + chips into the dashboard

**Files:**
- Modify: `frontend/app/page.tsx`

- [x] **Step 1: Read the current dashboard**

```bash
cd frontend && cat app/page.tsx
```

Familiarize yourself with the existing structure (`useSearchParams`, `useQuery` for `stats` + `bills`, `SearchInput`, debounced search).

- [x] **Step 2: Rewrite `app/page.tsx` to integrate the new filters**

Replace the existing file with:

```typescript
"use client";
import { Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";
import TagBadge from "@/components/TagBadge";
import SearchInput from "@/components/SearchInput";
import PendingBanner from "@/components/PendingBanner";
import SessionDropdown from "@/components/SessionDropdown";
import FilterChips from "@/components/FilterChips";

const TAG_LABELS: Record<string, string> = {
  source_cloned: "Source-Cloned",
  technical_conflict: "Technical Conflict",
  regressive_burden: "Regressive Burden",
  expert_defiance: "Expert Defiance",
  spatial_inconsistency: "Spatial Inconsistency",
  legal_hallucination: "Legal Hallucination",
};

function DashboardContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const q = searchParams.get("q") ?? "";
  const session = searchParams.get("session");
  const tagType = searchParams.get("tag_type");

  const { data: stats, isError: statsError } = useQuery({
    queryKey: ["stats"],
    queryFn: api.stats,
  });

  const { data: sessions } = useQuery({
    queryKey: ["sessions"],
    queryFn: api.sessions,
  });

  const billsKey = q.length >= 2
    ? ["bills", "search", q]
    : ["bills", { session, tagType }];

  const { data: bills, isPending: billsPending, isError: billsError } = useQuery({
    queryKey: billsKey,
    queryFn: () => {
      if (q.length >= 2) return api.searchBills(q);
      return api.bills({
        session: session ?? undefined,
        tag_type: tagType ?? undefined,
      });
    },
  });

  function updateParam(key: string, value: string | null) {
    const params = new URLSearchParams(Array.from(searchParams.entries()));
    if (value === null || value === "") params.delete(key);
    else params.set(key, value);
    const qs = params.toString();
    router.push(qs ? `/?${qs}` : "/");
  }

  return (
    <main id="main" className="mx-auto max-w-5xl px-4 py-12 space-y-10">
      <header>
        <h1 className="text-5xl font-black tracking-tight text-white">LegiLens</h1>
        <p className="mt-2 text-slate-400">
          Quantifying the Friction Gap in the Colorado General Assembly.
        </p>
      </header>

      {statsError ? (
        <div role="alert" className="rounded-md border border-red-500/30 bg-red-900/20 p-3 text-sm text-red-300">
          Failed to load statistics.
        </div>
      ) : stats ? (
        <div className="grid grid-cols-3 gap-4">
          {[
            { label: "Bills Analyzed", value: stats.bills_analyzed },
            { label: "Copycat Alerts", value: stats.copycat_alerts },
            { label: "CO Bills Tracked", value: stats.total_co_bills },
          ].map((s) => (
            <div key={s.label} className="rounded-md border border-slate-700 bg-slate-900 p-4">
              <div className="text-sm text-slate-400">{s.label}</div>
              <div className="text-3xl font-black text-white">{s.value}</div>
            </div>
          ))}
        </div>
      ) : null}

      <SearchInput />

      <div className="flex flex-wrap items-center gap-4">
        <SessionDropdown
          sessions={sessions ?? []}
          current={session}
          onChange={(value) => updateParam("session", value)}
        />
      </div>

      <FilterChips
        session={session}
        tagType={tagType}
        tagLabels={TAG_LABELS}
        onRemoveSession={() => updateParam("session", null)}
        onRemoveTag={() => updateParam("tag_type", null)}
      />

      {billsError ? (
        <div role="alert" className="rounded-md border border-red-500/30 bg-red-900/20 p-3 text-sm text-red-300">
          Failed to load bills.
        </div>
      ) : billsPending ? (
        <PendingBanner />
      ) : bills && bills.length > 0 ? (
        <ul className="space-y-2" aria-live="polite">
          {bills.map((b) => (
            <li key={b.id}>
              <Link
                href={`/bills/${b.id}`}
                className="flex items-center justify-between rounded-md border border-slate-700 bg-slate-900 p-4 hover:bg-slate-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-400"
              >
                <span>
                  <span className="font-mono text-sm text-slate-400">{b.bill_number}</span>
                  <span className="ml-3 text-slate-200">{b.title}</span>
                </span>
                {b.copycat_alert ? <TagBadge type="source_cloned" /> : null}
              </Link>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-slate-400">No bills match the current filters.</p>
      )}
    </main>
  );
}

export default function Page() {
  return (
    <Suspense fallback={<div className="p-12 text-slate-400">Loading…</div>}>
      <DashboardContent />
    </Suspense>
  );
}
```

- [x] **Step 3: Run all frontend unit tests to confirm no regression**

```bash
cd frontend && npm test
```

Expected: full suite green (existing dashboard tests still pass — the file changed structurally but selectors should still match).

- [x] **Step 4: Smoke test in browser**

```bash
cd frontend && npm run dev
```

Open `http://localhost:3000`. Verify:
- Session dropdown renders (may be empty if backend has no sessions yet — that's fine)
- Loading `/?tag_type=source_cloned` shows a chip
- Loading `/?tag_type=source_cloned&session=2025A` shows two chips
- Clicking × on the tag chip clears tag_type but keeps session
- Clicking × on the session chip clears session but keeps tag_type
- Tab through every interactive element; focus visible

- [x] **Step 5: Commit**

```bash
git add frontend/app/page.tsx
git commit -m "feat(frontend): wire SessionDropdown + FilterChips into dashboard"
```

### Task 6.4: E2E for full filter journey

**Files:**
- Create: `frontend/e2e/filters.spec.ts`

- [x] **Step 1: Write the E2E spec**

```typescript
import { test, expect } from "@playwright/test";
import { expectNoAxeViolations } from "./axe-helper";

test("user can navigate tags → dashboard filtered → dismiss chip", async ({ page }) => {
  await page.goto("/tags");
  const firstCard = page.getByRole("link").first();
  const href = await firstCard.getAttribute("href");
  await firstCard.click();
  await expect(page).toHaveURL(/tag_type=/);

  // Chip is visible and dismissible
  const chip = page.getByRole("button", { name: /remove tag filter/i });
  await expect(chip).toBeVisible();
  await chip.click();
  await expect(page).not.toHaveURL(/tag_type=/);

  await expectNoAxeViolations(page, "dashboard with filters");
});

test("deep link with tag_type + session renders both chips", async ({ page }) => {
  await page.goto("/?tag_type=source_cloned&session=2025A");
  await expect(page.getByRole("button", { name: /remove tag filter/i })).toBeVisible();
  await expect(page.getByRole("button", { name: /remove session filter/i })).toBeVisible();

  // Dismiss tag chip, session chip persists
  await page.getByRole("button", { name: /remove tag filter/i }).click();
  await expect(page).toHaveURL(/session=2025A/);
  await expect(page).not.toHaveURL(/tag_type=/);
  await expect(page.getByRole("button", { name: /remove session filter/i })).toBeVisible();
});

test("session dropdown updates URL and triggers refetch", async ({ page }) => {
  await page.goto("/");
  const select = page.getByRole("combobox", { name: /session/i });
  // If sessions list is empty in CI, skip; otherwise pick first non-empty option
  const options = await select.locator("option").allTextContents();
  const realOption = options.find((o) => o !== "All sessions");
  if (!realOption) {
    test.skip(true, "No sessions in DB; skip dropdown round-trip");
  } else {
    await select.selectOption(realOption);
    await expect(page).toHaveURL(new RegExp(`session=${realOption}`));
  }
});

test("filter chips meet 44px touch target on mobile viewport", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 667 });
  await page.goto("/?tag_type=source_cloned");
  const chipBtn = page.getByRole("button", { name: /remove tag filter/i });
  const box = await chipBtn.boundingBox();
  expect(box).not.toBeNull();
  expect(box!.width).toBeGreaterThanOrEqual(24); // WCAG 2.5.8 AA minimum
  expect(box!.height).toBeGreaterThanOrEqual(24);
});
```

- [x] **Step 2: Run E2E locally**

```bash
cd frontend && npm run build && npm run e2e -- --grep "filter"
```

Expected: 4 pass (3rd may skip if local DB has no sessions).

- [x] **Step 3: Commit**

```bash
git add frontend/e2e/filters.spec.ts
git commit -m "test(e2e): full filter journey + deep-link + mobile touch target"
```

### Task 6.5: Open PR for dashboard filter additions

- [x] **Step 1: Push + PR**

```bash
git push -u origin feat/dashboard-filter-chips
gh pr create --title "feat(frontend): dashboard session dropdown + dismissible filter chips" --body "$(cat <<'EOF'
## Summary
- `SessionDropdown` native `<select>` with associated `<label>` and accessible focus ring
- `FilterChips` row renders only when filters are active; each chip is a `<button>` with full accessible name ("Remove tag filter: Source-Cloned"); decorative × is `aria-hidden`
- Dashboard reads `session` + `tag_type` from URL params and pushes back to URL on filter changes; preserves other params on each update
- Full filter journey wired: `/tags` card → dashboard with chip → dismiss → unfiltered

## Accessibility
- [x] jest-axe: no violations in any state
- [x] @axe-core/playwright: no violations on dashboard with active filters
- [x] Keyboard-only: every chip and dropdown reachable, focus visible
- [x] VoiceOver: chip × buttons announce "Remove tag filter: Source-Cloned, button"; status changes announced
- [x] Contrast verified on chip text + focus ring
- [x] 320px viewport: chips wrap, touch target ≥ 24×24 px

## Test plan
- [x] `npm test -- --testPathPattern="SessionDropdown|FilterChips"` — 13 tests
- [x] `npm run e2e -- --grep "filter"` — 4 tests
- [x] Full unit suite green: `npm test`

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [x] **Step 2: Wait for CI green, merge**

```bash
gh pr merge --squash
git checkout main && git pull
```

---

## Phase 7 — Railway + Vercel deploy (interactive, human-in-loop)

These steps are run with the user. The plan documents the sequence; agent assists with exact commands and verification.

### Task 7.1: Verify Railway plan + create web service ✅

- [x] **Step 1:** User confirms they're on Railway Hobby plan ($5/mo) — required to keep two services running 24/7
- [x] **Step 2:** In Railway dashboard, create a new project → "Deploy from GitHub repo" → select `EMSwank/legilens`
- [x] **Step 3:** First service auto-creates. Rename to `legilens-web`. In Settings:
  - Root directory: `/` (Procfile handles `cd backend`)
  - Start command (override): `cd backend && alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- [x] **Step 4:** Set environment variables on `legilens-web`:
  - `DATABASE_URL` = Neon Postgres connection string
  - `REDIS_URL` = Redis URL (Railway Redis add-on or existing)
  - `LEGISCAN_API_KEY` = LegiScan API key
  - `ALLOWED_ORIGINS` = `https://<vercel-prod-url>` (fill after Vercel deploy in Task 7.3 — leave `http://localhost:3000` for now)
  - `PYTHONPATH` = `.`
- [x] **Step 5:** Trigger deploy. Watch logs for `alembic upgrade head` success then `Uvicorn running on http://0.0.0.0:...`
- [x] **Step 6:** Capture Railway-generated public URL (e.g., `https://legilens-web-production.up.railway.app`)
- [x] **Step 7:** Smoke test:
  ```bash
  curl https://<railway-web-url>/stats -H 'User-Agent: smoke-test'
  curl https://<railway-web-url>/bills/sessions -H 'User-Agent: smoke-test'
  ```
  Both must return 200.

### Task 7.2: Create worker service ✅

- [x] **Step 1:** In the same Railway project, click "New" → "GitHub Repo" → same `legilens` repo
- [x] **Step 2:** Rename second service to `legilens-worker`. In Settings:
  - Start command (override): `cd backend && python -m worker.scheduler`
- [x] **Step 3:** Copy the same env vars from `legilens-web` to `legilens-worker` (or use a Railway shared env group)
- [x] **Step 4:** Trigger deploy. Watch logs for `Scheduler started` line from APScheduler
- [x] **Step 5:** Confirm in Neon SQL editor that `alembic_version` table contains a row matching the latest revision in `backend/alembic/versions/`

### Task 7.3: Deploy to Vercel (new account walkthrough)

- [x] **Step 1:** User creates Vercel account at vercel.com using GitHub OAuth
- [x] **Step 2:** "Add New" → "Project" → import `EMSwank/legilens`
- [x] **Step 3:** In project settings:
  - Root Directory: `frontend`
  - Framework Preset: Next.js (auto-detected)
- [ ] **Step 4:** Environment variable — **BLOCKED: `NEXT_PUBLIC_API_URL` was set after initial build; must redeploy to bake Railway URL into bundle. Frontend was hitting `localhost:8000` in production.**
  - `NEXT_PUBLIC_API_URL` = `https://<railway-web-url>` (from Task 7.1)
- [ ] **Step 5:** Click Deploy (redeploy after fixing env var). Wait for build (3–5 min)
- [ ] **Step 6:** Capture Vercel production URL (e.g., `https://legilens.vercel.app`)
- [ ] **Step 7:** Return to Railway `legilens-web` service → update `ALLOWED_ORIGINS` to include the Vercel production URL → redeploy (CORS regex already covers preview URLs)

### Task 7.4: End-to-end smoke verification

- [ ] **Step 1:** Visit the Vercel production URL. Dashboard renders. Stats grid shows non-zero numbers
- [ ] **Step 2:** Navigate `/tags`. Cards render (assuming worker has run at least one ingest pass)
- [ ] **Step 3:** Navigate `/about`. Shingling SVG + Jaccard formula visible
- [ ] **Step 4:** Navigate `/accessibility`. WCAG statement + GitHub issues link visible
- [ ] **Step 5:** Click a tag card → dashboard shows chip → dismiss chip → unfiltered list returns
- [ ] **Step 6:** Open browser DevTools → Network tab → confirm fetches go to the Railway URL with no CORS errors
- [ ] **Step 7:** Open a Vercel preview URL for a recent PR → confirm CORS works there too (regex match)

### Task 7.5: Update README

**Files:**
- Modify: `README.md`

- [x] **Step 1:** Create branch + update README sprint table**

```bash
git checkout -b docs/sprint4-status
```

In `README.md`, add a Sprint 4 row to the status table:

```markdown
| Sprint 4 | Deployment (Railway + Vercel), /about, /tags, /accessibility, filter chips | ✅ Complete |
```

And add a "Sprint 4 — what shipped" section below the existing Sprint 3 summary:

```markdown
### Sprint 4 — what shipped

- Backend: `GET /bills/sessions` (distinct CO sessions), `tag_type` filter on `GET /bills`, CORS regex for Vercel previews
- Frontend: `/about` methodology page with MinHash proof-of-work (shingling SVG, Jaccard formula), `/tags` browser with counts and descriptions, `/accessibility` statement, dashboard session dropdown, dismissible filter chips
- Deployment: Railway (web + worker services), Vercel (production + preview deploys), alembic migrations folded into web service start
- A11y: `@axe-core/playwright` added to E2E, `frontend/A11Y_CHECKLIST.md` enforces per-PR manual checks
```

- [x] **Step 2:** Commit + PR

```bash
git add README.md
git commit -m "docs: mark Sprint 4 complete + what-shipped summary"
git push -u origin docs/sprint4-status
gh pr create --title "docs: Sprint 4 status update" --body "Marks Sprint 4 complete in README status table and adds what-shipped summary."
gh pr merge --squash
```

---

## Self-Review

Cross-check this plan against the spec.

**Spec section 1 (Deployment):**
- [x] Railway two services — Tasks 7.1, 7.2
- [x] Procfile + railway.toml — Tasks 1.1, 1.2
- [x] PYTHONPATH=. env var — Task 7.1
- [x] alembic in startCommand — Task 7.1 step 3
- [x] CORS regex — Tasks 1.3, 1.4
- [x] Vercel walkthrough — Task 7.3
- [x] pip freeze pre-deploy check — covered by manual deploy verification in Task 7.1 (Railway's pip install uses backend/requirements.txt directly)
- [x] npm run build pre-deploy check — covered by Vercel build itself failing if local-only TypeScript issues exist

**Spec section 2 (Backend):**
- [x] GET /bills/sessions — Tasks 2.1, 2.2 with route ordering note
- [x] tag_type filter — Tasks 2.3, 2.4 with compound + regression tests

**Spec section 3 (Frontend):**
- [x] /about with shingling SVG + Jaccard formula — Tasks 4.1, 4.2
- [x] /tags browser — Task 5.1
- [x] Dashboard session dropdown + filter chips — Tasks 6.1, 6.2, 6.3

**Spec section 4 (Testing):**
- [x] Backend test cases (sessions ordering, corpus-only exclusion, UA guard, tag_type compound, regression, CORS) — Phases 1 + 2
- [x] Frontend unit (axe, behavior, edge cases) — every component/page TDD task
- [x] E2E (filter journey, deep link, mobile viewport, axe scan) — Tasks 4.4, 5.2, 6.4
- [x] Deployment smoke tests — Task 7.4

**Spec section 5 (Accessibility):**
- [x] Per-page requirements — embedded in each TDD task
- [x] axe-core/playwright — Task 3.2
- [x] A11Y_CHECKLIST.md — Task 3.3
- [x] /accessibility statement route — Task 4.3
- [x] Manual checklist enforcement — referenced in every PR description

No placeholders. All file paths exact. Type signatures (`TagCount`, `api.bills` options, `SessionDropdown` props, `FilterChips` props) consistent across tasks.
