# WS3 — Coverage Tracker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a `/coverage` page that makes the slow corpus build visible — per-state ingest status + a single headline "matchable %" scoped to the current ingest target (Colorado + 5 comparison states).

**Architecture:** A nightly worker computes one coverage snapshot (per-state `{fetchable, with_sig}` counts) and persists it as JSON in the existing `worker_state` table. A read-only `GET /coverage` endpoint reads that one row and derives per-state statuses + the scoped matchable %. The frontend renders an accessible table (source of truth) with an inline, decorative status dot per row plus a headline matchable-% number — no separate geographic map in the MVP. No new DB migration, no new table.

**Tech Stack:** Python 3 / SQLAlchemy 2 async / FastAPI / Pydantic v2 / pytest-asyncio (backend); Next.js 16 / React 19 / TanStack Query / Tailwind / jest-axe / Playwright (frontend).

---

## Source of truth

Design spec: `docs/superpowers/specs/2026-06-02-co-related-bills-coverage-tracker-design.md` §5 (WS3). This plan implements that section verbatim, with two design refinements forced by codebase facts verified 2026-06-03:

1. **C-path aggregation (not SQL `GROUP BY`).** The test suite is 100% mock-only — there is **no** real DB engine in `backend/tests/` and `aiosqlite` is not installed; and `create_all` cannot run on SQLite because the models are Postgres-locked (`postgresql.UUID`, `ARRAY(BIGINT)`, `JSONB`). So the hazardous counting logic must live in a **pure Python function** (`aggregate_coverage`) that is unit-testable with no DB, fed by a read query that emits **one boolean-per-bill row** via `EXISTS` (no join → fan-out double-count is structurally impossible).
2. **`as_of` comes from `worker_state.updated_at`**, set explicitly in the upsert `set_=` (the model's `onupdate=func.now()` does **not** fire on the `pg_insert ... on_conflict_do_update` path — proven by `_mark_bootstrap_ran` in `scheduler.py`, which sets it explicitly). The timestamp is **not** embedded in the JSON.

### Load-bearing invariants (do not "simplify" away)

- **`with_sig` is AND-gated on `has_doc`.** A MinHash signature can exist for a bill with `text_doc_id IS NULL` (ingest's rare inline-text path: `backend/worker/tasks/ingest.py:247-256` writes a signature while `text_doc_id` at line 231 may be `None`). Without the AND-gate, per-state `with_sig` could exceed `fetchable` → ratio > 1.0 → false "complete" dot and matchable % > 100. The gate makes `with_sig ≤ fetchable` always true, so the ratio is always ≤ 1.
- **Read query uses `EXISTS`, never `LEFT JOIN`.** A join to `minhash_signatures` fan-out double-counts `fetchable` for any bill with duplicate signature rows (dupes existed historically — Alembic 004 added the `UNIQUE(bill_id)` constraint *because* of them; the `DISTINCT ON` guards are still kept as belt-and-suspenders). `EXISTS` short-circuits to one boolean per bill.
- **Honesty / scope:** the headline matchable % denominator is **scoped to `SCOPE = {CO, CA, NY, IL, TX, FL}`** (the current ingest target), not the full ~1M-bill corpus. A full-corpus denominator would top out near a few percent forever and read as broken. The page must label the metric "of the current target corpus (Colorado + 5 comparison states)".
- **`SCOPE` must stay in sync with `backend/worker/queue.py` `_STATE_PRIORITY`** (CO=tier 0, the five = tier 1). WS2 keys fetch scope off those tiers; if they drift, the coverage denominator and the actual fetch scope diverge. Reference the same five states; add a comment in both files pointing at each other.

---

## File Structure

**Backend — create:**
- `backend/app/services/coverage.py` — pure helpers (no DB): `SCOPE`, `aggregate_coverage(rows)`, `build_snapshot_payload(rows)`, `derive_state_status(fetchable, with_sig)`, `scoped_matchable_pct(per_state)`.
- `backend/app/schemas/coverage.py` — `StateCoverage`, `CoverageOut`.
- `backend/app/routers/coverage.py` — `GET /coverage`.
- `backend/worker/tasks/coverage.py` — `compute_and_store_coverage_snapshot()`.
- `backend/tests/test_coverage_service.py` — pure-function unit tests (the hazard tests live here).
- `backend/tests/test_api_coverage.py` — endpoint tests (mocked `get_db`, ready + pending).
- `backend/tests/test_coverage_snapshot.py` — worker wiring test (mocked session).

**Backend — modify:**
- `backend/app/main.py` — register the coverage router.
- `backend/worker/scheduler.py` — call the snapshot at the end of `fetch_and_match()` (unconditional, try/except).
- `backend/worker/queue.py` — add a cross-reference comment to `SCOPE` (no behavior change).
- `backend/tests/test_scheduler.py` — assert the snapshot is invoked.

**Frontend — create:**
- `frontend/app/coverage/page.tsx` — the `/coverage` page.
- `frontend/__tests__/pages/Coverage.test.tsx` — jest-axe unit tests.
- `frontend/e2e/coverage.spec.ts` — Playwright + axe E2E.

**Frontend — modify:**
- `frontend/lib/types.ts` — `StateCoverage`, `Coverage`.
- `frontend/lib/api.ts` — `coverage()` client method.
- `frontend/app/page.tsx` — add a `/coverage` nav link in the dashboard header.

**Docs — modify (final task):**
- `CLAUDE.md`, `README.md` — status-table row + design notes (mirror the WS1 docs discipline).

---

## Data shapes

**Snapshot JSON** (stored in `worker_state.value`, key `coverage_snapshot`):
```json
{"states": [{"state": "CO", "fetchable": 4000, "with_sig": 3999}, {"state": "TX", "fetchable": 120, "with_sig": 0}]}
```

**`GET /coverage` response (ready):**
```json
{"status": "ready", "as_of": "2026-06-03T04:12:00Z", "matchable_pct": 78.4,
 "states": [{"state": "CO", "fetchable": 4000, "with_sig": 3999, "status": "complete"}]}
```

**`GET /coverage` response (no snapshot yet):**
```json
{"status": "pending", "as_of": null, "matchable_pct": null, "states": []}
```

---

## Task 1: Pure coverage service

**Files:**
- Create: `backend/app/services/coverage.py`
- Test: `backend/tests/test_coverage_service.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_coverage_service.py
import json
from app.services.coverage import (
    SCOPE,
    aggregate_coverage,
    build_snapshot_payload,
    derive_state_status,
    scoped_matchable_pct,
)


def test_scope_is_co_plus_top5():
    assert set(SCOPE) == {"CO", "CA", "NY", "IL", "TX", "FL"}


def test_aggregate_counts_fetchable_and_with_sig():
    rows = [("CO", True, True), ("CO", True, False), ("CO", True, True)]
    assert aggregate_coverage(rows) == {"CO": {"fetchable": 3, "with_sig": 2}}


def test_aggregate_excludes_null_doc_bill_from_both():
    # Hazard #2: a signature with text_doc_id IS NULL must count toward neither.
    rows = [("CO", False, True)]
    assert aggregate_coverage(rows) == {"CO": {"fetchable": 0, "with_sig": 0}}


def test_aggregate_doc_without_sig_counts_fetchable_only():
    rows = [("CO", True, False)]
    assert aggregate_coverage(rows) == {"CO": {"fetchable": 1, "with_sig": 0}}


def test_aggregate_with_sig_never_exceeds_fetchable():
    rows = [("CO", True, True), ("CO", False, True), ("CO", True, False)]
    agg = aggregate_coverage(rows)["CO"]
    assert agg["with_sig"] <= agg["fetchable"]


def test_aggregate_groups_by_state():
    rows = [("CO", True, True), ("TX", True, False)]
    assert aggregate_coverage(rows) == {
        "CO": {"fetchable": 1, "with_sig": 1},
        "TX": {"fetchable": 1, "with_sig": 0},
    }


def test_derive_status_not_started_when_no_sig():
    assert derive_state_status(120, 0) == "not_started"


def test_derive_status_complete_at_95_percent():
    assert derive_state_status(100, 95) == "complete"


def test_derive_status_in_progress_below_95():
    assert derive_state_status(100, 94) == "in_progress"


def test_scoped_pct_counts_only_scope_states():
    per_state = {
        "CO": {"fetchable": 100, "with_sig": 80},
        "TX": {"fetchable": 100, "with_sig": 20},  # in scope
        "WY": {"fetchable": 100, "with_sig": 100},  # tier-2, excluded
    }
    # (80 + 20) / (100 + 100) = 50.0 ; WY excluded from numerator AND denominator
    assert scoped_matchable_pct(per_state) == 50.0


def test_scoped_pct_none_when_no_inscope_fetchable():
    assert scoped_matchable_pct({"WY": {"fetchable": 100, "with_sig": 100}}) is None
    assert scoped_matchable_pct({}) is None


def test_build_snapshot_payload_is_sorted_json_states():
    rows = [("TX", True, False), ("CO", True, True)]
    payload = json.loads(build_snapshot_payload(rows))
    assert payload == {
        "states": [
            {"state": "CO", "fetchable": 1, "with_sig": 1},
            {"state": "TX", "fetchable": 1, "with_sig": 0},
        ]
    }
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/python -m pytest tests/test_coverage_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.coverage'`

- [ ] **Step 3: Write the implementation**

```python
# backend/app/services/coverage.py
"""Pure coverage-tracker helpers — no DB access, fully unit-testable.

The counting logic lives here (not in SQL) because the test suite has no real
DB engine and the models are Postgres-locked, so the GROUP BY could not be
exercised in CI. The worker feeds aggregate_coverage() one boolean-per-bill row
(state, has_doc, has_sig) produced by an EXISTS query — no join, so duplicate
signature rows cannot fan-out double-count. See the WS3 plan for the full
rationale.

SCOPE must stay in sync with backend/worker/queue.py _STATE_PRIORITY tiers 0+1
(CO + top-5). If the fetch scope changes, change both.
"""
import json
from collections.abc import Iterable

# CO (tier 0) + the five comparison states (tier 1 in queue._STATE_PRIORITY).
SCOPE: tuple[str, ...] = ("CO", "CA", "NY", "IL", "TX", "FL")


def aggregate_coverage(rows: Iterable[tuple[str, bool, bool]]) -> dict[str, dict[str, int]]:
    """Fold (state, has_doc, has_sig) rows into per-state {fetchable, with_sig}.

    with_sig is AND-gated on has_doc so a signature attached to a bill with no
    text_doc_id never inflates the matchable count — this keeps with_sig <=
    fetchable, hence the matchable ratio <= 1.0.
    """
    acc: dict[str, dict[str, int]] = {}
    for state, has_doc, has_sig in rows:
        bucket = acc.setdefault(state, {"fetchable": 0, "with_sig": 0})
        if has_doc:
            bucket["fetchable"] += 1
            if has_sig:
                bucket["with_sig"] += 1
    return acc


def build_snapshot_payload(rows: Iterable[tuple[str, bool, bool]]) -> str:
    """Aggregate rows and serialize to the stored snapshot JSON (states sorted)."""
    agg = aggregate_coverage(rows)
    states = [
        {"state": s, "fetchable": c["fetchable"], "with_sig": c["with_sig"]}
        for s, c in sorted(agg.items())
    ]
    return json.dumps({"states": states})


def derive_state_status(fetchable: int, with_sig: int) -> str:
    """complete (>=95% matchable) / in_progress / not_started (no signatures)."""
    if with_sig == 0:
        return "not_started"
    if fetchable > 0 and with_sig / fetchable >= 0.95:
        return "complete"
    return "in_progress"


def scoped_matchable_pct(per_state: dict[str, dict[str, int]]) -> float | None:
    """Headline metric: in-scope with_sig / in-scope fetchable, as a 0-100 float.

    Returns None when no in-scope bill is fetchable yet (distinct from 0.0).
    """
    numerator = sum(v["with_sig"] for s, v in per_state.items() if s in SCOPE)
    denominator = sum(v["fetchable"] for s, v in per_state.items() if s in SCOPE)
    if denominator == 0:
        return None
    return round(numerator / denominator * 100, 1)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_coverage_service.py -v`
Expected: PASS (12 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/coverage.py backend/tests/test_coverage_service.py
git commit -m "feat(coverage): pure coverage aggregation + derivation helpers"
```

---

## Task 2: Coverage Pydantic schemas

**Files:**
- Create: `backend/app/schemas/coverage.py`
- Test: `backend/tests/test_api_coverage.py` (schema instantiation portion; full endpoint tests added in Task 3)

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_api_coverage.py
# All imports at top to avoid pylint C0413 (wrong-import-position) — CI fails on
# ANY pylint message. The json/AsyncClient/AsyncMock imports are used by the
# endpoint tests appended in Task 3; they're declared here so Task 3 adds only
# functions, never mid-file imports.
import json
from datetime import datetime, timezone
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport
from app.schemas.coverage import StateCoverage, CoverageOut


def test_coverage_schema_round_trips():
    out = CoverageOut(
        status="ready",
        as_of=datetime(2026, 6, 3, 4, 0, tzinfo=timezone.utc),
        matchable_pct=78.4,
        states=[StateCoverage(state="CO", fetchable=4000, with_sig=3999, status="complete")],
    )
    dumped = out.model_dump()
    assert dumped["status"] == "ready"
    assert dumped["matchable_pct"] == 78.4
    assert dumped["states"][0]["status"] == "complete"


def test_coverage_schema_allows_pending_nulls():
    out = CoverageOut(status="pending", as_of=None, matchable_pct=None, states=[])
    assert out.matchable_pct is None
    assert out.states == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_api_coverage.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.schemas.coverage'`

- [ ] **Step 3: Write the implementation**

```python
# backend/app/schemas/coverage.py
from datetime import datetime
from typing import Literal
from pydantic import BaseModel


class StateCoverage(BaseModel):
    state: str
    fetchable: int
    with_sig: int
    status: Literal["complete", "in_progress", "not_started"]


class CoverageOut(BaseModel):
    status: Literal["ready", "pending"]
    as_of: datetime | None
    matchable_pct: float | None
    states: list[StateCoverage]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_api_coverage.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/coverage.py backend/tests/test_api_coverage.py
git commit -m "feat(coverage): CoverageOut / StateCoverage schemas"
```

---

## Task 3: `GET /coverage` endpoint

**Files:**
- Create: `backend/app/routers/coverage.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_api_coverage.py` (append endpoint tests)

- [ ] **Step 1: Write the failing tests (append to test_api_coverage.py)**

```python
# --- append to backend/tests/test_api_coverage.py (imports already at top from Task 2) ---
@pytest_asyncio.fixture
async def client():
    from app.main import app
    from app.dependencies import get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c, app, get_db


async def test_coverage_ready(client):
    c, app, get_db = client
    snapshot = json.dumps({"states": [
        {"state": "CO", "fetchable": 100, "with_sig": 95},
        {"state": "WY", "fetchable": 10, "with_sig": 0},
    ]})
    mock_session = AsyncMock()
    execute_result = MagicMock()
    execute_result.first.return_value = (snapshot, datetime(2026, 6, 3, 4, 0, tzinfo=timezone.utc))
    mock_session.execute.return_value = execute_result

    async def override():
        yield mock_session

    app.dependency_overrides[get_db] = override
    try:
        resp = await c.get("/coverage", headers={"User-Agent": "TestClient/1.0"})
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ready"
    assert data["matchable_pct"] == 95.0  # CO only in scope; WY excluded
    co = next(s for s in data["states"] if s["state"] == "CO")
    assert co["status"] == "complete"
    wy = next(s for s in data["states"] if s["state"] == "WY")
    assert wy["status"] == "not_started"


async def test_coverage_pending_when_no_snapshot(client):
    c, app, get_db = client
    mock_session = AsyncMock()
    execute_result = MagicMock()
    execute_result.first.return_value = None
    mock_session.execute.return_value = execute_result

    async def override():
        yield mock_session

    app.dependency_overrides[get_db] = override
    try:
        resp = await c.get("/coverage", headers={"User-Agent": "TestClient/1.0"})
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "pending"
    assert data["matchable_pct"] is None
    assert data["states"] == []


async def test_coverage_requires_user_agent(client):
    c, app, get_db = client
    resp = await c.get("/coverage", headers={"User-Agent": ""})
    assert resp.status_code == 400
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/python -m pytest tests/test_api_coverage.py -v`
Expected: FAIL — `/coverage` returns 404 (router not registered).

- [ ] **Step 3: Write the endpoint**

```python
# backend/app/routers/coverage.py
import json
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db, require_user_agent
from app.models.worker_state import WorkerState
from app.schemas.coverage import CoverageOut, StateCoverage
from app.services.coverage import derive_state_status, scoped_matchable_pct

router = APIRouter(dependencies=[Depends(require_user_agent)])

COVERAGE_SNAPSHOT_KEY = "coverage_snapshot"


@router.get("/coverage", response_model=CoverageOut)
async def get_coverage(db: AsyncSession = Depends(get_db)):
    row = (
        await db.execute(
            select(WorkerState.value, WorkerState.updated_at).where(
                WorkerState.key == COVERAGE_SNAPSHOT_KEY
            )
        )
    ).first()

    # Cold start: no snapshot computed yet (first nightly run hasn't happened).
    if row is None or row[0] is None:
        return CoverageOut(status="pending", as_of=None, matchable_pct=None, states=[])

    value, updated_at = row
    per_state = {
        s["state"]: {"fetchable": s["fetchable"], "with_sig": s["with_sig"]}
        for s in json.loads(value)["states"]
    }
    states = [
        StateCoverage(
            state=state,
            fetchable=counts["fetchable"],
            with_sig=counts["with_sig"],
            status=derive_state_status(counts["fetchable"], counts["with_sig"]),
        )
        for state, counts in per_state.items()
    ]
    return CoverageOut(
        status="ready",
        as_of=updated_at,
        matchable_pct=scoped_matchable_pct(per_state),
        states=states,
    )
```

- [ ] **Step 4: Register the router**

Modify `backend/app/main.py`:
- Line 8: `from app.routers import bills, matches, tags, stats` → `from app.routers import bills, matches, tags, stats, coverage`
- After line 28 (`app.include_router(stats.router)`): add `app.include_router(coverage.router)`

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_api_coverage.py -v`
Expected: PASS (5 tests total in the file)

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/coverage.py backend/app/main.py backend/tests/test_api_coverage.py
git commit -m "feat(coverage): GET /coverage endpoint (snapshot read + pending state)"
```

---

## Task 4: Worker snapshot computation

**Files:**
- Create: `backend/worker/tasks/coverage.py`
- Modify: `backend/worker/queue.py` (cross-ref comment only)
- Test: `backend/tests/test_coverage_snapshot.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_coverage_snapshot.py
import json
from unittest.mock import AsyncMock, MagicMock, patch


async def test_compute_snapshot_aggregates_and_upserts():
    # One boolean-per-bill row each: a fully-matchable CO bill, a CO bill whose
    # signature has NULL text_doc_id (must NOT inflate counts), a fetchable-only TX bill.
    rows = [("CO", True, True), ("CO", False, True), ("TX", True, False)]

    mock_session = AsyncMock()
    read_result = MagicMock()
    read_result.all.return_value = rows
    # First execute() = read query, second = upsert.
    mock_session.execute.side_effect = [read_result, AsyncMock()]
    mock_session.commit = AsyncMock()

    fake_ctx = MagicMock()
    fake_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    fake_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("worker.tasks.coverage.async_session", return_value=fake_ctx):
        from worker.tasks.coverage import compute_and_store_coverage_snapshot
        await compute_and_store_coverage_snapshot()

    # Read + upsert both issued, and committed.
    assert mock_session.execute.await_count == 2
    mock_session.commit.assert_awaited()

    # Inspect the upsert statement's bound params (key + aggregated JSON value).
    upsert_stmt = mock_session.execute.await_args_list[1].args[0]
    from sqlalchemy.dialects import postgresql
    params = upsert_stmt.compile(dialect=postgresql.dialect()).params
    assert params["key"] == "coverage_snapshot"
    payload = json.loads(params["value"])
    assert payload == {"states": [
        {"state": "CO", "fetchable": 1, "with_sig": 1},
        {"state": "TX", "fetchable": 1, "with_sig": 0},
    ]}
```

> **Fallback if the bind-param assertion is fragile (advisor):** Postgres `on_conflict_do_update` bind-naming is version-sensitive. If `upsert_stmt.compile(dialect=postgresql.dialect()).params["value"]` raises `KeyError` or returns the wrong bind at Step 5, decouple the wiring test from compiler internals with a sentinel: wrap the call in `with patch("worker.tasks.coverage.build_snapshot_payload", return_value="SENTINEL"):`, then assert `params["value"] == "SENTINEL"`. The Task 1 `build_snapshot_payload`/`aggregate_coverage` tests remain the real proof of aggregation correctness; this test only proves the worker wires read → payload → upsert.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_coverage_snapshot.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'worker.tasks.coverage'`

- [ ] **Step 3: Write the worker task**

```python
# backend/worker/tasks/coverage.py
import logging
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.database import async_session
from app.models.bill import Bill
from app.models.minhash_signature import MinHashSignature
from app.models.worker_state import WorkerState
from app.services.coverage import build_snapshot_payload

logger = logging.getLogger(__name__)

COVERAGE_SNAPSHOT_KEY = "coverage_snapshot"


async def compute_and_store_coverage_snapshot() -> None:
    """Nightly coverage snapshot: one boolean-per-bill read, aggregate in Python,
    upsert the JSON into worker_state.

    The read emits (state, text_doc_id IS NOT NULL, EXISTS(signature)) per bill —
    EXISTS, never a join, so duplicate signature rows cannot fan-out double-count
    fetchable. Aggregation lives in app.services.coverage (pure, unit-tested).
    """
    sig_exists = (
        select(MinHashSignature.id)
        .where(MinHashSignature.bill_id == Bill.id)
        .exists()
    )
    stmt = select(
        Bill.state,
        Bill.text_doc_id.isnot(None),
        sig_exists,
    )

    async with async_session() as session:
        rows = (await session.execute(stmt)).all()
        payload = build_snapshot_payload(rows)
        await session.execute(
            pg_insert(WorkerState)
            .values(key=COVERAGE_SNAPSHOT_KEY, value=payload)
            .on_conflict_do_update(
                index_elements=["key"],
                # updated_at MUST be set explicitly — onupdate=func.now() does NOT
                # fire on the on_conflict_do_update path (see scheduler._mark_bootstrap_ran).
                set_={"value": payload, "updated_at": func.now()},
            )
        )
        await session.commit()
    logger.info("coverage: snapshot stored (%d states)", payload.count('"state"'))
```

- [ ] **Step 4: Add the cross-reference comment to queue.py**

Modify `backend/worker/queue.py`: above the `_STATE_PRIORITY` definition, add:
```python
# NOTE: tiers 0 (CO) + 1 (top-5) must stay in sync with app.services.coverage.SCOPE,
# which is the coverage tracker's matchable-% denominator. Change both together.
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_coverage_snapshot.py -v`
Expected: PASS (1 test)

- [ ] **Step 6: Commit**

```bash
git add backend/worker/tasks/coverage.py backend/worker/queue.py backend/tests/test_coverage_snapshot.py
git commit -m "feat(coverage): nightly worker snapshot (EXISTS read, Python aggregate, upsert)"
```

---

## Task 5: Hook snapshot into the nightly cron

**Files:**
- Modify: `backend/worker/scheduler.py`
- Test: `backend/tests/test_scheduler.py`

- [ ] **Step 1: Read the existing scheduler test for `fetch_and_match`**

Run: `cd backend && grep -n "fetch_and_match\|coverage\|compute_and_store" tests/test_scheduler.py`
Use the existing `fetch_and_match` test's mocking style (patch `worker.scheduler.fetch_bill_texts` / `worker.scheduler.match_co_bills`) as the template for the new patch.

- [ ] **Step 2: Write the failing test (append to test_scheduler.py)**

```python
# --- append to backend/tests/test_scheduler.py ---
from unittest.mock import AsyncMock, patch


async def test_fetch_and_match_computes_coverage_snapshot():
    with patch("worker.scheduler.fetch_bill_texts", new=AsyncMock(return_value=0)), \
         patch("worker.scheduler.match_co_bills", new=AsyncMock()), \
         patch("worker.scheduler.compute_and_store_coverage_snapshot", new=AsyncMock()) as snap:
        from worker.scheduler import fetch_and_match
        await fetch_and_match()
    # Snapshot runs even when 0 bills were fetched (coverage refreshes nightly).
    snap.assert_awaited_once()


async def test_fetch_and_match_survives_snapshot_failure():
    with patch("worker.scheduler.fetch_bill_texts", new=AsyncMock(return_value=5)), \
         patch("worker.scheduler.match_co_bills", new=AsyncMock()), \
         patch("worker.scheduler.compute_and_store_coverage_snapshot",
               new=AsyncMock(side_effect=RuntimeError("boom"))):
        from worker.scheduler import fetch_and_match
        await fetch_and_match()  # must not raise
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd backend && .venv/bin/python -m pytest tests/test_scheduler.py -k coverage -v`
Expected: FAIL — `AttributeError` on `worker.scheduler.compute_and_store_coverage_snapshot` (not imported).

- [ ] **Step 4: Wire the snapshot into `fetch_and_match`**

Modify `backend/worker/scheduler.py`:
- After line 19 (`from worker.tasks.match import match_co_bills`): add
  `from worker.tasks.coverage import compute_and_store_coverage_snapshot`
- In `fetch_and_match()`, replace the body after the `if count > 0:` block. Current lines 45-49:
```python
    count = await fetch_bill_texts(batch_size=1000, priority_state="CO")
    logger.info("fetch_and_match: fetched %d CO bills", count)
    if count > 0:
        await match_co_bills()
    logger.info("fetch_and_match: done")
```
becomes:
```python
    count = await fetch_bill_texts(batch_size=1000, priority_state="CO")
    logger.info("fetch_and_match: fetched %d CO bills", count)
    if count > 0:
        await match_co_bills()
    # Refresh the coverage snapshot every night regardless of fetch count, and
    # never let a snapshot failure break the cron.
    try:
        await compute_and_store_coverage_snapshot()
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception("Coverage snapshot failed")
    logger.info("fetch_and_match: done")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_scheduler.py -v`
Expected: PASS (all scheduler tests, including the 2 new ones)

- [ ] **Step 6: Commit**

```bash
git add backend/worker/scheduler.py backend/tests/test_scheduler.py
git commit -m "feat(coverage): compute snapshot at end of nightly fetch_and_match"
```

---

## Task 6: Frontend types + API client

**Files:**
- Modify: `frontend/lib/types.ts`
- Modify: `frontend/lib/api.ts`

- [ ] **Step 1: Add types**

Append to `frontend/lib/types.ts`:
```typescript
export interface StateCoverage {
  state: string;
  fetchable: number;
  with_sig: number;
  status: "complete" | "in_progress" | "not_started";
}

export interface Coverage {
  status: "ready" | "pending";
  as_of: string | null;
  matchable_pct: number | null;
  states: StateCoverage[];
}
```

- [ ] **Step 2: Add the API client method**

Modify `frontend/lib/api.ts`:
- Line 1: add `Coverage` to the import:
  `import type { BillListItem, BillDetail, Match, Stats, TagCount, Coverage } from "./types";`
- Inside the `api` object, after the `sessions:` line, add:
  `  coverage: (): Promise<Coverage> => get<Coverage>("/coverage"),`

- [ ] **Step 3: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/lib/types.ts frontend/lib/api.ts
git commit -m "feat(coverage): frontend Coverage types + api.coverage() client"
```

---

## Task 7: `/coverage` page

**Files:**
- Create: `frontend/app/coverage/page.tsx`
- Test: `frontend/__tests__/pages/Coverage.test.tsx`

- [ ] **Step 1: Write the failing jest-axe tests**

```tsx
// frontend/__tests__/pages/Coverage.test.tsx
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { axe } from "jest-axe";
import Coverage from "@/app/coverage/page";

jest.mock("@/lib/api", () => ({ api: { coverage: jest.fn() } }));
import { api } from "@/lib/api";

function withQueryClient(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{ui}</QueryClientProvider>;
}

const READY = {
  status: "ready",
  as_of: "2026-06-03T04:00:00Z",
  matchable_pct: 78.4,
  states: [
    { state: "CO", fetchable: 100, with_sig: 95, status: "complete" },
    { state: "TX", fetchable: 50, with_sig: 10, status: "in_progress" },
    { state: "WY", fetchable: 10, with_sig: 0, status: "not_started" },
  ],
};

beforeEach(() => (api.coverage as jest.Mock).mockReset());

test("Coverage page has no axe violations when data loads", async () => {
  (api.coverage as jest.Mock).mockResolvedValue(READY);
  const { container } = render(withQueryClient(<Coverage />));
  await waitFor(() => screen.getByText(/78.4%/));
  expect(await axe(container)).toHaveNoViolations();
});

test("Coverage page renders an accessible table row per state", async () => {
  (api.coverage as jest.Mock).mockResolvedValue(READY);
  render(withQueryClient(<Coverage />));
  await waitFor(() => screen.getByRole("table"));
  expect(screen.getByRole("row", { name: /CO/i })).toBeInTheDocument();
  expect(screen.getByText(/complete/i)).toBeInTheDocument();
  expect(screen.getByText(/not started/i)).toBeInTheDocument();
});

test("Coverage page shows pending state when snapshot not computed", async () => {
  (api.coverage as jest.Mock).mockResolvedValue({
    status: "pending", as_of: null, matchable_pct: null, states: [],
  });
  render(withQueryClient(<Coverage />));
  await waitFor(() => expect(screen.getByText(/computing/i)).toBeInTheDocument());
});

test("Coverage page handles null matchable_pct without printing 'null'", async () => {
  (api.coverage as jest.Mock).mockResolvedValue({
    status: "ready", as_of: "2026-06-03T04:00:00Z", matchable_pct: null,
    states: [{ state: "WY", fetchable: 0, with_sig: 0, status: "not_started" }],
  });
  render(withQueryClient(<Coverage />));
  await waitFor(() => screen.getByRole("table"));
  expect(screen.queryByText(/null/i)).not.toBeInTheDocument();
});

test("Coverage page shows loading state initially", () => {
  (api.coverage as jest.Mock).mockReturnValue(new Promise(() => {}));
  render(withQueryClient(<Coverage />));
  expect(screen.getByRole("status")).toHaveTextContent(/loading/i);
});

test("Coverage page shows error state on fetch failure", async () => {
  (api.coverage as jest.Mock).mockRejectedValue(new Error("boom"));
  render(withQueryClient(<Coverage />));
  await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx jest Coverage.test --no-coverage`
Expected: FAIL — cannot resolve `@/app/coverage/page`.

- [ ] **Step 3: Write the page**

```tsx
// frontend/app/coverage/page.tsx
"use client";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";
import type { StateCoverage } from "@/lib/types";

const STATUS_LABEL: Record<StateCoverage["status"], string> = {
  complete: "Complete",
  in_progress: "In progress",
  not_started: "Not started",
};

const STATUS_DOT: Record<StateCoverage["status"], string> = {
  complete: "bg-emerald-400",
  in_progress: "bg-amber-400",
  not_started: "bg-slate-600",
};

function pct(s: StateCoverage): string {
  if (s.fetchable === 0) return "—";
  return `${Math.round((s.with_sig / s.fetchable) * 100)}%`;
}

export default function Coverage() {
  const { data, isPending, isError } = useQuery({
    queryKey: ["coverage"],
    queryFn: api.coverage,
  });

  return (
    <main id="main" className="mx-auto max-w-3xl px-4 py-12 space-y-8 text-slate-200">
      <header>
        <h1 className="text-4xl font-black tracking-tight text-white">Corpus Coverage</h1>
        <p className="mt-3 text-slate-400">
          LegiLens cross-state copycat detection only works where bill text has been
          ingested and fingerprinted. This page tracks progress toward the current
          ingest target — Colorado plus five comparison states (CA, NY, IL, TX, FL).
          Remaining states are queued for a later phase.
        </p>
        <p className="mt-3">
          <Link href="/" className="text-sm text-blue-300 underline hover:text-blue-200">
            ← Back to dashboard
          </Link>
        </p>
      </header>

      {isPending && (
        <div role="status" aria-live="polite" className="text-slate-400">
          Loading coverage…
        </div>
      )}

      {isError && (
        <div role="alert" className="rounded-md border border-red-500/30 bg-red-900/20 p-3 text-red-300">
          Failed to load coverage data.
        </div>
      )}

      {data?.status === "pending" && (
        <div role="status" className="rounded-md border border-slate-700 bg-slate-900 p-4 text-slate-300">
          Coverage is computing — check back after tonight&apos;s ingest run.
        </div>
      )}

      {data?.status === "ready" && (
        <>
          <section aria-labelledby="matchable-heading" className="rounded-lg border border-slate-700 bg-slate-800 p-6">
            <h2 id="matchable-heading" className="text-sm font-semibold uppercase tracking-wide text-slate-400">
              Target corpus matchable
            </h2>
            <p className="mt-1 text-5xl font-black text-white">
              {data.matchable_pct === null ? "—" : `${data.matchable_pct}%`}
            </p>
            <p className="mt-1 text-sm text-slate-400">
              of fetchable bills in Colorado + 5 comparison states have a text fingerprint.
              {data.matchable_pct === null && " No in-scope bills are ingested yet."}
            </p>
            <div
              aria-hidden="true"
              className="mt-4 h-2 w-full overflow-hidden rounded-full bg-slate-700"
            >
              <div
                className="h-full bg-emerald-400"
                style={{ width: `${data.matchable_pct ?? 0}%` }}
              />
            </div>
          </section>

          {/* Accessible table — the source of truth for status. */}
          <section aria-labelledby="states-heading">
            <h2 id="states-heading" className="mb-3 text-lg font-bold text-slate-200">
              Per-state status
            </h2>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <caption className="sr-only">
                  Ingest coverage by state: fetchable bills, matchable percentage, and status.
                </caption>
                <thead>
                  <tr className="border-b border-slate-700 text-slate-400">
                    <th scope="col" className="py-2 pr-4">State</th>
                    <th scope="col" className="py-2 pr-4">Fetchable bills</th>
                    <th scope="col" className="py-2 pr-4">Matchable</th>
                    <th scope="col" className="py-2">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {data.states.map((s) => (
                    <tr key={s.state} className="border-b border-slate-800">
                      <th scope="row" className="py-2 pr-4 font-mono font-semibold text-white">
                        {s.state}
                      </th>
                      <td className="py-2 pr-4 text-slate-300">{s.fetchable.toLocaleString()}</td>
                      <td className="py-2 pr-4 text-slate-300">{pct(s)}</td>
                      <td className="py-2">
                        <span className="inline-flex items-center gap-2">
                          <span aria-hidden="true" className={`h-2.5 w-2.5 rounded-full ${STATUS_DOT[s.status]}`} />
                          {STATUS_LABEL[s.status]}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {data.as_of && (
            <p className="text-xs text-slate-500">
              Snapshot as of {new Date(data.as_of).toLocaleString()}.
            </p>
          )}
        </>
      )}
    </main>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx jest Coverage.test --no-coverage`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/app/coverage/page.tsx frontend/__tests__/pages/Coverage.test.tsx
git commit -m "feat(coverage): /coverage page (accessible table + headline matchable %)"
```

---

## Task 8: Dashboard nav link

**Files:**
- Modify: `frontend/app/page.tsx`
- Test: the existing dashboard page test (find it: `ls frontend/__tests__/pages/`)

- [ ] **Step 1: Find the dashboard page test and add a failing assertion**

Run: `ls frontend/__tests__/pages/ && grep -rln "LegiLens\|DashboardContent\|app/page" frontend/__tests__/`
In the dashboard page test file, add:
```tsx
test("dashboard links to the coverage page", async () => {
  // (reuse the file's existing api mock + render helper; stats/bills/sessions mocked)
  // After render:
  const link = await screen.findByRole("link", { name: /corpus coverage/i });
  expect(link).toHaveAttribute("href", "/coverage");
});
```
If no dashboard page test exists, create `frontend/__tests__/pages/Dashboard.test.tsx` mirroring `Tags.test.tsx` (mock `api.stats`/`api.bills`/`api.sessions`; **also mock `next/navigation`'s `useRouter`/`useSearchParams`** — the dashboard uses them, unlike Tags, so an unmocked render throws; wrap in `withQueryClient` + `Suspense` if needed) with just this assertion.

- [ ] **Step 2: Run to verify it fails**

Run: `cd frontend && npx jest pages --no-coverage`
Expected: FAIL — no "corpus coverage" link.

- [ ] **Step 3: Add the nav link**

Modify `frontend/app/page.tsx` header (after the tagline `<p>` that ends at line 73, before `</header>`):
```tsx
        <p className="mt-3">
          <Link href="/coverage" className="text-sm text-blue-300 underline hover:text-blue-200">
            Corpus coverage →
          </Link>
        </p>
```
(`Link` is already imported at line 5.)

- [ ] **Step 4: Run to verify it passes**

Run: `cd frontend && npx jest pages --no-coverage`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/app/page.tsx frontend/__tests__/pages/
git commit -m "feat(coverage): link to /coverage from the dashboard header"
```

---

## Task 9: Playwright E2E

**Files:**
- Create: `frontend/e2e/coverage.spec.ts`

- [ ] **Step 1: Write the E2E spec** (mirror `frontend/e2e/tags.spec.ts`)

```typescript
// frontend/e2e/coverage.spec.ts
import { test, expect } from "@playwright/test";
import { expectNoAxeViolations } from "./axe-helper";

test("coverage page renders and is axe-clean", async ({ page }) => {
  await page.goto("/coverage");
  await expect(page.getByRole("heading", { level: 1, name: /corpus coverage/i })).toBeVisible();
  await expectNoAxeViolations(page, "/coverage");

  // Either the snapshot is ready (table) or still pending — both are valid states.
  const ready = await page.getByRole("table").isVisible().catch(() => false);
  if (!ready) {
    await expect(page.getByText(/computing/i)).toBeVisible();
  }
});

test("dashboard links to coverage", async ({ page }) => {
  await page.goto("/");
  const link = page.getByRole("link", { name: /corpus coverage/i });
  await expect(link).toBeVisible();
  await link.click();
  await expect(page).toHaveURL(/\/coverage/);
});
```

- [ ] **Step 2: Run the E2E suite**

Run: `cd frontend && npm run build && npm run e2e -- coverage.spec.ts`
Expected: PASS (2 tests). (Playwright `webServer` runs `build && start` locally.)

- [ ] **Step 3: Commit**

```bash
git add frontend/e2e/coverage.spec.ts
git commit -m "test(coverage): Playwright + axe E2E for /coverage"
```

---

## Task 10: Full verification + real-runtime probe

**Files:** none (verification only)

- [ ] **Step 1: Backend — full suite + CI-exact pylint**

```bash
cd backend && .venv/bin/python -m pytest -q
cd /Users/eliotswank/dev/legilens && backend/.venv/bin/python -m pylint $(git ls-files '*.py')
```
Expected: all tests pass; pylint 10.00/10, exit 0. (Run pylint from the **repo root** so the root `.pylintrc` is discovered — CI does this.)

- [ ] **Step 2: Frontend — lint + unit + typecheck**

```bash
cd frontend && npm run lint && npx tsc --noEmit && npx jest --no-coverage
```
Expected: clean.

- [ ] **Step 3: Real-runtime Neon probe (read-only — the dialect/integration backstop)**

The pure tests verify the AND-gate logic; the EXISTS read query (the part that cannot run on the mock-only suite) is verified here against the real Postgres. Write `/tmp/coverage_probe.py`:
```python
import asyncio
from sqlalchemy import select
from app.database import async_session
from app.models.bill import Bill
from app.models.minhash_signature import MinHashSignature
from app.services.coverage import aggregate_coverage, scoped_matchable_pct

async def main():
    sig_exists = select(MinHashSignature.id).where(MinHashSignature.bill_id == Bill.id).exists()
    stmt = select(Bill.state, Bill.text_doc_id.isnot(None), sig_exists)
    async with async_session() as s:
        rows = (await s.execute(stmt)).all()
    agg = aggregate_coverage(rows)
    for st in sorted(agg):
        c = agg[st]
        assert c["with_sig"] <= c["fetchable"], (st, c)  # ratio <= 1, hazard guard
        print(f"{st}: fetchable={c['fetchable']} with_sig={c['with_sig']}")
    print("scoped_matchable_pct =", scoped_matchable_pct(agg))

asyncio.run(main())
```
Run (injects prod env locally, read-only):
```bash
cd backend && railway run --service worker .venv/bin/python /tmp/coverage_probe.py
```
Expected: per-state counts print; the `with_sig <= fetchable` assertion holds on real data; the query compiles on Postgres. **This is read-only — no writes.**

- [ ] **Step 4: Commit (if any lint touch-ups were needed)**

```bash
git add -A && git commit -m "chore(coverage): lint/test fixups" || echo "nothing to commit"
```

---

## Task 11: Docs sync + PR

**Files:**
- Modify: `CLAUDE.md`, `README.md`

- [ ] **Step 1: Update `CLAUDE.md`**
  - Add a status-table row (section 5): `| Coverage Tracker (WS3) | Nightly worker snapshot ... \`GET /coverage\` ... \`/coverage\` page ... | ✅ Merged to main (PR #NN) |`
  - Add backend key files: `backend/worker/tasks/coverage.py`, `backend/app/routers/coverage.py`, `backend/app/services/coverage.py`, `backend/app/schemas/coverage.py`.
  - Add a design-decision bullet: snapshot is computed in Python (not SQL GROUP BY) because the test suite is mock-only and models are PG-locked; the read uses EXISTS (no join) so dup sig rows can't fan-out; `with_sig` is AND-gated on `text_doc_id`; `as_of` is `worker_state.updated_at` set explicitly in the upsert; `SCOPE` mirrors `queue._STATE_PRIORITY`.
  - Add frontend key files: `frontend/app/coverage/page.tsx`.

- [ ] **Step 2: Update `README.md`**
  - Add a status-table row for the coverage tracker.
  - Add a short "Coverage Tracker — what shipped" subsection (honest: the matchable % is scoped to CO + 5 states, labeled as such).

- [ ] **Step 3: Commit + push + open PR**

```bash
git add CLAUDE.md README.md
git commit -m "docs(coverage): document WS3 coverage tracker"
git push -u origin feat/coverage-tracker
gh pr create --title "feat: corpus coverage tracker (/coverage) (WS3)" --body "<see template below>"
```
PR body must cover: what shipped, the C-path/EXISTS/AND-gate rationale, the SCOPE-sync note, the Neon-probe result, test counts. End with the "Generated with Claude Code" line.

- [ ] **Step 4: Watch CI to green, then squash-merge**

```bash
gh pr checks --watch
# after green:
gh pr merge --squash --delete-branch
```

---

## Optional post-merge (not a code task)

- **Seed the snapshot once** so `/coverage` isn't `pending` until the first 04:00 cron. This is a **write** to `worker_state` — requires explicit user approval before running (prod write). If approved:
  `cd backend && railway run --service worker .venv/bin/python -c "import asyncio; from worker.tasks.coverage import compute_and_store_coverage_snapshot as f; asyncio.run(f())"`
- **Set the Neon spend cap** in the console before WS2 un-gates non-CO fetching (user action, per spec §8).

---

## Execution notes — task routing & model

Per `/route-tasks` (pedalpoint) classification, when executing:
- **Structural → `local_llm` draft + Agent review** (spec-driven, framework-known, pattern exists): Task 1 (pure helpers), Task 2 (Pydantic schema), Task 6 (TS types + client method).
- **Judgment → Agent / main session** (cross-system, correctness-critical SQL, a11y nuance): Task 3 (endpoint), Task 4 (EXISTS read + upsert — the hazard-sensitive one), Task 5 (cron wiring), Task 7 (accessible page), Task 8, Task 9, Task 10 (verification), Task 11 (docs).

**Model:** planning is done on **Opus** (judgment). For execution:
- **Subagent-driven** mode → the main session keeps orchestrating + reviewing → **stay on Opus**.
- **Inline** mode → for the mechanical/structural tasks (1, 2, 6) → **switch to Sonnet**; switch **back to Opus** for the judgment tasks (3, 4, 5, 7) and all review/verification.

---

## Self-Review

**Spec coverage (§5):** matchable %-denominator pinned to CO+top5 ✓ (Task 1 `scoped_matchable_pct` + `SCOPE`); three status dots with thresholds ✓ (Task 1 `derive_state_status`); snapshot-not-live in `worker_state` ✓ (Task 4); `GET /coverage` reads snapshot + derives + pending cold-start ✓ (Task 3); accessible table as source of truth, with an inline decorative status dot per row — **no separate geographic map/grid in the MVP** (conscious scope choice; spec §5 offered "a simple state grid" as an *option*, and table-with-inline-dots is simpler and more accessible) ✓ (Task 7); `lib/api.ts`/`lib/types.ts` ✓ (Task 6); nav link ✓ (Task 8); tests at every layer ✓; legend naming the scope ✓ (Task 7 header copy).

**Advisor's three query points baked in:** no fan-out (EXISTS, Task 4) ✓; `with_sig ⊆ fetchable` AND-gate (Task 1 `aggregate_coverage`, tested in `test_aggregate_excludes_null_doc_bill_from_both` + `test_aggregate_with_sig_never_exceeds_fetchable`) ✓; explicit `updated_at` in upsert `set_=` (Task 4) ✓. `matchable_pct` nullable + page handles null distinct from pending (Task 7 `test_coverage_page_handles_null_matchable_pct`) ✓. SCOPE-sync cross-ref comment (Task 4 + queue.py) ✓. Neon probe backstop (Task 10) ✓.

**Type consistency:** `StateCoverage`/`CoverageOut` fields identical across `schemas/coverage.py` (Task 2), `routers/coverage.py` (Task 3), `lib/types.ts` (Task 6), and the page (Task 7). `COVERAGE_SNAPSHOT_KEY = "coverage_snapshot"` defined in both `routers/coverage.py` and `worker/tasks/coverage.py` (same literal — acceptable, or import one from the other in a cleanup). `aggregate_coverage` row shape `(state, has_doc, has_sig)` is identical between the worker read (Task 4) and the pure tests (Task 1).

**Placeholder scan:** none — every step carries real code or an exact command.
