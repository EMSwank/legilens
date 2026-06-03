# LegiLens Frontend

Next.js 16 public frontend for the LegiLens Colorado legislative analysis tool.

## Stack

- **Next.js 16** (App Router) + **React 19** + **TypeScript**
- **TanStack Query v5** — data fetching, caching, polling
- **shadcn/ui** + **Tailwind CSS** — UI primitives
- **Recharts** — IST score radial gauge
- **Playwright** — E2E tests
- **jest-axe** — accessibility unit tests (WCAG 2.1 AA)

## Getting Started

```bash
npm install
npm run dev       # dev server at http://localhost:3000
```

Requires the FastAPI backend running (default: `http://localhost:8000`). Override with:

```bash
NEXT_PUBLIC_API_URL=http://your-backend npm run dev
```

## Scripts

```bash
npm run dev       # development server
npm run build     # production build
npm run start     # production server (requires prior build)
npm test          # jest unit tests (87 tests across 18 files)
npm run e2e       # Playwright E2E (5 spec files; requires prior build locally)
npm run lint      # ESLint
```

## Architecture

```
app/
  page.tsx              # dashboard — stats, bill list (+ "Related" badge), search, session dropdown, filter chips
  bills/[id]/page.tsx   # bill detail — IST gauge, cross-state matches, Related Colorado Bills panel, snippets
  about/page.tsx        # methodology page with ShingleDiagram SVG
  tags/page.tsx         # friction tag browser
  accessibility/page.tsx # WCAG 2.1 AA accessibility statement
  layout.tsx            # root layout with skip link + query providers
  global-error.tsx      # root layout error boundary (Next.js 16)
  bills/[id]/error.tsx  # route-level error boundary

components/
  ISTScoreGauge.tsx     # Recharts radial chart, role="img"
  MatchCard.tsx         # cross-state similarity match with snippet diffs
  RelatedBillCard.tsx   # co_internal related-CO-bill link card (amber accent)
  SnippetDiff.tsx       # side-by-side CO vs source text
  GhostAlert.tsx        # "source text unavailable" state
  CopyButton.tsx        # journalist clipboard copy
  SearchInput.tsx       # debounced search with URL sync
  TagBadge.tsx          # friction tag pill
  SessionDropdown.tsx   # CO session filter
  FilterChips.tsx       # dismissible session/tag_type filter chips
  PendingBanner.tsx     # match-phase-not-yet-run state
  ShingleDiagram.tsx    # MinHash shingling proof-of-work SVG (/about)
  BillHeader.tsx        # bill detail title + metadata
  BillSidebar.tsx       # bill detail right rail
  ProgressBar.tsx       # IST score visual
  Providers.tsx         # TanStack Query client provider

lib/
  api.ts                # typed fetch client
  types.ts              # TypeScript interfaces (mirrors backend Pydantic schemas)

__tests__/              # 17 jest-axe unit test files (components/, lib/, pages/)
e2e/                    # 5 Playwright spec files (dashboard, bill-detail, about, tags, filters)
```

## Key design decisions

- Error boundaries use `unstable_retry` (Next.js 16 API). `global-error.tsx` requires `<html>/<body>` tags.
- `MatchCard` renders ghost/pending/verified by checking `snippet_status`, not `matched_snippets` contents.
- `SearchInput` uses `isFirstRender` ref to suppress mount-time router push.
- Playwright `webServer` runs `npm run build && npm run start` locally; CI runs `npm run start` (build step precedes E2E in the workflow).
- Bill detail splits matches by `match_type`: `cross_state` renders as `MatchCard`; `co_internal` renders as `RelatedBillCard` in a separate "Related Colorado Bills" panel. Related Colorado bills are never shown as a copycat signal — that framing mirrors the backend honesty guard (the CO-internal match pass writes similarity matches only, never an IST score).
