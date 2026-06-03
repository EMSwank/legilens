"use client";
import { Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";
import TagBadge from "@/components/TagBadge";
import SearchInput from "@/components/SearchInput";
import PendingBanner from "@/components/PendingBanner";
import SessionDropdown from "@/components/SessionDropdown";
import FilterChips from "@/components/FilterChips";

const TAG_LABELS: Record<string, string> = {
  source_cloned: "Source-Cloned",
  technical_conflict: "Technical Conflict",
  regressive_burden: "Regressive Burden",
  expert_defiance: "Expert Defiance",
  spatial_inconsistency: "Spatial Inconsistency",
  legal_hallucination: "Legal Hallucination",
};

function DashboardContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const q = searchParams.get("q") ?? "";
  const session = searchParams.get("session");
  const tagType = searchParams.get("tag_type");
  const searchActive = q.length >= 2;

  const { data: stats, isError: statsError } = useQuery({
    queryKey: ["stats"],
    queryFn: api.stats,
  });

  const { data: sessions } = useQuery({
    queryKey: ["sessions"],
    queryFn: api.sessions,
  });

  const billsKey = searchActive
    ? ["bills", "search", q]
    : ["bills", { session, tagType }];

  const {
    data: bills,
    isPending: billsPending,
    isError: billsError,
  } = useQuery({
    queryKey: billsKey,
    queryFn: () => {
      if (searchActive) return api.searchBills(q);
      return api.bills({
        session: session ?? undefined,
        tag_type: tagType ?? undefined,
      });
    },
  });

  function updateParam(key: string, value: string | null) {
    const params = new URLSearchParams(Array.from(searchParams.entries()));
    if (value === null || value === "") params.delete(key);
    else params.set(key, value);
    const qs = params.toString();
    router.push(qs ? `/?${qs}` : "/");
  }

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
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { label: "Bills Analyzed", value: stats.bills_analyzed },
            { label: "Copycat Alerts", value: stats.copycat_alerts },
            { label: "CO Bills with Related Text", value: stats.related_co_bills },
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
        <div className="mb-4 flex flex-wrap items-center gap-4">
          <SearchInput />
          <SessionDropdown
            sessions={sessions ?? []}
            current={session}
            onChange={(value) => updateParam("session", value)}
          />
        </div>

        {!searchActive && (
          <FilterChips
            session={session}
            tagType={tagType}
            tagLabels={TAG_LABELS}
            onRemoveSession={() => updateParam("session", null)}
            onRemoveTag={() => updateParam("tag_type", null)}
          />
        )}

        <div aria-live="polite" aria-label="Bills">
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
            <p className="text-slate-400">No bills match the current filters.</p>
          )}

          {bills && bills.length > 0 && (
            <ul className="space-y-2 mt-4">
              {bills.map((bill) => (
                <li key={bill.id}>
                  <Link
                    href={`/bills/${bill.id}`}
                    className="flex items-center justify-between rounded-lg border border-slate-700 bg-slate-800/50 px-4 py-3 hover:border-slate-500 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
                  >
                    <div>
                      <span className="font-mono text-sm text-slate-400">{bill.bill_number}</span>
                      <p className="font-medium text-slate-200">{bill.title}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      {bill.has_related && (
                        <span className="rounded bg-amber-900/60 px-2 py-0.5 text-xs font-semibold text-amber-300">
                          Related
                        </span>
                      )}
                      {bill.copycat_alert && <TagBadge type="source_cloned" />}
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          )}
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
