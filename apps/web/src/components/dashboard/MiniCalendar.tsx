"use client";

import { cn } from "@/lib/utils";

const WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];

function capitalize(s: string): string {
  return s.length ? s[0].toUpperCase() + s.slice(1) : s;
}

// Date.toISOString() converts to UTC, which silently shifts the date by a
// day for any positive-offset timezone (e.g. Kazakhstan, UTC+5) around local
// midnight — build the key from local date parts instead.
function toLocalIso(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

type Cell = { day: number; inMonth: boolean; iso: string; isToday: boolean };

function buildMonthGrid(ref: Date): Cell[] {
  const year = ref.getFullYear();
  const month = ref.getMonth();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const daysInPrevMonth = new Date(year, month, 0).getDate();
  // getDay(): 0=Sunday..6=Saturday → shift to Monday-first (0=Monday..6=Sunday).
  const firstWeekday = (new Date(year, month, 1).getDay() + 6) % 7;
  const totalCells = Math.ceil((firstWeekday + daysInMonth) / 7) * 7;
  const todayIso = toLocalIso(ref);

  const cells: Cell[] = [];
  for (let i = 0; i < totalCells; i++) {
    const dayNumber = i - firstWeekday + 1;
    // JS Date normalizes out-of-range months (e.g. month -1 → December of the
    // previous year), so passing `month - 1` / `month + 1` straight through
    // resolves the correct adjacent-month date without manual year math.
    let day: number, inMonth: boolean, cellMonth = month;
    if (dayNumber < 1) {
      day = daysInPrevMonth + dayNumber; inMonth = false; cellMonth = month - 1;
    } else if (dayNumber > daysInMonth) {
      day = dayNumber - daysInMonth; inMonth = false; cellMonth = month + 1;
    } else {
      day = dayNumber; inMonth = true;
    }
    const iso = toLocalIso(new Date(year, cellMonth, day));
    cells.push({ day, inMonth, iso, isToday: inMonth && iso === todayIso });
  }
  return cells;
}

export function MiniCalendar({ highlightDates = [] }: { highlightDates?: string[] }) {
  const today = new Date();
  const cells = buildMonthGrid(today);
  const highlighted = new Set(highlightDates);
  const title = today.toLocaleDateString("ru-RU", { month: "long", year: "numeric" });

  return (
    <div className="surface p-5">
      <div className="text-[13px] font-semibold tracking-tight mb-3">{capitalize(title)}</div>
      <div className="grid grid-cols-7 gap-y-1 text-center">
        {WEEKDAYS.map((w) => (
          <div key={w} className="text-[10px] uppercase tracking-wider text-muted-foreground pb-1">{w}</div>
        ))}
        {cells.map((c, i) => (
          <div key={i} className="flex items-center justify-center py-0.5">
            <span
              className={cn(
                "inline-flex h-7 w-7 items-center justify-center rounded-full text-[12.5px] tabular-nums transition-colors",
                !c.inMonth && "text-muted-foreground/35",
                c.inMonth && !c.isToday && !highlighted.has(c.iso) && "text-foreground",
                c.isToday && "bg-[hsl(var(--brand))] text-[hsl(var(--brand-foreground))] font-semibold",
                !c.isToday && c.inMonth && highlighted.has(c.iso) && "bg-[hsl(var(--brand-subtle))] text-[hsl(var(--brand))] font-medium",
              )}
            >
              {c.day}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
