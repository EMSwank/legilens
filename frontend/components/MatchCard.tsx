import type { Match } from "@/lib/types";
import GhostAlert from "./GhostAlert";
import PendingBanner from "./PendingBanner";
import SnippetDiff from "./SnippetDiff";
import CopyButton from "./CopyButton";

interface Props {
  match: Match;
  billNumber: string;
  billState: string;
  istScore: number;
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

      {match.snippet_status === "pending" && <PendingBanner />}

      {match.matched_snippets?.map((s, i) =>
        s.kind === "snippet" ? (
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
