"use client";

import { useEffect, useRef } from "react";
import { useApprovals, useInvoices } from "@/lib/hooks";
import { toast } from "@/components/Toaster";

/**
 * Watches polling queries for genuinely NEW pending approvals and overdue
 * invoices and surfaces them as toasts.
 *
 * Two real bugs lived here previously:
 *
 * 1. A race between the two effects: `initialized.current` was set inside
 *    the invoices effect at the very end, but the approvals effect read it
 *    at the top. If invoices loaded first (because it polls less or the
 *    network ordered it that way), the approvals effect would see
 *    `initialized=true` on its very first run and fire a toast for EVERY
 *    pending approval that already existed at page load — flooding the
 *    user with hundreds of notifications about historical state.
 *
 * 2. The `seen` sets were re-created on every browser reload. So even
 *    without the race, simply refreshing the page would re-announce every
 *    pending approval one more time.
 *
 * Fix: each watcher tracks its OWN "initialized" flag, and the seen sets
 * are hydrated from / persisted to localStorage so historical state stays
 * silent across page loads.
 */

const APPROVALS_KEY = "buchuchet.alertwatcher.approvals_seen";
const OVERDUE_KEY   = "buchuchet.alertwatcher.overdue_seen";

function loadSet(key: string): Set<string> {
  if (typeof window === "undefined") return new Set();
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return new Set();
    const arr = JSON.parse(raw);
    return new Set(Array.isArray(arr) ? arr : []);
  } catch { return new Set(); }
}

function saveSet(key: string, set: Set<string>): void {
  if (typeof window === "undefined") return;
  // Cap the persisted set to ~1000 entries so it can't grow unbounded
  // across years of normal operation.
  const arr = [...set].slice(-1000);
  try { window.localStorage.setItem(key, JSON.stringify(arr)); }
  catch { /* private mode / quota — ignore */ }
}


export function AlertWatcher() {
  const { data: approvals } = useApprovals();
  const { data: invoices } = useInvoices();

  // Per-watcher "first non-null payload seen" flag. Each effect owns its
  // own flag so they can't race against each other anymore.
  const approvalsInit = useRef(false);
  const invoicesInit = useRef(false);
  const seenApprovals = useRef<Set<string>>(loadSet(APPROVALS_KEY));
  const seenOverdue = useRef<Set<string>>(loadSet(OVERDUE_KEY));

  useEffect(() => {
    if (!approvals) return;
    const pending = approvals.filter((a) => a.status === "PENDING");

    if (!approvalsInit.current) {
      // First payload after page load — silently seed the seen set with
      // everything currently pending so we don't announce historical state.
      pending.forEach((a) => seenApprovals.current.add(a.id));
      saveSet(APPROVALS_KEY, seenApprovals.current);
      approvalsInit.current = true;
      return;
    }

    let changed = false;
    pending.forEach((a) => {
      if (!seenApprovals.current.has(a.id)) {
        seenApprovals.current.add(a.id);
        changed = true;
        toast.warn("Новый запрос на подтверждение", a.summary);
      }
    });
    if (changed) saveSet(APPROVALS_KEY, seenApprovals.current);
  }, [approvals]);

  useEffect(() => {
    if (!invoices) return;
    const overdue = invoices.filter((i) => i.status === "OVERDUE");

    if (!invoicesInit.current) {
      overdue.forEach((i) => seenOverdue.current.add(i.id));
      saveSet(OVERDUE_KEY, seenOverdue.current);
      invoicesInit.current = true;
      return;
    }

    let changed = false;
    overdue.forEach((i) => {
      if (!seenOverdue.current.has(i.id)) {
        seenOverdue.current.add(i.id);
        changed = true;
        toast.error("Счёт просрочен", `${i.number} · ${i.total} ${i.currency}`);
      }
    });
    if (changed) saveSet(OVERDUE_KEY, seenOverdue.current);
  }, [invoices]);

  return null;
}
