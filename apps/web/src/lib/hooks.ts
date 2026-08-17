"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  api, tokenStore,
  type Approval, type AuditEntry, type CompanyOut, type DashboardSummary, type DocumentDetail,
  type DocumentItem, type IntegrationItem, type Invoice, type InvoiceDetail, type Me,
  type MyPayment, type MySubscription,
  type OnboardingState, type ToolManifest, type UsageAnalytics,
} from "@/lib/api";

// Poll live operational data so toasts fire on backend-side state changes
// (approvals coming in via WhatsApp webhook, etc.). Tabs in background pause.
const LIVE = { refetchInterval: 6000, refetchIntervalInBackground: false };

export const useMe         = () => useQuery({ queryKey: ["me"],         queryFn: () => api.get<Me>("/auth/me") });
export const useInvoices   = () => useQuery({ queryKey: ["invoices"],   queryFn: () => api.get<Invoice[]>("/invoices"), ...LIVE });
export const useInvoice    = (id: string) =>
  useQuery({ queryKey: ["invoice", id], queryFn: () => api.get<InvoiceDetail>(`/invoices/${id}`), enabled: !!id, ...LIVE });
export const useApprovals  = () => useQuery({ queryKey: ["approvals"],  queryFn: () => api.get<Approval[]>("/approvals"), ...LIVE });
// Lightweight aggregate for the dashboard — server-side counts + last-5 lists,
// instead of the dashboard fetching every document/approval the company has
// ever had just to compute this-month totals.
export const useDashboardSummary = () =>
  useQuery({ queryKey: ["dashboard-summary"], queryFn: () => api.get<DashboardSummary>("/dashboard/summary"), ...LIVE });
export const useAuditLog   = () => useQuery({ queryKey: ["logs"],       queryFn: () => api.get<AuditEntry[]>("/logs"), ...LIVE });
export const useMySubscription = () =>
  useQuery({ queryKey: ["billing-subscription"], queryFn: () => api.get<MySubscription>("/billing/subscription") });
export const useMyPayments = () =>
  useQuery({ queryKey: ["billing-payments"], queryFn: () => api.get<MyPayment[]>("/billing/payments") });

export type ConvSummary = { id: string; title: string; created_at: string; message_count: number; user_id: string | null };
export type ConvDetail  = { id: string; title: string; created_at: string;
  messages: { id: number; role: "user"|"assistant"; content: string; at: string; tool_calls: any[] }[] };

export const useConversations = () => useQuery({
  queryKey: ["conversations"],
  queryFn: () => api.get<ConvSummary[]>("/conversations"),
});
export const useConversation = (id: string | null) => useQuery({
  queryKey: ["conversation", id],
  queryFn: () => api.get<ConvDetail>(`/conversations/${id}`),
  enabled: !!id,
});
export function useRenameConversation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) =>
      api.patch<{ id: string; title: string }>(`/conversations/${id}`, { title }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["conversations"] }),
  });
}
export function useDeleteConversation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => fetch(`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/conversations/${id}`,
      { method: "DELETE", headers: { Authorization: `Bearer ${localStorage.getItem("buchuchet.token")}` } })
      .then((r) => { if (!r.ok) throw new Error("delete failed"); return r.json(); }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["conversations"] }),
  });
}
export const useDocuments  = () => useQuery({ queryKey: ["documents"],  queryFn: () => api.get<DocumentItem[]>("/documents"), ...LIVE });
export const useDocument   = (id: string) =>
  useQuery({ queryKey: ["document", id], queryFn: () => api.get<DocumentDetail>(`/documents/${id}`), enabled: !!id });
export const useCompany    = () => useQuery({ queryKey: ["company"],    queryFn: () => api.get<CompanyOut>("/companies/me") });
export const useIntegrations = () => useQuery({ queryKey: ["integrations"], queryFn: () => api.get<IntegrationItem[]>("/integrations") });

export const useOnboarding = () =>
  useQuery({ queryKey: ["onboarding"], queryFn: () => api.get<OnboardingState>("/companies/onboarding"), refetchInterval: 4000 });

export const useUsageAnalytics = () =>
  useQuery({ queryKey: ["usage"], queryFn: () => api.get<UsageAnalytics>("/companies/analytics/usage") });

export const useToolManifest = () =>
  useQuery({ queryKey: ["tools"], queryFn: () => api.get<ToolManifest[]>("/ai/tools") });

export function useCompleteOnboarding() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<{ completed: boolean }>("/companies/onboarding/complete"),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["onboarding"] });
      qc.invalidateQueries({ queryKey: ["company"] });
    },
  });
}

export function useSeedDemo() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<{ already_seeded: boolean }>("/companies/seed-demo"),
    onSuccess: () => qc.invalidateQueries(),
  });
}

export function useExportInvoicePdf() {
  return useMutation({
    mutationFn: (id: string) => api.post<{ pdf_url: string; bytes: number }>(`/invoices/${id}/pdf`),
  });
}

export function useRetryInvoiceSend() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.post<Invoice>(`/invoices/${id}/retry-send`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["invoices"] });
      qc.invalidateQueries({ queryKey: ["logs"] });
    },
  });
}

export function useRetryDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.post<DocumentItem>(`/documents/${id}/retry`),
    onSuccess: (_d, id) => {
      qc.invalidateQueries({ queryKey: ["documents"] });
      qc.invalidateQueries({ queryKey: ["dashboard-summary"] });
      qc.invalidateQueries({ queryKey: ["document", id] });
    },
  });
}

export const useOperationalMetrics = () => useQuery({
  queryKey: ["ops"], queryFn: () => api.get<any>("/ops/operational"),
});
export const useOcrBenchmark = () => useQuery({
  queryKey: ["ocr-benchmark"], queryFn: () => api.get<any>("/ops/ocr-benchmark"),
});

export const useTeam = () => useQuery({
  queryKey: ["team"],
  queryFn: () => api.get<{ members: any[]; invites: any[] }>("/invitations"),
});
export const useAnomalies = () => useQuery({
  queryKey: ["anomalies"], queryFn: () => api.get<any[]>("/anomalies"), refetchInterval: 30000,
});
export const useRecovery = () => useQuery({
  queryKey: ["recovery"], queryFn: () => api.get<any[]>("/recovery"), ...LIVE,
});

export function useInviteTeammate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ email, role }: { email: string; role: string }) =>
      api.post<any>("/invitations", { email, role }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["team"] }),
  });
}
export function useRevokeInvite() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.post<any>(`/invitations/${id}/revoke`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["team"] }),
  });
}
export function useUpdateMemberRole() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, role }: { id: string; role: string }) =>
      api.patch<any>(`/invitations/members/${id}/role`, { role }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["team"] }),
  });
}

export const useTelegramStatus = () => useQuery({
  queryKey: ["telegram", "me"], queryFn: () => api.get<any>("/telegram/me"),
  refetchInterval: 5000,
});
export function useTelegramLink() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<{ deep_link: string; expires_at: string; token: string }>("/telegram/link/start"),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["telegram", "me"] }),
  });
}
export function useTelegramDisconnect() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<{ ok: boolean }>("/telegram/link/disconnect"),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["telegram", "me"] }),
  });
}
// Bot-level (per-workspace) connect/disconnect — distinct from the per-user
// link helpers above. `useTelegramLink` binds an individual operator's
// Telegram chat to their User row; these manage the bot itself.
export function useTelegramBotConnect() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { bot_token: string; public_webhook_base?: string }) =>
      api.post<{
        ok: boolean; bot_username: string; bot_id: number;
        webhook_url: string | null; webhook_registered: boolean;
        webhook_error: string | null;
      }>("/telegram/bot/connect", body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["telegram", "me"] });
      qc.invalidateQueries({ queryKey: ["integrations"] });
    },
  });
}
export function useTelegramBotDisconnect() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<{ ok: boolean; webhook_deleted: boolean }>("/telegram/bot/disconnect"),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["telegram", "me"] });
      qc.invalidateQueries({ queryKey: ["integrations"] });
    },
  });
}
export function useUpdateNotificationPrefs() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (patch: { notify_telegram?: boolean; notify_email?: boolean }) =>
      api.patch<any>("/telegram/preferences", patch),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["telegram", "me"] }),
  });
}

export function useLogin() {
  return useMutation({
    mutationFn: (body: { email: string; password: string; turnstile_token?: string }) =>
      api.postNoAuth<{ access_token: string; user: Me }>("/auth/login", body),
    onSuccess: (r) => tokenStore.set(r.access_token),
  });
}

export type RegisterInput = {
  company_name: string;
  email: string;
  password: string;
  name?: string;
  bin?: string;
  turnstile_token?: string;
};

// Backend shape depends on REQUIRE_EMAIL_VERIFICATION: verification off
// (default in beta) logs the user in immediately, same as the old flow;
// verification on returns a pending-confirmation marker instead.
export type RegisterResult =
  | { access_token: string; user: Me }
  | { status: string; email: string };

export function useRegister() {
  return useMutation({
    mutationFn: (body: RegisterInput) =>
      api.postNoAuth<RegisterResult>("/auth/register", body),
    onSuccess: (r) => { if ("access_token" in r) tokenStore.set(r.access_token); },
  });
}

export function useVerifyEmail() {
  return useMutation({
    mutationFn: ({ email, code }: { email: string; code: string }) =>
      api.postNoAuth<{ access_token: string; user: Me }>("/auth/verify-email", { email, code }),
    onSuccess: (r) => tokenStore.set(r.access_token),
  });
}

export function useResendCode() {
  return useMutation({
    mutationFn: (email: string) =>
      api.postNoAuth<{ status: string }>("/auth/resend-code", { email }),
  });
}

export function useLogout() {
  const qc = useQueryClient();
  return () => { tokenStore.clear(); qc.clear(); window.location.href = "/login"; };
}

export function useDecideApproval() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, approve }: { id: string; approve: boolean }) =>
      api.post<Approval>(`/approvals/${id}/decide`, { approve }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["approvals"] });
      qc.invalidateQueries({ queryKey: ["dashboard-summary"] });
      qc.invalidateQueries({ queryKey: ["invoices"] });
      qc.invalidateQueries({ queryKey: ["logs"] });
    },
  });
}

export function useSendChat() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ message, conversation_id }: { message: string; conversation_id?: string | null }) =>
      api.post<{ conversation_id: string; reply: string; tool_calls: { name: string; args: any; result: any }[] }>(
        "/ai/chat", { message, conversation_id },
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["invoices"] });
      qc.invalidateQueries({ queryKey: ["approvals"] });
      qc.invalidateQueries({ queryKey: ["dashboard-summary"] });
      qc.invalidateQueries({ queryKey: ["logs"] });
    },
  });
}

export function useSimulateWhatsApp() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ text, from_phone }: { text: string; from_phone?: string }) =>
      api.post<{ received: boolean; reply: string }>("/webhooks/whatsapp/sim", { text, from_phone }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["invoices"] });
      qc.invalidateQueries({ queryKey: ["approvals"] });
      qc.invalidateQueries({ queryKey: ["dashboard-summary"] });
      qc.invalidateQueries({ queryKey: ["logs"] });
    },
  });
}

export function useUploadDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ file, doc_type, onProgress }: { file: File; doc_type?: string; onProgress?: (p: number) => void }) => {
      // Use XHR to expose progress events.
      return await new Promise<DocumentItem>((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
        xhr.open("POST", `${BASE}/api/v1/documents/upload`);
        const tok = tokenStore.get();
        if (tok) xhr.setRequestHeader("Authorization", `Bearer ${tok}`);
        xhr.upload.onprogress = (e) => onProgress?.(Math.round((e.loaded / (e.total || 1)) * 100));
        xhr.onload = () => {
          if (xhr.status >= 200 && xhr.status < 300) resolve(JSON.parse(xhr.responseText));
          else reject(new Error(`API ${xhr.status}: ${xhr.responseText}`));
        };
        xhr.onerror = () => reject(new Error("network error"));
        const form = new FormData();
        form.append("file", file);
        if (doc_type) form.append("doc_type", doc_type);
        xhr.send(form);
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["documents"] });
      qc.invalidateQueries({ queryKey: ["dashboard-summary"] });
      qc.invalidateQueries({ queryKey: ["logs"] });
    },
  });
}

export function useUpdateDocumentFields() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, parsed }: { id: string; parsed: Record<string, any> }) =>
      api.patch<DocumentDetail>(`/documents/${id}/fields`, { parsed }),
    onSuccess: (_d, vars) => {
      qc.invalidateQueries({ queryKey: ["document", vars.id] });
      qc.invalidateQueries({ queryKey: ["logs"] });
    },
  });
}

export function useUpdateSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (patch: Record<string, any>) =>
      api.patch<{ settings: Record<string, any> }>("/companies/settings", { settings: patch }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["company"] }),
  });
}

export function useUpdateCompany() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (patch: Partial<CompanyOut>) => api.patch<{ id: string }>("/companies/me", patch),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["company"] }),
  });
}

export function useUploadLogo() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => {
      const f = new FormData(); f.append("file", file);
      return api.upload<{ logo_url: string }>("/companies/branding/logo", f);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["company"] }),
  });
}

export function useTemplates(kind?: string) {
  return useQuery({
    queryKey: ["templates", kind ?? "all"],
    queryFn: () => api.get<Array<{ id: string; name: string; kind: string; format: string; is_default: boolean; body: string | null }>>(
      `/templates${kind ? `?kind=${kind}` : ""}`,
    ),
  });
}

export function useUploadDocxTemplate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ file, name, kind = "invoice", is_default = false }: {
      file: File; name: string; kind?: string; is_default?: boolean;
    }) => {
      const f = new FormData();
      f.append("file", file); f.append("name", name); f.append("kind", kind);
      f.append("is_default", String(is_default));
      return api.upload<{ id: string; name: string; key: string }>("/templates/upload-docx", f);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["templates"] }),
  });
}

export function useConnectIntegration() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ provider, config, secrets }: { provider: string; config: any; secrets: any }) =>
      api.post<IntegrationItem>(`/integrations/${provider}/connect`, { config, secrets }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["integrations"] }),
  });
}
