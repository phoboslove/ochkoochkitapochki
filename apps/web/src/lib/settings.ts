"use client";

import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

export type BusinessContext = {
  company: any; accounting: any; branding: any;
  approvals: any; notifications: any;
  integrations: { items: { provider: string; status: string; config: any }[] };
  knowledge_doc_count: number;
  plan: string; onboarded: boolean;
};

export const useBusinessContext = () => useQuery({
  queryKey: ["settings"], queryFn: () => api.get<BusinessContext>("/settings"),
  refetchOnWindowFocus: true,
});

export function usePatchSection(section: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Record<string, any>) =>
      api.patch<BusinessContext>(`/settings/${section}`, { data }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["settings"] }),
  });
}

/**
 * Section editor with dirty-state + debounced autosave.
 * Saves 800ms after the last change. Returns helpers for the form.
 */
export function useSectionEditor<T extends Record<string, any>>(
  section: string, initial: T | undefined,
): {
  draft: T;
  setField: <K extends keyof T>(k: K, v: T[K]) => void;
  dirty: boolean;
  saving: boolean;
  savedAt: Date | null;
  flush: () => void;
} {
  const patch = usePatchSection(section);
  const [draft, setDraft] = useState<T>((initial ?? {}) as T);
  const [dirty, setDirty] = useState(false);
  const [savedAt, setSavedAt] = useState<Date | null>(null);
  const tRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastInit = useRef<T | undefined>(initial);
  // Mirror draft/dirty into refs so `flush` always reads the latest values
  // no matter which render's closure ends up calling it. Without this, the
  // unmount-flush effect below (empty deps, so its cleanup is frozen to the
  // very first render's closure) would read mount-time dirty=false and
  // silently drop the last edit if the user navigated away before the
  // 800ms debounce timer fired.
  const draftRef = useRef(draft);
  const dirtyRef = useRef(dirty);
  draftRef.current = draft;
  dirtyRef.current = dirty;

  // Pull external updates only when not currently dirty (preserve user edits).
  useEffect(() => {
    if (!initial) return;
    if (!dirty) { setDraft(initial); lastInit.current = initial; }
  }, [initial, dirty]);

  const flush = () => {
    if (tRef.current) clearTimeout(tRef.current);
    if (!dirtyRef.current) return;
    patch.mutate(draftRef.current as any, {
      onSuccess: () => { setDirty(false); setSavedAt(new Date()); },
    });
  };

  const setField: any = (k: keyof T, v: any) => {
    setDraft((d) => ({ ...d, [k]: v }));
    setDirty(true);
    if (tRef.current) clearTimeout(tRef.current);
    tRef.current = setTimeout(flush, 800);
  };

  // Flush on unmount to avoid losing the last debounced edit.
  useEffect(() => () => { flush(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);

  return { draft, setField, dirty, saving: patch.isPending, savedAt, flush };
}

// Knowledge base
export const useKnowledge = () => useQuery({
  queryKey: ["knowledge"], queryFn: () => api.get<any[]>("/knowledge"),
});

export function useUpsertKnowledge() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { id?: string; title: string; body?: string; tags?: string[] }) =>
      api.put<any>("/knowledge", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["knowledge"] }),
  });
}

export function useDeleteKnowledge() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/knowledge/${id}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${localStorage.getItem("buchuchet.token")}` },
      }).then((r) => { if (!r.ok) throw new Error("delete failed"); return r.json(); }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["knowledge"] }),
  });
}
