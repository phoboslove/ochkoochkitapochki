# Architecture

```
┌──────────────┐   HTTPS    ┌──────────────────────────────┐
│  Next.js UI  │ ─────────► │  FastAPI gateway (api/v1)    │
└──────────────┘            └───────────────┬──────────────┘
                                            │
              ┌─────────────┬───────────────┼────────────────┬──────────────┐
              ▼             ▼               ▼                ▼              ▼
        AI Orchestrator  Documents      Workflows       Integrations    Approvals
         (tools, mem)    (OCR/parse/     (engine +      (whatsapp,      (gating +
                          generate)      runner)         telegram,       audit)
                                                         bitrix, kaspi…)
                              │              │
                              ▼              ▼
                          S3 storage     Postgres (Prisma schema)
```

## Boundaries

- **AI never touches DB or FS directly.** All effects go through `services/ai/tools/*`,
  which call the same services the HTTP API uses, with the same validation.
- **Approvals + Audit** wrap every state-changing action. `Tool.requires_approval`
  routes the call through `approvals.service` instead of executing immediately.
- **Integrations** share the `IntegrationAdapter` interface — connect/test/send.
  The `IntegrationManager` is the only place the rest of the app talks to providers.
- **Workflows** are JSON DAGs. `Runner` walks them; step types map to executor
  functions. Swap the runner for LangGraph/Temporal without changing persistence.
- **OCR** is a single `OCRProvider` interface with pluggable Azure / Google / mock
  backends, selected via env.
- **Storage** is S3-compatible behind a thin `S3Storage` adapter (MinIO in dev).

## Data flow examples

### "Create invoice for TOO ABC, 250,000 ₸"
1. UI → `POST /ai/chat`
2. AIOrchestrator runs LLM with tool schemas
3. LLM calls `create_invoice` (requires_approval=true)
4. ApprovalService creates a pending approval; returns ID to AI
5. UI shows the request in `/approvals`; owner approves
6. Workflow runner finalizes invoice → InvoiceService → DocumentGenerator (PDF) → S3
7. WhatsApp adapter sends the PDF; AuditLogger records every step

### "WhatsApp inbound message → Invoice"
1. Provider webhook → `/integrations/whatsapp/webhook`
2. Workflow `wf_whatsapp_invoice` triggered with payload
3. Runner: parse intent (AI) → upsert client → draft invoice → request approval → send PDF

## What's mocked in the scaffold
- All services use in-memory demo data so the API runs without a DB.
- `AIOrchestrator._run_llm_loop` is a stub; wire OpenAI/Anthropic SDKs there.
- OCR defaults to `MockOCR`.
- Document generator returns a placeholder PDF.

These are the seams to replace as the MVP is built out.
