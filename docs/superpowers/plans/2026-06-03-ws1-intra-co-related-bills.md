# WS1 — Intra-CO Related Bills Implementation Plan

> **For agentic workers:** This plan is executed via the **`route-tasks`** (pedalpoint) skill per the
> project git workflow (NOT subagent-driven-development). Each task notes a **Route** classification
> (judgment / structural / mechanical) so the router sends mechanical/structural codegen to `local_llm`
> and judgment tasks to an Agent. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface ≥70% text reuse between *distinct* Colorado bills (companions + reintroductions) as a
"Related Colorado Bills" feature, kept rigorously separate from cross-state `copycat_alert`.

**Architecture:** Add a *second* CO-internal match pass inside `match_co_bills()` (after the existing
cross-state pass) that builds an LSH index from CO bills and writes `match_type='co_internal'`
`SimilarityMatch` rows **only** — it never creates or modifies `ISTScore`, so `copycat_alert` stays
cross-state-only and the homepage "Copycat Alerts: 0" stays truthful. The API exposes `match_type` +
the matched bill's id/number on `MatchOut`; the frontend groups matches by type and renders a separate,
honestly-worded panel + landing-page stat.

**Tech stack:** Python 3 / SQLAlchemy 2 async / FastAPI / Pydantic v2 / datasketch MinHash+LSH /
pytest-asyncio (backend); Next.js 16 / React / TanStack Query / Tailwind / jest-axe / Playwright (frontend).

**Zero Alembic migrations.** Every column this plan reads already exists: `similarity_matches.match_type`
(`String(16)`, server_default `cross_state`) and `similarity_matches.matched_bill_id` (NOT NULL). The new
API/UI fields `matched_bill_number`, `has_related`, `related_co_bills` are all **join-derived or computed at
read time** — nothing is stored. Do NOT add a migration or a `test_migration_*` for this work.

**Honesty guard (load-bearing, non-negotiable):** the CO-internal pass writes `SimilarityMatch` rows only.
It must NEVER `session.add(ISTScore(...))`. Task 1's test `test_co_internal_pass_does_not_write_ist_score`
is the guard; if it ever fails, the feature is wrong, not the test.

**Branch:** `feat/intra-co-related-bills` off `main`. Conventional Commits. One PR for the whole plan.

---

## File Structure

**Backend (modify):**
- `backend/worker/tasks/match.py` — add `_normalize_bill_number()`, `_find_co_internal_matches()`; rewrite the CO-loop tail of `match_co_bills()` into two passes (Task 1).
- `backend/app/schemas/match.py` — add `match_type`, `matched_bill_id`, `matched_bill_number` to `MatchOut` (Task 2).
- `backend/app/routers/matches.py` — outerjoin `Bill` for matched number; populate new fields (Task 2).
- `backend/app/schemas/stats.py` — add `related_co_bills` to `StatsOut` (Task 3).
- `backend/app/routers/stats.py` — count distinct CO bills with a `co_internal` match (Task 3).
- `backend/app/schemas/bill.py` — add `has_related` to `BillListItem` (Task 4, CUTTABLE).
- `backend/app/routers/bills.py` — `EXISTS` subquery for `has_related` in list + search (Task 4, CUTTABLE).

**Backend (tests):**
- `backend/tests/test_match.py` — new CO-internal pass tests (Task 1).
- `backend/tests/test_api_matches.py` — update mocks to rows-shape; assert new fields (Task 2).
- `backend/tests/test_api_stats.py` — assert `related_co_bills` (Task 3).
- `backend/tests/test_api_bills.py` — update mock tuples to include `has_related` (Task 4, CUTTABLE).

**Frontend (create):**
- `frontend/components/RelatedBillCard.tsx` — one related-bill row (Task 6).
- `frontend/__tests__/components/RelatedBillCard.test.tsx` — jest-axe (Task 6).

**Frontend (modify):**
- `frontend/lib/types.ts` — `match_type`+`matched_bill_id`+`matched_bill_number` on `Match`; `related_co_bills` on `Stats`; `has_related` on `BillListItem` (Task 5).
- existing fixtures (`e2e/bill-detail.spec.ts`, `e2e/dashboard.spec.ts`, `__tests__/pages/BillDetail.test.tsx`) — add new required fields (Task 5).
- `frontend/app/bills/[id]/page.tsx` — split by `match_type`; render Related panel (Task 6).
- `frontend/app/page.tsx` — 4th stat card; Related badge (Tasks 7, 8).
- `frontend/app/about/page.tsx` — distinguishing sentence (Task 9).

---

## Task 1: Worker — CO-internal related-bills match pass

**Route:** **Judgment → Agent. Execute AND review on Opus.** This is the single load-bearing task
(honesty guard + idempotency + dual-index correctness). Do NOT route to `local_llm`.

**Files:**
- Modify: `backend/worker/tasks/match.py`
- Test: `backend/tests/test_match.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_match.py`:

```python
async def test_normalize_bill_number_strips_and_uppercases():
    from worker.tasks.match import _normalize_bill_number
    assert _normalize_bill_number("hb 1234") == "HB1234"
    assert _normalize_bill_number(" SB24-005 ") == "SB24-005"
    assert _normalize_bill_number("Hb1234") == "HB1234"


async def test_co_internal_writes_match_for_distinct_numbers():
    from worker.tasks.match import _find_co_internal_matches, CorpusIndex
    from app.models.similarity_match import SimilarityMatch

    text = "The commission shall establish fees not to exceed one hundred dollars per application submitted to the board."
    a, b = uuid4(), uuid4()

    co_index = CorpusIndex()
    co_index.add(a, "CO", "HB-1", compute_minhash(text))
    co_index.add(b, "CO", "SB-2", compute_minhash(text))
    co_meta = {a: ("HB-1", "Bill A"), b: ("SB-2", "Bill B")}

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    await _find_co_internal_matches(mock_session, a, compute_minhash(text), co_index, co_meta)

    added = [call.args[0] for call in mock_session.add.call_args_list]
    matches = [x for x in added if isinstance(x, SimilarityMatch)]
    assert len(matches) == 1
    assert matches[0].match_type == "co_internal"
    assert matches[0].matched_bill_id == b
    assert matches[0].matched_state == "CO"
    assert matches[0].matched_bill_title == "Bill B"
    assert matches[0].snippet_status == "pending"


async def test_co_internal_pass_does_not_write_ist_score():
    """HONESTY GUARD: the CO-internal pass must never create an ISTScore, so
    copycat_alert stays cross-state-only. If this fails, the feature is wrong."""
    from worker.tasks.match import _find_co_internal_matches, CorpusIndex
    from app.models.ist_score import ISTScore

    text = "The commission shall establish fees not to exceed one hundred dollars per application submitted to the board."
    a, b = uuid4(), uuid4()

    co_index = CorpusIndex()
    co_index.add(a, "CO", "HB-1", compute_minhash(text))
    co_index.add(b, "CO", "SB-2", compute_minhash(text))
    co_meta = {a: ("HB-1", "Bill A"), b: ("SB-2", "Bill B")}

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    await _find_co_internal_matches(mock_session, a, compute_minhash(text), co_index, co_meta)

    added = [call.args[0] for call in mock_session.add.call_args_list]
    assert not any(isinstance(x, ISTScore) for x in added)


async def test_co_internal_self_guard_skips_same_bill():
    from worker.tasks.match import _find_co_internal_matches, CorpusIndex
    from app.models.similarity_match import SimilarityMatch

    text = "The commission shall establish fees not to exceed one hundred dollars per application submitted to the board."
    a = uuid4()

    co_index = CorpusIndex()
    co_index.add(a, "CO", "HB-1", compute_minhash(text))
    co_meta = {a: ("HB-1", "Bill A")}

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    await _find_co_internal_matches(mock_session, a, compute_minhash(text), co_index, co_meta)

    added = [call.args[0] for call in mock_session.add.call_args_list]
    assert not any(isinstance(x, SimilarityMatch) for x in added)


async def test_co_internal_companion_noise_guard_skips_identical_bill_number():
    """Same normalized bill_number = version/session duplicate of one bill, not a
    distinct related bill. Drop it (the 1 noise pair from the de-risk probe)."""
    from worker.tasks.match import _find_co_internal_matches, CorpusIndex
    from app.models.similarity_match import SimilarityMatch

    text = "The commission shall establish fees not to exceed one hundred dollars per application submitted to the board."
    a, b = uuid4(), uuid4()

    co_index = CorpusIndex()
    co_index.add(a, "CO", "HB-1234", compute_minhash(text))
    co_index.add(b, "CO", "hb 1234", compute_minhash(text))  # same number, different formatting
    co_meta = {a: ("HB-1234", "Bill v1"), b: ("hb 1234", "Bill v2")}

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    await _find_co_internal_matches(mock_session, a, compute_minhash(text), co_index, co_meta)

    added = [call.args[0] for call in mock_session.add.call_args_list]
    assert not any(isinstance(x, SimilarityMatch) for x in added)


async def test_co_internal_below_threshold_writes_no_match():
    from worker.tasks.match import _find_co_internal_matches, CorpusIndex
    from app.models.similarity_match import SimilarityMatch

    base = "no person shall operate a vehicle without a valid license issued by the department of motor vehicles"
    far = "quantum entanglement is a physical phenomenon observed at subatomic scales in laboratory settings"
    a, b = uuid4(), uuid4()

    co_index = CorpusIndex()
    co_index.add(a, "CO", "HB-1", compute_minhash(base))
    co_index.add(b, "CO", "SB-2", compute_minhash(far))
    co_meta = {a: ("HB-1", "Bill A"), b: ("SB-2", "Bill B")}

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    await _find_co_internal_matches(mock_session, a, compute_minhash(base), co_index, co_meta)

    added = [call.args[0] for call in mock_session.add.call_args_list]
    assert not any(isinstance(x, SimilarityMatch) for x in added)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && .venv/bin/pytest tests/test_match.py -k co_internal -x -q`
Expected: FAIL — `ImportError: cannot import name '_find_co_internal_matches'` (and `_normalize_bill_number`).

- [ ] **Step 3: Add the two helpers**

Add to `backend/worker/tasks/match.py`, after `_find_matches_for_bill` (end of file):

```python
def _normalize_bill_number(number: str) -> str:
    """Collapse whitespace and upcase so 'hb 1234' and 'HB1234' compare equal.

    Used by the CO-internal pass companion-noise guard: two CO bill rows with the
    same normalized number are version/session duplicates of one bill, not a real
    related pair. (Refinement deferred per spec §8: a rare cross-session
    reintroduction that kept the same number would also be dropped; the de-risk
    probe found only 1 same-number pair total, so MVP drops it. If valuable later,
    tighten to 'same number AND same session'.)
    """
    return "".join(number.split()).upper()


async def _find_co_internal_matches(session, co_bill_id: UUID, co_m, co_index: CorpusIndex, co_meta: dict):
    """Write co_internal SimilarityMatch rows for one CO bill against the CO index.

    HONESTY GUARD: writes SimilarityMatch rows ONLY. Never creates/modifies
    ISTScore — copycat_alert is computed solely from the cross-state corpus in
    _find_matches_for_bill, which never contains CO bills. Each unordered pair
    {A,B} is found twice (A->B and B->A); accepted, each bill's detail page shows
    its own related bills (spec §3).
    """
    self_number = _normalize_bill_number(co_meta[co_bill_id][0])
    for cand_id, cand_state, cand_number, cand_m in co_index.query(co_m):
        if cand_id == co_bill_id:
            continue  # self-guard
        if _normalize_bill_number(cand_number) == self_number:
            continue  # companion-noise guard
        sim = Decimal(str(round(jaccard_estimate(co_m, cand_m) * 100, 2)))
        if sim < Decimal("70.00"):
            continue  # precision gate (LSH candidates are a superset)
        session.add(SimilarityMatch(
            bill_id=co_bill_id,
            matched_bill_id=cand_id,
            matched_state="CO",
            matched_bill_title=co_meta[cand_id][1],
            similarity_score=sim,
            snippet_status="pending",
            match_type="co_internal",
        ))
    await session.commit()
```

- [ ] **Step 4: Run the new tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_match.py -k co_internal -x -q`
Expected: PASS (6 tests incl. normalize).

- [ ] **Step 5: Wire the second pass into `match_co_bills()`**

In `backend/worker/tasks/match.py`, replace the CO-scoring tail of `match_co_bills()` — the block that
currently starts at `t_match_start = time.monotonic()` and ends at the `logger.info("match: scored %d CO
bills against corpus in %.2fs", co_count, ...)` call — with:

```python
        # Materialize CO signatures once; reused by both passes. DISTINCT ON +
        # ORDER BY computed_at DESC defends against duplicate signature rows.
        co_rows = (await session.execute(
            select(MinHashSignature, Bill)
            .join(Bill, Bill.id == MinHashSignature.bill_id)
            .where(Bill.is_corpus_only.is_(False))
            .distinct(MinHashSignature.bill_id)
            .order_by(MinHashSignature.bill_id, MinHashSignature.computed_at.desc())
        )).all()
        # (bill_id, state, bill_number, title, MinHash) — MinHash computed once.
        co_entries = [
            (bill.id, bill.state, bill.bill_number, bill.title, minhash_from_signature(sig.signature))
            for sig, bill in co_rows
        ]

        # Pass 1 — cross-state scoring (writes cross_state SimilarityMatch + ISTScore).
        t_match_start = time.monotonic()
        for bill_id, _state, _number, _title, co_m in co_entries:
            await _find_matches_for_bill(session, bill_id, co_m, corpus)
        logger.info(
            "match: scored %d CO bills against cross-state corpus in %.2fs",
            len(co_entries), time.monotonic() - t_match_start,
        )

        # Pass 2 — CO-internal related bills (writes co_internal SimilarityMatch
        # ONLY; never ISTScore — honesty guard). Second index built from CO bills.
        t_co_start = time.monotonic()
        co_index = CorpusIndex()
        co_meta: dict[UUID, tuple[str, str]] = {}
        for bill_id, state, number, title, co_m in co_entries:
            co_index.add(bill_id, state, number, co_m)
            co_meta[bill_id] = (number, title)
        for bill_id, _state, _number, _title, co_m in co_entries:
            await _find_co_internal_matches(session, bill_id, co_m, co_index, co_meta)
        logger.info(
            "match: co-internal related-bills pass over %d CO bills in %.2fs",
            len(co_entries), time.monotonic() - t_co_start,
        )
```

Note: the entry-delete at the top of `match_co_bills()` already removes ALL `SimilarityMatch` rows
`WHERE bill_id IN (CO bill ids)` — co_internal rows are owned by a CO `bill_id`, so reruns stay idempotent
with no change to the delete.

- [ ] **Step 6: Run the full worker match suite**

Run: `cd backend && .venv/bin/pytest tests/test_match.py -x -q`
Expected: PASS (all existing cross-state tests + 6 new co_internal tests). The existing
`test_match_type_is_co_internal_when_corpus_state_is_co` and cross-state tests are untouched.

- [ ] **Step 7: Commit**

```bash
git add backend/worker/tasks/match.py backend/tests/test_match.py
git commit -m "feat(match): add CO-internal related-bills pass (co_internal, no ISTScore)"
```

---

## Task 2: API — expose `match_type` + matched bill id/number on `MatchOut`

**Route:** **Structural → `local_llm` draft + Agent review (orchestrate on Sonnet).**

**Files:**
- Modify: `backend/app/schemas/match.py`, `backend/app/routers/matches.py`
- Test: `backend/tests/test_api_matches.py`

- [ ] **Step 1: Update the existing matches tests (mocks → rows shape) and add a new assertion**

The router will change from `result.scalars().all()` to `result.all()` over `(SimilarityMatch, bill_number)`
rows, and `MatchOut` gains three required fields. Update **every** match-building test in
`backend/tests/test_api_matches.py`. For each of `test_get_matches_returns_list`,
`test_ghost_match_returns_message`, `test_pending_match_has_null_snippets`:

1. Add to the `mock_match` setup:
```python
    mock_match.match_type = "cross_state"
    mock_match.matched_bill_id = uuid4()
```
2. Replace the result wiring:
```python
    mock_session = AsyncMock()
    execute_result = MagicMock()
    execute_result.all.return_value = [(mock_match, "HB-1234")]
    mock_session.execute.return_value = execute_result
```
(delete the `scalars_result = MagicMock()` / `scalars_result.all...` / `execute_result.scalars...` lines).

For `test_empty_matches_returns_empty_list`, replace the scalars wiring with:
```python
    mock_session = AsyncMock()
    execute_result = MagicMock()
    execute_result.all.return_value = []
    mock_session.execute.return_value = execute_result
```

In `test_get_matches_returns_list`, add assertions:
```python
    assert data[0]["match_type"] == "cross_state"
    assert data[0]["matched_bill_number"] == "HB-1234"
    assert data[0]["matched_bill_id"] is not None
```

Add a new test:
```python
async def test_co_internal_match_type_round_trips(client):
    c, app, get_db = client
    bill_id, match_id, matched_id = uuid4(), uuid4(), uuid4()

    mock_match = MagicMock()
    mock_match.id = match_id
    mock_match.matched_bill_id = matched_id
    mock_match.matched_bill_title = "SB24-005 - Water Rights"
    mock_match.matched_state = "CO"
    mock_match.similarity_score = Decimal("0.93")
    mock_match.snippet_status = "pending"
    mock_match.matched_snippets = None
    mock_match.match_type = "co_internal"

    mock_session = AsyncMock()
    execute_result = MagicMock()
    execute_result.all.return_value = [(mock_match, "SB24-005")]
    mock_session.execute.return_value = execute_result

    async def override():
        yield mock_session

    app.dependency_overrides[get_db] = override
    try:
        resp = await c.get(f"/bills/{bill_id}/matches", headers={"User-Agent": "TestClient/1.0"})
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["match_type"] == "co_internal"
    assert data[0]["matched_state"] == "CO"
    assert data[0]["matched_bill_number"] == "SB24-005"
    assert data[0]["matched_bill_id"] == str(matched_id)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && .venv/bin/pytest tests/test_api_matches.py -x -q`
Expected: FAIL — `MatchOut` has no `match_type`/`matched_bill_id`/`matched_bill_number`; router still uses `.scalars()`.

- [ ] **Step 3: Add the fields to `MatchOut`**

In `backend/app/schemas/match.py`, replace the `MatchOut` class with:

```python
class MatchOut(BaseModel):
    id: UUID
    matched_bill_id: UUID
    matched_bill_number: str | None
    matched_bill_title: str | None
    matched_state: str | None
    similarity_score: Decimal
    snippet_status: SnippetStatus
    matched_snippets: list[SnippetOrGhost] | None
    match_type: Literal["cross_state", "co_internal"]

    model_config = {"from_attributes": True}
```

- [ ] **Step 4: Outerjoin the matched bill and populate the fields**

Replace `backend/app/routers/matches.py` with:

```python
from uuid import UUID
from pydantic import TypeAdapter
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db, require_user_agent
from app.models.bill import Bill
from app.models.similarity_match import SimilarityMatch
from app.schemas.match import MatchOut, SnippetOrGhost, GhostMessage

router = APIRouter(prefix="/bills", dependencies=[Depends(require_user_agent)])

_snippet_list_adapter = TypeAdapter(list[SnippetOrGhost])


@router.get("/{bill_id}/matches", response_model=list[MatchOut])
async def get_matches(bill_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SimilarityMatch, Bill.bill_number)
        .outerjoin(Bill, Bill.id == SimilarityMatch.matched_bill_id)
        .where(SimilarityMatch.bill_id == bill_id)
    )
    rows = result.all()

    out = []
    for m, matched_bill_number in rows:
        if m.snippet_status == "source_verified_text_missing":
            snippets = [GhostMessage(message="Source text unavailable for extraction")]
        elif m.matched_snippets is not None:
            snippets = _snippet_list_adapter.validate_python(m.matched_snippets)
        else:
            snippets = None

        out.append(MatchOut(
            id=m.id,
            matched_bill_id=m.matched_bill_id,
            matched_bill_number=matched_bill_number,
            matched_bill_title=m.matched_bill_title,
            matched_state=m.matched_state,
            similarity_score=m.similarity_score,
            snippet_status=m.snippet_status,
            matched_snippets=snippets,
            match_type=m.match_type,
        ))
    return out
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_api_matches.py -x -q`
Expected: PASS (all updated + new test).

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/match.py backend/app/routers/matches.py backend/tests/test_api_matches.py
git commit -m "feat(api): expose match_type and matched bill id/number on MatchOut"
```

---

## Task 3: API — `related_co_bills` stat

**Route:** **Structural → `local_llm` draft + Agent review (Sonnet).**

**Files:**
- Modify: `backend/app/schemas/stats.py`, `backend/app/routers/stats.py`
- Test: `backend/tests/test_api_stats.py`

- [ ] **Step 1: Update the stats test**

In `backend/tests/test_api_stats.py`, add to `test_stats_returns_counts` (after the existing key asserts):
```python
    assert "related_co_bills" in data
    assert data["related_co_bills"] == 5
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/test_api_stats.py::test_stats_returns_counts -x -q`
Expected: FAIL — `related_co_bills` not in response (and `StatsOut` rejects the kwarg once added in the wrong order).

- [ ] **Step 3: Add `related_co_bills` to `StatsOut`**

In `backend/app/schemas/stats.py`, replace the `StatsOut` class:
```python
class StatsOut(BaseModel):
    total_co_bills: int
    copycat_alerts: int
    bills_analyzed: int
    related_co_bills: int
```

- [ ] **Step 4: Count distinct CO bills with a co_internal match**

Replace `backend/app/routers/stats.py` with:
```python
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db, require_user_agent
from app.models.bill import Bill
from app.models.ist_score import ISTScore
from app.models.similarity_match import SimilarityMatch
from app.schemas.stats import StatsOut

router = APIRouter(dependencies=[Depends(require_user_agent)])


@router.get("/stats", response_model=StatsOut)
async def get_stats(db: AsyncSession = Depends(get_db)):
    total = await db.execute(
        select(func.count()).select_from(Bill).where(Bill.is_corpus_only.is_(False))
    )
    alerts = await db.execute(
        select(func.count()).select_from(ISTScore).where(ISTScore.copycat_alert.is_(True))
    )
    analyzed = await db.execute(select(func.count()).select_from(ISTScore))
    related = await db.execute(
        select(func.count(func.distinct(SimilarityMatch.bill_id)))
        .where(SimilarityMatch.match_type == "co_internal")
    )
    return StatsOut(
        total_co_bills=total.scalar() or 0,
        copycat_alerts=alerts.scalar() or 0,
        bills_analyzed=analyzed.scalar() or 0,
        related_co_bills=related.scalar() or 0,
    )
```

- [ ] **Step 5: Run to verify it passes**

Run: `cd backend && .venv/bin/pytest tests/test_api_stats.py -x -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/stats.py backend/app/routers/stats.py backend/tests/test_api_stats.py
git commit -m "feat(api): add related_co_bills count to /stats"
```

---

## Task 4: API — `has_related` flag on bill list  [CUTTABLE — pairs with Task 8]

**Route:** **Structural → `local_llm` draft + Agent review (Sonnet).**
**If time-boxing WS1, cut this task and Task 8 together** (the dashboard per-row badge). The landing-page
stat card (Tasks 3 + 7) and the bill-detail panel (Task 6) still deliver the feature; the badge is the
only droppable surface. Cut both or neither.

**Files:**
- Modify: `backend/app/schemas/bill.py`, `backend/app/routers/bills.py`
- Test: `backend/tests/test_api_bills.py`

- [ ] **Step 1: Update the existing list/search mocks and add an assertion**

In `backend/tests/test_api_bills.py`, the two propagation tests mock rows as 2-tuples; they become 3-tuples.
In `test_get_bills_propagates_copycat_alert` and `test_search_bills_propagates_copycat_alert`, change:
```python
    execute_result.all.return_value = [(mock_bill, True)]
```
to:
```python
    execute_result.all.return_value = [(mock_bill, True, True)]
```
and add after the existing `copycat_alert` assertion:
```python
    assert resp.json()[0]["has_related"] is True
```
(The `execute_result.all.return_value = []` and `execute_spy` tests are unaffected — empty rows.)

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/test_api_bills.py -x -q`
Expected: FAIL — `BillListItem` has no `has_related`; router still unpacks 2-tuples.

- [ ] **Step 3: Add `has_related` to `BillListItem`**

In `backend/app/schemas/bill.py`, replace `BillListItem`:
```python
class BillListItem(BaseModel):
    id: UUID
    bill_number: str
    title: str
    state: str
    session: str
    status: str | None
    copycat_alert: bool | None
    has_related: bool

    model_config = {"from_attributes": True}
```

- [ ] **Step 4: Add the `EXISTS` subquery to list + search**

In `backend/app/routers/bills.py`: add the import
```python
from app.models.similarity_match import SimilarityMatch
```
Define a reusable correlated EXISTS (place it just below the imports, module level):
```python
def _has_related_expr():
    return (
        select(SimilarityMatch.id)
        .where(
            SimilarityMatch.bill_id == Bill.id,
            SimilarityMatch.match_type == "co_internal",
        )
        .exists()
        .label("has_related")
    )
```
In `list_bills`, change the base select and the row unpack:
```python
    q = (
        select(Bill, ISTScore.copycat_alert, _has_related_expr())
        .outerjoin(ISTScore, ISTScore.bill_id == Bill.id)
        .where(Bill.is_corpus_only.is_(False))
    )
```
```python
    return [
        BillListItem(
            id=b.id,
            bill_number=b.bill_number,
            title=b.title,
            state=b.state,
            session=b.session,
            status=b.status,
            copycat_alert=copycat_alert,
            has_related=has_related,
        )
        for b, copycat_alert, has_related in rows
    ]
```
In `search_bills`, mirror it:
```python
        select(Bill, ISTScore.copycat_alert, _has_related_expr())
        .outerjoin(ISTScore, ISTScore.bill_id == Bill.id)
        .where(Bill.is_corpus_only.is_(False))
        .where(func.similarity(Bill.full_text, q) > 0.1)
        .order_by(func.similarity(Bill.full_text, q).desc())
        .limit(20)
```
```python
    return [
        BillListItem(
            id=b.id,
            bill_number=b.bill_number,
            title=b.title,
            state=b.state,
            session=b.session,
            status=b.status,
            copycat_alert=copycat_alert,
            has_related=has_related,
        )
        for b, copycat_alert, has_related in rows
    ]
```

- [ ] **Step 5: Run to verify it passes**

Run: `cd backend && .venv/bin/pytest tests/test_api_bills.py -x -q`
Expected: PASS. The `test_get_bills_without_tag_type_does_not_join_friction_tags` regression still holds
(EXISTS on `similarity_matches`, not a join on `friction_tags`).

- [ ] **Step 6: Run the whole backend suite (regression gate before frontend)**

Run: `cd backend && .venv/bin/pytest -q`
Expected: PASS (all prior + new). Fix any straggler before moving on.

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/bill.py backend/app/routers/bills.py backend/tests/test_api_bills.py
git commit -m "feat(api): add has_related flag to bill list and search"
```

---

## Task 5: Frontend — type plumbing + fixture updates (keep suite green)

**Route:** **Mechanical → `local_llm` (Sonnet).**
**FIRST:** per `frontend/AGENTS.md`, this is a non-standard Next.js 16 — read the relevant guide in
`node_modules/next/dist/docs/` before writing any frontend code in Tasks 5–9.

**Files:**
- Modify: `frontend/lib/types.ts`
- Modify (fixtures): `frontend/e2e/bill-detail.spec.ts`, `frontend/e2e/dashboard.spec.ts`, `frontend/__tests__/pages/BillDetail.test.tsx`

- [ ] **Step 1: Add the new fields to the interfaces**

In `frontend/lib/types.ts`:
- In `Match`, add (after `id`):
```typescript
  matched_bill_id: string;
  matched_bill_number: string | null;
```
  and (after `matched_snippets`):
```typescript
  match_type: "cross_state" | "co_internal";
```
- In `Stats`, add:
```typescript
  related_co_bills: number;
```
- In `BillListItem`, add:
```typescript
  has_related: boolean;
```
(If Task 4/8 are cut, still add `has_related` here — harmless and keeps the type honest with the API.)

- [ ] **Step 2: Update existing fixtures so the compiler is green**

In `frontend/__tests__/pages/BillDetail.test.tsx`, add to each of `matchFixture`, `ghostMatchFixture`,
`pendingMatchFixture`:
```typescript
  matched_bill_id: "00000000-0000-0000-0000-0000000000aa",
  matched_bill_number: "TX-1",
  match_type: "cross_state",
```
In `frontend/e2e/bill-detail.spec.ts`, add the same three fields to each object in `matchesFixture`,
`matchesWithContextFixture`, and `ghostMatchesFixture` (all are cross-state; vary the id/number freely).

In `frontend/e2e/dashboard.spec.ts`, update `statsFixture` to include the new field (REQUIRED — the new
stat card calls `value.toLocaleString()` and would throw on `undefined`):
```typescript
const statsFixture = { total_co_bills: 342, copycat_alerts: 17, bills_analyzed: 289, related_co_bills: 125 };
```
Add `has_related: false` to each object in `billsFixture` and `searchResultsFixture`.

- [ ] **Step 3: Typecheck + run the frontend suite (the compiler is the oracle for stragglers)**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors. If the compiler flags any other *typed* fixture missing a new field, add it there too.
Also `grep -n "total_co_bills\|bills_analyzed" frontend/__tests__/lib/api.test.ts` — `tsc` does NOT catch
*untyped* object literals, so manually add `related_co_bills` to any `Stats`-shaped fixture it finds.
Run: `cd frontend && npm test`
Expected: PASS (unchanged behavior — this task only adds optional-to-render fields). A runtime failure here
is the safety net for any untyped fixture `tsc` missed.

- [ ] **Step 4: Commit**

```bash
git add frontend/lib/types.ts frontend/e2e frontend/__tests__
git commit -m "feat(web): add match_type/matched bill id+number, related_co_bills, has_related to types"
```

---

## Task 6: Frontend — "Related Colorado Bills" panel on bill detail

**Route:** **Structural → `local_llm` draft + Agent review (Sonnet).** The empty-state split (below) is a
correctness point — keep the Agent review.

**Files:**
- Create: `frontend/components/RelatedBillCard.tsx`, `frontend/__tests__/components/RelatedBillCard.test.tsx`
- Modify: `frontend/app/bills/[id]/page.tsx`, `frontend/__tests__/pages/BillDetail.test.tsx`

- [ ] **Step 1: Write the failing component + page tests**

Create `frontend/__tests__/components/RelatedBillCard.test.tsx`:
```tsx
import { render } from "@testing-library/react";
import { axe } from "jest-axe";
import RelatedBillCard from "@/components/RelatedBillCard";
import type { Match } from "@/lib/types";

const related: Match = {
  id: "m1",
  matched_bill_id: "00000000-0000-0000-0000-0000000000bb",
  matched_bill_number: "SB24-005",
  matched_bill_title: "Concerning Water Rights",
  matched_state: "CO",
  similarity_score: 93.2,
  snippet_status: "pending",
  matched_snippets: null,
  match_type: "co_internal",
};

test("RelatedBillCard links to the related bill and shows number + score", () => {
  const { getByRole, getByText } = render(<RelatedBillCard match={related} />);
  expect(getByRole("link")).toHaveAttribute("href", "/bills/00000000-0000-0000-0000-0000000000bb");
  expect(getByText("SB24-005")).toBeInTheDocument();
  expect(getByText(/93/)).toBeInTheDocument();
});

test("RelatedBillCard has no accessibility violations", async () => {
  const { container } = render(<RelatedBillCard match={related} />);
  expect(await axe(container)).toHaveNoViolations();
});
```

In `frontend/__tests__/pages/BillDetail.test.tsx`, add a co_internal fixture and two tests:
```tsx
const relatedMatchFixture: Match = {
  id: "rel-1",
  matched_bill_id: "00000000-0000-0000-0000-0000000000cc",
  matched_bill_number: "SB24-113",
  matched_bill_title: "Prohibit Discrimination Labor Union Participation",
  matched_state: "CO",
  similarity_score: 96.0,
  snippet_status: "pending",
  matched_snippets: null,
  match_type: "co_internal",
};

test("BillDetailPage renders Related Colorado Bills panel for co_internal matches", async () => {
  (api.bill as jest.Mock).mockResolvedValue(billFixture);
  (api.matches as jest.Mock).mockResolvedValue([relatedMatchFixture]);
  const { getByText } = render(<BillDetailPage />, { wrapper });
  await waitFor(() => expect(getByText(/Related Colorado Bills/i)).toBeInTheDocument());
  expect(getByText("Prohibit Discrimination Labor Union Participation")).toBeInTheDocument();
});

test("BillDetailPage shows cross-state empty state AND related panel when only co_internal matches exist", async () => {
  (api.bill as jest.Mock).mockResolvedValue(billFixture);
  (api.matches as jest.Mock).mockResolvedValue([relatedMatchFixture]);
  const { getByText } = render(<BillDetailPage />, { wrapper });
  await waitFor(() => expect(getByText(/no similarity matches/i)).toBeInTheDocument());
  expect(getByText(/Related Colorado Bills/i)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npm test -- RelatedBillCard BillDetail`
Expected: FAIL — `RelatedBillCard` module not found; panel text absent.

- [ ] **Step 3: Create `RelatedBillCard`**

Create `frontend/components/RelatedBillCard.tsx`:
```tsx
import Link from "next/link";
import type { Match } from "@/lib/types";

export default function RelatedBillCard({ match }: { match: Match }) {
  return (
    <Link
      href={`/bills/${match.matched_bill_id}`}
      className="flex items-center justify-between rounded-lg border border-slate-700 bg-slate-800/50 px-4 py-3 hover:border-amber-500/60 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500"
    >
      <div>
        <span className="font-mono text-sm text-slate-400">{match.matched_bill_number ?? ""}</span>
        <p className="font-medium text-slate-200">{match.matched_bill_title ?? "Untitled Colorado bill"}</p>
      </div>
      <span className="text-sm font-bold text-amber-400">
        {match.similarity_score.toFixed(0)}% shared text
      </span>
    </Link>
  );
}
```

- [ ] **Step 4: Split matches by type in the bill-detail page**

In `frontend/app/bills/[id]/page.tsx`: import the card (`import RelatedBillCard from "@/components/RelatedBillCard";`).
After the `matches` query, derive the two groups:
```tsx
  const crossStateMatches = matches?.filter((m) => m.match_type === "cross_state") ?? [];
  const coInternalMatches = matches?.filter((m) => m.match_type === "co_internal") ?? [];
```
Change the existing "Similarity Matches" section so its render/empty logic keys on `crossStateMatches`
(NOT `matches`): replace the `matches && matches.length === 0 ? ... : matches ? matches.map(...)` block with:
```tsx
            ) : crossStateMatches.length === 0 ? (
              <p className="text-slate-400">No similarity matches found.</p>
            ) : (
              crossStateMatches.map((match) => (
                <MatchCard
                  key={match.id}
                  match={match}
                  billNumber={bill?.bill_number ?? ""}
                  billState={bill?.state ?? ""}
                  istScore={bill?.ist_score?.source_authenticity_score ?? 0}
                />
              ))
            )}
```
Add a new section AFTER the "Similarity Matches" `</section>`, rendered only when there are co_internal
matches (a supplementary panel — no empty state of its own):
```tsx
          {coInternalMatches.length > 0 && (
            <section aria-label="Related Colorado bills">
              <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-400">
                Related Colorado Bills
              </h2>
              <p className="mb-4 text-sm text-slate-400">
                Other Colorado bills that share substantial text with this one — typically companion
                bills or reintroductions. This is distinct from cross-state copycat detection.
              </p>
              <div className="space-y-2">
                {coInternalMatches.map((match) => (
                  <RelatedBillCard key={match.id} match={match} />
                ))}
              </div>
            </section>
          )}
```

- [ ] **Step 5: Run to verify pass**

Run: `cd frontend && npm test -- RelatedBillCard BillDetail`
Expected: PASS (incl. the only-co_internal empty-state-plus-panel test).

- [ ] **Step 6: Commit**

```bash
git add frontend/components/RelatedBillCard.tsx frontend/__tests__/components/RelatedBillCard.test.tsx frontend/app/bills/[id]/page.tsx frontend/__tests__/pages/BillDetail.test.tsx
git commit -m "feat(web): add Related Colorado Bills panel to bill detail"
```

---

## Task 7: Frontend — landing-page "CO Bills with Related Text" stat card

**Route:** **Mechanical → `local_llm` (Sonnet).**

**Files:**
- Modify: `frontend/app/page.tsx`
- Modify: `frontend/e2e/dashboard.spec.ts`

- [ ] **Step 1: Update the dashboard e2e for a 4th card**

In `frontend/e2e/dashboard.spec.ts` (statsFixture already has `related_co_bills: 125` from Task 5),
rename/extend the grid test:
```typescript
test("stats grid renders 4 cards with numeric values", async ({ page }) => {
  await interceptDefault(page);
  await page.goto("/");
  await expect(page.getByText("289")).toBeVisible();
  await expect(page.getByText("17")).toBeVisible();
  await expect(page.getByText("342")).toBeVisible();
  await expect(page.getByText("125")).toBeVisible();
  await expect(page.getByText("CO Bills with Related Text")).toBeVisible();
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npx playwright test dashboard.spec.ts -g "4 cards"`
Expected: FAIL — "125" / card label not present. (If Playwright browsers aren't installed locally, this
step's failure may surface at the full-suite gate in Task 10 instead; proceed to Step 3.)

- [ ] **Step 3: Add the card and widen the grid**

In `frontend/app/page.tsx`, change the grid container `className="grid grid-cols-3 gap-4"` to
`className="grid grid-cols-2 gap-4 md:grid-cols-4"`, and add the fourth entry to the cards array:
```tsx
            { label: "CO Bills with Related Text", value: stats.related_co_bills },
```
(Place it after the "Copycat Alerts" entry so the honest "Copycat Alerts: 0" and the non-zero
"CO Bills with Related Text" sit side by side.)

- [ ] **Step 4: Run to verify pass**

Run: `cd frontend && npm test` (jest still green) and, if browsers are available,
`cd frontend && npx playwright test dashboard.spec.ts -g "4 cards"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/app/page.tsx frontend/e2e/dashboard.spec.ts
git commit -m "feat(web): add CO Bills with Related Text stat card"
```

---

## Task 8: Frontend — "Related" badge on dashboard bill rows  [CUTTABLE — pairs with Task 4]

**Route:** **Mechanical → `local_llm` (Sonnet).** Cut together with Task 4 if time-boxing.

**Files:**
- Modify: `frontend/app/page.tsx`
- Modify: `frontend/e2e/dashboard.spec.ts`

- [ ] **Step 1: Add an e2e assertion for the badge**

In `frontend/e2e/dashboard.spec.ts`, set `has_related: true` on the second bill (`SB24-005`) in
`billsFixture`, then add:
```typescript
test("related badge visible on bills with co_internal matches", async ({ page }) => {
  await interceptDefault(page);
  await page.goto("/");
  await expect(page.getByText("Related", { exact: true })).toBeVisible();
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npx playwright test dashboard.spec.ts -g "related badge"`
Expected: FAIL (no "Related" text). (As in Task 7, may defer to the Task 10 gate if browsers are absent.)

- [ ] **Step 3: Render the badge**

In `frontend/app/page.tsx`, in the bills `<li>` row, replace the trailing
`{bill.copycat_alert && <TagBadge type="source_cloned" />}` with a small flex group:
```tsx
                    <div className="flex shrink-0 items-center gap-2">
                      {bill.copycat_alert && <TagBadge type="source_cloned" />}
                      {bill.has_related && (
                        <span className="rounded bg-amber-500/15 px-2 py-0.5 text-xs font-semibold text-amber-300">
                          Related
                        </span>
                      )}
                    </div>
```

- [ ] **Step 4: Run to verify pass**

Run: `cd frontend && npm test` and (if available) `npx playwright test dashboard.spec.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/app/page.tsx frontend/e2e/dashboard.spec.ts
git commit -m "feat(web): add Related badge to dashboard bill rows"
```

---

## Task 9: Frontend — `/about` honesty sentence

**Route:** **Mechanical → `local_llm` (Sonnet).**

**Files:**
- Modify: `frontend/app/about/page.tsx`
- Modify: `frontend/__tests__/pages/About.test.tsx`

- [ ] **Step 1: Add an assertion to the About test**

In `frontend/__tests__/pages/About.test.tsx`, add a test asserting the distinction text is present
(match the existing test style in that file — render `<About />`, then
`expect(getByText(/never counted as a copycat alert/i)).toBeInTheDocument()`).
NOTE: assert on this contiguous phrase, NOT on "companion bills … or reintroductions" — the prose splits
those words with an inline `<strong>`/parenthetical, so a regex spanning them won't match a single text
node. The phrase chosen is one text node AND asserts the actual honesty claim. Do not weaken the prose to
satisfy a brittle regex; keep the prose in Step 3 and assert the robust phrase.

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npm test -- About`
Expected: FAIL — text absent.

- [ ] **Step 3: Add the paragraph**

In `frontend/app/about/page.tsx`, inside the "What LegiLens measures" `<section>` (after the existing IST
paragraph), add:
```tsx
        <p>
          Separately, LegiLens surfaces <strong>Related Colorado Bills</strong> — pairs of distinct
          Colorado bills that share substantial text, typically companion bills (House and Senate
          versions of one policy) or reintroductions across sessions. This is intra-state text reuse and
          is <em>not</em> cross-state copycat detection: a related Colorado bill is never counted as a
          copycat alert.
        </p>
```

- [ ] **Step 4: Run to verify pass**

Run: `cd frontend && npm test -- About`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/app/about/page.tsx frontend/__tests__/pages/About.test.tsx
git commit -m "docs(web): distinguish intra-CO related bills from cross-state copycat on /about"
```

---

## Task 10: Verification & deploy-readiness (gate before PR)

**Route:** **Judgment → Opus.** Per guardrail #3, review-the-diff ≠ runtime verification.

- [ ] **Step 1: Full backend suite**

Run: `cd backend && .venv/bin/pytest -q`
Expected: PASS, no warnings about un-awaited coroutines from the new pass.

- [ ] **Step 2: Full frontend suite**

Run: `cd frontend && npx tsc --noEmit && npm test`
Run (if Playwright browsers installed): `cd frontend && npm run build && npx playwright test`
Expected: PASS; zero axe violations on bill-detail and dashboard.

- [ ] **Step 3: Runtime check against real CO data (requires explicit user approval — it WRITES prod)**

The CO-internal pass is the deliverable, and the nightly cron will run `match_co_bills()` in prod anyway.
To verify before merge, run the match worker against prod via Railway env injection (read the spec
"Prod access" section). **This writes `co_internal` rows to the prod DB — confirm with the user first.**
After it runs, verify with the live API:
```bash
curl -fsS -A "legilens" https://web-production-17051.up.railway.app/stats
# Expect: copycat_alerts still 0 (HONESTY GUARD held), related_co_bills > 0 (~125)
```
Then open a known related bill's matches and confirm a `co_internal` entry with `matched_bill_number`
and a `/bills/<matched_bill_id>` link target. If a local Postgres with real CO signatures is available,
prefer running the pass there first and asserting the same two invariants.

- [ ] **Step 4: Open the PR**

```bash
git push -u origin feat/intra-co-related-bills
gh pr create --base main --title "feat: intra-CO Related Bills (WS1)" \
  --body "Implements WS1 of the CO pivot spec (docs/superpowers/specs/2026-06-02-co-related-bills-coverage-tracker-design.md). CO-internal related-bills pass writes co_internal SimilarityMatch rows only — copycat_alert stays cross-state-only. Adds match_type/matched bill id+number to MatchOut, related_co_bills stat + card, has_related list flag + badge, Related Colorado Bills panel, /about distinction.

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
```

- [ ] **Step 5: Request code review (Opus) before merge** — run `superpowers:requesting-code-review`, with
explicit focus on the honesty guard (no `ISTScore` written by the co_internal pass) and idempotency.

---

## Self-Review (run against spec §3 before executing)

- **Backend CO-internal pass** → Task 1. Self-guard, companion-noise guard, ≥70 gate, honesty guard all tested. ✓
- **`match_type` on `MatchOut` + router** → Task 2. ✓
- **`matched_bill_id`/number for the panel link** → Task 2 (number via outerjoin — disambiguates same-title companions). ✓
- **`related_co_bills` stat + card** → Tasks 3, 7. ✓
- **Related Colorado Bills panel, honest copy, links** → Task 6 (+ empty-state split correctness). ✓
- **Dashboard "Related" badge** → Tasks 4 (backend `has_related`) + 8 (badge), marked CUTTABLE together. ✓
- **`/about` distinction sentence** → Task 9. ✓
- **Snippets = pending only (no extraction in MVP)** → Task 1 writes `snippet_status="pending"`; no snippet code. ✓ (spec §3 "Snippets (scoped)").
- **No migration** → stated in header; all new fields join/computed. ✓
- **`copycat_alert` stays 0 / honesty** → Task 1 test + Task 10 Step 3 runtime invariant. ✓
- **Bidirectional pairs accepted (A→B, B→A)** → documented in `_find_co_internal_matches` docstring (spec §8 risk). ✓
