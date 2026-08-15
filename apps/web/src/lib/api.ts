const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const TOKEN_KEY = "buchuchet.token";

export const tokenStore = {
  get(): string | null {
    if (typeof window === "undefined") return null;
    return window.localStorage.getItem(TOKEN_KEY);
  },
  set(t: string) { if (typeof window !== "undefined") window.localStorage.setItem(TOKEN_KEY, t); },
  clear()        { if (typeof window !== "undefined") window.localStorage.removeItem(TOKEN_KEY); },
};

async function request<T>(path: string, init: RequestInit = {}, opts: { auth?: boolean } = { auth: true }): Promise<T> {
  const headers: Record<string, string> = {
    ...(init.body && !(init.body instanceof FormData) ? { "Content-Type": "application/json" } : {}),
    ...((init.headers as Record<string, string>) ?? {}),
  };
  if (opts.auth) {
    const tok = tokenStore.get();
    if (tok) headers["Authorization"] = `Bearer ${tok}`;
  }
  const res = await fetch(`${BASE}/api/v1${path}`, { ...init, headers, cache: "no-store" });
  if (res.status === 401) {
    tokenStore.clear();
    if (typeof window !== "undefined" && window.location.pathname !== "/login") window.location.href = "/login";
    throw new Error("unauthorized");
  }
  if (!res.ok) {
    let body: any = {};
    try { body = await res.json(); } catch { body = { message: await res.text() }; }
    const supportId = res.headers.get("x-request-id") || body.support_id;
    const detail = body.message || body.error || res.statusText;
    const err = new Error(supportId ? `${detail} (ref: ${supportId})` : detail);
    (err as any).status = res.status;
    (err as any).body = body;
    throw err;
  }
  return res.json() as Promise<T>;
}

export const api = {
  get:    <T>(p: string) => request<T>(p),
  post:   <T>(p: string, body?: unknown) => request<T>(p, { method: "POST", body: JSON.stringify(body ?? {}) }),
  patch:  <T>(p: string, body?: unknown) => request<T>(p, { method: "PATCH", body: JSON.stringify(body ?? {}) }),
  put:    <T>(p: string, body?: unknown) => request<T>(p, { method: "PUT", body: JSON.stringify(body ?? {}) }),
  delete: <T>(p: string) => request<T>(p, { method: "DELETE" }),
  upload: <T>(p: string, form: FormData) => request<T>(p, { method: "POST", body: form }),
  postNoAuth: <T>(p: string, body?: unknown) =>
    request<T>(p, { method: "POST", body: JSON.stringify(body ?? {}) }, { auth: false }),
  // Storage URLs come back either absolute (S3/R2 presigned — already a full,
  // signed URL) or relative (local-storage backend's /api/v1/files/... path).
  // Only relative ones need the API origin prefixed; prefixing an absolute
  // URL would concatenate two origins into one broken string.
  fileUrl: (url: string) => /^https?:\/\//i.test(url) ? url : `${BASE}${url}`,
};

// Types
export type Role = "OWNER" | "ADMIN" | "MEMBER" | "VIEWER";
export type Me = {
  id: string; email: string; name: string | null; role: Role; company_id: string;
  is_platform_admin?: boolean;
};

export type Invoice = {
  id: string; number: string; client_id: string | null;
  issue_date: string | null; due_date: string | null;
  currency: string; subtotal: string; tax_total: string; total: string;
  status: "DRAFT" | "PENDING_APPROVAL" | "APPROVED" | "SENT" | "PAID" | "OVERDUE" | "CANCELLED";
  items: { name: string; qty: number; price: number; tax?: number }[];
  pdf_key: string | null; pdf_url: string | null;
};
export type InvoiceDetail = Invoice & {
  company: { name: string; bin: string | null } | null;
  client:  { id: string; name: string; bin: string | null; phone: string | null } | null;
};
export type Approval = {
  id: string; resource_type: string; resource_id: string; action: string;
  summary: string; status: "PENDING" | "APPROVED" | "REJECTED" | "BLOCKED";
  requested_by: string; decided_by: string | null; created_at: string;
  payload: Record<string, unknown>;
};
export type AuditEntry = {
  id: number; at: string; actor_type: string; actor_id: string | null;
  action: string; resource: string | null; meta: Record<string, unknown>;
};
export type DocumentItem = {
  id: string; title: string; type: string; mime: string; size: number;
  status: "UPLOADED" | "OCR_PENDING" | "OCR_DONE" | "PARSED" | "FAILED" | "GENERATED";
  created_at: string; checksum: string | null;
  parsed: Record<string, unknown> | null;
  preview_url: string | null;
};
export type DocumentDetail = DocumentItem & { ocr_text: string | null };
export type IntegrationItem = {
  id: string | null; provider: string; status: string; config: Record<string, unknown>;
};
export type CompanyOut = {
  id: string; name: string; bin: string | null; tax_mode: string | null;
  country_code: string; settings: Record<string, any>; logo_url: string | null;
  plan: string; onboarded: boolean;
};

export type OnboardingStep = { key: string; label: string; done: boolean; optional?: boolean };
export type OnboardingState = { steps: OnboardingStep[]; completed: boolean };

export type UsageAnalytics = {
  window_days: number;
  ai_tool_invocations: number; ai_tool_denied: number;
  approvals_decided: number; approvals_requested: number;
  invoices_created: number; invoices_sent: number;
  documents_uploaded: number; workflow_failures: number;
  by_action: Record<string, number>;
  plan: { name: string; limits: Record<string, number> } | null;
};

export type ToolManifest = {
  name: string; description: string; danger: "read" | "write" | "financial";
  min_role: string; requires_approval: boolean;
};

// ── Billing (client-facing) ─────────────────────────────────────────────

export type SubscriptionStatus = "trialing" | "active" | "past_due" | "suspended" | "cancelled";

export type MySubscription = {
  plan: { code: string; name: string; price_amount: number; price_currency: string; billing_period: string };
  status: SubscriptionStatus;
  period_start: string; period_end: string;
  days_until_period_end: number;
  grace_period_days: number;
  days_until_suspend: number | null;
  renewal_method: string;
  usage: { documents_used: number; documents_limit: number };
  limits: { documents_per_month: number; users: number; templates: number };
};

export type MyPayment = {
  id: string; amount: number; currency: string; status: string; method: string;
  comment: string | null; paid_at: string | null; created_at: string;
};

// ── Admin ────────────────────────────────────────────────────────────────

export type AdminDashboard = {
  companies: { total: number; active: number; trialing: number; past_due: number; suspended: number; cancelled: number };
  documents_this_month: number;
  mrr: number; mrr_currency: string;
  top_companies: { company_id: string; company_name: string; documents_this_month: number }[];
};

export type AdminCompanyListItem = {
  id: string; name: string; bin: string | null; created_at: string; users_count: number;
  subscription: { status: SubscriptionStatus; period_end: string; plan_code: string; plan_name: string } | null;
};

export type AdminCompanyDetail = {
  company: { id: string; name: string; bin: string | null; country_code: string; created_at: string };
  subscription: {
    id: string; status: SubscriptionStatus; period_start: string; period_end: string;
    grace_period_days: number; renewal_method: string;
    plan: { id: string; code: string; name: string; price_amount: number; price_currency: string;
             limit_documents_per_month: number; limit_users: number; limit_templates: number };
    usage: { documents_used: number; documents_limit: number };
  } | null;
  users: { id: string; email: string; name: string | null; role: string; active: boolean; created_at: string }[];
  payments: MyPayment[];
  usage_by_month: { period: string; documents_count: number }[];
  audit_trail: { id: number; actor_type: string; actor_id: string | null; action: string;
                 resource: string | null; meta: Record<string, any>; at: string }[];
};

export type AdminPlan = {
  id: string; code: string; name: string; price_amount: number; price_currency: string;
  billing_period: string; limit_documents_per_month: number; limit_users: number;
  limit_templates: number; allowed_integrations: string[] | null; is_active: boolean; sort_order: number;
};
