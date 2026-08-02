"use client";

import { useState } from "react";
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge, StatusDot } from "@/components/ui/badge";
import {
  CheckCircle2, X, FileText, Receipt, ListChecks, Sparkles, ChevronRight,
  AlertTriangle, ShieldAlert,
} from "lucide-react";
import { formatKZT, cn } from "@/lib/utils";
import { useDecideApproval } from "@/lib/hooks";
import { toast } from "@/components/Toaster";
import { OperationalBadges } from "@/components/OperationalBadges";

type ToolCall = { name: string; args: any; result: any };

export function AssistantActionCard({ tc }: { tc: ToolCall }) {
  const decide = useDecideApproval();

  if (tc.result?.error === "confirmation_required") {
    return (
      <Card className="mt-2 border-l-[3px] border-l-[hsl(var(--warning))]">
        <CardContent className="p-3.5 text-[13px] space-y-1.5">
          <div className="flex items-center gap-2 text-[12px] font-medium text-[hsl(var(--warning))] uppercase tracking-wider">
            <CheckCircle2 className="h-3.5 w-3.5" /> Confirmation required
          </div>
          <div>{tc.result.message}</div>
          <div className="text-[11px] text-muted-foreground">
            Reply <span className="kbd">yes, confirm {tc.result.amount} KZT</span> to proceed.
          </div>
        </CardContent>
      </Card>
    );
  }

  if (tc.result?.error === "permission_denied") {
    return (
      <Card className="mt-2 border-l-[3px] border-l-[hsl(var(--danger))]">
        <CardContent className="p-3.5 text-[13px] flex items-center gap-2">
          <X className="h-3.5 w-3.5 text-[hsl(var(--danger))]" />
          <span><strong>Blocked:</strong> {tc.result.message}</span>
        </CardContent>
      </Card>
    );
  }

  if (tc.result?.error === "invalid_args") {
    return (
      <Card className="mt-2 border-l-[3px] border-l-[hsl(var(--warning))]">
        <CardContent className="p-3.5 text-[13px] text-muted-foreground">
          Couldn't parse arguments — please rephrase.
        </CardContent>
      </Card>
    );
  }

  if (tc.name === "create_invoice") {
    const r = tc.result || {};
    const onDecide = (approve: boolean) => {
      if (!r.approval_id) return;
      decide.mutate({ id: r.approval_id, approve }, {
        onSuccess: () => toast.success(approve ? "Approved" : "Rejected", `${r.number} — ${approve ? "sending" : "cancelled"}`),
        onError:   (e) => toast.error("Action failed", (e as Error).message),
      });
    };

    return (
      <Card className="mt-2 border-l-[3px] border-l-[hsl(var(--warning))]">
        <CardContent className="px-4 py-3">
          <div className="flex items-center gap-2 mb-2.5">
            <span className="inline-flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
              <Sparkles className="h-3 w-3" /> AI-generated
            </span>
            <Receipt className="h-3.5 w-3.5 text-muted-foreground ml-1" />
            <span className="text-[13px] font-medium">Invoice draft</span>
            <Badge tone="warn" className="ml-auto">{r.status ?? "PENDING"}</Badge>
          </div>

          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-[12.5px]">
            <dt className="text-muted-foreground">Number</dt>
            <dd className="font-mono">{r.number ?? "—"}</dd>
            <dt className="text-muted-foreground">Total</dt>
            <dd className="tabular-nums font-medium">{r.total ? `${formatKZT(Number(r.total))} ${r.currency ?? ""}` : "—"}</dd>
            <dt className="text-muted-foreground">Template</dt>
            <dd className="truncate">
              {r.template_name
                ? <><span className="font-medium">{r.template_name}</span>
                    <span className="ml-1 text-[10.5px] text-muted-foreground">({r.template_format})</span></>
                : <span className="text-muted-foreground">Built-in HTML (no VERIFIED template)</span>}
            </dd>
            <dt className="text-muted-foreground">Action</dt>
            <dd>Send to client (requires your approval)</dd>
          </dl>

          {Array.isArray(r.needs_review) && r.needs_review.length > 0 && !r.template_name && (
            <div className="mt-2.5 rounded-md border border-[hsl(var(--warning)/0.4)] bg-warning-bg p-2 text-[11.5px]">
              <div className="font-medium text-[hsl(var(--warning))] mb-0.5">
                {r.needs_review.length} template{r.needs_review.length === 1 ? "" : "s"} exist but are not VERIFIED yet
              </div>
              <ul className="space-y-0.5">
                {r.needs_review.slice(0, 3).map((t: any) => (
                  <li key={t.id} className="flex items-center gap-2">
                    <span className="truncate">{t.name}</span>
                    <Link href={`/settings/templates/${t.id}`} className="text-[hsl(var(--brand))] hover:underline text-[11px] ml-auto">
                      Confirm mappings →
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="mt-3 flex flex-wrap items-center gap-1.5 pt-3 border-t border-border">
            <Link href={`/invoices/${r.invoice_id}`}>
              <Button size="sm" variant="ghost">
                Open invoice <ChevronRight className="h-3.5 w-3.5" />
              </Button>
            </Link>
            {r.pdf_url && (
              <a href={`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}${r.pdf_url}`}
                 target="_blank" rel="noreferrer">
                <Button size="sm" variant="outline">Download PDF</Button>
              </a>
            )}
            {r.approval_id && (
              <div className="ml-auto flex gap-1.5">
                <Button size="sm" variant="ghost" disabled={decide.isPending}
                  onClick={() => onDecide(false)}><X className="h-3.5 w-3.5" /> Reject</Button>
                <Button size="sm" disabled={decide.isPending}
                  onClick={() => onDecide(true)}><CheckCircle2 className="h-3.5 w-3.5" /> Approve & send</Button>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    );
  }

  if (tc.name === "propose_document") {
    return <DocumentProposalCard tc={tc} />;
  }

  if (tc.name === "generate_document") {
    return <GeneratedDocumentCard tc={tc} onDecide={
      (approve) => {
        const id = tc.result?.approval_id;
        if (!id) return;
        decide.mutate({ id, approve }, {
          onSuccess: () => toast.success(approve ? "Approved" : "Rejected",
            `${tc.result?.number ?? "document"} — ${approve ? "sending" : "cancelled"}`),
          onError:   (e) => toast.error("Action failed", (e as Error).message),
        });
      }
    } decidePending={decide.isPending} />;
  }

  if (tc.name === "list_invoices") {
    const list = tc.result?.invoices ?? [];
    return (
      <Card className="mt-2">
        <CardContent className="px-4 py-3">
          <div className="flex items-center gap-2 mb-2">
            <ListChecks className="h-3.5 w-3.5 text-muted-foreground" />
            <span className="text-[13px] font-medium">Invoices</span>
            <Badge tone="neutral" className="ml-auto">{list.length}</Badge>
          </div>
          {list.length === 0
            ? <div className="text-[12px] text-muted-foreground">No matching invoices.</div>
            : <ul className="divide-y divide-border -mx-1">
                {list.slice(0, 6).map((i: any) => (
                  <li key={i.id} className="flex items-center gap-2 px-1 py-1.5 text-[12.5px]">
                    <StatusDot tone={i.status === "PAID" ? "success" : i.status === "OVERDUE" ? "danger" : "info"} />
                    <span className="font-medium">{i.number}</span>
                    <span className="text-muted-foreground text-[11px]">{i.status}</span>
                    <span className="ml-auto tabular-nums">{formatKZT(Number(i.total))} {i.currency}</span>
                    <Link href={`/invoices/${i.id}`} className="text-muted-foreground hover:text-foreground">
                      <ChevronRight className="h-3.5 w-3.5" />
                    </Link>
                  </li>
                ))}
              </ul>}
        </CardContent>
      </Card>
    );
  }

  // Generic tool fallback — compact, no raw JSON leak. Operator gets the
  // tool name + the result's message if any; full payload behind a toggle.
  return (
    <Card className="mt-2">
      <CardContent className="px-3 py-2 text-[12px]">
        <div className="flex items-center gap-2 mb-1 text-muted-foreground">
          <FileText className="h-3.5 w-3.5" />
          <span className="font-medium">{tc.name}</span>
        </div>
        {tc.result?.message && (
          <div className="text-foreground/80">{String(tc.result.message)}</div>
        )}
        <details className="mt-1">
          <summary className="text-[11px] text-muted-foreground cursor-pointer select-none">
            tool details
          </summary>
          <pre className="mt-1 max-h-40 overflow-y-auto whitespace-pre-wrap text-[11px] text-muted-foreground font-mono">
            {JSON.stringify(tc.result, null, 2)}
          </pre>
        </details>
      </CardContent>
    </Card>
  );
}


// ── generate_document card ───────────────────────────────────────────────

const KIND_LABELS: Record<string, string> = {
  invoice: "Счёт", act: "Акт", nakladnaya: "Накладная",
  contract: "Договор", trust_letter: "Доверенность",
  arbitrary_template: "Документ",
};

function GeneratedDocumentCard({
  tc, onDecide, decidePending,
}: {
  tc: ToolCall;
  onDecide: (approve: boolean) => void;
  decidePending: boolean;
}) {
  const r = tc.result || {};
  const card = r.card || {};
  const tpl = card.template || {};
  const quality = card.quality || {};
  const approval = card.approval || {};
  const fallback = card.fallback || {};
  const files = card.files || {};
  const adaptation = card.adaptation || {};

  const isBlocked = approval.status === "blocked";
  const accent = isBlocked
    ? "border-l-[hsl(var(--danger))]"
    : fallback.used
      ? "border-l-[hsl(var(--warning))]"
      : "border-l-[hsl(var(--brand))]";

  const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const pdfHref = files.pdf?.url ? `${apiBase}${files.pdf.url}` : null;
  const docxHref = files.docx?.url ? `${apiBase}${files.docx.url}` : null;

  return (
    <Card className={`mt-2 border-l-[3px] ${accent}`}>
      <CardContent className="px-4 py-3 space-y-3">
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
            <Sparkles className="h-3 w-3" /> AI-generated
          </span>
          <FileText className="h-3.5 w-3.5 text-muted-foreground ml-1" />
          <span className="text-[13px] font-medium">
            {KIND_LABELS[card.kind] ?? "Document"} {r.number}
          </span>
          {isBlocked ? (
            <Badge tone="danger" className="ml-auto">BLOCKED</Badge>
          ) : (
            <Badge tone={fallback.used ? "warn" : "success"} className="ml-auto">
              {approval.status?.toUpperCase() ?? "GENERATED"}
            </Badge>
          )}
        </div>

        {card.subtitle && (
          <div className="text-[12.5px] text-muted-foreground -mt-2">{card.subtitle}</div>
        )}

        <OperationalBadges
          verified={tpl.verified}
          operationalScore={tpl.operational_score}
          qualityScore={quality.score}
          qualityStatus={quality.status}
          pdfReady={files.pdf?.ready}
          renderMs={card.render?.duration_ms}
          templateFormat={tpl.format}
        />

        <div className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-[12.5px] pt-1">
          <dt className="text-muted-foreground">Template</dt>
          <dd className="truncate">
            <span className="font-medium">{tpl.name ?? "—"}</span>
            {adaptation?.applied && (
              <span className="ml-2 text-[11px] text-sky-500">
                · adapted (+{adaptation.anchors_injected ?? 0} anchor{adaptation.anchors_injected === 1 ? "" : "s"})
              </span>
            )}
          </dd>
        </div>

        {fallback.used && (
          <div className="flex items-start gap-2 rounded-md ring-1 ring-amber-500/30 bg-amber-500/8 px-2.5 py-2 text-[11.5px]">
            <AlertTriangle className="h-3.5 w-3.5 mt-0.5 text-amber-500 shrink-0" />
            <div className="min-w-0">
              <div className="font-medium">Fallback layout used</div>
              <div className="text-muted-foreground">{fallback.reason ?? "Original template could not be rendered."}</div>
            </div>
          </div>
        )}

        {isBlocked && Array.isArray(quality.issues) && quality.issues.length > 0 && (
          <div className="rounded-md ring-1 ring-red-500/25 bg-red-500/8 px-2.5 py-2 text-[11.5px]">
            <div className="flex items-center gap-1.5 font-medium text-red-500">
              <ShieldAlert className="h-3.5 w-3.5" />
              Blocked by quality gate · {quality.issues.length} issue{quality.issues.length === 1 ? "" : "s"}
            </div>
            <ul className="mt-1 space-y-0.5 text-muted-foreground">
              {quality.issues.slice(0, 3).map((i: any, idx: number) => (
                <li key={idx}>• {i.message}</li>
              ))}
            </ul>
          </div>
        )}

        <div className="flex flex-wrap items-center gap-1.5 pt-2 border-t border-border">
          {pdfHref && (
            <a href={pdfHref} target="_blank" rel="noreferrer">
              <Button size="sm" variant="outline">Open PDF</Button>
            </a>
          )}
          {docxHref && tpl.format !== "html" && (
            <a href={docxHref} target="_blank" rel="noreferrer">
              <Button size="sm" variant="ghost">Download {tpl.format?.toUpperCase()}</Button>
            </a>
          )}
          <Link href={`/documents/${r.document_id}`}>
            <Button size="sm" variant="ghost">
              Open document <ChevronRight className="h-3.5 w-3.5" />
            </Button>
          </Link>
          {r.approval_id && !isBlocked && (
            <div className="ml-auto flex gap-1.5">
              <Button size="sm" variant="ghost" disabled={decidePending}
                onClick={() => onDecide(false)}>
                <X className="h-3.5 w-3.5" /> Reject
              </Button>
              <Button size="sm" disabled={decidePending}
                onClick={() => onDecide(true)}>
                <CheckCircle2 className="h-3.5 w-3.5" /> Approve & send
              </Button>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}


// ── propose_document card ────────────────────────────────────────────────
// Read-only preview rendered as an interactive confirmation card. Confirm
// dispatches a follow-up message ("Подтверждаю, создай документ") that the
// assistant page listens for and routes through send() → the LLM then
// invokes generate_document for the actual render.

function DocumentProposalCard({ tc }: { tc: ToolCall }) {
  const p = tc.result || {};
  if (p.error) {
    return (
      <Card className="mt-2 border-l-[3px] border-l-[hsl(var(--warning))]">
        <CardContent className="p-3.5 text-[13px] text-muted-foreground">
          {p.message ?? "Couldn't prepare a document proposal."}
        </CardContent>
      </Card>
    );
  }

  const human = p.human_kind ?? "Документ";
  const intent = p.intent ?? {};
  const items: any[] = p.items_preview ?? [];
  const missing: any[] = p.missing_fields ?? [];
  const suggested = p.suggested_template;
  const alternatives: any[] = p.alternatives ?? [];
  const ambiguous = !!p.ambiguous;

  const [selectedTpl, setSelectedTpl] = useState<string | null>(suggested?.id ?? null);
  const [confirming, setConfirming] = useState(false);

  const onConfirm = () => {
    setConfirming(true);
    const tplPart = selectedTpl && selectedTpl !== suggested?.id
      ? ` (шаблон: ${(alternatives.find((a) => a.id === selectedTpl)?.name) ?? selectedTpl})`
      : "";
    // Verb-style confirmation phrase so both the LLM and the regex fallback
    // recognise it as confirmation, not a new request.
    const text = `Подтверждаю, создай ${(p.kind ?? "документ")} как предложено${tplPart}.`;
    window.dispatchEvent(new CustomEvent("assistant:send", { detail: text }));
  };

  const onCancel = () => {
    window.dispatchEvent(new CustomEvent("assistant:send", { detail: "Отмена." }));
  };

  return (
    <Card className="mt-2 border-l-[3px] border-l-[hsl(var(--brand))]">
      <CardContent className="px-4 py-3 space-y-3">
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
            <Sparkles className="h-3 w-3" /> AI proposal
          </span>
          <FileText className="h-3.5 w-3.5 text-muted-foreground ml-1" />
          <span className="text-[13px] font-medium">{human} — подтвердите перед созданием</span>
          <Badge tone="brand" className="ml-auto">CONFIRM</Badge>
        </div>

        <div className="text-[12.5px] text-foreground/80 leading-snug">
          {p.message ?? "Готов сгенерировать документ. Проверьте параметры."}
        </div>

        {/* Intent summary */}
        <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-[12.5px]">
          {intent.client_name && (
            <>
              <dt className="text-muted-foreground">Клиент</dt>
              <dd className="font-medium">{intent.client_name}</dd>
            </>
          )}
          {intent.total != null && (
            <>
              <dt className="text-muted-foreground">Сумма</dt>
              <dd className="tabular-nums font-medium">
                {p.preview_context?.total ?? intent.total} {intent.currency ?? "KZT"}
                {intent.vat_percent != null && intent.vat_percent !== "" && (
                  <span className="ml-2 text-[11px] text-muted-foreground">
                    (НДС {intent.vat_percent}% — {p.preview_context?.vat})
                  </span>
                )}
              </dd>
            </>
          )}
          {items.length > 0 && (
            <>
              <dt className="text-muted-foreground">Позиций</dt>
              <dd>
                {items.length}
                {items.length <= 5 && (
                  <ul className="mt-1 space-y-0.5">
                    {items.map((it, i) => (
                      <li key={i} className="text-[11.5px] text-muted-foreground">
                        — {it.name} {it.qty && it.qty !== 1 ? `× ${it.qty}` : ""} · {it.total}
                      </li>
                    ))}
                  </ul>
                )}
              </dd>
            </>
          )}
        </dl>

        {/* Template selection */}
        {suggested ? (
          <div className="space-y-1.5">
            <div className="text-[10.5px] uppercase tracking-wider text-muted-foreground">
              {ambiguous ? "Несколько подходящих шаблонов" : "Предложенный шаблон"}
            </div>
            <div className="space-y-1">
              {[suggested, ...alternatives.filter((a) => a.id !== suggested.id)].map((t) => (
                <label key={t.id}
                  className={cn(
                    "flex items-center gap-2 rounded-md border px-2.5 py-1.5 cursor-pointer transition-colors",
                    selectedTpl === t.id
                      ? "border-[hsl(var(--brand))] bg-[hsl(var(--brand)/0.06)]"
                      : "border-border hover:bg-accent",
                  )}>
                  <input
                    type="radio" name={`tpl-${tc.name}`} className="h-3 w-3"
                    checked={selectedTpl === t.id}
                    onChange={() => setSelectedTpl(t.id)}
                  />
                  <span className="text-[12.5px] font-medium truncate flex-1">{t.name}</span>
                  {t.verified && (
                    <span className="text-[10px] font-medium text-emerald-500">VERIFIED</span>
                  )}
                  {typeof t.operational_score === "number" && (
                    <span className="text-[10.5px] text-muted-foreground tabular-nums">
                      {t.operational_score}/100
                    </span>
                  )}
                  <span className="text-[10px] font-mono opacity-60 uppercase">{t.format}</span>
                </label>
              ))}
            </div>
          </div>
        ) : (
          <div className="rounded-md ring-1 ring-amber-500/30 bg-amber-500/8 px-2.5 py-2 text-[11.5px] text-muted-foreground">
            Нет подходящего VERIFIED-шаблона — будет использован встроенный fallback-макет.
          </div>
        )}

        {/* Missing fields */}
        {missing.length > 0 && (
          <div className="rounded-md ring-1 ring-amber-500/30 bg-amber-500/8 px-2.5 py-2 text-[11.5px]">
            <div className="flex items-center gap-1.5 font-medium text-amber-500 mb-0.5">
              <AlertTriangle className="h-3.5 w-3.5" /> Не хватает данных
            </div>
            <ul className="text-muted-foreground space-y-0.5">
              {missing.map((m: any, i: number) => (
                <li key={i}>• {m.label} {m.hint && <span className="opacity-70">— {m.hint}</span>}</li>
              ))}
            </ul>
            <div className="mt-1 text-[11px] text-muted-foreground/80">
              Можно подтвердить как есть — поля будут пустыми, или уточните одним сообщением.
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="flex flex-wrap items-center gap-1.5 pt-2 border-t border-border">
          <Button size="sm" onClick={onConfirm} disabled={confirming}>
            <CheckCircle2 className="h-3.5 w-3.5" />
            {confirming ? "Создаю…" : "Подтвердить и создать"}
          </Button>
          <Button size="sm" variant="ghost" onClick={onCancel} disabled={confirming}>
            <X className="h-3.5 w-3.5" /> Отмена
          </Button>
          <span className="ml-auto text-[10.5px] text-muted-foreground">
            preview · никаких изменений не сохранено
          </span>
        </div>
      </CardContent>
    </Card>
  );
}
