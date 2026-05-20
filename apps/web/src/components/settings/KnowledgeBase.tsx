"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Trash2, BookOpen, Plus } from "lucide-react";
import { useDeleteKnowledge, useKnowledge, useUpsertKnowledge } from "@/lib/settings";
import { toast } from "@/components/Toaster";

export function KnowledgeBase() {
  const { data = [] } = useKnowledge();
  const upsert = useUpsertKnowledge();
  const del = useDeleteKnowledge();
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [tags, setTags] = useState("");

  const submit = () => {
    if (!title.trim()) { toast.warn("Title required"); return; }
    upsert.mutate(
      { title, body, tags: tags.split(",").map((s) => s.trim()).filter(Boolean) },
      {
        onSuccess: () => { toast.success("Knowledge added"); setTitle(""); setBody(""); setTags(""); },
        onError:   (e) => toast.error("Save failed", (e as Error).message),
      },
    );
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <BookOpen className="h-4 w-4 text-muted-foreground" />
          Knowledge base
          <Badge tone="info" className="ml-auto">{data.length} {data.length === 1 ? "doc" : "docs"}</Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        <p className="text-xs text-muted-foreground">
          Policies, instructions, contract clauses. The AI assistant retrieves these
          automatically when relevant to the user's question.
        </p>

        <div className="rounded-md border p-3 space-y-2 bg-muted/30">
          <div className="text-sm font-medium">Add entry</div>
          <Input placeholder="Title (e.g. Late-payment policy)" value={title}
                 onChange={(e) => setTitle(e.target.value)} />
          <textarea className="w-full min-h-[100px] rounded-md border bg-background p-2 text-sm"
                    placeholder="Markdown / plain text"
                    value={body} onChange={(e) => setBody(e.target.value)} />
          <div className="flex gap-2 items-center">
            <Input placeholder="tags, comma, separated" value={tags}
                   onChange={(e) => setTags(e.target.value)} />
            <Button size="sm" onClick={submit} disabled={upsert.isPending}>
              <Plus className="h-3.5 w-3.5" /> Add
            </Button>
          </div>
        </div>

        <ul className="divide-y border rounded-md">
          {data.length === 0 && (
            <li className="p-4 text-center text-sm text-muted-foreground">
              No knowledge yet — add a policy above.
            </li>
          )}
          {data.map((d) => (
            <li key={d.id} className="flex items-start gap-3 p-3">
              <BookOpen className="h-4 w-4 text-muted-foreground mt-0.5 shrink-0" />
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium truncate">{d.title}</div>
                <div className="text-[11px] text-muted-foreground flex flex-wrap gap-2 mt-0.5">
                  {(d.tags ?? []).map((t: string) =>
                    <span key={t} className="px-1.5 rounded bg-muted">{t}</span>,
                  )}
                  <span>{new Date(d.created_at).toLocaleDateString()}</span>
                  {d.mime && <span>{d.mime}</span>}
                </div>
              </div>
              <Button variant="ghost" size="icon"
                onClick={() => del.mutate(d.id, { onSuccess: () => toast.success("Removed") })}>
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
