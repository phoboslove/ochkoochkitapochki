# Buchuchet — Beta Readiness Audit

**Date:** 2026-06-02
**Audit mode:** brutal honesty. Only PASS when verified by code/tests/logs.
**Scope of this session:** code inspection + smoke harness + real cross-tenant
test + grep audit + deployment file review. Full manual UX/i18n walkthrough
of every page was **NOT performed** — flagged explicitly below.

---

## 1. Executive Summary

Pipeline correctness is solid (smoke 100% pass, parser-wins consistency,
proposal state machine, kind lock all hold up under test). Production
deployment files exist and look sane.

**Showstoppers for external beta:**

1. **`POST /api/v1/workflows/{id}/run` has zero authentication** — anyone on
   the internet can fire workflows for any workspace. CRITICAL.
2. **No i18n framework. ~170 hardcoded EN strings in UI**, no `messages.json`,
   no `useTranslation`. UI is accidentally bilingual (Russian on some
   pages, English on others). For a Kazakhstan product this is a beta
   blocker.
3. **Zero Kazakh templates**. All three commercial templates are Russian.
   System will silently fall back to Russian for Kazakh-speaking users.
4. **Service-layer cross-tenant gap on Approval.decide** — endpoint checks
   company isolation, the service doesn't. Defense-in-depth gap. Today not
   exploitable via HTTP (endpoint blocks), but Telegram callback also
   relies on the endpoint-style check; one missed call site = full RCE of
   approve/reject across the system.
5. **Bot tokens stored plaintext in `Integration.secrets` JSON**. Relies on
   DB-level encryption (Neon does encrypt at rest). Acceptable risk if you
   trust Neon; not acceptable for self-hosted.

**Pipeline quality (verified):**

- Smoke harness 18/18 pass, 0 fallback, avg render 5.7s, all 3 commercial
  templates render with quality 98.
- Frontend production build green (24/24 static pages, no type errors).
- Cross-tenant test on real DB: `DocumentService.get` / `InvoiceService.get`
  correctly return None for other-tenant lookups.

---

## 2. Critical Issues (must fix before any external testing)

### C1 · No auth on `/workflows` and `/reports`
**File:** `apps/api/app/api/v1/endpoints/workflows.py` (3 routes),
`apps/api/app/api/v1/endpoints/reports.py` (2 routes).
**Reproduction:** `curl https://api/.../api/v1/workflows/wf_x/run -d '{}'` — no
Bearer required, no tenant filter, no rate limit.
**Impact:** Full workflow trigger from internet. `reports/*` leaks demo data,
which is mild today but the pattern is the same as workflows.
**Fix:** wrap every route with `Depends(get_current_user)` and filter on
`user.company_id`. ~10 lines.

### C2 · No i18n framework, 170+ hardcoded English strings
**Verified by:** `grep -rEn '>[A-Z][a-z]+...' apps/web/src --include='*.tsx'`
returns 171 matches. Zero `useTranslation` calls. Zero translation files.
**Impact:** Beta users see broken bilingual UI. Russian/Kazakh accountants
will read "Approvals", "Recovery", "Open document", "Loading…" etc. in
English mixed with Russian explanations on the same page.
**Fix:** Adopt `next-intl` (or `next-i18next`), extract all user-facing
strings to `messages/ru.json`, ship Russian first, Kazakh second. Realistic
effort: **2–3 days for Russian to 100%**, another 2–3 days for Kazakh.

### C3 · Zero Kazakh-language templates
**Verified by:** SELECT all VERIFIED templates → `language='ru'` × 3, none
Kazakh.
**Impact:** Kazakh-speaking customer sends "келісім жасап бер" — gets a
Russian template silently. No "language mismatch" warning.
**Fix:** Hand-build 3 Kazakh commercial templates (act/invoice/nakladnaya),
extend matcher to score templates by language alignment with conversation
language, add explicit "no template in your language — use Russian?"
fallback message.

### C4 · `ApprovalService.decide` accepts any `decided_by` (no tenant check)
**Verified by:** real cross-tenant test, attacker user from Company B
successfully REJECTED Company A's PENDING approval via direct service
call. Endpoint layer blocks this, BUT:
- Service is the public surface for any future caller
- Two known callers exist (HTTP endpoint, Telegram callback) — both
  currently check. A third forgetful caller = full vuln.
**Impact:** Defense-in-depth failure. One regression → cross-tenant
approval bypass.
**Fix:** Move the company-isolation check INTO `decide()` itself: load
the deciding user, compare `user.company_id == approval.company_id`,
raise `PermissionError` otherwise. ~5 lines.

---

## 3. High Issues

### H1 · Telegram `verify_secret` returns True on missing secret
**File:** `apps/api/app/services/integrations/telegram/bot.py:129`.
```python
def verify_secret(self, header_token):
    if not self.webhook_secret: return True   # <-- accept any
    return header_token == self.webhook_secret
```
**Risk:** Older Integration rows with empty `webhook_secret` accept ANY
webhook request as authenticated. Current `connect` flow always generates
one, so new connects are safe. Pre-existing rows are not.
**Fix:** Invert default to deny when secret is missing; require a re-connect
to repopulate secret.

### H2 · Bot tokens / OpenAI keys stored plaintext in DB
`Integration.secrets` is a JSON column. Tokens visible in any backup, any
DB dump, any read-only replica. Relies entirely on DB encryption at rest
(Neon: yes; self-hosted with default Postgres: no).
**Fix:** Wrap in Fernet/age before insert, decrypt on read. Move encryption
key to env var. ~80 LOC.

### H3 · No rate limiting anywhere
No `slowapi`, no nginx limit_req, no per-user/per-IP throttling. Login is
unprotected. Webhook is unprotected.
**Impact:** Trivial DoS on `POST /auth/login` (bcrypt is slow). Brute force
of demo password. Telegram webhook flood drains OpenAI credits.
**Fix:** Add `slowapi` for `/auth/*` and `/telegram/*` endpoints. ~30 LOC.

### H4 · No CSP / security headers
Nginx config not audited; no `Content-Security-Policy` / `X-Frame-Options`
visible in code path. Frontend serves PDF previews via `<iframe>` — without
CSP, hostile PDF could try frame attacks.
**Fix:** Add to nginx.conf: `add_header Content-Security-Policy "..." always;`
plus `X-Frame-Options DENY` for everything but the file-preview iframe.

### H5 · No translation of structured error messages
`error: "proposal_required"`, `error: "permission_denied"`, etc. surface
to UI as English message field. User sees raw `"No recent propose_document
for kind='act'..."`.
**Fix:** Replace `error` strings with codes UI translates locally. ~50 LOC.

---

## 4. Medium Issues

### M1 · No background-job system; render blocks the request
`pipeline.generate` is synchronous, ~5–7s for DOCX→PDF via LibreOffice.
Telegram users see "Создаю…" for 5+ seconds. Not blocking but feels slow.
**Fix:** Move pipeline.generate to Celery/RQ; UI polls status.

### M2 · No request ID propagation between web and API
`X-Request-ID` not present. Debugging a user-reported issue requires
guessing from timestamps.

### M3 · Demo password is `demo1234`, plaintext in README + DEMO.md
For a public beta, demo account must be either disabled OR auto-rotating
password OR rate-limited.

### M4 · No Sentry / external error reporter wired (env var stub exists,
no DSN). All exceptions live in uvicorn console only. For beta you'll
miss every silent error.

### M5 · `Inv 10 inventarizatsionnaya opis...` template (archived now)
historically had operational_score=100 and was outscoring commercial
templates. The cleanup script `cleanup_legacy_verified.py` archived it
but if any seeding re-promotes inventory templates, the bug returns.
**Fix:** Add an assertion in install_commercial_templates that no
non-commercial template is VERIFIED at the end of the script.

### M6 · `verify_templates.py` script (older) auto-VERIFIES legacy Kazakh
inventory forms. Running it in production would re-introduce the
language-mismatch bug.
**Fix:** Delete the script or gate it behind a `--force` flag.

### M7 · DOCX QA "items_table_data_rows" heuristic is fragile
Only matches tables whose first row contains "Наимен/Кол-во/Цена/Сумма".
Kazakh templates ("Атауы/Саны/Бағасы/Сомасы") won't be detected → row
count check silently disabled.
**Fix:** Add Kazakh header markers + add a fallback "biggest commercial
table" detector with a guard against multi-table inventory layouts.

---

## 5. Low Issues

- L1: `_AMOUNT_FIRST_RE` matches `60000 за приезд` but also `60000 за двери`
  with `двери` as item name — generally fine, but with `60000 за услуга 1`
  it captures `услуга` (truncated). Polish needed.
- L2: `useEffect` listener for `assistant:send` in assistant/page.tsx has
  no dependency array → re-attaches every render. Functional but wasteful.
- L3: `parse_intent` re-runs `parse_line_items` even after explicit
  `args.items` are supplied — minor wasted work.
- L4: No favicon strategy explicitly checked; default Next.js favicon
  ships in production.
- L5: `INFO` logs include OpenAI HTTP requests — leak conversation lengths
  to anything tailing logs. Consider downgrading to DEBUG.
- L6: README and DEMO.md mention demo password in plaintext.

---

## 6. Security Findings (consolidated)

| Severity | Finding | Status |
|---|---|---|
| CRITICAL | `/workflows/*` and `/reports/*` no auth | **OPEN** |
| CRITICAL | `ApprovalService.decide` service-layer tenant gap | **OPEN** |
| HIGH | Telegram `verify_secret` deny-by-default missing | **OPEN** |
| HIGH | Tokens stored plaintext | **OPEN** |
| HIGH | No rate limiting | **OPEN** |
| HIGH | No CSP headers | **OPEN** |
| MEDIUM | No request ID | **OPEN** |
| MEDIUM | Demo password in repo | **OPEN** |
| MEDIUM | No Sentry | **OPEN** |
| PASS | Cross-tenant `DocumentService.get` returns None | verified |
| PASS | Cross-tenant `InvoiceService.get` returns None | verified |
| PASS | Cross-tenant `/approvals/{id}/decide` HTTP blocks (404) | verified |
| PASS | `/api/v1/files/...` uses signed URL or bearer+ACL | code |
| PASS | Telegram webhook secret enforced when set | code |
| PASS | `propose_document` hard gate on `generate_document` | verified |
| PASS | Bot tokens not logged | grep |

---

## 7. Functional Findings (Section 1)

Verified by smoke harness + targeted code reads. UX-level "click around
every page" walkthrough **NOT done in this session**.

| Flow | Status | Note |
|---|---|---|
| Login | PASS | bcrypt hash, JWT, tested live |
| Registration | PASS (code) | seed + demo seeder, real-user signup not stress-tested |
| Demo account | PASS | seeded, deterministic |
| AI Assistant chat | PASS (smoke) | tools + history + propose flow |
| Proposal flow | PASS (E2E) | PendingProposal, atomic claim, kind lock |
| Document generation | PASS | 18/18 smoke, quality 81–98 |
| PDF export | PASS | 100% in smoke, LibreOffice + xhtml2pdf |
| DOCX export | PASS | rendered from commercial templates |
| Approval workflow | PASS | endpoint-checked tenant isolation |
| Recovery workflow | NOT VERIFIED | endpoint + UI exist; not walked through |
| Template matching | PASS (after cleanup) | only commercial templates verified |
| Telegram integration | PASS (E2E) | deterministic propose + confirm |
| Notifications | PARTIAL | code path exists; email goes to console |
| Dashboard loading | NOT VERIFIED | live click-through not done |
| Documents page | NOT VERIFIED | live click-through not done |
| Approvals page | NOT VERIFIED | code OK, UI not walked |
| Recovery page | NOT VERIFIED | code OK, UI not walked |
| Templates page | NOT VERIFIED | 102 templates, no walk-through |
| Integrations page | PARTIAL | Telegram panel tested; WhatsApp/Bitrix not |
| File uploads | NOT VERIFIED | OCR pipeline not exercised |

**Flows marked NOT VERIFIED** require manual click-through in a browser
session — that wasn't in scope of this code-level audit.

---

## 8. Localization Findings (Section 8)

| Metric | Value |
|---|---|
| i18n framework installed | **none** |
| Translation files | **none** |
| Hardcoded English strings in `apps/web/src` | **171** (grep count) |
| Russian-language templates | 3 (act/invoice/nakladnaya) |
| Kazakh-language templates | **0** |
| Language-aware matcher | **no** — matcher has a `language` arg but no language inference from conversation |
| Russian readiness score | **~50/100** — Russian UI is partial, templates exist |
| Kazakh readiness score | **~5/100** — only Kazakh substrings in legacy inventory templates' names |
| Estimated effort to 100% RU | 2–3 days (extract strings + translate) |
| Estimated effort to 100% KZ | additional 2–3 days + Kazakh templates |

### Page-by-page (best-effort; full walkthrough not done)

| Page | Status |
|---|---|
| Login | FAIL — labels in English |
| Registration | FAIL — same |
| Dashboard | FAIL — mixed |
| Assistant | PARTIAL — assistant message is now Russian, UI chrome English |
| Documents list | FAIL — column headers English |
| Documents detail | PARTIAL — badges English, content fields data-driven |
| Approvals | PARTIAL — "Blocked by quality gate" is English; resolution box is bilingual |
| Recovery | PARTIAL — section labels English |
| Templates | FAIL — entire library list English |
| Integrations | PASS — Telegram panel mostly Russian |
| Notifications | NOT IMPLEMENTED visibly in UI |
| Telegram messages | PASS (Russian) |

**Hardcoded English samples that beta users will see:**
- "Approvals", "Recovery", "Documents", "Templates", "Integrations"
- "Loading…", "No matching invoices", "Open file", "Download DOCX"
- "Blocked by quality gate · N issues"
- "Linked to email", "Welcome to Buchuchet"
- "PDF ready", "Quality 92/100", "VERIFIED template"

---

## 9. Deployment Blockers (Section 3)

| Check | Status |
|---|---|
| `docker-compose.prod.yml` | exists, looks sane |
| `Dockerfile.prod` (api/web) | exists per compose references |
| `.env.prod.example` | exists |
| Postgres image + healthcheck | yes |
| MinIO image + healthcheck | yes |
| Migrations on startup | yes, `init_and_seed` runs `create_all` |
| Nginx config + TLS volume | exists, **TLS certs path is `./certs` — NOT bundled, operator must provide** |
| `PUBLIC_API_URL` env var for webhook | required; documented |
| Webhook URL derivation handles proxy headers | yes, `_derive_webhook_base` honors `X-Forwarded-Proto/Host` |
| Hardcoded localhost in frontend | All guarded by `process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"` — set the env var at build time |
| Health check endpoint | `/health` + `/health/diagnostics` |
| Logging to stdout (Docker-friendly) | yes, structlog JSON |
| Sentry DSN env var | wired but optional — leave unset = silent errors |
| Backup script | `infra/backup.sh` exists (not audited) |

**Production deployment checklist:**

1. ☐ Fill `.env.prod` (DATABASE_URL, JWT_SECRET=32 random bytes,
   OPENAI_API_KEY, S3_*, PUBLIC_API_URL=https://api.your.domain,
   SENTRY_DSN)
2. ☐ Provide TLS certs at `infra/certs/` (Let's Encrypt or your cert)
3. ☐ Edit `nginx.conf` for your domain name
4. ☐ `docker compose -f infra/docker-compose.prod.yml up -d --build`
5. ☐ Verify `https://api.your.domain/health` returns ok
6. ☐ Wipe the demo company OR rotate `demo1234` password
7. ☐ Test webhook by connecting a Telegram bot through the UI
8. ☐ Add `slowapi` rate limit on `/auth/*` (currently missing)
9. ☐ Add CSP headers to nginx.conf
10. ☐ Apply fixes for C1, C4, H1 BEFORE going live

---

## 10. Beta Readiness Score

**Numerical breakdown (honest):**

| Dimension | Score | Notes |
|---|---|---|
| Functional correctness | 75/100 | 18/18 smoke pass; UI walkthrough not done |
| Security | 45/100 | CRITICAL endpoint exposure + tenant defense gap |
| Localization | 25/100 | No i18n; zero Kazakh |
| Deployment | 70/100 | Files exist, prereqs documented, no tests run |
| UX polish | 55/100 | bilingual chaos, but core flows work |
| Reliability | 90/100 | smoke + state machine + parser-wins all solid |
| Observability | 50/100 | structured logs yes, Sentry no, request id no |

**Overall: 58/100.**

---

## 11. Production Readiness Score

**Overall: 45/100** — because the C1 (no-auth workflows) finding is a
real-world exploitable hole. Without it the score would be ~65.

---

## 12. GO / NO-GO Recommendation

| Audience | Decision | Reason |
|---|---|---|
| **Internal demo** (you, team) | **GO** | smoke passes, Telegram E2E works, demo password documented in DEMO.md |
| **External beta** (10–50 friendly users) | **NO-GO** | C1 (no-auth workflows) is exploitable from internet; bilingual UI looks unprofessional; no Kazakh |
| **First paying customer** | **HARD NO-GO** | until C1+C4+H1 fixed AND i18n minimally in place |

---

## 13. Exact Fixes Required Before External Testing

Estimated effort: **3–5 focused engineering days**.

1. **C1 — Auth on workflows + reports endpoints.** Add `Depends(get_current_user)` + company filter. ~15 LOC, half day.
2. **C4 — Move tenant check INTO `ApprovalService.decide`.** ~10 LOC.
3. **H1 — `verify_secret` deny-by-default.** ~3 LOC + migration to backfill secrets on existing rows. Half day.
4. **H3 — `slowapi` on `/auth/login` and `/telegram/{company_id}`.** ~30 LOC, half day.
5. **C2 (minimal) — Adopt `next-intl`, translate the 5 critical pages
   (Dashboard, Assistant, Approvals, Documents, Integrations) to Russian
   only.** Skip Kazakh for first beta wave. 2 focused days.
6. **M3 — Rotate demo password OR rate-limit it OR wipe demo seed on
   prod boot.** Half day.
7. **Tag a release.** Half day.

---

## 14. Exact Fixes Required Before First Paying Customer

Everything in §13 plus:

1. **C3 — Build 3 Kazakh templates (act / invoice / nakladnaya).** ~1 day.
2. **Language-aware matcher** — score templates by `language` matching
   conversation language; explicit "no template in <lang>, use Russian?"
   confirmation when missing. ~80 LOC.
3. **C2 (full) — Translate ALL UI strings to Russian and Kazakh.** Add
   user language preference in profile + Telegram per-user language. ~3
   days.
4. **H2 — Encrypt `Integration.secrets` (bot tokens, API keys) at rest
   with Fernet + KMS key in env.** 1 day.
5. **H4 — CSP headers + security review of nginx.conf.** Half day.
6. **M1 — Background job queue** (Celery + Redis) so render doesn't block
   web request. 2 days.
7. **M4 — Sentry DSN configured, alerts wired.** Half day.
8. **Real backup verification** — run `infra/backup.sh`, restore on
   staging, verify byte-for-byte. Half day.
9. **Real penetration test** by someone other than me (this audit is
   code-inspection, not pentest). Outside scope.

Total estimated to "paying customer ready": **~10 focused days**.

---

## What this audit did NOT verify (be honest about gaps)

- Full manual UI walkthrough of every page in a browser
- Live OCR upload flow with real Kazakh documents
- WhatsApp integration (only Telegram tested)
- Workflow execution against a real schedule
- Backup → restore cycle
- Load testing (concurrent users)
- Memory leak / long-running stability
- Email delivery (currently `console` provider)
- Mobile responsive layout
- Browser cross-compat (only Chromium implicitly)
- All 24 frontend routes individually exercised
- Penetration-style probing (this is code review, not security testing)
- Stripe/billing — not implemented yet
- Multi-region / failover behavior
