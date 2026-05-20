"use client";

/** Tiny zero-dep SVG sparkline / bar chart. Avoids pulling recharts at runtime. */
export function Sparkline({ values, height = 36 }: { values: number[]; height?: number }) {
  if (values.length === 0) return <div style={{ height }} />;
  const max = Math.max(...values, 1);
  const w = 200, gap = 4, bw = (w - gap * (values.length - 1)) / values.length;
  return (
    <svg width="100%" viewBox={`0 0 ${w} ${height}`} preserveAspectRatio="none" className="block">
      {values.map((v, i) => {
        const h = (v / max) * (height - 2);
        return (
          <rect key={i} x={i * (bw + gap)} y={height - h} width={bw} height={h}
                className="fill-[hsl(var(--brand)/0.7)]" rx={1} />
        );
      })}
    </svg>
  );
}
