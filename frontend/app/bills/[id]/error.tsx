"use client";

import Link from "next/link";
import { useEffect } from "react";

export default function BillDetailError({
  error,
  unstable_retry,
}: {
  error: Error & { digest?: string };
  unstable_retry: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <main id="main" className="flex min-h-screen flex-col items-center justify-center gap-4 bg-slate-900 text-slate-200">
      <h1 className="text-xl font-semibold">Failed to load bill</h1>
      <div className="flex gap-3">
        <button
          onClick={unstable_retry}
          className="rounded bg-slate-700 px-4 py-2 text-sm hover:bg-slate-600 focus-visible:ring-2 focus-visible:ring-slate-400"
        >
          Try again
        </button>
        <Link
          href="/"
          className="rounded bg-slate-700 px-4 py-2 text-sm hover:bg-slate-600 focus-visible:ring-2 focus-visible:ring-slate-400"
        >
          Back to dashboard
        </Link>
      </div>
    </main>
  );
}
