# Sprint 3: Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Next.js public frontend — dashboard, bill list, bill detail with IST score gauge, match cards, snippet diffs, ghost state alerts, journalist copy button, and pending state polling.

**Architecture:** Next.js 14+ App Router on Vercel. TanStack Query for all data fetching + 5s polling for pending matches. shadcn/ui primitives + Tailwind utility styles. Recharts for IST gauge. Inter variable font. Client Component `ProgressBar` wrapper to avoid hydration mismatch.

**Prerequisites:** Sprint 2 complete. API running at `NEXT_PUBLIC_API_URL` (e.g. `http://localhost:8000` for local dev).

**Tech Stack:** Next.js 14+, TypeScript, Tailwind CSS, shadcn/ui, Recharts, TanStack Query v5, next-nprogress-bar, Inter variable font (next/font/google)

**Accessibility target:** WCAG 2.1 AA. All pages must pass `axe-core` automated scan (`wcag2a` + `wcag2aa` tags) and keyboard-only navigation tests via Playwright.

---

## File Structure

```
frontend/
  package.json
  tsconfig.json
  tailwind.config.ts
  next.config.ts
  jest.config.ts
  jest.setup.ts
  playwright.config.ts
  .env.local.example
  __tests__/
    components/
      TagBadge.test.tsx
      GhostAlert.test.tsx
      PendingBanner.test.tsx
      CopyButton.test.tsx
      ISTScoreGauge.test.tsx
      SnippetDiff.test.tsx
      BillListRow.test.tsx
      Nav.test.tsx
  tests/
    e2e/
      accessibility.spec.ts   # Playwright page-level axe + keyboard tests
  app/
    layout.tsx              # root layout, Inter font, TanStack provider, ProgressBar
    page.tsx                # / dashboard
    bills/
      page.tsx              # /bills list + search
      [id]/
        page.tsx            # /bills/[id] detail
    about/
      page.tsx
  components/
    ProgressBar.tsx         # 'use client', next-nprogress-bar
    Providers.tsx           # 'use client', QueryClientProvider wrapper
    ISTScoreGauge.tsx       # Recharts radial gauge, 0-100, red below 30
    MatchCard.tsx           # similarity match card with snippet diff
    SnippetDiff.tsx         # co vs source text with context sentences
    CopyButton.tsx          # journalist clipboard button
    PendingBanner.tsx       # "Analyzing Cross-State Evidence..." banner
    GhostAlert.tsx          # source_verified_text_missing UI
    BillListRow.tsx         # /bills table row
    TagBadge.tsx            # friction tag chip
  lib/
    api.ts                  # typed fetch helpers for FastAPI
    types.ts                # TypeScript interfaces
```

---

## Task 1: Project Scaffold

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tailwind.config.ts`
- Create: `frontend/.env.local.example`

- [ ] **Step 1: Scaffold Next.js project**

```bash
cd /Users/eliotswank/dev/legilens
npx create-next-app@latest frontend \
  --typescript \
  --tailwind \
  --app \
  --no-src-dir \
  --import-alias "@/*"
cd frontend
```

- [ ] **Step 2: Install runtime dependencies**

```bash
npm install \
  @tanstack/react-query \
  recharts \
  next-nprogress-bar \
  class-variance-authority \
  clsx \
  tailwind-merge \
  lucide-react

npx shadcn@latest init
# Select: Default style, slate base color, CSS variables yes
```

- [ ] **Step 3: Install test dependencies**

```bash
npm install --save-dev \
  jest \
  jest-environment-jsdom \
  @testing-library/react \
  @testing-library/jest-dom \
  @testing-library/user-event \
  jest-axe \
  @types/jest-axe
```

- [ ] **Step 4: Create jest.config.ts**

```typescript
// frontend/jest.config.ts
import type { Config } from "jest";
import nextJest from "next/jest.js";

const createJestConfig = nextJest({ dir: "./" });

const config: Config = {
  testEnvironment: "jsdom",
  setupFilesAfterEnv: ["<rootDir>/jest.setup.ts"],
  testPathPattern: "__tests__",
};

export default createJestConfig(config);
```

- [ ] **Step 5: Create jest.setup.ts**

```typescript
// frontend/jest.setup.ts
import "@testing-library/jest-dom";
import { toHaveNoViolations } from "jest-axe";
expect.extend(toHaveNoViolations);
```

- [ ] **Step 6: Verify jest runs**

```bash
npx jest --passWithNoTests
```

Expected: `Test Suites: 0 skipped` with no errors.

- [ ] **Step 7: Create .env.local.example**

```bash
# frontend/.env.local.example
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Copy to `.env.local` and set value before running.

- [ ] **Step 8: Verify dev server starts**

```bash
npm run dev
```

Expected: Next.js starts on `http://localhost:3000` with no errors.

- [ ] **Step 9: Commit**

```bash
git add frontend/
git commit -m "chore: Next.js 14 frontend scaffold with Tailwind, shadcn, jest-axe"
```

---

## Task 2: Types and API Client

**Files:**
- Create: `frontend/lib/types.ts`
- Create: `frontend/lib/api.ts`

- [ ] **Step 1: Create types.ts**

These mirror the Pydantic response schemas from Sprint 2 exactly.

```typescript
// frontend/lib/types.ts
export interface ISTScore {
  source_authenticity_score: number;
  copycat_alert: boolean;
  analyzed_at: string;
}

export interface FrictionTag {
  type: string;
  confidence: number | null;
}

export interface BillListItem {
  id: string;
  bill_number: string;
  title: string;
  state: string;
  session: string;
  status: string | null;
  copycat_alert: boolean | null;
}

export interface BillDetail {
  id: string;
  bill_number: string;
  title: string;
  description: string | null;
  state: string;
  session: string;
  status: string | null;
  sponsors: unknown[] | null;
  ist_score: ISTScore | null;
  tags: FrictionTag[];
}

export interface SnippetItem {
  co_context_before: string;
  co_match: string;
  co_context_after: string;
  source_context_before: string;
  source_match: string;
  source_context_after: string;
}

export interface GhostMessage {
  message: "Source text unavailable for extraction";
}

export interface Match {
  id: string;
  matched_bill_title: string | null;
  matched_state: string | null;
  similarity_score: number;
  snippet_status: "pending" | "verified" | "source_verified_text_missing";
  matched_snippets: Array<SnippetItem | GhostMessage> | null;
}

export interface Stats {
  total_co_bills: number;
  copycat_alerts: number;
  bills_analyzed: number;
}

export interface TagCount {
  tag_type: string;
  count: number;
}
```

- [ ] **Step 2: Create api.ts**

```typescript
// frontend/lib/api.ts
import type { BillDetail, BillListItem, Match, Stats, TagCount } from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const HEADERS = { "User-Agent": "LegiLens-Frontend/1.0" };

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { headers: HEADERS });
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`);
  return res.json() as Promise<T>;
}

export const api = {
  bills: (params?: { session?: string; status?: string; page?: number }) => {
    const q = new URLSearchParams();
    if (params?.session) q.set("session", params.session);
    if (params?.status) q.set("status", params.status);
    if (params?.page) q.set("page", String(params.page));
    return get<BillListItem[]>(`/bills?${q}`);
  },
  searchBills: (q: string) => get<BillListItem[]>(`/bills/search?q=${encodeURIComponent(q)}`),
  bill: (id: string) => get<BillDetail>(`/bills/${id}`),
  matches: (billId: string) => get<Match[]>(`/bills/${billId}/matches`),
  stats: () => get<Stats>("/stats"),
  tags: () => get<TagCount[]>("/tags"),
};
```

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/
git commit -m "feat: typed API client and TypeScript interfaces"
```

---

## Task 3: Root Layout and Providers

**Files:**
- Create: `frontend/components/ProgressBar.tsx`
- Create: `frontend/components/Providers.tsx`
- Modify: `frontend/app/layout.tsx`

- [ ] **Step 1: Create ProgressBar.tsx**

```typescript
// frontend/components/ProgressBar.tsx
"use client";
import { AppProgressBar } from "next-nprogress-bar";

export default function ProgressBar() {
  return (
    <AppProgressBar
      color="#EF4444"
      height="3px"
      options={{ showSpinner: false }}
    />
  );
}
```

- [ ] **Step 2: Create Providers.tsx**

```typescript
// frontend/components/Providers.tsx
"use client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

export default function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(() => new QueryClient({
    defaultOptions: { queries: { staleTime: 30_000 } },
  }));
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
```

- [ ] **Step 3: Update app/layout.tsx**

The skip link (WCAG 2.4.1) must be first focusable element so keyboard users can bypass the sticky nav. Every page `<main>` must carry `id="main"`.

```typescript
// frontend/app/layout.tsx
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import Providers from "@/components/Providers";
import ProgressBar from "@/components/ProgressBar";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "LegiLens — Colorado Legislative Transparency",
  description: "Quantifying the Friction Gap in the Colorado General Assembly.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="bg-slate-900 text-slate-100 font-sans antialiased">
        {/* WCAG 2.4.1 — skip to main content link, visible only on focus */}
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-[100] focus:rounded focus:bg-white focus:px-3 focus:py-2 focus:text-slate-900 focus:shadow-lg"
        >
          Skip to main content
        </a>
        <Providers>
          <ProgressBar />
          {children}
        </Providers>
      </body>
    </html>
  );
}
```

- [ ] **Step 4: Verify no hydration errors**

```bash
npm run dev
```

Open `http://localhost:3000`. No console errors. Red progress bar appears on navigation.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/ProgressBar.tsx frontend/components/Providers.tsx frontend/app/layout.tsx
git commit -m "feat: root layout with Inter font, TanStack Query provider, progress bar"
```

---

## Task 4: Shared UI Components

**Files:**
- Create: `frontend/__tests__/components/TagBadge.test.tsx`
- Create: `frontend/__tests__/components/GhostAlert.test.tsx`
- Create: `frontend/__tests__/components/PendingBanner.test.tsx`
- Create: `frontend/__tests__/components/CopyButton.test.tsx`
- Create: `frontend/components/TagBadge.tsx`
- Create: `frontend/components/GhostAlert.tsx`
- Create: `frontend/components/PendingBanner.tsx`
- Create: `frontend/components/CopyButton.tsx`

- [ ] **Step 1: Write failing accessibility tests for all 4 components**

```typescript
// frontend/__tests__/components/TagBadge.test.tsx
import { render } from "@testing-library/react";
import { axe } from "jest-axe";
import TagBadge from "@/components/TagBadge";

test("TagBadge has no accessibility violations", async () => {
  const { container } = render(<TagBadge type="source_cloned" />);
  expect(await axe(container)).toHaveNoViolations();
});
```

```typescript
// frontend/__tests__/components/GhostAlert.test.tsx
import { render } from "@testing-library/react";
import { axe } from "jest-axe";
import GhostAlert from "@/components/GhostAlert";

test("GhostAlert has no accessibility violations", async () => {
  const { container } = render(<GhostAlert matchedBill="TX HB-1" />);
  expect(await axe(container)).toHaveNoViolations();
});

test("GhostAlert renders as alert role", () => {
  const { getByRole } = render(<GhostAlert matchedBill="TX HB-1" />);
  expect(getByRole("alert")).toBeInTheDocument();
});
```

```typescript
// frontend/__tests__/components/PendingBanner.test.tsx
import { render } from "@testing-library/react";
import { axe } from "jest-axe";
import PendingBanner from "@/components/PendingBanner";

test("PendingBanner has no accessibility violations", async () => {
  const { container } = render(<PendingBanner />);
  expect(await axe(container)).toHaveNoViolations();
});

test("PendingBanner renders as status role", () => {
  const { getByRole } = render(<PendingBanner />);
  expect(getByRole("status")).toBeInTheDocument();
});
```

```typescript
// frontend/__tests__/components/CopyButton.test.tsx
import { render, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import CopyButton from "@/components/CopyButton";

const props = {
  billNumber: "SB-1", state: "CO", coMatch: "fees not to exceed",
  matchedBill: "TX HB-1", matchedState: "TX", sourceMatch: "fees not to exceed", score: 12.5,
};

beforeEach(() => {
  Object.assign(navigator, {
    clipboard: { writeText: jest.fn().mockResolvedValue(undefined) },
  });
});

test("CopyButton has no accessibility violations", async () => {
  const { container } = render(<CopyButton {...props} />);
  expect(await axe(container)).toHaveNoViolations();
});

test("CopyButton announces copy to screen readers via live region", async () => {
  const { getByRole, getByText } = render(<CopyButton {...props} />);
  await userEvent.click(getByText("Copy to Clipboard"));
  await waitFor(() => {
    expect(getByRole("status")).toHaveTextContent("Copied to clipboard");
  });
});
```

- [ ] **Step 2: Run tests — verify all FAIL (components don't exist yet)**

```bash
cd frontend && npx jest __tests__/components
```

Expected: `Cannot find module '@/components/TagBadge'` (or similar import errors). This confirms TDD cycle is running correctly.

- [ ] **Step 3: Create TagBadge.tsx**

```typescript
// frontend/components/TagBadge.tsx
const TAG_LABELS: Record<string, string> = {
  source_cloned: "Source-Cloned",
  technical_conflict: "Technical Conflict",
  regressive_burden: "Regressive Burden",
  expert_defiance: "Expert Defiance",
  spatial_inconsistency: "Spatial Inconsistency",
  legal_hallucination: "Legal Hallucination",
};

export default function TagBadge({ type }: { type: string }) {
  return (
    <span className="inline-flex items-center rounded-full bg-red-900/40 px-2.5 py-0.5 text-xs font-medium text-red-300 ring-1 ring-inset ring-red-500/30">
      {TAG_LABELS[type] ?? type}
    </span>
  );
}
```

- [ ] **Step 2: Create GhostAlert.tsx**

`role="alert"` announces to screen readers immediately on mount (WCAG 4.1.3).

```typescript
// frontend/components/GhostAlert.tsx
export default function GhostAlert({ matchedBill }: { matchedBill: string | null }) {
  return (
    <div
      role="alert"
      className="rounded-md border border-amber-500/30 bg-amber-900/20 p-3 text-sm text-amber-300"
    >
      <span className="font-semibold">Match verified mathematically</span> against{" "}
      {matchedBill ?? "an external bill"} — source text no longer publicly available.
    </div>
  );
}
```

- [ ] **Step 3: Create PendingBanner.tsx**

`role="status"` + `aria-live="polite"` for screen reader announcement. `aria-hidden` on the decorative spinner; `motion-safe:` prevents animation for users with `prefers-reduced-motion`.

```typescript
// frontend/components/PendingBanner.tsx
export default function PendingBanner() {
  return (
    <div
      role="status"
      aria-live="polite"
      className="flex items-center gap-2 rounded-md border border-slate-600 bg-slate-800 px-4 py-3 text-sm text-slate-300"
    >
      <span className="motion-safe:animate-spin text-lg" aria-hidden="true">⟳</span>
      <span>
        <span className="font-semibold">Analyzing Cross-State Evidence…</span>{" "}
        Snippets will appear automatically when extraction completes.
      </span>
    </div>
  );
}
```

- [ ] **Step 4: Create CopyButton.tsx**

Use a visually-hidden `role="status"` live region instead of a dynamic `aria-label` — screen readers don't reliably re-announce changed `aria-label` values (WCAG 4.1.3). Add `focus-visible:ring-2` for keyboard focus visibility (WCAG 2.4.7).

```typescript
// frontend/components/CopyButton.tsx
"use client";
import { useState } from "react";

interface CopyButtonProps {
  billNumber: string;
  state: string;
  coMatch: string;
  matchedBill: string;
  matchedState: string;
  sourceMatch: string;
  score: number;
}

export default function CopyButton({
  billNumber, state, coMatch, matchedBill, matchedState, sourceMatch, score,
}: CopyButtonProps) {
  const [copied, setCopied] = useState(false);

  const text = [
    `[${state} ${billNumber}] "${coMatch}"`,
    `[${matchedState} ${matchedBill}] "${sourceMatch}"`,
    `Source Authenticity Score: ${score.toFixed(2)} — LegiLens.co`,
  ].join("\n");

  async function handleCopy() {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <>
      <button
        onClick={handleCopy}
        className="rounded bg-slate-700 px-3 py-1 text-xs text-slate-300 hover:bg-slate-600 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
      >
        {copied ? "Copied!" : "Copy to Clipboard"}
      </button>
      {/* Live region announces copy confirmation to screen readers */}
      <span role="status" aria-live="polite" className="sr-only">
        {copied ? "Copied to clipboard" : ""}
      </span>
    </>
  );
}
```

- [ ] **Step 5: Run tests — verify all PASS**

```bash
cd frontend && npx jest __tests__/components
```

Expected: 6 tests pass across 4 files.

- [ ] **Step 6: Commit**

```bash
git add frontend/components/TagBadge.tsx frontend/components/GhostAlert.tsx frontend/components/PendingBanner.tsx frontend/components/CopyButton.tsx frontend/__tests__/components/
git commit -m "feat: shared UI components — TagBadge, GhostAlert, PendingBanner, CopyButton (jest-axe TDD)"
```

---

## Task 5: IST Score Gauge

**Files:**
- Create: `frontend/__tests__/components/ISTScoreGauge.test.tsx`
- Create: `frontend/components/ISTScoreGauge.tsx`

- [ ] **Step 1: Write failing accessibility test**

Recharts does not render meaningfully in jsdom — mock it so the test targets the accessible wrapper, not the SVG internals.

```typescript
// frontend/__tests__/components/ISTScoreGauge.test.tsx
import { render } from "@testing-library/react";
import { axe } from "jest-axe";
import ISTScoreGauge from "@/components/ISTScoreGauge";

jest.mock("recharts", () => ({
  RadialBarChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  RadialBar: () => null,
  PolarAngleAxis: () => null,
}));

test("ISTScoreGauge has no accessibility violations", async () => {
  const { container } = render(<ISTScoreGauge score={42} copycatAlert={false} />);
  expect(await axe(container)).toHaveNoViolations();
});

test("ISTScoreGauge aria-label includes score", () => {
  const { getByRole } = render(<ISTScoreGauge score={42} copycatAlert={false} />);
  expect(getByRole("img")).toHaveAttribute("aria-label", expect.stringContaining("42.00"));
});

test("ISTScoreGauge aria-label includes copycat warning when alert active", () => {
  const { getByRole } = render(<ISTScoreGauge score={12} copycatAlert={true} />);
  expect(getByRole("img").getAttribute("aria-label")).toContain("Copycat alert triggered");
});
```

- [ ] **Step 2: Run test — verify FAIL**

```bash
cd frontend && npx jest __tests__/components/ISTScoreGauge
```

Expected: `Cannot find module '@/components/ISTScoreGauge'`.

- [ ] **Step 3: Create ISTScoreGauge.tsx**

Wrap chart in `role="img"` with `aria-label` (WCAG 1.1.1) — Recharts SVG is decorative and not interpretable by screen readers. The numeric score text beneath the chart is the accessible text alternative.

```typescript
// frontend/components/ISTScoreGauge.tsx
"use client";
import { RadialBarChart, RadialBar, PolarAngleAxis } from "recharts";

interface Props {
  score: number;  // 0-100
  copycatAlert: boolean;
}

export default function ISTScoreGauge({ score, copycatAlert }: Props) {
  const color = copycatAlert ? "#EF4444" : score < 60 ? "#F59E0B" : "#22C55E";
  const data = [{ value: score, fill: color }];
  const label = `Source Authenticity Score: ${score.toFixed(2)} out of 100.${copycatAlert ? " Copycat alert triggered." : ""}`;

  return (
    <div
      className="flex flex-col items-center gap-2"
      role="img"
      aria-label={label}
    >
      <RadialBarChart
        width={180}
        height={180}
        innerRadius={60}
        outerRadius={85}
        data={data}
        startAngle={180}
        endAngle={0}
      >
        <PolarAngleAxis type="number" domain={[0, 100]} angleAxisId={0} tick={false} />
        <RadialBar dataKey="value" angleAxisId={0} background={{ fill: "#1e293b" }} />
      </RadialBarChart>
      <div className="text-center -mt-12" aria-hidden="true">
        <p className="text-3xl font-black" style={{ color }}>
          {score.toFixed(2)}
        </p>
        <p className="text-xs text-slate-400">Source Authenticity Score</p>
        {copycatAlert && (
          <span className="mt-1 inline-block rounded-full bg-red-500/20 px-2 py-0.5 text-xs font-semibold text-red-400 ring-1 ring-red-500/40">
            COPYCAT ALERT
          </span>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run tests — verify all PASS**

```bash
cd frontend && npx jest __tests__/components/ISTScoreGauge
```

Expected: 3 tests pass.

- [ ] **Step 5: Verify gauge renders visually**

```bash
npm run dev
```

Import `ISTScoreGauge` in a test page, pass `score={12.58}` and `copycatAlert={true}`. Confirm red dial and "COPYCAT ALERT" badge render.

- [ ] **Step 6: Commit**

```bash
git add frontend/components/ISTScoreGauge.tsx frontend/__tests__/components/ISTScoreGauge.test.tsx
git commit -m "feat: IST Score Gauge — Recharts radial, red below 30 (jest-axe TDD)"
```

---

## Task 6: SnippetDiff and MatchCard

**Files:**
- Create: `frontend/__tests__/components/SnippetDiff.test.tsx`
- Create: `frontend/components/SnippetDiff.tsx`
- Create: `frontend/components/MatchCard.tsx`

- [ ] **Step 1: Write failing accessibility test for SnippetDiff**

```typescript
// frontend/__tests__/components/SnippetDiff.test.tsx
import { render } from "@testing-library/react";
import { axe } from "jest-axe";
import SnippetDiff from "@/components/SnippetDiff";

const snippet = {
  co_context_before: "Intro sentence.",
  co_match: "The commission shall establish fees not to exceed one hundred dollars.",
  co_context_after: "Outro sentence.",
  source_context_before: "Preamble.",
  source_match: "The commission shall establish fees not to exceed one hundred dollars.",
  source_context_after: "Closing.",
};

test("SnippetDiff has no accessibility violations", async () => {
  const { container } = render(<SnippetDiff snippet={snippet} />);
  expect(await axe(container)).toHaveNoViolations();
});
```

- [ ] **Step 2: Run test — verify FAIL**

```bash
cd frontend && npx jest __tests__/components/SnippetDiff
```

Expected: `Cannot find module '@/components/SnippetDiff'`.

- [ ] **Step 3: Create SnippetDiff.tsx**

```typescript
// frontend/components/SnippetDiff.tsx
import type { SnippetItem } from "@/lib/types";

export default function SnippetDiff({ snippet }: { snippet: SnippetItem }) {
  return (
    <div className="grid grid-cols-2 gap-4 rounded-md bg-slate-800 p-4 text-sm">
      <div>
        <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">Colorado</p>
        {snippet.co_context_before && (
          <p className="text-slate-500 italic">{snippet.co_context_before}</p>
        )}
        <p className="my-1 rounded bg-red-900/30 px-2 py-1 text-slate-200 ring-1 ring-red-500/30">
          {snippet.co_match}
        </p>
        {snippet.co_context_after && (
          <p className="text-slate-500 italic">{snippet.co_context_after}</p>
        )}
      </div>
      <div>
        <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">Source</p>
        {snippet.source_context_before && (
          <p className="text-slate-500 italic">{snippet.source_context_before}</p>
        )}
        <p className="my-1 rounded bg-red-900/30 px-2 py-1 text-slate-200 ring-1 ring-red-500/30">
          {snippet.source_match}
        </p>
        {snippet.source_context_after && (
          <p className="text-slate-500 italic">{snippet.source_context_after}</p>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create MatchCard.tsx**

```typescript
// frontend/components/MatchCard.tsx
import type { Match } from "@/lib/types";
import GhostAlert from "./GhostAlert";
import SnippetDiff from "./SnippetDiff";
import CopyButton from "./CopyButton";

interface Props {
  match: Match;
  billNumber: string;
  billState: string;
  istScore: number;
}

function isSnippetItem(s: unknown): s is { co_match: string; source_match: string; co_context_before: string; co_context_after: string; source_context_before: string; source_context_after: string } {
  return typeof s === "object" && s !== null && "co_match" in s;
}

export default function MatchCard({ match, billNumber, billState, istScore }: Props) {
  return (
    <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="rounded bg-slate-700 px-2 py-0.5 text-xs font-mono text-slate-300">
            [{match.matched_state}]
          </span>
          <span className="font-semibold text-slate-200">
            {match.matched_bill_title ?? "Unknown Bill"}
          </span>
        </div>
        <span className="text-sm font-bold text-red-400">
          {match.similarity_score.toFixed(2)}% match
        </span>
      </div>

      {match.snippet_status === "source_verified_text_missing" && (
        <GhostAlert matchedBill={match.matched_bill_title} />
      )}

      {match.matched_snippets?.map((s, i) =>
        isSnippetItem(s) ? (
          <div key={i} className="space-y-2">
            <SnippetDiff snippet={s} />
            <CopyButton
              billNumber={billNumber}
              state={billState}
              coMatch={s.co_match}
              matchedBill={match.matched_bill_title ?? ""}
              matchedState={match.matched_state ?? ""}
              sourceMatch={s.source_match}
              score={istScore}
            />
          </div>
        ) : null
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run tests — verify PASS**

```bash
cd frontend && npx jest __tests__/components/SnippetDiff
```

Expected: 1 test passes.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/SnippetDiff.tsx frontend/components/MatchCard.tsx frontend/__tests__/components/SnippetDiff.test.tsx
git commit -m "feat: SnippetDiff and MatchCard with journalist copy button (jest-axe TDD)"
```

---

## Task 7: Dashboard Page

**Files:**
- Modify: `frontend/app/page.tsx`

- [ ] **Step 1: Implement dashboard page**

```typescript
// frontend/app/page.tsx
"use client";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";
import TagBadge from "@/components/TagBadge";

export default function Dashboard() {
  const { data: stats } = useQuery({ queryKey: ["stats"], queryFn: api.stats });
  const { data: bills } = useQuery({ queryKey: ["bills"], queryFn: () => api.bills() });

  return (
    <main id="main" className="mx-auto max-w-5xl px-4 py-12 space-y-10">
      <header>
        <h1 className="text-5xl font-black tracking-tight text-white">LegiLens</h1>
        <p className="mt-2 text-slate-400">Quantifying the Friction Gap in the Colorado General Assembly.</p>
      </header>

      {stats && (
        <div className="grid grid-cols-3 gap-4">
          {[
            { label: "Bills Analyzed", value: stats.bills_analyzed },
            { label: "Copycat Alerts", value: stats.copycat_alerts },
            { label: "CO Bills Tracked", value: stats.total_co_bills },
          ].map(({ label, value }) => (
            <div key={label} className="rounded-lg border border-slate-700 bg-slate-800 p-4 text-center">
              <p className="text-3xl font-black text-white">{value.toLocaleString()}</p>
              <p className="text-sm text-slate-400">{label}</p>
            </div>
          ))}
        </div>
      )}

      <section>
        <h2 className="mb-4 text-lg font-bold text-slate-200">Recent Bills</h2>
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
```

- [ ] **Step 2: Verify dashboard renders**

```bash
npm run dev
```

Open `http://localhost:3000`. Stats grid and bill list render (may be empty if API has no data yet — that's fine).

- [ ] **Step 3: Commit**

```bash
git add frontend/app/page.tsx
git commit -m "feat: dashboard page — stats banner, recent bills feed"
```

---

## Task 8: Bills List Page

**Files:**
- Create: `frontend/__tests__/components/BillListRow.test.tsx`
- Create: `frontend/app/bills/page.tsx`
- Create: `frontend/components/BillListRow.tsx`

- [ ] **Step 1: Write failing accessibility test for BillListRow**

```typescript
// frontend/__tests__/components/BillListRow.test.tsx
import { render } from "@testing-library/react";
import { axe } from "jest-axe";
import BillListRow from "@/components/BillListRow";
import type { BillListItem } from "@/lib/types";

jest.mock("next/link", () => ({ href, children, ...rest }: any) => (
  <a href={href} {...rest}>{children}</a>
));

const bill: BillListItem = {
  id: "1", bill_number: "SB-1", title: "Test Bill",
  state: "CO", session: "2024A", status: "active", copycat_alert: false,
};

test("BillListRow has no accessibility violations", async () => {
  const { container } = render(<BillListRow bill={bill} />);
  expect(await axe(container)).toHaveNoViolations();
});
```

- [ ] **Step 2: Run test — verify FAIL**

```bash
cd frontend && npx jest __tests__/components/BillListRow
```

Expected: `Cannot find module '@/components/BillListRow'`.

- [ ] **Step 3: Create BillListRow.tsx**

```typescript
// frontend/components/BillListRow.tsx
import Link from "next/link";
import type { BillListItem } from "@/lib/types";
import TagBadge from "./TagBadge";

export default function BillListRow({ bill }: { bill: BillListItem }) {
  return (
    <Link
      href={`/bills/${bill.id}`}
      className="grid grid-cols-[1fr_auto] items-center gap-4 rounded-lg border border-slate-700 bg-slate-800/50 px-4 py-3 hover:border-slate-500 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
    >
      <div>
        <span className="font-mono text-xs text-slate-500">{bill.session} · {bill.bill_number}</span>
        <p className="font-medium text-slate-200">{bill.title}</p>
        {bill.status && (
          <span className="text-xs text-slate-500 capitalize">{bill.status}</span>
        )}
      </div>
      <div className="flex items-center gap-2">
        {bill.copycat_alert && <TagBadge type="source_cloned" />}
      </div>
    </Link>
  );
}
```

- [ ] **Step 2: Create bills/page.tsx**

Key WCAG fixes: `<label>` associated with search input (WCAG 1.3.1), `focus:outline-none` replaced with `focus-visible:ring-2` (WCAG 2.4.7), `aria-label` on pagination buttons (WCAG 2.4.6), `id="main"` for skip link target (WCAG 2.4.1).

```typescript
// frontend/app/bills/page.tsx
"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import BillListRow from "@/components/BillListRow";

export default function BillsPage() {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);

  const { data: bills, isLoading } = useQuery({
    queryKey: ["bills", search, page],
    queryFn: () => search.length >= 2 ? api.searchBills(search) : api.bills({ page }),
  });

  return (
    <main id="main" className="mx-auto max-w-5xl px-4 py-12 space-y-6">
      <h1 className="text-3xl font-black text-white">Colorado Bills</h1>

      <div>
        <label htmlFor="bill-search" className="sr-only">Search bills</label>
        <input
          id="bill-search"
          type="search"
          placeholder="Search bills…"
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1); }}
          className="w-full rounded-lg border border-slate-600 bg-slate-800 px-4 py-2 text-slate-200 placeholder-slate-500 focus:border-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
        />
      </div>

      {isLoading ? (
        <p className="text-slate-500">Loading…</p>
      ) : (
        <div className="space-y-2">
          {bills?.map((bill) => <BillListRow key={bill.id} bill={bill} />)}
          {bills?.length === 0 && <p className="text-slate-500">No bills found.</p>}
        </div>
      )}

      {!search && (
        <div className="flex gap-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            aria-label="Go to previous page"
            className="rounded bg-slate-700 px-3 py-1 text-sm text-slate-300 disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
          >
            ← Prev
          </button>
          <span className="px-2 py-1 text-sm text-slate-400" aria-live="polite">Page {page}</span>
          <button
            onClick={() => setPage((p) => p + 1)}
            disabled={(bills?.length ?? 0) < 20}
            aria-label="Go to next page"
            className="rounded bg-slate-700 px-3 py-1 text-sm text-slate-300 disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
          >
            Next →
          </button>
        </div>
      )}
    </main>
  );
}
```

- [ ] **Step 5: Run BillListRow test — verify PASS**

```bash
cd frontend && npx jest __tests__/components/BillListRow
```

Expected: 1 test passes.

- [ ] **Step 6: Commit**

```bash
git add frontend/app/bills/ frontend/components/BillListRow.tsx frontend/__tests__/components/BillListRow.test.tsx
git commit -m "feat: bills list page with search and pagination (jest-axe TDD)"
```

---

## Task 9: Bill Detail Page

**Files:**
- Create: `frontend/app/bills/[id]/page.tsx`

- [ ] **Step 1: Create bill detail page**

```typescript
// frontend/app/bills/[id]/page.tsx
"use client";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import ISTScoreGauge from "@/components/ISTScoreGauge";
import MatchCard from "@/components/MatchCard";
import PendingBanner from "@/components/PendingBanner";
import TagBadge from "@/components/TagBadge";
import type { Match } from "@/lib/types";

function isGhostMessage(s: unknown): s is { message: string } {
  return typeof s === "object" && s !== null && "message" in s;
}

export default function BillDetailPage() {
  const { id } = useParams<{ id: string }>();

  const { data: bill } = useQuery({
    queryKey: ["bill", id],
    queryFn: () => api.bill(id),
  });

  const { data: matches } = useQuery({
    queryKey: ["matches", id],
    queryFn: () => api.matches(id),
    refetchInterval: (query) => {
      const data = query.state.data as Match[] | undefined;
      const hasPending = data?.some((m) => m.snippet_status === "pending");
      return hasPending ? 5000 : false;
    },
  });

  const hasPending = matches?.some((m) => m.snippet_status === "pending");

  if (!bill) return <p className="p-12 text-slate-500">Loading…</p>;

  return (
    <main id="main" className="mx-auto max-w-4xl px-4 py-12 space-y-8">
      <div>
        <span className="font-mono text-sm text-slate-500">{bill.session} · {bill.bill_number}</span>
        <h1 className="mt-1 text-3xl font-black text-white">{bill.title}</h1>
        {bill.description && <p className="mt-2 text-slate-400">{bill.description}</p>}
        <div className="mt-3 flex flex-wrap gap-2">
          {bill.tags.map((t) => <TagBadge key={t.type} type={t.type} />)}
        </div>
      </div>

      {bill.ist_score && (
        <ISTScoreGauge
          score={Number(bill.ist_score.source_authenticity_score)}
          copycatAlert={bill.ist_score.copycat_alert}
        />
      )}

      <section className="space-y-4">
        <h2 className="text-xl font-bold text-slate-200">Cross-State Matches</h2>
        {hasPending && <PendingBanner />}
        {matches?.length === 0 && !hasPending && (
          <p className="text-slate-500">No significant matches found in national corpus.</p>
        )}
        {matches?.map((match) => (
          <MatchCard
            key={match.id}
            match={match}
            billNumber={bill.bill_number}
            billState={bill.state}
            istScore={Number(bill.ist_score?.source_authenticity_score ?? 100)}
          />
        ))}
      </section>
    </main>
  );
}
```

- [ ] **Step 2: Verify full detail page renders**

```bash
npm run dev
```

Navigate to a bill detail page. IST gauge, match cards, pending banner (if applicable) all render.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/bills/
git commit -m "feat: bill detail page — IST gauge, match cards, snippet diffs, pending poll"
```

---

## Task 10: About Page

**Files:**
- Create: `frontend/app/about/page.tsx`

- [ ] **Step 1: Create about page**

```typescript
// frontend/app/about/page.tsx
export default function AboutPage() {
  return (
    <main id="main" className="mx-auto max-w-3xl px-4 py-12 space-y-8">
      <h1 className="text-4xl font-black text-white">About LegiLens</h1>

      <section className="prose prose-invert max-w-none space-y-4">
        <p className="text-slate-300 leading-relaxed">
          LegiLens quantifies the "Friction Gap" in the Colorado General Assembly — the discrepancy
          between legislative rhetoric and administrative reality. Our Influence & Source Tracker (IST)
          detects when Colorado bills share language with legislation introduced in other states or
          known model bill templates.
        </p>

        <h2 className="text-xl font-bold text-white">How Scoring Works</h2>
        <p className="text-slate-300 leading-relaxed">
          Every Colorado bill is analyzed using MinHash locality-sensitive hashing (num_perm=128)
          against a corpus of 190,000+ national bills. Bills sharing more than 70% textual similarity
          with out-of-state legislation trigger a Copycat Alert.
        </p>
        <p className="text-slate-300 leading-relaxed">
          The <span className="text-white font-semibold">Source Authenticity Score</span> runs from
          0 to 100. A score of 100 means no significant matches found. A score below 30 triggers a
          Copycat Alert (red). Matching sentence pairs are extracted using Python's difflib to show
          exactly which language was copied.
        </p>

        <h2 className="text-xl font-bold text-white">Ghost State</h2>
        <p className="text-slate-300 leading-relaxed">
          When a mathematical match is confirmed but the source bill's text is no longer publicly
          available, LegiLens displays a "Match verified mathematically" notice. The IST score
          remains valid — only the visual snippet is unavailable.
        </p>

        <h2 className="text-xl font-bold text-white">Data Sources</h2>
        <p className="text-slate-300 leading-relaxed">
          Bill data is sourced from{" "}
          <a href="https://legiscan.com" className="text-red-400 hover:underline">
            LegiScan
          </a>
          , updated nightly. LegiLens is an independent transparency project and is not affiliated
          with the Colorado General Assembly.
        </p>
      </section>
    </main>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/app/about/page.tsx
git commit -m "feat: about page — methodology, scoring explanation"
```

---

## Task 11: Navigation

**Files:**
- Create: `frontend/__tests__/components/Nav.test.tsx`
- Create: `frontend/components/Nav.tsx`
- Modify: `frontend/app/layout.tsx`

- [ ] **Step 1: Write failing accessibility test for Nav**

`usePathname` and `Link` must be mocked — they are Next.js runtime APIs unavailable in jsdom.

```typescript
// frontend/__tests__/components/Nav.test.tsx
import { render } from "@testing-library/react";
import { axe } from "jest-axe";
import Nav from "@/components/Nav";

jest.mock("next/navigation", () => ({ usePathname: () => "/bills" }));
jest.mock("next/link", () => ({ href, children, ...rest }: any) => (
  <a href={href} {...rest}>{children}</a>
));

test("Nav has no accessibility violations", async () => {
  const { container } = render(<Nav />);
  expect(await axe(container)).toHaveNoViolations();
});

test("Nav marks active page with aria-current", () => {
  const { getByText } = render(<Nav />);
  expect(getByText("Bills")).toHaveAttribute("aria-current", "page");
  expect(getByText("About")).not.toHaveAttribute("aria-current");
});

test("Nav landmark has accessible name", () => {
  const { getByRole } = render(<Nav />);
  expect(getByRole("navigation", { name: "Main navigation" })).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test — verify FAIL**

```bash
cd frontend && npx jest __tests__/components/Nav
```

Expected: `Cannot find module '@/components/Nav'`.

- [ ] **Step 3: Create Nav.tsx**

Must be a Client Component to use `usePathname` for `aria-current="page"` (WCAG 2.4.8). `aria-label` on `<nav>` distinguishes it from any other nav landmarks (WCAG 2.4.6). Focus ring on links (WCAG 2.4.7).

```typescript
// frontend/components/Nav.tsx
"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

export default function Nav() {
  const pathname = usePathname();

  return (
    <nav
      aria-label="Main navigation"
      className="border-b border-slate-800 bg-slate-900/80 backdrop-blur-sm sticky top-0 z-50"
    >
      <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
        <Link
          href="/"
          className="text-xl font-black text-white tracking-tight focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500 rounded"
          aria-label="LegiLens home"
        >
          LegiLens
        </Link>
        <div className="flex gap-6 text-sm text-slate-400">
          <Link
            href="/bills"
            aria-current={pathname.startsWith("/bills") ? "page" : undefined}
            className="hover:text-white transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500 rounded"
          >
            Bills
          </Link>
          <Link
            href="/about"
            aria-current={pathname === "/about" ? "page" : undefined}
            className="hover:text-white transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500 rounded"
          >
            About
          </Link>
        </div>
      </div>
    </nav>
  );
}
```

- [ ] **Step 2: Add Nav to layout.tsx**

```typescript
// Add inside <body>, above {children}:
import Nav from "@/components/Nav";
// ...
<body className="bg-slate-900 text-slate-100 font-sans antialiased">
  <Providers>
    <ProgressBar />
    <Nav />
    {children}
  </Providers>
</body>
```

- [ ] **Step 5: Run tests — verify all PASS**

```bash
cd frontend && npx jest __tests__/components/Nav
```

Expected: 3 tests pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/components/Nav.tsx frontend/app/layout.tsx frontend/__tests__/components/Nav.test.tsx
git commit -m "feat: sticky nav with WCAG aria-current and accessible landmark (jest-axe TDD)"
```

---

## Task 12: WCAG 2.1 AA Accessibility Tests

**Files:**
- Create: `frontend/playwright.config.ts`
- Create: `frontend/tests/accessibility.spec.ts`

Automated axe scans catch ~30% of issues. Supplement with explicit keyboard navigation tests for the remaining coverage.

- [ ] **Step 1: Install Playwright and axe-core**

```bash
cd frontend
npm install --save-dev @playwright/test @axe-core/playwright
npx playwright install --with-deps chromium
```

- [ ] **Step 2: Create playwright.config.ts**

E2E tests live in `tests/e2e/` — separate from jest's `__tests__/` so the two runners don't pick up each other's files.

```typescript
// frontend/playwright.config.ts
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  use: {
    baseURL: "http://localhost:3000",
  },
  webServer: {
    command: "npm run dev",
    url: "http://localhost:3000",
    reuseExistingServer: !process.env.CI,
  },
});
```

- [ ] **Step 3: Write axe accessibility tests**

```typescript
// frontend/tests/e2e/accessibility.spec.ts
import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const staticPages = [
  { name: "Dashboard", url: "/" },
  { name: "Bills list", url: "/bills" },
  { name: "About", url: "/about" },
];

for (const { name, url } of staticPages) {
  test(`${name} — no WCAG 2.1 AA violations`, async ({ page }) => {
    await page.goto(url);
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa"])
      .analyze();
    expect(results.violations).toEqual([]);
  });
}

test("Bills list — search input is keyboard reachable and labeled", async ({ page }) => {
  await page.goto("/bills");
  await page.keyboard.press("Tab"); // skip link
  await page.keyboard.press("Tab"); // nav: LegiLens
  await page.keyboard.press("Tab"); // nav: Bills
  await page.keyboard.press("Tab"); // nav: About
  await page.keyboard.press("Tab"); // search input
  const focused = page.locator(":focus");
  await expect(focused).toHaveAttribute("id", "bill-search");
});

test("Bills list — pagination buttons keyboard accessible", async ({ page }) => {
  await page.goto("/bills");
  // Tab to next-page button and activate with Enter
  await page.locator('[aria-label="Go to next page"]').focus();
  await page.keyboard.press("Enter");
  await expect(page.locator('[aria-live="polite"]')).toContainText("Page 2");
});

test("Skip link — visible on focus, navigates to main", async ({ page }) => {
  await page.goto("/");
  await page.keyboard.press("Tab");
  const skipLink = page.locator('a[href="#main"]');
  await expect(skipLink).toBeVisible();
  await page.keyboard.press("Enter");
  const main = page.locator("#main");
  await expect(main).toBeFocused();
});

test("CopyButton — copy confirmation announced to screen readers", async ({ page }) => {
  // Navigate to a bill detail page; requires at least one bill in DB.
  // In CI with no API, this test is skipped via environment check.
  test.skip(!process.env.TEST_BILL_ID, "Requires TEST_BILL_ID env var pointing to a seeded bill");
  await page.goto(`/bills/${process.env.TEST_BILL_ID}`);
  const copyBtn = page.locator("button", { hasText: "Copy to Clipboard" }).first();
  await copyBtn.focus();
  await page.keyboard.press("Enter");
  const liveRegion = page.locator('[role="status"][aria-live="polite"]').first();
  await expect(liveRegion).toContainText("Copied to clipboard");
});
```

- [ ] **Step 4: Run axe tests**

```bash
cd frontend
npx playwright test tests/accessibility.spec.ts
```

Expected: all `no WCAG 2.1 AA violations` tests pass. Fix any `results.violations` — each violation object includes `id`, `description`, `nodes` with exact selector, and a `helpUrl` link.

- [ ] **Step 5: Verify focus ring on all interactive elements manually**

Start dev server. Tab through each page without touching the mouse. Verify:
- Skip link appears on first Tab
- Nav links show red ring on focus
- Bill list rows show focus indicator (add `focus-visible:ring-2 focus-visible:ring-red-500` to `BillListRow` Link if missing)
- Search input shows ring
- Pagination buttons show ring
- CopyButton shows ring
- No element loses focus visibility at any point

Fix any missing focus rings before proceeding.

- [ ] **Step 6: Commit**

```bash
git add frontend/playwright.config.ts frontend/tests/e2e/
git commit -m "test: WCAG 2.1 AA — Playwright E2E axe scans and keyboard navigation"
```

---

## Task 13: Build Verification and Merge

- [ ] **Step 1: Run TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 2: Run production build**

```bash
npm run build
```

Expected: build completes with no errors.

- [ ] **Step 3: Merge to main**

```bash
git checkout main
git merge feat/frontend --no-ff -m "feat: Sprint 3 — Next.js frontend complete, WCAG 2.1 AA"
git branch -d feat/frontend
```
