"use client";

import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/layout/PageHeader";
import { useAdminDashboard } from "@/lib/admin-hooks";
import { formatKZT } from "@/lib/utils";

function Stat({ label, value, tone }: { label: string; value: string | number; tone?: string }) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="text-[11px] uppercase tracking-wider text-muted-foreground">{label}</div>
        <div className={"text-2xl font-semibold mt-1 tabular-nums " + (tone ?? "")}>{value}</div>
      </CardContent>
    </Card>
  );
}

export default function AdminDashboardPage() {
  const { data, isLoading } = useAdminDashboard();

  if (isLoading || !data) {
    return <div className="text-sm text-muted-foreground">Загрузка…</div>;
  }

  return (
    <>
      <PageHeader title="Дашборд" description="Метрики платформы по всем компаниям." />

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-6">
        <Stat label="Компаний всего" value={data.companies.total} />
        <Stat label="Активных" value={data.companies.active} tone="text-[hsl(var(--success))]" />
        <Stat label="На триале" value={data.companies.trialing} tone="text-[hsl(var(--info))]" />
        <Stat label="Просрочено" value={data.companies.past_due} tone="text-[hsl(var(--warning))]" />
        <Stat label="Приостановлено" value={data.companies.suspended} tone="text-[hsl(var(--danger))]" />
        <Stat label="Документов / месяц" value={data.documents_this_month} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader><CardTitle>MRR</CardTitle></CardHeader>
          <CardContent>
            <div className="text-3xl font-semibold tabular-nums">
              {formatKZT(data.mrr)} <span className="text-sm text-muted-foreground">{data.mrr_currency}</span>
            </div>
            <p className="text-xs text-muted-foreground mt-2">
              Сумма тарифов активных (оплаченных) подписок.
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>Топ компаний по генерации (этот месяц)</CardTitle></CardHeader>
          <CardContent>
            {data.top_companies.length === 0 ? (
              <div className="text-sm text-muted-foreground">Пока нет данных.</div>
            ) : (
              <ul className="space-y-2">
                {data.top_companies.map((c) => (
                  <li key={c.company_id} className="flex items-center justify-between text-sm">
                    <Link href={`/admin/companies/${c.company_id}`} className="hover:underline">
                      {c.company_name}
                    </Link>
                    <span className="tabular-nums text-muted-foreground">{c.documents_this_month}</span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </>
  );
}
