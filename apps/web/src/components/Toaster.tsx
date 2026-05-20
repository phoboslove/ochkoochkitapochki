"use client";

import { create } from "zustand";
import { useEffect } from "react";
import { CheckCircle2, AlertTriangle, AlertCircle, Info, X } from "lucide-react";
import { cn } from "@/lib/utils";

type Tone = "success" | "error" | "warn" | "info";
type Toast = { id: number; tone: Tone; title: string; description?: string; ttl: number };

type Store = {
  toasts: Toast[];
  push: (t: Omit<Toast, "id" | "ttl"> & { ttl?: number }) => void;
  remove: (id: number) => void;
};

const useToastStore = create<Store>((set) => ({
  toasts: [],
  push: (t) => set((s) => ({ toasts: [...s.toasts, { id: Date.now() + Math.random(), ttl: 4500, ...t }] })),
  remove: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
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
  return (
    <div className="pointer-events-none fixed right-4 bottom-4 z-50 flex w-[min(360px,calc(100vw-2rem))] flex-col gap-2">
      {toasts.map((t) => <Item key={t.id} t={t} onClose={() => remove(t.id)} />)}
    </div>
  );
}

function Item({ t, onClose }: { t: Toast; onClose: () => void }) {
  useEffect(() => { const id = window.setTimeout(onClose, t.ttl); return () => window.clearTimeout(id); }, [onClose, t.ttl]);
  const Icon = ICONS[t.tone];
  return (
    <div className={cn("pointer-events-auto rounded-md border bg-card p-3 shadow-md animate-slideIn", TONE[t.tone])}>
      <div className="flex items-start gap-2">
        <Icon className="h-4 w-4 mt-0.5 shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium leading-tight">{t.title}</div>
          {t.description && <div className="text-xs opacity-80 mt-0.5">{t.description}</div>}
        </div>
        <button onClick={onClose} className="opacity-60 hover:opacity-100"><X className="h-3.5 w-3.5" /></button>
      </div>
    </div>
  );
}
