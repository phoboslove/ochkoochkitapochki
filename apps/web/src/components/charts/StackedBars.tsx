"use client";

import { cn } from "@/lib/utils";

type Stack = { key: string; value: number; color: string };

export function StackedBars({
  data, height = 130, className,
}: {
  data: { label: string; stacks: Stack[] }[];
  height?: number;
  className?: string;
}) {
  const w = 600;
  const pad = { top: 10, right: 8, bottom: 22, left: 8 };
  const innerH = height - pad.top - pad.bottom;
  const innerW = w - pad.left - pad.right;
  const barW = (innerW / data.length) * 0.65;
  const gap = (innerW / data.length) * 0.35;
  const max = Math.max(1, ...data.map((d) => d.stacks.reduce((s, x) => s + x.value, 0)));

  return (
    <svg viewBox={`0 0 ${w} ${height}`} width="100%" height={height} className={cn("block", className)}>
      <g transform={`translate(${pad.left} ${pad.top})`}>
        {data.map((d, i) => {
          const total = d.stacks.reduce((s, x) => s + x.value, 0);
          let y = innerH;
          const x = i * (barW + gap) + gap / 2;
          return (
            <g key={d.label}>
              {d.stacks.map((s) => {
                const h = (s.value / max) * innerH;
                y -= h;
                return (
                  <rect key={s.key} x={x} y={y} width={barW} height={Math.max(0, h)}
                        rx={2} style={{ fill: s.color }} />
                );
              })}
              <text x={x + barW / 2} y={innerH + 14} textAnchor="middle"
                    className="fill-muted-foreground text-[9px]">{d.label}</text>
              {total > 0 && (
                <text x={x + barW / 2} y={y - 4} textAnchor="middle"
                      className="fill-muted-foreground text-[9px] tabular-nums">{total}</text>
              )}
            </g>
          );
        })}
      </g>
    </svg>
  );
}
