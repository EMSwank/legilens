# Sprint 3: Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Next.js public frontend — dashboard, bill list, bill detail with IST score gauge, match cards, snippet diffs, ghost state alerts, journalist copy button, and pending state polling.

**Architecture:** Next.js 14+ App Router on Vercel. TanStack Query for all data fetching + 5s polling for pending matches. shadcn/ui primitives + Tailwind utility styles. Recharts for IST gauge. Inter variable font. Client Component `ProgressBar` wrapper to avoid hydration mismatch.

**Prerequisites:** Sprint 2 complete. API running at `NEXT_PUBLIC_API_URL` (e.g. `http://localhost:8000` for local dev).

**Tech Stack:** Next.js 14+, TypeScript, Tailwind CSS, shadcn/ui, Recharts, TanStack Query v5, next-nprogress-bar, Inter variable font (next/font/google)

---

## File Structure

```
frontend/
  package.json
  tsconfig.json
  tailwind.config.ts
  next.config.ts
  .env.local.example
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

- [ ] **Step 2: Install dependencies**

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

- [ ] **Step 3: Create .env.local.example**

```bash
# frontend/.env.local.example
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Copy to `.env.local` and set value before running.

- [ ] **Step 4: Verify dev server starts**

```bash
npm run dev
```

Expected: Next.js starts on `http://localhost:3000` with no errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/
git commit -m "chore: Next.js 14 frontend scaffold with Tailwind and shadcn"
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
- Create: `frontend/components/TagBadge.tsx`
- Create: `frontend/components/GhostAlert.tsx`
- Create: `frontend/components/PendingBanner.tsx`
- Create: `frontend/components/CopyButton.tsx`

- [ ] **Step 1: Create TagBadge.tsx**

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

```typescript
// frontend/components/GhostAlert.tsx
export default function GhostAlert({ matchedBill }: { matchedBill: string | null }) {
  return (
    <div className="rounded-md border border-amber-500/30 bg-amber-900/20 p-3 text-sm text-amber-300">
      <span className="font-semibold">Match verified mathematically</span> against{" "}
      {matchedBill ?? "an external bill"} — source text no longer publicly available.
    </div>
  );
}
```

- [ ] **Step 3: Create PendingBanner.tsx**

```typescript
// frontend/components/PendingBanner.tsx
export default function PendingBanner() {
  return (
    <div className="flex items-center gap-2 rounded-md border border-slate-600 bg-slate-800 px-4 py-3 text-sm text-slate-300">
      <span className="animate-spin text-lg">⟳</span>
      <span>
        <span className="font-semibold">Analyzing Cross-State Evidence…</span>{" "}
        Snippets will appear automatically when extraction completes.
      </span>
    </div>
  );
}
```

- [ ] **Step 4: Create CopyButton.tsx**

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
    <button
      onClick={handleCopy}
      className="rounded bg-slate-700 px-3 py-1 text-xs text-slate-300 hover:bg-slate-600 transition-colors"
    >
      {copied ? "Copied!" : "Copy to Clipboard"}
    </button>
  );
}
```

- [ ] **Step 5: Commit**

```bash
git add frontend/components/TagBadge.tsx frontend/components/GhostAlert.tsx frontend/components/PendingBanner.tsx frontend/components/CopyButton.tsx
git commit -m "feat: shared UI components — TagBadge, GhostAlert, PendingBanner, CopyButton"
```

---

## Task 5: IST Score Gauge

**Files:**
- Create: `frontend/components/ISTScoreGauge.tsx`

- [ ] **Step 1: Create ISTScoreGauge.tsx**

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

  return (
    <div className="flex flex-col items-center gap-2">
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
      <div className="text-center -mt-12">
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

- [ ] **Step 2: Verify gauge renders**

```bash
npm run dev
```

Import `ISTScoreGauge` in a test page, pass `score={12.58}` and `copycatAlert={true}`. Confirm red dial and "COPYCAT ALERT" badge render.

- [ ] **Step 3: Commit**

```bash
git add frontend/components/ISTScoreGauge.tsx
git commit -m "feat: IST Score Gauge — Recharts radial, red below 30"
```

---

## Task 6: SnippetDiff and MatchCard

**Files:**
- Create: `frontend/components/SnippetDiff.tsx`
- Create: `frontend/components/MatchCard.tsx`

- [ ] **Step 1: Create SnippetDiff.tsx**

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

- [ ] **Step 3: Commit**

```bash
git add frontend/components/SnippetDiff.tsx frontend/components/MatchCard.tsx
git commit -m "feat: SnippetDiff and MatchCard with journalist copy button"
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
    <main className="mx-auto max-w-5xl px-4 py-12 space-y-10">
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
              className="flex items-center justify-between rounded-lg border border-slate-700 bg-slate-800/50 px-4 py-3 hover:border-slate-500 transition-colors"
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
- Create: `frontend/app/bills/page.tsx`
- Create: `frontend/components/BillListRow.tsx`

- [ ] **Step 1: Create BillListRow.tsx**

```typescript
// frontend/components/BillListRow.tsx
import Link from "next/link";
import type { BillListItem } from "@/lib/types";
import TagBadge from "./TagBadge";

export default function BillListRow({ bill }: { bill: BillListItem }) {
  return (
    <Link
      href={`/bills/${bill.id}`}
      className="grid grid-cols-[1fr_auto] items-center gap-4 rounded-lg border border-slate-700 bg-slate-800/50 px-4 py-3 hover:border-slate-500 transition-colors"
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
    <main className="mx-auto max-w-5xl px-4 py-12 space-y-6">
      <h1 className="text-3xl font-black text-white">Colorado Bills</h1>

      <input
        type="search"
        placeholder="Search bills…"
        value={search}
        onChange={(e) => { setSearch(e.target.value); setPage(1); }}
        className="w-full rounded-lg border border-slate-600 bg-slate-800 px-4 py-2 text-slate-200 placeholder-slate-500 focus:border-slate-400 focus:outline-none"
      />

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
            className="rounded bg-slate-700 px-3 py-1 text-sm text-slate-300 disabled:opacity-40"
          >
            ← Prev
          </button>
          <span className="px-2 py-1 text-sm text-slate-400">Page {page}</span>
          <button
            onClick={() => setPage((p) => p + 1)}
            disabled={(bills?.length ?? 0) < 20}
            className="rounded bg-slate-700 px-3 py-1 text-sm text-slate-300 disabled:opacity-40"
          >
            Next →
          </button>
        </div>
      )}
    </main>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/app/bills/ frontend/components/BillListRow.tsx
git commit -m "feat: bills list page with search and pagination"
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
    <main className="mx-auto max-w-4xl px-4 py-12 space-y-8">
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
    <main className="mx-auto max-w-3xl px-4 py-12 space-y-8">
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
- Create: `frontend/components/Nav.tsx`
- Modify: `frontend/app/layout.tsx`

- [ ] **Step 1: Create Nav.tsx**

```typescript
// frontend/components/Nav.tsx
import Link from "next/link";

export default function Nav() {
  return (
    <nav className="border-b border-slate-800 bg-slate-900/80 backdrop-blur-sm sticky top-0 z-50">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
        <Link href="/" className="text-xl font-black text-white tracking-tight">
          LegiLens
        </Link>
        <div className="flex gap-6 text-sm text-slate-400">
          <Link href="/bills" className="hover:text-white transition-colors">Bills</Link>
          <Link href="/about" className="hover:text-white transition-colors">About</Link>
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

- [ ] **Step 3: Commit**

```bash
git add frontend/components/Nav.tsx frontend/app/layout.tsx
git commit -m "feat: sticky nav with LegiLens brand and bill/about links"
```

---

## Task 12: Build Verification and Merge

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
git merge feat/frontend --no-ff -m "feat: Sprint 3 — Next.js frontend complete"
git branch -d feat/frontend
```
