const TAG_LABELS: Record<string, string> = {
  source_cloned: "Source-Cloned",
  technical_conflict: "Technical Conflict",
  regressive_burden: "Regressive Burden",
  expert_defiance: "Expert Defiance",
  spatial_inconsistency: "Spatial Inconsistency",
  legal_hallucination: "Legal Hallucination",
};

export default function TagBadge({ type }: { type: string }) {
  return (
    <span className="inline-flex items-center rounded-full bg-red-900/40 px-2.5 py-0.5 text-xs font-medium text-red-300 ring-1 ring-inset ring-red-500/30">
      {TAG_LABELS[type] ?? type}
    </span>
  );
}
