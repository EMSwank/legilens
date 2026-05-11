"use client";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

export default function SearchInput() {
  const router = useRouter();
  const [value, setValue] = useState("");
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      const q = value.trim();
      router.push(q ? `?q=${encodeURIComponent(q)}` : "?");
    }, 300);
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [value, router]);

  return (
    <input
      role="searchbox"
      aria-label="Search bills"
      type="search"
      value={value}
      onChange={(e) => setValue(e.target.value)}
      placeholder="Search bills…"
      className="w-full rounded-lg border border-slate-700 bg-slate-800 px-4 py-2 text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-red-500"
    />
  );
}
