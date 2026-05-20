"use client";

import { useQuery } from "@tanstack/react-query";
import { api, type AuditEntry } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CheckCircle2, AlertTriangle, Clock, Send, FileText, Sparkles, FileSignature, MessageSquare } from "lucide-react";
import { cn } from "@/lib/utils";

type Tone = "ok" | "warn" | "err" | "muted";

const TONE: Record<Tone, string> = {
  ok:    "bg-success-bg text-[hsl(var(--success))] border-[hsl(var(--success)/0.3)]",
  warn:  "bg-warning-bg text-[hsl(var(--warning))] border-[hsl(var(--warning)/0.3)]",
  err:   "bg-danger-bg  text-[hsl(var(--danger))]  border-[hsl(var(--danger)/0.3)]",
  muted: "bg-muted text-muted-foreground border-border",
};

const ICONS: Record<string, any> = {
  "whatsapp.inbound":         MessageSquare,
  "telegram.message_received":MessageSquare,
  "ai.intent_parsed":         Sparkles,
  "invoice.create_draft":     FileText,
  "invoice.pending_approval": Clock,
  "approval.request":         FileSignature,
  "approval.decide":          CheckCircle2,
  "approval.auto_sent":       CheckCircle2,
  "invoice.approved":         CheckCircle2,
  "invoice.rejected":         AlertTriangle,
  "whatsapp.send_pdf":        Send,
  "telegram.notification_sent": Send,
  "whatsapp.send_failed":     AlertTriangle,
  "document.upload":          FileText,
  "document.parsed":          CheckCircle2,
  "document.failed":          AlertTriangle,
};

const LABELS: Record<string, string> = {
  "whatsapp.inbound":         "Message received",
  "telegram.message_received":"Telegram message",
  "ai.intent_parsed":         "AI parsed intent",
  "invoice.create_draft":     "Invoice drafted",
  "invoice.pending_approval": "Awaiting approval",
  "approval.request":         "Approval requested",
  "approval.decide":          "Approval decided",
  "approval.auto_sent":       "Auto-sent (below threshold)",
  "invoice.approved":         "Approved",
  "invoice.rejected":         "Rejected",
  "whatsapp.send_pdf":        "Sent via WhatsApp",
  "whatsapp.send_failed":     "WhatsApp delivery failed",
  "telegram.notification_sent": "Telegram notification sent",
  "document.upload":          "Document uploaded",
  "document.parsed":          "Document parsed",
  "document.failed":          "Document failed",
};

function toneOf(action: string): Tone {
  if (action.endsWith(".failed") || action.endsWith(".rejected") || action.endsWith(".denied")) return "err";
  if (action.includes("pending") || action.includes("request") || action.includes("inbound")) return "warn";
  if (action.includes("approved") || action.endsWith(".parsed") ||
      action.includes("send_pdf") || action.endsWith(".auto_sent") || action.endsWith(".notification_sent")) return "ok";
  return "muted";
}

function groupByDay(entries: AuditEntry[]): { day: string; items: AuditEntry[] }[] {
  const map = new Map<string, AuditEntry[]>();
  for (const e of entries) {
    const day = new Date(e.at).toLocaleDateString([], { day: "2-digit", month: "short", year: "numeric" });
    (map.get(day) ?? map.set(day, []).get(day)!).push(e);
  }
  return [...map.entries()].map(([day, items]) => ({ day, items }));
}

export function WorkflowTimeline({ resource, title = "Workflow timeline" }: { resource: string; title?: string }) {
  const { data = [], isLoading } = useQuery({
    queryKey: ["timeline", resource],
    queryFn: () => api.get<AuditEntry[]>(`/logs?resource=${encodeURIComponent(resource)}&limit=50`),
    refetchInterval: 6000,
  });

  const ordered = [...data].reverse();   // oldest → newest
  const groups = groupByDay(ordered);

  return (
    <Card>
      <CardHeader><CardTitle>{title}</CardTitle></CardHeader>
      <CardContent className="pt-0">
        {isLoading && <div className="text-[12px] text-muted-foreground">Loading…</div>}
        {!isLoading && ordered.length === 0 && (
          <div className="text-[12px] text-muted-foreground py-2">No activity recorded for this resource.</div>
        )}

        {groups.map((g) => (
          <div key={g.day} className="mb-4 last:mb-0">
            <div className="text-[10.5px] uppercase tracking-wider text-muted-foreground mb-2">{g.day}</div>
            <ol className="relative pl-6">
              <span className="absolute left-[11px] top-2 bottom-2 w-px bg-border" />
              {g.items.map((e) => {
                const tone = toneOf(e.action);
                const Icon = ICONS[e.action] ?? Clock;
                const label = LABELS[e.action] ?? e.action;
                return (
                  <li key={e.id} className="relative pb-3 last:pb-0">
                    <span className={cn(
                      "absolute -left-[19px] top-0.5 h-[18px] w-[18px] rounded-full grid place-items-center border",
                      TONE[tone],
                    )}>
                      <Icon className="h-2.5 w-2.5" strokeWidth={2} />
                    </span>
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-[13px] font-medium">{label}</span>
                      <Badge tone={e.actor_type === "ai" ? "info" : e.actor_type === "user" ? "success" : "neutral"}>
                        {e.actor_type}
                      </Badge>
                      <span className="ml-auto text-[11px] text-muted-foreground tabular-nums">
                        {new Date(e.at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                      </span>
                    </div>
                    {e.meta && Object.keys(e.meta).length > 0 && (
                      <div className="mt-0.5 text-[11px] text-muted-foreground">
                        {Object.entries(e.meta).slice(0, 4).map(([k, v]) => (
                          <span key={k} className="mr-3">
                            <span className="opacity-60">{k}:</span> <span className="font-mono">{String(v).slice(0, 60)}</span>
                          </span>
                        ))}
                      </div>
                    )}
                  </li>
                );
              })}
            </ol>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
