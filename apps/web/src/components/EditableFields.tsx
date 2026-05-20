"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Pencil, Check, X } from "lucide-react";

export function EditableFields({
  values, onSave,
}: { values: Record<string, any>; onSave: (patch: Record<string, any>) => Promise<void> | void }) {
  const [draft, setDraft] = useState<Record<string, string>>(
    Object.fromEntries(Object.entries(values).map(([k, v]) => [k, String(v ?? "")])),
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
      {Object.entries(draft).map(([k, v]) => {
        const isEdit = editing === k;
        return (
          <div key={k} className="grid grid-cols-[110px_1fr_auto] items-center gap-2 py-1.5">
            <dt className="text-xs text-muted-foreground capitalize">{k.replace(/_/g, " ")}</dt>
            <dd>
              {isEdit ? (
                <Input value={v} onChange={(e) => setDraft({ ...draft, [k]: e.target.value })} className="h-7 text-xs" />
              ) : (
                <span className="text-xs font-mono break-all">{v || "—"}</span>
              )}
            </dd>
            <div className="flex gap-1">
              {isEdit ? (
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
