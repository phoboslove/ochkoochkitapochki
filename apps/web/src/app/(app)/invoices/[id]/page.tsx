"use client";

import { useParams } from "next/navigation";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, THead, TR, TH, TD } from "@/components/ui/table";
import { useInvoice, useRetryInvoiceSend, useExportInvoicePdf } from "@/lib/hooks";
import { formatKZT } from "@/lib/utils";
import { api } from "@/lib/api";
import { WorkflowTimeline } from "@/components/WorkflowTimeline";
import { toast } from "@/components/Toaster";
import { RefreshCw, Download } from "lucide-react";

export default function InvoiceDetailPage() {
  const params = useParams<{ id: string }>();
  const { data, isLoading } = useInvoice(params.id);
  const retry = useRetryInvoiceSend();
  const pdf   = useExportInvoicePdf();

  if (isLoading || !data) return <div className="text-muted-foreground">Loading…</div>;
  const previewUrl = data.pdf_url ? api.fileUrl(data.pdf_url) : null;

  return (
    <>
      <PageHeader
        title={`Invoice ${data.number}`}
        description={`${data.client?.name ?? "—"} · ${data.issue_date ?? ""}`}
        actions={
          <div className="flex gap-2">
            {(data.status === "SENT" || data.status === "APPROVED") && (
              <Button variant="outline" disabled={retry.isPending}
                onClick={() => retry.mutate(data.id, {
                  onSuccess: () => toast.success("Resent", `${data.number} resent via WhatsApp`),
                  onError:   (e) => toast.error("Send failed", (e as Error).message),
                })}>
                <RefreshCw className="h-3.5 w-3.5" /> Retry send
              </Button>
            )}
            <Button variant="outline" disabled={pdf.isPending}
              onClick={() => pdf.mutate(data.id, {
                onSuccess: (r) => { window.open(api.fileUrl(r.pdf_url), "_blank"); toast.success("PDF exported", `${(r.bytes/1024).toFixed(1)} KB`); },
                onError:   (e) => toast.error("PDF export failed", (e as Error).message),
              })}>
              <Download className="h-3.5 w-3.5" /> {pdf.isPending ? "Rendering…" : "Export PDF"}
            </Button>
            {previewUrl && (
              <a href={previewUrl} target="_blank" rel="noreferrer">
                <Button variant="outline">Open HTML</Button>
              </a>
            )}
          </div>
        }
      />
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6 order-2 lg:order-1">
          {previewUrl && (
            <Card><CardContent className="p-0">
              <iframe src={previewUrl} className="w-full h-[50vh] sm:h-[60vh] border-0" />
            </CardContent></Card>
          )}
          <Card>
            <CardHeader><CardTitle>Line items</CardTitle></CardHeader>
            <CardContent className="p-0 overflow-x-auto">
              <Table>
                <THead><TR><TH>Item</TH><TH>Qty</TH><TH>Price</TH><TH>Total</TH></TR></THead>
                <tbody>
                  {data.items.map((it, idx) => (
                    <TR key={idx}>
                      <TD>{it.name}</TD><TD>{it.qty}</TD>
                      <TD className="tabular-nums">{formatKZT(it.price)}</TD>
                      <TD className="tabular-nums">{formatKZT(it.qty * it.price)}</TD>
                    </TR>
                  ))}
                </tbody>
              </Table>
            </CardContent>
          </Card>
          <WorkflowTimeline resource={data.id} title="Invoice workflow" />
        </div>
        <div className="space-y-6 order-1 lg:order-2">
          <Card>
            <CardHeader><CardTitle>Status</CardTitle></CardHeader>
            <CardContent>
              <Badge tone={(data.status === "PAID" ? "success" : data.status === "PENDING_APPROVAL" ? "warn" : data.status === "SENT" ? "info" : "neutral") as any}>
                {data.status}
              </Badge>
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>Totals</CardTitle></CardHeader>
            <CardContent className="space-y-2 text-sm">
              <Row label="Subtotal" value={formatKZT(Number(data.subtotal))} />
              <Row label="Tax"      value={formatKZT(Number(data.tax_total))} />
              <Row label="Total"    value={formatKZT(Number(data.total))} bold />
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>Client</CardTitle></CardHeader>
            <CardContent className="text-sm space-y-1">
              <div className="font-medium">{data.client?.name ?? "—"}</div>
              <div className="text-muted-foreground">BIN {data.client?.bin ?? "—"}</div>
              <div className="text-muted-foreground">{data.client?.phone ?? ""}</div>
            </CardContent>
          </Card>
        </div>
      </div>
    </>
  );
}

function Row({ label, value, bold }: { label: string; value: string; bold?: boolean }) {
  return (
    <div className={"flex justify-between " + (bold ? "border-t pt-2 font-semibold" : "")}>
      <span className="text-muted-foreground">{label}</span><span className="tabular-nums">{value}</span>
    </div>
  );
}
