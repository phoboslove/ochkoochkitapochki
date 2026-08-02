# Buchuchet — MVP Readiness Report

**Date:** 2026-05-23
**Smoke harness:** 18/18 pass (3 runs × 6 scenarios) — see
[`apps/api/smoke_report.json`](apps/api/smoke_report.json) for raw data.

## Headline numbers

| Metric                        | Value                       | Target  |
|-------------------------------|-----------------------------|---------|
| Pipeline crash rate           | 0 / 18                      | 0       |
| Fallback rate                 | **0%** (was 50%, then 100%) | <20%    |
| Quality-blocked rate          | 33% (correct: empty/extreme)| n/a     |
| PDF generation rate           | 100%                        | >=95%   |
| Avg render time               | 5.4s                        | <10s    |
| ACT happy-path quality        | 84/100 (stable, min=max)    | >=80    |
| NAKLADNAYA happy-path quality | 90/100 (stable, min=max)    | >=80    |
| INVOICE happy-path quality    | 92/100                      | >=80    |

## Strengths

1. **Pipeline stability.** 0 crashes across 18 renders. No silent failures —
   every failed scenario surfaces structured diagnostics with `suggested_fix`.
2. **Real KZ templates rendering.** Three VERIFIED templates (`Inv 10` for
   invoice, `Inv 4` for act, `Da 4` for nakladnaya) render through LibreOffice
   to real PDFs. Fallback rate is 0% across all happy paths.
3. **Honest quality gate.** Bad inputs (empty prompt, no items) get
   `BLOCKED` correctly — documents stay downloadable, but cannot be sent.
4. **Adapter handles legacy.** Templates with raw Kazakh labels
   (`Бухгалтер`, `Поставщик`) get `{{canonical}}` placeholders injected at
   render time without modifying the stored file.
5. **Operational scoring works.** `template_operational_score` rises with
   render history (`Inv 10` is at 100/100 after 20+ successful renders),
   and the matcher uses it as additive bias.
6. **Audit trail is complete.** Every render writes `document.generated`
   with quality / fallback / template metadata. Recovery Center reads it
   live.
7. **Operator-facing UI surfaces it cleanly.** `OperationalBadges` shows
   `VERIFIED template · Reliability 100/100 · Quality 84/100 · PDF ready ·
   Rendered in 4.2s` — no raw JSON anywhere.
8. **Assistant tone is operational.** System prompt rewritten — short,
   confident, no debug strings. Tool messages are operator-style sentences,
   structured detail lives in the `card` object.

## Known limitations

1. **Template corpus is narrow.** Only 1 verified template per kind. All KZ
   templates in the library are *inventory acts* (опись), not commercial
   *acts of work*. Real customers will need to upload their own templates
   and run the mapping wizard. No template auto-mining yet.
2. **Quality stuck at 84 for act.** The verified ACT template has no items
   table, so QA deducts 10 points for `empty_items`. This is a correct
   penalty, not a bug — but it means the score stays in `warning` range
   even on happy paths. Mitigation: communicate this in the demo; real
   commercial act templates will score higher.
3. **PDF engine is xhtml2pdf for HTML.** WeasyPrint isn't installed
   (needs GTK on Windows). DOCX→PDF goes through LibreOffice (fine).
   HTML fallback PDFs are functional but lower fidelity. **Demo machines
   should have LibreOffice installed** — verified via
   `GET /health/diagnostics`.
4. **Recovery actions are partial.** `Retry send` and `Retry OCR` work.
   `Regenerate` from Recovery is shown as a button but disabled (would
   require re-running the generation pipeline with stored parameters —
   not yet wired).
5. **Some UI surfaces aren't polished.** Settings, Integrations, full
   Templates library, Anomalies pages haven't been polished. The
   `DEMO.md` explicitly avoids them.
6. **Stale invoice numbering across runs.** Each smoke run increments
   the `Document` counter, so demo numbers like `ACT-2026-0001` shift on
   re-run. Not a defect — just a recording consideration.
7. **OCR is real but limited.** OCR.Space integration works; Azure adapter
   exists but isn't wired into the demo flow. The seeder pre-populates
   parsed documents so demos don't depend on a live OCR call.
8. **No tenant isolation stress test.** RBAC enforced in code; no
   multi-tenant load test has been run.
9. **No background job system.** Heavy work runs synchronously — render
   takes 4–6s per call. Acceptable for MVP; will need a queue for scale.

## Stable flows (safe to demo)

- **Assistant → "Создай акт ..."** — 100% pass over 30+ runs.
- **Assistant → "Создай счёт ..."** — 100% pass over 30+ runs.
- **Assistant → "Создай накладную ..."** — 100% pass over 10+ runs.
- **Document detail / Recovery / Approvals** — read paths are deterministic
  on seeded data.
- **Approve & send (PENDING approval)** — works end-to-end.
- **Recovery `Retry send` / `Retry OCR`** — works.

## Risky areas (avoid in live demo)

- **Live OCR upload** — depends on network + OCR.Space API. Use pre-seeded
  documents instead. If you must demo OCR, do it once before the audience
  joins and play the resulting card.
- **WhatsApp / Telegram integrations** — disconnected by default in demo.
  Don't click `Connect` mid-demo.
- **Plan upgrade / Stripe** — no Stripe yet. UI exists but pressing
  upgrade does nothing.
- **`/settings/templates` list** — shows 102 entries, mostly ANALYZED
  (legacy clutter). Don't scroll through it unprompted.
- **Stress-rendering the same prompt 50× in 30 seconds** — Neon Postgres
  free tier rate-limits; you'll see slow renders. Demo at human pace.

## Recommended next steps after demo

In priority order:

1. **Template wizard polish.** Make the upload+map+verify flow itself a
   demoable feature. Currently it's a debug surface.
2. **Background job queue.** Move render to Celery/RQ so the UI returns
   instantly with a "generating..." state and websocket updates. Avg
   render of 5s is the biggest perceived-performance issue.
3. **Real commercial act/nakladnaya templates.** Source 2-3 real KZ
   commercial templates (акт выполненных работ, ТТН) and verify them so
   quality scores cross 90.
4. **Regenerate-from-Recovery wiring.** Closes the operator loop —
   currently the button is disabled.
5. **Settings page polish.** Branding, company defaults, plan info —
   currently sparse, blocks the "looks finished" perception on careful
   audiences.
6. **Mobile layout pass.** Currently desktop-only. Add responsive grid
   tweaks for the 3 core pages (Dashboard, Assistant, Documents).
7. **Stripe wiring.** Plan gate exists in code, no billing yet. Needed
   before any paid pilot.
8. **Multi-tenant load test.** Verify RBAC + tenant prefix isolation
   under concurrent renders.
9. **Sentry + structured-log shipping** in prod. Local logs work, no
   external collector yet.

## How to re-run the smoke gate before each demo

```powershell
cd apps\api
python scripts\smoke_generation.py --runs 3
```

Expected output: `Pass: 18/18 (100.0%)`, `Fallback: 0.0%`, `PDF ready:
100.0%`. Any regression in those numbers is a no-go for live demo —
investigate before walking on stage.

If `fallback` jumps above 0%, run `python scripts/verify_templates.py`
to re-promote the ACT + NAKLADNAYA templates (they may have been
unverified by a code path that resets template state).

## Final verdict

**Ready for a 5-minute live demo against a sophisticated audience.**

The three flows in `DEMO.md` are reliable on the seeded dataset. Bad
inputs are handled honestly (not hidden), good inputs produce real KZ
business documents, and the operator UI shows trustworthy badges.

The known limitations are mostly **scope** issues (narrow template
corpus, sparse Settings pages) rather than **correctness** issues. Show
the flows you have; acknowledge what's next when asked.
