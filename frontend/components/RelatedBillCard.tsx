import Link from "next/link";
import type { Match } from "@/lib/types";

export default function RelatedBillCard({ match }: { match: Match }) {
  return (
    <Link
      href={`/bills/${match.matched_bill_id}`}
      className="flex items-center justify-between rounded-lg border border-slate-700 bg-slate-800/50 px-4 py-3 hover:border-amber-500/60 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500"
    >
      <div>
        <span className="font-mono text-sm text-slate-400">{match.matched_bill_number ?? ""}</span>
        <p className="font-medium text-slate-200">{match.matched_bill_title ?? "Untitled Colorado bill"}</p>
      </div>
      <span className="text-sm font-bold text-amber-400">
        {match.similarity_score.toFixed(0)}% shared text
      </span>
    </Link>
  );
}
