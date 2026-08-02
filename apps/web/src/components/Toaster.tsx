"use client";

import { create } from "zustand";
import { memo, useEffect } from "react";
import {
  CheckCircle2, AlertTriangle, AlertCircle, Info, X, Bell, Trash2,
} from "lucide-react";
import { cn } from "@/lib/utils";

type Tone = "success" | "error" | "warn" | "info";
type Toast = {
  id: string;
  tone: Tone;
  title: string;
  description?: string;
  ttl: number;
  /** Composite signature used to dedupe identical events fired in rapid
   *  succession (e.g. an alert watcher re-firing on every poll). */
  dedupeKey: string;
  /** ms-since-epoch at creation — for max-age cleanup on tab return. */
  createdAt: number;
};

/** Maximum number of toasts kept in the store. Anything beyond this is
 *  dropped FIFO so a bursty event (approval list re-fired by AlertWatcher)
 *  can't lock up the UI with 200+ overlay nodes. */
const MAX_TOASTS = 20;
/** Same dedupe key fired within this window is silently dropped. */
const DEDUPE_WINDOW_MS = 2000;
/** Toasts older than this on the next mount are auto-removed (e.g. user
 *  was away from the tab for an hour and 200 timers all want to fire). */
const STALE_AFTER_MS = 30_000;


// ── Stable unique-id generator ─────────────────────────────────────────────
//
// `Date.now() + Math.random()` was the original bug: JS numbers carry only
// ~15-17 significant decimal digits, so adding a 13-digit timestamp to a
// 0.x random eats almost all the randomness — repeated calls within the
// same ms collide, breaking React's key invariant. Use crypto.randomUUID
// where available (modern browsers, Node 19+), fall back to a monotonic
// counter combined with timestamp for older environments.

let _counter = 0;
function newId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  _counter = (_counter + 1) & 0x7fff_ffff;
  // `${ts}-${counter}-${random}` — counter alone guarantees uniqueness even
  // when called synchronously within a single ms; the random suffix just
  // adds entropy in case crypto.getRandomValues isn't available either.
  return `t${Date.now().toString(36)}-${_counter.toString(36)}-${
    Math.floor((Math.random() || 0) * 0x7fff_ffff).toString(36)
  }`;
}


type Store = {
  toasts: Toast[];
  push: (t: Omit<Toast, "id" | "ttl" | "dedupeKey" | "createdAt"> & { ttl?: number }) => void;
  remove: (id: string) => void;
  clearAll: () => void;
};

const useToastStore = create<Store>((set, get) => ({
  toasts: [],

  push: (input) => {
    const dedupeKey = `${input.tone}|${input.title}|${input.description ?? ""}`;
    const now = Date.now();
    const recent = get().toasts.find(
      (t) => t.dedupeKey === dedupeKey && now - t.createdAt < DEDUPE_WINDOW_MS,
    );
    if (recent) return;  // Silent drop of a near-duplicate burst.

    const next: Toast = {
      id: newId(),
      tone: input.tone,
      title: input.title,
      description: input.description,
      ttl: input.ttl ?? 4500,
      dedupeKey,
      createdAt: now,
    };

    set((s) => {
      // Drop stale ones first (covers the "tab woke up after an hour" case)
      // then enforce MAX_TOASTS by chopping the head — FIFO eviction.
      const fresh = s.toasts.filter((t) => now - t.createdAt < STALE_AFTER_MS);
      const trimmed = fresh.length >= MAX_TOASTS
        ? fresh.slice(fresh.length - (MAX_TOASTS - 1))
        : fresh;
      return { toasts: [...trimmed, next] };
    });
  },

  remove: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
  clearAll: () => set({ toasts: [] }),
}));


export const toast = {
  success: (title: string, description?: string) => useToastStore.getState().push({ tone: "success", title, description }),
  error:   (title: string, description?: string) => useToastStore.getState().push({ tone: "error",   title, description, ttl: 7000 }),
  warn:    (title: string, description?: string) => useToastStore.getState().push({ tone: "warn",    title, description }),
  info:    (title: string, description?: string) => useToastStore.getState().push({ tone: "info",    title, description }),
};


const ICONS: Record<Tone, any> = { success: CheckCircle2, error: AlertCircle, warn: AlertTriangle, info: Info };
const TONE: Record<Tone, string> = {
  success: "border-[hsl(var(--success)/0.3)] bg-success-bg text-[hsl(var(--success))]",
  error:   "border-[hsl(var(--danger)/0.3)]  bg-danger-bg  text-[hsl(var(--danger))]",
  warn:    "border-[hsl(var(--warning)/0.3)] bg-warning-bg text-[hsl(var(--warning))]",
  info:    "border-[hsl(var(--info)/0.3)]    bg-info-bg    text-[hsl(var(--info))]",
};


export function Toaster() {
  const toasts = useToastStore((s) => s.toasts);
  const remove = useToastStore((s) => s.remove);
  const clearAll = useToastStore((s) => s.clearAll);

  return (
    <div className="pointer-events-none fixed right-4 bottom-4 z-50 flex w-[min(360px,calc(100vw-2rem))] flex-col gap-2">
      {toasts.length >= 3 && (
        <div className="pointer-events-auto self-end flex items-center gap-2 rounded-md border bg-card/90 px-2.5 py-1 text-[11px] text-muted-foreground shadow-sm backdrop-blur">
          <Bell className="h-3 w-3" />
          <span className="tabular-nums">{toasts.length}</span>
          <button
            onClick={clearAll}
            className="inline-flex items-center gap-1 hover:text-foreground"
            aria-label="Очистить все уведомления"
          >
            <Trash2 className="h-3 w-3" /> Очистить все
          </button>
        </div>
      )}
      {toasts.map((t) => (
        <Item key={t.id} t={t} onClose={() => remove(t.id)} />
      ))}
    </div>
  );
}


const Item = memo(function Item({ t, onClose }: { t: Toast; onClose: () => void }) {
  useEffect(() => {
    const id = window.setTimeout(onClose, t.ttl);
    return () => window.clearTimeout(id);
  }, [onClose, t.ttl]);

  const Icon = ICONS[t.tone];
  return (
    <div className={cn(
      "pointer-events-auto rounded-md border bg-card p-3 shadow-md animate-slideIn",
      TONE[t.tone],
    )}>
      <div className="flex items-start gap-2">
        <Icon className="h-4 w-4 mt-0.5 shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium leading-tight">{t.title}</div>
          {t.description && <div className="text-xs opacity-80 mt-0.5">{t.description}</div>}
        </div>
        <button
          onClick={onClose}
          className="opacity-60 hover:opacity-100"
          aria-label="Закрыть"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
});
