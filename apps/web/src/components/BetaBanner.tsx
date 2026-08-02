"use client";

import { useEffect, useState } from "react";
import { X, Info } from "lucide-react";

const DISMISS_KEY = "buchuchet.beta_banner.dismissed_at";
const REAPPEAR_AFTER_DAYS = 7;

/**
 * Single global banner shown above the app shell during the closed beta.
 * Operator-facing copy is intentionally Russian — this is what we agreed to
 * ship for the RU-only closed beta. Banner is dismissible per browser; it
 * re-surfaces after a week so a returning user is reminded.
 */
export function BetaBanner() {
  const [hidden, setHidden] = useState(true);  // start hidden to avoid SSR flash

  useEffect(() => {
    if (typeof window === "undefined") return;
    const raw = window.localStorage.getItem(DISMISS_KEY);
    const dismissedAt = raw ? Number(raw) : 0;
    const ageDays = (Date.now() - dismissedAt) / 86_400_000;
    setHidden(dismissedAt > 0 && ageDays < REAPPEAR_AFTER_DAYS);
  }, []);

  if (hidden) return null;

  const dismiss = () => {
    try { window.localStorage.setItem(DISMISS_KEY, String(Date.now())); }
    catch { /* private mode — fine */ }
    setHidden(true);
  };

  return (
    <div className="flex items-start gap-3 border-b border-amber-500/30 bg-amber-500/10 px-4 py-2 text-[12.5px] text-foreground">
      <Info className="h-4 w-4 mt-0.5 text-amber-500 shrink-0" />
      <div className="flex-1">
        <b>Бета-версия.</b>{" "}
        Сейчас система поддерживает русский язык. Казахская локализация
        находится в разработке.
      </div>
      <button
        onClick={dismiss}
        aria-label="Скрыть"
        className="opacity-60 hover:opacity-100 transition-opacity p-0.5"
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}
