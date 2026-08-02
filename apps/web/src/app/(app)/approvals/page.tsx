"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useApprovals, useDecideApproval } from "@/lib/hooks";
import { Check, X, ExternalLink, Sparkles, ShieldAlert } from "lucide-react";
import { toast } from "@/components/Toaster";
import { DiagnosticsPanel, QualityBadge, type Diagnostic } from "@/components/DiagnosticsPanel";
import { cn } from "@/lib/utils";

type ApprovalPayload = {
  invoice_id?: string; document_id?: string; kind?: string; number?: string;
  client?: string; total?: number | string; currency?: string;
  quality_score?: number; quality_status?: string;
  blocking_issues?: Array<{ code?: string; message?: string; where?: string | null; severity?: string }>;
};

export default function ApprovalsPage() {
  const { data = [], isLoading } = useApprovals();
  const decide = useDecideApproval();

  const blocked = data.filter((a) => a.status === "BLOCKED");
  const pending = data.filter((a) => a.status === "PENDING");
  const decided = data.filter((a) => a.status !== "PENDING" && a.status !== "BLOCKED");

  const onDecide = (id: string, approve: boolean, summary: string) =>
    decide.mutate({ id, approve }, {
      onSuccess: () => toast.success(approve ? "Approved" : "Rejected", summary),
      onError:   (e) => toast.error("Action failed", (e as Error).message),
    });

  return (
    <>
      <PageHeader title="Approvals" description="State-changing AI/workflow actions waiting on a human." />
      {isLoading && (
        <Card><CardContent className="p-5 text-sm text-muted-foreground animate-pulse">
          Loading approvals…
        </CardContent></Card>
      )}

      {!isLoading && pending.length === 0 && blocked.length === 0 && (
        <Card><CardContent className="p-6 text-center text-muted-foreground text-sm">
          No pending approvals 🎉
        </CardContent></Card>
      )}

      {blocked.length > 0 && (
        <section className="mb-6">
          <h3 className="mb-2 text-[11px] uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
            <ShieldAlert className="h-3.5 w-3.5 text-red-500" />
            Blocked by quality gate · {blocked.length}
          </h3>
          <div className="space-y-3">
            {blocked.map((a) => <BlockedCard key={a.id} approval={a} />)}
          </div>
        </section>
      )}

      <div className="space-y-3">
        {pending.map((a) => {
          const p = (a.payload ?? {}) as ApprovalPayload;
          return (
            <Card key={a.id} className="border-l-4 border-l-amber-500">
              <CardContent className="flex flex-col sm:flex-row sm:items-center gap-3 p-4">
                <Badge tone="warn">PENDING</Badge>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium leading-snug">{a.summary}</div>
                  <div className="mt-0.5 text-[11.5px] text-muted-foreground flex items-center gap-2 flex-wrap">
                    <Sparkles className="h-3 w-3" />
                    requested by {a.requested_by} · {new Date(a.created_at).toLocaleString()}
                    {typeof p.quality_score === "number" && (
                      <QualityBadge score={p.quality_score} status={p.quality_status} />
                    )}
                    {a.resource_type === "invoice" && (
                      <Link href={`/invoices/${a.resource_id}`} className="inline-flex items-center gap-1 hover:underline">
                        <ExternalLink className="h-3 w-3" /> open invoice
                      </Link>
                    )}
                    {a.resource_type === "document" && (
                      <Link href={`/documents/${a.resource_id}`} className="inline-flex items-center gap-1 hover:underline">
                        <ExternalLink className="h-3 w-3" /> open document
                      </Link>
                    )}
                  </div>
                </div>
                <div className="flex gap-2 sm:ml-auto">
                  <Button variant="destructive" size="sm" disabled={decide.isPending}
                    onClick={() => onDecide(a.id, false, a.summary)}>
                    <X className="h-3.5 w-3.5" /> Reject
                  </Button>
                  <Button size="sm" disabled={decide.isPending}
                    onClick={() => onDecide(a.id, true, a.summary)}>
                    <Check className="h-3.5 w-3.5" /> Approve
                  </Button>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {decided.length > 0 && (
        <>
          <h3 className="mt-8 mb-2 text-[11px] uppercase tracking-wider text-muted-foreground">Recently decided</h3>
          <div className="space-y-2">
            {decided.slice(0, 12).map((a) => (
              <Card key={a.id}>
                <CardContent className="flex items-center gap-3 p-3 text-sm">
                  <Badge tone={a.status === "APPROVED" ? "success" : "danger"}>{a.status}</Badge>
                  <span className="flex-1 min-w-0 truncate">{a.summary}</span>
                  <span className="text-xs text-muted-foreground hidden sm:block">{a.decided_by ?? "—"}</span>
                </CardContent>
              </Card>
            ))}
          </div>
        </>
      )}
    </>
  );
}


function BlockedCard({ approval }: { approval: any }) {
  const p = (approval.payload ?? {}) as ApprovalPayload;
  const diagnostics: Diagnostic[] = (p.blocking_issues ?? []).map((i) => ({
    stage: "quality", code: i.code, message: i.message,
    severity: (i.severity as any) ?? "error", where: i.where ?? null,
  }));
  return (
    <Card className={cn("border-l-4 border-l-red-500")}>
      <CardContent className="p-4 space-y-3">
        <div className="flex flex-wrap items-start gap-2.5">
          <Badge tone="danger">BLOCKED</Badge>
          {typeof p.quality_score === "number" && (
            <QualityBadge score={p.quality_score} status={p.quality_status} />
          )}
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium leading-snug">{approval.summary}</div>
            <div className="mt-0.5 text-[11.5px] text-muted-foreground flex flex-wrap items-center gap-x-2 gap-y-0.5">
              <Sparkles className="h-3 w-3" />
              {approval.requested_by} · {new Date(approval.created_at).toLocaleString()}
              {p.client && <span>· {p.client}</span>}
              {p.number && <span className="font-mono">{p.number}</span>}
              {approval.resource_type === "document" && approval.resource_id && (
                <Link href={`/documents/${approval.resource_id}`} className="inline-flex items-center gap-1 hover:underline">
                  <ExternalLink className="h-3 w-3" /> open document
                </Link>
              )}
            </div>
          </div>
        </div>
        {diagnostics.length > 0 && (
          <DiagnosticsPanel diagnostics={diagnostics} title="Why this is blocked" compact />
        )}
        <div className="rounded-md bg-card/70 ring-1 ring-border/50 px-3 py-2 text-[11.5px] text-muted-foreground">
          <span className="font-medium text-foreground/80">Resolution:</span>{" "}
          Fix the missing fields above, then regenerate the document. The quality gate
          will release the approval automatically once the score crosses 60.
        </div>
      </CardContent>
    </Card>
  );
}
