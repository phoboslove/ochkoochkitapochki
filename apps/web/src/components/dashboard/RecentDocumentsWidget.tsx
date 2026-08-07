"use client";

import Link from "next/link";
import { Download, FileText } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useDocuments } from "@/lib/hooks";
import type { DocumentItem } from "@/lib/api";

const KIND_LABEL: Record<string, string> = {
  INVOICE: "Счёт", ACT: "Акт", NAKLADNAYA: "Накладная",
  CONTRACT: "Договор", TRUST_LETTER: "Доверенность", OTHER: "Документ",
};

const STATUS_TONE: Record<DocumentItem["status"], "neutral" | "warn" | "danger" | "success" | "info"> = {
  UPLOADED: "neutral", OCR_PENDING: "info", OCR_DONE: "info",
  PARSED: "info", FAILED: "danger", GENERATED: "success",
};

const STATUS_LABEL: Record<DocumentItem["status"], string> = {
  UPLOADED: "Загружен", OCR_PENDING: "OCR…", OCR_DONE: "OCR готов",
  PARSED: "Разобран", FAILED: "Ошибка", GENERATED: "Готов",
};

export function RecentDocumentsWidget() {
  const { data: documents } = useDocuments();

  const recent = (documents ?? [])
    .slice()
    .sort((a, b) => +new Date(b.created_at) - +new Date(a.created_at))
    .slice(0, 5);

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Последние документы</CardTitle>
        <Link href="/documents" className="text-[11px] text-muted-foreground hover:text-foreground transition-colors">
          Все →
        </Link>
      </CardHeader>
      <CardContent className="pt-0">
        {recent.length === 0 ? (
          <div className="text-[13px] text-muted-foreground py-2 flex items-center gap-2">
            <FileText className="h-3.5 w-3.5" />
            Документов пока нет.
          </div>
        ) : (
          <ul className="divide-y divide-border -mx-5">
            {recent.map((d) => (
              <li key={d.id} className="flex items-center gap-3 px-5 py-3 hover:bg-accent/30 transition-colors">
                <Badge tone="neutral" className="shrink-0">{KIND_LABEL[d.type] ?? d.type}</Badge>
                <Link href={`/documents/${d.id}`} className="flex-1 min-w-0">
                  <div className="text-[13px] font-medium truncate hover:underline">{d.title}</div>
                  <div className="text-[11px] text-muted-foreground">
                    {new Date(d.created_at).toLocaleDateString("ru-RU")}
                  </div>
                </Link>
                <Badge tone={STATUS_TONE[d.status]} className="shrink-0">{STATUS_LABEL[d.status]}</Badge>
                {d.preview_url ? (
                  <a
                    href={d.preview_url} target="_blank" rel="noreferrer"
                    aria-label="Скачать"
                    className="shrink-0 inline-flex h-7 w-7 items-center justify-center rounded-md
                               text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
                  >
                    <Download className="h-3.5 w-3.5" />
                  </a>
                ) : (
                  <span className="shrink-0 w-7" />
                )}
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
