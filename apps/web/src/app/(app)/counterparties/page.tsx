"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Table, THead, TR, TH, TD } from "@/components/ui/table";
import { Field, Text, Toggle } from "@/components/settings/SettingsField";
import { api } from "@/lib/api";
import { toast } from "@/components/Toaster";
import { Plus, Pencil, Trash2 } from "lucide-react";

type Counterparty = {
  id: string; name: string; bin: string | null; phone: string | null; email: string | null;
  address: string | null; signatory_name: string | null; signatory_basis: string | null;
  bank_name: string | null; bank_bik: string | null; bank_iik: string | null; bank_kbe: string | null;
  vat_registered: boolean; vat_certificate_number: string | null; contact_person: string | null;
  created_at: string;
};

const EMPTY: Partial<Counterparty> = { name: "", vat_registered: false };

export default function CounterpartiesPage() {
  const qc = useQueryClient();
  const { data = [], isLoading } = useQuery({
    queryKey: ["clients"],
    queryFn: () => api.get<Counterparty[]>("/clients"),
  });
  const [editing, setEditing] = useState<Partial<Counterparty> | null>(null);

  const save = useMutation({
    mutationFn: (draft: Partial<Counterparty>) =>
      draft.id ? api.patch<Counterparty>(`/clients/${draft.id}`, draft)
               : api.post<Counterparty>("/clients", draft),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["clients"] });
      toast.success("Контрагент сохранён");
      setEditing(null);
    },
    onError: (e) => toast.error("Не удалось сохранить", (e as Error).message),
  });

  const del = useMutation({
    mutationFn: (id: string) => api.delete(`/clients/${id}`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["clients"] }); toast.success("Контрагент удалён"); },
    onError: (e) => toast.error("Не удалось удалить", (e as Error).message),
  });

  return (
    <>
      <PageHeader title="Контрагенты" description="Справочник контрагентов — автоподстановка в документы по совпадению названия."
        actions={
          <Button size="sm" onClick={() => setEditing({ ...EMPTY })}>
            <Plus className="h-3.5 w-3.5" /> Добавить
          </Button>
        } />

      <Card>
        <CardContent className="p-0 overflow-x-auto">
          <Table>
            <THead><TR>
              <TH>Название</TH><TH>БИН/ИИН</TH><TH>Телефон</TH><TH>Адрес</TH><TH>НДС</TH><TH></TH>
            </TR></THead>
            <tbody>
              {isLoading && <TR><TD colSpan={6} className="text-center text-muted-foreground py-6">Загрузка…</TD></TR>}
              {!isLoading && data.length === 0 && (
                <TR><TD colSpan={6} className="text-center text-muted-foreground py-6">Пока нет контрагентов.</TD></TR>
              )}
              {data.map((c) => (
                <TR key={c.id}>
                  <TD className="font-medium">{c.name}</TD>
                  <TD className="font-mono text-xs text-muted-foreground">{c.bin ?? "—"}</TD>
                  <TD>{c.phone ?? "—"}</TD>
                  <TD className="text-muted-foreground truncate max-w-[220px]">{c.address ?? "—"}</TD>
                  <TD>{c.vat_registered ? <Badge tone="success">Да</Badge> : <Badge tone="neutral">Нет</Badge>}</TD>
                  <TD className="text-right whitespace-nowrap">
                    <Button variant="ghost" size="sm" onClick={() => setEditing(c)}>
                      <Pencil className="h-3.5 w-3.5" />
                    </Button>
                    <Button variant="ghost" size="sm"
                      onClick={() => { if (confirm(`Удалить «${c.name}»?`)) del.mutate(c.id); }}>
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
        <CounterpartyModal
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

function CounterpartyModal({ draft, saving, onChange, onSave, onClose }: {
  draft: Partial<Counterparty>;
  saving: boolean;
  onChange: (d: Partial<Counterparty>) => void;
  onSave: () => void;
  onClose: () => void;
}) {
  const set = (k: keyof Counterparty, v: any) => onChange({ ...draft, [k]: v });

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-[hsl(var(--shadow-color)/0.5)] p-4" onClick={onClose}>
      <Card className="w-[640px] max-w-full max-h-[85vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <CardContent className="p-5 space-y-4">
          <div className="text-sm font-medium">{draft.id ? "Редактировать контрагента" : "Новый контрагент"}</div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Field label="Название" span={2}>
              <Text value={draft.name} onChange={(v) => set("name", v)} placeholder="ТОО Ромашка" />
            </Field>
            <Field label="БИН/ИИН"><Text value={draft.bin ?? ""} onChange={(v) => set("bin", v)} /></Field>
            <Field label="Телефон"><Text value={draft.phone ?? ""} onChange={(v) => set("phone", v)} /></Field>
            <Field label="Email"><Text value={draft.email ?? ""} onChange={(v) => set("email", v)} type="email" /></Field>
            <Field label="Контактное лицо"><Text value={draft.contact_person ?? ""} onChange={(v) => set("contact_person", v)} /></Field>
            <Field label="Адрес" span={2}><Text value={draft.address ?? ""} onChange={(v) => set("address", v)} /></Field>
            <Field label="ФИО подписанта"><Text value={draft.signatory_name ?? ""} onChange={(v) => set("signatory_name", v)} /></Field>
            <Field label="Основание полномочий"><Text value={draft.signatory_basis ?? ""} onChange={(v) => set("signatory_basis", v)}
              placeholder="Устав / доверенность №..." /></Field>
          </div>

          <h3 className="text-xs uppercase tracking-wider text-muted-foreground">Банк</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Field label="Банк"><Text value={draft.bank_name ?? ""} onChange={(v) => set("bank_name", v)} /></Field>
            <Field label="БИК"><Text value={draft.bank_bik ?? ""} onChange={(v) => set("bank_bik", v)} /></Field>
            <Field label="ИИК"><Text value={draft.bank_iik ?? ""} onChange={(v) => set("bank_iik", v)} /></Field>
            <Field label="Кбе"><Text value={draft.bank_kbe ?? ""} onChange={(v) => set("bank_kbe", v)} /></Field>
          </div>

          <Field label="НДС">
            <div className="flex items-center gap-4">
              <Toggle label="Плательщик НДС" checked={!!draft.vat_registered} onChange={(v) => set("vat_registered", v)} />
              <div className="flex-1">
                <Text value={draft.vat_certificate_number ?? ""} onChange={(v) => set("vat_certificate_number", v)}
                      placeholder="№ свидетельства" disabled={!draft.vat_registered} />
              </div>
            </div>
          </Field>

          <div className="flex justify-end gap-2 pt-2 border-t border-border">
            <Button variant="ghost" onClick={onClose}>Отмена</Button>
            <Button onClick={onSave} disabled={!draft.name?.trim() || saving}>
              {saving ? "Сохраняю…" : "Сохранить"}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
