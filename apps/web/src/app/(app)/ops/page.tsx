"use client";

import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Table, THead, TR, TH, TD } from "@/components/ui/table";
import { useMe, useOcrBenchmark, useOperationalMetrics } from "@/lib/hooks";

export default function OpsPage() {
  const { data: me } = useMe();
  const { data, isLoading } = useOperationalMetrics();
  const { data: bench } = useOcrBenchmark();

  if (me && me.role !== "OWNER" && me.role !== "ADMIN") {
    return <div className="text-sm text-muted-foreground">Admins only.</div>;
  }
  if (isLoading || !data) return <div className="text-sm text-muted-foreground">Loading…</div>;

  const ocr = data.ocr, wf = data.workflows, ap = data.approvals, tools = data.ai_tools;

  return (
    <>
      <PageHeader title="Operations" description="Pilot health metrics — last 30 days." />

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
        <Stat label="OCR success" value={pct(1 - (ocr.failure_rate ?? 0))} tone={ocr.failure_rate > 0.1 ? "danger" : "success"} />
        <Stat label="Avg confidence" value={ocr.avg_confidence == null ? "—" : `${(ocr.avg_confidence*100).toFixed(0)}%`} />
        <Stat label="Workflow success" value={pct(wf.success_rate ?? 0)} tone={(wf.success_rate ?? 1) < 0.95 ? "warn" : "success"} />
        <Stat label="Approval latency" value={ap.avg_latency_seconds == null ? "—" : fmtDuration(ap.avg_latency_seconds)} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader><CardTitle>Documents</CardTitle></CardHeader>
          <CardContent className="text-sm space-y-1">
            <Row k="Uploaded" v={ocr.documents_total} />
            <Row k="Parsed"   v={ocr.documents_parsed} />
            <Row k="Failed"   v={ocr.documents_failed} tone={ocr.documents_failed > 0 ? "danger" : "neutral"} />
            <Row k="Needs review" v={ocr.needs_review} tone={ocr.needs_review > 0 ? "warn" : "neutral"} />
            <Row k="Low-confidence rate" v={ocr.low_confidence_pct == null ? "—" : pct(ocr.low_confidence_pct)} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>Approvals</CardTitle></CardHeader>
          <CardContent className="text-sm space-y-1">
            <Row k="Requested" v={ap.requested} />
            <Row k="Decided"   v={ap.decided} />
            <Row k="Median latency" v={ap.median_latency_seconds == null ? "—" : fmtDuration(ap.median_latency_seconds)} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>Workflows & recovery</CardTitle></CardHeader>
          <CardContent className="text-sm space-y-1">
            <Row k="Runs"     v={wf.runs} />
            <Row k="Failures" v={wf.failures} tone={wf.failures > 0 ? "danger" : "neutral"} />
            <Row k="Unique failure types" v={data.recovery.unique_failures} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>AI tool usage</CardTitle></CardHeader>
          <CardContent className="text-sm space-y-1">
            <Row k="Invocations"        v={tools.invoked} />
            <Row k="Denied (guardrail)" v={tools.denied} tone={tools.denied > 0 ? "warn" : "neutral"} />
            <Row k="Invoices created"   v={data.invoices.created} />
            <Row k="Invoices sent"      v={data.invoices.sent} />
          </CardContent>
        </Card>
      </div>

      {bench && (
        <div className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>OCR benchmark by file type</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <Table>
                <THead><TR>
                  <TH>MIME</TH><TH>Docs</TH><TH>Avg conf.</TH>
                  <TH>Low-conf</TH><TH>Failed</TH><TH>Manually corrected</TH><TH>Correction rate</TH>
                </TR></THead>
                <tbody>
                  {(bench.cohorts ?? []).map((c: any) => (
                    <TR key={c.mime}>
                      <TD className="font-mono text-xs">{c.mime}</TD>
                      <TD>{c.count}</TD>
                      <TD>{c.avg_confidence == null ? "—" : `${(c.avg_confidence*100).toFixed(0)}%`}</TD>
                      <TD>{c.low_confidence}</TD>
                      <TD>{c.failed}</TD>
                      <TD>{c.corrected}</TD>
                      <TD>
                        <Badge tone={c.correction_rate > 0.4 ? "danger" : c.correction_rate > 0.2 ? "warn" : "success"}>
                          {pct(c.correction_rate)}
                        </Badge>
                      </TD>
                    </TR>
                  ))}
                </tbody>
              </Table>
              <p className="text-xs text-muted-foreground p-3">
                Correction rate = share of documents whose OCR fields were edited by humans. High values flag OCR provider gaps.
              </p>
            </CardContent>
          </Card>
        </div>
      )}
    </>
  );
}

function Stat({ label, value, tone = "neutral" }: { label: string; value: string; tone?: "success" | "warn" | "danger" | "neutral" }) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="text-xs text-muted-foreground">{label}</div>
        <div className={"text-xl font-semibold mt-1 " + (tone === "danger" ? "text-red-600" : tone === "warn" ? "text-amber-600" : tone === "success" ? "text-emerald-600" : "")}>{value}</div>
      </CardContent>
    </Card>
  );
}
function Row({ k, v, tone = "neutral" }: { k: string; v: any; tone?: "danger" | "warn" | "neutral" }) {
  return (
    <div className="flex justify-between border-b last:border-0 py-1">
      <span className="text-muted-foreground">{k}</span>
      <span className={"tabular-nums " + (tone === "danger" ? "text-red-600" : tone === "warn" ? "text-amber-600" : "")}>{v ?? "—"}</span>
    </div>
  );
}
function pct(n: number): string { return `${Math.round(n * 100)}%`; }
function fmtDuration(s: number): string {
  if (s < 60) return `${Math.round(s)}s`;
  if (s < 3600) return `${Math.round(s/60)}m`;
  return `${(s/3600).toFixed(1)}h`;
}
