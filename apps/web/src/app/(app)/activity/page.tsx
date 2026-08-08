"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { useAuditLog, useUsageAnalytics } from "@/lib/hooks";
import { Sparkles, ShieldCheck, FileText, Plug, Workflow, User, AlertTriangle, Activity } from "lucide-react";

type Cat = "all" | "ai" | "approvals" | "documents" | "workflows" | "integrations" | "users";

const CATS: { key: Cat; label: string; icon: any; match: (a: string, t: string) => boolean }[] = [
  { key: "all",          label: "All",          icon: Activity,    match: () => true },
  { key: "ai",           label: "AI",           icon: Sparkles,    match: (a, t) => t === "ai" || a.startsWith("ai.") },
  { key: "approvals",    label: "Approvals",    icon: ShieldCheck, match: (a) => a.startsWith("approval.") },
  { key: "documents",    label: "Documents",    icon: FileText,    match: (a) => a.startsWith("document.") },
  { key: "workflows",    label: "Workflows",    icon: Workflow,    match: (a) => a.startsWith("workflow.") },
  { key: "integrations", label: "Integrations", icon: Plug,
    match: (a) => a.startsWith("whatsapp.") || a.startsWith("telegram.") || a.startsWith("kaspi.") || a.startsWith("email.") },
  { key: "users",        label: "Users",        icon: User,        match: (_a, t) => t === "user" },
];

export default function ActivityPage() {
  const { data: logs = [] } = useAuditLog();
  const { data: usage } = useUsageAnalytics();
  const [cat, setCat] = useState<Cat>("all");
  const [q, setQ] = useState("");

  const filtered = useMemo(() => {
    const c = CATS.find((x) => x.key === cat)!;
    return logs.filter((l) => c.match(l.action, l.actor_type) &&
      (q === "" ||
        l.action.toLowerCase().includes(q.toLowerCase()) ||
        (l.resource ?? "").toLowerCase().includes(q.toLowerCase())));
  }, [logs, cat, q]);

  return (
    <>
      <PageHeader title="Activity center" description="Mission control — every AI action, approval, upload, workflow event, and user action." />

      {usage && (
        <div className="mb-5 grid grid-cols-2 sm:grid-cols-4 gap-3">
          <Stat label="AI tool calls (30d)" value={usage.ai_tool_invocations} />
          <Stat label="Approvals decided"   value={usage.approvals_decided} tone={usage.approvals_decided > 0 ? "success" : "neutral"} />
          <Stat label="Workflow failures"   value={usage.workflow_failures} tone={usage.workflow_failures > 0 ? "danger" : "neutral"} />
          <Stat label="Documents uploaded"  value={usage.documents_uploaded} />
        </div>
      )}

      <div className="flex flex-wrap gap-2 mb-3">
        {CATS.map((c) => {
          const I = c.icon;
          return (
            <button key={c.key} onClick={() => setCat(c.key)}
              className={"inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs " +
                (cat === c.key ? "bg-primary text-primary-foreground border-primary" : "hover:bg-accent")}>
              <I className="h-3 w-3" /> {c.label}
            </button>
          );
        })}
        <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter by action or resource…"
               className="ml-auto w-full sm:w-64 h-7 text-xs" />
      </div>

      <Card>
        <CardContent className="p-0">
          {filtered.length === 0 ? (
            <div className="p-8 text-center text-sm text-muted-foreground">
              <Activity className="h-5 w-5 mx-auto mb-2 opacity-60" /> No matching activity.
            </div>
          ) : (
            <ul className="divide-y">
              {filtered.map((l) => (
                <li key={l.id} className="flex items-start gap-3 p-3 text-sm">
                  <span className="w-32 shrink-0 text-xs text-muted-foreground tabular-nums">
                    {new Date(l.at).toLocaleString()}
                  </span>
                  <Badge tone={l.actor_type === "ai" ? "info" : l.actor_type === "user" ? "success" : "neutral"}>
                    {l.actor_type}{l.actor_id ? `:${l.actor_id.slice(0, 14)}` : ""}
                  </Badge>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-mono text-xs">{l.action}</span>
                      {l.action.includes("failed") && <AlertTriangle className="h-3 w-3 text-[hsl(var(--danger))]" />}
                      {l.resource && (
                        <Link
                          href={l.resource.startsWith("inv_") ? `/invoices/${l.resource}` :
                                l.resource.startsWith("doc_") ? `/documents/${l.resource}` : "#"}
                          className="text-xs text-muted-foreground hover:underline"
                        >{l.resource}</Link>
                      )}
                    </div>
                    {l.meta && Object.keys(l.meta).length > 0 && (
                      <div className="text-[11px] text-muted-foreground mt-0.5 truncate">
                        {Object.entries(l.meta).slice(0, 4).map(([k, v]) => (
                          <span key={k} className="mr-3"><span className="opacity-60">{k}:</span> <span className="font-mono">{String(v).slice(0, 80)}</span></span>
                        ))}
                      </div>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </>
  );
}

function Stat({ label, value, tone = "neutral" }: { label: string; value: number; tone?: "success" | "danger" | "neutral" }) {
  return (
    <Card>
      <CardContent className="p-3">
        <div className="text-xs text-muted-foreground">{label}</div>
        <div className={"text-xl font-semibold " + (tone === "danger" ? "text-[hsl(var(--danger))]" : tone === "success" ? "text-[hsl(var(--success))]" : "")}>{value}</div>
      </CardContent>
    </Card>
  );
}
