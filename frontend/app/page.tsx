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
