export default function PendingBanner() {
  return (
    <div
      role="status"
      aria-live="polite"
      className="flex items-center gap-2 rounded-md border border-slate-600 bg-slate-800 px-4 py-3 text-sm text-slate-300"
    >
      <span className="motion-safe:animate-spin text-lg" aria-hidden="true">⟳</span>
      <span>
        <span className="font-semibold">Analyzing Cross-State Evidence…</span>{" "}
        Reload the page to check for updated snippets.
      </span>
    </div>
  );
}
