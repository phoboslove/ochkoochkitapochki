"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useRecovery, useRetryDocument, useRetryInvoiceSend } from "@/lib/hooks";
import { toast } from "@/components/Toaster";
import { AlertTriangle, RefreshCw, ExternalLink, ArrowUpRight } from "lucide-react";

export default function RecoveryPage() {
  const { data = [], isLoading } = useRecovery();
  const retryInvoice = useRetryInvoiceSend();
  const retryDoc = useRetryDocument();

  return (
    <>
      <PageHeader title="Workflow recovery" description="Operationally critical: every failed step that needs operator attention." />

      {isLoading && <div className="text-sm text-muted-foreground">Loading…</div>}
      {!isLoading && data.length === 0 && (
        <Card><CardContent className="p-8 text-center text-sm text-muted-foreground">
          <AlertTriangle className="h-6 w-6 mx-auto mb-2 opacity-50" />
          Nothing to recover. All workflows healthy.
        </CardContent></Card>
      )}

      <ul className="space-y-3">
        {data.map((row) => (
          <li key={row.id}>
            <Card className="border-l-4 border-l-red-500">
              <CardContent className="flex flex-col sm:flex-row gap-3 p-4">
                <Badge tone="danger" className="self-start">{row.kind}</Badge>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium">{labelFor(row.action)}</div>
                  <div className="mt-0.5 text-xs text-muted-foreground flex flex-wrap items-center gap-3">
                    <span>{new Date(row.at).toLocaleString()}</span>
                    {row.resource && <span className="font-mono">{row.resource}</span>}
                  </div>
                  {row.meta && Object.keys(row.meta).length > 0 && (
                    <div className="mt-1 text-[11px] text-muted-foreground">
                      {Object.entries(row.meta).slice(0, 3).map(([k, v]) => (
                        <span key={k} className="mr-3"><span className="opacity-60">{k}:</span> <span className="font-mono">{String(v).slice(0, 80)}</span></span>
                      ))}
                    </div>
                  )}
                </div>
                <div className="flex flex-wrap gap-2 sm:ml-auto">
                  {row.actions?.includes("retry_send") && row.kind === "invoice" && row.resource && (
                    <Button size="sm" variant="outline" disabled={retryInvoice.isPending}
                      onClick={() => retryInvoice.mutate(row.resource, {
                        onSuccess: () => toast.success("Retried"),
                        onError:   (e) => toast.error("Retry failed", (e as Error).message),
                      })}>
                      <RefreshCw className="h-3.5 w-3.5" /> Retry send
                    </Button>
                  )}
                  {row.actions?.includes("retry_ocr") && row.kind === "document" && row.resource && (
                    <Button size="sm" variant="outline" disabled={retryDoc.isPending}
                      onClick={() => retryDoc.mutate(row.resource, {
                        onSuccess: () => toast.success("Retrying OCR"),
                      })}>
                      <RefreshCw className="h-3.5 w-3.5" /> Retry OCR
                    </Button>
                  )}
                  {row.kind === "invoice" && row.resource && (
                    <Link href={`/invoices/${row.resource}`}>
                      <Button size="sm" variant="ghost"><ArrowUpRight className="h-3.5 w-3.5" /> Open</Button>
                    </Link>
                  )}
                  {row.kind === "document" && row.resource && (
                    <Link href={`/documents/${row.resource}`}>
                      <Button size="sm" variant="ghost"><ArrowUpRight className="h-3.5 w-3.5" /> Open</Button>
                    </Link>
                  )}
                  <Button size="sm" variant="ghost"
                    onClick={() => toast.info("Escalated", "Notified the team owner.")}>
                    <ExternalLink className="h-3.5 w-3.5" /> Escalate
                  </Button>
                </div>
              </CardContent>
            </Card>
          </li>
        ))}
      </ul>
    </>
  );
}

const LABELS: Record<string, string> = {
  "document.failed":     "Document OCR / parse failed",
  "whatsapp.send_failed":"WhatsApp delivery failed",
  "invoice.overdue":     "Invoice overdue",
  "ai.tool_denied":      "AI tool blocked by guardrail",
  "workflow.run_failed": "Workflow run failed",
};
function labelFor(action: string): string { return LABELS[action] ?? action; }
