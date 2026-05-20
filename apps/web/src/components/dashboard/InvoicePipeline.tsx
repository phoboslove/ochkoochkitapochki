"use client";

import Link from "next/link";
import { formatKZT } from "@/lib/utils";

const STAGES = [
  { key: "DRAFT",            label: "Draft",     color: "hsl(var(--muted-foreground))" },
  { key: "PENDING_APPROVAL", label: "Pending",   color: "hsl(var(--warning))" },
  { key: "SENT",             label: "Sent",      color: "hsl(var(--info))" },
  { key: "PAID",             label: "Paid",      color: "hsl(var(--success))" },
  { key: "OVERDUE",          label: "Overdue",   color: "hsl(var(--danger))" },
] as const;

export function InvoicePipeline({ invoices }: { invoices: { status: string; total: string }[] }) {
  const buckets = STAGES.map((s) => {
    const items = invoices.filter((i) => i.status === s.key);
    return {
      ...s,
      count: items.length,
      total: items.reduce((sum, i) => sum + Number(i.total), 0),
    };
  });
  const maxCount = Math.max(1, ...buckets.map((b) => b.count));

  return (
    <div className="flex items-stretch gap-2 sm:gap-3 overflow-x-auto pb-1">
      {buckets.map((b, idx) => (
        <Link
          key={b.key}
          href={`/invoices?status=${b.key}`}
          className="group relative flex-1 min-w-[140px] rounded-lg border border-border bg-card px-4 py-3 transition-all duration-150 hover:border-[hsl(var(--brand)/0.4)] hover:-translate-y-[1px] hover:shadow-md"
        >
          <div className="flex items-center gap-2">
            <span className="h-1.5 w-1.5 rounded-full" style={{ background: b.color }} />
            <span className="text-[11px] text-muted-foreground uppercase tracking-wider">{b.label}</span>
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-[20px] font-semibold tabular-nums tracking-tight">{b.count}</span>
            <span className="text-[11px] text-muted-foreground tabular-nums truncate">
              {b.count > 0 ? formatKZT(b.total) : "—"}
            </span>
          </div>
          {/* fill bar */}
          <div className="mt-2 h-[3px] rounded-full bg-subtle overflow-hidden">
            <div className="h-full rounded-full transition-[width] duration-500"
                 style={{ width: `${(b.count / maxCount) * 100}%`, background: b.color, opacity: 0.85 }} />
          </div>
          {/* arrow chevron between */}
          {idx < buckets.length - 1 && (
            <span className="hidden sm:block absolute right-[-9px] top-1/2 -translate-y-1/2 text-muted-foreground/40 select-none z-10">
              ›
            </span>
          )}
        </Link>
      ))}
    </div>
  );
}
