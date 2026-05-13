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
          <p className="text-slate-400">No bills match your search.</p>
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
    <Suspense fallback={<PendingBanner />}>
      <DashboardContent />
    </Suspense>
  );
}
