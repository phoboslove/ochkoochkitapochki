import { cn } from "@/lib/utils";
import type { LucideIcon } from "lucide-react";

export function StatTile({ label, value, hint, tone = "neutral", icon: Icon }: {
  label: string;
  value: number | string;
  hint?: string;
  tone?: "neutral" | "warn" | "danger" | "success";
  icon?: LucideIcon;
}) {
  return (
    <div className="surface p-5 transition-[transform,box-shadow] duration-200 hover:-translate-y-0.5 hover:shadow-md">
      <div className="flex items-center justify-between gap-2">
        <div className="text-[10.5px] uppercase tracking-wider text-muted-foreground">{label}</div>
        {Icon && (
          <Icon className={cn(
            "h-3.5 w-3.5 shrink-0",
            tone === "danger" ? "text-[hsl(var(--danger))]" :
            tone === "warn"   ? "text-[hsl(var(--warning))]" :
            tone === "success"? "text-[hsl(var(--success))]" : "text-muted-foreground",
          )} />
        )}
      </div>
      <div className={cn(
        "mt-2 text-[30px] font-semibold tabular-nums tracking-tight leading-none",
        tone === "danger" ? "text-[hsl(var(--danger))]" :
        tone === "warn"   ? "text-[hsl(var(--warning))]" :
        tone === "success"? "text-[hsl(var(--success))]" : "",
      )}>
        {value}
      </div>
      {hint && <div className="mt-1.5 text-[11.5px] text-muted-foreground truncate">{hint}</div>}
    </div>
  );
}
