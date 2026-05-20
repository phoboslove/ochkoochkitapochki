"use client";

import { useState } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useTemplates, useUploadDocxTemplate } from "@/lib/hooks";
import { toast } from "@/components/Toaster";
import { Upload, FileType2 } from "lucide-react";

const PLACEHOLDERS = [
  "{{ invoice.number }}",
  "{{ invoice.issue_date }}",
  "{{ invoice.total | money }} {{ invoice.currency }}",
  "{{ company.name }}, BIN {{ company.bin }}",
  "{{ client.name }}, BIN {{ client.bin }}",
  "{% for it in invoice.items %} … {% endfor %}",
];

export function TemplateManager() {
  const { data: templates = [] } = useTemplates("invoice");
  const upload = useUploadDocxTemplate();
  const [name, setName] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [isDefault, setIsDefault] = useState(false);

  const submit = () => {
    if (!file || !name.trim()) { toast.warn("Pick a file and a name"); return; }
    upload.mutate(
      { file, name, kind: "invoice", is_default: isDefault },
      {
        onSuccess: () => { toast.success("Template uploaded", name); setFile(null); setName(""); },
        onError:   (e) => toast.error("Upload failed", (e as Error).message),
      },
    );
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Invoice templates</CardTitle>
        <Link href="/settings/templates" className="text-[11px] text-muted-foreground hover:text-foreground">
          Full library →
        </Link>
      </CardHeader>
      <CardContent className="space-y-5">
        <ul className="divide-y border rounded">
          {templates.length === 0 && (
            <li className="p-3 text-xs text-muted-foreground">No custom templates — using built-in HTML default.</li>
          )}
          {templates.map((t) => (
            <li key={t.id} className="flex items-center gap-3 p-3">
              <FileType2 className="h-4 w-4 text-muted-foreground" />
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium truncate">{t.name}</div>
                <div className="text-xs text-muted-foreground uppercase tracking-wide">{t.format}</div>
              </div>
              {t.is_default && <Badge tone="success">default</Badge>}
            </li>
          ))}
        </ul>

        <div className="space-y-2">
          <div className="text-sm font-medium">Upload DOCX template</div>
          <div className="grid grid-cols-1 sm:grid-cols-[1fr_auto] gap-2">
            <Input placeholder="Template name (e.g. KZ standard invoice)"
                   value={name} onChange={(e) => setName(e.target.value)} />
            <label className="inline-flex items-center justify-center gap-2 rounded-md border bg-background px-3 h-9 text-sm cursor-pointer hover:bg-accent">
              <Upload className="h-3.5 w-3.5" />
              {file ? file.name : "Choose .docx"}
              <input type="file" accept=".docx" className="hidden"
                     onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
            </label>
          </div>
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            <input type="checkbox" checked={isDefault} onChange={(e) => setIsDefault(e.target.checked)} />
            Make default for this kind
          </label>
          <Button size="sm" onClick={submit} disabled={upload.isPending || !file}>
            {upload.isPending ? "Uploading…" : "Upload template"}
          </Button>
        </div>

        <details className="text-xs">
          <summary className="cursor-pointer text-muted-foreground">Available placeholders</summary>
          <ul className="mt-2 space-y-1 font-mono">
            {PLACEHOLDERS.map((p) => <li key={p} className="text-muted-foreground">{p}</li>)}
          </ul>
        </details>
      </CardContent>
    </Card>
  );
}
