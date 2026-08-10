"use client";

import { useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, THead, TR, TH, TD } from "@/components/ui/table";
import {
  useAdminPlans, useAdminCreatePlan, useAdminUpdatePlan, useAdminDisablePlan,
} from "@/lib/admin-hooks";
import type { AdminPlan } from "@/lib/api";
import { toast } from "@/components/Toaster";
import { Plus } from "lucide-react";

const EMPTY_FORM = {
  code: "", name: "", price_amount: 0, limit_documents_per_month: 0,
  limit_users: 0, limit_templates: 0,
};

export default function AdminPlansPage() {
  const { data: plans, isLoading } = useAdminPlans();
  const create = useAdminCreatePlan();
  const update = useAdminUpdatePlan();
  const disable = useAdminDisablePlan();

  const [showNew, setShowNew] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<Partial<AdminPlan>>({});

  const startEdit = (p: AdminPlan) => {
    setEditingId(p.id);
    setEditForm({
      price_amount: p.price_amount, limit_documents_per_month: p.limit_documents_per_month,
      limit_users: p.limit_users, limit_templates: p.limit_templates,
    });
  };

  return (
    <>
      <PageHeader
        title="Тарифы"
        description="Планы и лимиты — меняются здесь, без деплоя."
        actions={
          <Button size="sm" onClick={() => setShowNew((v) => !v)}>
            <Plus className="h-3.5 w-3.5" /> {showNew ? "Отмена" : "Новый тариф"}
          </Button>
        }
      />

      {showNew && (
        <Card className="mb-4">
          <CardContent className="p-4 flex flex-wrap items-end gap-2">
            <div><label className="text-[11px] text-muted-foreground block mb-1">Код</label>
              <Input className="w-28" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} /></div>
            <div><label className="text-[11px] text-muted-foreground block mb-1">Название</label>
              <Input className="w-40" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
            <div><label className="text-[11px] text-muted-foreground block mb-1">Цена (KZT/мес)</label>
              <Input type="number" className="w-28" value={form.price_amount}
                onChange={(e) => setForm({ ...form, price_amount: Number(e.target.value) })} /></div>
            <div><label className="text-[11px] text-muted-foreground block mb-1">Документов/мес</label>
              <Input type="number" className="w-24" value={form.limit_documents_per_month}
                onChange={(e) => setForm({ ...form, limit_documents_per_month: Number(e.target.value) })} /></div>
            <div><label className="text-[11px] text-muted-foreground block mb-1">Пользователей</label>
              <Input type="number" className="w-20" value={form.limit_users}
                onChange={(e) => setForm({ ...form, limit_users: Number(e.target.value) })} /></div>
            <div><label className="text-[11px] text-muted-foreground block mb-1">Шаблонов</label>
              <Input type="number" className="w-20" value={form.limit_templates}
                onChange={(e) => setForm({ ...form, limit_templates: Number(e.target.value) })} /></div>
            <Button size="sm" disabled={!form.code || !form.name || create.isPending}
              onClick={() => create.mutate(form, {
                onSuccess: () => { toast.success("Тариф создан"); setForm(EMPTY_FORM); setShowNew(false); },
                onError: (e) => toast.error("Ошибка", (e as Error).message),
              })}>
              Создать
            </Button>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardContent className="p-0">
          <Table>
            <THead><TR>
              <TH>Код</TH><TH>Название</TH><TH>Цена</TH><TH>Документов/мес</TH>
              <TH>Пользователей</TH><TH>Шаблонов</TH><TH>Статус</TH><TH />
            </TR></THead>
            <tbody>
              {isLoading && <TR><TD colSpan={8} className="text-center text-muted-foreground py-6">Загрузка…</TD></TR>}
              {plans?.map((p) => {
                const editing = editingId === p.id;
                return (
                  <TR key={p.id}>
                    <TD className="font-mono text-[12px]">{p.code}</TD>
                    <TD>{p.name}</TD>
                    <TD className="tabular-nums">
                      {editing ? (
                        <Input type="number" className="w-24 h-7" value={editForm.price_amount}
                          onChange={(e) => setEditForm({ ...editForm, price_amount: Number(e.target.value) })} />
                      ) : `${p.price_amount} ${p.price_currency}`}
                    </TD>
                    <TD className="tabular-nums">
                      {editing ? (
                        <Input type="number" className="w-20 h-7" value={editForm.limit_documents_per_month}
                          onChange={(e) => setEditForm({ ...editForm, limit_documents_per_month: Number(e.target.value) })} />
                      ) : p.limit_documents_per_month}
                    </TD>
                    <TD className="tabular-nums">
                      {editing ? (
                        <Input type="number" className="w-16 h-7" value={editForm.limit_users}
                          onChange={(e) => setEditForm({ ...editForm, limit_users: Number(e.target.value) })} />
                      ) : p.limit_users}
                    </TD>
                    <TD className="tabular-nums">
                      {editing ? (
                        <Input type="number" className="w-16 h-7" value={editForm.limit_templates}
                          onChange={(e) => setEditForm({ ...editForm, limit_templates: Number(e.target.value) })} />
                      ) : p.limit_templates}
                    </TD>
                    <TD>{p.is_active ? <Badge tone="success">Активен</Badge> : <Badge tone="neutral">Отключён</Badge>}</TD>
                    <TD>
                      <div className="flex gap-1.5 justify-end">
                        {editing ? (
                          <>
                            <Button size="sm" variant="ghost" onClick={() => setEditingId(null)}>Отмена</Button>
                            <Button size="sm" disabled={update.isPending}
                              onClick={() => update.mutate({ id: p.id, ...editForm }, {
                                onSuccess: () => { toast.success("Сохранено"); setEditingId(null); },
                              })}>
                              Сохранить
                            </Button>
                          </>
                        ) : (
                          <>
                            <Button size="sm" variant="ghost" onClick={() => startEdit(p)}>Изменить</Button>
                            {p.is_active && (
                              <Button size="sm" variant="ghost"
                                onClick={() => disable.mutate(p.id, { onSuccess: () => toast.success("Тариф отключён") })}>
                                Отключить
                              </Button>
                            )}
                          </>
                        )}
                      </div>
                    </TD>
                  </TR>
                );
              })}
            </tbody>
          </Table>
        </CardContent>
      </Card>
    </>
  );
}
