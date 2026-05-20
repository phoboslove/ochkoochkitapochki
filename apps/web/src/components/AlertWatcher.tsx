"use client";

import { useEffect, useRef } from "react";
import { useApprovals, useInvoices } from "@/lib/hooks";
import { toast } from "@/components/Toaster";

/** Watches polling queries for new pending approvals and overdue invoices,
 *  and surfaces them as toast notifications. Lightweight — no websockets yet. */
export function AlertWatcher() {
  const { data: approvals } = useApprovals();
  const { data: invoices } = useInvoices();
  const seenApprovals = useRef<Set<string>>(new Set());
  const seenOverdue = useRef<Set<string>>(new Set());
  const initialized = useRef(false);

  useEffect(() => {
    if (!approvals) return;
    const pending = approvals.filter((a) => a.status === "PENDING");
    if (!initialized.current) {
      pending.forEach((a) => seenApprovals.current.add(a.id));
      return;
    }
    pending.forEach((a) => {
      if (!seenApprovals.current.has(a.id)) {
        seenApprovals.current.add(a.id);
        toast.warn("New approval requested", a.summary);
      }
    });
  }, [approvals]);

  useEffect(() => {
    if (!invoices) return;
    invoices.filter((i) => i.status === "OVERDUE").forEach((i) => {
      if (!seenOverdue.current.has(i.id)) {
        seenOverdue.current.add(i.id);
        if (initialized.current) toast.error("Invoice overdue", `${i.number} · ${i.total} ${i.currency}`);
      }
    });
    initialized.current = true;
  }, [invoices]);

  return null;
}
