"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const SUGGESTIONS = [
  "Акт выполненных работ для ТОО...",
  "Счёт на оплату",
  "Товарная накладная",
];

export function QuickCreateWidget() {
  const router = useRouter();
  const [value, setValue] = useState("");

  const submit = (text: string) => {
    const trimmed = text.trim();
    if (!trimmed) return;
    router.push(`/assistant?send=${encodeURIComponent(trimmed)}`);
  };

  return (
    <div className="surface-tinted surface-spotlight glow-accent p-6 sm:p-7 flex flex-col justify-between min-h-[176px]">
      <div>
        <div className="inline-flex items-center gap-1.5 text-[11px] font-medium text-[hsl(var(--brand))]">
          <Sparkles className="h-3.5 w-3.5" />
          Создать документ
        </div>
        <p className="mt-1.5 text-[13px] text-muted-foreground">
          Опишите, что нужно — акт, счёт, накладная, доверенность.
        </p>
      </div>

      <form
        onSubmit={(e) => { e.preventDefault(); submit(value); }}
        className="mt-5 flex items-center gap-2"
      >
        <input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Напиши, какой документ нужен..."
          className={cn(
            "h-11 w-full rounded-lg border border-input bg-card px-4 text-[14px] shadow-xs",
            "placeholder:text-muted-foreground/70",
            "transition-[border-color,box-shadow] focus-visible:outline-none",
            "focus-visible:border-[hsl(var(--brand))]",
          )}
        />
        <Button type="submit" size="lg" className="h-11 px-4 shrink-0" aria-label="Отправить">
          <ArrowRight className="h-4 w-4" />
        </Button>
      </form>

      <div className="mt-3 flex flex-wrap gap-1.5">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => submit(s)}
            className="rounded-full border border-border bg-card/60 px-2.5 py-1 text-[11px] text-muted-foreground
                       transition-colors hover:bg-accent hover:text-foreground hover:border-[hsl(var(--brand)/0.4)]"
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}
