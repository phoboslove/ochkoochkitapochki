"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge, StatusDot } from "@/components/ui/badge";
import { EmptyState } from "@/components/EmptyState";
import { useCorpusAudit } from "@/lib/templates";
import { toast } from "@/components/Toaster";
import {
  ArrowLeft, ShieldCheck, AlertTriangle, PlayCircle, FileCheck, FileWarning,
  AlertCircle, ListChecks,
} from "lucide-react";
import { cn } from "@/lib/utils";

export default function CorpusAuditPage() {
  const audit = useCorpusAudit();
  const [report, setReport] = useState<any | null>(null);

  useEffect(() => {
    audit.mutate(undefined, {
      onSuccess: (r) => setReport(r),
      onError:   (e) => toast.error("Audit failed", (e as Error).message),
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const rerun = () => audit.mutate(undefined, { onSuccess: (r) => setReport(r) });

  return (
    <>
      <Link href="/settings/templates"
            className="inline-flex items-center gap-1 text-[12px] text-muted-foreground hover:text-foreground mb-4">
        <ArrowLeft className="h-3.5 w-3.5" /> Templates
      </Link>

      <PageHeader
        eyebrow="Business · Templates"
        title="Corpus audit"
        description="Full production-readiness sweep across the template library — integrity, mapping quality, render verification, recovery visibility."
        actions={
          <Button size="sm" variant="outline" disabled={audit.isPending} onClick={rerun}>
            <PlayCircle className="h-3.5 w-3.5" /> {audit.isPending ? "Auditing…" : "Re-run audit"}
          </Button>
        }
      />

      {audit.isPending && !report && (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => <div key={i} className="sk h-32" />)}
        </div>
      )}

      {report && (
        <div className="space-y-6 animate-fadeIn">
          {/* ── Readiness hero ────────────────────────────────────────── */}
          <Card className="surface-spotlight">
            <CardContent className="p-6 grid grid-cols-1 sm:grid-cols-[auto_1fr] gap-6 items-start">
              <ScoreRing score={report.production_readiness.score} />
              <div className="space-y-3">
                <div>
                  <div className="text-[10.5px] uppercase tracking-wider text-muted-foreground">Production readiness</div>
                  <div className="text-[34px] font-semibold tabular-nums leading-none mt-1">
                    {report.production_readiness.score}<span className="text-[16px] text-muted-foreground"> / 100</span>
                  </div>
                  <div className="mt-1 text-[12px] text-muted-foreground">
                    Verified {report.production_readiness.verified_pct}% · render-sample {report.production_readiness.render_success_rate}% OK
                  </div>
                </div>
                {report.production_readiness.blockers.length > 0 && (
                  <div>
                    <div className="text-[10.5px] uppercase tracking-wider text-muted-foreground mb-1.5">Blockers</div>
                    <ul className="space-y-1 text-[12.5px]">
                      {report.production_readiness.blockers.map((b: string, i: number) => (
                        <li key={i} className="flex gap-2"><StatusDot tone="danger" className="mt-1.5"/><span>{b}</span></li>
                      ))}
                    </ul>
                  </div>
                )}
                {report.production_readiness.recommendations.length > 0 && (
                  <div>
                    <div className="text-[10.5px] uppercase tracking-wider text-muted-foreground mb-1.5">Recommendations</div>
                    <ul className="space-y-1 text-[12.5px] text-muted-foreground">
                      {report.production_readiness.recommendations.map((r: string, i: number) => (
                        <li key={i}>→ {r}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* ── Corpus summary KPIs ───────────────────────────────────── */}
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
            <KPI label="Total" value={report.corpus_summary.total} />
            <KPI label="Verified"   value={report.corpus_summary.verified}    tone="success" />
            <KPI label="Operational"value={report.corpus_summary.operational} tone="info" />
            <KPI label="Broken / archived" value={report.corpus_summary.broken} tone={report.corpus_summary.broken ? "danger" : "neutral"} />
            <KPI label="Duplicates"  value={report.corpus_summary.duplicates}  tone={report.corpus_summary.duplicates ? "warn" : "neutral"} />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            <Distribution title="By status"     map={report.corpus_summary.by_status} />
            <Distribution title="By document kind" map={report.corpus_summary.by_kind} />
            <Distribution title="By industry"   map={report.corpus_summary.by_industry} />
            <Distribution title="By format"     map={report.corpus_summary.by_format} />
          </div>

          {/* ── Integrity ─────────────────────────────────────────────── */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle><ShieldCheck className="inline h-3.5 w-3.5 mr-1" /> Ingestion integrity</CardTitle>
              <span className="text-[11px] text-muted-foreground">
                {sumCounts(report.integrity_counts)} issue(s)
              </span>
            </CardHeader>
            <CardContent className="pt-0 space-y-3">
              {Object.entries(report.integrity_counts).map(([k, v]: any) => (
                <IssueRow key={k} k={prettyIntegrity(k)} v={v as number}
                          items={(report.integrity[k] || []) as any[]} tone={v ? "warn" : "success"} />
              ))}
            </CardContent>
          </Card>

          {/* ── Mapping quality ────────────────────────────────────────── */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle><ListChecks className="inline h-3.5 w-3.5 mr-1" /> Mapping quality</CardTitle>
              <span className="text-[11px] text-muted-foreground">
                {sumCounts(report.mapping_counts)} issue(s)
              </span>
            </CardHeader>
            <CardContent className="pt-0 space-y-3">
              {Object.entries(report.mapping_counts).map(([k, v]: any) => (
                <IssueRow key={k} k={prettyMapping(k)} v={v as number}
                          items={(report.mapping_quality[k] || []) as any[]}
                          tone={v ? (k === "missing_required" ? "danger" : "warn") : "success"} />
              ))}
            </CardContent>
          </Card>

          {/* ── Render verification ───────────────────────────────────── */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle><FileCheck className="inline h-3.5 w-3.5 mr-1" /> Render verification</CardTitle>
              <span className="text-[11px] text-muted-foreground">
                {report.render_check.ok} / {report.render_check.attempted} OK
              </span>
            </CardHeader>
            <CardContent className="pt-0 space-y-3">
              <div className="h-2 w-full rounded-full bg-subtle overflow-hidden">
                <div className="h-full rounded-full bg-[hsl(var(--success))]"
                     style={{ width: `${report.render_check.attempted ? (report.render_check.ok / report.render_check.attempted) * 100 : 0}%` }} />
              </div>
              {(report.render_check.failed?.length ?? 0) === 0 && (
                <div className="text-[12.5px] text-muted-foreground flex items-center gap-2">
                  <StatusDot tone="success" /> All sampled templates rendered successfully.
                </div>
              )}
              {(report.render_check.failed?.length ?? 0) > 0 && (
                <>
                  <div className="text-[11px] uppercase tracking-wider text-muted-foreground">Failed renders</div>
                  <ul className="space-y-1.5">
                    {report.render_check.failed.map((f: any) => (
                      <li key={f.id} className="flex items-start gap-2 text-[12px]">
                        <StatusDot tone="danger" className="mt-1" />
                        <Link href={`/settings/templates/${f.id}`} className="font-medium hover:underline">
                          {f.name}
                        </Link>
                        <span className="font-mono text-[11px] text-muted-foreground">[{f.format}]</span>
                        <span className="text-muted-foreground truncate">→ {f.error}</span>
                      </li>
                    ))}
                  </ul>
                  {Object.keys(report.render_check.failure_patterns ?? {}).length > 0 && (
                    <div className="mt-2 text-[11.5px] text-muted-foreground">
                      Failure patterns:{" "}
                      {Object.entries(report.render_check.failure_patterns).map(([k, v]) => (
                        <code key={k} className="mx-1 font-mono">{k}×{v as number}</code>
                      ))}
                    </div>
                  )}
                </>
              )}
            </CardContent>
          </Card>

          {/* ── Recovery audit visibility ─────────────────────────────── */}
          <Card>
            <CardHeader><CardTitle><AlertCircle className="inline h-3.5 w-3.5 mr-1" /> Recovery & audit · 14d</CardTitle></CardHeader>
            <CardContent className="pt-0">
              {Object.keys(report.recovery ?? {}).length === 0
                ? <p className="text-[12.5px] text-muted-foreground">No template-related audit events in the last 14 days.</p>
                : <ul className="grid grid-cols-1 sm:grid-cols-2 gap-1 text-[12.5px]">
                    {Object.entries(report.recovery).map(([action, n]) => (
                      <li key={action} className="flex items-center justify-between border-b border-border py-1">
                        <span className="font-mono text-muted-foreground">{action}</span>
                        <span className="tabular-nums font-medium">{n as number}</span>
                      </li>
                    ))}
                  </ul>}
              <p className="mt-3 text-[11px] text-muted-foreground">
                Full operational timeline → <Link href="/activity" className="underline">Activity center</Link>.
                Items in <code>FAILED</code> state appear in <Link href="/recovery" className="underline">Recovery</Link>.
              </p>
            </CardContent>
          </Card>

          <p className="text-[10.5px] text-muted-foreground text-right">
            Generated {new Date(report.generated_at).toLocaleString()}
          </p>
        </div>
      )}
    </>
  );
}

function KPI({ label, value, tone = "neutral" }: { label: string; value: number; tone?: "success"|"warn"|"danger"|"info"|"neutral" }) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="text-[10.5px] uppercase tracking-wider text-muted-foreground">{label}</div>
        <div className={cn(
          "mt-1.5 text-[22px] font-semibold tabular-nums tracking-tight",
          tone === "danger" ? "text-[hsl(var(--danger))]" :
          tone === "warn"   ? "text-[hsl(var(--warning))]" :
          tone === "success"? "text-[hsl(var(--success))]" :
          tone === "info"   ? "text-[hsl(var(--info))]"   : "",
        )}>{value}</div>
      </CardContent>
    </Card>
  );
}

function Distribution({ title, map }: { title: string; map: Record<string, number> }) {
  const entries = Object.entries(map).sort((a, b) => b[1] - a[1]);
  const max = Math.max(1, ...entries.map(([_, v]) => v));
  return (
    <Card>
      <CardHeader><CardTitle>{title}</CardTitle></CardHeader>
      <CardContent className="pt-0 space-y-2">
        {entries.map(([k, v]) => (
          <div key={k}>
            <div className="flex items-center justify-between text-[12px]">
              <span className="text-muted-foreground capitalize">{k}</span>
              <span className="tabular-nums">{v}</span>
            </div>
            <div className="h-[3px] bg-subtle rounded-full overflow-hidden">
              <div className="h-full bg-[hsl(var(--brand))] rounded-full transition-[width] duration-500"
                   style={{ width: `${(v / max) * 100}%`, opacity: 0.85 }} />
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function IssueRow({ k, v, items, tone }: { k: string; v: number; items: any[]; tone: "success"|"warn"|"danger" }) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <button onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-2 text-[12.5px] py-1.5 hover:bg-accent/40 rounded-md px-2 -mx-2">
        <StatusDot tone={tone} />
        <span className="flex-1 text-left">{k}</span>
        <span className="tabular-nums font-medium">{v}</span>
        {items.length > 0 && <span className="text-muted-foreground text-[10px]">{open ? "−" : "+"}</span>}
      </button>
      {open && items.length > 0 && (
        <ul className="mt-1 mb-2 space-y-1 pl-5 text-[11.5px]">
          {items.slice(0, 10).map((it: any, i: number) => (
            <li key={i} className="flex items-center gap-2">
              {it.id ? (
                <Link href={`/settings/templates/${it.id}`} className="hover:underline truncate max-w-[280px]">
                  {it.name || it.filename}
                </Link>
              ) : <span>—</span>}
              {it.field && <code className="font-mono text-muted-foreground">{it.field}</code>}
              {it.missing && <code className="font-mono text-muted-foreground">missing: {(it.missing as string[]).join(",")}</code>}
              {it.source && <code className="font-mono text-muted-foreground">"{it.source}"</code>}
              {it.error && <span className="text-muted-foreground truncate">→ {it.error}</span>}
            </li>
          ))}
          {items.length > 10 && <li className="text-muted-foreground">… {items.length - 10} more</li>}
        </ul>
      )}
    </div>
  );
}

function ScoreRing({ score }: { score: number }) {
  const r = 38, c = 2 * Math.PI * r;
  const offset = c * (1 - score / 100);
  const color = score >= 85 ? "var(--success)" : score >= 60 ? "var(--info)" : score >= 35 ? "var(--warning)" : "var(--danger)";
  return (
    <svg width="100" height="100" viewBox="0 0 100 100">
      <circle cx="50" cy="50" r={r} fill="none" className="stroke-subtle" strokeWidth="6" />
      <circle cx="50" cy="50" r={r} fill="none" strokeWidth="6" strokeLinecap="round"
              transform="rotate(-90 50 50)"
              style={{ stroke: `hsl(${color})`, strokeDasharray: c, strokeDashoffset: offset,
                       transition: "stroke-dashoffset .5s ease-out" }} />
      <text x="50" y="55" textAnchor="middle" className="fill-foreground text-[18px] font-semibold tabular-nums">{score}</text>
    </svg>
  );
}

function sumCounts(o: Record<string, number>): number {
  return Object.values(o).reduce((a, b) => a + (b || 0), 0);
}
function prettyIntegrity(k: string): string {
  return ({
    storage_missing: "Storage file missing",
    empty_content:   "Empty extracted content",
    malformed_mappings: "Malformed mapping structure",
    broken_lineage: "Broken converted-from lineage",
    no_paragraphs: "No paragraphs extracted",
  } as any)[k] ?? k;
}
function prettyMapping(k: string): string {
  return ({
    low_confidence: "Low-confidence suggestions",
    missing_required: "Missing required fields",
    duplicate_sources: "Duplicate source labels",
    suspicious_total_vs_subtotal: "Suspicious total / subtotal labels",
  } as any)[k] ?? k;
}
