"use client";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";
import type { StateCoverage } from "@/lib/types";

const STATUS_LABEL: Record<StateCoverage["status"], string> = {
  complete: "Complete",
  in_progress: "In progress",
  not_started: "Not started",
};

const STATUS_DOT: Record<StateCoverage["status"], string> = {
  complete: "bg-emerald-400",
  in_progress: "bg-amber-400",
  not_started: "bg-slate-600",
};

function pct(s: StateCoverage): string {
  if (s.fetchable === 0) return "—";
  return `${Math.round((s.with_sig / s.fetchable) * 100)}%`;
}

export default function Coverage() {
  const { data, isPending, isError } = useQuery({
    queryKey: ["coverage"],
    queryFn: api.coverage,
  });

  return (
    <main id="main" className="mx-auto max-w-3xl px-4 py-12 space-y-8 text-slate-200">
      <header>
        <h1 className="text-4xl font-black tracking-tight text-white">Corpus Coverage</h1>
        <p className="mt-3 text-slate-400">
          LegiLens cross-state copycat detection only works where bill text has been
          ingested and fingerprinted. This page tracks progress toward the current
          ingest target — Colorado plus five comparison states (CA, NY, IL, TX, FL).
          Remaining states are queued for a later phase.
        </p>
        <p className="mt-3">
          <Link href="/" className="text-sm text-blue-300 underline hover:text-blue-200">
            ← Back to dashboard
          </Link>
        </p>
      </header>

      {isPending && (
        <div role="status" aria-live="polite" className="text-slate-400">
          Loading coverage…
        </div>
      )}

      {isError && (
        <div role="alert" className="rounded-md border border-red-500/30 bg-red-900/20 p-3 text-red-300">
          Failed to load coverage data.
        </div>
      )}

      {data?.status === "pending" && (
        <div role="status" className="rounded-md border border-slate-700 bg-slate-900 p-4 text-slate-300">
          Coverage is computing — check back after tonight&apos;s ingest run.
        </div>
      )}

      {data?.status === "ready" && (
        <>
          <section aria-labelledby="matchable-heading" className="rounded-lg border border-slate-700 bg-slate-800 p-6">
            <h2 id="matchable-heading" className="text-sm font-semibold uppercase tracking-wide text-slate-400">
              Target corpus matchable
            </h2>
            <p className="mt-1 text-5xl font-black text-white">
              {data.matchable_pct === null ? "—" : `${data.matchable_pct}%`}
            </p>
            <p className="mt-1 text-sm text-slate-400">
              of fetchable bills in Colorado + 5 comparison states have a text fingerprint.
              {data.matchable_pct === null && " No in-scope bills are ingested yet."}
            </p>
            <div
              aria-hidden="true"
              className="mt-4 h-2 w-full overflow-hidden rounded-full bg-slate-700"
            >
              <div
                className="h-full bg-emerald-400"
                style={{ width: `${data.matchable_pct ?? 0}%` }}
              />
            </div>
          </section>

          <section aria-labelledby="states-heading">
            <h2 id="states-heading" className="mb-3 text-lg font-bold text-slate-200">
              Per-state status
            </h2>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <caption className="sr-only">
                  Ingest coverage by state: fetchable bills, matchable percentage, and status.
                </caption>
                <thead>
                  <tr className="border-b border-slate-700 text-slate-400">
                    <th scope="col" className="py-2 pr-4">State</th>
                    <th scope="col" className="py-2 pr-4">Fetchable bills</th>
                    <th scope="col" className="py-2 pr-4">Matchable</th>
                    <th scope="col" className="py-2">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {data.states.map((s) => (
                    <tr key={s.state} className="border-b border-slate-800">
                      <th scope="row" className="py-2 pr-4 font-mono font-semibold text-white">
                        {s.state}
                      </th>
                      <td className="py-2 pr-4 text-slate-300">{s.fetchable.toLocaleString()}</td>
                      <td className="py-2 pr-4 text-slate-300">{pct(s)}</td>
                      <td className="py-2">
                        <span className="inline-flex items-center gap-2">
                          <span aria-hidden="true" className={`h-2.5 w-2.5 rounded-full ${STATUS_DOT[s.status]}`} />
                          {STATUS_LABEL[s.status]}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {data.as_of && (
            <p className="text-xs text-slate-500">
              Snapshot as of {new Date(data.as_of).toLocaleString()}.
            </p>
          )}
        </>
      )}
    </main>
  );
}
