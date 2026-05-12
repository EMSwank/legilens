"use client";

import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-slate-900 text-slate-200">
      <h1 className="text-xl font-semibold">Something went wrong</h1>
      <button
        onClick={reset}
        className="rounded bg-slate-700 px-4 py-2 text-sm hover:bg-slate-600 focus-visible:ring-2 focus-visible:ring-slate-400"
      >
        Try again
      </button>
    </main>
  );
}
