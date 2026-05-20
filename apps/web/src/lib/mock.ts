// Demo data used until the API is reachable. Mirrors backend shape.

export const dashboardStats = {
  revenue_mtd: 1_820_000,
  invoices_open: 7,
  invoices_overdue: 2,
  approvals_pending: 2,
  documents_processed: 38,
  workflow_failures: 1,
};

export const activityFeed = [
  { id: "a1", at: "08:01", actor: "AI",     text: "Created draft invoice INV-2025-017 for TOO Gamma" },
  { id: "a2", at: "08:02", actor: "AI",     text: "Requested approval to send INV-2025-014 (850,000 ₸)" },
  { id: "a3", at: "08:14", actor: "Owner",  text: "Approved invoice INV-2025-014" },
  { id: "a4", at: "08:15", actor: "System", text: "WhatsApp: invoice PDF delivered to TOO ABC" },
  { id: "a5", at: "08:33", actor: "AI",     text: "Parsed 3 documents from inbox (OCR done)" },
];

export const documents = [
  { id: "doc_1", title: "Contract — TOO ABC.pdf",     type: "CONTRACT", status: "PARSED",   updated: "Today 09:12" },
  { id: "doc_2", title: "Invoice INV-2025-014.pdf",   type: "INVOICE",  status: "PARSED",   updated: "Today 08:01" },
  { id: "doc_3", title: "Act #2025-04-30.docx",       type: "ACT",      status: "OCR_DONE", updated: "Yesterday" },
  { id: "doc_4", title: "Schet-faktura 412.pdf",      type: "SCHET_FAKTURA", status: "UPLOADED", updated: "2 days ago" },
];

export const invoices = [
  { id: "inv_001", number: "INV-2025-014", client: "TOO ABC",    total: 850000, status: "SENT",    issue_date: "2026-04-12" },
  { id: "inv_002", number: "INV-2025-015", client: "ИП Иванов",  total: 120000, status: "PAID",    issue_date: "2026-04-15" },
  { id: "inv_003", number: "INV-2025-016", client: "TOO Beta",   total: 540000, status: "OVERDUE", issue_date: "2026-03-20" },
  { id: "inv_004", number: "INV-2025-017", client: "TOO Gamma",  total: 310000, status: "DRAFT",   issue_date: "2026-05-01" },
];

export const workflows = [
  { id: "wf_1", name: "WhatsApp → Invoice",            trigger: "whatsapp.message",  enabled: true,  last_run: "succeeded · 2m ago" },
  { id: "wf_2", name: "Monthly accounting report",     trigger: "schedule:monthly",  enabled: true,  last_run: "succeeded · 8d ago" },
  { id: "wf_3", name: "Overdue invoice reminder",      trigger: "schedule:daily",    enabled: true,  last_run: "succeeded · 6h ago" },
  { id: "wf_4", name: "Kaspi payout reconciliation",   trigger: "kaspi.payout",      enabled: false, last_run: "—" },
];

export const integrations = [
  { provider: "whatsapp", name: "WhatsApp Business",  status: "connected"    },
  { provider: "telegram", name: "Telegram",           status: "disconnected" },
  { provider: "bitrix",   name: "Bitrix24",           status: "connected"    },
  { provider: "amocrm",   name: "amoCRM",             status: "disconnected" },
  { provider: "kaspi",    name: "Kaspi.kz",           status: "disconnected" },
  { provider: "ozon",     name: "Ozon",               status: "disconnected" },
  { provider: "gsheets",  name: "Google Sheets",      status: "connected"    },
  { provider: "gmail",    name: "Gmail",              status: "disconnected" },
  { provider: "gdrive",   name: "Google Drive",       status: "disconnected" },
  { provider: "1c",       name: "1C",                 status: "disconnected" },
];

export const approvals = [
  { id: "apr_001", action: "Send invoice INV-2025-014 to TOO ABC", amount: 850000, requested_by: "AI", at: "08:02" },
  { id: "apr_002", action: "Release supplier payment to TOO Delta", amount: 220000, requested_by: "AI", at: "07:55" },
];

export const clients = [
  { id: "cl_1", name: "TOO ABC",   bin: "123456789012", phone: "+7 701 000 0001", invoices: 6, revenue: 4_200_000 },
  { id: "cl_2", name: "ИП Иванов", bin: "987654321098", phone: "+7 705 000 0002", invoices: 3, revenue:   860_000 },
  { id: "cl_3", name: "TOO Beta",  bin: "555555555555", phone: "+7 707 000 0003", invoices: 2, revenue: 1_100_000 },
  { id: "cl_4", name: "TOO Gamma", bin: "111122223333", phone: "+7 700 000 0004", invoices: 1, revenue:   310_000 },
];

export const logs = [
  { at: "08:01:12", actor: "AI",     action: "invoice.create_draft", resource: "inv_004" },
  { at: "08:02:01", actor: "AI",     action: "approval.request",     resource: "apr_001" },
  { at: "08:14:33", actor: "Owner",  action: "approval.decide",      resource: "apr_001" },
  { at: "08:15:02", actor: "System", action: "whatsapp.send_pdf",    resource: "inv_001" },
  { at: "08:33:10", actor: "AI",     action: "document.ocr",         resource: "doc_3"   },
];
