# Buchuchet — Demo Script

A scripted 3-flow walkthrough. Run it in this exact order; the flows build on
each other and the timing assumes the demo dataset has been seeded.

## Before you start

**Preflight (60 seconds):**

```powershell
# Terminal 1 — API
cd apps\api
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
# Wait for "Application startup complete." in the logs.

# Terminal 2 — Web
cd apps\web
npm run dev
# Wait for "Ready in NNNms" on http://localhost:3000.

# Terminal 3 — Sanity check
curl http://127.0.0.1:8000/health
# {"status":"ok"}
```

Open http://localhost:3000 and log in:

- **email:** `demo@buchuchet.io`
- **password:** `demo1234`

Verify the dashboard isn't empty (should show ~14 invoices, ~3 generated
documents, ~3 approvals — the v2 seeder produces these on first boot).

If the dashboard looks dead, the seeder didn't run. Run it manually:

```powershell
# In Terminal 1 venv:
python scripts\verify_templates.py     # promotes ACT + NAKLADNAYA templates
python scripts\smoke_generation.py     # adds 18 fresh render records
```

Open one private/incognito tab too so live demo isn't competing with your
auth tokens.

---

## Flow A — AI operational assistant (the headline flow)

**Why this flow:** Shows the whole loop in 90 seconds: NL prompt → template
match → real DOCX render → PDF → approval gate. This is the strongest demo.

**Steps:**

1. Navigate to **Assistant** (`/assistant`).
2. Type and send:
   > **Создай акт для TOO Sigma на 450000 KZT за консалтинговые услуги**
3. Wait ~5 seconds.

**Expected outcome (point to it on screen):**

- Assistant reply: one calm sentence, e.g.
  *"Готово. Акт ACT-2026-NNNN для TOO Sigma. PDF готов к отправке."*
- A **generated_document card** appears with:
  - Badges row: `VERIFIED template` (green) · `Reliability XX/100` · `Quality 84/100` · `PDF ready DOCX` · `Rendered in 4.2s`
  - Template line: *"Inv 4 akt inventarizatsii debitorskoy... · adapted (+1 anchor)"*
  - **PENDING** status badge top-right
  - Buttons: `Open PDF`, `Download DOCX`, `Open document`, `Approve & send`

**Talking points:**

- "Notice the `VERIFIED template` badge — this isn't a built-in fallback,
  it's a real Kazakhstan template the operator confirmed."
- "`Reliability 100/100` comes from the system's own audit log — how often
  this template has actually rendered successfully in production."
- "The adapter found the Russian label `Бухгалтер` in the legacy template
  and injected our canonical `{{accountant_name}}` placeholder at render
  time — without modifying the stored file."
- "Quality 84 means we passed the QA gate (threshold 60); had it failed,
  the document would still be downloadable but approval would be BLOCKED."

**Click `Open PDF`** — opens a real LibreOffice-rendered PDF in a new tab.

**Click `Approve & send`** — toast appears, status flips to `APPROVED`.

---

## Flow B — Quality gate + Recovery Center (the trust flow)

**Why this flow:** Demonstrates that the system is honest about failure.
Most AI demos hide errors — this one routes them to operators with
actionable fixes.

**Steps:**

1. Back to **Assistant**.
2. Type:
   > **Создай акт**

   (Deliberately incomplete — no client, no amount.)
3. Wait ~4 seconds.

**Expected outcome:**

- Assistant reply: one direct sentence, e.g.
  *"Акт ACT-2026-NNNN подготовлен, но не прошёл проверку качества.
  Документ доступен для просмотра — ниже видно, что нужно исправить."*
- Card with:
  - `BLOCKED` red badge top-right
  - Red issues panel: "Blocked by quality gate · 3 issues" — `Client name is empty`, `Total amount is empty`, etc.
  - PDF download still works (operator can inspect)
  - No `Approve & send` button (the gate blocks it)

4. Navigate to **Recovery** (`/recovery`).

**Expected outcome:**

- Top of the queue: a `Generation blocked` red card with:
  - The blocked document title
  - Quality score badge (red, e.g. `Quality 48/100`)
  - **Inline diagnostics panel** grouped by stage (intent / match / quality) with severity colors
  - A **highlighted `Fix:` box** with the suggested resolution
- Below it: `Approval blocked`, `Workflow run failed` (Kaspi 401), `Document OCR / parse failed` rows — each with its own `suggested_fix`

**Talking points:**

- "The system never silently fails — every failure has a structured
  diagnostic with a `Fix:` hint."
- "The Recovery Center is sorted by severity: BLOCKED approvals first,
  then generation failures, then OCR failures."
- "Each row has an action: regenerate, retry OCR, retry send, or escalate."
- "This is how the AI stays trustworthy — when it doesn't know how to
  finish a job, it tells the operator exactly where to look."

5. Navigate to **Approvals** (`/approvals`).

**Expected outcome:**

- Top section: *"Blocked by quality gate · 1"* — the same document, with
  its blocking issues and a `Resolution:` box.
- Below: pending approvals from the demo seeder.

---

## Flow C — OCR + document detail (the depth flow)

**Why this flow:** Shows the **document detail** view as a single place
where everything about a document is visible — render, quality issues,
diagnostics, edit fields. This is the operator's daily workspace.

**Steps:**

1. Navigate to **Documents** (`/documents`).
2. From the list, click any AI-generated document (status = `GENERATED`).
3. (Optional, only if you want to show OCR: upload a JPG of a Kazakh
   invoice via the `Upload` button — for live demos, the pre-seeded
   `Договор поставки — TOO Сапа.pdf` already has parsed fields and is
   safer than risking a real OCR call.)

**Expected outcome on the detail page:**

- Header with `Open file` button
- **Operational badges row**: `VERIFIED template` / `Reliability 100/100`
  / `Quality 84/100` / `PDF ready` / `Rendered in 4.2s`
- Status timeline (UPLOADED → OCR_DONE → PARSED, OR DRAFT → GENERATED)
- Inline PDF preview (iframe)
- Side panel: editable extracted fields
- **Render diagnostics** card: grouped by stage (intent, match,
  adaptation, render, pdf_export) — each row has code + suggested_fix
- **Quality issues** card (for documents that have any)
- Document timeline (audit events)

**Talking points:**

- "Every document is a complete operational artifact — render details,
  who generated it, what template, what diagnostics, what's pending."
- "Operators don't need to read logs — the diagnostics are right here."

---

## Fallback handling during the demo

| Symptom | Cause | Recovery |
|---|---|---|
| Assistant returns plain text, no card | LLM didn't call the tool | Reword more directly: "Сгенерируй акт..." |
| Card shows `HTML fallback` badge | VERIFIED template missing | Run `python scripts\verify_templates.py` — promotes the ACT + NAKLADNAYA |
| 500 on PDF | LibreOffice path broken | Visit `/health/diagnostics` to confirm |
| Recovery is empty | Seeder ran on a clean DB but BLOCKED demos haven't been triggered | Run Flow B once to populate |
| Dashboard empty | Seeder didn't trigger | Restart API; v2 marker re-seeds automatically |

## Talking points cheat sheet (60-second pitch)

1. **"Not a CRM. An AI backoffice operating system."**
   Connects WhatsApp, Telegram, accounting, OCR, templates, and approvals.
2. **"Accounting-grade trust."**
   Deterministic-first. AI proposes, humans confirm. Every state change
   is in the audit log.
3. **"Real Kazakhstan templates."**
   Not a generic invoice. Renders against actual KZ DOCX/XLSX templates
   the operator uploaded, with auto-adaptation for legacy layouts.
4. **"Honest failure modes."**
   Quality gate blocks bad documents from being sent. Recovery Center
   tells operators what to fix.
5. **"Measurable reliability."**
   Every render contributes to a per-template `operational_score`. The
   matcher prefers templates that have actually worked in production.

## Best order

1. **Flow A first** — biggest "wow", shortest path, sets the tone.
2. **Flow B second** — proves the system is honest about failure.
3. **Flow C last** — depth/maturity proof for skeptical audiences.

Total time: ~5 minutes for all three. Cut Flow C if under 3 minutes.

## What NOT to demo

- Settings/Integrations pages (currently sparse — wait for Phase 2 polish).
- The full Templates library list (102 entries, most ANALYZED-only —
  visible legacy clutter).
- The Anomalies page (sparse data outside heavy live use).
- Mobile / responsive — desktop only for now.

## Recovery if it really breaks

Open another browser tab, navigate to `http://127.0.0.1:8000/docs`, and
demo the **API directly** as a fallback. The `POST /api/v1/documents/generate`
endpoint produces the same structured response — looks operational and
recovers the demo even if the frontend hits an error.
