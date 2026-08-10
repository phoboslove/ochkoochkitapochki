"use client";

import { useState } from "react";
import {
  Building2, Calculator, Palette, FileType2, ShieldCheck, Bell, Plug,
  BookOpen, Lock, Languages, CreditCard,
} from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Field, Text, Toggle, Select } from "@/components/settings/SettingsField";
import { SaveIndicator } from "@/components/settings/SaveIndicator";
import { KnowledgeBase } from "@/components/settings/KnowledgeBase";
import { TemplateManager } from "@/components/TemplateManager";
import { TelegramPanel } from "@/components/TelegramPanel";
import { LanguagePicker } from "@/components/LanguagePicker";
import { useBusinessContext, useSectionEditor } from "@/lib/settings";
import { useUploadLogo, useMySubscription, useMyPayments } from "@/lib/hooks";
import { formatKZT } from "@/lib/utils";
import type { SubscriptionStatus } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { TranslationKey } from "@/lib/translations";

const TABS = [
  { key: "company",       labelKey: "settings.tab.company",       icon: Building2 },
  { key: "accounting",    labelKey: "settings.tab.accounting",    icon: Calculator },
  { key: "branding",      labelKey: "settings.tab.branding",      icon: Palette },
  { key: "templates",     labelKey: "settings.tab.templates",     icon: FileType2 },
  { key: "approvals",     labelKey: "settings.tab.approvals",     icon: ShieldCheck },
  { key: "notifications", labelKey: "settings.tab.notifications", icon: Bell },
  { key: "integrations",  labelKey: "settings.tab.integrations",  icon: Plug },
  { key: "knowledge",     labelKey: "settings.tab.knowledge",     icon: BookOpen },
  { key: "language",      labelKey: "settings.tab.language",      icon: Languages },
  { key: "billing",       labelKey: "settings.tab.billing",       icon: CreditCard },
  { key: "security",      labelKey: "settings.tab.security",      icon: Lock },
] as const satisfies readonly { key: string; labelKey: TranslationKey; icon: any }[];
type TabKey = typeof TABS[number]["key"];

export default function SettingsPage() {
  const [tab, setTab] = useState<TabKey>("company");
  const { data: ctx } = useBusinessContext();
  const t = useT();

  return (
    <>
      <PageHeader title={t("settings.title")}
        description={t("settings.subtitle")} />

      <div className="flex flex-col lg:flex-row gap-6">
        <nav className="lg:w-56 shrink-0 grid grid-cols-3 lg:grid-cols-1 gap-1">
          {TABS.map((tab_) => {
            const Icon = tab_.icon;
            const active = tab_.key === tab;
            return (
              <button key={tab_.key} onClick={() => setTab(tab_.key)}
                className={cn(
                  "flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors",
                  active ? "bg-accent text-accent-foreground"
                         : "text-muted-foreground hover:bg-accent/50 hover:text-foreground",
                )}>
                <Icon className="h-4 w-4" /> <span className="truncate">{t(tab_.labelKey)}</span>
              </button>
            );
          })}
        </nav>

        <div className="flex-1 min-w-0 space-y-6">
          {tab === "company"       && <CompanySection ctx={ctx} />}
          {tab === "accounting"    && <AccountingSection ctx={ctx} />}
          {tab === "branding"      && <BrandingSection ctx={ctx} />}
          {tab === "templates"     && <TemplateManager />}
          {tab === "approvals"     && <ApprovalsSection ctx={ctx} />}
          {tab === "notifications" && <NotificationsSection ctx={ctx} />}
          {tab === "integrations"  && <IntegrationsHint />}
          {tab === "knowledge"     && <KnowledgeBase />}
          {tab === "language"      && <LanguagePicker />}
          {tab === "billing"       && <BillingSection />}
          {tab === "security"      && <SecurityHint />}
          {tab === "company" && <TelegramPanel />}
        </div>
      </div>
    </>
  );
}

// ── Sections ────────────────────────────────────────────────────────────────

function SectionShell({ title, hint, status, children }: {
  title: string; hint?: string; status: React.ReactNode; children: React.ReactNode;
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between">
        <div>
          <CardTitle>{title}</CardTitle>
          {hint && <p className="text-xs text-muted-foreground mt-1">{hint}</p>}
        </div>
        {status}
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

function CompanySection({ ctx }: { ctx: any }) {
  const ed = useSectionEditor<any>("company", ctx?.company);
  const f = ed.draft;
  return (
    <SectionShell title="Company profile"
      hint="Used in invoice headers, AI context, tax reminders, emails."
      status={<SaveIndicator dirty={ed.dirty} saving={ed.saving} savedAt={ed.savedAt} />}>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Field label="Company name"><Text value={f.name} onChange={(v) => ed.setField("name", v)} /></Field>
        <Field label="Legal name"><Text value={f.legal_name} onChange={(v) => ed.setField("legal_name", v)} /></Field>
        <Field label="BIN / Tax ID"><Text value={f.bin} onChange={(v) => ed.setField("bin", v)} /></Field>
        <Field label="Country code"><Text value={f.country_code} onChange={(v) => ed.setField("country_code", v.toUpperCase())} /></Field>
        <Field label="Currency"><Text value={f.currency} onChange={(v) => ed.setField("currency", v.toUpperCase())} /></Field>
        <Field label="Timezone"><Text value={f.timezone} onChange={(v) => ed.setField("timezone", v)} /></Field>
        <Field label="Phone"><Text value={f.phone} onChange={(v) => ed.setField("phone", v)} /></Field>
        <Field label="Email"><Text value={f.email} onChange={(v) => ed.setField("email", v)} type="email" /></Field>
        <Field label="Address" span={2}><Text value={f.address} onChange={(v) => ed.setField("address", v)} /></Field>
        <Field label="Website"><Text value={f.website} onChange={(v) => ed.setField("website", v)} /></Field>
        <Field label="Director"><Text value={f.director_name} onChange={(v) => ed.setField("director_name", v)} /></Field>
        <Field label="Accountant"><Text value={f.accountant_name} onChange={(v) => ed.setField("accountant_name", v)} /></Field>
      </div>

      <h3 className="mt-6 mb-2 text-xs uppercase tracking-wider text-muted-foreground">Bank details</h3>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Field label="Bank name"><Text value={f.bank?.bank_name}
          onChange={(v) => ed.setField("bank", { ...(f.bank ?? {}), bank_name: v })} /></Field>
        <Field label="IBAN"><Text value={f.bank?.iban}
          onChange={(v) => ed.setField("bank", { ...(f.bank ?? {}), iban: v })} /></Field>
        <Field label="BIK"><Text value={f.bank?.bik}
          onChange={(v) => ed.setField("bank", { ...(f.bank ?? {}), bik: v })} /></Field>
        <Field label="Account"><Text value={f.bank?.account}
          onChange={(v) => ed.setField("bank", { ...(f.bank ?? {}), account: v })} /></Field>
      </div>
    </SectionShell>
  );
}

function AccountingSection({ ctx }: { ctx: any }) {
  const ed = useSectionEditor<any>("accounting", ctx?.accounting);
  const f = ed.draft;
  return (
    <SectionShell title="Accounting & tax"
      hint="Applied automatically to invoices, AI calculations, anomaly detection."
      status={<SaveIndicator dirty={ed.dirty} saving={ed.saving} savedAt={ed.savedAt} />}>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Field label="Tax mode">
          <Select value={f.tax_mode ?? "simplified"} onChange={(v) => ed.setField("tax_mode", v)}
            options={[
              { value: "simplified", label: "Simplified" },
              { value: "general",    label: "General" },
              { value: "retail",     label: "Retail" },
              { value: "custom",     label: "Custom" },
            ]} />
        </Field>
        <Field label="Payroll tax mode">
          <Select value={f.payroll_tax_mode ?? "standard"} onChange={(v) => ed.setField("payroll_tax_mode", v)}
            options={[
              { value: "standard", label: "Standard" },
              { value: "none",     label: "None" },
              { value: "custom",   label: "Custom" },
            ]} />
        </Field>

        <Field label="VAT / НДС" span={2}>
          <div className="flex items-center gap-4">
            <Toggle label="Enabled" checked={!!f.vat_enabled}
              onChange={(v) => ed.setField("vat_enabled", v)}
              hint="When on, invoices auto-apply the VAT %." />
            <div className="w-32">
              <Text value={f.vat_percent} onChange={(v) => ed.setField("vat_percent", Number(v) || 0)}
                    type="number" step="0.1" />
            </div>
            <span className="text-xs text-muted-foreground">%</span>
          </div>
        </Field>

        <Field label="Numbering format" hint='{year}, {seq:04d} placeholders'>
          <Text value={f.numbering_format} onChange={(v) => ed.setField("numbering_format", v)} />
        </Field>
        <Field label="Default currency"><Text value={f.currency_default}
          onChange={(v) => ed.setField("currency_default", v.toUpperCase())} /></Field>

        <Field label="Default due (days)"><Text value={f.due_in_days_default}
          onChange={(v) => ed.setField("due_in_days_default", Number(v) || 0)} type="number" /></Field>
        <Field label="Overdue reminder after (days)"><Text value={f.overdue_reminder_days}
          onChange={(v) => ed.setField("overdue_reminder_days", Number(v) || 0)} type="number" /></Field>

        <Field label="Fiscal year starts month"><Text value={f.fiscal_year_start_month}
          onChange={(v) => ed.setField("fiscal_year_start_month", Math.min(12, Math.max(1, Number(v) || 1)))}
          type="number" min={1} max={12} /></Field>
        <Field label="Invoice footer note" span={2}>
          <Text value={f.footer_note} onChange={(v) => ed.setField("footer_note", v)} />
        </Field>
      </div>
    </SectionShell>
  );
}

function BrandingSection({ ctx }: { ctx: any }) {
  const ed = useSectionEditor<any>("branding", ctx?.branding);
  const f = ed.draft;
  const uploadLogo = useUploadLogo();
  return (
    <SectionShell title="Branding"
      hint="Applied to invoice PDFs, emails, the dashboard."
      status={<SaveIndicator dirty={ed.dirty} saving={ed.saving} savedAt={ed.savedAt} />}>
      <div className="flex items-center gap-4 mb-5">
        {ctx?.branding?.logo_key
          ? <div className="h-12 w-12 rounded border bg-muted" />
          : <div className="h-12 w-12 rounded border bg-muted" />}
        <label className="inline-flex items-center gap-2 cursor-pointer rounded-md border bg-background h-9 px-3 text-sm hover:bg-accent">
          {uploadLogo.isPending ? "Uploading…" : "Upload logo"}
          <input type="file" accept="image/*" className="hidden"
            onChange={(e) => { const file = e.target.files?.[0]; if (file) uploadLogo.mutate(file); }} />
        </label>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Field label="Primary color" hint="hex, e.g. #0f172a">
          <div className="flex items-center gap-2">
            <input type="color" value={f.primary_color || "#0f172a"}
                   onChange={(e) => ed.setField("primary_color", e.target.value)}
                   className="h-9 w-12 border rounded cursor-pointer" />
            <Text value={f.primary_color} onChange={(v) => ed.setField("primary_color", v)} />
          </div>
        </Field>
        <Field label="Secondary color">
          <div className="flex items-center gap-2">
            <input type="color" value={f.secondary_color || "#e5e7eb"}
                   onChange={(e) => ed.setField("secondary_color", e.target.value)}
                   className="h-9 w-12 border rounded cursor-pointer" />
            <Text value={f.secondary_color} onChange={(v) => ed.setField("secondary_color", v)} />
          </div>
        </Field>
        <Field label="Stamp image key" hint="Upload separately to /companies/branding/stamp (future)">
          <Text value={f.stamp_key} onChange={(v) => ed.setField("stamp_key", v)} />
        </Field>
        <Field label="Signature image key">
          <Text value={f.signature_key} onChange={(v) => ed.setField("signature_key", v)} />
        </Field>
      </div>
    </SectionShell>
  );
}

function ApprovalsSection({ ctx }: { ctx: any }) {
  const ed = useSectionEditor<any>("approvals", ctx?.approvals);
  const f = ed.draft;
  return (
    <SectionShell title="Approval rules"
      hint="Approvals, Telegram quick-actions, and workflows all read from these rules."
      status={<SaveIndicator dirty={ed.dirty} saving={ed.saving} savedAt={ed.savedAt} />}>
      <div className="space-y-4">
        <Toggle label="Auto-send invoices below threshold (skip approval)"
          checked={!!f.auto_send_invoices}
          onChange={(v) => ed.setField("auto_send_invoices", v)}
          hint="Only applies when amount is below threshold AND below high-value cap." />

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Field label="Invoice threshold (require approval above)" hint="0 = always require approval">
            <Text value={f.invoice_amount_threshold}
              onChange={(v) => ed.setField("invoice_amount_threshold", Number(v) || 0)} type="number" />
          </Field>
          <Field label="High-value cap (extra confirmation in AI)">
            <Text value={f.high_value_threshold}
              onChange={(v) => ed.setField("high_value_threshold", Number(v) || 0)} type="number" />
          </Field>
          <Field label="Admin/Owner required above" span={2}>
            <Text value={f.require_admin_above}
              onChange={(v) => ed.setField("require_admin_above", Number(v) || 0)} type="number" />
          </Field>
        </div>
      </div>
    </SectionShell>
  );
}

function NotificationsSection({ ctx }: { ctx: any }) {
  const ed = useSectionEditor<any>("notifications", ctx?.notifications);
  const f = ed.draft;
  const setOn = (k: string, v: boolean) =>
    ed.setField("notify_on", { ...(f.notify_on ?? {}), [k]: v });
  return (
    <SectionShell title="Notifications"
      hint="Telegram + email fan-out respects these toggles for the whole organization."
      status={<SaveIndicator dirty={ed.dirty} saving={ed.saving} savedAt={ed.savedAt} />}>
      <div className="space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 rounded-md border p-3">
          <Toggle label="Telegram channel enabled (org-wide)"
            checked={!!f.org_telegram_enabled}
            onChange={(v) => ed.setField("org_telegram_enabled", v)} />
          <Toggle label="Email channel enabled (org-wide)"
            checked={!!f.org_email_enabled}
            onChange={(v) => ed.setField("org_email_enabled", v)} />
        </div>
        <div className="rounded-md border p-3 space-y-2">
          <div className="text-xs text-muted-foreground mb-1">Event types</div>
          {Object.entries({
            approval_request: "Approval requested",
            approval_decided: "Approval decided",
            overdue:          "Overdue invoice",
            workflow_failed:  "Workflow failure",
            anomaly:          "Anomaly detected",
            ocr_failed:       "OCR failed",
          }).map(([k, label]) => (
            <Toggle key={k} label={label} checked={!!f.notify_on?.[k]} onChange={(v) => setOn(k, v)} />
          ))}
        </div>
      </div>
    </SectionShell>
  );
}

const STATUS_TONE: Record<SubscriptionStatus, "success" | "info" | "warn" | "danger" | "neutral"> = {
  active: "success", trialing: "info", past_due: "warn", suspended: "danger", cancelled: "neutral",
};
const STATUS_LABEL: Record<SubscriptionStatus, string> = {
  active: "Активна", trialing: "Триал", past_due: "Просрочена", suspended: "Приостановлена", cancelled: "Отменена",
};

function BillingSection() {
  const { data: sub, isLoading } = useMySubscription();
  const { data: payments } = useMyPayments();

  if (isLoading) return <Card><CardContent className="p-6 text-sm text-muted-foreground">Загрузка…</CardContent></Card>;
  if (!sub) return <Card><CardContent className="p-6 text-sm text-muted-foreground">Нет данных о подписке.</CardContent></Card>;

  const pct = Math.min(100, Math.round((sub.usage.documents_used / Math.max(sub.usage.documents_limit, 1)) * 100));
  const nearLimit = pct >= 80;

  return (
    <div className="space-y-6">
      <SectionShell
        title="Текущий тариф"
        hint="Лимиты и использование за этот календарный месяц."
        status={<Badge tone={STATUS_TONE[sub.status]}>{STATUS_LABEL[sub.status]}</Badge>}
      >
        <div className="flex items-center justify-between mb-4">
          <div>
            <div className="text-lg font-semibold">{sub.plan.name}</div>
            <div className="text-sm text-muted-foreground">
              {formatKZT(sub.plan.price_amount)} {sub.plan.price_currency} / {sub.plan.billing_period === "month" ? "мес" : "год"}
            </div>
          </div>
          <a href="mailto:sales@wagwan1.com?subject=Продление подписки">
            <button className="h-8 px-3 rounded-md bg-[hsl(var(--brand))] text-[hsl(var(--brand-foreground))] text-[13px] font-medium hover:bg-[hsl(var(--brand)/0.92)]">
              Продлить
            </button>
          </a>
        </div>

        <div className="mb-1 flex items-center justify-between text-[12.5px]">
          <span className="text-muted-foreground">Документов в этом месяце</span>
          <span className="tabular-nums font-medium">{sub.usage.documents_used} / {sub.usage.documents_limit}</span>
        </div>
        <div className="h-1.5 rounded-full bg-muted overflow-hidden">
          <div
            className={"h-full rounded-full transition-[width] " + (nearLimit ? "bg-[hsl(var(--warning))]" : "bg-[hsl(var(--brand))]")}
            style={{ width: `${pct}%` }}
          />
        </div>

        <dl className="grid grid-cols-2 gap-y-2 mt-5 text-[13px]">
          <dt className="text-muted-foreground">Период действует до</dt>
          <dd>{new Date(sub.period_end).toLocaleString("ru-RU")}</dd>
          <dt className="text-muted-foreground">Пользователей по тарифу</dt>
          <dd>{sub.limits.users}</dd>
          <dt className="text-muted-foreground">Шаблонов по тарифу</dt>
          <dd>{sub.limits.templates}</dd>
        </dl>
      </SectionShell>

      <SectionShell title="История платежей" status={null}>
        {!payments || payments.length === 0 ? (
          <div className="text-sm text-muted-foreground">Платежей ещё не было.</div>
        ) : (
          <ul className="space-y-2 text-[13px]">
            {payments.map((p) => (
              <li key={p.id} className="flex justify-between">
                <span className="text-muted-foreground">
                  {new Date(p.created_at).toLocaleDateString("ru-RU")} {p.comment && `· ${p.comment}`}
                </span>
                <span className="tabular-nums font-medium">{formatKZT(p.amount)} {p.currency}</span>
              </li>
            ))}
          </ul>
        )}
      </SectionShell>
    </div>
  );
}

function IntegrationsHint() {
  return (
    <Card>
      <CardContent className="p-6 text-sm text-muted-foreground">
        Integrations are managed in the dedicated page → <a href="/integrations" className="underline">/integrations</a>.
        Their <em>state</em> (connected, provider, config) is part of the shared business context and is
        automatically synced with AI tools, approvals, and notification fan-out.
      </CardContent>
    </Card>
  );
}

function SecurityHint() {
  return (
    <Card>
      <CardContent className="p-6 text-sm text-muted-foreground space-y-2">
        <p>Sessions use bearer JWT (HS256). Rotate <code className="font-mono">JWT_SECRET</code> per environment.</p>
        <p>Roles: <b>OWNER</b> → <b>ADMIN</b> → <b>MEMBER</b>/<b>ACCOUNTANT</b> → <b>VIEWER</b>. Configure in /team.</p>
        <p>All settings changes are logged in <a href="/activity" className="underline">Activity</a> as <code className="font-mono">settings.changed</code>.</p>
      </CardContent>
    </Card>
  );
}
