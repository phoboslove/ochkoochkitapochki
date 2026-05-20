"use client";

import { useParams } from "next/navigation";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useDocument, useUpdateDocumentFields, useRetryDocument } from "@/lib/hooks";
import { RefreshCw } from "lucide-react";
import { api } from "@/lib/api";
import { DocumentStatusTimeline } from "@/components/DocumentStatusTimeline";
import { EditableFields } from "@/components/EditableFields";
import { WorkflowTimeline } from "@/components/WorkflowTimeline";
import { toast } from "@/components/Toaster";

export default function DocumentDetailPage() {
  const params = useParams<{ id: string }>();
  const { data, isLoading } = useDocument(params.id);
  const update = useUpdateDocumentFields();
  const retry = useRetryDocument();

  if (isLoading || !data) return <div className="text-muted-foreground">Loading…</div>;

  const previewable = data.mime.startsWith("image/") || data.mime === "application/pdf" || data.mime === "text/html";

  return (
    <>
      <PageHeader
        title={data.title}
        description={`${data.type} · ${data.mime} · ${(data.size / 1024).toFixed(1)} KB`}
        actions={
          <div className="flex gap-2">
            {data.status === "FAILED" && (
              <Button variant="outline" disabled={retry.isPending}
                onClick={() => retry.mutate(data.id, {
                  onSuccess: () => toast.success("Retrying OCR + parse"),
                  onError:   (e) => toast.error("Retry failed", (e as Error).message),
                })}>
                <RefreshCw className="h-3.5 w-3.5" /> Retry
              </Button>
            )}
            {data.preview_url && (
              <a href={api.fileUrl(data.preview_url)} target="_blank" rel="noreferrer">
                <Button variant="outline">Open file</Button>
              </a>
            )}
          </div>
        }
      />

      <Card className="mb-6">
        <CardContent className="p-4 sm:p-5">
          <DocumentStatusTimeline status={data.status} />
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6 order-2 lg:order-1">
          {previewable && data.preview_url && (
            <Card><CardContent className="p-0">
              {data.mime.startsWith("image/")
                ? <img src={api.fileUrl(data.preview_url)} className="w-full" alt={data.title} />
                : <iframe src={api.fileUrl(data.preview_url)} className="w-full h-[60vh] sm:h-[70vh] border-0" />}
            </CardContent></Card>
          )}
          {data.ocr_text && (
            <Card>
              <CardHeader><CardTitle>OCR text</CardTitle></CardHeader>
              <CardContent><pre className="text-xs whitespace-pre-wrap max-h-72 overflow-y-auto">{data.ocr_text}</pre></CardContent>
            </Card>
          )}
          <WorkflowTimeline resource={data.id} title="Document timeline" />
        </div>

        <div className="space-y-6 order-1 lg:order-2">
          <Card>
            <CardHeader><CardTitle>Extracted fields</CardTitle></CardHeader>
            <CardContent>
              <EditableFields
                values={data.parsed ?? {}}
                onSave={async (patch) => {
                  try {
                    await update.mutateAsync({ id: data.id, parsed: patch });
                    toast.success("Saved", Object.keys(patch).join(", "));
                  } catch (e) { toast.error("Save failed", (e as Error).message); }
                }}
              />
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>Metadata</CardTitle></CardHeader>
            <CardContent className="text-xs space-y-1 text-muted-foreground">
              <div>Uploaded: {new Date(data.created_at).toLocaleString()}</div>
              {data.checksum && <div className="font-mono break-all">sha256: {data.checksum}</div>}
            </CardContent>
          </Card>
        </div>
      </div>
    </>
  );
}
