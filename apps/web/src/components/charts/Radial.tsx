"use client";

import { cn } from "@/lib/utils";

/** Thin-stroke radial progress for operational KPIs (OCR confidence, success rate). */
export function Radial({
  value, label, hint, size = 64, stroke = 4, tone = "brand", className,
}: {
  value: number;            // 0..1
  label: string;
  hint?: string;
  size?: number;
  stroke?: number;
  tone?: "brand" | "success" | "warn" | "danger" | "info";
  className?: string;
}) {
  const v = Math.max(0, Math.min(1, value));
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const offset = c * (1 - v);
  const colorVar = tone === "brand" ? "--brand"
                  : tone === "success" ? "--success"
                  : tone === "warn"    ? "--warning"
                  : tone === "danger"  ? "--danger"
                  : "--info";

  return (
    <div className={cn("flex items-center gap-3", className)}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none"
                className="stroke-subtle" strokeWidth={stroke} />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none"
                style={{ stroke: `hsl(var(${colorVar}))`, strokeDasharray: c, strokeDashoffset: offset,
                         transition: "stroke-dashoffset .35s ease-out" }}
                strokeWidth={stroke} strokeLinecap="round"
                transform={`rotate(-90 ${size / 2} ${size / 2})`} />
        <text x={size / 2} y={size / 2 + 4} textAnchor="middle"
              className="fill-foreground text-[11px] font-semibold tabular-nums">
          {Math.round(v * 100)}%
        </text>
      </svg>
      <div className="min-w-0">
        <div className="text-[12px] font-medium leading-tight">{label}</div>
        {hint && <div className="text-[10.5px] text-muted-foreground mt-0.5">{hint}</div>}
      </div>
    </div>
  );
}
