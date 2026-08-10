"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  useCompany, useUpdateCompany, useUploadLogo, useUploadDocxTemplate,
  useConnectIntegration, useSimulateWhatsApp, useOnboarding, useCompleteOnboarding, useSeedDemo,
} from "@/lib/hooks";
import { toast } from "@/components/Toaster";
import { Check, Building2, Image as Img, FileText, MessageSquare, Receipt, Users, Sparkles, ArrowLeft } from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/api";

const STEPS = [
  { key: "organization", label: "Organization",  icon: Building2 },
  { key: "branding",     label: "Branding",      icon: Img },
  { key: "template",     label: "Template",      icon: FileText },
  { key: "whatsapp",     label: "WhatsApp",      icon: MessageSquare },
  { key: "first_invoice",label: "First invoice", icon: Receipt },
  { key: "team",         label: "Invite team",   icon: Users },
];

export default function OnboardingPage() {
  const router = useRouter();
  const { data: company } = useCompany();
  const { data: state } = useOnboarding();
  const complete = useCompleteOnboarding();
  const seed = useSeedDemo();
  const [step, setStep] = useState(0);

  const stepDone = (key: string) => state?.steps.find((s) => s.key === key)?.done ?? false;

  const finish = () =>
    complete.mutate(undefined, {
      onSuccess: () => { toast.success("All set", "Welcome to Wagwan"); router.replace("/dashboard"); },
    });

  const doneCount = state?.steps.filter((s) => s.done).length ?? 0;
  const totalSteps = state?.steps.length ?? STEPS.length;

  return (
    <div className="mx-auto max-w-3xl">
      <Link href="/dashboard"
        className="inline-flex items-center gap-1 text-[12px] text-muted-foreground hover:text-foreground mb-4">
        <ArrowLeft className="h-3.5 w-3.5" /> Back to dashboard
      </Link>

      <div className="mb-6 flex items-end justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Setup guide</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {state?.completed
              ? "Already complete — revisit any step to reconfigure."
              : "A few quick steps and you're ready to operate."}
          </p>
          <div className="mt-3 flex items-center gap-3">
            <div className="h-1.5 w-48 bg-muted rounded-full overflow-hidden">
              <div className="h-full bg-[hsl(var(--brand))] rounded-full transition-[width] duration-500"
                   style={{ width: `${(doneCount / totalSteps) * 100}%` }} />
            </div>
            <span className="text-[11px] text-muted-foreground tabular-nums">{doneCount} / {totalSteps}</span>
            {state?.completed && <Badge tone="success">Completed</Badge>}
          </div>
        </div>
        <Button variant="outline" size="sm" disabled={seed.isPending}
          onClick={() => seed.mutate(undefined, {
            onSuccess: (r) => toast.success(r.already_seeded ? "Demo already loaded" : "Demo data loaded",
              "Explore invoices, approvals, and the activity feed."),
          })}>
          <Sparkles className="h-3.5 w-3.5" /> Load demo data
        </Button>
      </div>

      <Stepper current={step} steps={STEPS} doneOf={stepDone} onClick={setStep} />

      <Card className="mt-6">
        <CardContent className="p-6">
          {step === 0 && <OrgStep company={company} />}
          {step === 1 && <BrandingStep />}
          {step === 2 && <TemplateStep />}
          {step === 3 && <WhatsAppStep />}
          {step === 4 && <FirstInvoiceStep />}
          {step === 5 && <TeamStep />}
        </CardContent>
      </Card>

      <div className="mt-4 flex items-center justify-between">
        <Button variant="ghost" onClick={() => setStep(Math.max(0, step - 1))} disabled={step === 0}>Back</Button>
        {step < STEPS.length - 1 ? (
          <Button onClick={() => setStep(step + 1)}>Next</Button>
        ) : (
          <Button onClick={finish} disabled={complete.isPending}>
            {complete.isPending ? "Finishing…" : "Enter Wagwan"}
          </Button>
        )}
      </div>

      <p className="mt-4 text-xs text-muted-foreground text-center">
        Optional steps can be skipped — you can finish them later in <code className="font-mono">/settings</code>.
      </p>
    </div>
  );
}

function Stepper({ current, steps, doneOf, onClick }: {
  current: number; steps: { key: string; label: string; icon: any }[];
  doneOf: (k: string) => boolean; onClick: (i: number) => void;
}) {
  return (
    <ol className="grid grid-cols-3 sm:grid-cols-6 gap-2">
      {steps.map((s, i) => {
        const done = doneOf(s.key); const active = i === current;
        const Icon = s.icon;
        return (
          <li key={s.key}>
            <button onClick={() => onClick(i)}
              className={"w-full flex flex-col items-center gap-1 rounded-md border p-2 text-xs transition " +
                (active ? "border-primary bg-accent" : done ? "border-[hsl(var(--success)/0.3)]" : "border-border hover:bg-accent/30")}>
              <span className={"h-7 w-7 rounded-full grid place-items-center " +
                (done ? "bg-success-bg text-[hsl(var(--success))]" : active ? "bg-primary text-primary-foreground" : "bg-muted")}>
                {done ? <Check className="h-3.5 w-3.5" /> : <Icon className="h-3.5 w-3.5" />}
              </span>
              <span className="text-center leading-tight">{s.label}</span>
            </button>
          </li>
        );
      })}
    </ol>
  );
}

function OrgStep({ company }: { company: any }) {
  const update = useUpdateCompany();
  const [name, setName] = useState(company?.name ?? "");
  const [bin, setBin] = useState(company?.bin ?? "");
  const [tax, setTax] = useState(company?.tax_mode ?? "simplified");
  return (
    <div className="space-y-4">
      <Heading title="Tell us about your business" sub="Used for invoice headers, AI context, and tax reminders." />
      <Field label="Company name"><Input value={name} onChange={(e) => setName(e.target.value)} /></Field>
      <Field label="BIN / tax ID"><Input value={bin} onChange={(e) => setBin(e.target.value)} /></Field>
      <Field label="Tax mode"><Input value={tax} onChange={(e) => setTax(e.target.value)} /></Field>
      <Button onClick={() => update.mutate({ name, bin, tax_mode: tax } as any, {
        onSuccess: () => toast.success("Saved"),
      })} disabled={update.isPending}>{update.isPending ? "Saving…" : "Save"}</Button>
    </div>
  );
}

function BrandingStep() {
  const { data: company } = useCompany();
  const upload = useUploadLogo();
  return (
    <div className="space-y-4">
      <Heading title="Add a logo" sub="Appears on invoices and PDFs. Optional but recommended." />
      <div className="flex items-center gap-4">
        {company?.logo_url
          ? <img src={api.fileUrl(company.logo_url)} alt="" className="h-14 rounded border" />
          : <div className="h-14 w-14 rounded bg-muted" />}
        <label className="inline-flex items-center gap-2 cursor-pointer rounded-md border bg-background h-9 px-3 text-sm hover:bg-accent">
          <Img className="h-3.5 w-3.5" />
          {upload.isPending ? "Uploading…" : "Choose image"}
          <input type="file" accept="image/*" className="hidden"
                 onChange={(e) => { const f = e.target.files?.[0]; if (f) upload.mutate(f, { onSuccess: () => toast.success("Logo updated") }); }} />
        </label>
      </div>
    </div>
  );
}

function TemplateStep() {
  const upload = useUploadDocxTemplate();
  const [name, setName] = useState("Standard invoice");
  const [file, setFile] = useState<File | null>(null);
  return (
    <div className="space-y-4">
      <Heading title="Custom invoice template (optional)" sub="Upload a .docx template — placeholders like {{ invoice.number }} will be filled automatically." />
      <Field label="Template name"><Input value={name} onChange={(e) => setName(e.target.value)} /></Field>
      <label className="inline-flex items-center justify-center gap-2 rounded-md border bg-background h-9 px-3 text-sm cursor-pointer hover:bg-accent">
        <FileText className="h-3.5 w-3.5" /> {file ? file.name : "Choose .docx"}
        <input type="file" accept=".docx" className="hidden" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
      </label>
      <div>
        <Button onClick={() => file && upload.mutate({ file, name, kind: "invoice", is_default: true }, {
          onSuccess: () => toast.success("Template saved"),
        })} disabled={!file || upload.isPending}>
          {upload.isPending ? "Uploading…" : "Upload template"}
        </Button>
      </div>
      <p className="text-xs text-muted-foreground">Skip to use the built-in HTML template.</p>
    </div>
  );
}

function WhatsAppStep() {
  const connect = useConnectIntegration();
  const [token, setToken] = useState("");
  const [phoneId, setPhoneId] = useState("");
  return (
    <div className="space-y-4">
      <Heading title="Connect WhatsApp (optional)" sub="Inbound messages → AI parses → drafts invoices for your approval. Skip to test with the simulator first." />
      <Field label="Phone number ID"><Input value={phoneId} onChange={(e) => setPhoneId(e.target.value)} /></Field>
      <Field label="Access token"><Input value={token} onChange={(e) => setToken(e.target.value)} type="password" /></Field>
      <div className="flex gap-2">
        <Button onClick={() => connect.mutate({
          provider: "whatsapp",
          config:  { provider: "meta_cloud", phone_number_id: phoneId },
          secrets: { access_token: token },
        }, { onSuccess: () => toast.success("WhatsApp connected") })} disabled={connect.isPending || !phoneId || !token}>
          {connect.isPending ? "Connecting…" : "Connect"}
        </Button>
      </div>
      <p className="text-xs text-muted-foreground">You can also choose Twilio later in <code className="font-mono">/integrations</code>.</p>
    </div>
  );
}

function FirstInvoiceStep() {
  const sim = useSimulateWhatsApp();
  const [text, setText] = useState("Create invoice for TOO ABC for 250000 KZT");
  return (
    <div className="space-y-4">
      <Heading title="Try your first AI-driven invoice" sub="The simulator runs the same path a real WhatsApp message would." />
      <Field label="Message"><Input value={text} onChange={(e) => setText(e.target.value)} /></Field>
      <Button onClick={() => sim.mutate({ text }, {
        onSuccess: () => toast.success("Draft created", "Check Approvals → Approve to finish"),
      })} disabled={sim.isPending}>
        {sim.isPending ? "Sending…" : "Run"}
      </Button>
    </div>
  );
}

function TeamStep() {
  const [email, setEmail] = useState("");
  return (
    <div className="space-y-4">
      <Heading title="Invite a teammate (optional)" sub="Multi-user invites land in the next milestone — for now, share access via shared org credentials." />
      <Field label="Email"><Input value={email} onChange={(e) => setEmail(e.target.value)} type="email" /></Field>
      <Button variant="outline" disabled>Coming soon</Button>
      <Badge tone="info" className="block w-fit">You can finish onboarding now and invite later.</Badge>
    </div>
  );
}

function Heading({ title, sub }: { title: string; sub: string }) {
  return (
    <div>
      <h2 className="text-base font-semibold">{title}</h2>
      <p className="text-sm text-muted-foreground mt-1">{sub}</p>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="mb-1 block text-xs text-muted-foreground">{label}</label>
      {children}
    </div>
  );
}
