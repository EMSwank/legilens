# WS2 — Cron Un-gate to CO + Tier-1 (NY deferred) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Routing per task is driven by the `route-tasks` (pedalpoint) skill: mechanical → local_llm, structural → local_llm draft + Agent review, judgment → Agent.

**Goal:** Un-gate the nightly text-fetch cron from CO-only to CO + tier-1 comparison states **excluding New York**, so the corpus accrues cross-state MinHash signatures and real cross-state copycat alerts can surface — bounded, measured, reversible.

**Architecture:** New York is **demoted from priority tier 1 to tier 2** (not added to an exclude list). This implements spec §4's exact `max_priority_tier=1` mechanism while honoring the user's "without NY" decision, and — critically — keeps the load-bearing invariant `queue tier{0,1} == coverage.SCOPE` intact (both drop to 5 states together). The coverage matchable-% denominator must drop NY in lockstep, or NY's ~150k never-fetched bills pin the thermometer near ~14% forever (the exact "reads broken" failure spec §5 warns about). No new fetch/signature code: each fetched corpus bill already auto-gets a signature (spec §2, verified), and `match_co_bills`'s cross-state corpus is `is_corpus_only`-scoped, not state-scoped (verified `match.py:95`) — so CA/IL/TX/FL signatures flow in with zero match-phase change.

**Tech Stack:** Python 3.11, SQLAlchemy 2 async, FastAPI, pytest-asyncio (mock-only suite), pylint (CI fails on ANY message), Next.js 16 / React 19 / jest-axe.

**Why this is bigger than spec §4's "one-liner + 2 tests":** the spec assumed NY ∈ top-5. Excluding NY ripples into coverage SCOPE + frontend copy + the count-agnostic naming. Verified blast radius below.

---

## Why NY-out forces a coverage change (the load-bearing bit)

`scoped_matchable_pct` = Σ in-scope `with_sig` / Σ in-scope `fetchable`, SCOPE = the fetch target.
NY `fetchable` ≈ 150,449 (all have `text_doc_id`); NY `with_sig` ≈ 0 (text never fetched).
- Leave NY in SCOPE → denominator ≈ 174k, numerator climbs only via the other 24k → caps ≈ 14%.
- Drop NY from SCOPE → denominator ≈ 24k → climbs to 100% as CA/IL/TX/FL fetch.

Spec §5 PINS the denominator to "the current ingest goal … so it climbs to 100%." NY is no longer in the goal → NY must leave SCOPE. NY still renders on the coverage table as a `not_started` (tier-2) row — honest, and the legend already says remaining states are "queued for a later phase."

---

## File Structure

**Backend (source):**
- `backend/worker/queue.py` — demote NY (`_TOP5_STATES` → `_TIER1_STATES`, count-agnostic), add pure `tier_for()` mirror, add `max_priority_tier` param.
- `backend/worker/tasks/fetch_bill_texts.py` — thread `max_priority_tier` through to `next_queued_bills` (else scheduler call TypeErrors).
- `backend/worker/scheduler.py` — `fetch_and_match`: `priority_state="CO"` → `max_priority_tier=1`; rewrite the gate docstring.
- `backend/app/services/coverage.py` — `SCOPE` drops NY (6 → 5); update header/sync comment.

**Backend (tests):**
- `backend/tests/worker/test_queue.py` — `tier_for` classification test (real correctness) + `max_priority_tier` accepted-and-executes test (mock ceiling).
- `backend/tests/test_scheduler.py` — update the `fetch_and_match` assertion.
- `backend/tests/test_coverage_service.py` — update the SCOPE-set assertion + rename.

**Frontend:**
- `frontend/app/coverage/page.tsx` — "five comparison states (CA, NY, IL, TX, FL)" → "four (CA, IL, TX, FL)"; add NY-deferred note.
- `frontend/__tests__/pages/Coverage.test.tsx` — re-run (no `5`-string assertion expected; verify).

**Verification (not committed to app):**
- `/tmp/ws2_tier_probe.py` — read-only Neon probe: `next_queued_bills(max_priority_tier=1)` returns **zero** NY/tier-2 rows against real data (the SQL `.where()` the mock suite cannot verify).

**Docs:**
- `CLAUDE.md`, `README.md` — WS2 status row; correct WS3 SCOPE bullet ("CO + 5" → "CO + 4; NY deferred"); note `max_priority_tier`.

---

## Reversibility (re-promote NY later)

To fund NY (the ~150k / ~6.5mo tail) in a future WS2.5: add `"NY"` back to `_TIER1_STATES` and `coverage.SCOPE` (two edits, same list shape), bump the Neon cap, redeploy. The count-agnostic names mean no rename churn. This is the natural place to also raise the spend cap.

---

### Task 1: Pure `tier_for()` state→tier mirror

**Files:**
- Modify: `backend/worker/queue.py`
- Test: `backend/tests/worker/test_queue.py`

Route: **structural** (pure fn, framework-known) — local_llm draft + Agent review. This is load-bearing tier logic; WS3 showed local_llm flubbing exactly this kind of branch, so review on Opus.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/worker/test_queue.py` (top-level, alongside existing tests):

```python
def test_tier_for_classifies_states():
    """Pure mirror of the SQL _STATE_PRIORITY case. NY is tier 2 (deferred), not tier 1."""
    from worker.queue import tier_for

    assert tier_for("CO") == 0
    for s in ("CA", "IL", "TX", "FL"):
        assert tier_for(s) == 1, f"{s} must be tier 1"
    assert tier_for("NY") == 2, "NY is deferred to tier 2 in WS2 v1"
    assert tier_for("WY") == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/eliotswank/dev/legilens/backend && .venv/bin/python -m pytest tests/worker/test_queue.py::test_tier_for_classifies_states -v`
Expected: FAIL — `ImportError: cannot import name 'tier_for'`.

- [ ] **Step 3: Write minimal implementation**

In `backend/worker/queue.py`, replace the `_TOP5_STATES` definition and the sync comment (lines 18–20) with:

```python
# Keep tiers 0 (CO) + 1 (these states) in sync with app.services.coverage.SCOPE,
# the coverage tracker's matchable-% denominator. Change both together.
# NY is intentionally NOT here in WS2 v1: it is ~150k bills (~6.5 months alone) and is
# deferred to tier 2. Re-promote NY to this list AND to coverage.SCOPE together when the
# national tail is funded (and bump the Neon spend cap at the same time).
_TIER1_STATES = ["CA", "IL", "TX", "FL"]


def tier_for(state: str) -> int:
    """Pure-Python mirror of the SQL _STATE_PRIORITY case below.

    Exists so the mock-only test suite can verify tier membership (esp. that NY is
    excluded from tier 1) without a real DB — the SQL `case()` itself is exercised by a
    read-only Neon probe, not by unit tests.
    """
    if state == "CO":
        return 0
    if state in _TIER1_STATES:
        return 1
    return 2
```

Then update the `_STATE_PRIORITY` case (was `_TOP5_STATES`) to reference the renamed list:

```python
_STATE_PRIORITY = case(
    (Bill.state == "CO", 0),
    (Bill.state.in_(_TIER1_STATES), 1),
    else_=2,
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/eliotswank/dev/legilens/backend && .venv/bin/python -m pytest tests/worker/test_queue.py -v`
Expected: PASS (all queue tests, incl. existing `priority_state` test).

- [ ] **Step 5: Commit**

```bash
cd /Users/eliotswank/dev/legilens && git add backend/worker/queue.py backend/tests/worker/test_queue.py
git commit -m "feat(worker): demote NY to tier 2 + add tier_for mirror (WS2)"
```

---

### Task 2: `max_priority_tier` param on `next_queued_bills`

**Files:**
- Modify: `backend/worker/queue.py`
- Test: `backend/tests/worker/test_queue.py`

Route: **structural** — local_llm draft + Agent review.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/worker/test_queue.py`:

```python
async def test_next_queued_bills_max_priority_tier_accepted():
    """max_priority_tier kwarg is accepted and the query still executes.
    (Row-level tier exclusion is verified by the read-only Neon probe, not here —
    the mock session cannot evaluate the SQL .where().)"""
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = []
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result_mock)

    result = await next_queued_bills(session, batch_size=10, max_priority_tier=1)
    assert result == []
    session.execute.assert_awaited_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/eliotswank/dev/legilens/backend && .venv/bin/python -m pytest tests/worker/test_queue.py::test_next_queued_bills_max_priority_tier_accepted -v`
Expected: FAIL — `TypeError: next_queued_bills() got an unexpected keyword argument 'max_priority_tier'`.

- [ ] **Step 3: Write minimal implementation**

In `backend/worker/queue.py`, update the signature and add the filter. New signature:

```python
async def next_queued_bills(
    session,
    *,
    batch_size: int,
    priority_state: str | None = None,
    max_priority_tier: int | None = None,
) -> list[Bill]:
```

Extend the docstring Args with:

```
        max_priority_tier: if set, only return bills whose state priority tier is
                           <= this value (0=CO, 1=tier-1 comparison states, 2=rest).
                           max_priority_tier=1 is the steady-state corpus build (CO +
                           tier-1, NY excluded — NY is tier 2).
```

After the existing `priority_state` block, add:

```python
    if max_priority_tier is not None:
        stmt = stmt.where(_STATE_PRIORITY <= max_priority_tier)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/eliotswank/dev/legilens/backend && .venv/bin/python -m pytest tests/worker/test_queue.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/eliotswank/dev/legilens && git add backend/worker/queue.py backend/tests/worker/test_queue.py
git commit -m "feat(worker): add max_priority_tier filter to next_queued_bills (WS2)"
```

---

### Task 3: Thread `max_priority_tier` through `fetch_bill_texts`

**Files:**
- Modify: `backend/worker/tasks/fetch_bill_texts.py`

Route: **mechanical** (passthrough following existing `priority_state` pattern) — local_llm.

- [ ] **Step 1: Update the signature (line ~39–41)**

```python
async def fetch_bill_texts(
    *,
    batch_size: int = 50,
    priority_state: str | None = None,
    max_priority_tier: int | None = None,
) -> int:
```

- [ ] **Step 2: Pass it to `next_queued_bills` (line ~60–62)**

```python
        bills = await next_queued_bills(
            session,
            batch_size=batch_size,
            priority_state=priority_state,
            max_priority_tier=max_priority_tier,
        )
```

- [ ] **Step 3: Run the fetch + queue tests**

Run: `cd /Users/eliotswank/dev/legilens/backend && .venv/bin/python -m pytest tests/worker/ -v`
Expected: PASS (no behavior change when the new kwarg is unset; burst path still passes `priority_state="CO"`).

- [ ] **Step 4: Commit**

```bash
cd /Users/eliotswank/dev/legilens && git add backend/worker/tasks/fetch_bill_texts.py
git commit -m "feat(worker): thread max_priority_tier through fetch_bill_texts (WS2)"
```

---

### Task 4: Un-gate the cron in `fetch_and_match`

**Files:**
- Modify: `backend/worker/scheduler.py`
- Test: `backend/tests/test_scheduler.py`

Route: **judgment** (docstring rewrite encodes the policy decision + cites spec) — Agent / keep on Opus. The one-line call change is mechanical.

**Note — burst path stays CO-only on purpose.** `fetch_bill_texts_burst.py` keeps `priority_state="CO"`; cold-start fast-visibility is a different job than steady-state corpus build. Do NOT change it.

- [ ] **Step 1: Update the failing test first**

In `backend/tests/test_scheduler.py`, change the assertion in `test_fetch_and_match_runs_fetch_then_match` (line ~241):

```python
    fetch.assert_awaited_once_with(batch_size=1000, max_priority_tier=1)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd /Users/eliotswank/dev/legilens/backend && .venv/bin/python -m pytest tests/test_scheduler.py::test_fetch_and_match_runs_fetch_then_match -v`
Expected: FAIL — asserts `max_priority_tier=1` but code still calls `priority_state="CO"`.

- [ ] **Step 3: Change the call + rewrite the docstring**

In `backend/worker/scheduler.py`, change line ~46:

```python
    count = await fetch_bill_texts(batch_size=1000, max_priority_tier=1)
```

Update the log line ~47 to drop the "CO" wording:

```python
    logger.info("fetch_and_match: fetched %d bills (CO + tier-1, NY deferred)", count)
```

Replace the `fetch_and_match` docstring body (the `priority_state="CO"` paragraph) with:

```python
    """Daily steady-state: fetch ~1k queued bill texts (CO + tier-1 comparison
    states, NY excluded) then run the match phase.

    Runs after run_full_pipeline (03:00). Quota guard inside fetch_bill_texts
    (QUOTA_HARD_LIMIT=27_000/mo) prevents overrun even if called extra times.

    max_priority_tier=1 un-gates the fetch from CO-only (PR #58) to CO + tier-1.
    This is the WS2 decision (docs/superpowers/specs/2026-06-02-...-design.md §4):
    fund a bounded cross-state corpus so real cross-state copycat alerts can
    surface. New York is deliberately deferred: it is ~150k bills (~6.5 months at
    the quota cap) and is demoted to tier 2 (worker/queue.py) — fetched only when
    the national tail is explicitly funded and the Neon spend cap is raised.

    Reassess trigger: when CO + tier-1 reach ~complete on /coverage, evaluate
    whether real cross-state copycat_alerts appeared. If yes, plan widening
    (re-promote NY, then the rest). If no, stop. Document in a follow-up.
    """
```

- [ ] **Step 4: Run the scheduler tests**

Run: `cd /Users/eliotswank/dev/legilens/backend && .venv/bin/python -m pytest tests/test_scheduler.py -v`
Expected: PASS (all fetch_and_match tests, incl. the zero-fetch + coverage-snapshot ones).

- [ ] **Step 5: Commit**

```bash
cd /Users/eliotswank/dev/legilens && git add backend/worker/scheduler.py backend/tests/test_scheduler.py
git commit -m "feat(worker): un-gate fetch_and_match to CO + tier-1, NY deferred (WS2)"
```

---

### Task 5: Drop NY from coverage `SCOPE`

**Files:**
- Modify: `backend/app/services/coverage.py`
- Test: `backend/tests/test_coverage_service.py`

Route: **mechanical** (tuple edit + comment) — local_llm. The *reason* is judgment but the edit is trivial; the test pins it.

- [ ] **Step 1: Update the failing test first**

In `backend/tests/test_coverage_service.py`, rename and update (lines 11–12):

```python
def test_scope_is_co_plus_tier1_excludes_ny():
    # NY is deferred (tier 2) in WS2 v1 — it must NOT be in the matchable-% denominator,
    # or its ~150k never-fetched bills pin the thermometer near ~14%.
    assert set(SCOPE) == {"CO", "CA", "IL", "TX", "FL"}
    assert "NY" not in SCOPE
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd /Users/eliotswank/dev/legilens/backend && .venv/bin/python -m pytest tests/test_coverage_service.py::test_scope_is_co_plus_tier1_excludes_ny -v`
Expected: FAIL — `SCOPE` still contains `"NY"`.

- [ ] **Step 3: Update `SCOPE` + comment**

In `backend/app/services/coverage.py`, change the `SCOPE` definition and its header comment (lines ~9, ~15–16):

```python
# SCOPE must stay in sync with backend/worker/queue.py tiers 0+1 (_STATE_PRIORITY).
# Change both together.
```

```python
# CO (tier 0) + the tier-1 comparison states (currently CA/IL/TX/FL).
# NY is deferred to tier 2 in WS2 v1, so it is intentionally NOT in scope — including it
# would pin the matchable-% thermometer near ~14% (its ~150k bills are never fetched).
SCOPE: tuple[str, ...] = ("CO", "CA", "IL", "TX", "FL")
```

- [ ] **Step 4: Run the coverage-service tests**

Run: `cd /Users/eliotswank/dev/legilens/backend && .venv/bin/python -m pytest tests/test_coverage_service.py -v`
Expected: PASS (the `scoped_pct` tests use CO/TX/WY rows — no NY data — so numbers are unaffected).

- [ ] **Step 5: Commit**

```bash
cd /Users/eliotswank/dev/legilens && git add backend/app/services/coverage.py backend/tests/test_coverage_service.py
git commit -m "feat(api): drop NY from coverage SCOPE to keep thermometer honest (WS2)"
```

---

### Task 6: Frontend coverage copy (NY out of the named set)

**Files:**
- Modify: `frontend/app/coverage/page.tsx`
- Test: `frontend/__tests__/pages/Coverage.test.tsx` (re-run)

Route: **mechanical** (copy edit) — local_llm or inline.

- [ ] **Step 1: Update the two copy strings**

Line ~37 — change:
```
          ingest target — Colorado plus five comparison states (CA, NY, IL, TX, FL).
```
to:
```
          ingest target — Colorado plus four comparison states (CA, IL, TX, FL).
          New York is queued for a later phase.
```

Line ~75 — change `Colorado + 5 comparison states` to `Colorado + 4 comparison states`.

- [ ] **Step 2: Run the unit test**

Run: `cd /Users/eliotswank/dev/legilens/frontend && npm test -- Coverage`
Expected: PASS (jest-axe; assertions are on roles/structure, not the comparison-state count).

- [ ] **Step 3: Commit**

```bash
cd /Users/eliotswank/dev/legilens && git add frontend/app/coverage/page.tsx
git commit -m "feat(web): coverage copy reflects NY-deferred tier-1 set (WS2)"
```

---

### Task 7: Read-only Neon probe — prove the SQL excludes NY

**Files:**
- Create: `/tmp/ws2_tier_probe.py` (not committed)

Route: **judgment** (verification design) — keep on Opus. This is the real correctness gate the mock suite cannot provide (mirror of the WS3 coverage probe).

- [ ] **Step 1: Write the probe**

```python
"""Read-only WS2 probe. Proves next_queued_bills(max_priority_tier=1) excludes NY/tier-2.
SELECT only — no writes."""
import asyncio
from collections import Counter
from app.database import async_session
from worker.queue import next_queued_bills, tier_for


async def main():
    async with async_session() as s:
        bills = await next_queued_bills(s, batch_size=5000, max_priority_tier=1)
    by_state = Counter(b.state for b in bills)
    tiers = {st: tier_for(st) for st in by_state}
    ny = by_state.get("NY", 0)
    tier2 = sum(n for st, n in by_state.items() if tier_for(st) == 2)
    print(f"rows={len(bills)}  distinct_states={dict(by_state)}")
    print(f"tiers={tiers}")
    print(f"NY_rows={ny}  (MUST be 0)")
    print(f"tier2_rows={tier2}  (MUST be 0)")
    assert ny == 0, "NY leaked into max_priority_tier=1 result"
    assert tier2 == 0, "a tier-2 state leaked into max_priority_tier=1 result"
    print("PASS: max_priority_tier=1 returns only CO + tier-1 states")


asyncio.run(main())
```

- [ ] **Step 2: Run it against prod (read-only, env injected)**

Run: `cd /Users/eliotswank/dev/legilens/backend && railway run --service worker .venv/bin/python /tmp/ws2_tier_probe.py`
Expected: `NY_rows=0`, `tier2_rows=0`, `PASS`. If anything leaks, STOP — the `_STATE_PRIORITY`/`tier_for` logic disagrees with the SQL.

---

### Task 8: Full green gate

**Files:** none (verification only)

Route: **me** (orchestration).

- [ ] **Step 1: Backend tests**

Run: `cd /Users/eliotswank/dev/legilens/backend && .venv/bin/python -m pytest -q`
Expected: all pass (≈185), no new skips.

- [ ] **Step 2: Pylint (CI parity — fails on ANY message)**

Run: `cd /Users/eliotswank/dev/legilens/backend && .venv/bin/python -m pylint $(git -C /Users/eliotswank/dev/legilens ls-files 'backend/**/*.py')`
Expected: `10.00/10`, zero messages.

- [ ] **Step 3: Frontend unit + build**

Run: `cd /Users/eliotswank/dev/legilens/frontend && npm test && npm run build`
Expected: jest green; Next build succeeds.

---

### Task 9: Docs sync + PR (pause before merge)

**Files:**
- Modify: `CLAUDE.md`, `README.md`

Route: **judgment** (doc accuracy) — keep on Opus.

- [ ] **Step 1: Update `CLAUDE.md`**
  - Add a WS2 status row to §5 (Current Implementation Status).
  - Correct the WS3 design bullet: "SCOPE = CO + 5 comparison states" → "CO + 4 (CA/IL/TX/FL); NY deferred to tier 2 (WS2)".
  - Note `max_priority_tier` on `next_queued_bills` + that `fetch_and_match` now un-gated to tier-1.

- [ ] **Step 2: Update `README.md`** (mirror the status + any SCOPE/state-count mention).

- [ ] **Step 3: Commit + push + open PR**

```bash
cd /Users/eliotswank/dev/legilens && git add CLAUDE.md README.md
git commit -m "docs: WS2 cron un-gate (CO + tier-1, NY deferred)"
git push -u origin feat/cron-ungate-tier1
gh pr create --title "feat: un-gate cron to CO + tier-1, NY deferred (WS2)" --body "<summary + merge-gate note>"
```

- [ ] **Step 4: STOP — do not merge.**
  Merging starts real LegiScan quota + Neon $ burn (the cron begins draining ~24k non-CO bills, ~1 month). **Merge waits on the user confirming the Neon spend cap is set.** Report green CI + PR link and hold.

---

## Self-Review

**Spec coverage (§4):** ✓ `max_priority_tier` param (T2), ✓ scheduler un-gate + docstring citing spec (T4), ✓ tests for tier filter (T1 mirror + T7 probe) and the scheduler assertion (T4). Divergence from spec — NY excluded — is explicit and carries the coverage-SCOPE change (T5) the spec didn't anticipate.

**Placeholder scan:** PR body `<summary…>` is the only placeholder, filled at T9 from the green-CI results. All code steps show full code.

**Type/name consistency:** `_TIER1_STATES` (not `_TOP5`/`_TOP4`) used in T1 def, T1 `_STATE_PRIORITY`, and `tier_for`. `max_priority_tier: int | None = None` identical across `next_queued_bills` (T2) and `fetch_bill_texts` (T3). `SCOPE` 5-tuple in T5 matches `_TIER1_STATES` ∪ {CO}. Probe (T7) imports `tier_for` + `next_queued_bills` exactly as defined.

**Invariant check:** queue tier{0,1} = {CO,CA,IL,TX,FL} == coverage.SCOPE (T1 ↔ T5). Both edited, both tested. The sync comment in both files cross-references the other.
