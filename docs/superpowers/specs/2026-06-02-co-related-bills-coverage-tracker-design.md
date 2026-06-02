# Design — CO Pivot: Related Bills, Coverage Tracker, Cron Un-gate

**Date:** 2026-06-02
**Status:** Approved design, ready for implementation planning
**Branch (spec):** `docs/related-bills-and-coverage-spec`

---

## 1. Context & Motivation

LegiScan's core advertised module is the **Influence & Source Tracker (IST)** — cross-state
"copycat" detection: a CO bill that shares ≥70% text with bills in other states (imported
model legislation / dark-money agendas). Today the live site shows **`copycat_alerts = 0`**
because the corpus has almost no cross-state MinHash signatures (only ~1000 of ~1M ingested
bills have signatures; CO has ~4000 from the per-bill text fetch).

### De-risk verdict (2026-06-01/02, ~31 LegiScan quota spent, read-only DB)

We tested whether cross-state copycat is a viable **week-one** deliverable:

- Loaded the ~4000 CO MinHash signatures already in the DB.
- Title-matched CO bills against FL / TX / AZ dataset ZIPs (0-quota metadata), fetched the
  most-distinctive title-matched candidates, MinHash-compared them to CO sigs in memory.
- **Result: 2 candidates total across FL/TX/AZ, both unfetchable. No ≥70% cross-state pair found.**

**Interpretation (important — not a clean negative):** Colorado uses a distinctive long-title
convention ("Concerning the creation of …, and, in connection therewith, …") that almost never
matches other states' title formats *verbatim*, even when policy is genuinely imported. So
exact-title matching — the only **cheap** mechanism to *target* which cross-state bills to
fetch — finds essentially nothing for CO. **There is no cheap targeting path.** Without it,
populating cross-state copycat means draining the full ~302k-bill non-CO fetch queue blind
(~11 months at the 27k/mo quota, multi-GB, ongoing cost) for a payoff the probe gives zero
evidence exists. **Cross-state copycat is therefore not the week-one deliverable.**

### What we ship instead (this pivot)

1. **Intra-CO Related Bills** — surface text reuse *between distinct Colorado bills*
   (companion bills + reintroductions). Real data already in the DB (0 quota). This is the
   week-one deliverable: real results on the page.
2. **Coverage Tracker** — a `/coverage` page that makes the slow corpus build *visible*
   (per-state status, % of the target corpus that is matchable). Turns the quota constraint
   into transparency.
3. **Un-gate the cron** to **CO → top-5 states**, then reassess — a measured, reversible bet
   on cross-state copycat, with progress shown by the coverage tracker. If real cross-state
   copycats appear, widen to all 50; if not, stop at ~2 months instead of ~11.

### Intra-CO signal — verified real (re-run 2026-06-02 over 3999 CO sigs)

- **93 candidate pairs ≥70%; 92 with distinct bill numbers; 125 CO bills** have ≥1 distinct-number match.
- Examples: "Prohibit Discrimination Labor Union Participation" filed 4× across sessions
  (SB024 / SB113 / HB1098 / HB1106, 93–98%); "Ban Sex-selection Abortions" reintroduced (95%);
  "Regulatory Reform Act 2015" House+Senate companions (94%).
- Signal = companion bills (same session, both chambers) + reintroductions (same policy across
  years). Both are genuine text reuse. **This is NOT cross-state copycat and must never be
  presented as such.**

---

## 2. Verified Codebase Facts (read this session — trust these in a cold start)

These were re-verified against the working tree on 2026-06-02 and **correct two errors from the
prior session's compaction summary**. The new build session should rely on these, not on memory.

- **`backend/worker/tasks/match.py`**
  - `match_co_bills()` deletes prior CO `SimilarityMatch` + `ISTScore` rows at entry (CO = `is_corpus_only=False`), then rebuilds — **idempotent** across nightly + bootstrap reruns.
  - The cross-state corpus index (`CorpusIndex`, an LSH wrapper) is built **only** from `is_corpus_only=True` bills (line ~93). CO bills are `is_corpus_only=False`, so **CO-vs-CO matching is unreachable today**.
  - `_find_matches_for_bill()` sets `match_type = "co_internal" if corpus_state == "CO" else "cross_state"` (line ~156) — forward-looking scaffolding, currently dead because the corpus index never contains CO bills.
  - **CRITICAL:** `copycat_alert` (line ~165) is `authenticity < 30`, i.e. derived from `max_similarity` over **all** candidate matches. Naïvely adding CO bills to the corpus index would make CO-vs-CO matches **flip `copycat_alert = True`**, violating the honesty guard. → WS1 must NOT reuse the cross-state path for CO-internal matches.
- **`backend/app/models/similarity_match.py`** — `match_type` column **already exists**: `String(16), nullable=False, default="cross_state", server_default="cross_state"`. **No migration needed for this column.** Model also has `matched_bill_title`, `matched_bill_url`, `matched_snippets`, `snippet_status`, `algorithm`, `matched_state`.
- **`backend/app/schemas/match.py`** — `MatchOut` has **no `match_type` field** (the discriminated union there is Snippet-vs-Ghost, unrelated). → WS1 must add `match_type` to `MatchOut`.
- **`backend/app/routers/matches.py`** — `GET /bills/{bill_id}/matches` returns `list[MatchOut]` for **all** of a bill's `SimilarityMatch` rows, mixed, with no type split.
- **`backend/app/routers/bills.py`** — `BillDetail` (`GET /bills/{id}`) does **not** query `SimilarityMatch`; matches come only from the separate `/matches` endpoint.
- **`backend/app/schemas/bill.py`** — `BillDetail` fields: id, bill_number, title, description, state, session, status, sponsors, ist_score, tags. No matches field.
- **`backend/app/routers/stats.py`** — `/stats` returns `total_co_bills` (count `is_corpus_only=False`), `copycat_alerts` (`ISTScore.copycat_alert=True` count), `bills_analyzed` (`ISTScore` count).
- **`backend/worker/queue.py`** — `next_queued_bills()` filters `text_fetch_status='queued'`, `full_text IS NULL`, `attempts<3`, `text_doc_id IS NOT NULL`, orders by `_STATE_PRIORITY` (CO=0; CA/NY/IL/TX/FL=1; rest=2). **No `is_corpus_only` filter** → corpus bills are already fetch-eligible. `priority_state` param filters to one state.
- **`backend/worker/tasks/fetch_bill_texts.py`** — `_fetch_one()` success path writes `full_text`, sets `text_fetch_status='done'`, and upserts a `MinHashSignature` **with no `is_corpus_only` gate**. → Fetching a corpus bill produces a signature exactly like a CO bill. This is the unblock that makes WS2 free of new fetch/signature code.
- **`backend/worker/scheduler.py`** — `fetch_and_match()` currently calls `fetch_bill_texts(batch_size=1000, priority_state="CO")` (PR #58 gate). Daily 04:00 UTC cron.
- **`backend/tests/test_match.py:232`** — `test_match_type_is_co_internal_when_corpus_state_is_co` already exists (exercises the dead co_internal branch by forcing a CO corpus_state).
- **Data model fields used:** `bills.state`, `bills.is_corpus_only`, `bills.text_fetch_status`, `bills.text_doc_id`, `bills.full_text`, `bills.bill_number`, `bills.session`; `minhash_signatures.bill_id`, `.signature`, `.computed_at`.
- **Infra:** Neon upgraded to **Launch** (usage-based, ~$2–4/mo; storage wall resolved). Worker on Railway with a persistent volume at `LEGISCAN_ZIP_CACHE_DIR`.

---

## 3. WS1 — Intra-CO Related Bills  (week-one deliverable, 0 quota)

### Goal
Surface ≥70% text reuse between **distinct** CO bills as a "Related Colorado Bills" feature,
kept rigorously separate from cross-state `copycat_alert`.

### Backend — new CO-internal match pass (`match.py`)
Add a **separate** CO-internal pass, run inside `match_co_bills()` after the existing
cross-state scoring loop (so the entry-delete keeps everything idempotent):

1. Build a **second** `CorpusIndex` from **CO bills** (`is_corpus_only=False`, `state='CO'`,
   newest signature per bill via the same `DISTINCT ON (bill_id) ORDER BY computed_at DESC`
   guard already used for the corpus/CO loads).
2. For each CO bill, `query()` the CO index. For each candidate with `similarity ≥ 70`:
   - **Self-guard:** skip if `candidate.bill_id == co_bill.id`.
   - **Companion-noise guard:** skip if normalized `bill_number` is identical (drops version/
     session duplicates of one bill — the 1 noise pair in the probe; keeps the 92 real).
   - Write a `SimilarityMatch` with `match_type='co_internal'`, `matched_bill_id`,
     `matched_state='CO'`, `matched_bill_title`, `similarity_score`, `snippet_status='pending'`.
3. **Honesty guard (non-negotiable):** the CO-internal pass writes `SimilarityMatch` rows
   **only**. It does **not** create or modify `ISTScore`. `copycat_alert` continues to be
   computed solely in `_find_matches_for_bill()` from the cross-state corpus index (which never
   contains CO bills). Result: `copycat_alert` stays cross-state-only and the homepage
   "Copycat Alerts" stat stays truthfully 0 until real cross-state matches land.

Avoid double-counting: each unordered CO pair {A,B} will be found twice (A→B and B→A). That is
acceptable — each bill's detail page shows its own related bills. (If dedup is later desired,
store both directions and let the per-bill query naturally show the relevant direction.)

### API
- `schemas/match.py`: add `match_type: Literal["cross_state", "co_internal"]` to `MatchOut`.
- `routers/matches.py`: include `match_type=m.match_type` in the `MatchOut` construction.
  The endpoint keeps returning all matches; the frontend groups by `match_type`.
- (Decision A, chosen) Expose via the **existing** `/bills/{id}/matches` endpoint + `match_type`
  field, rather than a new `/related` endpoint — minimal surface, frontend groups.

### Stats / homepage visibility  (advisor flag — put a result on the LANDING page)
- `routers/stats.py` + `schemas/stats.py`: add `related_co_bills: int` = count of **distinct
  CO bills** that have ≥1 `co_internal` `SimilarityMatch`.
- Frontend dashboard: add a stat card "CO Bills with Related Text" → `related_co_bills` (≈125).
  This puts a real, non-zero, honestly-labeled result on the landing page (the "Copycat Alerts:
  0" card stays, truthful). Distinct wording from copycat.

### Frontend
- `/bills/[id]`: new "Related Colorado Bills" panel rendering the `co_internal` matches (number,
  title, link to that bill, similarity %). Honest copy: "shares substantial text with" — NOT
  "copied from." Separate visually from the existing cross-state `MatchCard` section.
- Dashboard bill list: small "Related" badge on the ≈125 bills with a `co_internal` match
  (parallel to the existing copycat `TagBadge`), so results are visible without drilling in.
- `lib/types.ts` / `lib/api.ts`: add `match_type` to the match type; add `related_co_bills` to stats.
- `/about`: a sentence distinguishing intra-CO related bills (companions/reintroductions) from
  cross-state copycat. Honesty is core to the product.

### Snippets (scoped)
Both bills in a `co_internal` pair are CO and have `full_text`, so the existing evidence/snippet
worker *can* extract shared passages. **MVP: render related bills with similarity % only**
(snippet_status='pending', no snippet rendering required). Snippet extraction for co_internal
matches is an explicit **enhancement**, not in the WS1 MVP.

### Tests
- Worker: CO-internal pass finds distinct-number ≥70% pairs; self-guard excludes same bill_id;
  companion-noise guard excludes identical bill_number; **`copycat_alert` is NOT set by
  co_internal matches** (the load-bearing honesty test).
- API: `MatchOut.match_type` round-trips; `/matches` returns both types distinguishably.
- Stats: `related_co_bills` counts distinct CO bills, not match rows.
- Frontend: jest-axe on the new panel + badge; Playwright covers a bill with related bills.

---

## 4. WS2 — Un-gate the cron to CO → top-5  (measured, reversible)

### Goal
Let the corpus accrue cross-state signatures over time, bounded to CO + the top-5 states
(~50k bills, ~2 months), then reassess. (User decision: "CO → top-5, then reassess.")

### Design
- `queue.py`: add a `max_priority_tier: int | None` param to `next_queued_bills()`. The state
  priority is already `CO=0`, top-5=`1`, rest=`2`. When `max_priority_tier=1`, add a filter so
  only tiers ≤ 1 (CO + top-5) are returned. Implement by reusing the existing `case()` priority
  expression in a `.where(priority_expr <= max_priority_tier)`.
- `scheduler.py`: change `fetch_and_match()` from `priority_state="CO"` to
  `fetch_bill_texts(batch_size=1000, max_priority_tier=1)`. Update the gate docstring: the PR #58
  comment said remove the CO gate "only with an explicit decision to fund a non-CO fetch" — that
  decision is now made and bounded to top-5; cite this spec.
- No new fetch/signature code: each fetched corpus bill auto-gets a signature (verified §2). Once
  cross-state sigs exist, `match_co_bills` surfaces real cross-state `copycat_alert`s with no
  further change.
- Self-limiting: `QUOTA_HARD_LIMIT=27_000/mo` already caps monthly burn. Storage on Neon Launch.
- **Reassess trigger:** when CO + top-5 reach ~complete on the coverage tracker, evaluate
  whether any real cross-state `copycat_alert`s appeared. If yes → plan widening to all 50. If
  no → stop (do not relax `max_priority_tier`). Document the reassessment in a follow-up.

### Tests
- `next_queued_bills(max_priority_tier=1)` returns only CO + top-5 bills, never tier-2 states.
- `fetch_and_match` calls `fetch_bill_texts(batch_size=1000, max_priority_tier=1)` (update the
  existing scheduler test that asserts `priority_state="CO"`).

---

## 5. WS3 — Coverage Tracker  (`/coverage` page)

### Goal
Make the corpus build visible: per-state ingest status + the share of the **target** corpus
that is matchable. (User picks: dedicated `/coverage` page; status dots per state;
single headline metric = % with signatures (matchable).)

### The "matchable %" denominator — PINNED (advisor block)
Headline metric = progress toward the **current ingest goal**, i.e. **scoped to CO + top-5**:

- **Numerator:** in-scope fetchable bills that have a MinHash signature.
- **Denominator:** in-scope fetchable bills = `state ∈ {CO,CA,NY,IL,TX,FL} AND text_doc_id IS NOT NULL`.
- This climbs from current (~CO-only) toward 100% as the WS2 un-gate completes — a coherent
  "% completed" thermometer.
- **Rationale:** a full-corpus denominator (~1M, incl. the 302k tail we are deliberately NOT
  fetching) would top out around a few percent forever and read as broken — contradicting the
  "% completed" the user asked for. The page must label the metric as "of the current target
  corpus (Colorado + 5 comparison states)".

### Per-state status dots (all states on the map)
For each state, from the snapshot: `fetchable = bills with text_doc_id`, `with_sig = bills with
≥1 signature`.
- `complete`: `fetchable > 0 AND with_sig/fetchable ≥ 0.95`
- `in_progress`: `0 < with_sig` and not complete
- `not_started`: `with_sig == 0`
States outside CO+top-5 will read `not_started` (genuinely 0 sigs) — honest. A legend states:
"Current ingest target: Colorado + CA/NY/IL/TX/FL. Remaining states are queued for a later phase."
(Three statuses only — matches the user's pick; no 4th status invented.)

### Backend — snapshot, not live aggregation (advisor: perf)
- The worker computes coverage **at the end of each nightly `fetch_and_match` run**: one
  `GROUP BY state` query over `bills` (with an `EXISTS`/left-join to `minhash_signatures`)
  producing per-state `{fetchable, with_sig}`. Aggregating ~1M rows once/night is fine; doing it
  per page request is not.
- Persist the result as JSON in the existing `worker_state` table (e.g. key `coverage_snapshot`,
  with a UTC timestamp). (Same table already used for quota + bootstrap debounce.)
- `GET /coverage` reads the one snapshot row, derives statuses + scoped matchable %, returns
  per-state list + overall metric + `as_of` timestamp.
- **Cold start (no snapshot yet):** endpoint returns `200` with `status: "pending"` (frontend
  shows "coverage is computing — check back after tonight's run"). The build may optionally seed
  the snapshot once at deploy via a one-off invocation of the snapshot function.

### Frontend
- New `/coverage` page + nav link. US map with a status dot per state (lightweight inline SVG or
  a simple state grid — no heavy map dependency). Headline scoped matchable % (thermometer/number).
- **Accessibility (WCAG 2.1 AA — project requirement):** an accessible data table (State |
  Bills | Matchable % | Status) is the source of truth; the map is a visual enhancement with
  appropriate ARIA / text equivalents. jest-axe unit test + Playwright-axe E2E, matching existing
  patterns.
- `lib/api.ts` + `lib/types.ts`: `coverage()` client + types.

### Tests
- Coverage snapshot computation: per-state counts correct; status thresholds correct;
  scoped denominator excludes tier-2 states and non-fetchable bills.
- `/coverage` endpoint: reads snapshot; pending state when absent.
- Frontend: axe-clean page; table renders from API; pending state renders.

---

## 6. Build Order & Branching

Each workstream is its own `feat/` branch + PR (per the project git workflow). Suggested order:

1. **WS1 — Related bills** (`feat/intra-co-related-bills`): immediate real results.
2. **WS3 — Coverage tracker** (`feat/coverage-tracker`): makes ingest visible.
3. **WS2 — Cron un-gate** (`feat/cron-ungate-top5`): last, so the coverage page shows progress
   from the moment cross-state fetching begins.

This spec (all three) lives on `docs/related-bills-and-coverage-spec`; merge it (or cherry-pick
into the first feature branch) before building so each branch can reference it.

---

## 7. Non-Goals / Out of Scope

- **No cross-state copycat targeting heuristic** (title-match proven ineffective for CO). Cross-
  state copycat depends solely on the WS2 un-gate accruing signatures over time.
- **No full 50-state un-gate** now (bounded to top-5; reassess later).
- **No new pillars** (SNP / ALE / CGE remain unbuilt; only IST exists as code). This pivot does
  not add them.
- **No snippet extraction for co_internal matches in MVP** (enhancement).
- **No homepage map widget** (user chose dedicated `/coverage` page only).
- **Other tracker metrics** (corpus total, quota used, ETA) — user chose matchable-% only.

## 8. Risks / Open Questions

- **Cross-state payoff unverified.** The un-gate may run ~2 months and surface few/no cross-state
  copycats. Mitigation: bounded to top-5 + explicit reassess gate; coverage tracker sets honest
  expectations.
- **Bidirectional co_internal pairs** (A→B and B→A both stored). Accepted for MVP; revisit only
  if it causes confusing UI.
- **Companion-noise guard granularity.** Excluding identical normalized `bill_number` correctly
  drops same-bill version rows, but could also drop the rare *cross-session* reintroduction that
  kept the same number (different bill, different session, same `bill_number`). The probe found
  only 1 same-number pair total, so impact is negligible for MVP. If cross-session same-number
  reintroductions prove valuable, refine the guard to `same bill_number AND same session` at
  build time.
- **Coverage snapshot freshness** is once/night. Acceptable for a slow-moving ingest; the page
  shows `as_of`.
- **CO companion vs reintroduction classification** (same-session-both-chambers vs across-years)
  is not distinguished in MVP — both shown as "related." Could derive from `session` later.
- **Neon spend cap** should be set in the console (user action) now that the cron will fetch
  beyond CO.
