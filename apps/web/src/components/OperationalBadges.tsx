"use client";

import { ShieldCheck, FileCheck2, Gauge, Timer, FileText } from "lucide-react";
import { cn } from "@/lib/utils";

/** Small confidence-layer badges shown on AI-generated documents and approvals.
 *
 * Each badge is independent and renders only when the data is present, so
 * cards stay clean for cold-start templates and degrade gracefully when
 * scoring isn't yet available.
 */
export function OperationalBadges({
  verified,
  operationalScore,
  qualityScore,
  qualityStatus,
  pdfReady,
  renderMs,
  templateFormat,
  className,
}: {
  verified?: boolean;
  operationalScore?: number | null;
  qualityScore?: number | null;
  qualityStatus?: string | null;
  pdfReady?: boolean;
  renderMs?: number | null;
  templateFormat?: string | null;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-wrap items-center gap-1.5", className)}>
      {verified && <VerifiedBadge />}
      {typeof operationalScore === "number" && (
        <OperationalScoreBadge score={operationalScore} />
      )}
      {typeof qualityScore === "number" && (
        <QualityBadge score={qualityScore} status={qualityStatus} />
      )}
      {pdfReady && <PdfReadyBadge templateFormat={templateFormat} />}
      {typeof renderMs === "number" && renderMs > 0 && (
        <RenderTimeBadge ms={renderMs} />
      )}
    </div>
  );
}


function Pill({
  Icon, children, tone,
}: {
  Icon: any; children: React.ReactNode;
  tone: "verified" | "ok" | "warn" | "danger" | "neutral";
}) {
  const TONE: Record<string, string> = {
    verified: "bg-emerald-500/10 text-emerald-500 ring-emerald-500/25",
    ok:       "bg-sky-500/10 text-sky-500 ring-sky-500/25",
    warn:     "bg-amber-500/10 text-amber-500 ring-amber-500/25",
    danger:   "bg-red-500/10 text-red-500 ring-red-500/25",
    neutral:  "bg-card text-muted-foreground ring-border/60",
  };
  return (
    <span className={cn(
      "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 tabular-nums whitespace-nowrap",
      TONE[tone],
    )}>
      <Icon className="h-3 w-3" />
      {children}
    </span>
  );
}


export function VerifiedBadge() {
  return (
    <Pill Icon={ShieldCheck} tone="verified">
      <span>VERIFIED template</span>
    </Pill>
  );
}


export function OperationalScoreBadge({ score }: { score: number }) {
  const tone = score >= 85 ? "verified" : score >= 70 ? "ok" : score >= 50 ? "warn" : "danger";
  return (
    <Pill Icon={Gauge} tone={tone}>
      <span>Reliability {score}/100</span>
    </Pill>
  );
}


export function QualityBadge({
  score, status,
}: { score: number; status?: string | null }) {
  const tone =
    status === "blocked" || score < 60 ? "danger" :
    status === "warning" || score < 80 ? "warn" :
                                          "ok";
  return (
    <Pill Icon={FileCheck2} tone={tone}>
      <span>Quality {score}/100</span>
    </Pill>
  );
}


export function PdfReadyBadge({ templateFormat }: { templateFormat?: string | null }) {
  return (
    <Pill Icon={FileText} tone="verified">
      <span>PDF ready</span>
      {templateFormat && templateFormat !== "html" && (
        <span className="ml-1 opacity-70 font-mono uppercase">{templateFormat}</span>
      )}
    </Pill>
  );
}


export function RenderTimeBadge({ ms }: { ms: number }) {
  // Tone shifts when render starts feeling sluggish so the operator notices
  // performance regressions without us having to wire up sparkline charts.
  const tone = ms < 3000 ? "ok" : ms < 6000 ? "neutral" : "warn";
  const display = ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)}s`;
  return (
    <Pill Icon={Timer} tone={tone}>
      <span>Rendered in {display}</span>
    </Pill>
  );
}
