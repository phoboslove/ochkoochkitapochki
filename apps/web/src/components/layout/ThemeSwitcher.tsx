"use client";

import { useEffect, useRef, useState } from "react";
import { useTheme } from "next-themes";
import { Check, Palette } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const THEMES: { key: string; label: string }[] = [
  { key: "light",      label: "Светлая" },
  { key: "dark",       label: "Тёмная" },
  { key: "monochrome", label: "Монохром" },
  { key: "graphite",   label: "Графит и золото" },
  { key: "ivory",      label: "Слоновая кость" },
  { key: "midnight",   label: "Полночь" },
];

/** Live swatch — carries its own data-theme so the CSS variables it reads
 * (background/card/brand) resolve to that theme's real palette, not the
 * page's current one. No hardcoded hex, so it can never drift from
 * globals.css. */
function ThemeSwatch({ themeKey, active, size = 36 }: { themeKey: string; active: boolean; size?: number }) {
  return (
    <span
      data-theme={themeKey}
      style={{ height: size, width: size }}
      className={cn(
        "relative flex shrink-0 items-center justify-center overflow-hidden rounded-full border-2 bg-background transition-colors",
        active ? "border-brand" : "border-border",
      )}
    >
      <span className="absolute bottom-0 right-0 h-[62%] w-[62%] rounded-tl-full bg-card" />
      <span className="absolute rounded-full bg-brand" style={{ height: Math.max(4, size * 0.22), width: Math.max(4, size * 0.22) }} />
    </span>
  );
}

function ThemePicker({ value, onChange, onClose }: {
  value: string | undefined; onChange: (v: string) => void; onClose: () => void;
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
      className="surface-elevated absolute right-0 top-9 z-30 w-[268px] p-2.5 animate-fadeIn"
    >
      <div className="grid grid-cols-3 gap-1">
        {THEMES.map((t) => (
          <button
            key={t.key}
            onClick={() => { onChange(t.key); onClose(); }}
            className={cn(
              "flex flex-col items-center gap-1.5 rounded-md p-2 transition-colors hover:bg-accent",
              value === t.key && "bg-accent",
            )}
          >
            <span className="relative">
              <ThemeSwatch themeKey={t.key} active={value === t.key} />
              {value === t.key && (
                <span className="absolute -bottom-0.5 -right-0.5 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-brand text-brand-foreground">
                  <Check className="h-2.5 w-2.5" strokeWidth={3} />
                </span>
              )}
            </span>
            <span className="text-[10px] leading-tight text-muted-foreground text-center">{t.label}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

export function ThemeSwitcher() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  const [open, setOpen] = useState(false);
  useEffect(() => { setMounted(true); }, []);

  return (
    <div className="relative">
      <Button variant="ghost" size="icon" aria-label="Тема" onClick={() => setOpen((v) => !v)}>
        {mounted
          ? <ThemeSwatch themeKey={theme ?? "dark"} active={false} size={16} />
          : <Palette className="h-4 w-4" />}
      </Button>
      {open && mounted && (
        <ThemePicker value={theme} onChange={setTheme} onClose={() => setOpen(false)} />
      )}
    </div>
  );
}
