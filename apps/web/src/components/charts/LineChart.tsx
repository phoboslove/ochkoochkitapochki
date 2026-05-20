"use client";

import { useMemo, useState } from "react";
import { cn } from "@/lib/utils";

/**
 * Premium finance-grade line chart. Zero deps.
 * Supports compare-series (previous period) and a hover marker.
 */
export function LineChart({
  series,
  compare,
  labels,
  height = 160,
  className,
  yFormat = (v) => Math.round(v).toLocaleString(),
}: {
  series: number[];
  compare?: number[];
  labels?: string[];
  height?: number;
  className?: string;
  yFormat?: (v: number) => string;
}) {
  const w = 600;
  const pad = { top: 12, right: 12, bottom: 22, left: 44 };
  const innerW = w - pad.left - pad.right;
  const innerH = height - pad.top - pad.bottom;

  const all = useMemo(() => [...series, ...(compare ?? [])], [series, compare]);
  const max = Math.max(...all, 1);
  const min = 0;

  const path = useMemo(() => toPath(series, innerW, innerH, max, min), [series, innerW, innerH, max, min]);
  const area = useMemo(() => toArea(series, innerW, innerH, max, min), [series, innerW, innerH, max, min]);
  const cmp  = compare && compare.length
    ? toPath(compare, innerW, innerH, max, min)
    : null;

  const ticks = useMemo(() => yTicks(max, 4), [max]);
  const [hover, setHover] = useState<number | null>(null);

  const onMove = (e: React.MouseEvent<SVGSVGElement>) => {
    const rect = (e.currentTarget as SVGSVGElement).getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * w;
    const i = Math.round(((x - pad.left) / innerW) * (series.length - 1));
    setHover(Math.max(0, Math.min(series.length - 1, i)));
  };

  return (
    <svg
      viewBox={`0 0 ${w} ${height}`}
      width="100%" height={height}
      onMouseMove={onMove} onMouseLeave={() => setHover(null)}
      className={cn("block", className)}
    >
      <defs>
        <linearGradient id="lc-area" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%"  stopColor="hsl(var(--brand))" stopOpacity="0.32" />
          <stop offset="55%" stopColor="hsl(var(--brand))" stopOpacity="0.08" />
          <stop offset="100%" stopColor="hsl(var(--brand))" stopOpacity="0" />
        </linearGradient>
        <linearGradient id="lc-line" x1="0" x2="1" y1="0" y2="0">
          <stop offset="0%" stopColor="hsl(var(--brand))" stopOpacity="0.85" />
          <stop offset="100%" stopColor="hsl(var(--brand))" stopOpacity="1" />
        </linearGradient>
      </defs>

      {/* gridlines */}
      {ticks.map((t, i) => {
        const y = pad.top + innerH - (t / max) * innerH;
        return (
          <g key={i}>
            <line x1={pad.left} x2={pad.left + innerW} y1={y} y2={y}
                  className="stroke-border" strokeDasharray="2 4" />
            <text x={pad.left - 6} y={y + 3} textAnchor="end"
                  className="fill-muted-foreground text-[9px]">{yFormat(t)}</text>
          </g>
        );
      })}

      {/* x-axis labels (sparse) */}
      {labels && labels.map((lab, i) => {
        const step = Math.max(1, Math.floor(labels.length / 6));
        if (i % step !== 0 && i !== labels.length - 1) return null;
        const x = pad.left + (i / Math.max(1, series.length - 1)) * innerW;
        return (
          <text key={i} x={x} y={height - 6} textAnchor="middle"
                className="fill-muted-foreground text-[9px]">{lab}</text>
        );
      })}

      <g transform={`translate(${pad.left} ${pad.top})`}>
        {/* compare (previous period) */}
        {cmp && (
          <path d={cmp} fill="none" className="stroke-muted-foreground/50"
                strokeWidth={1.25} strokeDasharray="3 3" />
        )}
        {/* area + line */}
        <path d={area} fill="url(#lc-area)" />
        <path d={path} fill="none" stroke="url(#lc-line)" strokeWidth={2}
              strokeLinecap="round" strokeLinejoin="round" />

        {/* hover marker */}
        {hover !== null && (
          <>
            {(() => {
              const x = (hover / Math.max(1, series.length - 1)) * innerW;
              const y = innerH - (series[hover] / max) * innerH;
              return (
                <>
                  <line x1={x} x2={x} y1={0} y2={innerH} className="stroke-border" />
                  <circle cx={x} cy={y} r={3.5} className="fill-[hsl(var(--brand))]" />
                  <g transform={`translate(${Math.min(x, innerW - 80)} ${Math.max(0, y - 28)})`}>
                    <rect width="78" height="22" rx="4" className="fill-card stroke-border" />
                    <text x="6" y="14" className="fill-foreground text-[10px] font-medium tabular-nums">
                      {yFormat(series[hover])}
                    </text>
                  </g>
                </>
              );
            })()}
          </>
        )}
      </g>
    </svg>
  );
}

function pointsOf(values: number[], w: number, h: number, max: number, min: number): [number, number][] {
  if (values.length === 0) return [];
  const dx = w / Math.max(1, values.length - 1);
  return values.map((v, i) => {
    const x = i * dx;
    const y = h - ((v - min) / (max - min || 1)) * h;
    return [x, y];
  });
}

// Smooth Catmull-Rom → cubic-bezier conversion for elegant curves.
function toPath(values: number[], w: number, h: number, max: number, min: number): string {
  const p = pointsOf(values, w, h, max, min);
  if (p.length === 0) return "";
  if (p.length === 1) return `M ${p[0][0]} ${p[0][1]}`;
  const t = 0.2; // tension — lower = smoother, but not loopy
  let d = `M ${p[0][0].toFixed(2)} ${p[0][1].toFixed(2)}`;
  for (let i = 0; i < p.length - 1; i++) {
    const p0 = p[i - 1] ?? p[i];
    const p1 = p[i];
    const p2 = p[i + 1];
    const p3 = p[i + 2] ?? p2;
    const c1x = p1[0] + (p2[0] - p0[0]) * t;
    const c1y = p1[1] + (p2[1] - p0[1]) * t;
    const c2x = p2[0] - (p3[0] - p1[0]) * t;
    const c2y = p2[1] - (p3[1] - p1[1]) * t;
    d += ` C ${c1x.toFixed(2)} ${c1y.toFixed(2)} ${c2x.toFixed(2)} ${c2y.toFixed(2)} ${p2[0].toFixed(2)} ${p2[1].toFixed(2)}`;
  }
  return d;
}

function toArea(values: number[], w: number, h: number, max: number, min: number): string {
  const path = toPath(values, w, h, max, min);
  if (!path) return "";
  return `${path} L ${w} ${h} L 0 ${h} Z`;
}

function yTicks(max: number, n: number): number[] {
  if (max <= 0) return [0];
  const step = niceStep(max / n);
  const out: number[] = [];
  for (let v = 0; v <= max + step / 2; v += step) out.push(v);
  return out;
}
function niceStep(raw: number): number {
  const exp = Math.floor(Math.log10(raw));
  const base = Math.pow(10, exp);
  const f = raw / base;
  if (f < 1.5) return 1 * base;
  if (f < 3)   return 2 * base;
  if (f < 7.5) return 5 * base;
  return 10 * base;
}
