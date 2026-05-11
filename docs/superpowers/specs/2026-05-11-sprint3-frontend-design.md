# Sprint 3 Frontend Design — Bill Detail, Search, Playwright E2E

**Date:** 2026-05-11  
**Branch:** feat/frontend  
**Status:** Approved

---

## 1. Scope

Complete Sprint 3 frontend for LegiLens:

1. Bill detail page (`/bills/[id]`)
2. Inline search on dashboard
3. Playwright E2E tests (full coverage, TDD)

---

## 2. File Structure

```
frontend/
  app/
    bills/
      [id]/
        page.tsx              ← bill detail page ("use client")
  components/
    BillHeader.tsx            ← bill number, title, status pill, CO · session
    BillSidebar.tsx           ← IST gauge + tags, PendingBanner when score null
    SearchInput.tsx           ← debounced input, writes ?q= to URL
  __tests__/
    components/
      BillHeader.test.tsx
      BillSidebar.test.tsx
      SearchInput.test.tsx
    pages/
      BillDetail.test.tsx
  e2e/
    dashboard.spec.ts
    bill-detail.spec.ts
  playwright.config.ts
```

---

## 3. Bill Detail Page

### Layout

Two-column at `md:` breakpoint, single-column stack on mobile.

- **Left sidebar** (sticky, 280px): `BillSidebar` — IST gauge + friction tags. Collapses above matches on mobile.
- **Main column**: `BillHeader` → "Similarity Matches" heading → `MatchCard` list.

### Data Fetching

Two parallel `useQuery` calls on mount:

```ts
useQuery(["bill", id], () => api.bill(id))
useQuery(["matches", id], () => api.matches(id))
```

Independent loading states — gauge can render while matches still load.

### Components

**`BillHeader`** — props: `bill: BillDetail`. Renders: mono bill number, title, `CO · {session}`, status pill (blue).

**`BillSidebar`** — props: `istScore: ISTScore | null`, `tags: FrictionTag[]`. Renders:
- `istScore === null` → `PendingBanner` 
- `istScore` present → `ISTScoreGauge` + `TagBadge` list per tag

### States (all covered by TDD)

| State | Behavior |
|---|---|
| Bill query loading | `PendingBanner` in sidebar + skeleton cards in main |
| Bill 404 / API error | Full-page error with back link to `/` |
| `ist_score: null` | `PendingBanner` in sidebar where gauge would be |
| `ist_score` present | `ISTScoreGauge` + `TagBadge` list |
| Matches loading | Skeleton cards (independent from bill query) |
| `snippet_status === "source_verified_text_missing"` | `GhostAlert` inside `MatchCard` |
| `snippet_status === "pending"` | `PendingBanner` inside `MatchCard` |
| No matches | Empty state: "No similarity matches found" |

---

## 4. Dashboard Search

### Behavior

`SearchInput` — controlled input, 300ms debounce, writes `?q=` to URL via `useRouter().push`. Clears param on empty.

Dashboard reads `?q=` via `useSearchParams`. Query switches at `>= 2` chars (matches backend `min_length=2`):

```ts
const q = searchParams.get("q") ?? "";
const { data: bills } = useQuery({
  queryKey: q.length >= 2 ? ["bills", "search", q] : ["bills"],
  queryFn: () => q.length >= 2 ? api.searchBills(q) : api.bills(),
});
```

### States (all covered by TDD)

| State | Behavior |
|---|---|
| Empty / `< 2` chars | Default bills list, no extra fetch |
| `>= 2` chars, loading | `PendingBanner` above list |
| `>= 2` chars, results | Filtered list replaces default |
| `>= 2` chars, no results | "No bills match your search" empty state |
| API error | `GhostAlert` with retry message |

---

## 5. Playwright E2E

### Setup

- Package: `@playwright/test` + `playwright-chromium`
- Config: `frontend/playwright.config.ts`
  - `baseURL: http://localhost:3000`
  - `webServer`: auto-starts `next dev`, waits for port 3000
- All tests use `page.route()` for API interception — no real backend required
- One JSON fixture blob per scenario

### `dashboard.spec.ts`

- Stats grid renders 3 cards with numeric values
- Bills list renders rows with links to `/bills/[id]`
- Copycat badge visible on flagged bills
- Search: type `"privacy"` (>= 2 chars) → list updates to search results
- Search: type 1 char → list unchanged (threshold guard)
- Search: clear input → list resets to default bills
- `/stats` API error → `GhostAlert` visible
- `/bills` API error → `GhostAlert` visible

### `bill-detail.spec.ts`

- Bill header renders bill number, title, status
- IST gauge has `role="img"` with aria-label containing score
- `copycat_alert: true` → copycat badge visible in sidebar
- Friction tags render in sidebar
- Matches render `MatchCard` list
- Ghost match (`snippet_status: "source_verified_text_missing"`) → `GhostAlert` inside card
- `ist_score: null` → `PendingBanner` in sidebar
- No matches → empty state message
- `/bills/bad-id` → 404 error state

---

## 6. Constraints

- WCAG 2.1 AA: all new components pass `jest-axe` (same pattern as existing components)
- No new dependencies except `@playwright/test` + `playwright-chromium`
- TDD throughout: failing tests written before implementation code
- Follows existing `"use client"` + TanStack Query patterns from `app/page.tsx`
- Next.js 16 / React 19 — read `node_modules/next/dist/docs/` before writing route code
