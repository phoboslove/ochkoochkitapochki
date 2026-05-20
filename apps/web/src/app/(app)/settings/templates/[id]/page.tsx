"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge, StatusDot } from "@/components/ui/badge";
import { api } from "@/lib/api";
import {
  useTemplate, useTemplateRegistry, useTemplateVersions,
  useRenderPreview, usePatchMappings, useTemplateActions,
  useConvertTemplate, useValidateTemplate, useConverterStatus,
  useSummarizeTemplate, useUpdateTagging,
  type TemplateDetail,
} from "@/lib/templates";
import { toast } from "@/components/Toaster";
import { ArrowLeft, Check, FileType2, History, PlayCircle, Star, Archive, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";

export default function TemplateMappingPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const { data: tpl } = useTemplate(id);
  const { data: registry } = useTemplateRegistry();
  const { data: versions = [] } = useTemplateVersions(id);
  const patch = usePatchMappings(id);
  const render = useRenderPreview(id);
  const actions = useTemplateActions(id);
  const convert = useConvertTemplate(id);
  const validate = useValidateTemplate(id);
  const { data: converter } = useConverterStatus();
  const summarize = useSummarizeTemplate(id);
  const tagging   = useUpdateTagging(id);

  const [draft, setDraft] = useState<TemplateDetail["mappings"]>({});
  useEffect(() => { if (tpl) setDraft({ ...tpl.mappings }); }, [tpl?.id]); // eslint-disable-line

  const allCanonical = registry?.fields ?? [];
  const grouped = useMemo(() => {
    const map = new Map<string, typeof allCanonical>();
    for (const f of allCanonical) { (map.get(f.group) ?? map.set(f.group, []).get(f.group)!).push(f); }
    return map;
  }, [allCanonical]);

  const sourceOptions = useMemo(() => {
    if (!tpl) return [];
    const labels = new Set<string>();
    (tpl.detected_fields?.paragraphs ?? []).forEach((p) => labels.add(p));
    (tpl.detected_tables ?? []).forEach((t) => t.headers.forEach((h) => h && labels.add(h)));
    (tpl.detected_fields?.placeholders ?? []).forEach((p) => labels.add(`{{${p}}}`));
    return Array.from(labels).slice(0, 200);
  }, [tpl]);

  if (!tpl) return <div className="text-muted-foreground text-sm">Loading…</div>;

  const update = (key: string, patch: Partial<TemplateDetail["mappings"][string]>) =>
    setDraft((d) => ({ ...d, [key]: { ...d[key], ...patch } as any }));

  const save = () =>
    patch.mutate({ mappings: draft }, {
      onSuccess: () => toast.success("Mappings saved", "Status updated"),
      onError:   (e) => toast.error("Save failed", (e as Error).message),
    });

  const confirmAll = () =>
    patch.mutate({ mappings: draft, confirm_all: true }, {
      onSuccess: () => toast.success("All confirmed"),
    });

  const renderNow = () =>
    render.mutate(undefined, {
      onSuccess: (r) => {
        toast.success("Preview rendered", `${(r.bytes / 1024).toFixed(1)} KB · ${r.ext}`);
        window.open(api.fileUrl(r.preview_url), "_blank");
      },
      onError: (e) => toast.error("Render failed", (e as Error).message),
    });

  return (
    <>
      <Link href="/settings/templates"
            className="inline-flex items-center gap-1 text-[12px] text-muted-foreground hover:text-foreground mb-4">
        <ArrowLeft className="h-3.5 w-3.5" /> Templates
      </Link>

      <PageHeader
        eyebrow={`Template · v${tpl.version}`}
        title={tpl.name}
        description={`${tpl.format.toUpperCase()} · kind: ${tpl.kind} · language: ${tpl.language ?? "—"}`}
        actions={
          <div className="flex flex-wrap gap-2 items-center">
            <Badge tone={tpl.status === "VERIFIED" ? "success" : tpl.status === "FAILED" ? "danger" : "warn"}>
              {tpl.status.toLowerCase()}
            </Badge>
            {(tpl.format === "doc" || tpl.format === "xls") && (
              <Button size="sm" disabled={convert.isPending || !converter?.available}
                onClick={() => convert.mutate(undefined, {
                  onSuccess: () => toast.success("Converted", "Open the new template from the library."),
                  onError:   (e) => toast.error("Convert failed", (e as Error).message),
                })}
                title={converter?.available ? "" : "LibreOffice not installed"}>
                {convert.isPending ? "Converting…" : `Convert → ${tpl.format === "doc" ? "DOCX" : "XLSX"}`}
              </Button>
            )}
            <Button variant="outline" size="sm" disabled={summarize.isPending}
              onClick={() => summarize.mutate(undefined, {
                onSuccess: (r) => toast.success("AI summary refreshed", `${(r.semantic?.tags ?? []).slice(0,4).join(", ")}`),
              })}>
              {summarize.isPending ? "Summarizing…" : "AI summarize"}
            </Button>
            <Button variant="outline" size="sm" disabled={validate.isPending}
              onClick={() => validate.mutate(undefined, {
                onSuccess: (r) => toast.success(`QA: ${r.qa_status}`,
                  `Score ${r.score} · ${r.warnings.length} warning(s)`),
              })}>
              {validate.isPending ? "Validating…" : "Validate"}
            </Button>
            <Button variant="outline" size="sm" onClick={renderNow} disabled={render.isPending}>
              <PlayCircle className="h-3.5 w-3.5" /> {render.isPending ? "Rendering…" : "Render preview"}
            </Button>
            {!tpl.is_default && (
              <Button variant="outline" size="sm"
                onClick={() => actions.makeDefault.mutate(undefined, { onSuccess: () => toast.success("Set as default") })}>
                <Star className="h-3.5 w-3.5" /> Make default
              </Button>
            )}
            <Button variant="ghost" size="sm"
              onClick={() => actions.archive.mutate(undefined, { onSuccess: () => toast.success("Archived") })}>
              <Archive className="h-3.5 w-3.5" /> Archive
            </Button>
          </div>
        }
      />

      {tpl.last_error && (
        <Card className="mb-4 border-l-[3px] border-l-[hsl(var(--danger))]">
          <CardContent className="p-3.5 flex items-start gap-2 text-[12.5px]">
            <AlertTriangle className="h-4 w-4 text-[hsl(var(--danger))] mt-0.5" />
            <div><b>Last error:</b> <span className="font-mono">{tpl.last_error}</span></div>
          </CardContent>
        </Card>
      )}

      <SemanticPanel tpl={tpl} onSave={(p) => tagging.mutate(p, { onSuccess: () => toast.success("Tagging saved") })}
                     saving={tagging.isPending} />

      {(tpl.validation_warnings ?? []).length > 0 && (
        <Card className="mb-4">
          <CardContent className="p-4">
            <div className="flex items-center gap-3 mb-3">
              <span className="text-[10.5px] uppercase tracking-wider text-muted-foreground">Validation</span>
              {tpl.validation_score != null && (
                <Badge tone={tpl.validation_score >= 90 ? "success" : tpl.validation_score >= 70 ? "info" : tpl.validation_score >= 40 ? "warn" : "danger"}>
                  Score <span className="tabular-nums ml-1">{tpl.validation_score}</span>
                </Badge>
              )}
              <span className="text-[11px] text-muted-foreground">{tpl.validation_warnings!.length} issue(s)</span>
            </div>
            <ul className="space-y-1.5">
              {tpl.validation_warnings!.map((w, i) => (
                <li key={i} className="flex items-start gap-2 text-[12.5px]">
                  <span className={cn(
                    "mt-0.5 h-1.5 w-1.5 rounded-full",
                    w.severity === "critical" ? "bg-[hsl(var(--danger))]" :
                    w.severity === "high"     ? "bg-[hsl(var(--danger))]" :
                    w.severity === "warn"     ? "bg-[hsl(var(--warning))]" :
                                                 "bg-[hsl(var(--info))]",
                  )} />
                  <div className="flex-1">
                    <div>{w.message}</div>
                    {w.fix && <div className="text-[11px] text-muted-foreground">→ {w.fix}</div>}
                  </div>
                  <span className="text-[10px] text-muted-foreground font-mono uppercase">{w.code}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_420px] gap-6">
        {/* ── LEFT: detected content + analysis ── */}
        <Card>
          <CardHeader><CardTitle>Detected content</CardTitle></CardHeader>
          <CardContent className="pt-0 space-y-5">
            {/* Tables */}
            {(tpl.detected_tables ?? []).length > 0 && (
              <section>
                <SectionLabel>Tables ({(tpl.detected_tables ?? []).length})</SectionLabel>
                <div className="space-y-2">
                  {tpl.detected_tables.map((t, i) => (
                    <div key={i} className="rounded-md border border-border bg-surface-2 p-3">
                      <div className="flex items-center justify-between mb-2">
                        <div className="text-[12px] text-muted-foreground">
                          {t.sheet ? `Sheet: ${t.sheet}` : "Document table"}
                        </div>
                        {t.is_repeating && <Badge tone="info">repeating rows</Badge>}
                      </div>
                      <div className="overflow-x-auto">
                        <table className="text-[11.5px] min-w-full">
                          <thead className="text-[10px] text-muted-foreground uppercase">
                            <tr>{t.headers.map((h, j) => <th key={j} className="text-left pr-3 py-1 font-medium">{h || "—"}</th>)}</tr>
                          </thead>
                          <tbody>
                            {t.rows_preview.map((row, ri) => (
                              <tr key={ri} className="text-foreground/80">
                                {row.map((c, ci) => <td key={ci} className="pr-3 py-0.5 truncate max-w-[180px]">{c}</td>)}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* Placeholders already in the file */}
            {(tpl.detected_fields?.placeholders ?? []).length > 0 && (
              <section>
                <SectionLabel>Existing placeholders</SectionLabel>
                <div className="flex flex-wrap gap-1.5">
                  {tpl.detected_fields!.placeholders!.map((p) => (
                    <code key={p} className="px-1.5 py-0.5 text-[11px] rounded bg-muted border border-border font-mono">
                      {`{{${p}}}`}
                    </code>
                  ))}
                </div>
              </section>
            )}

            {/* Paragraphs */}
            <section>
              <SectionLabel>Extracted text ({(tpl.detected_fields?.paragraphs ?? []).length})</SectionLabel>
              <div className="max-h-72 overflow-y-auto rounded-md border border-border bg-surface-2 p-3 text-[12px] leading-relaxed space-y-1">
                {(tpl.detected_fields?.paragraphs ?? []).slice(0, 80).map((p, i) => (
                  <div key={i} className="text-foreground/85">{p}</div>
                ))}
                {(tpl.detected_fields?.paragraphs ?? []).length === 0 &&
                  <div className="text-muted-foreground">No text extracted.</div>}
              </div>
            </section>

            {(tpl.detected_fields?.notes ?? []).length > 0 && (
              <div className="text-[11px] text-muted-foreground">
                <b>Notes:</b> {tpl.detected_fields!.notes!.join(" · ")}
              </div>
            )}
          </CardContent>
        </Card>

        {/* ── RIGHT: mapping panel ── */}
        <div className="space-y-5">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>Field mappings</CardTitle>
              <div className="flex gap-1.5">
                <Button size="sm" variant="ghost" onClick={confirmAll}>Confirm all</Button>
                <Button size="sm" onClick={save} disabled={patch.isPending}>
                  {patch.isPending ? "Saving…" : "Save"}
                </Button>
              </div>
            </CardHeader>
            <CardContent className="pt-0 space-y-5">
              {(registry?.groups ?? []).map((g) => {
                const fields = grouped.get(g) ?? [];
                if (fields.length === 0) return null;
                return (
                  <section key={g}>
                    <SectionLabel>{g}</SectionLabel>
                    <ul className="space-y-1.5">
                      {fields.map((f) => {
                        const m = draft[f.key];
                        const tone = !m ? "neutral" : m.confirmed ? "success"
                                     : m.confidence >= 0.85 ? "info"
                                     : m.confidence >= 0.6  ? "warn" : "neutral";
                        return (
                          <li key={f.key} className="rounded-md border border-border bg-card p-2.5">
                            <div className="flex items-center gap-2 mb-1">
                              <StatusDot tone={tone as any} />
                              <span className="text-[12.5px] font-medium">{f.label}</span>
                              <code className="text-[10.5px] text-muted-foreground font-mono">{`{{${f.key}}}`}</code>
                              {m && <span className="ml-auto text-[10.5px] tabular-nums text-muted-foreground">
                                {Math.round((m.confidence ?? 0) * 100)}%
                              </span>}
                            </div>
                            <div className="grid grid-cols-[1fr_auto] gap-1.5 items-center">
                              <select
                                className={cn(
                                  "h-7 w-full rounded-md border bg-card px-2 text-[11.5px]",
                                  m?.confirmed ? "border-[hsl(var(--success)/0.4)]" : "border-input",
                                )}
                                value={m?.source_label ?? ""}
                                onChange={(e) => update(f.key, {
                                  source_label: e.target.value,
                                  source_kind: "manual",
                                  confidence: 1.0,
                                  confirmed: !!e.target.value,
                                })}
                              >
                                <option value="">— not mapped —</option>
                                {sourceOptions.map((s) => <option key={s} value={s}>{s.length > 50 ? s.slice(0, 50) + "…" : s}</option>)}
                              </select>
                              <button
                                disabled={!m?.source_label}
                                onClick={() => update(f.key, { confirmed: !m?.confirmed })}
                                className={cn(
                                  "h-7 px-2 rounded-md border text-[11px] transition-colors",
                                  m?.confirmed
                                    ? "border-[hsl(var(--success)/0.4)] bg-success-bg text-[hsl(var(--success))]"
                                    : "border-border bg-card text-muted-foreground hover:bg-accent",
                                )}
                                title={m?.confirmed ? "Confirmed" : "Confirm mapping"}
                              >
                                <Check className="h-3 w-3" />
                              </button>
                            </div>
                          </li>
                        );
                      })}
                    </ul>
                  </section>
                );
              })}
            </CardContent>
          </Card>

          {versions.length > 0 && (
            <Card>
              <CardHeader><CardTitle><History className="inline h-3.5 w-3.5 mr-1" /> Versions</CardTitle></CardHeader>
              <CardContent className="pt-0 space-y-1.5">
                {versions.map((v) => (
                  <Link key={v.id} href={`/settings/templates/${v.id}`}
                        className={cn(
                          "flex items-center gap-2 rounded-md px-2 py-1.5 text-[12.5px] transition-colors",
                          v.id === id ? "bg-accent" : "hover:bg-accent/60",
                        )}>
                    <FileType2 className="h-3.5 w-3.5 text-muted-foreground" />
                    <span>v{v.version}</span>
                    {v.is_default && <Badge tone="brand">default</Badge>}
                    <span className="text-[11px] text-muted-foreground ml-auto">{v.status.toLowerCase()}</span>
                  </Link>
                ))}
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return <div className="text-[10.5px] uppercase tracking-wider text-muted-foreground mb-2">{children}</div>;
}

function SemanticPanel({ tpl, onSave, saving }: {
  tpl: any; saving: boolean;
  onSave: (p: { tags?: string[]; use_case?: string; summary?: string; business_purpose?: string }) => void;
}) {
  const sem = (tpl.detected_fields?.semantic) ?? {};
  const [tagsInput, setTagsInput] = useState<string>((sem.tags ?? []).join(", "));
  const [useCase, setUseCase] = useState<string>(sem.use_case ?? "");
  const [editing, setEditing] = useState(false);

  useEffect(() => {
    setTagsInput((sem.tags ?? []).join(", "));
    setUseCase(sem.use_case ?? "");
  }, [tpl.id, sem.tags?.length]); // eslint-disable-line

  const hasSemantic = sem.model || sem.summary || (sem.tags ?? []).length > 0;
  return (
    <Card className="mb-4">
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Semantic</CardTitle>
        <div className="flex items-center gap-2">
          {sem.model && <Badge tone={sem.model === "manual" ? "brand" : sem.model.startsWith("fallback") ? "warn" : "info"}>
            {sem.model === "manual" ? "manual" : sem.model.startsWith("fallback") ? "heuristic" : "ai"}
          </Badge>}
          <button onClick={() => setEditing((e) => !e)}
            className="text-[11px] text-muted-foreground hover:text-foreground">
            {editing ? "cancel" : "edit"}
          </button>
        </div>
      </CardHeader>
      <CardContent className="pt-0 space-y-3 text-[12.5px]">
        {!hasSemantic && (
          <div className="text-muted-foreground italic">
            Not summarized yet. Click "AI summarize" above to generate tags + summary.
          </div>
        )}
        {sem.summary && (
          <div>
            <div className="text-[10.5px] uppercase tracking-wider text-muted-foreground mb-0.5">Summary</div>
            <div>{sem.summary}</div>
          </div>
        )}
        {sem.business_purpose && (
          <div>
            <div className="text-[10.5px] uppercase tracking-wider text-muted-foreground mb-0.5">Business purpose</div>
            <div className="text-foreground/85">{sem.business_purpose}</div>
          </div>
        )}
        <div>
          <div className="text-[10.5px] uppercase tracking-wider text-muted-foreground mb-0.5">Use case</div>
          {editing ? (
            <input className="h-8 w-full rounded-md border border-input bg-card px-3 text-[12.5px]"
                   value={useCase} onChange={(e) => setUseCase(e.target.value)} />
          ) : (
            <div className="text-foreground/85">{sem.use_case || "—"}</div>
          )}
        </div>
        <div>
          <div className="text-[10.5px] uppercase tracking-wider text-muted-foreground mb-1">Tags</div>
          {editing ? (
            <input className="h-8 w-full rounded-md border border-input bg-card px-3 text-[12.5px]"
                   value={tagsInput} onChange={(e) => setTagsInput(e.target.value)}
                   placeholder="comma-separated, e.g. act, services, acceptance" />
          ) : (
            <div className="flex flex-wrap gap-1.5">
              {(sem.tags ?? []).map((t: string) => (
                <span key={t} className="rounded-md px-1.5 py-0.5 text-[11px] border border-border bg-muted">{t}</span>
              ))}
              {(sem.tags ?? []).length === 0 && <span className="text-muted-foreground">—</span>}
            </div>
          )}
        </div>
        {editing && (
          <div className="flex gap-2">
            <Button size="sm" disabled={saving}
              onClick={() => {
                const tags = tagsInput.split(",").map((s) => s.trim()).filter(Boolean);
                onSave({ tags, use_case: useCase });
                setEditing(false);
              }}>{saving ? "Saving…" : "Save"}</Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
