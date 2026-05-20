"use client";

import { StatusDot } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export type HealthLevel = "healthy" | "warn" | "degraded" | "critical";

export function HealthStrip({ items }: {
  items: { label: string; value: string; level: HealthLevel; hint?: string }[];
}) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
      {items.map((it) => (
        <div key={it.label} className="rounded-md border border-border bg-card px-3 py-2.5">
          <div className="flex items-center gap-2 mb-1">
            <StatusDot tone={TONE[it.level]} />
            <span className="text-[10.5px] uppercase tracking-wider text-muted-foreground">{it.label}</span>
          </div>
          <div className={cn("text-[14px] font-semibold tabular-nums", LABEL_COLOR[it.level])}>{it.value}</div>
          {it.hint && <div className="text-[10.5px] text-muted-foreground mt-0.5 truncate">{it.hint}</div>}
        </div>
      ))}
    </div>
  );
}

const TONE: Record<HealthLevel, "success" | "warn" | "danger" | "info"> = {
  healthy:  "success",
  warn:     "warn",
  degraded: "warn",
  critical: "danger",
};
const LABEL_COLOR: Record<HealthLevel, string> = {
  healthy:  "",
  warn:     "text-[hsl(var(--warning))]",
  degraded: "text-[hsl(var(--warning))]",
  critical: "text-[hsl(var(--danger))]",
};
