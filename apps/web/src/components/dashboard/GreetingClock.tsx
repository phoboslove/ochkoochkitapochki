"use client";

import { useEffect, useRef, useState } from "react";
import { Settings2 } from "lucide-react";
import { AnalogClock } from "@/components/dashboard/AnalogClock";
import { useWorkspace, type ClockStyle } from "@/lib/workspace";
import { cn } from "@/lib/utils";

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

/** Digital HH:MM:SS face — ticks on its own, independent of whatever
 * mounts it, so a second-by-second update never propagates upward. */
function DigitalClockFace({ big = false }: { big?: boolean }) {
  const [now, setNow] = useState<Date | null>(null);

  useEffect(() => {
    setNow(new Date());
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const hh = now ? String(now.getHours()).padStart(2, "0") : "";
  const mm = now ? String(now.getMinutes()).padStart(2, "0") : "";
  const ss = now ? String(now.getSeconds()).padStart(2, "0") : "";

  if (!now) return <div className={cn("sk", big ? "h-[64px] w-56" : "h-[44px] sm:h-[52px] w-40")} />;

  return (
    <div className="flex items-baseline gap-1">
      <span className={cn(
        "font-extralight tabular-nums leading-none tracking-tight",
        big ? "text-[64px] sm:text-[76px]" : "text-[44px] sm:text-[52px]",
      )}>
        {hh}:{mm}
      </span>
      <span
        key={ss}
        className={cn(
          "font-extralight tabular-nums leading-none text-muted-foreground animate-fadeIn",
          big ? "text-[24px] sm:text-[28px]" : "text-[18px] sm:text-[20px]",
        )}
      >
        :{ss}
      </span>
    </div>
  );
}

const STYLE_OPTIONS: { key: ClockStyle; label: string }[] = [
  { key: "digital", label: "Цифровые" },
  { key: "analog",  label: "Аналоговые" },
  { key: "minimal", label: "Минимал" },
];

function ClockStylePicker({ value, onChange, onClose }: {
  value: ClockStyle; onChange: (v: ClockStyle) => void; onClose: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [onClose]);

  return (
    <div
      ref={ref}
      className="surface-elevated absolute right-0 top-9 z-20 p-2 flex gap-1.5 animate-fadeIn"
    >
      {STYLE_OPTIONS.map((opt) => (
        <button
          key={opt.key}
          onClick={() => { onChange(opt.key); onClose(); }}
          className={cn(
            "flex flex-col items-center gap-1.5 rounded-md p-2.5 w-[84px] transition-colors",
            "hover:bg-accent",
            value === opt.key && "bg-accent ring-1 ring-[hsl(var(--brand)/0.4)]",
          )}
        >
          <div className="h-10 flex items-center justify-center">
            {opt.key === "analog" ? (
              <AnalogClock size={38} live={false} />
            ) : opt.key === "minimal" ? (
              <span className="text-[15px] font-extralight tabular-nums">14:32</span>
            ) : (
              <span className="text-[13px] font-extralight tabular-nums">14:32<span className="text-muted-foreground">:07</span></span>
            )}
          </div>
          <span className="text-[10.5px] text-muted-foreground">{opt.label}</span>
        </button>
      ))}
    </div>
  );
}

export function GreetingClock({ name }: { name?: string | null }) {
  const clockStyle = useWorkspace((s) => s.clockStyle);
  const setClockStyle = useWorkspace((s) => s.setClockStyle);
  const [pickerOpen, setPickerOpen] = useState(false);

  // Greeting + date only need to be right, not to the second — computed
  // once on mount (still deferred to a client-only effect for the same
  // hydration-safety reason as the clock faces) rather than re-ticking
  // every second along with the clock.
  const [today, setToday] = useState<Date | null>(null);
  useEffect(() => { setToday(new Date()); }, []);

  if (clockStyle === "minimal") {
    return (
      <div className="group relative surface-tinted p-6 sm:p-7 flex items-center justify-center min-h-[176px]">
        <button
          onClick={() => setPickerOpen((v) => !v)}
          className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 focus-visible:opacity-100 transition-opacity
                     inline-flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground hover:text-foreground hover:bg-accent"
          aria-label="Стиль часов"
        >
          <Settings2 className="h-3.5 w-3.5" />
        </button>
        {pickerOpen && (
          <ClockStylePicker value={clockStyle} onChange={setClockStyle} onClose={() => setPickerOpen(false)} />
        )}
        <DigitalClockFace big />
      </div>
    );
  }

  return (
    <div className="group relative surface-tinted p-6 sm:p-7 flex flex-col justify-between min-h-[176px]">
      <button
        onClick={() => setPickerOpen((v) => !v)}
        className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 focus-visible:opacity-100 transition-opacity
                   inline-flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground hover:text-foreground hover:bg-accent"
        aria-label="Стиль часов"
      >
        <Settings2 className="h-3.5 w-3.5" />
      </button>
      {pickerOpen && (
        <ClockStylePicker value={clockStyle} onChange={setClockStyle} onClose={() => setPickerOpen(false)} />
      )}

      <div>
        <h1 className="text-[24px] sm:text-[27px] font-semibold tracking-tight leading-tight">
          {today ? greetingFor(today.getHours()) : "Добрый день"}
          {name ? `, ${name}` : ""}
        </h1>
        {today ? (
          <p className="mt-1.5 text-[13px] text-muted-foreground">
            {capitalize(DATE_FMT.format(today))}
          </p>
        ) : (
          <div className="sk h-[18px] w-40 mt-2" />
        )}
      </div>

      <div className="mt-6 flex items-end justify-between">
        {clockStyle === "analog" ? <AnalogClock size={72} /> : <DigitalClockFace />}
      </div>
    </div>
  );
}
