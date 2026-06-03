import type { Metadata } from "next";
import ShingleDiagram from "@/components/ShingleDiagram";

export const metadata: Metadata = {
  title: "About — LegiLens",
  description:
    "How LegiLens measures the Friction Gap between Colorado legislative rhetoric and reality. MinHash methodology, score interpretation, and friction tag glossary.",
};

const TAGS = [
  {
    name: "Technical Conflict",
    definition: "Mandates that break existing technical standards or architecture.",
    example: "A bill regulating encryption that contradicts established protocols (TLS, POSIX, NIST).",
  },
  {
    name: "Spatial Inconsistency",
    definition: "Proposals that are geographically or logistically impossible.",
    example: "Buffer-zone or land-use rules with measurements that don't fit the affected parcels.",
  },
  {
    name: "Expert Defiance",
    definition: "Disregarding non-partisan expert testimony for intuitive logic.",
    example: "Overriding an ALJ or agency head with a representative's personal anecdote.",
  },
  {
    name: "Regressive Burden",
    definition: "Using flat fees to fund public goods, impacting the majority disproportionately.",
    example: "A new 'enterprise' fee or delivery surcharge instead of a graduated tax.",
  },
  {
    name: "Source-Cloned",
    definition: "Identical to model legislation or bills in 5+ other states.",
    example: "Language matching ALEC-style templates introduced across multiple states.",
  },
  {
    name: "Legal Hallucination",
    definition: "Citing inapplicable legal theories to create delay or obstruction.",
    example: "Frivolous constitutional or contract-law claims raised in committee.",
  },
];

export default function About() {
  return (
    <main id="main" className="mx-auto max-w-3xl px-4 py-12 space-y-10 text-slate-200">
      <header>
        <h1 className="text-4xl font-black tracking-tight text-white">About LegiLens</h1>
        <p className="mt-3 text-slate-400">
          LegiLens measures the Friction Gap in the Colorado General Assembly —
          the distance between what legislators say a bill does and what the
          text and process actually deliver.
        </p>
      </header>

      <section className="space-y-3">
        <h2 className="text-2xl font-bold text-white">What LegiLens measures</h2>
        <p>
          The Influence &amp; Source Tracker (IST) is the launch module. It
          computes cross-state text similarity to identify whether a Colorado
          bill is locally authored or copied from a template circulating in
          other state legislatures.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-2xl font-bold text-white">How MinHash works</h2>
        <p>
          MinHash estimates Jaccard similarity between two sets of text
          fragments. The process has three steps.
        </p>

        <h3 className="text-lg font-semibold text-white pt-2">1. Shingling</h3>
        <p>
          Each bill&apos;s text is broken into overlapping fixed-length word
          sequences called <em>shingles</em>. The diagram below shows 3-shingles
          (three-word windows) of one sentence.
        </p>
        <ShingleDiagram />

        <h3 className="text-lg font-semibold text-white pt-2">2. Jaccard similarity</h3>
        <p>The similarity between two bills is the Jaccard index of their shingle sets:</p>
        <code
          className="block rounded-md bg-slate-900 px-4 py-3 font-mono text-blue-200"
          aria-label="Jaccard similarity formula: J of A and B equals the size of A intersected with B over the size of A unioned with B"
        >
          J(A, B) = |A ∩ B| / |A ∪ B|
        </code>
        <p>
          A value of 1.0 means identical shingle sets; 0.0 means no overlap.
        </p>

        <h3 className="text-lg font-semibold text-white pt-2">3. MinHash + LSH</h3>
        <p>
          Computing exact Jaccard pairwise across 190,000+ bills is O(n²) and
          infeasible. MinHash approximates Jaccard with 128 hash permutations
          per document. Locality-Sensitive Hashing then buckets similar
          signatures together, reducing candidate comparisons to sub-linear
          time.
        </p>

        <h3 className="text-lg font-semibold text-white pt-2">The 0.70 threshold</h3>
        <p>
          A Jaccard similarity of 0.70 or higher flags a likely text-reuse
          match. This threshold was calibrated against known model-bill
          templates (ALEC-style and similar) to maximize precision while
          keeping recall meaningful.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-2xl font-bold text-white">Score interpretation</h2>
        <p>
          Every Colorado bill receives a Source Authenticity Score from 0 to
          100. It is the inverse of cross-state textual overlap.
        </p>
        <ul className="list-disc pl-6 space-y-1">
          <li><strong>0–30:</strong> Copycat alert — most language matches bills in other states.</li>
          <li><strong>31–69:</strong> Partial overlap — some sections appear elsewhere; some original.</li>
          <li><strong>70–100:</strong> Likely original — minimal textual reuse detected.</li>
        </ul>
      </section>

      <section className="space-y-3">
        <h2 className="text-2xl font-bold text-white">Related Colorado Bills</h2>
        <p>
          In addition to cross-state matching, LegiLens identifies Colorado bills that share
          similar language with each other within the same state legislature. These appear on
          bill detail pages as &ldquo;Related Colorado Bills.&rdquo;
        </p>
        <p>
          Related Colorado bills are never counted as a copycat alert. The copycat alert and
          Source Authenticity Score are computed exclusively from cross-state comparisons against
          legislation from other states. Companion bills, reintroductions, and thematically
          related legislation that stays within Colorado do not affect a bill&apos;s IST score.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-2xl font-bold text-white">Friction tag glossary</h2>
        <p>
          When a bill triggers specific patterns, LegiLens applies one or more
          friction tags. Tags are computed independently of the IST score.
        </p>
        <dl className="space-y-4">
          {TAGS.map((tag) => (
            <div key={tag.name}>
              <dt className="font-semibold text-white">{tag.name}</dt>
              <dd className="text-slate-300">
                {tag.definition} <span className="text-slate-400">Example: {tag.example}</span>
              </dd>
            </div>
          ))}
        </dl>
      </section>

      <section className="space-y-3">
        <h2 className="text-2xl font-bold text-white">Data sources</h2>
        <p>
          Bill text and status come from{" "}
          <a href="https://legiscan.com" className="text-blue-300 underline" target="_blank" rel="noopener noreferrer">LegiScan</a>,
          which aggregates legislative data across all 50 U.S. states. LegiLens
          syncs nightly. The corpus exceeds 190,000 bills as of launch.
        </p>
        <p>
          For accessibility information and our WCAG conformance statement, see{" "}
          <a href="/accessibility" className="text-blue-300 underline">Accessibility</a>.
        </p>
      </section>
    </main>
  );
}
