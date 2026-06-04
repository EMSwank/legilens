# CLAUDE.md
# **LegiLens: Colorado Project Overview**

## **1\. Project Mission**

To quantify the "Friction Gap" in the Colorado General Assembly by analyzing the discrepancy between legislative rhetoric and administrative/technical reality. LegiLens provides an objective, data-driven lens to evaluate how every bill aligns with technical logic, administrative efficiency, and the "Common Good" (The We-The-People Metric).

## **2\. Core Analysis Modules (Universal Framework)**

### **A. The Signal-to-Noise Processor (SNP)**

* **Method:** Uses NLP to compare the "Bill Vocabulary" (actual text and definitions) against the "Transcript Vocabulary" of speakers.  
* **Metric:** **Topic Adherence Score**. Detects when floor or committee time is diverted for campaign-style grandstanding or non-germane topics, measuring the literal time-cost of performative politics.

### **B. The Administrative Logic Engine (ALE)**

* **Method:** A RAG (Retrieval-Augmented Generation) system holding "Reality Baselines" (Colorado Revised Statutes, agency SOPs, and technical standards like POSIX/NIST).  
* **Metric:** **Reality Mismatch Flag**. Triggered when a legislator makes a claim that contradicts physics, geography, established administrative protocol, or technical architecture.

### **C. The Common Good Evaluator (CGE)**

* **Method:** Analyzes the distribution of a bill's financial and social impact across the general population.  
* **Metric:** **Utility Weighting**.  
  * **Fee-Shifting Detection:** Identifies bills that use flat fees (regressive) to avoid the political friction of graduated taxes (progressive).  
  * **Extraction Analysis:** Highlights tax credits or carve-outs that benefit narrow special interests while depleting the General Fund for schools and public infrastructure.

### **D. The Influence & Source Tracker (IST)**

* **Method:** Uses **Text Reuse Detection** (min-hashing or Smith-Waterman algorithms) to compare Colorado bill text against a national database of 50-state legislation and known "Model Bills."  
* **Metric:** **Source Authenticity Score**.  
  * **"Copycat" Alert:** Triggered when a bill shares \>70% identical language with bills introduced in other states or model templates.  
  * **Dark Money Correlation:** Cross-references "Copycat" bills with campaign contribution data to identify high-probability "pay-to-play" legislation.

## **3\. Universal Friction & Fairness Tags**

| Tag | Definition | Global Application |
| :---- | :---- | :---- |
| **Technical Conflict** | Mandates that break existing technical standards or architecture. | Any bill regulating software, encryption, or digital platforms. |
| **Spatial Inconsistency** | Proposals that are geographically or logistically impossible. | Land use, buffer zones, or infrastructure mandates. |
| **Expert Defiance** | Disregarding non-partisan expert testimony for "intuitive" logic. | Ignoring ALJs, agency heads, or scientists during hearings. |
| **Regressive Burden** | Using flat fees to fund public goods, impacting the majority. | New "enterprise" fees or delivery surcharges. |
| **Source-Cloned** | Identical to model legislation or bills in 5+ other states. | Indicates imported special-interest agendas over local needs. |
| **Legal Hallucination** | Citing inapplicable legal theories to create delay or obstruction. | Frivolous constitutional or contract law claims. |

## **4\. Visualizations**

* **The "Taxpayer Burden" Shift:** A longitudinal chart showing the growth of fees vs. taxes, illustrating the "hidden" cost of political expediency.  
* **The "Expert-to-Amateur" Ratio:** Compares time given to verified experts versus time taken by representatives to rebut them with non-factual anecdotes.  
* **The "Influence Map":** A visual network showing how identical language travels from national think tanks into the Colorado House floor.

## **5\. Current Implementation Status**

| Sprint | Scope | Status |
| :---- | :---- | :---- |
| Sprint 1 | LegiScan ingestion, MinHash LSH pipeline, nightly worker, Postgres schema | ✅ Merged to main |
| Sprint 2 | FastAPI read-only API, Pydantic v2 schemas, rate limiting, 56 tests | ✅ Merged to main |
| Sprint 3 | Next.js 16 frontend, WCAG 2.1 AA, TanStack Query, Playwright E2E | ✅ Merged to main |
| Sprint 4 | Railway/Vercel deploy config, sessions endpoint, tag_type filter, /about + /accessibility + /tags pages, dashboard session dropdown + filter chips | ✅ Merged to main (PRs #12–#16) |
| Post-MVP | Ingest hardening: Postgres-backed dataset dedup (PR #35), API-key redaction in logs (PRs #36–#37), local ZIP cache + hash.md5 manifest enforcement (PR #39). Worker Railway Volume mounted at `/data/zip_cache` with `LEGISCAN_ZIP_CACHE_DIR` env var. | ✅ Merged to main |
| Bootstrap & resilience | Fresh DB session per dataset (PR #41), CO-first two-pass bootstrap so live site shows data within minutes (PR #42), Postgres-backed bootstrap debounce with single `getDatasetList` per run (PR #43), server-side `state="CO"` filter for pass=1 (PR #44). | ✅ Merged to main |
| Match-phase perf & schema | LSH-backed sublinear match phase via `CorpusIndex` wrapper around `MinHashLSH` (PR #45), defenses against duplicate `MinHashSignature` rows (`DISTINCT ON` query + `CorpusIndex.add` guard, PR #46), root-fix `UNIQUE` constraint on `minhash_signatures.bill_id` with Postgres upsert in `_process_bill` (Alembic 004, PR #48). | ✅ Merged to main |
| Intra-CO Related Bills (WS1) | Two-pass `match_co_bills`: cross-state pass writes `ISTScore` + cross_state `SimilarityMatch`; new CO-internal pass writes co_internal `SimilarityMatch` **only** (honesty guard — never `ISTScore`). Surfaces ≥70% text reuse between *distinct* CO bills (companions + reintroductions) as a "Related Colorado Bills" panel on bill detail, a "Related" badge in the dashboard list, and a `related_co_bills` stat. Zero migrations — `has_related` / `matched_bill_number` / `matched_bill_title` are join-derived at read time (PR #60). | ✅ Merged to main |
| Coverage Tracker (WS3) | `/coverage` page makes the corpus build visible: per-state ingest status + a headline "matchable %" scoped to CO + 5 comparison states. Nightly worker writes a per-state `{fetchable, with_sig}` snapshot (JSON in `worker_state`); read-only `GET /coverage` derives statuses + scoped %; accessible table + dashboard nav link. Counting is pure-Python (mock-only suite + PG-locked models block a testable SQL `GROUP BY`); read uses `EXISTS` (no join fan-out); `with_sig` AND-gated on `text_doc_id`. Zero migrations (PR #62). | ✅ Merged to main |

## **6\. Architecture**

```
LegiScan API → backend/worker/ → Neon Postgres → backend/app/ (FastAPI) → frontend/ (Next.js)
```

### Backend (Sprints 1 + 2)

**Key files:**
- `backend/app/main.py` — FastAPI app, GZip + CORS + slowapi middleware
- `backend/app/dependencies.py` — async DB session (rollback on exception), User-Agent guard
- `backend/app/routers/` — bills, matches, tags, stats, coverage
- `backend/app/schemas/` — Pydantic v2: bill.py, match.py (discriminated union), stats.py, coverage.py
- `backend/app/models/` — SQLAlchemy ORM: Bill, ISTScore, FrictionTag, SimilarityMatch
- `backend/worker/tasks/evidence.py` — snippet extraction worker; ghost state when source text unavailable
- `backend/worker/scheduler.py` — apscheduler entry point; nightly cron + cold-start bootstrap; runs the two-pass pipeline (see below)
- `backend/worker/tasks/ingest.py` — LegiScan dataset sync, MinHash computation, ZIP cache + hash.md5 manifest verification; `only_state=` param filters to one state for the CO-first bootstrap pass
- `backend/worker/tasks/match.py` — two-pass Jaccard similarity match. Pass 1 (`_find_matches_for_bill`) scores each CO bill against the cross-state corpus, writing `ISTScore` + cross_state `SimilarityMatch`. Pass 2 (`_find_co_internal_matches`) scores CO bills against each other, writing co_internal `SimilarityMatch` **only** — never `ISTScore` (honesty guard). CO `ISTScore` + `SimilarityMatch` rows (both match_types) are deleted at the top of every run for idempotency
- `backend/worker/tasks/coverage.py` — nightly coverage snapshot: EXISTS-based boolean-per-bill read, pure-Python aggregate, upsert JSON into `worker_state` (key `coverage_snapshot`); hooked into `fetch_and_match`
- `backend/app/services/coverage.py` — pure coverage helpers (aggregate / derive status / scoped matchable %); `SCOPE` = CO + 5 comparison states, kept in sync with `queue._STATE_PRIORITY`
- `backend/tests/` — pytest-asyncio suite (183 tests), all API tests using `dependency_overrides` (not patch); worker tests use `unittest.mock.patch`

**Design decisions to remember:**
- `GhostMessage` is synthesized by the router at read time — never stored in DB. `snippet_status == "source_verified_text_missing"` + `matched_snippets IS NULL` → ghost response.
- Snippet dicts stored in DB include `kind: "snippet"` for Pydantic v2 discriminated union deserialization.
- `BillDetail` is constructed manually in the route handler (no `from_attributes`); `ISTScoreOut` and `FrictionTagOut` use `from_attributes = True`.
- `db.execute()` is async; `.scalars()`, `.scalar()`, `.all()`, `scalar_one_or_none()` are sync.
- `list_bills` and `search_bills` outerjoin `ISTScore` so `copycat_alert` propagates to list views.
- Dataset dedup truth lives in the `dataset_hashes` Postgres table (PR #35). The worker also caches each ZIP at `$LEGISCAN_ZIP_CACHE_DIR/<session_id>.zip` and reads `hash.md5` inside to (a) seed the DB row on cold start without an extra `getDataset` call and (b) refuse to ingest a fresh ZIP whose internal manifest disagrees with the API `dataset_hash` (PR #39). Prod requires a persistent volume mounted at the cache path; ephemeral disk silently defeats cross-restart caching.
- `ingest_all_states` opens a fresh `async_session` per dataset (PR #41) — Neon drops idle connections during the sync `_parse_dataset_zip` phase, which would hang the next `session.execute`.
- Cold-start pipeline is two-pass (PR #42): pass 1 ingests CO only so the live site shows data within minutes; pass 2 ingests the remaining 49 states and runs match + evidence against the full corpus. `match_co_bills` deletes existing CO `ISTScore`/`SimilarityMatch` rows at entry to stay idempotent across nightly + bootstrap reruns.
- `run_full_pipeline` calls `getDatasetList` exactly once per run and passes the result into both ingest passes — LegiScan datasets refresh weekly, duplicate calls within a run are pure quota waste.
- Bootstrap debounce lives in the Postgres `worker_state` table (TTL 7 days), not Redis. Redis is ephemeral on Railway by default; losing the debounce key is exactly what triggers a full 50-state re-download. PR #35 already moved dataset dedup off Redis for the same reason.
- `match_co_bills` uses `CorpusIndex` (LSH wrapper) for candidate retrieval — never iterate the full corpus per CO bill. The LSH threshold in `build_lsh()` must be **≤** the match-phase Jaccard cutoff (70%), and `weights=(0.1, 0.9)` biases band/row selection toward recall so candidates are a strict superset of real matches. Setting the LSH threshold equal to the match cutoff with default weights silently drops ~56% of matches at the boundary — verified in `test_corpus_index_recalls_near_threshold_match`.
- `MinHashSignature` has a `UNIQUE(bill_id)` constraint (Alembic 004, PR #48). `_process_bill` writes signatures via `pg_insert(...).on_conflict_do_update(...)` so re-ingest replaces the row instead of stacking duplicates. The `DISTINCT ON (bill_id) ORDER BY computed_at DESC` guard in `_load_co_signatures_for_matching` and the `CorpusIndex.add` dedup guard are now redundant but kept as belt-and-suspenders — remove only in a future cleanup PR with explicit reasoning.
- **WS1 honesty guard (load-bearing, PR #60):** `_find_co_internal_matches` writes co_internal `SimilarityMatch` rows **only** — it never creates or modifies `ISTScore`. `copycat_alert` and the Source Authenticity Score stay derived *exclusively* from the cross-state pass, whose corpus is `is_corpus_only=True` and therefore never contains CO bills. This is what keeps the homepage "Copycat Alerts: 0" literally true. The CO-internal pass applies three guards: self-match skip, companion-noise skip via `_normalize_bill_number` (collapses whitespace + upcases so "HB 1234" / "HB1234" version-dupes don't pair), and the ≥70% Jaccard precision gate. Each unordered pair {A,B} is intentionally written twice (A→B and B→A) so each bill's detail page lists its own related bills — no UNIQUE constraint on the pair.
- WS1 added **zero Alembic migrations**: `related_co_bills` (stats), `has_related` (bills list/detail), and `matched_bill_number` / `matched_bill_title` (matches) are all computed or join-derived at read time. `stats.related_co_bills` counts DISTINCT CO `bill_id` with ≥1 co_internal match; `has_related` is a per-bill `EXISTS` over co_internal matches; the matched number/title come from joining `SimilarityMatch.matched_bill_id` back to `Bill`.
- **WS3 Coverage Tracker (PR #62):** the nightly `fetch_and_match` computes a per-state `{fetchable, with_sig}` snapshot and upserts it as JSON in `worker_state` (key `coverage_snapshot`). Counting is **pure Python** (`app/services/coverage.py`), not a SQL `GROUP BY`, because the test suite is mock-only and the models are Postgres-locked (`postgresql.UUID` / `ARRAY` / `JSONB`) — so the hazard logic must be unit-testable with no DB. The read emits one boolean-per-bill row via `EXISTS` (never a join → duplicate signature rows can't fan-out double-count `fetchable`); `with_sig` is AND-gated on `text_doc_id IS NOT NULL` so a signature on a doc-less bill can't push the matchable ratio above 1. `as_of` is read from `worker_state.updated_at`, set **explicitly** in the upsert `set_=` (the model's `onupdate=func.now()` does not fire on the `on_conflict_do_update` path). The headline matchable-% denominator is scoped to `SCOPE` (CO + 5 comparison states), which mirrors `queue._STATE_PRIORITY`. The snapshot call is wrapped in try/except so it can never break the cron, and runs even on 0-fetch nights. Zero migrations.

### Frontend (Sprints 3 + 4)

**Key files:**
- `frontend/app/page.tsx` — dashboard: stats grid (incl. "CO Bills with Related Text" / `related_co_bills`), debounced search, SessionDropdown, FilterChips, bill list with `aria-live` + amber "Related" badge when `has_related`; filter state in URL params only; header links to `/coverage`
- `frontend/app/bills/[id]/page.tsx` — bill detail: IST gauge, friction tags, cross_state match cards, and a separate "Related Colorado Bills" panel (co_internal matches, rendered only when ≥1 exists) carrying the copycat-exclusion disclaimer
- `frontend/app/about/page.tsx` — methodology page with ShingleDiagram SVG; includes the "Related Colorado Bills" section explaining co_internal matches are never a copycat alert
- `frontend/app/accessibility/page.tsx` — WCAG 2.1 AA accessibility statement
- `frontend/app/tags/page.tsx` — friction tag browser; each tag card links to `/?tag_type=<slug>`
- `frontend/app/coverage/page.tsx` — corpus coverage tracker: headline scoped matchable %, accessible per-state status table (inline status dots), pending/loading/error states; linked from the dashboard header
- `frontend/components/` — ISTScoreGauge, MatchCard, RelatedBillCard, SnippetDiff, GhostAlert, TagBadge, CopyButton, SearchInput, PendingBanner, SessionDropdown, FilterChips, ShingleDiagram, BillHeader, BillSidebar, ProgressBar, Providers
- `frontend/lib/api.ts` — typed fetch client, `NEXT_PUBLIC_API_URL` base; exports `bills()`, `searchBills()`, `tags()`, `sessions()`, `stats()`, `coverage()`
- `frontend/lib/types.ts` — TypeScript interfaces mirroring Pydantic schemas; includes `TagCount`, `Coverage`
- `frontend/e2e/` — 6 spec files (dashboard, bill-detail, about, tags, filters, coverage); Playwright + @axe-core/playwright
- `frontend/__tests__/` — 92 jest-axe unit tests across 19 test files

**Design decisions to remember:**
- `MatchCard` renders ghost/pending/verified states by inspecting `snippet_status`, not `matched_snippets` contents.
- Bill detail splits matches by `match_type`: `cross_state` → `MatchCard` (under "Similarity Matches"), `co_internal` → `RelatedBillCard` (under "Related Colorado Bills", shown only when ≥1 exists). The Related panel carries an inline "never counted as a copycat alert" disclaimer mirroring the backend honesty guard.
- `RelatedBillCard` links to the matched CO bill and shows "{score}% shared text" with an amber accent — deliberately distinct from the red copycat `TagBadge` so related bills never read as a copycat signal.
- `/coverage` renders the accessible per-state table as the source of truth (status shown as text, not color alone); the inline status dots are `aria-hidden` decoration. The headline matchable % is scoped to CO + 5 comparison states and labeled as such; the `pending` cold-start state and a `null` matchable % are handled distinctly from each other.
- Error boundaries use Next.js 16 `unstable_retry` (not `reset`). `global-error.tsx` must include `<html>/<body>` tags.
- `SearchInput` uses `isFirstRender` ref to prevent mount-time router push.
- Playwright `webServer`: `npm run build && npm run start` locally; `npm run start` in CI (build step precedes E2E step).
- `FilterChips` is hidden when search is active (`q.length >= 2`) — search bypasses session/tag_type filters in the API, so showing stale chips would misrepresent result state.
- `updateParam()` in dashboard preserves all existing URL params when adding/removing individual filters.
- Bills list uses `<ul aria-live="polite">` wrapping both the list and empty/loading states so filter transitions announce to screen readers.

Always invoke the using-superpowers skill at the start of a session.