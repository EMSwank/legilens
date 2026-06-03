import type { Match } from "@/lib/types";
import PendingBanner from "./PendingBanner";

interface Props {
  match: Match;
}

export default function RelatedBillCard({ match }: Props) {
  return (
    <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="rounded bg-slate-700 px-2 py-0.5 text-xs font-mono text-slate-300">
            {match.matched_bill_number ?? "Unknown"}
          </span>
          <span className="font-semibold text-slate-200">
            {match.matched_bill_title ?? "Unknown Bill"}
          </span>
        </div>
        <span className="text-sm font-bold text-amber-400">
          {match.similarity_score.toFixed(2)}% similar
        </span>
      </div>

      {match.snippet_status === "pending" && <PendingBanner />}
    </div>
  );
}
