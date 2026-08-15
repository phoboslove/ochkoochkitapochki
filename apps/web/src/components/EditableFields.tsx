"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Pencil, Check, X } from "lucide-react";

// Nested objects/arrays (e.g. the `intent`/`template` blobs a generated
// document stores alongside its flat fields) aren't single-line-editable —
// coercing them with String() just produces the literal text "[object
// Object]". Render those as read-only pretty-printed JSON instead, and only
// offer inline editing for primitive-valued fields.
const isPlainValue = (v: unknown): v is string | number | boolean | null | undefined =>
  v === null || v === undefined || typeof v !== "object";

export function EditableFields({
  values, onSave,
}: { values: Record<string, any>; onSave: (patch: Record<string, any>) => Promise<void> | void }) {
  const [draft, setDraft] = useState<Record<string, string>>(
    Object.fromEntries(
      Object.entries(values)
        .filter(([, v]) => isPlainValue(v))
        .map(([k, v]) => [k, String(v ?? "")]),
    ),
  );
  const [editing, setEditing] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  if (Object.keys(values).length === 0) {
    return <div className="text-xs text-muted-foreground">No extracted fields yet.</div>;
  }

  const save = async (k: string) => {
    setSaving(true);
    try { await onSave({ [k]: draft[k] }); setEditing(null); } finally { setSaving(false); }
  };

  return (
    <dl className="text-sm divide-y">
      {Object.entries(values).map(([k, rawValue]) => {
        const plain = isPlainValue(rawValue);
        const isEdit = plain && editing === k;
        return (
          <div key={k} className="grid grid-cols-[110px_1fr_auto] items-center gap-2 py-1.5">
            <dt className="text-xs text-muted-foreground capitalize self-start pt-1">{k.replace(/_/g, " ")}</dt>
            <dd className="min-w-0">
              {!plain ? (
                <pre className="text-xs font-mono whitespace-pre-wrap break-all bg-muted/50 rounded p-2 max-h-40 overflow-y-auto">
                  {JSON.stringify(rawValue, null, 2)}
                </pre>
              ) : isEdit ? (
                <Input value={draft[k] ?? ""} onChange={(e) => setDraft({ ...draft, [k]: e.target.value })} className="h-7 text-xs" />
              ) : (
                <span className="text-xs font-mono break-all">{draft[k] || "—"}</span>
              )}
            </dd>
            <div className="flex gap-1">
              {!plain ? null : isEdit ? (
                <>
                  <Button variant="ghost" size="icon" onClick={() => setEditing(null)} disabled={saving}>
                    <X className="h-3.5 w-3.5" />
                  </Button>
                  <Button size="icon" onClick={() => save(k)} disabled={saving}>
                    <Check className="h-3.5 w-3.5" />
                  </Button>
                </>
              ) : (
                <Button variant="ghost" size="icon" onClick={() => setEditing(k)}>
                  <Pencil className="h-3.5 w-3.5" />
                </Button>
              )}
            </div>
          </div>
        );
      })}
    </dl>
  );
}
