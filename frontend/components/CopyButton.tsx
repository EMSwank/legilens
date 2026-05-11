"use client";
import { useState } from "react";

interface CopyButtonProps {
  billNumber: string;
  state: string;
  coMatch: string;
  matchedBill: string;
  matchedState: string;
  sourceMatch: string;
  score: number;
}

export default function CopyButton({
  billNumber, state, coMatch, matchedBill, matchedState, sourceMatch, score,
}: CopyButtonProps) {
  const [copied, setCopied] = useState(false);

  const text = [
    `[${state} ${billNumber}] "${coMatch}"`,
    `[${matchedState} ${matchedBill}] "${sourceMatch}"`,
    `Source Authenticity Score: ${score.toFixed(2)} — LegiLens.co`,
  ].join("\n");

  async function handleCopy() {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <>
      <button
        onClick={handleCopy}
        className="rounded bg-slate-700 px-3 py-1 text-xs text-slate-300 hover:bg-slate-600 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
      >
        {copied ? "Copied!" : "Copy to Clipboard"}
      </button>
      <span role="status" aria-live="polite" className="sr-only">
        {copied ? "Copied to clipboard" : ""}
      </span>
    </>
  );
}
