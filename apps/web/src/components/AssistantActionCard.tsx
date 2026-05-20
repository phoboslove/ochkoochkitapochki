"use client";

import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge, StatusDot } from "@/components/ui/badge";
import { CheckCircle2, X, FileText, Receipt, ListChecks, Sparkles, ChevronRight } from "lucide-react";
import { formatKZT } from "@/lib/utils";
import { useDecideApproval } from "@/lib/hooks";
import { toast } from "@/components/Toaster";

type ToolCall = { name: string; args: any; result: any };

export function AssistantActionCard({ tc }: { tc: ToolCall }) {
  const decide = useDecideApproval();

  if (tc.result?.error === "confirmation_required") {
    return (
      <Card className="mt-2 border-l-[3px] border-l-[hsl(var(--warning))]">
        <CardContent className="p-3.5 text-[13px] space-y-1.5">
          <div className="flex items-center gap-2 text-[12px] font-medium text-[hsl(var(--warning))] uppercase tracking-wider">
            <CheckCircle2 className="h-3.5 w-3.5" /> Confirmation required
          </div>
          <div>{tc.result.message}</div>
          <div className="text-[11px] text-muted-foreground">
            Reply <span className="kbd">yes, confirm {tc.result.amount} KZT</span> to proceed.
          </div>
        </CardContent>
      </Card>
    );
  }

  if (tc.result?.error === "permission_denied") {
    return (
      <Card className="mt-2 border-l-[3px] border-l-[hsl(var(--danger))]">
        <CardContent className="p-3.5 text-[13px] flex items-center gap-2">
          <X className="h-3.5 w-3.5 text-[hsl(var(--danger))]" />
          <span><strong>Blocked:</strong> {tc.result.message}</span>
        </CardContent>
      </Card>
    );
  }

  if (tc.result?.error === "invalid_args") {
    return (
      <Card className="mt-2 border-l-[3px] border-l-[hsl(var(--warning))]">
        <CardContent className="p-3.5 text-[13px] text-muted-foreground">
          Couldn't parse arguments — please rephrase.
        </CardContent>
      </Card>
    );
  }

  if (tc.name === "create_invoice") {
    const r = tc.result || {};
    const onDecide = (approve: boolean) => {
      if (!r.approval_id) return;
      decide.mutate({ id: r.approval_id, approve }, {
        onSuccess: () => toast.success(approve ? "Approved" : "Rejected", `${r.number} — ${approve ? "sending" : "cancelled"}`),
        onError:   (e) => toast.error("Action failed", (e as Error).message),
      });
    };

    return (
      <Card className="mt-2 border-l-[3px] border-l-[hsl(var(--warning))]">
        <CardContent className="px-4 py-3">
          <div className="flex items-center gap-2 mb-2.5">
            <span className="inline-flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
              <Sparkles className="h-3 w-3" /> AI-generated
            </span>
            <Receipt className="h-3.5 w-3.5 text-muted-foreground ml-1" />
            <span className="text-[13px] font-medium">Invoice draft</span>
            <Badge tone="warn" className="ml-auto">{r.status ?? "PENDING"}</Badge>
          </div>

          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-[12.5px]">
            <dt className="text-muted-foreground">Number</dt>
            <dd className="font-mono">{r.number ?? "—"}</dd>
            <dt className="text-muted-foreground">Total</dt>
            <dd className="tabular-nums font-medium">{r.total ? `${formatKZT(Number(r.total))} ${r.currency ?? ""}` : "—"}</dd>
            <dt className="text-muted-foreground">Template</dt>
            <dd className="truncate">
              {r.template_name
                ? <><span className="font-medium">{r.template_name}</span>
                    <span className="ml-1 text-[10.5px] text-muted-foreground">({r.template_format})</span></>
                : <span className="text-muted-foreground">Built-in HTML (no VERIFIED template)</span>}
            </dd>
            <dt className="text-muted-foreground">Action</dt>
            <dd>Send to client (requires your approval)</dd>
          </dl>

          {Array.isArray(r.needs_review) && r.needs_review.length > 0 && !r.template_name && (
            <div className="mt-2.5 rounded-md border border-[hsl(var(--warning)/0.4)] bg-warning-bg p-2 text-[11.5px]">
              <div className="font-medium text-[hsl(var(--warning))] mb-0.5">
                {r.needs_review.length} template{r.needs_review.length === 1 ? "" : "s"} exist but are not VERIFIED yet
              </div>
              <ul className="space-y-0.5">
                {r.needs_review.slice(0, 3).map((t: any) => (
                  <li key={t.id} className="flex items-center gap-2">
                    <span className="truncate">{t.name}</span>
                    <Link href={`/settings/templates/${t.id}`} className="text-[hsl(var(--brand))] hover:underline text-[11px] ml-auto">
                      Confirm mappings →
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="mt-3 flex flex-wrap items-center gap-1.5 pt-3 border-t border-border">
            <Link href={`/invoices/${r.invoice_id}`}>
              <Button size="sm" variant="ghost">
                Open invoice <ChevronRight className="h-3.5 w-3.5" />
              </Button>
            </Link>
            {r.pdf_url && (
              <a href={`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}${r.pdf_url}`}
                 target="_blank" rel="noreferrer">
                <Button size="sm" variant="outline">Download PDF</Button>
              </a>
            )}
            {r.approval_id && (
              <div className="ml-auto flex gap-1.5">
                <Button size="sm" variant="ghost" disabled={decide.isPending}
                  onClick={() => onDecide(false)}><X className="h-3.5 w-3.5" /> Reject</Button>
                <Button size="sm" disabled={decide.isPending}
                  onClick={() => onDecide(true)}><CheckCircle2 className="h-3.5 w-3.5" /> Approve & send</Button>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    );
  }

  if (tc.name === "list_invoices") {
    const list = tc.result?.invoices ?? [];
    return (
      <Card className="mt-2">
        <CardContent className="px-4 py-3">
          <div className="flex items-center gap-2 mb-2">
            <ListChecks className="h-3.5 w-3.5 text-muted-foreground" />
            <span className="text-[13px] font-medium">Invoices</span>
            <Badge tone="neutral" className="ml-auto">{list.length}</Badge>
          </div>
          {list.length === 0
            ? <div className="text-[12px] text-muted-foreground">No matching invoices.</div>
            : <ul className="divide-y divide-border -mx-1">
                {list.slice(0, 6).map((i: any) => (
                  <li key={i.id} className="flex items-center gap-2 px-1 py-1.5 text-[12.5px]">
                    <StatusDot tone={i.status === "PAID" ? "success" : i.status === "OVERDUE" ? "danger" : "info"} />
                    <span className="font-medium">{i.number}</span>
                    <span className="text-muted-foreground text-[11px]">{i.status}</span>
                    <span className="ml-auto tabular-nums">{formatKZT(Number(i.total))} {i.currency}</span>
                    <Link href={`/invoices/${i.id}`} className="text-muted-foreground hover:text-foreground">
                      <ChevronRight className="h-3.5 w-3.5" />
                    </Link>
                  </li>
                ))}
              </ul>}
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="mt-2"><CardContent className="px-3 py-2 text-[12px]">
      <div className="flex items-center gap-2 mb-1 text-muted-foreground">
        <FileText className="h-3.5 w-3.5" /> tool · {tc.name}
      </div>
      <pre className="text-[11px] text-muted-foreground overflow-x-auto">{JSON.stringify(tc.result, null, 2)}</pre>
    </CardContent></Card>
  );
}
