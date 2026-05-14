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

## **6\. Architecture**

```
LegiScan API → backend/worker/ → Neon Postgres → backend/app/ (FastAPI) → frontend/ (Next.js)
```

### Backend (Sprints 1 + 2)

**Key files:**
- `backend/app/main.py` — FastAPI app, GZip + CORS + slowapi middleware
- `backend/app/dependencies.py` — async DB session (rollback on exception), User-Agent guard
- `backend/app/routers/` — bills, matches, tags, stats
- `backend/app/schemas/` — Pydantic v2: bill.py, match.py (discriminated union), stats.py
- `backend/app/models/` — SQLAlchemy ORM: Bill, ISTScore, FrictionTag, SimilarityMatch
- `backend/worker/tasks/evidence.py` — snippet extraction worker; ghost state when source text unavailable
- `backend/worker/tasks/ingest.py` — LegiScan dataset sync, MinHash computation
- `backend/tests/` — 70 pytest-asyncio tests, all using `dependency_overrides` (not patch)

**Design decisions to remember:**
- `GhostMessage` is synthesized by the router at read time — never stored in DB. `snippet_status == "source_verified_text_missing"` + `matched_snippets IS NULL` → ghost response.
- Snippet dicts stored in DB include `kind: "snippet"` for Pydantic v2 discriminated union deserialization.
- `BillDetail` is constructed manually in the route handler (no `from_attributes`); `ISTScoreOut` and `FrictionTagOut` use `from_attributes = True`.
- `db.execute()` is async; `.scalars()`, `.scalar()`, `.all()`, `scalar_one_or_none()` are sync.
- `list_bills` and `search_bills` outerjoin `ISTScore` so `copycat_alert` propagates to list views.

### Frontend (Sprints 3 + 4)

**Key files:**
- `frontend/app/page.tsx` — dashboard: stats grid, debounced search, SessionDropdown, FilterChips, bill list with `aria-live`; filter state in URL params only
- `frontend/app/bills/[id]/page.tsx` — bill detail: IST gauge, friction tags, match cards
- `frontend/app/about/page.tsx` — methodology page with ShingleDiagram SVG
- `frontend/app/accessibility/page.tsx` — WCAG 2.1 AA accessibility statement
- `frontend/app/tags/page.tsx` — friction tag browser; each tag card links to `/?tag_type=<slug>`
- `frontend/components/` — ISTScoreGauge, MatchCard, SnippetDiff, GhostAlert, TagBadge, CopyButton, SearchInput, PendingBanner, SessionDropdown, FilterChips, ShingleDiagram, BillHeader, BillSidebar, ProgressBar, Providers
- `frontend/lib/api.ts` — typed fetch client, `NEXT_PUBLIC_API_URL` base; exports `bills()`, `searchBills()`, `tags()`, `sessions()`, `stats()`
- `frontend/lib/types.ts` — TypeScript interfaces mirroring Pydantic schemas; includes `TagCount`
- `frontend/e2e/` — 5 spec files (dashboard, bill-detail, about, tags, filters); Playwright + @axe-core/playwright
- `frontend/__tests__/` — 81 jest-axe unit tests across 17 test files

**Design decisions to remember:**
- `MatchCard` renders ghost/pending/verified states by inspecting `snippet_status`, not `matched_snippets` contents.
- Error boundaries use Next.js 16 `unstable_retry` (not `reset`). `global-error.tsx` must include `<html>/<body>` tags.
- `SearchInput` uses `isFirstRender` ref to prevent mount-time router push.
- Playwright `webServer`: `npm run build && npm run start` locally; `npm run start` in CI (build step precedes E2E step).
- `FilterChips` is hidden when search is active (`q.length >= 2`) — search bypasses session/tag_type filters in the API, so showing stale chips would misrepresent result state.
- `updateParam()` in dashboard preserves all existing URL params when adding/removing individual filters.
- Bills list uses `<ul aria-live="polite">` wrapping both the list and empty/loading states so filter transitions announce to screen readers.

Always invoke the using-superpowers skill at the start of a session.