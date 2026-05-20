"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, tokenStore } from "@/lib/api";

export type ValidationWarning = {
  code: string; severity: "info"|"warn"|"high"|"critical"; message: string; fix?: string;
};

export type TemplateSummary = {
  id: string; name: string; kind: string;
  format: "html"|"docx"|"xlsx"|"pdf"|"doc"|"xls"|"rtf";
  is_default: boolean;
  status: "UPLOADED"|"ANALYZED"|"MAPPED"|"VERIFIED"|"FAILED"|"ARCHIVED";
  version: number; language: string | null;
  confidence: number | null;
  original_filename: string | null;
  industry: string | null;
  validation_score: number | null;
  validation_warnings: ValidationWarning[];
  converted_from_id: string | null;
  updated_at: string | null;
  last_render_at: string | null;
  last_error: string | null;
  parent_template_id: string | null;
};

export type DetectedTable = {
  sheet: string | null; headers: string[];
  rows_preview: string[][]; is_repeating: boolean;
};

export type TemplateDetail = TemplateSummary & {
  detected_fields: { paragraphs?: string[]; placeholders?: string[]; notes?: string[] };
  detected_tables: DetectedTable[];
  mappings: Record<string, {
    source_label: string; source_kind: string; confidence: number; confirmed: boolean;
  }>;
  body: string | null;
  storage_key: string | null;
};

export type FieldRegistry = {
  groups: string[];
  fields: { key: string; group: string; label: string; sample: string }[];
};

export const useTemplateRegistry = () => useQuery({
  queryKey: ["templates","registry"],
  queryFn: () => api.get<FieldRegistry>("/templates/registry"),
  staleTime: 5 * 60_000,
});

export const useTemplatesLib = (filters: { kind?: string; industry?: string } = {}) => useQuery({
  queryKey: ["templates","lib", filters.kind ?? "all", filters.industry ?? "all"],
  queryFn: () => {
    const p = new URLSearchParams();
    if (filters.kind)     p.set("kind", filters.kind);
    if (filters.industry) p.set("industry", filters.industry);
    const qs = p.toString();
    return api.get<TemplateSummary[]>(`/templates${qs ? `?${qs}` : ""}`);
  },
});

export const useIndustryPacks = () => useQuery({
  queryKey: ["templates","packs"],
  queryFn: () => api.get<{ packs: { industry: string; count: number }[] }>("/templates/industry-packs"),
});

export const useConverterStatus = () => useQuery({
  queryKey: ["templates","converter"],
  queryFn: () => api.get<{ available: boolean; soffice_path: string | null }>("/templates/converter-status"),
});

export function useConvertTemplate(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<any>(`/templates/${id}/convert`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["templates"] }),
  });
}
export function useConvertAllLegacy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<{ total: number; converted: number; failed: number; items: any[] }>(
      "/templates/convert-legacy-all"),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["templates"] }),
  });
}
export function useCorpusAudit() {
  return useMutation({
    mutationFn: () => api.post<any>("/templates/audit"),
  });
}

export function useSummarizeTemplate(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<{ semantic: any }>(`/templates/${id}/summarize`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["templates", id] }),
  });
}
export function useSummarizeAll() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (limit?: number) => api.post<{ summarized: number; remaining: number }>(
      `/templates/summarize-all${limit ? `?limit=${limit}` : ""}`,
    ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["templates"] }),
  });
}
export function useUpdateTagging(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { tags?: string[]; use_case?: string; summary?: string; business_purpose?: string }) =>
      api.patch<any>(`/templates/${id}/tagging`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["templates", id] }),
  });
}
export const useTemplateClusters = () => useQuery({
  queryKey: ["templates", "clusters"],
  queryFn: () => api.get<any>("/templates/clusters"),
});

export function useValidateTemplate(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.get<{ score: number; qa_status: string; warnings: ValidationWarning[] }>(
      `/templates/${id}/validate`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["templates", id] });
      qc.invalidateQueries({ queryKey: ["templates","lib"] });
    },
  });
}

export const useTemplate = (id: string) => useQuery({
  queryKey: ["templates", id],
  queryFn: () => api.get<TemplateDetail>(`/templates/${id}`),
  enabled: !!id,
});

export const useTemplateVersions = (id: string) => useQuery({
  queryKey: ["templates", id, "versions"],
  queryFn: () => api.get<TemplateSummary[]>(`/templates/${id}/versions`),
  enabled: !!id,
});

export function useUploadTemplate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ file, name, kind = "", is_default = false }: {
      file: File; name: string; kind?: string; is_default?: boolean;
    }) => {
      const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
      const fd = new FormData();
      fd.append("file", file); fd.append("name", name);
      if (kind) fd.append("kind", kind);
      fd.append("is_default", String(is_default));
      const r = await fetch(`${BASE}/api/v1/templates/upload`, {
        method: "POST", body: fd,
        headers: { Authorization: `Bearer ${tokenStore.get()}` },
      });
      if (!r.ok) throw new Error(await r.text());
      return r.json() as Promise<TemplateDetail>;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["templates"] }),
  });
}

export function usePatchMappings(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { mappings: TemplateDetail["mappings"]; confirm_all?: boolean }) =>
      api.patch<TemplateDetail>(`/templates/${id}/mappings`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["templates", id] });
      qc.invalidateQueries({ queryKey: ["templates", "lib"] });
    },
  });
}

export function useRenderPreview(id: string) {
  return useMutation({
    mutationFn: () => api.post<{ preview_url: string; mime: string; ext: string; bytes: number }>(
      `/templates/${id}/preview`,
    ),
  });
}

export function useTemplateActions(id: string) {
  const qc = useQueryClient();
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["templates", id] });
    qc.invalidateQueries({ queryKey: ["templates", "lib"] });
  };
  const archive    = useMutation({ mutationFn: () => api.post(`/templates/${id}/archive`),     onSuccess: invalidate });
  const makeDefault= useMutation({ mutationFn: () => api.post(`/templates/${id}/make-default`),onSuccess: invalidate });
  return { archive, makeDefault };
}
