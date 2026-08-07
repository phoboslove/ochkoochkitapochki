"use client";

import Link from "next/link";
import { Check, X } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useApprovals, useDecideApproval } from "@/lib/hooks";
import { toast } from "@/components/Toaster";

export function PendingApprovalsWidget() {
  const { data: approvals } = useApprovals();
  const decide = useDecideApproval();

  const pending = (approvals ?? [])
    .filter((a) => a.status === "PENDING")
    .sort((a, b) => +new Date(b.created_at) - +new Date(a.created_at))
    .slice(0, 5);

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Ожидают подтверждения</CardTitle>
        <Link href="/approvals" className="text-[11px] text-muted-foreground hover:text-foreground transition-colors">
          Все →
        </Link>
      </CardHeader>
      <CardContent className="pt-0">
        {pending.length === 0 ? (
          <div className="text-[13px] text-muted-foreground py-2 flex items-center gap-2">
            <span className="h-1.5 w-1.5 rounded-full bg-[hsl(var(--success))]" />
            Нечего подтверждать.
          </div>
        ) : (
          <ul className="divide-y divide-border -mx-5">
            {pending.map((a) => (
              <li key={a.id} className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-3 px-5 py-3 hover:bg-accent/30 transition-colors">
                <Badge tone="warn">Ожидает</Badge>
                <div className="flex-1 min-w-0">
                  <div className="text-[13px] font-medium truncate">{a.summary}</div>
                  <div className="text-[11px] text-muted-foreground">
                    {new Date(a.created_at).toLocaleString("ru-RU")}
                  </div>
                </div>
                <div className="flex gap-1.5">
                  <Button size="sm" variant="ghost" disabled={decide.isPending}
                    onClick={() => decide.mutate({ id: a.id, approve: false }, {
                      onSuccess: () => toast.success("Отклонено"),
                    })}><X className="h-3.5 w-3.5" /> Отклонить</Button>
                  <Button size="sm" disabled={decide.isPending}
                    onClick={() => decide.mutate({ id: a.id, approve: true }, {
                      onSuccess: () => toast.success("Подтверждено"),
                    })}><Check className="h-3.5 w-3.5" /> Подтвердить</Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
