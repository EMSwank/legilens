export default function GhostAlert({ matchedBill }: { matchedBill: string | null }) {
  return (
    <div
      role="alert"
      className="rounded-md border border-amber-500/30 bg-amber-900/20 p-3 text-sm text-amber-300"
    >
      <span className="font-semibold">Match verified mathematically</span> against{" "}
      {matchedBill ?? "an external bill"} — source text no longer publicly available.
    </div>
  );
}
