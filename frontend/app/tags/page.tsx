"use client";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";

const TAG_META: Record<string, { label: string; description: string }> = {
  source_cloned: {
    label: "Source-Cloned",
    description: "Identical to model legislation or bills in 5+ other states.",
  },
  technical_conflict: {
    label: "Technical Conflict",
    description: "Mandates that break existing technical standards or architecture.",
  },
  regressive_burden: {
    label: "Regressive Burden",
    description: "Flat fees that disproportionately impact the majority.",
  },
  expert_defiance: {
    label: "Expert Defiance",
    description: "Disregards non-partisan expert testimony for intuitive logic.",
  },
  spatial_inconsistency: {
    label: "Spatial Inconsistency",
    description: "Proposals that are geographically or logistically impossible.",
  },
  legal_hallucination: {
    label: "Legal Hallucination",
    description: "Cites inapplicable legal theories to create delay or obstruction.",
  },
};

export default function Tags() {
  const { data, isPending, isError } = useQuery({
    queryKey: ["tags"],
    queryFn: api.tags,
  });

  return (
    <main id="main" className="mx-auto max-w-3xl px-4 py-12 space-y-8 text-slate-200">
      <header>
        <h1 className="text-4xl font-black tracking-tight text-white">Friction Tags</h1>
        <p className="mt-3 text-slate-400">
          When a Colorado bill triggers a specific pattern, LegiLens applies a
          friction tag. Click a tag to see the bills it covers.
        </p>
      </header>

      {isPending && (
        <div role="status" aria-live="polite" className="text-slate-400">
          Loading tags…
        </div>
      )}

      {isError && (
        <div role="alert" className="rounded-md border border-red-500/30 bg-red-900/20 p-3 text-red-300">
          Failed to load tags.
        </div>
      )}

      {data && data.length === 0 && (
        <p className="text-slate-400">No tags yet. Check back after the next analysis run.</p>
      )}

      {data && data.length > 0 && (
        <ul className="space-y-3">
          {data.map((t) => {
            const meta = TAG_META[t.tag_type] ?? { label: t.tag_type, description: "" };
            return (
              <li key={t.tag_type}>
                <Link
                  href={`/?tag_type=${encodeURIComponent(t.tag_type)}`}
                  className="flex flex-col gap-1 rounded-md border border-slate-700 bg-slate-900 p-4 hover:bg-slate-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-400"
                >
                  <span className="flex items-center justify-between">
                    <span className="font-semibold text-white">{meta.label}</span>
                    <span className="text-sm text-slate-400">{t.count} bills</span>
                  </span>
                  {meta.description && (
                    <span className="text-sm text-slate-300">{meta.description}</span>
                  )}
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </main>
  );
}
