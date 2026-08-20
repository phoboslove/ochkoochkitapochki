"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Table, THead, TR, TH, TD } from "@/components/ui/table";
import { Field, Text } from "@/components/settings/SettingsField";
import { api } from "@/lib/api";
import { toast } from "@/components/Toaster";
import { Plus, Pencil, Trash2 } from "lucide-react";

type Employee = {
  id: string; full_name: string; iin: string | null; position: string | null; department: string | null;
  hire_date: string | null; salary: number | null; allowances: number | null;
  probation_period: string | null; work_schedule: string | null; vacation_days: number;
  address: string | null; id_doc_number: string | null; id_doc_issued_by: string | null; id_doc_date: string | null;
  created_at: string;
};

const EMPTY: Partial<Employee> = { full_name: "", vacation_days: 24 };

export default function EmployeesPage() {
  const qc = useQueryClient();
  const { data = [], isLoading } = useQuery({
    queryKey: ["employees"],
    queryFn: () => api.get<Employee[]>("/employees"),
  });
  const [editing, setEditing] = useState<Partial<Employee> | null>(null);

  const save = useMutation({
    mutationFn: (draft: Partial<Employee>) =>
      draft.id ? api.patch<Employee>(`/employees/${draft.id}`, draft)
               : api.post<Employee>("/employees", draft),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["employees"] });
      toast.success("Сотрудник сохранён");
      setEditing(null);
    },
    onError: (e) => toast.error("Не удалось сохранить", (e as Error).message),
  });

  const del = useMutation({
    mutationFn: (id: string) => api.delete(`/employees/${id}`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["employees"] }); toast.success("Сотрудник удалён"); },
    onError: (e) => toast.error("Не удалось удалить", (e as Error).message),
  });

  return (
    <>
      <PageHeader title="Сотрудники" description="Справочник сотрудников — автоподстановка в кадровые документы по совпадению ФИО."
        actions={
          <Button size="sm" onClick={() => setEditing({ ...EMPTY })}>
            <Plus className="h-3.5 w-3.5" /> Добавить
          </Button>
        } />

      <Card>
        <CardContent className="p-0 overflow-x-auto">
          <Table>
            <THead><TR>
              <TH>ФИО</TH><TH>Должность</TH><TH>Подразделение</TH><TH>Оклад</TH><TH></TH>
            </TR></THead>
            <tbody>
              {isLoading && <TR><TD colSpan={5} className="text-center text-muted-foreground py-6">Загрузка…</TD></TR>}
              {!isLoading && data.length === 0 && (
                <TR><TD colSpan={5} className="text-center text-muted-foreground py-6">Пока нет сотрудников.</TD></TR>
              )}
              {data.map((e) => (
                <TR key={e.id}>
                  <TD className="font-medium">{e.full_name}</TD>
                  <TD className="text-muted-foreground">{e.position ?? "—"}</TD>
                  <TD className="text-muted-foreground">{e.department ?? "—"}</TD>
                  <TD className="tabular-nums">{e.salary != null ? `${e.salary.toLocaleString("ru-RU")} ₸` : "—"}</TD>
                  <TD className="text-right whitespace-nowrap">
                    <Button variant="ghost" size="sm" onClick={() => setEditing(e)}>
                      <Pencil className="h-3.5 w-3.5" />
                    </Button>
                    <Button variant="ghost" size="sm"
                      onClick={() => { if (confirm(`Удалить «${e.full_name}»?`)) del.mutate(e.id); }}>
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </TD>
                </TR>
              ))}
            </tbody>
          </Table>
        </CardContent>
      </Card>

      {editing && (
        <EmployeeModal
          draft={editing}
          saving={save.isPending}
          onChange={setEditing}
          onSave={() => save.mutate(editing)}
          onClose={() => setEditing(null)}
        />
      )}
    </>
  );
}

function EmployeeModal({ draft, saving, onChange, onSave, onClose }: {
  draft: Partial<Employee>;
  saving: boolean;
  onChange: (d: Partial<Employee>) => void;
  onSave: () => void;
  onClose: () => void;
}) {
  const set = (k: keyof Employee, v: any) => onChange({ ...draft, [k]: v });

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-[hsl(var(--shadow-color)/0.5)] p-4" onClick={onClose}>
      <Card className="w-[640px] max-w-full max-h-[85vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <CardContent className="p-5 space-y-4">
          <div className="text-sm font-medium">{draft.id ? "Редактировать сотрудника" : "Новый сотрудник"}</div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Field label="ФИО" span={2}>
              <Text value={draft.full_name} onChange={(v) => set("full_name", v)} placeholder="Асанов Аслан Асланович" />
            </Field>
            <Field label="ИИН"><Text value={draft.iin ?? ""} onChange={(v) => set("iin", v)} /></Field>
            <Field label="Должность"><Text value={draft.position ?? ""} onChange={(v) => set("position", v)} /></Field>
            <Field label="Подразделение"><Text value={draft.department ?? ""} onChange={(v) => set("department", v)} /></Field>
            <Field label="Дата приёма"><Text value={draft.hire_date ?? ""} onChange={(v) => set("hire_date", v)} type="date" /></Field>
            <Field label="Оклад"><Text value={draft.salary ?? ""} onChange={(v) => set("salary", Number(v) || null)} type="number" /></Field>
            <Field label="Надбавки"><Text value={draft.allowances ?? ""} onChange={(v) => set("allowances", Number(v) || null)} type="number" /></Field>
            <Field label="Испытательный срок"><Text value={draft.probation_period ?? ""} onChange={(v) => set("probation_period", v)}
              placeholder="3 месяца" /></Field>
            <Field label="График работы"><Text value={draft.work_schedule ?? ""} onChange={(v) => set("work_schedule", v)} /></Field>
            <Field label="Дни отпуска"><Text value={draft.vacation_days ?? 24} onChange={(v) => set("vacation_days", Number(v) || 24)} type="number" /></Field>
            <Field label="Адрес" span={2}><Text value={draft.address ?? ""} onChange={(v) => set("address", v)} /></Field>
          </div>

          <h3 className="text-xs uppercase tracking-wider text-muted-foreground">Удостоверение личности</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Field label="Номер"><Text value={draft.id_doc_number ?? ""} onChange={(v) => set("id_doc_number", v)} /></Field>
            <Field label="Дата выдачи"><Text value={draft.id_doc_date ?? ""} onChange={(v) => set("id_doc_date", v)} /></Field>
            <Field label="Кем выдано" span={2}><Text value={draft.id_doc_issued_by ?? ""} onChange={(v) => set("id_doc_issued_by", v)} /></Field>
          </div>

          <div className="flex justify-end gap-2 pt-2 border-t border-border">
            <Button variant="ghost" onClick={onClose}>Отмена</Button>
            <Button onClick={onSave} disabled={!draft.full_name?.trim() || saving}>
              {saving ? "Сохраняю…" : "Сохранить"}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
