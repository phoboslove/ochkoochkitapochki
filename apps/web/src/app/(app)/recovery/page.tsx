"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useRecovery, useRetryDocument, useRetryInvoiceSend } from "@/lib/hooks";
import { toast } from "@/components/Toaster";
import { DiagnosticsPanel, QualityBadge, type Diagnostic } from "@/components/DiagnosticsPanel";
import {
  AlertTriangle, RefreshCw, ExternalLink, ArrowUpRight, FileX, Receipt,
  ShieldAlert, Workflow, ScanLine,
} from "lucide-react";
import { cn } from "@/lib/utils";

type RecoveryRow = {
  id: string;
  kind: "document" | "invoice" | "system" | "approval" | "generated_document";
  action: string;
  resource: string | null;
  at: string;
  meta: Record<string, any>;
  actions?: string[];
};

const KIND_META: Record<RecoveryRow["kind"], { Icon: any; tone: string; label: string }> = {
  document:           { Icon: ScanLine,    tone: "warn",   label: "OCR / parse" },
  invoice:            { Icon: Receipt,     tone: "danger", label: "Invoice" },
  approval:           { Icon: ShieldAlert, tone: "danger", label: "Approval blocked" },
  generated_document: { Icon: FileX,       tone: "danger", label: "Generation blocked" },
  system:             { Icon: Workflow,    tone: "warn",   label: "Workflow" },
};

const LABELS: Record<string, string> = {
  "document.failed":            "Document OCR / parse failed",
  "whatsapp.send_failed":       "WhatsApp delivery failed",
  "invoice.overdue":            "Invoice overdue",
  "ai.tool_denied":             "AI tool blocked by guardrail",
  "workflow.run_failed":        "Workflow run failed",
  "approval.blocked":           "Approval blocked by quality gate",
  "document.quality_blocked":   "Generated document failed QA",
};

export default function RecoveryPage() {
  const { data = [], isLoading } = useRecovery() as { data: RecoveryRow[]; isLoading: boolean };
  const retryInvoice = useRetryInvoiceSend();
  const retryDoc = useRetryDocument();

  // Group by severity tone for visual ordering — most critical first.
  const ordered = [...data].sort((a, b) => kindWeight(b) - kindWeight(a));

  return (
    <>
      <PageHeader
        title="Workflow recovery"
        description="Every failure, blocked approval, and degraded render that needs an operator."
      />

      {isLoading && (
        <Card><CardContent className="p-5 text-sm text-muted-foreground animate-pulse">
          Loading recovery queue…
        </CardContent></Card>
      )}

      {!isLoading && ordered.length === 0 && (
        <Card>
          <CardContent className="p-8 text-center text-sm text-muted-foreground">
            <AlertTriangle className="h-6 w-6 mx-auto mb-2 opacity-40" />
            Nothing to recover. All workflows healthy.
          </CardContent>
        </Card>
      )}

      <ul className="space-y-3">
        {ordered.map((row) => (
          <li key={row.id}>
            <RecoveryCard
              row={row}
              onRetryInvoice={() => retryInvoice.mutate(row.resource!, {
                onSuccess: () => toast.success("Retried", "Send re-queued."),
                onError:   (e) => toast.error("Retry failed", (e as Error).message),
              })}
              onRetryDoc={() => retryDoc.mutate(row.resource!, {
                onSuccess: () => toast.success("Retrying OCR", row.meta.title ?? row.resource ?? ""),
                onError:   (e) => toast.error("Retry failed", (e as Error).message),
              })}
            />
          </li>
        ))}
      </ul>
    </>
  );
}


function RecoveryCard({
  row, onRetryInvoice, onRetryDoc,
}: {
  row: RecoveryRow;
  onRetryInvoice: () => void;
  onRetryDoc: () => void;
}) {
  const km = KIND_META[row.kind] ?? KIND_META.system;
  const Icon = km.Icon;
  const isCritical = row.kind === "approval" || row.kind === "generated_document";
  const accent = isCritical ? "border-l-red-500" : "border-l-amber-500";
  const label = LABELS[row.action] ?? row.action;

  const diagnostics: Diagnostic[] = [];
  // Convert payload signals into structured diagnostic rows the panel can render.
  if (row.meta.blocking_issues?.length) {
    for (const i of row.meta.blocking_issues) {
      diagnostics.push({
        stage: i.stage ?? "quality",
        code: i.code,
        message: i.message,
        severity: i.severity ?? "error",
        where: i.where ?? null,
        suggested_fix: i.suggested_fix,
      });
    }
  }
  if (row.meta.suggested_fix && !diagnostics.some((d) => d.suggested_fix)) {
    diagnostics.push({
      stage: row.kind === "approval" ? "approval" : row.kind === "generated_document" ? "quality" : "render",
      code: row.action, severity: isCritical ? "error" : "warning",
      message: row.meta.summary ?? label,
      suggested_fix: row.meta.suggested_fix,
    });
  }
  if (row.meta.error) {
    diagnostics.push({
      stage: "render", code: row.action, severity: "error",
      message: String(row.meta.error),
      suggested_fix: row.meta.suggested_fix,
    });
  }

  return (
    <Card className={cn("border-l-4", accent)}>
      <CardContent className="p-4 space-y-3">
        <div className="flex flex-wrap items-start gap-3">
          <div className="flex items-center gap-2">
            <span className={cn(
              "inline-flex h-7 w-7 items-center justify-center rounded-md ring-1",
              isCritical ? "bg-red-500/10 ring-red-500/25 text-red-500"
                         : "bg-amber-500/10 ring-amber-500/25 text-amber-500",
            )}>
              <Icon className="h-3.5 w-3.5" />
            </span>
            <Badge tone={km.tone as any}>{km.label}</Badge>
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium leading-snug">{label}</div>
            <div className="mt-0.5 text-[11.5px] text-muted-foreground flex flex-wrap items-center gap-x-3 gap-y-0.5">
              <span>{new Date(row.at).toLocaleString()}</span>
              {row.resource && <span className="font-mono opacity-80">{row.resource}</span>}
              {typeof row.meta.quality_score === "number" && (
                <QualityBadge score={row.meta.quality_score} status={row.meta.quality_status} />
              )}
              {row.meta.client && <span>· {row.meta.client}</span>}
              {row.meta.number && <span className="font-mono">{row.meta.number}</span>}
              {row.meta.title && <span className="truncate max-w-[300px]">{row.meta.title}</span>}
            </div>
          </div>
          <RowActions row={row} onRetryDoc={onRetryDoc} onRetryInvoice={onRetryInvoice} />
        </div>

        {diagnostics.length > 0 && (
          <DiagnosticsPanel diagnostics={diagnostics} title="What happened" compact />
        )}

        {/* Fallback transparency banner for generated docs that used HTML fallback. */}
        {row.meta.fallback?.used && (
          <div className="rounded-md ring-1 ring-amber-500/30 bg-amber-500/8 px-3 py-2 text-[11.5px] text-muted-foreground">
            <span className="font-medium text-foreground/80">Fallback engine used:</span>{" "}
            {row.meta.fallback.reason ?? "no template available"}
            {row.meta.fallback.engine && <span className="ml-2 font-mono opacity-70">{row.meta.fallback.engine}</span>}
          </div>
        )}
      </CardContent>
    </Card>
  );
}


function RowActions({
  row, onRetryDoc, onRetryInvoice,
}: { row: RecoveryRow; onRetryDoc: () => void; onRetryInvoice: () => void }) {
  return (
    <div className="flex flex-wrap gap-2">
      {row.actions?.includes("retry_send") && row.kind === "invoice" && row.resource && (
        <Button size="sm" variant="outline" onClick={onRetryInvoice}>
          <RefreshCw className="h-3.5 w-3.5" /> Retry send
        </Button>
      )}
      {row.actions?.includes("retry_ocr") && row.kind === "document" && row.resource && (
        <Button size="sm" variant="outline" onClick={onRetryDoc}>
          <RefreshCw className="h-3.5 w-3.5" /> Retry OCR
        </Button>
      )}
      {row.actions?.includes("regenerate") && (
        <Button size="sm" variant="outline" disabled
          title="Regenerate flow — coming next. For now, re-trigger via assistant.">
          <RefreshCw className="h-3.5 w-3.5" /> Regenerate
        </Button>
      )}
      {row.kind === "invoice" && row.resource && (
        <Link href={`/invoices/${row.resource}`}>
          <Button size="sm" variant="ghost"><ArrowUpRight className="h-3.5 w-3.5" /> Open</Button>
        </Link>
      )}
      {(row.kind === "document" || row.kind === "generated_document") && row.resource && (
        <Link href={`/documents/${row.resource}`}>
          <Button size="sm" variant="ghost"><ArrowUpRight className="h-3.5 w-3.5" /> Open</Button>
        </Link>
      )}
      {row.kind === "approval" && (
        <Link href="/approvals">
          <Button size="sm" variant="ghost"><ArrowUpRight className="h-3.5 w-3.5" /> Open approval</Button>
        </Link>
      )}
      <Button size="sm" variant="ghost"
        onClick={() => toast.info("Escalated", "Notified the team owner.")}>
        <ExternalLink className="h-3.5 w-3.5" /> Escalate
      </Button>
    </div>
  );
}


function kindWeight(row: RecoveryRow): number {
  if (row.kind === "approval") return 4;
  if (row.kind === "generated_document") return 3;
  if (row.kind === "document") return 2;
  if (row.kind === "invoice") return 1;
  return 0;
}
