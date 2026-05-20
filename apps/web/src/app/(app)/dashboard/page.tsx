"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge, StatusDot } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/EmptyState";
import { LineChart } from "@/components/charts/LineChart";
import { StackedBars } from "@/components/charts/StackedBars";
import { Radial } from "@/components/charts/Radial";
import { InvoicePipeline } from "@/components/dashboard/InvoicePipeline";
import { HealthStrip, type HealthLevel } from "@/components/dashboard/HealthStrip";
import { PriorityBar, type PriorityItem } from "@/components/dashboard/PriorityBar";
import { AnomalyCard } from "@/components/AnomalyCard";
import { WhatsAppSimulator } from "@/components/WhatsAppSimulator";
import {
  useApprovals, useAuditLog, useDecideApproval, useInvoices, useSeedDemo,
  useOperationalMetrics,
} from "@/lib/hooks";
import { formatKZT, cn } from "@/lib/utils";
import {
  Check, X, Sparkles, AlertTriangle, ShieldCheck, FileWarning,
  ArrowUpRight, ArrowDownRight, TrendingUp,
} from "lucide-react";
import { toast } from "@/components/Toaster";

type Period = 7 | 30 | 90;

export default function DashboardPage() {
  const { data: invoices, isLoading: invLoading } = useInvoices();
  const { data: approvals, isLoading: appLoading } = useApprovals();
  const { data: logs } = useAuditLog();
  const { data: ops } = useOperationalMetrics();
  const decide = useDecideApproval();
  const seed = useSeedDemo();
  const [period, setPeriod] = useState<Period>(30);

  const safe = useMemo(() => ({
    invoices:  invoices  ?? [],
    approvals: approvals ?? [],
    logs:      logs      ?? [],
  }), [invoices, approvals, logs]);

  const initialLoading = (invLoading && !invoices) || (appLoading && !approvals);
  const isEmpty = !initialLoading && safe.invoices.length === 0 && safe.approvals.length === 0;

  const stats = useMemo(() => {
    const inv = safe.invoices;
    const revenuePaidSent = sumBy(inv, (i) => (i.status === "PAID" || i.status === "SENT") ? Number(i.total) : 0);
    const outstanding     = sumBy(inv, (i) => ["DRAFT","PENDING_APPROVAL","SENT","OVERDUE"].includes(i.status) ? Number(i.total) : 0);
    const overdueAmount   = sumBy(inv, (i) => i.status === "OVERDUE" ? Number(i.total) : 0);
    const paid            = sumBy(inv, (i) => i.status === "PAID" ? Number(i.total) : 0);
    return {
      revenuePaidSent, outstanding, overdueAmount, paid,
      open:     inv.filter((i) => i.status !== "PAID" && i.status !== "CANCELLED").length,
      overdue:  inv.filter((i) => i.status === "OVERDUE").length,
      pending:  safe.approvals.filter((a) => a.status === "PENDING").length,
    };
  }, [safe]);

  const { current, previous, labels } = useMemo(() => buildSeries(safe.invoices, period), [safe.invoices, period]);
  const trendDelta = useMemo(() => {
    const c = current.reduce((a, b) => a + b, 0);
    const p = previous.reduce((a, b) => a + b, 0);
    if (p === 0) return null;
    return Math.round(((c - p) / p) * 100);
  }, [current, previous]);

  const volumeData = useMemo(() => buildVolume(safe.invoices, Math.min(period, 14)), [safe.invoices, period]);

  const approvalStats = useMemo(() => {
    const decided  = safe.approvals.filter((a) => a.status !== "PENDING");
    const rejected = safe.approvals.filter((a) => a.status === "REJECTED");
    const avgSec   = ops?.approvals?.avg_latency_seconds ?? null;
    return {
      pending:   stats.pending,
      decided:   decided.length,
      rejectPct: decided.length ? Math.round((rejected.length / decided.length) * 100) : 0,
      avgMin:    avgSec != null ? Math.max(1, Math.round(avgSec / 60)) : null,
    };
  }, [safe.approvals, ops, stats.pending]);

  const priorities = useMemo<PriorityItem[]>(() => [
    { key: "pending",  count: stats.pending,  href: "/approvals",
      label: `${stats.pending} approval${stats.pending === 1 ? "" : "s"} waiting on you`,
      severity: "warn", icon: ShieldCheck },
    { key: "overdue",  count: stats.overdue,  href: "/invoices",
      label: `${stats.overdue} overdue invoice${stats.overdue === 1 ? "" : "s"} · ${formatKZT(stats.overdueAmount)}`,
      severity: "danger" },
    { key: "failures", count: ops?.workflows?.failures ?? 0, href: "/recovery",
      label: `${ops?.workflows?.failures ?? 0} failed workflow step${(ops?.workflows?.failures ?? 0) === 1 ? "" : "s"} need recovery`,
      severity: "danger", icon: FileWarning },
    { key: "lowconf",  count: ops?.ocr?.needs_review ?? 0, href: "/documents",
      label: `${ops?.ocr?.needs_review ?? 0} document${(ops?.ocr?.needs_review ?? 0) === 1 ? "" : "s"} flagged for review`,
      severity: "warn", icon: AlertTriangle },
  ], [stats, ops]);

  const health: { label: string; value: string; level: HealthLevel; hint?: string }[] = useMemo(() => {
    const ocrSuccess = ops?.ocr ? Math.round((1 - (ops.ocr.failure_rate ?? 0)) * 100) : 100;
    const wfSuccess  = ops?.workflows?.success_rate != null ? Math.round(ops.workflows.success_rate * 100) : 100;
    return [
      { label: "OCR Pipeline",  value: `${ocrSuccess}%`,
        level: ocrSuccess >= 95 ? "healthy" : ocrSuccess >= 85 ? "warn" : "critical",
        hint:  `${ops?.ocr?.documents_total ?? 0} docs (30d)` },
      { label: "Workflows",     value: `${wfSuccess}%`,
        level: wfSuccess >= 95 ? "healthy" : wfSuccess >= 85 ? "warn" : "critical",
        hint:  `${ops?.workflows?.failures ?? 0} failures` },
      { label: "Integrations",  value: "operational", level: "healthy", hint: "WhatsApp · Telegram" },
      { label: "Notifications", value: "delivered",   level: "healthy", hint: "email · in-app" },
    ];
  }, [ops]);

  return (
    <>
      <PageHeader
        eyebrow="Operations"
        title="Today at a glance"
        description="Live operational visibility — what needs attention, what's healthy, what changed."
        actions={
          isEmpty ? (
            <Button size="sm" disabled={seed.isPending}
              onClick={() => seed.mutate(undefined, {
                onSuccess: (r) => toast.success(r.already_seeded ? "Already loaded" : "Demo loaded"),
              })}>Load demo data</Button>
          ) : null
        }
      />

      {initialLoading ? (
        <LoadingShell />
      ) : isEmpty ? (
        <EmptyState
          icon={Sparkles}
          title="Operations console is ready"
          description="Populate the dashboard with realistic operational data in one click, or open the AI assistant to start your first invoice."
          action={<Button onClick={() => seed.mutate(undefined)}>Load demo data</Button>}
          secondary={<Link href="/assistant"><Button variant="outline">Open AI assistant</Button></Link>}
        />
      ) : (
        <div className="space-y-7 animate-fadeIn">
          <PriorityBar items={priorities} />

          {/* ─── Hero KPI row ─── */}
          <div className="grid grid-cols-1 lg:grid-cols-[1.4fr_1fr_1fr_1fr] gap-3 lg:gap-4">
            <HeroKpi
              label="Revenue · sent + paid"
              value={formatKZT(stats.revenuePaidSent)}
              delta={trendDelta}
              period={period} setPeriod={setPeriod}
              series={current} compare={previous} labels={labels}
            />
            <SupportKpi label="Outstanding" value={formatKZT(stats.outstanding)}
              sub={`${stats.open} open invoice${stats.open === 1 ? "" : "s"}`} />
            <SupportKpi label="Overdue exposure" value={formatKZT(stats.overdueAmount)}
              tone={stats.overdue > 0 ? "danger" : "neutral"} sub={`${stats.overdue} past due`} />
            <SupportKpi label="Approvals queue" value={String(stats.pending)}
              tone={stats.pending > 0 ? "warn" : "neutral"}
              sub={approvalStats.avgMin ? `avg ${approvalStats.avgMin}m to decide` : "no decisions yet"} />
          </div>

          <section>
            <SectionTitle title="Invoice pipeline" hint="Status flow · click to drill down" />
            <InvoicePipeline invoices={safe.invoices.map((i) => ({ status: i.status, total: i.total }))} />
          </section>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle>Invoice volume</CardTitle>
                <p className="mt-1 text-[11px] text-muted-foreground">Last {Math.min(period, 14)} days · by status</p>
              </CardHeader>
              <CardContent className="pt-0">
                {volumeData.length > 0 && volumeData.some((d) => d.stacks.some((s) => s.value > 0))
                  ? <StackedBars data={volumeData} height={170} />
                  : <EmptyChart label="No invoices in this period yet." />}
                <Legend items={[
                  { color: "hsl(var(--success))", label: "Paid" },
                  { color: "hsl(var(--info))",    label: "Sent" },
                  { color: "hsl(var(--warning))", label: "Pending approval" },
                  { color: "hsl(var(--danger))",  label: "Overdue" },
                ]} />
              </CardContent>
            </Card>

            <Card>
              <CardHeader><CardTitle>Cashflow snapshot</CardTitle></CardHeader>
              <CardContent className="pt-0 space-y-4">
                <CashRow label="Paid"             value={stats.paid}          tone="success" total={stats.paid + stats.outstanding} />
                <CashRow label="Outstanding"      value={stats.outstanding}   tone="info"    total={stats.paid + stats.outstanding} />
                <CashRow label="Overdue exposure" value={stats.overdueAmount} tone="danger"  total={stats.paid + stats.outstanding} />
                <div className="pt-3 mt-2 border-t border-border flex items-center justify-between text-[12.5px]">
                  <span className="text-muted-foreground">Collection rate</span>
                  <span className="tabular-nums font-medium text-[14px]">
                    {stats.paid + stats.outstanding === 0 ? "—"
                      : `${Math.round((stats.paid / (stats.paid + stats.outstanding)) * 100)}%`}
                  </span>
                </div>
              </CardContent>
            </Card>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
            <Card>
              <CardHeader><CardTitle>Approval metrics</CardTitle></CardHeader>
              <CardContent className="pt-0 space-y-3 text-[13px]">
                <Row k="Pending"            v={approvalStats.pending} />
                <Row k="Decided · 30d"      v={approvalStats.decided} />
                <Row k="Avg time to decide" v={approvalStats.avgMin ? `${approvalStats.avgMin}m` : "—"} />
                <Row k="Reject rate"        v={`${approvalStats.rejectPct}%`}
                     tone={approvalStats.rejectPct > 20 ? "warn" : "neutral"} />
              </CardContent>
            </Card>

            <Card>
              <CardHeader><CardTitle>Automation health</CardTitle></CardHeader>
              <CardContent className="pt-0 space-y-3.5">
                <Radial value={ops?.ocr?.avg_confidence ?? 1} label="OCR confidence"
                        hint={`${ops?.ocr?.documents_parsed ?? 0} parsed`} tone="info" />
                <Radial value={ops?.workflows?.success_rate ?? 1} label="Workflow success"
                        hint={`${ops?.workflows?.failures ?? 0} failures`} tone="success" />
                <Radial value={(() => {
                  const t = ops?.ai_tools?.invoked ?? 0;
                  const d = ops?.ai_tools?.denied ?? 0;
                  return t === 0 ? 1 : (t - d) / t;
                })()} label="AI tool success" hint={`${ops?.ai_tools?.invoked ?? 0} invocations`} tone="brand" />
              </CardContent>
            </Card>

            <Card>
              <CardHeader><CardTitle>AI productivity · 30d</CardTitle></CardHeader>
              <CardContent className="pt-0 space-y-2.5 text-[13px]">
                <Row k="Documents processed"    v={ops?.ocr?.documents_total ?? 0} />
                <Row k="Invoices drafted by AI" v={ops?.invoices?.created ?? 0} />
                <Row k="Approvals accelerated"  v={ops?.approvals?.decided ?? 0} />
                <Row k="Tool invocations"       v={ops?.ai_tools?.invoked ?? 0} />
                <div className="pt-3 mt-1 border-t border-border flex items-center gap-2 text-[11.5px]">
                  <TrendingUp className="h-3 w-3 text-[hsl(var(--brand))]" />
                  <span className="text-muted-foreground">
                    Time saved ≈
                    <span className="ml-1 text-foreground font-medium tabular-nums">
                      {Math.round((((ops?.invoices?.created ?? 0) * 4
                        + (ops?.ocr?.documents_parsed ?? 0) * 2
                        + (ops?.approvals?.decided ?? 0) * 1) / 60))}h
                    </span>
                  </span>
                </div>
              </CardContent>
            </Card>
          </div>

          <section>
            <SectionTitle title="Operational health" />
            <HealthStrip items={health} />
          </section>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
            <Card className="lg:col-span-2">
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle>Pending actions</CardTitle>
                <Link href="/approvals" className="text-[11px] text-muted-foreground hover:text-foreground transition-colors">
                  View all →
                </Link>
              </CardHeader>
              <CardContent className="pt-0">
                {safe.approvals.filter((a) => a.status === "PENDING").length === 0 ? (
                  <div className="text-[13px] text-muted-foreground py-2 flex items-center gap-2">
                    <span className="h-1.5 w-1.5 rounded-full bg-[hsl(var(--success))]" />
                    Nothing waiting on you.
                  </div>
                ) : (
                  <ul className="divide-y divide-border -mx-5">
                    {safe.approvals.filter((a) => a.status === "PENDING").slice(0, 5).map((a) => (
                      <li key={a.id} className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-3 px-5 py-3 hover:bg-accent/30 transition-colors">
                        <Badge tone="warn">Pending</Badge>
                        <div className="flex-1 min-w-0">
                          <div className="text-[13px] font-medium truncate">{a.summary}</div>
                          <div className="text-[11px] text-muted-foreground">
                            {new Date(a.created_at).toLocaleString()}
                          </div>
                        </div>
                        <div className="flex gap-1.5">
                          <Button size="sm" variant="ghost" disabled={decide.isPending}
                            onClick={() => decide.mutate({ id: a.id, approve: false }, {
                              onSuccess: () => toast.success("Rejected"),
                            })}><X className="h-3.5 w-3.5" /> Reject</Button>
                          <Button size="sm" disabled={decide.isPending}
                            onClick={() => decide.mutate({ id: a.id, approve: true }, {
                              onSuccess: () => toast.success("Approved"),
                            })}><Check className="h-3.5 w-3.5" /> Approve</Button>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
            <WhatsAppSimulator />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
            <Card className="lg:col-span-2">
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle>Recent activity</CardTitle>
                <Link href="/activity" className="text-[11px] text-muted-foreground hover:text-foreground">
                  Activity center →
                </Link>
              </CardHeader>
              <CardContent className="pt-0">
                {safe.logs.length === 0
                  ? <p className="text-[13px] text-muted-foreground">No activity yet.</p>
                  : (
                    <ul className="space-y-1.5">
                      {safe.logs.slice(0, 10).map((l) => (
                        <li key={l.id} className="flex items-center gap-3 text-[12.5px] py-1.5 rounded-md hover:bg-accent/30 px-1 transition-colors">
                          <span className="w-14 sm:w-20 shrink-0 text-muted-foreground tabular-nums text-[11px]">
                            {new Date(l.at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                          </span>
                          <Badge tone={l.actor_type === "ai" ? "info" : l.actor_type === "user" ? "success" : "neutral"}>
                            {l.actor_type}
                          </Badge>
                          <span className="font-mono text-[11px] truncate text-muted-foreground">{l.action}</span>
                          {l.resource && (
                            <Link
                              href={l.resource.startsWith("inv_") ? `/invoices/${l.resource}` :
                                    l.resource.startsWith("doc_") ? `/documents/${l.resource}` : "#"}
                              className="ml-auto text-[11px] text-muted-foreground hover:underline truncate hidden sm:inline"
                            >{l.resource}</Link>
                          )}
                        </li>
                      ))}
                    </ul>
                  )}
              </CardContent>
            </Card>
            <AnomalyCard />
          </div>
        </div>
      )}
    </>
  );
}

/* ─────────── Components ─────────── */

function HeroKpi({ label, value, delta, period, setPeriod, series, compare, labels }: {
  label: string; value: string; delta: number | null;
  period: Period; setPeriod: (p: Period) => void;
  series: number[]; compare: number[]; labels: string[];
}) {
  const hasData = series.some((v) => v > 0);
  return (
    <div className="surface-tinted surface-spotlight p-5 sm:p-6 flex flex-col">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-[10.5px] uppercase tracking-wider text-muted-foreground">{label}</div>
          <div className="mt-1.5 flex items-baseline gap-3 flex-wrap">
            <span className="text-[28px] sm:text-[34px] font-semibold tabular-nums tracking-tight leading-none">
              {value}
            </span>
            {delta !== null && (
              <span className={cn(
                "inline-flex items-center gap-0.5 text-[11.5px] tabular-nums font-medium",
                delta >= 0 ? "text-[hsl(var(--success))]" : "text-[hsl(var(--danger))]",
              )}>
                {delta >= 0 ? <ArrowUpRight className="h-3.5 w-3.5" /> : <ArrowDownRight className="h-3.5 w-3.5" />}
                {Math.abs(delta)}% vs prev {period}d
              </span>
            )}
          </div>
        </div>
        <div className="inline-flex rounded-md border border-border bg-card overflow-hidden shrink-0">
          {[7, 30, 90].map((p) => (
            <button key={p}
              onClick={() => setPeriod(p as Period)}
              className={cn(
                "px-2.5 h-7 text-[11px] font-medium transition-colors",
                period === p ? "bg-accent text-foreground" : "text-muted-foreground hover:bg-accent/60",
              )}>
              {p}d
            </button>
          ))}
        </div>
      </div>
      <div className="mt-4 -mx-2">
        {hasData
          ? <LineChart series={series} compare={compare} labels={labels} height={150}
                       yFormat={(v) => v >= 1_000_000 ? `${(v/1_000_000).toFixed(1)}M`
                                       : v >= 1_000 ? `${Math.round(v/1_000)}k` : `${v}`} />
          : <EmptyChart label="No revenue in this period." />}
      </div>
    </div>
  );
}

function SupportKpi({ label, value, sub, tone = "neutral" }: {
  label: string; value: string; sub?: string;
  tone?: "success" | "warn" | "danger" | "neutral";
}) {
  return (
    <div className="surface p-5">
      <div className="text-[10.5px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className={cn(
        "mt-2 text-[22px] sm:text-[24px] font-semibold tabular-nums tracking-tight leading-none",
        tone === "danger" ? "text-[hsl(var(--danger))]" :
        tone === "warn"   ? "text-[hsl(var(--warning))]" : "",
      )}>{value}</div>
      {sub && <div className="mt-1.5 text-[11.5px] text-muted-foreground truncate">{sub}</div>}
    </div>
  );
}

function SectionTitle({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="flex items-end justify-between mb-3">
      <h2 className="text-[13px] font-semibold tracking-tight">{title}</h2>
      {hint && <span className="text-[11px] text-muted-foreground">{hint}</span>}
    </div>
  );
}

function CashRow({ label, value, tone, total }: {
  label: string; value: number; tone: "success" | "info" | "danger"; total: number;
}) {
  const pct = total > 0 ? (value / total) * 100 : 0;
  const colorVar = tone === "success" ? "--success" : tone === "danger" ? "--danger" : "--info";
  return (
    <div>
      <div className="flex items-center justify-between text-[12.5px] mb-1.5">
        <span className="flex items-center gap-1.5 text-muted-foreground">
          <StatusDot tone={tone === "info" ? "info" : tone === "danger" ? "danger" : "success"} /> {label}
        </span>
        <span className="tabular-nums font-medium text-foreground">{formatKZT(value)}</span>
      </div>
      <div className="h-[3px] rounded-full bg-subtle overflow-hidden">
        <div className="h-full rounded-full transition-[width] duration-500"
             style={{ width: `${pct}%`, background: `hsl(var(${colorVar}))`, opacity: 0.9 }} />
      </div>
    </div>
  );
}

function Row({ k, v, tone = "neutral" }: { k: string; v: any; tone?: "warn" | "neutral" }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-muted-foreground">{k}</span>
      <span className={cn("tabular-nums font-medium", tone === "warn" ? "text-[hsl(var(--warning))]" : "")}>
        {v ?? "—"}
      </span>
    </div>
  );
}

function Legend({ items }: { items: { color: string; label: string }[] }) {
  return (
    <div className="flex flex-wrap gap-x-3 gap-y-1 mt-3 text-[10.5px] text-muted-foreground">
      {items.map((i) => (
        <span key={i.label} className="inline-flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 rounded-full" style={{ background: i.color }} /> {i.label}
        </span>
      ))}
    </div>
  );
}

function EmptyChart({ label }: { label: string }) {
  return (
    <div className="h-[140px] rounded-md border border-dashed border-border flex items-center justify-center text-[12px] text-muted-foreground">
      {label}
    </div>
  );
}

function LoadingShell() {
  return (
    <div className="space-y-6 animate-fadeIn">
      <div className="sk h-12" />
      <div className="grid grid-cols-1 lg:grid-cols-[1.4fr_1fr_1fr_1fr] gap-4">
        <div className="sk h-44" /><div className="sk h-44" /><div className="sk h-44" /><div className="sk h-44" />
      </div>
      <div className="sk h-20" />
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div className="sk h-56 lg:col-span-2" /><div className="sk h-56" />
      </div>
    </div>
  );
}

/* ─────────── Pure helpers ─────────── */

function sumBy<T>(arr: T[], f: (x: T) => number): number {
  let s = 0; for (const x of arr) s += f(x); return s;
}

function buildSeries(invoices: { status: string; total: string; issue_date: string | null }[], days: number) {
  const now = new Date();
  const current = Array(days).fill(0);
  const previous = Array(days).fill(0);
  const labels: string[] = [];
  for (let i = 0; i < days; i++) {
    const d = new Date(now); d.setDate(now.getDate() - (days - 1 - i));
    labels.push(d.toLocaleDateString([], { day: "2-digit", month: "short" }));
  }
  for (const inv of invoices) {
    if (!inv.issue_date) continue;
    if (inv.status !== "SENT" && inv.status !== "PAID") continue;
    const t = new Date(inv.issue_date).getTime();
    if (Number.isNaN(t)) continue;
    const diff = Math.floor((+now - t) / 86400000);
    if (diff >= 0 && diff < days) current[days - 1 - diff] += Number(inv.total);
    else if (diff >= days && diff < days * 2) previous[days * 2 - 1 - diff] += Number(inv.total);
  }
  return { current, previous, labels };
}

function buildVolume(invoices: { status: string; issue_date: string | null }[], days: number) {
  const out: { label: string; stacks: { key: string; value: number; color: string }[] }[] = [];
  const now = new Date();
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(now); d.setDate(now.getDate() - i);
    const day = d.toISOString().slice(0, 10);
    const sameDay = invoices.filter((inv) => (inv.issue_date ?? "").slice(0, 10) === day);
    out.push({
      label: d.toLocaleDateString([], { day: "2-digit", month: "short" }),
      stacks: [
        { key: "paid",    value: sameDay.filter((x) => x.status === "PAID").length,             color: "hsl(var(--success))" },
        { key: "sent",    value: sameDay.filter((x) => x.status === "SENT").length,             color: "hsl(var(--info))" },
        { key: "pending", value: sameDay.filter((x) => x.status === "PENDING_APPROVAL").length, color: "hsl(var(--warning))" },
        { key: "overdue", value: sameDay.filter((x) => x.status === "OVERDUE").length,          color: "hsl(var(--danger))" },
      ],
    });
  }
  return out;
}
