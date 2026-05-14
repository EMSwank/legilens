# LegiLens

**Colorado passes hundreds of bills each session. Most people have no idea where those bills actually come from.**

LegiLens is a public transparency tool that measures the "Friction Gap" in the Colorado General Assembly — the distance between what legislators say they're doing and what the legislation actually does.

---

## What it does

Most legislative analysis tells you *what* a bill does. LegiLens tells you *where it came from* and *who it serves*.

The core question: When a Colorado bill is introduced, is it locally authored, or is it a copy-paste import from a national template written by a lobbying organization?

**The Influence & Source Tracker (IST)** answers that. It computes cross-state text similarity across 50-state legislation using MinHash locality-sensitive hashing. When a Colorado bill shares >70% identical language with bills introduced in other states, it gets flagged.

That's not an opinion. That's a measurement.

---

## The modules

**IST — Influence & Source Tracker** *(MVP)*
Cross-state text reuse detection. Compares every Colorado bill against a national corpus of 190,000+ bills. Produces a Source Authenticity Score (0–100). Below 30 = copycat alert.

**SNP — Signal-to-Noise Processor** *(coming)*
Measures how much committee and floor time gets spent on the actual bill versus campaign-style grandstanding. Quantifies the time-cost of performative politics.

**ALE — Administrative Logic Engine** *(coming)*
RAG system grounded in Colorado Revised Statutes and agency SOPs. Flags when legislative claims contradict existing law, geography, scientific, or technical standards.

**CGE — Common Good Evaluator** *(coming)*
Analyzes the distribution of a bill's financial impact. Detects fee-shifting (flat fees that hit everyone equally instead of graduated taxes) and tax carve-outs that benefit narrow interests.

---

## Who this is for

- **Journalists** who want to know if the bill they're covering originated in a think tank three states away
- **Researchers** studying model legislation and ALEC-style policy diffusion
- **Engaged citizens** who want a quick read on whether their representative actually wrote the bill they're sponsoring

---

## How it works (technically)

```
LegiScan API → Nightly Worker → Postgres → FastAPI → Next.js
```

- Bill corpus: all 50 states via LegiScan dataset API, synced nightly
- Similarity: 128-permutation MinHash with LSH bucketing (Jaccard threshold 0.70)
- Snippet extraction: difflib SequenceMatcher on confirmed matches, surfaced in the UI with surrounding context
- Stack: Python / FastAPI / asyncpg / Neon Postgres / Redis / Next.js / Vercel

---

## Status

MVP is under active development.

| Sprint | Scope | Status |
|--------|-------|--------|
| Sprint 1 | Data ingestion, MinHash pipeline, nightly worker | ✅ Complete |
| Sprint 2 | FastAPI endpoints, Pydantic schemas, rate limiting | ✅ Complete |
| Sprint 3 | Next.js frontend, WCAG 2.1 AA, Playwright E2E | ✅ Complete |
| Sprint 4 | Deployment (Railway + Vercel), /about, /tags, /accessibility, filter chips | ✅ Complete |

### Sprint 4 — what shipped

- Backend: `GET /bills/sessions` (distinct CO sessions), `tag_type` filter on `GET /bills`, CORS regex for Vercel previews
- Frontend: `/about` methodology page with MinHash proof-of-work (shingling SVG, Jaccard formula), `/tags` browser with counts and descriptions, `/accessibility` statement, dashboard session dropdown, dismissible filter chips
- Deployment: Railway (web + worker services), Vercel (production + preview deploys), alembic migrations folded into web service start
- A11y: `@axe-core/playwright` added to E2E, `frontend/A11Y_CHECKLIST.md` enforces per-PR manual checks

### Sprint 3 — what shipped

- Dashboard: bill list with copycat alert badges, stats grid, 300ms-debounced search with URL sync
- Bill detail: IST score gauge (Recharts radial chart, `role="img"` + `aria-label`), friction tag badges, similarity match cards with side-by-side snippet diffs, journalist copy button, ghost alert for missing source text, pending state banner
- WCAG 2.1 AA throughout: skip link, focus rings, `role="alert"` / `role="status"` on dynamic states, all components pass `axe-core` automated scan
- 42 jest-axe unit tests (TDD on every component), 16 Playwright E2E scenarios (dashboard + bill detail)
- CI: backend pytest, frontend lint/unit/E2E, Pylint — all wired to `pull_request` on main

### Sprint 2 — what shipped

- Read-only FastAPI app: `GET /bills`, `GET /bills/search`, `GET /bills/{id}`, `GET /bills/{id}/matches`, `GET /tags`, `GET /stats`
- Pydantic v2 discriminated union for snippet responses: verified snippets (`kind: "snippet"`) vs. ghost messages (`kind: "ghost"`) when source bill text is unavailable
- Async SQLAlchemy 2.0 with session rollback on exception
- User-Agent guard (400 if missing), GZip + CORS middleware, slowapi rate limiting (60 req/min per IP)
- 56 tests across all API routes

Contributions, issue reports, and methodology critiques are welcome.

---

## Data source

Legislative data provided by [LegiScan](https://legiscan.com). LegiScan aggregates bill text and status for all 50 U.S. states.

---

*LegiLens is not affiliated with the Colorado General Assembly or any political organization.*
