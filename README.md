# Buchuchet — AI Backoffice OS

An AI-powered backoffice operating system for SMB businesses. **Not a CRM.** An
orchestration layer that connects WhatsApp, Telegram, accounting, documents,
templates, and AI into one operational platform — built with accounting-grade
trust (deterministic-first, AI-assisted, human-confirmed).

## Monorepo layout

```
apps/
  web/        Next.js 15 (App Router, TypeScript, Tailwind, React Query)
  api/        FastAPI backend (Python 3.11+, SQLAlchemy 2.x async)
packages/
  db/         Prisma schema (single source of truth for Postgres)
infra/
  docker-compose.yml         dev infra (Postgres + MinIO + Redis)
  docker-compose.prod.yml    production stack with Nginx
  nginx.conf                 reverse proxy + TLS termination
  backup.sh                  hourly DB + storage snapshot
```

## Tech stack

| Layer | Stack |
|---|---|
| Backend | FastAPI · SQLAlchemy 2.x async · Pydantic v2 · Alembic |
| Database | PostgreSQL (Neon / Supabase / local Docker); SQLite for dev fallback |
| Frontend | Next.js 15 (App Router) · TypeScript · Tailwind · React Query · Zustand |
| AI | OpenAI / Anthropic via a tool-calling orchestrator (`apps/api/app/services/ai`) |
| OCR | OCR.Space (mvp) · Azure Document Intelligence adapter (production) |
| PDF | WeasyPrint (prod) → xhtml2pdf fallback (Windows dev) |
| Templates | python-docx · docxtpl · openpyxl · striprtf · LibreOffice for legacy |
| Storage | S3-compatible (MinIO / AWS S3 / R2) · local FS for dev |
| Messaging | WhatsApp Meta Cloud API · Twilio · Telegram Bot API |
| Monitoring | Sentry (optional) · structured logs via structlog |

## Architecture principles

- AI **never** mutates state directly — only through validated tools.
- Every state-changing action passes through the **approval + audit log** layer.
- Integrations sit behind a uniform `IntegrationAdapter` interface.
- Workflows are data, not code (JSON DAGs executed by a runner).
- Templates are deterministically analyzed; mappings require **human confirmation**
  before AI is allowed to render real business documents.

## Getting started (local dev)

### 1. Prerequisites
- Python 3.11+
- Node.js 20+
- (optional) LibreOffice — for converting legacy `.doc/.xls` templates
- (optional) Docker + Docker Compose — for Postgres / MinIO

### 2. Configure environment
```bash
cp .env.example apps/api/.env
# edit apps/api/.env — set JWT_SECRET, DATABASE_URL (SQLite works out of the box),
# and your OpenAI / OCR.Space keys if you want real AI / OCR.
```

For the frontend:
```bash
cp .env.example apps/web/.env.local
# only NEXT_PUBLIC_API_URL is needed there (defaults to http://localhost:8000).
```

### 3. Backend (API)
```bash
cd apps/api
pip install -e .
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
The first start creates the schema (SQLite default) or applies idempotent
ALTERs on Postgres, then seeds a demo company:
- **email:** `demo@buchuchet.io`
- **password:** `demo1234`

### 4. Frontend (Web)
```bash
cd apps/web
npm install
npm run dev      # http://localhost:3000
```

### 5. Health check
```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/health/diagnostics   # checks DB / OCR / PDF / AI / email
```

## Docker production

```bash
cp .env.prod.example .env.prod      # fill in real secrets
cd infra
cp docker-compose.override.example.yml docker-compose.override.yml   # edit for your server
docker compose -f docker-compose.prod.yml -f docker-compose.override.yml up -d --build
```
The api container runs `alembic upgrade head` before starting; Nginx terminates
TLS and proxies to api/web. `docker-compose.override.yml` is gitignored and holds
whatever differs between this server and the generic reference stack (managed DB,
real TLS certs, subdomain routing) — see **[infra/README.md](infra/README.md)**
for the full bootstrap/deploy runbook and why `git pull` never needs to touch it.

## Required environment variables

See `.env.example` for the full template. Critical ones:

| Var | Purpose |
|---|---|
| `DATABASE_URL` | Postgres DSN (`postgresql+asyncpg://...?sslmode=require`) or `sqlite+aiosqlite:///./buchuchet.db` |
| `JWT_SECRET` | 32+ bytes of randomness — rotate per environment |
| `OPENAI_API_KEY` | enables real AI tool-calling (regex fallback otherwise) |
| `OCR_PROVIDER` + `OCR_SPACE_API_KEY` / Azure pair | document text extraction |
| `STORAGE_BACKEND` + `S3_*` | file storage (`local` for dev) |
| `EMAIL_PROVIDER` + `RESEND_API_KEY` or `POSTMARK_TOKEN` | transactional email |
| `SENTRY_DSN` | error reporting (optional but recommended for prod) |

Per-tenant integration secrets (WhatsApp / Telegram / Bitrix / Kaspi) live in
the database (`integrations.secrets`) — configure them via the `/integrations`
page, not via env.

## Feature surface

- **AI Assistant** — persistent conversations with tool-calling and approval gating
- **Templates** — DOCX/XLSX/PDF/RTF ingestion, AI semantic analysis, deterministic
  mapping with human confirmation, render preview, PDF export
- **Invoicing** — AI/manual creation, approval flow, VAT, immutable lifecycle
- **Documents** — OCR pipeline, editable fields, document timeline
- **Operations dashboard** — pipeline, cashflow, anomalies, activity center, recovery
- **Multichannel** — WhatsApp, Telegram (with inline approve buttons), email
- **Multi-tenant** — RBAC (OWNER / ADMIN / MEMBER / ACCOUNTANT / VIEWER), audit log
- **Plan gating** — Free / Starter / Growth / Business (Stripe-ready, no Stripe yet)

## Documentation

`docs/ARCHITECTURE.md` (in-repo) — system architecture deep-dive.

## License

Proprietary — early-stage product. Not yet open-source.
