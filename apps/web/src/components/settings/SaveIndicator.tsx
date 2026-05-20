"use client";

import { Check, Loader2, CircleDot } from "lucide-react";

export function SaveIndicator({ dirty, saving, savedAt }: {
  dirty: boolean; saving: boolean; savedAt: Date | null;
}) {
  if (saving) return (
    <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
      <Loader2 className="h-3 w-3 animate-spin" /> Saving…
    </span>
  );
  if (dirty) return (
    <span className="inline-flex items-center gap-1.5 text-xs text-amber-600">
      <CircleDot className="h-3 w-3" /> Unsaved
    </span>
  );
  if (savedAt) return (
    <span className="inline-flex items-center gap-1.5 text-xs text-emerald-600">
      <Check className="h-3 w-3" /> Saved {savedAt.toLocaleTimeString()}
    </span>
  );
  return null;
}
