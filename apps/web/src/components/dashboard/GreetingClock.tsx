"use client";

import { useEffect, useState } from "react";

function greetingFor(hour: number): string {
  if (hour >= 5 && hour < 12)  return "Доброе утро";
  if (hour >= 12 && hour < 18) return "Добрый день";
  if (hour >= 18 && hour < 23) return "Добрый вечер";
  return "Доброй ночи";
}

function capitalize(s: string): string {
  return s.length ? s[0].toUpperCase() + s.slice(1) : s;
}

const DATE_FMT = new Intl.DateTimeFormat("ru-RU", {
  weekday: "long", day: "numeric", month: "long", year: "numeric",
});

export function GreetingClock({ name }: { name?: string | null }) {
  // Clock starts null and is only set client-side, in an effect — the server
  // has no idea what time it is on the visitor's clock, so rendering a real
  // time during SSR would just produce a hydration mismatch a moment later.
  const [now, setNow] = useState<Date | null>(null);

  useEffect(() => {
    setNow(new Date());
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const hh = now ? String(now.getHours()).padStart(2, "0") : "";
  const mm = now ? String(now.getMinutes()).padStart(2, "0") : "";
  const ss = now ? String(now.getSeconds()).padStart(2, "0") : "";

  return (
    <div className="surface-tinted surface-spotlight p-6 sm:p-7 flex flex-col justify-between min-h-[176px]">
      <div>
        <h1 className="text-[24px] sm:text-[27px] font-semibold tracking-tight leading-tight">
          {now ? greetingFor(now.getHours()) : "Добрый день"}
          {name ? `, ${name}` : ""}
        </h1>
        {now ? (
          <p className="mt-1.5 text-[13px] text-muted-foreground">
            {capitalize(DATE_FMT.format(now))}
          </p>
        ) : (
          <div className="sk h-[18px] w-40 mt-2" />
        )}
      </div>

      <div className="mt-6 flex items-baseline gap-1">
        {now ? (
          <>
            <span className="text-[44px] sm:text-[52px] font-extralight tabular-nums leading-none tracking-tight">
              {hh}:{mm}
            </span>
            <span
              key={ss}
              className="text-[18px] sm:text-[20px] font-extralight tabular-nums leading-none text-muted-foreground animate-fadeIn"
            >
              :{ss}
            </span>
          </>
        ) : (
          <div className="sk h-[44px] sm:h-[52px] w-40" />
        )}
      </div>
    </div>
  );
}
