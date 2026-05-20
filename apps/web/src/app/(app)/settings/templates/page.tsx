"use client";

import Link from "next/link";
import { useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Table, THead, TR, TH, TD, SkeletonRow } from "@/components/ui/table";
import { EmptyState } from "@/components/EmptyState";
import {
  useTemplatesLib, useUploadTemplate, useIndustryPacks,
  useConverterStatus, useConvertAllLegacy, useSummarizeAll,
} from "@/lib/templates";
import { toast } from "@/components/Toaster";
import {
  FileType2, Upload, ArrowRight, Star, AlertTriangle, RefreshCcw, Filter,
} from "lucide-react";
import { cn } from "@/lib/utils";

const KIND_OPTIONS = ["", "invoice", "act", "nakladnaya", "contract", "proposal"] as const;

export default function TemplatesLibraryPage() {
  const [industry, setIndustry] = useState<string>("");
  const [kind, setKind] = useState<string>("");
  const { data = [], isLoading } = useTemplatesLib({ kind: kind || undefined, industry: industry || undefined });
  const { data: packs } = useIndustryPacks();
  const { data: converter } = useConverterStatus();
  const convertAll = useConvertAllLegacy();
  const summarizeAll = useSummarizeAll();
  const upload = useUploadTemplate();
  const [name, setName] = useState("");
  const [uploadKind, setUploadKind] = useState("");
  const [file, setFile] = useState<File | null>(null);

  const submit = () => {
    if (!file) { toast.warn("Pick a file first"); return; }
    upload.mutate(
      { file, name: name || file.name, kind: uploadKind, is_default: false },
      {
        onSuccess: () => { toast.success("Template ingested", "Analyzing now…"); setFile(null); setName(""); },
        onError:   (e) => toast.error("Upload failed", (e as Error).message),
      },
    );
  };

  const legacyCount = data.filter((t) => t.format === "doc" || t.format === "xls").length;

  return (
    <>
      <PageHeader
        eyebrow="Business · Templates"
        title="Document library"
        description="Real DOCX / XLSX / PDF / RTF templates with deterministic analysis, semantic mapping suggestions, validation and conversion."
        actions={
          <div className="flex flex-wrap gap-2">
            <Link href="/settings/templates/audit">
              <Button size="sm" variant="outline">Corpus audit</Button>
            </Link>
            <Button size="sm" variant="outline" disabled={summarizeAll.isPending}
              onClick={() => summarizeAll.mutate(undefined, {
                onSuccess: (r) => toast.success("AI summarization done", `${r.summarized} processed, ${r.remaining} remaining`),
              })}>
              {summarizeAll.isPending ? "Summarizing…" : "AI summarize batch"}
            </Button>
            {legacyCount > 0 && converter?.available ? (
              <Button size="sm"
                onClick={() => convertAll.mutate(undefined, {
                  onSuccess: (r) => toast.success("Conversion finished", `${r.converted}/${r.total} converted, ${r.failed} failed`),
                  onError:   (e) => toast.error("Convert all failed", (e as Error).message),
                })}
                disabled={convertAll.isPending}>
                <RefreshCcw className={cn("h-3.5 w-3.5", convertAll.isPending && "animate-spin")} />
                {convertAll.isPending ? "Converting…" : `Convert ${legacyCount} legacy`}
              </Button>
            ) : null}
          </div>
        }
      />

      {legacyCount > 0 && !converter?.available && (
        <Card className="mb-5 border-l-[3px] border-l-[hsl(var(--warning))]">
          <CardContent className="p-3.5 flex items-start gap-2 text-[12.5px]">
            <AlertTriangle className="h-4 w-4 text-[hsl(var(--warning))] mt-0.5" />
            <div>
              <b>LibreOffice not detected</b> — install it to enable automatic conversion of {legacyCount} legacy file(s).
              <a href="https://www.libreoffice.org/download/" target="_blank" rel="noreferrer" className="underline underline-offset-2 ml-1">
                Download →
              </a>
            </div>
          </CardContent>
        </Card>
      )}

      <Card className="mb-5">
        <CardContent className="p-5 space-y-3">
          <div className="text-[13px] font-medium">Upload template</div>
          <div className="grid grid-cols-1 sm:grid-cols-[1fr_180px_auto_auto] gap-2 items-stretch">
            <Input value={name} onChange={(e) => setName(e.target.value)}
                   placeholder="Name (auto from filename if empty)" />
            <select className="h-8 rounded-md border border-input bg-card px-3 text-[13px]"
                    value={uploadKind} onChange={(e) => setUploadKind(e.target.value)}>
              <option value="">auto-detect kind</option>
              {KIND_OPTIONS.slice(1).map((k) => <option key={k} value={k}>{k}</option>)}
            </select>
            <label className="inline-flex items-center justify-center gap-2 rounded-md border border-input bg-card h-8 px-3 text-[13px] cursor-pointer hover:bg-accent">
              <Upload className="h-3.5 w-3.5" />
              {file ? file.name.slice(0, 24) : ".docx / .xlsx / .pdf / .rtf"}
              <input type="file" accept=".docx,.xlsx,.pdf,.rtf,.doc,.xls" className="hidden"
                     onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
            </label>
            <Button onClick={submit} disabled={upload.isPending || !file}>
              {upload.isPending ? "Uploading…" : "Upload & analyze"}
            </Button>
          </div>
        </CardContent>
      </Card>

      <div className="mb-3 flex items-center gap-1.5 flex-wrap">
        <Filter className="h-3.5 w-3.5 text-muted-foreground mr-1" />
        <Chip active={industry === ""} onClick={() => setIndustry("")}>
          All <span className="text-muted-foreground ml-1 tabular-nums">{data.length}</span>
        </Chip>
        {packs?.packs.map((p) => (
          <Chip key={p.industry} active={industry === p.industry} onClick={() => setIndustry(p.industry)}>
            {p.industry} <span className="text-muted-foreground ml-1 tabular-nums">{p.count}</span>
          </Chip>
        ))}
        <span className="mx-2 h-3.5 w-px bg-border" />
        <Chip active={kind === ""} onClick={() => setKind("")}>any kind</Chip>
        {KIND_OPTIONS.slice(1).map((k) => (
          <Chip key={k} active={kind === k} onClick={() => setKind(k)}>{k}</Chip>
        ))}
      </div>

      <Card>
        <CardContent className="p-0 overflow-x-auto">
          <Table>
            <THead><TR>
              <TH>Template</TH><TH>Kind</TH><TH>Industry</TH><TH>Format</TH>
              <TH>Status</TH><TH>QA</TH><TH>Confidence</TH><TH>Default</TH><TH></TH>
            </TR></THead>
            <tbody>
              {isLoading && Array.from({ length: 4 }).map((_, i) => <SkeletonRow key={i} cols={9} />)}
              {!isLoading && data.length === 0 && (
                <TR><TD colSpan={9} className="py-0">
                  <EmptyState
                    icon={FileType2}
                    title="No templates in this filter"
                    description="Try a different industry/kind, or upload a new file."
                    className="border-0"
                  />
                </TD></TR>
              )}
              {data.map((t) => {
                const legacy = t.format === "doc" || t.format === "xls";
                return (
                  <TR key={t.id}>
                    <TD>
                      <Link href={`/settings/templates/${t.id}`} className="font-medium hover:underline">
                        {t.name}
                      </Link>
                      {t.original_filename && (
                        <div className="text-[11px] text-muted-foreground truncate max-w-[280px]">
                          {t.original_filename} · v{t.version}
                        </div>
                      )}
                    </TD>
                    <TD className="text-muted-foreground uppercase text-[11px]">{t.kind}</TD>
                    <TD className="text-muted-foreground capitalize text-[11.5px]">{t.industry ?? "—"}</TD>
                    <TD><FormatBadge format={t.format} /></TD>
                    <TD><StatusBadge status={t.status} /></TD>
                    <TD>
                      {t.validation_score == null
                        ? <span className="text-muted-foreground text-[11.5px]">—</span>
                        : <ScoreBadge score={t.validation_score} warnings={t.validation_warnings.length} />}
                    </TD>
                    <TD>
                      {t.confidence != null
                        ? <span className="tabular-nums text-[12px]">{Math.round(t.confidence * 100)}%</span>
                        : <span className="text-muted-foreground">—</span>}
                    </TD>
                    <TD>{t.is_default ? <Badge tone="brand"><Star className="h-3 w-3" /> default</Badge> : "—"}</TD>
                    <TD className="text-right">
                      <Link href={`/settings/templates/${t.id}`}>
                        <Button variant="ghost" size="sm">
                          {legacy ? "Convert" : "Open"} <ArrowRight className="h-3.5 w-3.5" />
                        </Button>
                      </Link>
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

function Chip({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[11px] transition-all",
        active ? "border-[hsl(var(--brand))] bg-[hsl(var(--brand-subtle))] text-foreground"
               : "border-border bg-card text-muted-foreground hover:bg-accent hover:text-foreground",
      )}>
      {children}
    </button>
  );
}

function StatusBadge({ status }: { status: string }) {
  const tone: any = status === "VERIFIED" ? "success"
               : status === "MAPPED"   ? "info"
               : status === "FAILED"   ? "danger"
               : status === "ARCHIVED" ? "neutral"
               : "warn";
  return <Badge tone={tone}>{status.toLowerCase()}</Badge>;
}

function FormatBadge({ format }: { format: string }) {
  const legacy = format === "doc" || format === "xls";
  return (
    <Badge tone={legacy ? "warn" : format === "docx" ? "info" : format === "xlsx" ? "success" : "neutral"}>
      {format}{legacy && " · legacy"}
    </Badge>
  );
}

function ScoreBadge({ score, warnings }: { score: number; warnings: number }) {
  const tone: any = score >= 90 ? "success" : score >= 70 ? "info" : score >= 40 ? "warn" : "danger";
  return (
    <Badge tone={tone}>
      <span className="tabular-nums">{score}</span>
      {warnings > 0 && <span className="opacity-70 ml-1">({warnings} ⚠)</span>}
    </Badge>
  );
}
