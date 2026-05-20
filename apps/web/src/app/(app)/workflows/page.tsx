import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Table, THead, TR, TH, TD } from "@/components/ui/table";
import { workflows } from "@/lib/mock";
import { Plus, Play } from "lucide-react";

export default function WorkflowsPage() {
  return (
    <>
      <PageHeader
        title="Workflows"
        description="Triggers → AI parsing → actions → approvals → notifications."
        actions={<Button><Plus className="h-4 w-4" /> New workflow</Button>}
      />
      <Card>
        <CardContent className="p-0">
          <Table>
            <THead>
              <TR><TH>Name</TH><TH>Trigger</TH><TH>Status</TH><TH>Last run</TH><TH></TH></TR>
            </THead>
            <tbody>
              {workflows.map((w) => (
                <TR key={w.id}>
                  <TD className="font-medium">{w.name}</TD>
                  <TD className="text-muted-foreground font-mono text-xs">{w.trigger}</TD>
                  <TD><Badge tone={w.enabled ? "success" : "neutral"}>{w.enabled ? "enabled" : "paused"}</Badge></TD>
                  <TD className="text-muted-foreground">{w.last_run}</TD>
                  <TD className="text-right">
                    <Button variant="ghost" size="sm"><Play className="h-3.5 w-3.5" /> Run</Button>
                  </TD>
                </TR>
              ))}
            </tbody>
          </Table>
        </CardContent>
      </Card>
    </>
  );
}
