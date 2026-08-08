"use client";

import { Check, Clock, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";

const STEPS = [
  { key: "UPLOADED",    label: "Uploaded" },
  { key: "OCR_PENDING", label: "OCR pending" },
  { key: "OCR_DONE",    label: "OCR complete" },
  { key: "PARSED",      label: "Parsed" },
];

export function DocumentStatusTimeline({ status }: { status: string }) {
  const failed = status === "FAILED";
  const idx = STEPS.findIndex((s) => s.key === status);
  return (
    <div className="flex items-center gap-2">
      {STEPS.map((s, i) => {
        const done = !failed && i <= idx;
        const current = !failed && i === idx;
        return (
          <div key={s.key} className="flex items-center gap-2 flex-1">
            <div className={cn(
              "h-6 w-6 rounded-full border flex items-center justify-center text-[10px]",
              done ? "bg-success-bg border-[hsl(var(--success))] text-[hsl(var(--success))]"
                   : current ? "bg-warning-bg border-[hsl(var(--warning))] text-[hsl(var(--warning))]"
                   : "bg-muted border-border text-muted-foreground",
            )}>
              {done ? <Check className="h-3 w-3" /> : current ? <Clock className="h-3 w-3" /> : i + 1}
            </div>
            <span className={cn("text-[11px]", done ? "text-foreground" : "text-muted-foreground")}>{s.label}</span>
            {i < STEPS.length - 1 && <span className={cn("flex-1 h-px", done ? "bg-success-bg" : "bg-border")} />}
          </div>
        );
      })}
      {failed && (
        <span className="ml-2 inline-flex items-center gap-1 text-[hsl(var(--danger))] text-xs">
          <AlertTriangle className="h-3 w-3" /> Failed
        </span>
      )}
    </div>
  );
}
