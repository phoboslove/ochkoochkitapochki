"use client";

import { AlertCircle, AlertTriangle, Info, Lightbulb, Wrench } from "lucide-react";
import { cn } from "@/lib/utils";

export type Diagnostic = {
  stage?: string;
  code?: string;
  message?: string;
  severity?: "info" | "warning" | "error";
  template_id?: string | null;
  failed_field?: string | null;
  failed_placeholder?: string | null;
  table_index?: number | null;
  row_index?: number | null;
  render_engine?: string | null;
  exception?: string | null;
  suggested_fix?: string | null;
  where?: string | null;
  extra?: Record<string, unknown>;
};

const SEVERITY_STYLES: Record<string, { ring: string; bg: string; fg: string; Icon: any }> = {
  error:   { ring: "ring-[hsl(var(--danger)/0.3)]",   bg: "bg-danger-bg",    fg: "text-[hsl(var(--danger))]",    Icon: AlertCircle    },
  warning: { ring: "ring-[hsl(var(--warning)/0.3)]", bg: "bg-warning-bg",  fg: "text-[hsl(var(--warning))]",  Icon: AlertTriangle  },
  info:    { ring: "ring-[hsl(var(--info)/0.25)]",   bg: "bg-info-bg",    fg: "text-[hsl(var(--info))]",    Icon: Info           },
};

const STAGE_LABELS: Record<string, string> = {
  intent:      "Intent",
  match:       "Template match",
  adaptation:  "Legacy adaptation",
  render:      "Render",
  pdf_export:  "PDF export",
  storage:     "Storage",
  quality:     "Quality QA",
  approval:    "Approval",
};

export function DiagnosticsPanel({
  diagnostics,
  title = "Diagnostics",
  compact = false,
}: {
  diagnostics: Diagnostic[] | null | undefined;
  title?: string;
  compact?: boolean;
}) {
  const entries = (diagnostics ?? []).filter((d) => d && (d.message || d.code));
  if (entries.length === 0) {
    return null;
  }

  // Group by stage so the operator can mentally scan "what happened where".
  const byStage = new Map<string, Diagnostic[]>();
  for (const d of entries) {
    const k = d.stage ?? "other";
    if (!byStage.has(k)) byStage.set(k, []);
    byStage.get(k)!.push(d);
  }

  return (
    <div className="space-y-3">
      {!compact && (
        <div className="flex items-center justify-between">
          <h3 className="text-[13px] font-medium">{title}</h3>
          <span className="text-[11px] text-muted-foreground tabular-nums">
            {entries.length} event{entries.length === 1 ? "" : "s"}
          </span>
        </div>
      )}
      <ol className="space-y-2">
        {[...byStage.entries()].map(([stage, items]) => (
          <li key={stage} className="space-y-1.5">
            <div className="text-[10.5px] uppercase tracking-wider text-muted-foreground/80 pl-px">
              {STAGE_LABELS[stage] ?? stage}
            </div>
            {items.map((d, idx) => (
              <DiagnosticRow key={idx} d={d} />
            ))}
          </li>
        ))}
      </ol>
    </div>
  );
}

function DiagnosticRow({ d }: { d: Diagnostic }) {
  const sev = d.severity ?? "info";
  const s = SEVERITY_STYLES[sev] ?? SEVERITY_STYLES.info;
  const Icon = s.Icon;
  const where: string[] = [];
  if (d.failed_field) where.push(`field: ${d.failed_field}`);
  if (d.failed_placeholder) where.push(`{{${d.failed_placeholder}}}`);
  if (d.table_index != null) where.push(`table ${d.table_index}`);
  if (d.row_index != null) where.push(`row ${d.row_index}`);
  if (d.render_engine) where.push(d.render_engine);
  if (d.where) where.push(d.where);

  return (
    <div className={cn("rounded-md px-3 py-2 ring-1", s.ring, s.bg)}>
      <div className="flex items-start gap-2">
        <Icon className={cn("h-3.5 w-3.5 mt-0.5 shrink-0", s.fg)} />
        <div className="min-w-0 flex-1">
          <div className="text-[12.5px] leading-snug">{d.message}</div>
          {(where.length > 0 || d.code) && (
            <div className="mt-1 text-[11px] text-muted-foreground flex flex-wrap items-center gap-x-3 gap-y-0.5">
              {d.code && <span className="font-mono opacity-70">{d.code}</span>}
              {where.map((w, i) => (
                <span key={i} className="opacity-80">{w}</span>
              ))}
            </div>
          )}
          {d.suggested_fix && (
            <div className="mt-1.5 flex items-start gap-1.5 rounded-md bg-card/70 px-2 py-1.5 ring-1 ring-border/50">
              <Lightbulb className="h-3.5 w-3.5 mt-0.5 text-[hsl(var(--warning))] shrink-0" />
              <span className="text-[11.5px] text-muted-foreground leading-snug">
                <span className="font-medium text-foreground/80 mr-1">Fix:</span>
                {d.suggested_fix}
              </span>
            </div>
          )}
          {d.exception && (
            <details className="mt-1 text-[11px] text-muted-foreground">
              <summary className="cursor-pointer select-none opacity-70 hover:opacity-100">
                <Wrench className="inline h-3 w-3 mr-1" />exception
              </summary>
              <pre className="mt-1 max-h-32 overflow-y-auto whitespace-pre-wrap font-mono text-[10.5px] opacity-80">
                {d.exception}
              </pre>
            </details>
          )}
        </div>
      </div>
    </div>
  );
}


/** Quality score pill — small reusable component. */
export function QualityBadge({
  score, status,
}: { score: number | null | undefined; status?: string | null }) {
  if (score == null) return null;
  const tone =
    status === "blocked" || score < 60 ? "bg-danger-bg text-[hsl(var(--danger))] ring-[hsl(var(--danger)/0.25)]" :
    status === "warning" || score < 80 ? "bg-warning-bg text-[hsl(var(--warning))] ring-[hsl(var(--warning)/0.25)]" :
                                          "bg-success-bg text-[hsl(var(--success))] ring-[hsl(var(--success)/0.25)]";
  return (
    <span className={cn(
      "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 tabular-nums",
      tone,
    )}>
      Quality {score}/100
    </span>
  );
}


/** Fallback warning banner — shown when AI couldn't render the real template. */
export function FallbackWarning({
  used, reason, engine,
}: { used: boolean; reason?: string | null; engine?: string | null }) {
  if (!used) return null;
  return (
    <div className="flex items-start gap-2.5 rounded-md ring-1 ring-[hsl(var(--warning)/0.3)] bg-warning-bg px-3 py-2.5">
      <AlertTriangle className="h-4 w-4 mt-0.5 text-[hsl(var(--warning))] shrink-0" />
      <div className="min-w-0">
        <div className="text-[13px] font-medium">
          Original template could not be rendered — fallback layout used
        </div>
        <div className="mt-0.5 text-[11.5px] text-muted-foreground">
          {reason ?? "Reason not recorded."}
          {engine && <span className="ml-2 font-mono opacity-70">engine: {engine}</span>}
        </div>
      </div>
    </div>
  );
}
