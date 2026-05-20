"use client";

import Link from "next/link";
import { AlertTriangle, ShieldCheck, FileWarning, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";

export type PriorityItem = {
  key: string;
  href: string;
  label: string;
  count: number;
  severity: "info" | "warn" | "danger";
  icon?: React.ComponentType<{ className?: string }>;
};

export function PriorityBar({ items }: { items: PriorityItem[] }) {
  const visible = items.filter((i) => i.count > 0);
  if (visible.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-card px-4 py-3 flex items-center gap-2 text-[13px]">
        <span className="h-1.5 w-1.5 rounded-full bg-[hsl(var(--success))]" />
        <span className="text-muted-foreground">All clear — nothing needs your attention right now.</span>
      </div>
    );
  }
  return (
    <div className="rounded-lg border border-border bg-card divide-y divide-border">
      {visible.map((it) => {
        const Icon = it.icon ?? (it.severity === "danger" ? AlertCircle : it.severity === "warn" ? AlertTriangle : FileWarning);
        return (
          <Link
            key={it.key} href={it.href}
            className="flex items-center gap-3 px-4 py-2.5 hover:bg-accent/40 transition-colors group"
          >
            <span className={cn(
              "h-7 w-7 rounded-md grid place-items-center shrink-0",
              it.severity === "danger" ? "bg-danger-bg text-[hsl(var(--danger))]"
              : it.severity === "warn" ? "bg-warning-bg text-[hsl(var(--warning))]"
              : "bg-info-bg text-[hsl(var(--info))]",
            )}>
              <Icon className="h-3.5 w-3.5" strokeWidth={1.75} />
            </span>
            <span className="flex-1 text-[13px] truncate">{it.label}</span>
            <span className="tabular-nums text-[13px] font-medium">{it.count}</span>
            <span className="text-muted-foreground group-hover:text-foreground transition-colors">›</span>
          </Link>
        );
      })}
    </div>
  );
}

export { ShieldCheck };
