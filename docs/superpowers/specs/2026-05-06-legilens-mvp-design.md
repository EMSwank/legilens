# LegiLens MVP Design Spec

**Date:** 2026-05-06  
**Status:** Approved  
**Scope:** MVP — archive-first, IST module only, public access

---

## 1. Product Goal

Public transparency tool exposing the "Friction Gap" in Colorado General Assembly legislation. MVP focuses on the Influence & Source Tracker (IST) module: detecting copycat bills via cross-state text similarity. Live session analysis is a future paid tier.

**Primary audience:** General public, journalists, researchers.

---

## 2. System Architecture

**Deployment:**
- Frontend: Next.js → Vercel
- Backend API: FastAPI → Fly.io
- Database: Neon (managed Postgres)
- Cache: Redis (Fly.io or Upstash)
- Background worker: Python → Fly.io (separate machine)

**Data flow:**
```
LegiScan API → Fly Worker → Neon Postgres → FastAPI → Vercel (Next.js) → Browser
```

**Cost at MVP scale:** ~$7/mo (Fly.io VM + free tiers elsewhere)

---

## 3. Data Model

### `bills`
```sql
id                  UUID PRIMARY KEY DEFAULT gen_random_uuid()
legiscan_id         INTEGER UNIQUE NOT NULL   -- sync key only, never FK target
state               CHAR(2) NOT NULL
session             TEXT NOT NULL
bill_number         TEXT NOT NULL
title               TEXT NOT NULL
description         TEXT
full_text           TEXT                      -- NULL for corpus-only bills
sponsors            JSONB
status              TEXT
is_corpus_only      BOOLEAN NOT NULL DEFAULT false
last_updated        TIMESTAMPTZ

-- Indexes
CREATE INDEX ON bills (state, is_corpus_only);
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX ON bills USING GIN (full_text gin_trgm_ops)
  WHERE is_corpus_only = false;             -- CO bills only
```

**Corpus bills** (`is_corpus_only = true`): store only `legiscan_id`, `title`, `state`, `session`, `bill_number`, and `minhash_signature`. No `full_text`. Saves ~9.5GB vs storing all national bill text.

### `minhash_signatures`
```sql
id                  UUID PRIMARY KEY DEFAULT gen_random_uuid()
bill_id             UUID REFERENCES bills(id)
signature           INTEGER[]                 -- 128-band MinHash
computed_at         TIMESTAMPTZ
```

### `ist_scores`
```sql
id                  UUID PRIMARY KEY DEFAULT gen_random_uuid()
bill_id             UUID REFERENCES bills(id)
source_authenticity_score  DECIMAL(5,2)      -- 0.00–100.00; lower = more copied
copycat_alert       BOOLEAN NOT NULL          -- true when score < 30.00
analyzed_at         TIMESTAMPTZ
```

### `similarity_matches`
```sql
id                  UUID PRIMARY KEY DEFAULT gen_random_uuid()
bill_id             UUID REFERENCES bills(id)
matched_bill_id     UUID REFERENCES bills(id)
matched_state       CHAR(2)
similarity_score    DECIMAL(5,2)              -- Jaccard approximation, e.g. 87.42
algorithm           TEXT DEFAULT 'minhash'
matched_bill_title  TEXT
matched_bill_url    TEXT
matched_snippets    JSONB                     -- array of {co, source} string pairs
snippet_status      TEXT NOT NULL CHECK (snippet_status IN (
                      'pending',
                      'verified',
                      'source_verified_text_missing'
                    ))

-- Indexes
CREATE INDEX idx_matches_bill_status
  ON similarity_matches (bill_id, snippet_status);
```

### `friction_tags`
```sql
id                  UUID PRIMARY KEY DEFAULT gen_random_uuid()
bill_id             UUID REFERENCES bills(id)
tag_type            TEXT NOT NULL             -- source_cloned, technical_conflict, etc.
confidence          DECIMAL(4,3)
evidence            TEXT
```

### Scoring logic
- `source_authenticity_score` = `100 - max(similarity_score)` across all matches
- `copycat_alert` = `true` when `source_authenticity_score < 30.00`
- Ghost state: when match confirmed via MinHash but source text unavailable → `snippet_status = 'source_verified_text_missing'`

---

## 4. IST Worker Pipeline

### MinHash parameters (datasketch library)
```python
num_perm = 128       # must match across all bills — never change post-ingest
lsh_threshold = 0.7  # Jaccard threshold; aligns with copycat_alert cutoff (score < 30)
lsh = MinHashLSH(threshold=lsh_threshold, num_perm=num_perm)
```
These values are fixed. Changing `num_perm` invalidates all stored signatures and requires full re-ingest.

### Phase 1 — Ingest (nightly, all states via LegiScan public API)
1. Fetch new/updated bills for all 50 states
2. Tokenize bill text into k-shingles (in-memory)
3. Compute MinHash signature (`num_perm=128`)
4. Store signature + metadata in Postgres
5. Cache compressed text in Redis: `bills:{legiscan_id}:text` → `zlib.compress(text)`, TTL 24h
6. Discard raw text from memory — never persisted for corpus bills

### Phase 2 — Match (triggered after CO bill ingest, LegiScan public API tier)
1. Compute MinHash for incoming CO bill (`num_perm=128`)
2. LSH bucket comparison against 190k+ stored signatures (`threshold=0.7`)
3. Identify candidates with Jaccard similarity > 0.70
4. Write `similarity_matches` rows with `snippet_status = 'pending'`
5. Write `ist_scores` row

### Phase 3 — Evidence (background job, LegiScan Pro API tier, demand-driven)
1. For each pending match:
   - Check Redis for `bills:{legiscan_id}:text`
   - Cache hit: decompress → Python memory
   - Cache miss: LegiScan Pro fetch → zlib compress → cache → Python memory
   - If text unavailable: set `snippet_status = 'source_verified_text_missing'`
2. Run `difflib.SequenceMatcher` on CO text vs corpus text in memory
3. Extract matching blocks > 50 chars; include 1 sentence of surrounding context on each side
4. Store as `{co_context_before, co_match, co_context_after, source_context_before, source_match, source_context_after}`
5. Write `matched_snippets` JSONB + set `snippet_status = 'verified'`

**Snippet JSONB shape:**
```json
{
  "co_context_before": "The legislature finds that...",
  "co_match": "The commission shall establish fees not to exceed...",
  "co_context_after": "Such fees shall be deposited...",
  "source_context_before": "The legislature finds that...",
  "source_match": "The commission shall establish fees not to exceed...",
  "source_context_after": "Such fees shall be deposited..."
}
```
Context sentences prevent snippets feeling clipped when shared. Copy-to-clipboard uses `co_match` + `source_match` only (tight format); full context renders in UI.

**Note:** API never triggers Phase 3. API is read-only over Postgres. Worker owns all LegiScan calls.

---

## 5. API Layer (FastAPI)

### Middleware
```python
app.add_middleware(GZipMiddleware, minimum_size=1000)

# CORS — restrict to Vercel frontend origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://legilens.co", "https://*.vercel.app"],
    allow_methods=["GET"],
    allow_headers=["*"],
)
```

**User-Agent policy:** Requests without a `User-Agent` header return `400 Bad Request`. Enforced via FastAPI dependency on all routes. Blocks naive scrapers; legitimate researchers and browsers always send UA strings.

```python
async def require_user_agent(user_agent: str | None = Header(default=None)):
    if not user_agent:
        raise HTTPException(status_code=400, detail="User-Agent required")
```

### Endpoints
```
GET  /bills                  # paginated CO bills; filters: session, status, tag
GET  /bills/search?q=        # pg_trgm full-text search, CO bills only
GET  /bills/{id}             # bill detail + IST score + friction tags
GET  /bills/{id}/matches     # similarity matches with snippets; always reads DB only
GET  /tags                   # friction tag types + counts
GET  /stats                  # dashboard: bills analyzed, copycat alert count
```

### Response contract — `/bills/{id}`
```json
{
  "id": "uuid",
  "bill_number": "SB-123",
  "title": "...",
  "status": "passed",
  "ist_score": {
    "source_authenticity_score": 12.58,
    "copycat_alert": true,
    "analyzed_at": "2026-05-06T00:00:00Z"
  },
  "tags": [{"type": "source_cloned", "confidence": 0.94}]
}
```

### Response contract — `/bills/{id}/matches`
```json
[
  {
    "matched_bill": "HB-22-1001",
    "matched_state": "TX",
    "similarity_score": 87.42,
    "snippet_status": "verified",
    "matched_snippets": [
      {"co": "The commission shall...", "source": "The commission shall..."}
    ]
  },
  {
    "matched_bill": "SB-21-0042",
    "matched_state": "FL",
    "similarity_score": 74.11,
    "snippet_status": "source_verified_text_missing",
    "matched_snippets": [
      {"message": "Source text unavailable for extraction"}
    ]
  }
]
```

### Validation
- Strict Pydantic models for all responses
- `TypeAdapter(list[SnippetItem | GhostMessage])` for match list validation
- asyncpg + SQLAlchemy 2.0 async — no blocking DB calls
- Rate limiting via `slowapi`
- No auth on MVP; auth layer added with paid tier

---

## 6. Frontend (Next.js)

### Pages
```
/                  Dashboard: stats banner, copycat alert feed, recent bills
/bills             Searchable/filterable bill list, IST score column, tag badges
/bills/[id]        Bill detail: score gauge, match cards, snippet diffs, ghost alerts
/about             Methodology explainer, scoring explanation
```

### Key components

**IST Score Gauge** — 0–100 radial dial. Red (`#EF4444`) below 30 (copycat alert). Single-glance credibility signal.

**Match Card**
```
[TX] HB-22-1001 · 87.42% match
"The commission shall establish..." → "The commission shall establish..."
[Copy to Clipboard]                    ← pre-formatted journalist-ready output
```
Ghost state renders: "Source text unavailable — match verified mathematically."

**Pending status banner** (on `/bills/[id]/matches` while any match is `pending`):
> ⟳ Analyzing Cross-State Evidence... snippets will appear automatically.

**Snippet polling:** TanStack Query polls `/bills/{id}/matches` every 5s while `hasPending`. Stops when all resolved.

**Copy-to-clipboard format:**
```
[CO SB-123] "The commission shall establish fees not to exceed..."
[TX HB-22-1001] "The commission shall establish fees not to exceed..."
Source Authenticity Score: 12.58 — LegiLens.co
```

### Tech stack
- **Tailwind CSS** — utility-first styling
- **Inter variable font** — `next/font/google`, weights 100–900, clinical/authoritative aesthetic
- **Recharts** — IST gauge, future visualizations (Influence Map, Taxpayer Burden)
- **TanStack Query** — data fetching, cache, polling
- **shadcn/ui** — accessible component primitives
- **next-nprogress-bar** — global loading bar (Client Component wrapper to avoid hydration mismatch)
- **Color:** `#EF4444` (red-500) on `#0F172A` (slate-900) = ~4.8:1 contrast ratio, meets WCAG AA

### Navigation loading bar
```typescript
// components/ProgressBar.tsx — 'use client'
<AppProgressBar color="#EF4444" height="3px" options={{ showSpinner: false }} />
```

---

## 7. Git Workflow

- `main` — stable, deployable
- Feature branches: `feat/<topic>`, `fix/<topic>`, `chore/<topic>`, `docs/<topic>`
- Conventional commits throughout
- Never commit directly to `main`

**Planned branch sequence (3 sprints):**
1. `feat/data-ingestion` — LegiScan worker, MinHash pipeline, DB schema
2. `feat/api-layer` — FastAPI endpoints, Pydantic models, asyncpg
3. `feat/frontend` — Next.js pages, components, polling

---

## 8. Out of Scope (MVP)

- SNP, ALE, CGE modules
- Live session analysis / WebSocket
- Auth / paid tier
- Influence Map network visualization
- Campaign contribution cross-reference (Dark Money Correlation)
- OpenStates or direct scraping fallback
