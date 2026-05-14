"use client";

export default function SessionDropdown({
  sessions,
  current,
  onChange,
}: {
  sessions: string[];
  current: string | null;
  onChange: (session: string | null) => void;
}) {
  return (
    <label className="flex items-center gap-2 text-sm text-slate-300">
      <span>Session</span>
      <select
        value={current ?? ""}
        onChange={(e) => onChange(e.target.value || null)}
        className="rounded-md border border-slate-700 bg-slate-900 px-2 py-1 text-slate-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-400"
      >
        <option value="">All sessions</option>
        {sessions.map((s) => (
          <option key={s} value={s}>
            {s}
          </option>
        ))}
      </select>
    </label>
  );
}
