"use client";

import { useState } from "react";
import Link from "next/link";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, THead, TR, TH, TD, SkeletonRow } from "@/components/ui/table";
import { useAdminCompanies } from "@/lib/admin-hooks";
import type { SubscriptionStatus } from "@/lib/api";
import { Plus } from "lucide-react";

const STATUS_TONE: Record<SubscriptionStatus, "success" | "info" | "warn" | "danger" | "neutral"> = {
  active: "success", trialing: "info", past_due: "warn", suspended: "danger", cancelled: "neutral",
};
const STATUS_LABEL: Record<SubscriptionStatus, string> = {
  active: "Активна", trialing: "Триал", past_due: "Просрочена", suspended: "Приостановлена", cancelled: "Отменена",
};

const STATUS_FILTERS: { value: string; label: string }[] = [
  { value: "", label: "Все" },
  { value: "trialing", label: "Триал" },
  { value: "active", label: "Активные" },
  { value: "past_due", label: "Просроченные" },
  { value: "suspended", label: "Приостановленные" },
];

export default function AdminCompaniesPage() {
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const { data, isLoading } = useAdminCompanies({ status: status || undefined, q: q || undefined });

  return (
    <>
      <PageHeader
        title="Компании"
        description={`Всего: ${data?.total ?? "…"}`}
        actions={
          <Link href="/admin/companies/new">
            <Button size="sm"><Plus className="h-3.5 w-3.5" /> Создать компанию</Button>
          </Link>
        }
      />

      <div className="flex flex-wrap gap-2 mb-4">
        {STATUS_FILTERS.map((f) => (
          <button
            key={f.value}
            onClick={() => setStatus(f.value)}
            className={`rounded-full border px-3 py-1 text-xs transition-colors ${
              status === f.value ? "bg-primary text-primary-foreground border-primary" : "hover:bg-accent"
            }`}
          >
            {f.label}
          </button>
        ))}
        <Input
          value={q} onChange={(e) => setQ(e.target.value)}
          placeholder="Поиск по названию или БИН…"
          className="ml-auto w-full sm:w-64 h-7 text-xs"
        />
      </div>

      <Card>
        <CardContent className="p-0">
          <Table>
            <THead><TR>
              <TH>Компания</TH><TH>БИН</TH><TH>Тариф</TH><TH>Статус</TH>
              <TH>Пользователей</TH><TH>Окончание периода</TH>
            </TR></THead>
            <tbody>
              {isLoading && Array.from({ length: 5 }).map((_, i) => <SkeletonRow key={i} cols={6} />)}
              {!isLoading && (data?.items.length ?? 0) === 0 && (
                <TR><TD colSpan={6} className="text-center text-muted-foreground py-8">Ничего не найдено.</TD></TR>
              )}
              {data?.items.map((c) => (
                <TR key={c.id} className="cursor-pointer">
                  <TD>
                    <Link href={`/admin/companies/${c.id}`} className="font-medium hover:underline">
                      {c.name}
                    </Link>
                  </TD>
                  <TD className="text-muted-foreground">{c.bin ?? "—"}</TD>
                  <TD>{c.subscription?.plan_name ?? "—"}</TD>
                  <TD>
                    {c.subscription ? (
                      <Badge tone={STATUS_TONE[c.subscription.status]}>{STATUS_LABEL[c.subscription.status]}</Badge>
                    ) : "—"}
                  </TD>
                  <TD className="tabular-nums">{c.users_count}</TD>
                  <TD className="text-muted-foreground">
                    {c.subscription ? new Date(c.subscription.period_end).toLocaleDateString("ru-RU") : "—"}
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
