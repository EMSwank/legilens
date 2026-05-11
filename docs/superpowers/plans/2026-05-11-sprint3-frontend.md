# Sprint 3 Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete Sprint 3 frontend — bill detail page (`/bills/[id]`), inline dashboard search, and full Playwright E2E coverage with TDD throughout.

**Architecture:** Three tracks executed sequentially: (1) new display components (`BillHeader`, `BillSidebar`, `SearchInput`) built TDD with jest-axe; (2) new bill detail page and updated dashboard using TanStack Query v5 parallel queries; (3) Playwright E2E using `page.route()` interception — no real backend required.

**Tech Stack:** Next.js 16, React 19, TanStack Query v5, Tailwind CSS v4, jest-axe, `@playwright/test`

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `frontend/playwright.config.ts` | Create | Playwright config: chromium, baseURL, webServer auto-start |
| `frontend/components/BillHeader.tsx` | Create | Bill number (mono), title, `CO · session`, status pill |
| `frontend/components/BillSidebar.tsx` | Create | IST gauge + tags, or `PendingBanner` when `ist_score` is null |
| `frontend/components/SearchInput.tsx` | Create | Debounced input, writes `?q=` to URL via `useRouter().push` |
| `frontend/app/bills/[id]/page.tsx` | Create | Bill detail: sidebar + main, two parallel `useQuery` calls |
| `frontend/app/page.tsx` | Modify | Add `SearchInput`, `useSearchParams`, switch query at ≥2 chars, wrap in `Suspense` |
| `frontend/__tests__/components/BillHeader.test.tsx` | Create | axe + renders number/title/status |
| `frontend/__tests__/components/BillSidebar.test.tsx` | Create | axe + null IST → PendingBanner, present IST → gauge + tags |
| `frontend/__tests__/components/SearchInput.test.tsx` | Create | axe + debounce 300ms + URL set/clear |
| `frontend/__tests__/pages/BillDetail.test.tsx` | Create | 9 states: success, error, null-IST, ghost match, pending match, no matches |
| `frontend/e2e/dashboard.spec.ts` | Create | 7 E2E scenarios: stats, bills, copycat, search, errors |
| `frontend/e2e/bill-detail.spec.ts` | Create | 9 E2E scenarios: header, gauge, tags, matches, ghost, 404 |

---

## Task 1: Playwright install and config

**Files:**
- Create: `frontend/playwright.config.ts`
- Modify: `frontend/package.json`

- [ ] **Step 1: Install `@playwright/test` and Chromium browser**

```bash
cd frontend && npm install --save-dev @playwright/test && npx playwright install chromium
```

Expected: `@playwright/test` in `package.json` devDependencies. Chromium downloads to Playwright cache (`~/.cache/ms-playwright`).

- [ ] **Step 2: Create `frontend/playwright.config.ts`**

```typescript
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
  webServer: {
    command: "npm run dev",
    url: "http://localhost:3000",
    reuseExistingServer: !process.env.CI,
  },
});
```

- [ ] **Step 3: Add `e2e` script to `frontend/package.json`**

In the `"scripts"` object, add:

```json
"e2e": "playwright test",
"e2e:ui": "playwright test --ui"
```

- [ ] **Step 4: Commit**

```bash
git add frontend/playwright.config.ts frontend/package.json frontend/package-lock.json
git commit -m "feat(frontend): install Playwright + chromium config"
```

---

## Task 2: `BillHeader` component (TDD)

**Files:**
- Create: `frontend/__tests__/components/BillHeader.test.tsx`
- Create: `frontend/components/BillHeader.tsx`

- [ ] **Step 1: Write the failing tests**

Create `frontend/__tests__/components/BillHeader.test.tsx`:

```typescript
import { render } from "@testing-library/react";
import { axe } from "jest-axe";
import BillHeader from "@/components/BillHeader";
import type { BillDetail } from "@/lib/types";

const bill: BillDetail = {
  id: "00000000-0000-0000-0000-000000000001",
  bill_number: "HB24-1234",
  title: "Concerning Digital Privacy Requirements for State Agencies",
  description: "A privacy bill.",
  state: "CO",
  session: "2024A",
  status: "Introduced",
  sponsors: null,
  ist_score: null,
  tags: [],
};

test("BillHeader has no accessibility violations", async () => {
  const { container } = render(<BillHeader bill={bill} />);
  expect(await axe(container)).toHaveNoViolations();
});

test("BillHeader renders bill number", () => {
  const { getByText } = render(<BillHeader bill={bill} />);
  expect(getByText("HB24-1234")).toBeInTheDocument();
});

test("BillHeader renders title", () => {
  const { getByText } = render(<BillHeader bill={bill} />);
  expect(getByText("Concerning Digital Privacy Requirements for State Agencies")).toBeInTheDocument();
});

test("BillHeader renders state and session", () => {
  const { getByText } = render(<BillHeader bill={bill} />);
  expect(getByText(/CO/)).toBeInTheDocument();
  expect(getByText(/2024A/)).toBeInTheDocument();
});

test("BillHeader renders status pill when status present", () => {
  const { getByText } = render(<BillHeader bill={bill} />);
  expect(getByText("Introduced")).toBeInTheDocument();
});

test("BillHeader omits status pill when status is null", () => {
  const { queryByText } = render(<BillHeader bill={{ ...bill, status: null }} />);
  expect(queryByText("Introduced")).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npx jest __tests__/components/BillHeader.test.tsx --no-coverage
```

Expected: FAIL — `Cannot find module '@/components/BillHeader'`

- [ ] **Step 3: Implement `BillHeader`**

Create `frontend/components/BillHeader.tsx`:

```typescript
import type { BillDetail } from "@/lib/types";

export default function BillHeader({ bill }: { bill: BillDetail }) {
  return (
    <div className="space-y-2">
      <p className="font-mono text-sm text-slate-400">{bill.bill_number}</p>
      <h1 className="text-2xl font-bold text-slate-100">{bill.title}</h1>
      <div className="flex items-center gap-2 text-sm text-slate-400">
        <span>{bill.state}</span>
        <span aria-hidden="true">·</span>
        <span>{bill.session}</span>
        {bill.status && (
          <>
            <span aria-hidden="true">·</span>
            <span className="inline-flex items-center rounded-full bg-blue-900/40 px-2.5 py-0.5 text-xs font-medium text-blue-300 ring-1 ring-inset ring-blue-500/30">
              {bill.status}
            </span>
          </>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend && npx jest __tests__/components/BillHeader.test.tsx --no-coverage
```

Expected: PASS — 6 tests

- [ ] **Step 5: Commit**

```bash
git add frontend/components/BillHeader.tsx frontend/__tests__/components/BillHeader.test.tsx
git commit -m "feat(frontend): BillHeader component with axe TDD"
```

---

## Task 3: `BillSidebar` component (TDD)

**Files:**
- Create: `frontend/__tests__/components/BillSidebar.test.tsx`
- Create: `frontend/components/BillSidebar.tsx`

- [ ] **Step 1: Write the failing tests**

Create `frontend/__tests__/components/BillSidebar.test.tsx`:

```typescript
import { render } from "@testing-library/react";
import { axe } from "jest-axe";
import BillSidebar from "@/components/BillSidebar";
import type { ISTScore, FrictionTag } from "@/lib/types";

jest.mock("recharts", () => ({
  RadialBarChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  RadialBar: () => null,
  PolarAngleAxis: () => null,
}));

const istScore: ISTScore = {
  source_authenticity_score: 73.4,
  copycat_alert: true,
  analyzed_at: "2024-01-15T00:00:00Z",
};

const tags: FrictionTag[] = [
  { tag_type: "source_cloned", confidence: 0.95 },
  { tag_type: "technical_conflict", confidence: 0.7 },
];

test("BillSidebar has no accessibility violations when score present", async () => {
  const { container } = render(<BillSidebar istScore={istScore} tags={tags} />);
  expect(await axe(container)).toHaveNoViolations();
});

test("BillSidebar has no accessibility violations when score null", async () => {
  const { container } = render(<BillSidebar istScore={null} tags={[]} />);
  expect(await axe(container)).toHaveNoViolations();
});

test("BillSidebar renders ISTScoreGauge when score present", () => {
  const { getByRole } = render(<BillSidebar istScore={istScore} tags={tags} />);
  expect(getByRole("img")).toBeInTheDocument();
});

test("BillSidebar renders PendingBanner when ist_score is null", () => {
  const { getByRole } = render(<BillSidebar istScore={null} tags={[]} />);
  expect(getByRole("status")).toBeInTheDocument();
});

test("BillSidebar renders all friction tags", () => {
  const { getByText } = render(<BillSidebar istScore={istScore} tags={tags} />);
  expect(getByText("Source-Cloned")).toBeInTheDocument();
  expect(getByText("Technical Conflict")).toBeInTheDocument();
});

test("BillSidebar renders no tags when tags array is empty", () => {
  const { queryByText } = render(<BillSidebar istScore={istScore} tags={[]} />);
  expect(queryByText("Source-Cloned")).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npx jest __tests__/components/BillSidebar.test.tsx --no-coverage
```

Expected: FAIL — `Cannot find module '@/components/BillSidebar'`

- [ ] **Step 3: Implement `BillSidebar`**

Create `frontend/components/BillSidebar.tsx`:

```typescript
import type { ISTScore, FrictionTag } from "@/lib/types";
import ISTScoreGauge from "./ISTScoreGauge";
import PendingBanner from "./PendingBanner";
import TagBadge from "./TagBadge";

interface Props {
  istScore: ISTScore | null;
  tags: FrictionTag[];
}

export default function BillSidebar({ istScore, tags }: Props) {
  return (
    <div className="space-y-4">
      {istScore ? (
        <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-4">
          <ISTScoreGauge
            score={istScore.source_authenticity_score}
            copycatAlert={istScore.copycat_alert}
          />
        </div>
      ) : (
        <PendingBanner />
      )}
      {tags.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {tags.map((tag) => (
            <TagBadge key={tag.tag_type} type={tag.tag_type} />
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend && npx jest __tests__/components/BillSidebar.test.tsx --no-coverage
```

Expected: PASS — 6 tests

- [ ] **Step 5: Commit**

```bash
git add frontend/components/BillSidebar.tsx frontend/__tests__/components/BillSidebar.test.tsx
git commit -m "feat(frontend): BillSidebar component with axe TDD"
```

---

## Task 4: `SearchInput` component (TDD)

**Files:**
- Create: `frontend/__tests__/components/SearchInput.test.tsx`
- Create: `frontend/components/SearchInput.tsx`

- [ ] **Step 1: Write the failing tests**

Create `frontend/__tests__/components/SearchInput.test.tsx`:

```typescript
import { render, fireEvent, act } from "@testing-library/react";
import { axe } from "jest-axe";
import SearchInput from "@/components/SearchInput";

const mockPush = jest.fn();
jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

beforeEach(() => {
  jest.clearAllMocks();
  jest.useFakeTimers();
});

afterEach(() => {
  jest.useRealTimers();
});

test("SearchInput has no accessibility violations", async () => {
  jest.useRealTimers();
  const { container } = render(<SearchInput />);
  expect(await axe(container)).toHaveNoViolations();
});

test("SearchInput renders a searchbox", () => {
  const { getByRole } = render(<SearchInput />);
  expect(getByRole("searchbox")).toBeInTheDocument();
});

test("SearchInput does not push URL before 300ms", () => {
  const { getByRole } = render(<SearchInput />);
  fireEvent.change(getByRole("searchbox"), { target: { value: "privacy" } });
  act(() => { jest.advanceTimersByTime(299); });
  expect(mockPush).not.toHaveBeenCalled();
});

test("SearchInput pushes ?q= after 300ms", () => {
  const { getByRole } = render(<SearchInput />);
  fireEvent.change(getByRole("searchbox"), { target: { value: "privacy" } });
  act(() => { jest.advanceTimersByTime(300); });
  expect(mockPush).toHaveBeenCalledWith("?q=privacy");
});

test("SearchInput pushes ? when input is cleared", () => {
  const { getByRole } = render(<SearchInput />);
  const input = getByRole("searchbox");
  fireEvent.change(input, { target: { value: "privacy" } });
  act(() => { jest.advanceTimersByTime(300); });
  jest.clearAllMocks();
  fireEvent.change(input, { target: { value: "" } });
  act(() => { jest.advanceTimersByTime(300); });
  expect(mockPush).toHaveBeenCalledWith("?");
});

test("SearchInput resets debounce timer on each keystroke", () => {
  const { getByRole } = render(<SearchInput />);
  const input = getByRole("searchbox");
  fireEvent.change(input, { target: { value: "p" } });
  act(() => { jest.advanceTimersByTime(200); });
  fireEvent.change(input, { target: { value: "pr" } });
  act(() => { jest.advanceTimersByTime(200); });
  expect(mockPush).not.toHaveBeenCalled();
  act(() => { jest.advanceTimersByTime(100); });
  expect(mockPush).toHaveBeenCalledWith("?q=pr");
  expect(mockPush).toHaveBeenCalledTimes(1);
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npx jest __tests__/components/SearchInput.test.tsx --no-coverage
```

Expected: FAIL — `Cannot find module '@/components/SearchInput'`

- [ ] **Step 3: Implement `SearchInput`**

Create `frontend/components/SearchInput.tsx`:

```typescript
"use client";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

export default function SearchInput() {
  const router = useRouter();
  const [value, setValue] = useState("");
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      const q = value.trim();
      router.push(q ? `?q=${encodeURIComponent(q)}` : "?");
    }, 300);
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [value, router]);

  return (
    <input
      role="searchbox"
      aria-label="Search bills"
      type="search"
      value={value}
      onChange={(e) => setValue(e.target.value)}
      placeholder="Search bills…"
      className="w-full rounded-lg border border-slate-700 bg-slate-800 px-4 py-2 text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-red-500"
    />
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend && npx jest __tests__/components/SearchInput.test.tsx --no-coverage
```

Expected: PASS — 6 tests

- [ ] **Step 5: Commit**

```bash
git add frontend/components/SearchInput.tsx frontend/__tests__/components/SearchInput.test.tsx
git commit -m "feat(frontend): SearchInput with 300ms debounce TDD"
```

---

## Task 5: Bill detail page (TDD)

**Files:**
- Create: `frontend/__tests__/pages/BillDetail.test.tsx`
- Create: `frontend/app/bills/[id]/page.tsx`

- [ ] **Step 1: Write the failing tests**

Create `frontend/__tests__/pages/BillDetail.test.tsx`:

```typescript
import { render, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { axe } from "jest-axe";
import BillDetailPage from "@/app/bills/[id]/page";
import type { BillDetail, Match } from "@/lib/types";

jest.mock("next/navigation", () => ({
  useParams: () => ({ id: "00000000-0000-0000-0000-000000000001" }),
}));

jest.mock("recharts", () => ({
  RadialBarChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  RadialBar: () => null,
  PolarAngleAxis: () => null,
}));

jest.mock("@/lib/api", () => ({
  api: { bill: jest.fn(), matches: jest.fn() },
}));

import { api } from "@/lib/api";

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

const billFixture: BillDetail = {
  id: "00000000-0000-0000-0000-000000000001",
  bill_number: "HB24-1234",
  title: "Concerning Digital Privacy Requirements",
  description: "A privacy bill.",
  state: "CO",
  session: "2024A",
  status: "Introduced",
  sponsors: null,
  ist_score: {
    source_authenticity_score: 73.4,
    copycat_alert: true,
    analyzed_at: "2024-01-15T00:00:00Z",
  },
  tags: [{ tag_type: "source_cloned", confidence: 0.95 }],
};

const matchFixture: Match = {
  id: "match-1",
  matched_bill_title: "Texas Digital Data Rights Act",
  matched_state: "TX",
  similarity_score: 87.3,
  snippet_status: "verified",
  matched_snippets: [{
    kind: "snippet",
    co_context_before: "",
    co_match: "data collection by state agencies",
    co_context_after: "",
    source_context_before: "",
    source_match: "data processing by government entities",
    source_context_after: "",
  }],
};

const ghostMatchFixture: Match = {
  id: "match-2",
  matched_bill_title: "FL Ghost Bill",
  matched_state: "FL",
  similarity_score: 78.1,
  snippet_status: "source_verified_text_missing",
  matched_snippets: null,
};

const pendingMatchFixture: Match = {
  id: "match-3",
  matched_bill_title: "AZ Pending Bill",
  matched_state: "AZ",
  similarity_score: 65.0,
  snippet_status: "pending",
  matched_snippets: null,
};

beforeEach(() => jest.clearAllMocks());

test("BillDetailPage renders bill header on success", async () => {
  (api.bill as jest.Mock).mockResolvedValue(billFixture);
  (api.matches as jest.Mock).mockResolvedValue([matchFixture]);
  const { getByText } = render(<BillDetailPage />, { wrapper });
  await waitFor(() => expect(getByText("HB24-1234")).toBeInTheDocument());
  expect(getByText("Concerning Digital Privacy Requirements")).toBeInTheDocument();
});

test("BillDetailPage has no accessibility violations on success", async () => {
  (api.bill as jest.Mock).mockResolvedValue(billFixture);
  (api.matches as jest.Mock).mockResolvedValue([matchFixture]);
  const { container } = render(<BillDetailPage />, { wrapper });
  await waitFor(() => expect(container.querySelector('[aria-label*="73.4"]')).toBeInTheDocument());
  expect(await axe(container)).toHaveNoViolations();
});

test("BillDetailPage renders IST gauge when score present", async () => {
  (api.bill as jest.Mock).mockResolvedValue(billFixture);
  (api.matches as jest.Mock).mockResolvedValue([]);
  const { getByRole } = render(<BillDetailPage />, { wrapper });
  await waitFor(() => expect(getByRole("img")).toBeInTheDocument());
  expect(getByRole("img").getAttribute("aria-label")).toContain("73.4");
});

test("BillDetailPage renders PendingBanner in sidebar when ist_score is null", async () => {
  (api.bill as jest.Mock).mockResolvedValue({ ...billFixture, ist_score: null });
  (api.matches as jest.Mock).mockResolvedValue([]);
  const { getByRole, getByText } = render(<BillDetailPage />, { wrapper });
  await waitFor(() => expect(getByText("HB24-1234")).toBeInTheDocument());
  expect(getByRole("status")).toBeInTheDocument();
});

test("BillDetailPage renders error state with back link when bill fetch fails", async () => {
  (api.bill as jest.Mock).mockRejectedValue(new Error("API error 404"));
  (api.matches as jest.Mock).mockResolvedValue([]);
  const { getByRole } = render(<BillDetailPage />, { wrapper });
  await waitFor(() => expect(getByRole("link", { name: /back/i })).toBeInTheDocument());
});

test("BillDetailPage renders match cards", async () => {
  (api.bill as jest.Mock).mockResolvedValue(billFixture);
  (api.matches as jest.Mock).mockResolvedValue([matchFixture]);
  const { getByText } = render(<BillDetailPage />, { wrapper });
  await waitFor(() => expect(getByText("Texas Digital Data Rights Act")).toBeInTheDocument());
});

test("BillDetailPage renders GhostAlert for ghost match", async () => {
  (api.bill as jest.Mock).mockResolvedValue(billFixture);
  (api.matches as jest.Mock).mockResolvedValue([ghostMatchFixture]);
  const { getByRole } = render(<BillDetailPage />, { wrapper });
  await waitFor(() => expect(getByRole("alert")).toBeInTheDocument());
});

test("BillDetailPage renders PendingBanner inside pending match card", async () => {
  (api.bill as jest.Mock).mockResolvedValue(billFixture);
  (api.matches as jest.Mock).mockResolvedValue([pendingMatchFixture]);
  const { getByRole, getByText } = render(<BillDetailPage />, { wrapper });
  await waitFor(() => expect(getByText("HB24-1234")).toBeInTheDocument());
  expect(getByRole("status")).toBeInTheDocument();
});

test("BillDetailPage renders empty state when no matches", async () => {
  (api.bill as jest.Mock).mockResolvedValue(billFixture);
  (api.matches as jest.Mock).mockResolvedValue([]);
  const { getByText } = render(<BillDetailPage />, { wrapper });
  await waitFor(() => expect(getByText(/no similarity matches/i)).toBeInTheDocument());
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npx jest __tests__/pages/BillDetail.test.tsx --no-coverage
```

Expected: FAIL — `Cannot find module '@/app/bills/[id]/page'`

- [ ] **Step 3: Create directory and implement page**

```bash
mkdir -p "frontend/app/bills/[id]"
```

Create `frontend/app/bills/[id]/page.tsx`:

```typescript
"use client";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";
import BillHeader from "@/components/BillHeader";
import BillSidebar from "@/components/BillSidebar";
import MatchCard from "@/components/MatchCard";
import PendingBanner from "@/components/PendingBanner";

export default function BillDetailPage() {
  const { id } = useParams<{ id: string }>();

  const { data: bill, isPending: billPending, isError: billError } = useQuery({
    queryKey: ["bill", id],
    queryFn: () => api.bill(id),
  });

  const { data: matches, isPending: matchesPending } = useQuery({
    queryKey: ["matches", id],
    queryFn: () => api.matches(id),
    enabled: !billError,
  });

  if (billError) {
    return (
      <main id="main" className="mx-auto max-w-5xl px-4 py-12">
        <p className="mb-4 text-slate-400">Bill not found or unavailable.</p>
        <Link href="/" className="text-red-400 underline" aria-label="Back to dashboard">
          Back to dashboard
        </Link>
      </main>
    );
  }

  return (
    <main id="main" className="mx-auto max-w-5xl px-4 py-12">
      <div className="flex flex-col md:flex-row gap-8">
        <aside className="md:w-72 md:flex-shrink-0 md:sticky md:top-8 md:self-start">
          {billPending ? (
            <PendingBanner />
          ) : bill ? (
            <BillSidebar istScore={bill.ist_score} tags={bill.tags} />
          ) : null}
        </aside>

        <div className="flex-1 space-y-6">
          {billPending ? (
            <div
              className="h-24 animate-pulse rounded-lg bg-slate-700"
              aria-label="Loading bill details"
            />
          ) : bill ? (
            <BillHeader bill={bill} />
          ) : null}

          <section aria-label="Similarity matches">
            <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-500">
              Similarity Matches
            </h2>
            {matchesPending ? (
              <>
                <div className="mb-3 h-32 animate-pulse rounded-lg bg-slate-700" aria-label="Loading match" />
                <div className="h-32 animate-pulse rounded-lg bg-slate-700" aria-label="Loading match" />
              </>
            ) : matches && matches.length === 0 ? (
              <p className="text-slate-500">No similarity matches found.</p>
            ) : matches ? (
              matches.map((match) => (
                <MatchCard
                  key={match.id}
                  match={match}
                  billNumber={bill?.bill_number ?? ""}
                  billState={bill?.state ?? ""}
                  istScore={bill?.ist_score?.source_authenticity_score ?? 0}
                />
              ))
            ) : null}
          </section>
        </div>
      </div>
    </main>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd frontend && npx jest __tests__/pages/BillDetail.test.tsx --no-coverage
```

Expected: PASS — 9 tests

- [ ] **Step 5: Commit**

```bash
git add "frontend/app/bills/[id]/page.tsx" frontend/__tests__/pages/BillDetail.test.tsx
git commit -m "feat(frontend): bill detail page — sidebar layout, IST gauge, matches TDD"
```

---

## Task 6: Dashboard search integration

**Files:**
- Modify: `frontend/app/page.tsx`

Next.js 16 requires components calling `useSearchParams()` to be wrapped in `<Suspense>`. Extract `DashboardContent` as an inner component so it can safely call `useSearchParams()`, then wrap it in `Suspense` in the default export.

- [ ] **Step 1: Replace `frontend/app/page.tsx`**

```typescript
"use client";
import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";
import TagBadge from "@/components/TagBadge";
import SearchInput from "@/components/SearchInput";
import PendingBanner from "@/components/PendingBanner";

function DashboardContent() {
  const searchParams = useSearchParams();
  const q = searchParams.get("q") ?? "";

  const { data: stats, isError: statsError } = useQuery({
    queryKey: ["stats"],
    queryFn: api.stats,
  });

  const {
    data: bills,
    isPending: billsPending,
    isError: billsError,
  } = useQuery({
    queryKey: q.length >= 2 ? ["bills", "search", q] : ["bills"],
    queryFn: () => (q.length >= 2 ? api.searchBills(q) : api.bills()),
  });

  return (
    <main id="main" className="mx-auto max-w-5xl px-4 py-12 space-y-10">
      <header>
        <h1 className="text-5xl font-black tracking-tight text-white">LegiLens</h1>
        <p className="mt-2 text-slate-400">
          Quantifying the Friction Gap in the Colorado General Assembly.
        </p>
      </header>

      {statsError ? (
        <div
          role="alert"
          className="rounded-md border border-red-500/30 bg-red-900/20 p-3 text-sm text-red-300"
        >
          Failed to load statistics.
        </div>
      ) : stats ? (
        <div className="grid grid-cols-3 gap-4">
          {[
            { label: "Bills Analyzed", value: stats.bills_analyzed },
            { label: "Copycat Alerts", value: stats.copycat_alerts },
            { label: "CO Bills Tracked", value: stats.total_co_bills },
          ].map(({ label, value }) => (
            <div
              key={label}
              className="rounded-lg border border-slate-700 bg-slate-800 p-4 text-center"
            >
              <p className="text-3xl font-black text-white">{value.toLocaleString()}</p>
              <p className="text-sm text-slate-400">{label}</p>
            </div>
          ))}
        </div>
      ) : null}

      <section>
        <h2 className="mb-4 text-lg font-bold text-slate-200">Bills</h2>
        <div className="mb-4">
          <SearchInput />
        </div>

        {billsError && (
          <div
            role="alert"
            className="rounded-md border border-red-500/30 bg-red-900/20 p-3 text-sm text-red-300"
          >
            Failed to load bills.
          </div>
        )}

        {billsPending && <PendingBanner />}

        {!billsPending && !billsError && bills?.length === 0 && (
          <p className="text-slate-500">No bills match your search.</p>
        )}

        <div className="space-y-2">
          {bills?.map((bill) => (
            <Link
              key={bill.id}
              href={`/bills/${bill.id}`}
              className="flex items-center justify-between rounded-lg border border-slate-700 bg-slate-800/50 px-4 py-3 hover:border-slate-500 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
            >
              <div>
                <span className="font-mono text-sm text-slate-400">{bill.bill_number}</span>
                <p className="font-medium text-slate-200">{bill.title}</p>
              </div>
              {bill.copycat_alert && <TagBadge type="source_cloned" />}
            </Link>
          ))}
        </div>
      </section>
    </main>
  );
}

export default function Dashboard() {
  return (
    <Suspense>
      <DashboardContent />
    </Suspense>
  );
}
```

- [ ] **Step 2: Run full jest suite to verify no regressions**

```bash
cd frontend && npx jest --no-coverage
```

Expected: All tests PASS.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/page.tsx
git commit -m "feat(frontend): dashboard inline search with useSearchParams + Suspense"
```

---

## Task 7: Playwright dashboard E2E

**Files:**
- Create: `frontend/e2e/dashboard.spec.ts`

- [ ] **Step 1: Create `e2e/` directory and write tests**

```bash
mkdir -p frontend/e2e
```

Create `frontend/e2e/dashboard.spec.ts`:

```typescript
import { test, expect, type Page } from "@playwright/test";

const statsFixture = { total_co_bills: 342, copycat_alerts: 17, bills_analyzed: 289 };

const billsFixture = [
  {
    id: "bill-1",
    bill_number: "HB24-1234",
    title: "Concerning Digital Privacy",
    state: "CO",
    session: "2024A",
    status: "Introduced",
    copycat_alert: true,
  },
  {
    id: "bill-2",
    bill_number: "SB24-005",
    title: "Concerning Water Rights",
    state: "CO",
    session: "2024A",
    status: "Passed",
    copycat_alert: false,
  },
];

const searchResultsFixture = [
  {
    id: "bill-1",
    bill_number: "HB24-1234",
    title: "Concerning Digital Privacy",
    state: "CO",
    session: "2024A",
    status: "Introduced",
    copycat_alert: false,
  },
];

async function interceptDefault(page: Page) {
  await page.route("**/stats", (route) => route.fulfill({ json: statsFixture }));
  await page.route("**/bills", (route) => route.fulfill({ json: billsFixture }));
}

test("stats grid renders 3 cards with numeric values", async ({ page }) => {
  await interceptDefault(page);
  await page.goto("/");
  await expect(page.getByText("289")).toBeVisible();
  await expect(page.getByText("17")).toBeVisible();
  await expect(page.getByText("342")).toBeVisible();
});

test("bills list renders rows with links to /bills/[id]", async ({ page }) => {
  await interceptDefault(page);
  await page.goto("/");
  await expect(page.getByText("HB24-1234")).toBeVisible();
  await expect(
    page.getByRole("link", { name: /Concerning Digital Privacy/i })
  ).toHaveAttribute("href", "/bills/bill-1");
});

test("copycat badge visible on flagged bills", async ({ page }) => {
  await interceptDefault(page);
  await page.goto("/");
  await expect(page.getByText("Source-Cloned")).toBeVisible();
});

test("search: 2+ chars triggers search results", async ({ page }) => {
  await interceptDefault(page);
  await page.route("**/bills/search*", (route) =>
    route.fulfill({ json: searchResultsFixture })
  );
  await page.goto("/");
  await page.getByRole("searchbox").fill("privacy");
  await expect(page.getByText("Concerning Digital Privacy")).toBeVisible();
  await expect(page.getByText("Concerning Water Rights")).not.toBeVisible();
});

test("search: 1 char does not trigger search", async ({ page }) => {
  await interceptDefault(page);
  let searchFired = false;
  await page.route("**/bills/search*", (route) => {
    searchFired = true;
    route.fulfill({ json: [] });
  });
  await page.goto("/");
  await page.getByRole("searchbox").fill("p");
  await page.waitForTimeout(400);
  expect(searchFired).toBe(false);
  await expect(page.getByText("Concerning Water Rights")).toBeVisible();
});

test("search: clearing input resets to default bills list", async ({ page }) => {
  await interceptDefault(page);
  await page.route("**/bills/search*", (route) =>
    route.fulfill({ json: searchResultsFixture })
  );
  await page.goto("/");
  const searchbox = page.getByRole("searchbox");
  await searchbox.fill("privacy");
  await expect(page.getByText("Concerning Water Rights")).not.toBeVisible();
  await searchbox.clear();
  await expect(page.getByText("Concerning Water Rights")).toBeVisible();
});

test("/stats API error shows error alert", async ({ page }) => {
  await page.route("**/stats", (route) => route.fulfill({ status: 500 }));
  await page.route("**/bills", (route) => route.fulfill({ json: billsFixture }));
  await page.goto("/");
  await expect(page.getByRole("alert")).toBeVisible();
});

test("/bills API error shows error alert", async ({ page }) => {
  await page.route("**/stats", (route) => route.fulfill({ json: statsFixture }));
  await page.route("**/bills", (route) => route.fulfill({ status: 500 }));
  await page.goto("/");
  await expect(page.getByRole("alert")).toBeVisible();
});
```

- [ ] **Step 2: Run E2E tests**

```bash
cd frontend && npm run e2e -- --project=chromium
```

Expected: 7 dashboard tests PASS. Playwright auto-starts `next dev` if not already running.

- [ ] **Step 3: Commit**

```bash
git add frontend/e2e/dashboard.spec.ts
git commit -m "feat(frontend): Playwright E2E — dashboard stats, bills, search"
```

---

## Task 8: Playwright bill detail E2E

**Files:**
- Create: `frontend/e2e/bill-detail.spec.ts`

- [ ] **Step 1: Write the E2E tests**

Create `frontend/e2e/bill-detail.spec.ts`:

```typescript
import { test, expect, type Page } from "@playwright/test";

const billFixture = {
  id: "bill-1",
  bill_number: "HB24-1234",
  title: "Concerning Digital Privacy Requirements",
  description: "A privacy bill.",
  state: "CO",
  session: "2024A",
  status: "Introduced",
  sponsors: null,
  ist_score: {
    source_authenticity_score: 73.4,
    copycat_alert: true,
    analyzed_at: "2024-01-15T00:00:00Z",
  },
  tags: [
    { tag_type: "source_cloned", confidence: 0.95 },
    { tag_type: "technical_conflict", confidence: 0.7 },
  ],
};

const matchesFixture = [
  {
    id: "match-1",
    matched_bill_title: "Texas Digital Data Rights Act",
    matched_state: "TX",
    similarity_score: 87.3,
    snippet_status: "verified",
    matched_snippets: [
      {
        kind: "snippet",
        co_context_before: "",
        co_match: "data collection by state agencies",
        co_context_after: "",
        source_context_before: "",
        source_match: "data processing by government entities",
        source_context_after: "",
      },
    ],
  },
];

const ghostMatchesFixture = [
  {
    id: "match-2",
    matched_bill_title: "FL Ghost Bill",
    matched_state: "FL",
    similarity_score: 78.1,
    snippet_status: "source_verified_text_missing",
    matched_snippets: null,
  },
];

async function interceptBill(
  page: Page,
  billOverride = billFixture,
  matchesOverride = matchesFixture
) {
  await page.route("**/bills/bill-1/matches", (route) =>
    route.fulfill({ json: matchesOverride })
  );
  await page.route("**/bills/bill-1", (route) =>
    route.fulfill({ json: billOverride })
  );
}

test("bill detail renders header with number, title, status", async ({ page }) => {
  await interceptBill(page);
  await page.goto("/bills/bill-1");
  await expect(page.getByText("HB24-1234")).toBeVisible();
  await expect(page.getByText("Concerning Digital Privacy Requirements")).toBeVisible();
  await expect(page.getByText("Introduced")).toBeVisible();
});

test("IST gauge has role=img with aria-label containing score", async ({ page }) => {
  await interceptBill(page);
  await page.goto("/bills/bill-1");
  const gauge = page.getByRole("img");
  await expect(gauge).toBeVisible();
  await expect(gauge).toHaveAttribute("aria-label", /73\.4/);
});

test("copycat_alert: true shows COPYCAT ALERT in sidebar", async ({ page }) => {
  await interceptBill(page);
  await page.goto("/bills/bill-1");
  await expect(page.getByText("COPYCAT ALERT")).toBeVisible();
});

test("friction tags render in sidebar", async ({ page }) => {
  await interceptBill(page);
  await page.goto("/bills/bill-1");
  await expect(page.getByText("Source-Cloned")).toBeVisible();
  await expect(page.getByText("Technical Conflict")).toBeVisible();
});

test("similarity match cards render with title and score", async ({ page }) => {
  await interceptBill(page);
  await page.goto("/bills/bill-1");
  await expect(page.getByText("Texas Digital Data Rights Act")).toBeVisible();
  await expect(page.getByText(/87\.3/)).toBeVisible();
});

test("ghost match renders alert", async ({ page }) => {
  await interceptBill(page, billFixture, ghostMatchesFixture);
  await page.goto("/bills/bill-1");
  await expect(page.getByRole("alert")).toBeVisible();
});

test("ist_score null renders status banner in sidebar", async ({ page }) => {
  await interceptBill(page, { ...billFixture, ist_score: null }, []);
  await page.goto("/bills/bill-1");
  await expect(page.getByRole("status")).toBeVisible();
});

test("no matches renders empty state message", async ({ page }) => {
  await interceptBill(page, billFixture, []);
  await page.goto("/bills/bill-1");
  await expect(page.getByText(/no similarity matches/i)).toBeVisible();
});

test("/bills/bad-id 404 renders error state with back link", async ({ page }) => {
  await page.route("**/bills/bad-id/matches", (route) => route.fulfill({ json: [] }));
  await page.route("**/bills/bad-id", (route) =>
    route.fulfill({ status: 404, json: { detail: "Bill not found" } })
  );
  await page.goto("/bills/bad-id");
  await expect(page.getByRole("link", { name: /back/i })).toBeVisible();
});
```

- [ ] **Step 2: Run all E2E tests**

```bash
cd frontend && npm run e2e -- --project=chromium
```

Expected: 16 total E2E tests PASS (7 dashboard + 9 bill detail).

- [ ] **Step 3: Run full jest unit test suite**

```bash
cd frontend && npx jest --no-coverage
```

Expected: All unit tests PASS.

- [ ] **Step 4: Commit**

```bash
git add frontend/e2e/bill-detail.spec.ts
git commit -m "feat(frontend): Playwright E2E — bill detail all states"
```

---

## Self-Review

**Spec coverage:**
- ✅ Bill detail sidebar layout + mobile breakpoint `md:` (Task 5)
- ✅ Two parallel `useQuery` calls, independent loading (Task 5)
- ✅ `BillHeader` — number, title, session, state, status (Task 2)
- ✅ `BillSidebar` — IST gauge, tags, PendingBanner for null score (Task 3)
- ✅ All 8 bill detail states: success, error, null-IST, ghost, pending match, no matches (Tasks 5 + 8)
- ✅ `SearchInput` — 300ms debounce, URL set/clear (Task 4)
- ✅ Dashboard `useSearchParams` + `Suspense` wrapper (Task 6)
- ✅ Search threshold ≥2 chars matches backend constraint (Task 6 + 7)
- ✅ All dashboard states: empty, <2 chars, loading, results, no results, stats error, bills error (Tasks 4 + 7)
- ✅ Playwright install + config (Task 1)
- ✅ Dashboard E2E: 7 scenarios (Task 7)
- ✅ Bill detail E2E: 9 scenarios (Task 8)
- ✅ WCAG jest-axe in every component test and bill detail page test (Tasks 2, 3, 4, 5)
- ✅ No new dependencies beyond `@playwright/test` + Chromium (Task 1)

**Placeholder scan:** No TBDs. All steps include complete code or exact commands.

**Type consistency:**
- `BillSidebar` props `{ istScore: ISTScore | null, tags: FrictionTag[] }` — consistent Tasks 3 and 5
- `BillHeader` props `{ bill: BillDetail }` — consistent Tasks 2 and 5
- `SearchInput` — no props — consistent Tasks 4 and 6
- `MatchCard` called with `{ match, billNumber, billState, istScore }` — matches existing `components/MatchCard.tsx` signature
- `api.bill(id)` → `BillDetail`, `api.matches(id)` → `Match[]` — matches `lib/api.ts` and `lib/types.ts`
