"use client";

import { useEffect } from "react";

export default function GlobalError({
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
    <html>
      <body className="bg-slate-900 text-slate-200">
        <main className="flex min-h-screen flex-col items-center justify-center gap-4">
          <h1 className="text-xl font-semibold">Something went wrong</h1>
          <button
            onClick={unstable_retry}
            className="rounded bg-slate-700 px-4 py-2 text-sm hover:bg-slate-600 focus-visible:ring-2 focus-visible:ring-slate-400"
          >
            Try again
          </button>
        </main>
      </body>
    </html>
  );
}
