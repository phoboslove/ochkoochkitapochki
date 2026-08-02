"use client";

import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent } from "@/components/ui/card";
import { Table, THead, TR, TH, TD } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { useAuditLog } from "@/lib/hooks";

export default function LogsPage() {
  const { data = [], isLoading } = useAuditLog();
  return (
    <>
      <PageHeader title="Audit logs" description="Every state-changing action — who, what, when." />
      <Card>
        <CardContent className="p-0">
          <Table>
            <THead><TR><TH>Time</TH><TH>Actor</TH><TH>Action</TH><TH>Resource</TH></TR></THead>
            <tbody>
              {isLoading && <TR><TD colSpan={4} className="text-center text-muted-foreground py-6">Loading…</TD></TR>}
              {data.map((l) => (
                <TR key={l.id}>
                  <TD className="font-mono text-xs text-muted-foreground">{new Date(l.at).toLocaleString()}</TD>
                  <TD>
                    <Badge tone={l.actor_type === "ai" ? "info" : l.actor_type === "user" ? "success" : "neutral"}>
                      {l.actor_type}{l.actor_id ? `:${l.actor_id}` : ""}
                    </Badge>
                  </TD>
                  <TD className="font-mono text-xs">{l.action}</TD>
                  <TD className="font-mono text-xs text-muted-foreground">{l.resource ?? "—"}</TD>
                </TR>
              ))}
            </tbody>
          </Table>
        </CardContent>
      </Card>
    </>
  );
}
