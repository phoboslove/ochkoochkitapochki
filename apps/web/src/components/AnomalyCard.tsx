"use client";

import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useAnomalies } from "@/lib/hooks";
import { AlertTriangle } from "lucide-react";

export function AnomalyCard() {
  const { data = [], isLoading } = useAnomalies();
  if (isLoading || data.length === 0) return null;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <AlertTriangle className="h-3.5 w-3.5 text-[hsl(var(--warning))]" /> Anomalies ({data.length})
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ul className="space-y-2">
          {data.slice(0, 6).map((a: any) => (
            <li key={a.id} className="flex items-start gap-2 text-sm">
              <Badge tone={a.severity === "high" ? "danger" : a.severity === "warn" ? "warn" : "info"}>{a.kind}</Badge>
              <span className="flex-1 min-w-0">{a.message}</span>
              {a.resource?.startsWith("inv_") && (
                <Link href={`/invoices/${a.resource}`} className="text-xs text-muted-foreground hover:underline">view</Link>
              )}
            </li>
          ))}
        </ul>
        <p className="mt-3 text-xs text-muted-foreground">
          Detections only — no autonomous actions are taken on these signals.
        </p>
      </CardContent>
    </Card>
  );
}
