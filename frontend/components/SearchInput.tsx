"use client";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

export default function SearchInput() {
  const router = useRouter();
  const pathname = usePathname();
  const [value, setValue] = useState("");
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isFirstRender = useRef(true);
  const pushRef = useRef(router.push.bind(router));

  useEffect(() => {
    pushRef.current = router.push.bind(router);
  }, [router]);

  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      const q = value.trim();
      pushRef.current(q ? `?q=${encodeURIComponent(q)}` : pathname);
    }, 300);
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [value, pathname]);

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
