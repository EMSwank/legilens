# LegiLens

**Colorado passes hundreds of bills each session. Most people have no idea where those bills actually come from.**

LegiLens is a public transparency tool that measures the "Friction Gap" in the Colorado General Assembly — the distance between what legislators say they're doing and what the legislation actually does.

---

## What it does

Most legislative analysis tells you *what* a bill does. LegiLens tells you *where it came from* and *who it serves*.

The core question: When a Colorado bill is introduced, is it locally authored, or is it a copy-paste import from a national template written by a lobbying organization?

**The Influence & Source Tracker (IST)** answers that. It computes cross-state text similarity across 50-state legislation using MinHash locality-sensitive hashing (LSH bucketing for sublinear lookup). When a Colorado bill shares >70% identical language with bills introduced in other states, it gets flagged.

That's not an opinion. That's a measurement.

---

## The modules

**IST — Influence & Source Tracker** *(MVP)*
Cross-state text reuse detection. Compares every Colorado bill against the full national LegiScan corpus (all 50 states, hundreds of thousands of bills, refreshed nightly). Produces a Source Authenticity Score (0–100). Below 30 = copycat alert.

*Related Colorado bills* — companion bills and reintroductions that share language with each other *within* Colorado — also surface on each bill's page. They are deliberately never counted as a copycat alert: the Source Authenticity Score is computed only against *other states'* legislation, so a related Colorado bill never moves a bill's score.

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

MVP shipped — deployed on Railway (backend) + Vercel (frontend). Post-MVP modules (SNP, ALE, CGE) are under active development.

| Sprint | Scope | Status |
|--------|-------|--------|
| Sprint 1 | Data ingestion, MinHash pipeline, nightly worker | ✅ Complete |
| Sprint 2 | FastAPI endpoints, Pydantic schemas, rate limiting | ✅ Complete |
| Sprint 3 | Next.js frontend, WCAG 2.1 AA, Playwright E2E | ✅ Complete |
| Sprint 4 | Deployment (Railway + Vercel), /about, /tags, /accessibility, filter chips | ✅ Complete |
| Post-MVP | Ingest hardening: Postgres-backed dataset dedup, API-key log redaction, local ZIP cache with `hash.md5` manifest enforcement (Railway Volume) | ✅ Complete |
| Bootstrap & resilience | Fresh DB session per dataset, CO-first two-pass bootstrap, Postgres-backed bootstrap debounce, server-side state filter for pass=1 | ✅ Complete |
| Match-phase perf & schema | LSH-backed sublinear match (sub-second corpus lookups), `UNIQUE` constraint + Postgres upsert on `minhash_signatures.bill_id` | ✅ Complete |
| Intra-CO Related Bills | Two-pass match: cross-state copycat detection plus a Colorado-internal pass that surfaces companion bills and reintroductions sharing ≥70% text — kept strictly separate from the copycat signal | ✅ Complete |

### Intra-CO Related Bills — what shipped

- Two-pass `match_co_bills`: the existing cross-state pass writes the Source Authenticity Score and copycat alerts; a new Colorado-internal pass surfaces *distinct* CO bills that share ≥70% language with each other (companion bills, reintroductions, thematically related drafts)
- Honesty guard: the Colorado-internal pass writes similarity matches only, never an authenticity score. Copycat alerts and the Source Authenticity Score stay computed *exclusively* from cross-state comparisons — a related Colorado bill never moves a bill's IST score, and "Copycat Alerts: 0" on the dashboard stays literally true
- Surfaced as a "Related Colorado Bills" panel on bill detail pages, a "Related" badge in the dashboard bill list, and a "CO Bills with Related Text" stat — each visually distinct from the copycat alert
- Zero schema migrations: the related-bill count, the per-bill flag, and the matched bill number/title are all derived at read time

### Post-MVP — what shipped

- LegiScan dataset dedup state persisted in Postgres so worker restarts no longer re-download all 50 state archives
- LegiScan API key redacted from all worker log lines (including non-string args), with a loud failure mode when the key is locked
- Worker caches each downloaded ZIP to `/data/zip_cache` on a Railway Volume; on cold start, reads `hash.md5` inside the archive and skips `getDataset` when the manifest matches the API hash; fresh-ZIP manifest mismatch is now a hard error, not a warning
- Worker opens a fresh DB session per dataset so Neon's idle-connection drop during sync ZIP parsing no longer hangs ingestion
- Cold-start pipeline is two-pass: Colorado bills ingest first so the live site shows data within minutes; the remaining 49 states ingest in pass 2 and feed the full-corpus copycat-similarity match
- Bootstrap debounce moved off ephemeral Redis into Postgres (7-day TTL); `getDatasetList` is called exactly once per pipeline run; LegiScan requests now identify the operator via User-Agent so the API team can reach out before locking the key
- Match phase rewritten as an LSH-backed sublinear lookup (`MinHashLSH` with `weights=(0.1, 0.9)` for recall); candidate retrieval is now sub-second per CO bill even at full-corpus scale
- `minhash_signatures.bill_id` enforced `UNIQUE` at the schema level; ingest writes via Postgres upsert (`ON CONFLICT DO UPDATE`) so re-ingest replaces signatures instead of stacking duplicates

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
