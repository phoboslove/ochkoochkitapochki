"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, THead, TR, TH, TD } from "@/components/ui/table";
import {
  useAdminCompanyDetail, useAdminPlans, useAdminChangePlan, useAdminExtendSubscription,
  useAdminSuspendSubscription, useAdminReactivateSubscription, useAdminAddPayment,
  useAdminCreateUser, useAdminSetUserActive, useAdminResetPassword,
} from "@/lib/admin-hooks";
import type { SubscriptionStatus } from "@/lib/api";
import { toast } from "@/components/Toaster";
import { formatKZT } from "@/lib/utils";

const STATUS_TONE: Record<SubscriptionStatus, "success" | "info" | "warn" | "danger" | "neutral"> = {
  active: "success", trialing: "info", past_due: "warn", suspended: "danger", cancelled: "neutral",
};
const STATUS_LABEL: Record<SubscriptionStatus, string> = {
  active: "Активна", trialing: "Триал", past_due: "Просрочена", suspended: "Приостановлена", cancelled: "Отменена",
};

export default function CompanyDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data, isLoading, refetch } = useAdminCompanyDetail(id);
  const { data: plans } = useAdminPlans();

  const changePlan = useAdminChangePlan(id);
  const extend = useAdminExtendSubscription(id);
  const suspend = useAdminSuspendSubscription(id);
  const reactivate = useAdminReactivateSubscription(id);
  const addPayment = useAdminAddPayment(id);
  const createUser = useAdminCreateUser(id);
  const setUserActive = useAdminSetUserActive(id);
  const resetPassword = useAdminResetPassword(id);

  const [planCode, setPlanCode] = useState("");
  const [extendDays, setExtendDays] = useState(30);
  const [payAmount, setPayAmount] = useState("");
  const [payComment, setPayComment] = useState("");
  const [showNewUser, setShowNewUser] = useState(false);
  const [newUserEmail, setNewUserEmail] = useState("");
  const [newUserPassword, setNewUserPassword] = useState("");
  const [newUserRole, setNewUserRole] = useState("MEMBER");

  if (isLoading || !data) return <div className="text-sm text-muted-foreground">Загрузка…</div>;

  const sub = data.subscription;

  return (
    <>
      <PageHeader
        title={data.company.name}
        description={`БИН: ${data.company.bin ?? "—"} · создана ${new Date(data.company.created_at).toLocaleDateString("ru-RU")}`}
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Subscription */}
        <Card className="lg:col-span-2">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>Подписка</CardTitle>
            {sub && <Badge tone={STATUS_TONE[sub.status]}>{STATUS_LABEL[sub.status]}</Badge>}
          </CardHeader>
          <CardContent>
            {!sub ? (
              <div className="text-sm text-muted-foreground">Нет подписки.</div>
            ) : (
              <>
                <dl className="grid grid-cols-2 gap-y-2 text-[13px] mb-4">
                  <dt className="text-muted-foreground">Тариф</dt>
                  <dd>{sub.plan.name} — {formatKZT(sub.plan.price_amount)} {sub.plan.price_currency}/мес</dd>
                  <dt className="text-muted-foreground">Период до</dt>
                  <dd>{new Date(sub.period_end).toLocaleString("ru-RU")}</dd>
                  <dt className="text-muted-foreground">Документов использовано</dt>
                  <dd className="tabular-nums">{sub.usage.documents_used} / {sub.usage.documents_limit}</dd>
                  <dt className="text-muted-foreground">Способ продления</dt>
                  <dd>{sub.renewal_method}</dd>
                </dl>

                <div className="flex flex-wrap items-end gap-2 pt-3 border-t border-border">
                  <div>
                    <label className="text-[11px] text-muted-foreground block mb-1">Сменить тариф</label>
                    <div className="flex gap-1.5">
                      <select
                        value={planCode || sub.plan.code} onChange={(e) => setPlanCode(e.target.value)}
                        className="h-8 rounded-md border border-input bg-card px-2 text-[12.5px]"
                      >
                        {(plans ?? []).filter((p) => p.is_active).map((p) => (
                          <option key={p.code} value={p.code}>{p.name}</option>
                        ))}
                      </select>
                      <Button size="sm" variant="outline" disabled={changePlan.isPending}
                        onClick={() => changePlan.mutate(planCode || sub.plan.code, {
                          onSuccess: () => toast.success("Тариф изменён"),
                        })}>
                        Применить
                      </Button>
                    </div>
                  </div>
                  <div>
                    <label className="text-[11px] text-muted-foreground block mb-1">Продлить (дней)</label>
                    <div className="flex gap-1.5">
                      <Input type="number" value={extendDays} onChange={(e) => setExtendDays(Number(e.target.value))}
                        className="h-8 w-20" />
                      <Button size="sm" variant="outline" disabled={extend.isPending}
                        onClick={() => extend.mutate(extendDays, { onSuccess: () => toast.success("Период продлён") })}>
                        Продлить
                      </Button>
                    </div>
                  </div>
                  <div className="ml-auto flex gap-1.5">
                    {sub.status === "suspended" ? (
                      <Button size="sm" disabled={reactivate.isPending}
                        onClick={() => reactivate.mutate(undefined, { onSuccess: () => toast.success("Подписка возобновлена") })}>
                        Reactivate
                      </Button>
                    ) : (
                      <Button size="sm" variant="destructive" disabled={suspend.isPending}
                        onClick={() => suspend.mutate(undefined, { onSuccess: () => toast.success("Подписка приостановлена") })}>
                        Suspend
                      </Button>
                    )}
                  </div>
                </div>
              </>
            )}
          </CardContent>
        </Card>

        {/* Add payment */}
        <Card>
          <CardHeader><CardTitle>Добавить платёж</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            <Input placeholder="Сумма (KZT)" value={payAmount} onChange={(e) => setPayAmount(e.target.value)} />
            <Input placeholder="Комментарий" value={payComment} onChange={(e) => setPayComment(e.target.value)} />
            <Button size="sm" className="w-full" disabled={!payAmount || addPayment.isPending}
              onClick={() => addPayment.mutate({ amount: payAmount, comment: payComment || undefined }, {
                onSuccess: () => { toast.success("Платёж записан"); setPayAmount(""); setPayComment(""); },
              })}>
              Записать платёж
            </Button>
          </CardContent>
        </Card>
      </div>

      {/* Users */}
      <Card className="mt-6">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Пользователи</CardTitle>
          <Button size="sm" variant="outline" onClick={() => setShowNewUser((v) => !v)}>
            {showNewUser ? "Отмена" : "+ Пользователь"}
          </Button>
        </CardHeader>
        <CardContent>
          {showNewUser && (
            <div className="flex flex-wrap items-end gap-2 mb-4 p-3 rounded-md bg-muted">
              <Input placeholder="email" value={newUserEmail} onChange={(e) => setNewUserEmail(e.target.value)} className="w-48" />
              <Input placeholder="временный пароль" value={newUserPassword} onChange={(e) => setNewUserPassword(e.target.value)} className="w-40" />
              <select value={newUserRole} onChange={(e) => setNewUserRole(e.target.value)}
                className="h-8 rounded-md border border-input bg-card px-2 text-[12.5px]">
                {["OWNER", "ADMIN", "MEMBER", "ACCOUNTANT", "VIEWER"].map((r) => <option key={r} value={r}>{r}</option>)}
              </select>
              <Button size="sm" disabled={!newUserEmail || !newUserPassword || createUser.isPending}
                onClick={() => createUser.mutate({ email: newUserEmail, password: newUserPassword, role: newUserRole }, {
                  onSuccess: () => { toast.success("Пользователь создан"); setNewUserEmail(""); setNewUserPassword(""); setShowNewUser(false); },
                  onError: (e) => toast.error("Ошибка", (e as Error).message),
                })}>
                Создать
              </Button>
            </div>
          )}
          <Table>
            <THead><TR><TH>Email</TH><TH>Имя</TH><TH>Роль</TH><TH>Статус</TH><TH /></TR></THead>
            <tbody>
              {data.users.map((u) => (
                <TR key={u.id}>
                  <TD>{u.email}</TD>
                  <TD className="text-muted-foreground">{u.name ?? "—"}</TD>
                  <TD>{u.role}</TD>
                  <TD>{u.active ? <Badge tone="success">Активен</Badge> : <Badge tone="neutral">Деактивирован</Badge>}</TD>
                  <TD>
                    <div className="flex gap-1.5 justify-end">
                      <Button size="sm" variant="ghost"
                        onClick={() => setUserActive.mutate({ userId: u.id, active: !u.active })}>
                        {u.active ? "Деактивировать" : "Активировать"}
                      </Button>
                      <Button size="sm" variant="ghost"
                        onClick={() => resetPassword.mutate(u.id, {
                          onSuccess: (r) => toast.info("Новый пароль", r.temporary_password),
                        })}>
                        Сбросить пароль
                      </Button>
                    </div>
                  </TD>
                </TR>
              ))}
            </tbody>
          </Table>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
        {/* Payment history */}
        <Card>
          <CardHeader><CardTitle>История платежей</CardTitle></CardHeader>
          <CardContent>
            {data.payments.length === 0 ? (
              <div className="text-sm text-muted-foreground">Платежей ещё не было.</div>
            ) : (
              <ul className="space-y-2 text-[13px]">
                {data.payments.map((p) => (
                  <li key={p.id} className="flex justify-between">
                    <span className="text-muted-foreground">
                      {new Date(p.created_at).toLocaleDateString("ru-RU")} {p.comment && `· ${p.comment}`}
                    </span>
                    <span className="tabular-nums font-medium">{formatKZT(p.amount)} {p.currency}</span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        {/* Usage by month */}
        <Card>
          <CardHeader><CardTitle>Использование по месяцам</CardTitle></CardHeader>
          <CardContent>
            {data.usage_by_month.length === 0 ? (
              <div className="text-sm text-muted-foreground">Нет данных.</div>
            ) : (
              <ul className="space-y-2 text-[13px]">
                {data.usage_by_month.map((u) => (
                  <li key={u.period} className="flex justify-between">
                    <span className="text-muted-foreground">{u.period}</span>
                    <span className="tabular-nums">{u.documents_count} документов</span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Audit trail */}
      <Card className="mt-6">
        <CardHeader><CardTitle>Журнал действий</CardTitle></CardHeader>
        <CardContent className="p-0">
          <Table>
            <THead><TR><TH>Когда</TH><TH>Кто</TH><TH>Действие</TH></TR></THead>
            <tbody>
              {data.audit_trail.map((a) => (
                <TR key={a.id}>
                  <TD className="text-muted-foreground whitespace-nowrap">{new Date(a.at).toLocaleString("ru-RU")}</TD>
                  <TD className="text-muted-foreground">{a.actor_type}</TD>
                  <TD className="font-mono text-[12px]">{a.action}</TD>
                </TR>
              ))}
              {data.audit_trail.length === 0 && (
                <TR><TD colSpan={3} className="text-center text-muted-foreground py-6">Пока пусто.</TD></TR>
              )}
            </tbody>
          </Table>
        </CardContent>
      </Card>
    </>
  );
}
