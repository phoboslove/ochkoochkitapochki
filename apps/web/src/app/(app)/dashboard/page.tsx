"use client";

import { useMemo } from "react";
import { FileCheck2, Hourglass, ShieldAlert } from "lucide-react";
import { GreetingClock } from "@/components/dashboard/GreetingClock";
import { QuickCreateWidget } from "@/components/dashboard/QuickCreateWidget";
import { StatTile } from "@/components/dashboard/StatTile";
import { PendingApprovalsWidget } from "@/components/dashboard/PendingApprovalsWidget";
import { RecentDocumentsWidget } from "@/components/dashboard/RecentDocumentsWidget";
import { MiniCalendar } from "@/components/dashboard/MiniCalendar";
import { useMe, useDocuments, useApprovals } from "@/lib/hooks";

export default function DashboardPage() {
  const { data: me } = useMe();
  const { data: documents, isLoading: docsLoading } = useDocuments();
  const { data: approvals, isLoading: appsLoading } = useApprovals();

  const initialLoading = (docsLoading && !documents) || (appsLoading && !approvals);

  const monthStats = useMemo(() => {
    const now = new Date();
    const firstOfMonth = new Date(now.getFullYear(), now.getMonth(), 1);
    const docs = documents ?? [];
    const apps = approvals ?? [];
    return {
      generated: docs.filter((d) => d.status === "GENERATED" && new Date(d.created_at) >= firstOfMonth).length,
      pending:   apps.filter((a) => a.status === "PENDING"   && new Date(a.created_at) >= firstOfMonth).length,
      blocked:   apps.filter((a) => a.status === "BLOCKED"   && new Date(a.created_at) >= firstOfMonth).length,
    };
  }, [documents, approvals]);

  if (initialLoading) return <DashboardLoadingShell />;

  return (
    <div className="space-y-5 animate-fadeIn">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <GreetingClock name={me?.name} />
        <QuickCreateWidget />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatTile label="Документов сгенерировано" value={monthStats.generated}
          hint="за этот месяц" icon={FileCheck2} tone="success" />
        <StatTile label="На подтверждении" value={monthStats.pending}
          hint="за этот месяц" icon={Hourglass} tone={monthStats.pending > 0 ? "warn" : "neutral"} />
        <StatTile label="Заблокировано QA" value={monthStats.blocked}
          hint="за этот месяц" icon={ShieldAlert} tone={monthStats.blocked > 0 ? "danger" : "neutral"} />
      </div>

      <PendingApprovalsWidget />
      <RecentDocumentsWidget />

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
        <MiniCalendar />
      </div>
    </div>
  );
}

function DashboardLoadingShell() {
  return (
    <div className="space-y-5 animate-fadeIn">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <div className="sk h-[176px]" />
        <div className="sk h-[176px]" />
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="sk h-24" /><div className="sk h-24" /><div className="sk h-24" />
      </div>
      <div className="sk h-52" />
      <div className="sk h-64" />
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
        <div className="sk h-64" />
      </div>
    </div>
  );
}
