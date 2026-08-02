"use client";

import { Languages } from "lucide-react";
import { LOCALES, useI18n, useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";

/**
 * Two-button toggle for switching UI locale. Lives in Settings → Language.
 * Selection is persisted to localStorage by the Zustand `persist` middleware
 * in [i18n.ts](apps/web/src/lib/i18n.ts), so reloads keep the choice.
 */
export function LanguagePicker() {
  const t = useT();
  const locale = useI18n((s) => s.locale);
  const setLocale = useI18n((s) => s.setLocale);

  return (
    <div className="rounded-md border bg-card p-4 space-y-3">
      <div className="flex items-center gap-2">
        <Languages className="h-4 w-4 text-muted-foreground" />
        <div className="text-sm font-medium">{t("settings.language.title")}</div>
      </div>
      <p className="text-xs text-muted-foreground">{t("settings.language.hint")}</p>

      <div className="flex flex-wrap gap-2">
        {LOCALES.map((l) => {
          const active = locale === l.value;
          return (
            <button
              key={l.value}
              onClick={() => setLocale(l.value)}
              aria-pressed={active}
              className={cn(
                "inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm transition-colors",
                active
                  ? "border-[hsl(var(--brand)/0.4)] bg-[hsl(var(--brand-subtle))] text-foreground"
                  : "border-border text-muted-foreground hover:bg-accent/60 hover:text-foreground",
              )}
            >
              <span className="text-[11px] uppercase tracking-wider tabular-nums">{l.value}</span>
              <span>{l.native}</span>
            </button>
          );
        })}
      </div>

      <p className="text-[11px] text-muted-foreground/80 pt-1 border-t">
        {t("settings.language.note")}
      </p>
    </div>
  );
}
