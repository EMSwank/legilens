import type { BillDetail } from "@/lib/types";

export default function BillHeader({ bill }: { bill: BillDetail }) {
  return (
    <div className="space-y-2">
      <p className="font-mono text-sm text-slate-400">{bill.bill_number}</p>
      <h1 className="text-2xl font-bold text-slate-100">{bill.title}</h1>
      <div className="flex items-center gap-2 text-sm text-slate-400">
        <span>{bill.state}</span>
        <span aria-hidden="true">·</span>
        <span>{bill.session}</span>
        {bill.status && (
          <>
            <span aria-hidden="true">·</span>
            <span className="inline-flex items-center rounded-full bg-blue-900/40 px-2.5 py-0.5 text-xs font-medium text-blue-300 ring-1 ring-inset ring-blue-500/30">
              {bill.status}
            </span>
          </>
        )}
      </div>
    </div>
  );
}
