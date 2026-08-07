"use client";

import { useEffect, useState } from "react";

const TICKS = Array.from({ length: 12 }, (_, i) => i);

/** Self-ticking SVG analog clock. Every color comes from the design
 * system's CSS variables, so it follows the active theme automatically. */
export function AnalogClock({ size = 120, className, live = true }: {
  size?: number; className?: string;
  /** false renders a fixed classic 10:10 pose and never ticks — for small
   * static previews (e.g. the style-picker popover) that don't need their
   * own running timer. */
  live?: boolean;
}) {
  // Starts null and is only set client-side — same hydration-safety guard
  // as the digital face: the server has no idea what time it is on the
  // visitor's clock.
  const [now, setNow] = useState<Date | null>(null);

  useEffect(() => {
    if (!live) { setNow(new Date(2000, 0, 1, 10, 10, 30)); return; }
    setNow(new Date());
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, [live]);

  const hours = now ? now.getHours() % 12 : 0;
  const minutes = now ? now.getMinutes() : 0;
  const seconds = now ? now.getSeconds() : 0;

  const hourDeg = (hours + minutes / 60) * 30;
  const minuteDeg = (minutes + seconds / 60) * 6;
  // The second hand animates via a CSS transition, which interpolates the
  // raw numeric angle — going 354deg -> 0deg would visibly spin backward
  // through the whole dial once a minute. Using unbounded epoch-based
  // degrees (never resets to 0) keeps every tick a forward step; it
  // renders identically since rotate(720deg) looks the same as rotate(0deg).
  const secondDeg = now ? (now.getTime() / 1000) * 6 : 0;

  const c = 50; // viewBox center

  return (
    <svg
      viewBox="0 0 100 100"
      width={size}
      height={size}
      className={className}
      role="img"
      aria-label={now ? now.toLocaleTimeString("ru-RU") : "Часы"}
    >
      <circle cx={c} cy={c} r={46} fill="hsl(var(--card))" stroke="hsl(var(--border))" strokeWidth={1.5} />

      {TICKS.map((i) => {
        const deg = i * 30;
        const cardinal = i % 3 === 0;
        const rOuter = 42;
        const rInner = cardinal ? 36 : 38.5;
        const x1 = c + rOuter * Math.sin((deg * Math.PI) / 180);
        const y1 = c - rOuter * Math.cos((deg * Math.PI) / 180);
        const x2 = c + rInner * Math.sin((deg * Math.PI) / 180);
        const y2 = c - rInner * Math.cos((deg * Math.PI) / 180);
        return (
          <line
            key={i}
            x1={x1} y1={y1} x2={x2} y2={y2}
            stroke="hsl(var(--muted-foreground))"
            strokeWidth={cardinal ? 2 : 1}
            strokeLinecap="round"
            opacity={cardinal ? 0.9 : 0.5}
          />
        );
      })}

      {now && (
        <>
          {/* Hour hand */}
          <line
            x1={c} y1={c} x2={c} y2={c - 24}
            stroke="hsl(var(--foreground))" strokeWidth={3} strokeLinecap="round"
            transform={`rotate(${hourDeg} ${c} ${c})`}
          />
          {/* Minute hand */}
          <line
            x1={c} y1={c} x2={c} y2={c - 34}
            stroke="hsl(var(--foreground))" strokeWidth={2} strokeLinecap="round"
            transform={`rotate(${minuteDeg} ${c} ${c})`}
          />
          {/* Second hand */}
          <line
            x1={c} y1={c + 6} x2={c} y2={c - 38}
            stroke="hsl(var(--brand))" strokeWidth={1} strokeLinecap="round"
            transform={`rotate(${secondDeg} ${c} ${c})`}
            style={{ transition: "transform 0.2s cubic-bezier(0.4, 2.2, 0.6, 1)" }}
          />
          <circle cx={c} cy={c} r={2.2} fill="hsl(var(--brand))" />
        </>
      )}
    </svg>
  );
}
