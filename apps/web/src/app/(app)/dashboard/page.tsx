"use client";

import { FileCheck2, Hourglass, ShieldAlert } from "lucide-react";
import { GreetingClock } from "@/components/dashboard/GreetingClock";
import { QuickCreateWidget } from "@/components/dashboard/QuickCreateWidget";
import { StatTile } from "@/components/dashboard/StatTile";
import { PendingApprovalsWidget } from "@/components/dashboard/PendingApprovalsWidget";
import { RecentDocumentsWidget } from "@/components/dashboard/RecentDocumentsWidget";
import { MiniCalendar } from "@/components/dashboard/MiniCalendar";
import { useMe, useDashboardSummary } from "@/lib/hooks";

export default function DashboardPage() {
  const { data: me } = useMe();
  const { data: summary, isLoading } = useDashboardSummary();

  if (isLoading && !summary) return <DashboardLoadingShell />;

  return (
    <div className="space-y-5 animate-fadeIn">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <GreetingClock name={me?.name} />
        <QuickCreateWidget />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatTile label="Документов сгенерировано" value={summary?.documents_generated_this_month ?? 0}
          hint="за этот месяц" icon={FileCheck2} tone="success" />
        <StatTile label="На подтверждении" value={summary?.approvals_pending_this_month ?? 0}
          hint="за этот месяц" icon={Hourglass} tone={(summary?.approvals_pending_this_month ?? 0) > 0 ? "warn" : "neutral"} />
        <StatTile label="Заблокировано QA" value={summary?.approvals_blocked_this_month ?? 0}
          hint="за этот месяц" icon={ShieldAlert} tone={(summary?.approvals_blocked_this_month ?? 0) > 0 ? "danger" : "neutral"} />
      </div>

      <PendingApprovalsWidget approvals={summary?.recent_pending_approvals ?? []} />
      <RecentDocumentsWidget documents={summary?.recent_documents ?? []} />

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
