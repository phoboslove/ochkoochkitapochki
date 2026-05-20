"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  Search, Receipt, FileText, Users, Activity, Workflow, ShieldCheck,
  Sparkles, Plug, Building2, ArrowRight, Clock,
} from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

type Result = {
  kind: "invoice" | "client" | "document" | "page" | "action" | "recent";
  id: string; label: string; sub?: string; href: string; icon: any;
};

const QUICK_ACTIONS: Result[] = [
  { kind: "page", id: "qa-newinv",  label: "Create invoice with AI", sub: "Open assistant and prefill",
    href: "/assistant?prompt=Create%20invoice%20for%20",  icon: Receipt },
  { kind: "page", id: "qa-upload",  label: "Upload document",        sub: "OCR + parse",
    href: "/documents",     icon: FileText },
  { kind: "page", id: "qa-overdue", label: "Jump to overdue invoices", sub: "Past-due exposure",
    href: "/invoices?status=OVERDUE", icon: Receipt },
  { kind: "page", id: "qa-recov",   label: "Open recovery center",   sub: "Failed workflows",
    href: "/recovery",      icon: Workflow },
  { kind: "page", id: "qa-app",     label: "Review approvals",       sub: "Pending decisions",
    href: "/approvals",     icon: ShieldCheck },
];

const PAGES: Result[] = [
  { kind: "page", id: "p-dash",  label: "Dashboard",   sub: "Operations overview",     href: "/dashboard",     icon: ArrowRight },
  { kind: "page", id: "p-inv",   label: "Invoices",    sub: "All invoices",            href: "/invoices",      icon: Receipt },
  { kind: "page", id: "p-doc",   label: "Documents",   sub: "OCR + parsing",           href: "/documents",     icon: FileText },
  { kind: "page", id: "p-app",   label: "Approvals",   sub: "Pending decisions",       href: "/approvals",     icon: ShieldCheck },
  { kind: "page", id: "p-act",   label: "Activity",    sub: "Operational timeline",    href: "/activity",      icon: Activity },
  { kind: "page", id: "p-ai",    label: "AI Assistant",sub: "Run operational tools",   href: "/assistant",     icon: Sparkles },
  { kind: "page", id: "p-wf",    label: "Workflows",   sub: "Triggers + runs",         href: "/workflows",     icon: Workflow },
  { kind: "page", id: "p-cl",    label: "Clients",     sub: "Counterparties",          href: "/clients",       icon: Users },
  { kind: "page", id: "p-int",   label: "Integrations",sub: "WhatsApp · Telegram",     href: "/integrations",  icon: Plug },
  { kind: "page", id: "p-co",    label: "Business",    sub: "Company configuration",   href: "/settings",      icon: Building2 },
];

const RECENT_KEY = "buchuchet.command.recent";

export function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [focus, setFocus] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const [recent, setRecent] = useState<Result[]>([]);

  useEffect(() => {
    if (!open) return;
    setQ(""); setFocus(0);
    inputRef.current?.focus();
    try { setRecent(JSON.parse(localStorage.getItem(RECENT_KEY) || "[]")); } catch { /* ignore */ }
  }, [open]);

  const { data: search } = useQuery({
    queryKey: ["search", q],
    queryFn: () => api.get<{ keyword: any }>(`/search?q=${encodeURIComponent(q)}`),
    enabled: open && q.trim().length >= 2,
    staleTime: 10_000,
  });

  const results: Result[] = useMemo(() => {
    if (!open) return [];
    const term = q.trim().toLowerCase();
    if (!term) {
      return [
        ...recent,
        ...QUICK_ACTIONS.map((a) => ({ ...a, kind: "action" as const })),
        ...PAGES,
      ];
    }
    const pageHits: Result[] = PAGES.filter((p) =>
      p.label.toLowerCase().includes(term) || (p.sub ?? "").toLowerCase().includes(term),
    );
    const kw = search?.keyword;
    const invs: Result[] = (kw?.invoices ?? []).slice(0, 6).map((i: any) => ({
      kind: "invoice", id: `inv-${i.id}`, label: i.number,
      sub: `${i.status} · ${i.total} ${i.currency}`,
      href: `/invoices/${i.id}`, icon: Receipt,
    }));
    const docs: Result[] = (kw?.documents ?? []).slice(0, 6).map((d: any) => ({
      kind: "document", id: `doc-${d.id}`, label: d.title, sub: `${d.type} · ${d.status}`,
      href: `/documents/${d.id}`, icon: FileText,
    }));
    const cls: Result[] = (kw?.clients ?? []).slice(0, 6).map((c: any) => ({
      kind: "client", id: `cl-${c.id}`, label: c.name, sub: c.bin || c.phone || "",
      href: `/clients`, icon: Users,
    }));
    return [...pageHits, ...invs, ...docs, ...cls];
  }, [open, q, search, recent]);

  const groups = useMemo(() => {
    const byKind: Record<string, Result[]> = {};
    results.forEach((r) => { (byKind[r.kind] ??= []).push(r); });
    return byKind;
  }, [results]);

  const flat = useMemo(() => Object.values(groups).flat(), [groups]);

  const go = (r: Result) => {
    const recent = JSON.parse(localStorage.getItem(RECENT_KEY) || "[]") as Result[];
    const next = [{ ...r, kind: "recent" as const }, ...recent.filter((x) => x.id !== r.id)].slice(0, 5);
    localStorage.setItem(RECENT_KEY, JSON.stringify(next));
    onClose();
    router.push(r.href);
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-start justify-center p-4 sm:pt-[12vh] bg-black/40 animate-fadeIn"
         onClick={onClose}>
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-xl rounded-xl border border-border bg-card shadow-lg overflow-hidden animate-slideIn"
      >
        <div className="flex items-center gap-2 border-b border-border px-3">
          <Search className="h-4 w-4 text-muted-foreground" />
          <input
            ref={inputRef}
            value={q}
            onChange={(e) => { setQ(e.target.value); setFocus(0); }}
            onKeyDown={(e) => {
              if (e.key === "Escape") onClose();
              if (e.key === "ArrowDown") { e.preventDefault(); setFocus((i) => Math.min(flat.length - 1, i + 1)); }
              if (e.key === "ArrowUp")   { e.preventDefault(); setFocus((i) => Math.max(0, i - 1)); }
              if (e.key === "Enter" && flat[focus]) { e.preventDefault(); go(flat[focus]); }
            }}
            placeholder="Search invoices, documents, clients, pages…"
            className="h-12 w-full bg-transparent text-[13px] outline-none placeholder:text-muted-foreground/60"
          />
          <span className="kbd">Esc</span>
        </div>

        <div className="max-h-[55vh] overflow-y-auto py-2">
          {flat.length === 0 && (
            <div className="px-4 py-6 text-center text-xs text-muted-foreground">
              No matches. Try a different query.
            </div>
          )}
          {Object.entries(groups).map(([kind, items]) => (
            <div key={kind} className="mb-1">
              <div className="px-3 py-1 text-[10px] uppercase tracking-wider text-muted-foreground flex items-center gap-1">
                {kind === "recent" && <Clock className="h-3 w-3" />}
                {GROUP_LABEL[kind] ?? kind}
              </div>
              <ul>
                {items.map((r) => {
                  const idx = flat.indexOf(r);
                  const Icon = r.icon;
                  return (
                    <li key={r.id}>
                      <button
                        onMouseEnter={() => setFocus(idx)}
                        onClick={() => go(r)}
                        className={cn(
                          "w-full flex items-center gap-2.5 px-3 py-2 text-[13px] text-left",
                          focus === idx ? "bg-accent" : "hover:bg-accent/50",
                        )}
                      >
                        <Icon className="h-4 w-4 text-muted-foreground" strokeWidth={1.75} />
                        <span className="flex-1 min-w-0">
                          <span className="block truncate">{highlight(r.label, q)}</span>
                          {r.sub && <span className="block text-[11px] text-muted-foreground truncate">{r.sub}</span>}
                        </span>
                        {focus === idx && <span className="kbd">↵</span>}
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </div>

        <div className="flex items-center gap-3 border-t border-border px-3 py-2 text-[10px] text-muted-foreground">
          <span><span className="kbd">↑</span><span className="kbd">↓</span> navigate</span>
          <span><span className="kbd">↵</span> open</span>
          <span><span className="kbd">Esc</span> close</span>
          <span className="ml-auto">Buchuchet command</span>
        </div>
      </div>
    </div>
  );
}

const GROUP_LABEL: Record<string, string> = {
  recent: "Recent", action: "Quick actions", page: "Navigate",
  invoice: "Invoices", document: "Documents", client: "Clients",
};

function highlight(text: string, query: string) {
  const q = query.trim();
  if (!q) return text;
  const i = text.toLowerCase().indexOf(q.toLowerCase());
  if (i === -1) return text;
  return (
    <>
      {text.slice(0, i)}
      <mark className="bg-warning-bg text-[hsl(var(--warning))] rounded px-0.5">{text.slice(i, i + q.length)}</mark>
      {text.slice(i + q.length)}
    </>
  );
}

/** Global keyboard hook — opens palette on Cmd/Ctrl + K. */
export function useCommandPaletteShortcut(open: () => void) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && (e.key === "k" || e.key === "K")) {
        e.preventDefault(); open();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);
}
