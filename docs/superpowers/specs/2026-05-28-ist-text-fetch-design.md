# IST Text-Fetch Pipeline Redesign

**Date:** 2026-05-28
**Status:** Design / pre-implementation
**Owner:** Eliot Swank
**Supersedes (partially):** `docs/superpowers/specs/2026-05-06-legilens-mvp-design.md` — text-acquisition section

---

## Problem statement

The Influence & Source Tracker (IST) pipeline is architecturally broken. Symptoms observed against the live deploy on 2026-05-28:

- 422 LegiScan datasets ingested
- ~802,000 bill rows in `bills`
- **0 rows in `minhash_signatures`**
- 12,430 CO bills, `with_text=0`
- `/stats` returns `copycat_alerts=0, bills_analyzed=0`

Root cause: LegiScan `getDataset` ZIP archives contain bill metadata and **references** to text (`doc_id`, `mime`, `url`, `state_link`) but **do not** include inline base64 `doc` fields. Inline bill text is only delivered by `getBillText`, which the MVP design (2026-05-06) explicitly reserved for "Phase 3 on-demand Pro API calls only." That phasing is internally inconsistent — Phase 1 ingest cannot compute MinHash signatures without text, so signatures never get written, so the match phase finds nothing, so the live site displays zero alerts indefinitely.

The MVP did ship — ingest works, schema is current (`alembic_version=004`), API endpoints respond, frontend renders. The IST module specifically is a no-op until text lands in `bills.full_text`.

## Goals

1. Restore IST functionality on free-tier LegiScan (30,000 calls / month).
2. Surface usable copycat signal on the live site within days of deploy.
3. Improve daily — site gets better every 24h as more text arrives.
4. Preserve the existing 802k bill rows. No re-ingest. No deletes.
5. Scale toward national coverage over weeks/months without ever exceeding free quota.

## Non-goals

- Real-time fetching of new bills (daily batch is fine).
- Paid LegiScan tier (explicitly out — user chose free-only).
- Scraping state websites (deferred — only if LegiScan path proves insufficient).
- Backfilling MinHash signatures via alternate text sources (Open States, state PDFs) — deferred.
- ~~Storage optimization deferred~~ — **moved into scope** as Phase 2.5 measurement gate. Storage is a hard constraint that gates Phase 3, not a future cleanup.

## Constraints (locked in brainstorm)

- **Budget:** free LegiScan only.
- **Quality > speed:** no shortcuts that compromise sample completeness.
- **CO-first:** Colorado bills get fetched before any other state.
- **Storage:** persist full text in Postgres for now. Storage cost optimization is a separate future concern.
- **Burst the rest of May:** ~3k calls remaining in May get spent immediately on CO bills.
- **Adaptive quota:** worker tracks its own call count, throttles at 90% of monthly budget. No reliance on LegiScan response headers (not reliable enough).
- **Daily updates:** the worker incrementally improves the site every 24h. Users see new data appear without redeploys.

---

## Architecture overview

Two distinct fetch modes, one shared steady-state loop:

```
┌─────────────────────────────────────────────────────────────────┐
│  Existing pipeline (unchanged where possible)                   │
│                                                                  │
│  LegiScan getDatasetList → getDataset (ZIPs) → bills table      │
│                                                                  │
│  ingest still runs — it maintains the bill inventory.            │
│  bills get text=NULL, text_fetch_status='queued' at insert.      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  NEW: fetch_bill_texts worker                                    │
│                                                                  │
│  Picks N bills from queue, calls getBillText per bill,          │
│  decodes base64 → bills.full_text, computes MinHash → upsert    │
│  to minhash_signatures, marks text_fetch_status='done'.          │
│                                                                  │
│  Two modes:                                                      │
│    burst: CO-only, runs once on demand, burns remaining quota   │
│    steady: priority-ordered, daily cron, ~800-1k calls/day      │
│                                                                  │
│  Adaptive throttle: aborts when worker_state.quota_used > 27k.  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  match_co_bills (modified)                                       │
│                                                                  │
│  Runs after each fetch batch (not just nightly).                │
│  Queries CorpusIndex built ONLY from bills with signatures.     │
│  Match population grows daily as more signatures appear.         │
│  Idempotent — CO IST scores + matches deleted + rebuilt.        │
└─────────────────────────────────────────────────────────────────┘
```

### Why two modes

**Burst** exists because May's quota would otherwise expire unused. Spending ~3k calls in late May on CO bills surfaces immediate CO-internal copycat signal (same-legislator-across-sessions, common boilerplate). Provides a "the site works" demo within 24h of deploy.

**Steady-state** is the long game. ~1000 calls/day × 30 days = 30k/month. Burns ~80% of monthly quota on text fetches, leaves headroom for ingest + retries. CO finishes in ~12-15 days, then priority order falls through: CA, NY, IL, TX, FL (legislatures with high model-bill traffic), then alphabetical.

---

## Components

### `backend/worker/tasks/fetch_bill_texts.py` (new)

Function: `async def fetch_bill_texts(session, batch_size: int = 50, priority_state: str | None = None)`

Behavior:
1. Load `worker_state.legiscan_quota_used` and `legiscan_quota_month`. If month rolled over, reset counter to 0.
2. If `quota_used >= 27000`: log warning, return early.
3. Query `bills` for next `batch_size` rows where `text_fetch_status='queued' AND full_text IS NULL AND text_fetch_attempts < 3`, ordered by priority (see below). If `priority_state` set, filter to that state.
4. For each bill, run **one transaction** containing all of:
   - Mark `text_fetch_status='fetching'`, increment `text_fetch_attempts` (committed as part of the same transaction below — the in-flight marker exists only to detect zombie rows on worker restart, not as a separate commit).
   - Call `legiscan.get_bill_text_by_doc_id(bill.text_doc_id)` — returns decoded UTF-8 string (the helper decodes base64 internally) or None on empty/decode-fail. **API call happens outside the DB transaction** to avoid holding a connection during network I/O; the transaction opens after the response lands. Note: this requires `bills.text_doc_id` to be populated; ingest writes it from `texts[-1].doc_id` on every dataset parse, and a one-shot backfill script handles legacy rows.
   - Decode base64. Outcomes:
     - **Success** (doc present, decodes, non-empty): set `bills.full_text = decoded`, `bills.text_fetched_at = now()`, `bills.text_fetch_status = 'done'`. Compute MinHash. Upsert to `minhash_signatures` (existing `on_conflict_do_update` path from PR #48). Increment `worker_state.legiscan_quota_used` by 1. Commit.
     - **Permanent failure** (decode error, empty doc, HTTP 4xx other than 429): set `text_fetch_status='failed'`, `text_fetch_attempts += 1`. Increment `legiscan_quota_used` (call was made). Commit. If `text_fetch_attempts >= 3` after increment, status set to `skipped` instead.
     - **Transient failure** (HTTP 429, 5xx, network timeout): set `text_fetch_status='queued'` again (no progress, retry next batch), `text_fetch_attempts += 1`. **Do not** increment quota counter — LegiScan typically doesn't charge against quota for 429/5xx. Commit.
   - On crash mid-transaction: full rollback. `text_fetch_status` stays `queued`, counter unchanged, no torn state. Next batch picks the bill up again.
5. Return count of bills processed (success + permanent-failure count, excludes transient retries).

**Transaction invariant:** quota counter, bill row, and signature row update atomically. Crash anywhere = clean rollback. This is the mitigation for risk #2 (quota drift).

**Retry semantics (3-strike rule):**
- `text_fetch_attempts` increments on every permanent or transient failure.
- At attempt 3+, bill is marked `skipped` and excluded from the queue permanently. Prevents quota burn on malformed/deleted bills.
- Operator can manually reset `text_fetch_attempts=0` and `text_fetch_status='queued'` to force a re-attempt if a known LegiScan-side fix lands.

Priority order for the queue:
```
ORDER BY
  CASE state
    WHEN 'CO' THEN 0
    WHEN 'CA' THEN 1
    WHEN 'NY' THEN 1
    WHEN 'IL' THEN 1
    WHEN 'TX' THEN 1
    WHEN 'FL' THEN 1
    ELSE 2
  END,
  state ASC,
  bill_id ASC
```

### `backend/worker/tasks/fetch_bill_texts_burst.py` (new)

Wrapper that calls `fetch_bill_texts(priority_state='CO', batch_size=…)` in a loop until either:
- CO queue is exhausted (no rows where `state='CO' AND text_fetch_status='queued'`)
- Quota budget for this run is hit (`max_calls` arg, default 3000)
- Adaptive throttle fires (`quota_used >= 27000`)

After the loop completes: invoke `match_co_bills` once to score the new signatures.

### `backend/worker/tasks/match.py` (modified)

Current code: loads all CO signatures, builds `CorpusIndex` from all corpus signatures, runs LSH lookup.

Change required: nothing structurally — already iterates over whatever signatures exist. The relevant change is **scheduling**: invoke `match_co_bills` after each fetch batch, not only at end of nightly ingest.

Add a `match_type` column to `similarity_matches` populated by the matcher:
- `co_internal` if `bill_a.state == 'CO' AND bill_b.state == 'CO'`
- `cross_state` if `bill_a.state != bill_b.state`

This lets the UI surface CO-vs-CO matches as a distinct category ("intra-Colorado model legislation") that's interesting even before national coverage is complete.

### `backend/worker/tasks/ingest.py` (modified)

`_process_bill` change: when inserting a new bill row, set `text_fetch_status='queued'` and leave `full_text=NULL`. Do not attempt to extract text from the dataset ZIP — that's known broken and a waste of cycles.

Remove the existing `_extract_text` no-op path. Drop the MinHash computation from ingest entirely — moved to `fetch_bill_texts`.

Existing 802k bill rows: a one-shot UPDATE in migration 005 sets `text_fetch_status='queued'` for all rows where `full_text IS NULL`. Bills that somehow already have text (none currently, but defensive) get `text_fetch_status='done'`.

### `backend/worker/scheduler.py` (modified)

Add a new APScheduler job:
- ID: `fetch_and_match`
- Cron: daily at 04:00 UTC (one hour after `run_full_pipeline`)
- Function: `fetch_bill_texts(batch_size=1000)` → on success → `match_co_bills`
- `max_instances=1`
- `coalesce=True`

Burst is **not** scheduled. It's invoked manually via Railway shell or a one-shot job at deploy time.

### `backend/worker/state.py` (small addition)

Helper functions for the quota counter:
- `async def get_quota_used(session) -> int`
- `async def increment_quota(session, n: int = 1)` — atomic UPDATE
- `async def reset_quota_if_month_rolled(session)` — compares stored month to current UTC month, zeroes counter on rollover

Uses existing `worker_state` table (no schema change for this — keys are `legiscan_quota_used`, `legiscan_quota_month`).

---

## Data model changes

### Alembic migration 005 (`005_text_fetch_columns.py`)

**Forward:**
```sql
ALTER TABLE bills ADD COLUMN text_fetch_status VARCHAR(16) NOT NULL DEFAULT 'queued';
ALTER TABLE bills ADD COLUMN text_fetched_at TIMESTAMPTZ NULL;
ALTER TABLE bills ADD COLUMN text_fetch_attempts INT NOT NULL DEFAULT 0;
ALTER TABLE bills ADD COLUMN text_doc_id INT NULL;
CREATE INDEX ix_bills_text_fetch_queue
  ON bills (state, legiscan_id)
  WHERE text_fetch_status = 'queued' AND full_text IS NULL AND text_fetch_attempts < 3;

ALTER TABLE similarity_matches ADD COLUMN match_type VARCHAR(16) NOT NULL DEFAULT 'cross_state';
CREATE INDEX ix_similarity_matches_match_type ON similarity_matches (match_type);

-- Backfill: bills already in DB with no text get the queued status.
UPDATE bills SET text_fetch_status='done' WHERE full_text IS NOT NULL;
-- Default handles the NULL-text case.
```

**Downgrade:**
```sql
DROP INDEX IF EXISTS ix_similarity_matches_match_type;
ALTER TABLE similarity_matches DROP COLUMN match_type;
DROP INDEX IF EXISTS ix_bills_text_fetch_queue;
ALTER TABLE bills DROP COLUMN text_doc_id;
ALTER TABLE bills DROP COLUMN text_fetch_attempts;
ALTER TABLE bills DROP COLUMN text_fetched_at;
ALTER TABLE bills DROP COLUMN text_fetch_status;
```

Allowed values for `bills.text_fetch_status`: `queued`, `fetching`, `done`, `failed`, `skipped`. No enum constraint — string column for flexibility. App code is the source of truth.

`text_fetch_attempts` tracks the 3-strike retry budget. Partial index on the queue filter (`queued + null text + attempts < 3`) keeps queue queries sublinear as the `done`/`skipped` set grows to dominate.

### `models/bill.py` additions

```python
text_fetch_status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued")
text_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
text_fetch_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
text_doc_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
```

`text_doc_id` is the LegiScan text document reference extracted from a bill's `texts[].doc_id` array at ingest. It's the input to `getBillText`. A separate Phase 2c backfill script populates this column for the existing 802k bill rows by re-parsing cached dataset ZIPs from the Railway Volume.

### `models/similarity_match.py` addition

```python
match_type: Mapped[str] = mapped_column(String(16), nullable=False, default="cross_state")
```

### `worker_state` reuse (no schema change)

Two new keys: `legiscan_quota_used` (int as string), `legiscan_quota_month` (`YYYY-MM` string). Existing `worker_state` table from Alembic 003 already has the right shape (`key VARCHAR PRIMARY KEY`, `value TEXT`, `updated_at TIMESTAMPTZ`).

---

## Match phase: incremental rebuild

The existing `match_co_bills` already does the right thing for an incremental world — it queries the current set of signatures and builds `CorpusIndex` from whatever exists. No structural rewrite needed.

What changes:
1. **Trigger frequency:** runs after every fetch batch instead of only end of nightly ingest.
2. **Result population:** as more signatures land, more matches surface. The first burst run on CO-only signatures produces CO-internal matches only (because corpus = CO bills only at that point). Once cross-state fetches begin in steady-state, cross-state matches join the result set automatically.
3. **`match_type` tagging:** new column populated based on `bill_a.state` vs `bill_b.state`.
4. **Idempotency preserved:** existing top-of-run DELETE on CO `ISTScore` + `SimilarityMatch` rows keeps working. Reruns produce consistent state.

The first usable site state (post-burst) shows ~CO-internal copycat alerts only. That's interesting in its own right — boilerplate definitions, same-sponsor reuse across sessions, common preamble language. It's also the most defensible "the IST module works" demo because the user can verify CO-vs-CO matches directly without trusting our national corpus.

---

## Salvage analysis

All 802k existing bill rows are reusable. Concrete reuse:

| Existing data | Reused as | Action needed |
|---|---|---|
| `bills` rows (802k) | Inventory of what to fetch text for | Migration 005 backfills `text_fetch_status='queued'` |
| `bills.bill_id`, `state`, `session`, `title`, `description` | Display + filtering on the live site | No change |
| `bills.is_corpus_only` | Public-visibility flag (only CO shown) | No change |
| `dataset_hashes` rows (422) | Skip re-download on next pipeline run | No change |
| `worker_state.bootstrap_*` | Bootstrap debounce (7-day TTL) | No change |
| `minhash_signatures` (currently 0 rows) | Will populate as fetcher runs | No change to table |
| ZIP cache on Railway Volume | Skip API call on dataset hash match | No change |

No deletes. No re-ingest. The fetcher walks the existing inventory and adds text/signatures via UPDATE.

---

## Testing strategy

### Unit tests (`backend/tests/worker/`)

1. **`test_fetch_bill_texts.py`**
   - Mocked LegiScan client. Fetches N=10 queued bills. Assert N API calls made.
   - Status transitions: `queued → fetching → done` (commit per bill).
   - Failure path: HTTP 500 → `text_fetch_status='failed'`, no signature row written.
   - Quota guard: stored `quota_used >= 27000` → returns early, zero API calls.

2. **`test_fetch_bill_texts_burst.py`**
   - `priority_state='CO'` filter applied.
   - Stops when CO queue exhausted even if `max_calls` not hit.
   - Stops when `max_calls` hit even if CO queue has more rows.
   - Triggers `match_co_bills` exactly once after loop.

3. **`test_priority_queue.py`**
   - Insert bills with states: CO, CA, NY, AL, WY. Assert returned order: CO, CA, NY, AL, WY.
   - Assert `full_text IS NOT NULL` rows skipped.
   - Assert `text_fetch_status='done'` rows skipped.
   - Assert `LIMIT N` respected.

4. **`test_match_co_bills_incremental.py`**
   - Seed: 100 corpus bills, 30 with signatures, 5 of which are CO.
   - Run match. Assert only 5×30 candidate pairs evaluated (not 5×100).
   - Re-run. Assert idempotent — same matches, no duplicates.
   - Assert `match_type='co_internal'` for CO-CO pair, `match_type='cross_state'` for CO-other pair.

5. **`test_adaptive_quota.py`**
   - Seed `worker_state.legiscan_quota_used='27000'`, `legiscan_quota_month='2026-05'`. Run fetcher with current month = May. Assert no API calls.
   - Seed `legiscan_quota_month='2026-04'`, run with current month = May. Assert counter resets to 0, fetcher proceeds.

### Integration test (CI-only)

6. **`test_legiscan_getBillText_real.py`**
   - Gated on `LEGISCAN_API_KEY` env. Skipped by default locally.
   - Hits real LegiScan API for one known bill ID per CI run.
   - Asserts response shape: `doc` field present, base64 decodes to non-empty bytes.
   - Costs 1 quota call per CI build.

### Migration regression

7. **`test_migration_005.py`**
   - Stamp DB to 004. Run upgrade to 005.
   - Assert new columns + indexes present.
   - Assert backfill: existing `bills` rows with `full_text=NULL` have `text_fetch_status='queued'`.
   - Assert legacy `similarity_matches` rows have `match_type='cross_state'`.
   - Run downgrade. Assert clean rollback.

### End-to-end smoke (manual, post-deploy)

8. Burst run against staging Neon branch with real API key.
   - ~100 CO bills get text + signatures within 10 min.
   - At least 1 CO-internal match surfaces (high-confidence prediction — boilerplate is everywhere).
   - `/stats` shows `bills_analyzed > 0`.
   - `/bills/{id}/matches` returns non-empty for ≥1 bill.

### Coverage targets

- `fetch_bill_texts.py`: 90%+ line coverage (new code, high risk).
- `match.py` modifications: existing coverage maintained or improved.
- Migration 005: covered by regression test.

---

## Rollout plan

### Phase 0 — Halt damage (immediate, current session)

- Pause Railway worker service via dashboard. Worker currently burns quota on ingest passes that produce 0 signatures. Reclaim ~3k remaining May calls.
- Verify worker stopped. No new dataset downloads.

### Phase 1 — Migration (day 1)

- Branch `feat/ist-migration-005`.
- Write Alembic 005 + `test_migration_005.py`.
- Apply locally against fresh DB, verify forward + downgrade.
- PR review, merge.
- Deploy. Verify `alembic upgrade head` runs on prod Neon. Spot-check new columns present. No data loss.

### Phase 2 — Fetcher implementation (day 2-3)

- Branch `feat/ist-fetch-bill-texts`.
- Implement `fetch_bill_texts.py` + unit tests.
- Implement `fetch_bill_texts_burst.py` + unit tests.
- Implement priority queue + adaptive quota helpers.
- Modify `_process_bill` for the queue/upsert split.
- Modify `match_co_bills` for `match_type` column.
- Wire scheduler: daily `fetch_and_match` at 04:00 UTC.
- PR review, merge.

### Phase 2.5 — Storage measurement gate (day 3.5, **BLOCKS Phase 3**)

The 1.2GB raw-text estimate vs 0.5GB Neon free tier is the single hardest constraint in this design. Postgres TOAST auto-compresses `text` columns >2KB with pglz (~70-80% compression on legislative prose), so real on-disk cost is likely 300-500MB. But "likely" is not "verified" — and a managed-tier overrun crashes the worker mid-fetch and corrupts the `text_fetch_status` queue. Measure before committing.

Procedure:
1. Deploy Phase 2 code to Railway.
2. Run `fetch_bill_texts_burst(max_calls=100, priority_state='CO')` — small sample, ~100 CO bills.
3. Query Neon for actual storage footprint:
   ```sql
   SELECT pg_size_pretty(pg_total_relation_size('bills')) AS bills_size,
          pg_size_pretty(pg_total_relation_size('minhash_signatures')) AS sigs_size,
          pg_size_pretty(pg_database_size(current_database())) AS db_size,
          COUNT(*) FILTER (WHERE text_fetch_status='done') AS done_count,
          AVG(LENGTH(full_text)) FILTER (WHERE full_text IS NOT NULL) AS avg_text_bytes
     FROM bills;
   ```
4. Extrapolate: `(avg_text_bytes × 12_430 CO bills) + current overhead = projected DB size after CO complete`.
5. Decision tree:
   - **Projected < 400MB:** safe headroom. Proceed to Phase 3 burst.
   - **Projected 400-480MB:** tight. Either (a) accept and add daily storage monitor, or (b) implement snippet-only storage now (described below). Pick before proceeding.
   - **Projected > 480MB:** **stop.** Pick one of:
     - **(a) Snippet-only storage:** add `bills.text_snippets` JSONB column. After MinHash computed, extract top-K shingles + surrounding context (~5KB/bill), store only that. Drop `full_text`. Trade-off: cannot re-extract snippets if matching algorithm changes; ghost-state needed for unmatched-but-text-bearing bills. Preserves UI snippet diffs. ~60MB total instead of 1.2GB.
     - **(b) Neon paid tier:** $19/mo, 10GB. User said "free-only" but storage is a different cost axis than API quota — surface the trade-off, let user decide.
     - **(c) Object storage:** offload `full_text` to S3-equivalent, keep only signatures + metadata in Postgres. Bigger architecture change, defer if (a) or (b) viable.

Gate: do not proceed to Phase 3 until projected national footprint (CO + top-5 states ≈ 80k bills × avg) also fits the chosen storage strategy. National extrapolation matters because Phase 4 will get there.

### Phase 3 — Controlled burst (day 4, **gated on Phase 2.5**)

- Confirm storage strategy from Phase 2.5 deployed.
- Manually trigger `fetch_bill_texts_burst` via Railway shell or one-shot cron. Spends remaining ~3k calls on CO bills only (Phase 2.5 used ~100, leaving ~2.9k).
- Watch logs live: quota counter increments, `with_text` (or `text_snippets`) count climbs, signatures appear, match phase fires.
- After burst:
  - `/stats` shows `bills_analyzed > 0`, `copycat_alerts > 0`
  - Spot-check 5 CO bills on legilens.vercel.app — matches look plausible.
  - Neon dashboard shows DB size matches Phase 2.5 projection.

### Phase 4 — Steady-state (day 5, June 1)

- Monthly quota resets June 1. Fresh 30k.
- Daily cron picks up where burst left off. Budget ~800-1000 calls/day = ~24-30k/month.
- CO completes in ~12-15 days. Priority queue then advances to CA, NY, IL, TX, FL.
- Full top-10-state coverage estimated ~80 days. Acceptable per quality > speed.

### Phase 5 — Monitoring (ongoing)

- Daily check: `worker_state.legiscan_quota_used < 25000`.
- Daily check: `bills.text_fetch_status='done'` count rising.
- Weekly check: `/stats` numbers trending up.
- Alert/manual throttle if quota approaches 28k mid-month.

### Rollback plan

- **Phase 1 migration corrupts data:** downgrade migration; restore from Neon point-in-time backup (7-day PITR on free tier).
- **Phase 2 fetcher misbehaves:** stop scheduler job. Existing data intact (columns added but no fetcher writes). Debug + redeploy.
- **Phase 3 burst hits unexpected API behavior:** existing CO data (text + signatures partially populated) stays in DB, harmless. Investigate API response shape, patch, retry.

### Decision point (end of Phase 3)

- If CO-internal match yields useful signal (≥10 plausible copycat alerts): ship UI changes surfacing "intra-CO model bills" as a distinct category. Discuss positioning copy.
- If signal sparse: continue accumulating. Revisit at end of Phase 4 when top-5 states are filled in.

---

## Open questions (resolved during brainstorm)

| Question | Answer |
|---|---|
| Free or paid LegiScan? | Free only |
| Storage strategy? | **Measure first** (Phase 2.5 gate); pre-committed remediations: snippet-only / paid Neon / object storage |
| Burst remaining May quota? | Yes — burn it on CO (after Phase 2.5 sample of 100) |
| Quota tracking source? | Worker-side adaptive counter, not API headers |
| Burst priority order? | CO-first, then alphabetical (CA/NY/IL/TX/FL elevated) |
| Daily improvement cadence? | Yes — fetch + match every 24h, site evolves continuously |
| Reuse existing 802k bills? | Yes — all rows kept, fetcher walks inventory via UPDATE |
| Discard or keep text for non-CO? | Keep, conditional on storage gate; fall back to snippet-only if needed |
| Match frequency? | After every fetch batch, not just nightly |
| New `match_type` distinction? | Yes — `co_internal` vs `cross_state` |
| Retry behavior for failed fetches? | 3-strike rule via `text_fetch_attempts`; mark `skipped` after threshold |
| Transaction boundaries? | One transaction per bill: API result write + signature upsert + quota increment, all atomic |

---

## Risks

1. **LegiScan changes `getBillText` response shape.** Mitigation: integration test in CI catches drift on next PR.
2. **Quota counter drift** if commit/increment order is wrong and a crash leaves DB inconsistent. Mitigation: single transaction per bill containing the API-result write + signature upsert + quota increment. Spec section "Behavior" step 4 enforces this. Crash anywhere = full rollback, counter stays accurate.
3. **Postgres storage overrun — HARD BLOCKER, not deferred.** Neon free tier is 0.5GB. Raw text estimate is 1.2GB; Postgres TOAST pglz compression likely brings real cost to 300-500MB, but that's unverified. Managed-tier overrun causes immediate INSERT/UPDATE failures, which corrupts `text_fetch_status` mid-batch. **Mitigation:** Phase 2.5 measurement gate (in rollout plan) blocks Phase 3 until projected storage is verified against tier limit, with three pre-committed remediations: (a) snippet-only storage, (b) Neon paid tier, (c) object storage. Not optional.
4. **Burst depletes quota before Phase 2.5 finishes measurement.** Phase 2.5 spends ~100 calls. If LegiScan response shape is wrong on first call, those 100 still count against May quota. Mitigation: integration test (`test_legiscan_getBillText_real.py`) runs in CI before deploy — catches shape drift for free (1 call/CI run).
5. **Permanent-failure bills keep burning quota.** Mitigation: 3-strike `text_fetch_attempts` budget. After 3 failures, bill marked `skipped` and dropped from queue permanently. Operator can manually reset if a fix lands upstream.
6. **CO-internal matches may be uninteresting** (mostly boilerplate). Mitigation: surface match diff snippets prominently so users can judge for themselves; tune Jaccard threshold per `match_type` if needed.
7. **`fetch_bill_texts` is sequential** — one API call per loop iteration. 1000 calls/day × ~500ms/call = ~8 min/day of worker activity. Trivial. No concurrency needed.
8. **Zombie `fetching` rows on worker crash.** A worker killed mid-API-call leaves rows stuck at `text_fetch_status='fetching'` (single transaction handles writes, but if status flip is committed before API call, see Behavior step 4 note — status flip is part of the same transaction, no separate commit, so this risk does not materialize). Documented here to lock the design choice.

---

## Out of scope (future work)

- Bulk text alternatives (Open States, state PDFs, web scraping) — only if LegiScan path proves insufficient.
- Multi-state public site (national coverage of the UI). Currently the API filters `is_corpus_only=False` to show only CO. Lifting that is a separate design.
- Storage compression / object storage migration — own design when Postgres free tier limit hits.
- Concurrent fetcher (`ProcessPoolExecutor` for MinHash) — not needed at current scale.
- Phase B / C / D from `docs/superpowers/plans/2026-05-27-lsh-match-phase.md` — orthogonal to this design.
