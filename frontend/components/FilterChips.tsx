"use client";

type Props = {
  session: string | null;
  tagType: string | null;
  tagLabels: Record<string, string>;
  onRemoveSession: () => void;
  onRemoveTag: () => void;
};

export default function FilterChips({
  session,
  tagType,
  tagLabels,
  onRemoveSession,
  onRemoveTag,
}: Props) {
  if (!session && !tagType) return null;

  const tagLabel = tagType ? (tagLabels[tagType] ?? tagType) : null;

  return (
    <div className="flex flex-wrap items-center gap-2" role="region" aria-label="Active filters">
      {session && (
        <span className="inline-flex items-center gap-1 rounded-full bg-slate-800 px-3 py-1 text-sm font-semibold text-slate-200 ring-1 ring-slate-600">
          Session: {session}
          <button
            type="button"
            aria-label={`Remove session filter: ${session}`}
            onClick={onRemoveSession}
            className="ml-1 inline-flex h-6 w-6 items-center justify-center rounded-full hover:bg-slate-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-400"
          >
            <span aria-hidden="true">×</span>
          </button>
        </span>
      )}
      {tagType && (
        <span className="inline-flex items-center gap-1 rounded-full bg-slate-800 px-3 py-1 text-sm font-semibold text-slate-200 ring-1 ring-slate-600">
          Tag: {tagLabel}
          <button
            type="button"
            aria-label={`Remove tag filter: ${tagLabel}`}
            onClick={onRemoveTag}
            className="ml-1 inline-flex h-6 w-6 items-center justify-center rounded-full hover:bg-slate-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-400"
          >
            <span aria-hidden="true">×</span>
          </button>
        </span>
      )}
    </div>
  );
}
