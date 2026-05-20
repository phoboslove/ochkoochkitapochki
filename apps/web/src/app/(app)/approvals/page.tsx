"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useApprovals, useDecideApproval } from "@/lib/hooks";
import { Check, X, ExternalLink, Sparkles } from "lucide-react";
import { toast } from "@/components/Toaster";

export default function ApprovalsPage() {
  const { data = [], isLoading } = useApprovals();
  const decide = useDecideApproval();

  const pending = data.filter((a) => a.status === "PENDING");
  const decided = data.filter((a) => a.status !== "PENDING");

  const onDecide = (id: string, approve: boolean, summary: string) =>
    decide.mutate({ id, approve }, {
      onSuccess: () => toast.success(approve ? "Approved" : "Rejected", summary),
      onError:   (e) => toast.error("Action failed", (e as Error).message),
    });

  return (
    <>
      <PageHeader title="Approvals" description="State-changing AI/workflow actions waiting on a human." />
      {isLoading && <div className="text-muted-foreground text-sm">Loading…</div>}
      {!isLoading && pending.length === 0 && (
        <Card><CardContent className="p-6 text-center text-muted-foreground text-sm">
          No pending approvals 🎉
        </CardContent></Card>
      )}
      <div className="space-y-3">
        {pending.map((a) => (
          <Card key={a.id} className="border-l-4 border-l-amber-500">
            <CardContent className="flex flex-col sm:flex-row sm:items-center gap-3 p-4">
              <Badge tone="warn">PENDING</Badge>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium">{a.summary}</div>
                <div className="mt-0.5 text-xs text-muted-foreground flex items-center gap-2 flex-wrap">
                  <Sparkles className="h-3 w-3" /> requested by {a.requested_by} · {new Date(a.created_at).toLocaleString()}
                  {a.resource_type === "invoice" && (
                    <Link href={`/invoices/${a.resource_id}`} className="inline-flex items-center gap-1 hover:underline">
                      <ExternalLink className="h-3 w-3" /> open invoice
                    </Link>
                  )}
                </div>
              </div>
              <div className="flex gap-2 sm:ml-auto">
                <Button variant="destructive" size="sm" disabled={decide.isPending}
                  onClick={() => onDecide(a.id, false, a.summary)}><X className="h-3.5 w-3.5" /> Reject</Button>
                <Button size="sm" disabled={decide.isPending}
                  onClick={() => onDecide(a.id, true, a.summary)}><Check className="h-3.5 w-3.5" /> Approve</Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {decided.length > 0 && (
        <>
          <h3 className="mt-8 mb-2 text-xs uppercase tracking-wider text-muted-foreground">Recently decided</h3>
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
