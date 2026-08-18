"use client";

import { useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAdminDocumentLookup, useAdminRecheckQuality } from "@/lib/admin-hooks";
import { toast } from "@/components/Toaster";
import type { AdminDocument } from "@/lib/api";

const STATUS_TONE: Record<string, "success" | "info" | "warn" | "danger" | "neutral"> = {
  PENDING: "info", BLOCKED: "danger", APPROVED: "success", REJECTED: "neutral",
};

export default function AdminDocumentsPage() {
  const [documentId, setDocumentId] = useState("");
  const [doc, setDoc] = useState<AdminDocument | null>(null);
  const lookup = useAdminDocumentLookup();
  const recheck = useAdminRecheckQuality();

  const runLookup = () => {
    if (!documentId.trim()) return;
    lookup.mutate(documentId.trim(), {
      onSuccess: (d) => setDoc(d),
      onError: (e) => { setDoc(null); toast.error("Документ не найден", (e as Error).message); },
    });
  };

  const runRecheck = () => {
    if (!doc) return;
    recheck.mutate(doc.id, {
      onSuccess: (d) => {
        setDoc(d);
        toast.success(
          "Проверка выполнена",
          d.approval?.status === "BLOCKED" ? "Документ по-прежнему заблокирован" : "Документ разблокирован",
        );
      },
      onError: (e) => toast.error("Ошибка проверки", (e as Error).message),
    });
  };

  return (
    <>
      <PageHeader
        title="Документы"
        description="Найдите документ по ID и пересчитайте quality gate по актуальным правилам — без правки БД руками."
      />

      <Card>
        <CardHeader><CardTitle>Найти документ</CardTitle></CardHeader>
        <CardContent>
          <div className="flex items-end gap-2">
            <div className="flex-1">
              <label className="text-[11px] text-muted-foreground mb-1 block">
                Document ID (например, gen_a3bbe6a770)
              </label>
              <Input
                value={documentId} onChange={(e) => setDocumentId(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && runLookup()}
                placeholder="gen_..."
              />
            </div>
            <Button onClick={runLookup} disabled={lookup.isPending || !documentId.trim()}>
              {lookup.isPending ? "Ищу…" : "Найти"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {doc && (
        <Card className="mt-6">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>{doc.title}</CardTitle>
            {doc.approval && (
              <Badge tone={STATUS_TONE[doc.approval.status] ?? "neutral"}>{doc.approval.status}</Badge>
            )}
          </CardHeader>
          <CardContent className="space-y-4">
            <dl className="grid grid-cols-2 gap-y-2 text-[13px]">
              <dt className="text-muted-foreground">Компания</dt>
              <dd className="font-mono text-[12px]">{doc.company_id}</dd>
              <dt className="text-muted-foreground">Kind</dt>
              <dd>{doc.kind ?? "—"}</dd>
              <dt className="text-muted-foreground">Номер</dt>
              <dd>{doc.document_number ?? "—"}</dd>
              <dt className="text-muted-foreground">Создан</dt>
              <dd>{new Date(doc.created_at).toLocaleString("ru-RU")}</dd>
              {doc.quality && (
                <>
                  <dt className="text-muted-foreground">Quality</dt>
                  <dd className="tabular-nums">{doc.quality.score}/100 · {doc.quality.status}</dd>
                </>
              )}
            </dl>

            {doc.quality && doc.quality.issues.length > 0 && (
              <div className="rounded-md ring-1 ring-[hsl(var(--danger)/0.25)] bg-danger-bg px-3 py-2 text-[12.5px]">
                <div className="font-medium text-[hsl(var(--danger))] mb-1">
                  {doc.quality.issues.length} issue{doc.quality.issues.length === 1 ? "" : "s"}
                </div>
                <ul className="space-y-0.5 text-muted-foreground">
                  {doc.quality.issues.map((i, idx) => (
                    <li key={idx}>• [{i.severity}] {i.message}</li>
                  ))}
                </ul>
              </div>
            )}

            {!doc.recheck_available && (
              <div className="rounded-md ring-1 ring-[hsl(var(--warning)/0.3)] bg-warning-bg px-3 py-2 text-[12.5px] text-muted-foreground">
                Этот документ создан до появления сохранённого canonical-контекста — пересчёт недоступен для него.
              </div>
            )}

            <div className="pt-2 border-t border-border">
              <Button
                variant="outline" disabled={!doc.recheck_available || !doc.approval || recheck.isPending}
                onClick={runRecheck}
              >
                {recheck.isPending ? "Пересчитываю…" : "Recheck quality"}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </>
  );
}
