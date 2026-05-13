import type { SnippetItem } from "@/lib/types";

export default function SnippetDiff({ snippet }: { snippet: SnippetItem }) {
  return (
    <div className="grid grid-cols-2 gap-4 rounded-md bg-slate-800 p-4 text-sm">
      <div>
        <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">Colorado</p>
        {snippet.co_context_before && (
          <p className="text-slate-400 italic">{snippet.co_context_before}</p>
        )}
        <p className="my-1 rounded bg-red-900/30 px-2 py-1 text-slate-200 ring-1 ring-red-500/30">
          {snippet.co_match}
        </p>
        {snippet.co_context_after && (
          <p className="text-slate-400 italic">{snippet.co_context_after}</p>
        )}
      </div>
      <div>
        <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">Source</p>
        {snippet.source_context_before && (
          <p className="text-slate-400 italic">{snippet.source_context_before}</p>
        )}
        <p className="my-1 rounded bg-red-900/30 px-2 py-1 text-slate-200 ring-1 ring-red-500/30">
          {snippet.source_match}
        </p>
        {snippet.source_context_after && (
          <p className="text-slate-400 italic">{snippet.source_context_after}</p>
        )}
      </div>
    </div>
  );
}
