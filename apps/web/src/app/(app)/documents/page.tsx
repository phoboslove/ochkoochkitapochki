"use client";

import Link from "next/link";
import { useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, THead, TR, TH, TD } from "@/components/ui/table";
import { Dropzone } from "@/components/Dropzone";
import { useDocuments, useUploadDocument } from "@/lib/hooks";
import { toast } from "@/components/Toaster";
import { CheckCircle2, AlertCircle, Loader2 } from "lucide-react";

type QueueItem = { key: string; name: string; size: number; progress: number; status: "uploading" | "done" | "error"; error?: string };

const tone = (s: string) =>
  s === "PARSED" ? "success" : s === "OCR_DONE" ? "info" : s === "FAILED" ? "danger" : "warn";

export default function DocumentsPage() {
  const { data = [], isLoading } = useDocuments();
  const upload = useUploadDocument();
  const [queue, setQueue] = useState<QueueItem[]>([]);

  const onFiles = (files: File[]) => {
    files.forEach((file) => {
      const key = `${file.name}-${file.size}-${Date.now()}`;
      setQueue((q) => [...q, { key, name: file.name, size: file.size, progress: 0, status: "uploading" }]);
      upload.mutate(
        { file, onProgress: (p) => setQueue((q) => q.map((it) => it.key === key ? { ...it, progress: p } : it)) },
        {
          onSuccess: () => {
            setQueue((q) => q.map((it) => it.key === key ? { ...it, status: "done", progress: 100 } : it));
            toast.success("Uploaded", file.name);
            window.setTimeout(() => setQueue((q) => q.filter((it) => it.key !== key)), 2500);
          },
          onError: (e) => {
            const msg = (e as Error).message;
            setQueue((q) => q.map((it) => it.key === key ? { ...it, status: "error", error: msg } : it));
            toast.error("Upload failed", file.name);
          },
        },
      );
    });
  };

  return (
    <>
      <PageHeader title="Documents" description="Upload, OCR, parse, generate, search." />
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
        <div className="lg:col-span-2"><Dropzone onFiles={onFiles} /></div>
        <Card>
          <CardContent className="p-5">
            <div className="text-sm font-medium mb-2">Upload queue</div>
            {queue.length === 0 && <div className="text-xs text-muted-foreground">Idle.</div>}
            <ul className="space-y-3">
              {queue.map((it) => (
                <li key={it.key}>
                  <div className="flex items-center gap-2 text-xs">
                    {it.status === "uploading" && <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />}
                    {it.status === "done"      && <CheckCircle2 className="h-3 w-3 text-[hsl(var(--success))]" />}
                    {it.status === "error"     && <AlertCircle className="h-3 w-3 text-[hsl(var(--danger))]" />}
                    <span className="truncate flex-1">{it.name}</span>
                    <span className="tabular-nums">{it.status === "error" ? "failed" : `${it.progress}%`}</span>
                  </div>
                  <div className="mt-1 h-1.5 bg-muted rounded overflow-hidden">
                    <div
                      className={"h-full " + (it.status === "error" ? "bg-[hsl(var(--danger))]" : it.status === "done" ? "bg-[hsl(var(--success))]" : "bg-primary")}
                      style={{ width: `${it.progress}%` }}
                    />
                  </div>
                  {it.error && <div className="mt-1 text-[11px] text-[hsl(var(--danger))]">{it.error}</div>}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardContent className="p-0 overflow-x-auto">
          <Table>
            <THead><TR><TH>Title</TH><TH>Type</TH><TH>Status</TH><TH>Size</TH><TH></TH></TR></THead>
            <tbody>
              {isLoading && <TR><TD colSpan={5} className="text-center text-muted-foreground py-8">Loading…</TD></TR>}
              {!isLoading && data.length === 0 && (
                <TR><TD colSpan={5} className="text-center text-muted-foreground py-8">
                  No documents yet — upload above.
                </TD></TR>
              )}
              {data.map((d) => (
                <TR key={d.id}>
                  <TD className="font-medium">{d.title}</TD>
                  <TD className="text-muted-foreground">{d.type}</TD>
                  <TD><Badge tone={tone(d.status) as any}>{d.status}</Badge></TD>
                  <TD className="text-muted-foreground">{(d.size / 1024).toFixed(1)} KB</TD>
                  <TD className="text-right">
                    <Link href={`/documents/${d.id}`}><Button variant="ghost" size="sm">Open</Button></Link>
                  </TD>
                </TR>
              ))}
            </tbody>
          </Table>
        </CardContent>
      </Card>
    </>
  );
}
