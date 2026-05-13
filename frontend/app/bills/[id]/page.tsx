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

  const { data: matches, isPending: matchesPending, isError: matchesError } = useQuery({
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
            ) : matchesError ? (
              <div role="alert" className="rounded-md border border-red-800 bg-red-950 px-4 py-3 text-sm text-red-300">
                Failed to load similarity matches.
              </div>
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
