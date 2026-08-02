"""Generation stability harness (Priority 1-lite).

Runs the document-generation pipeline against the demo company across 6
scenarios x 3 iterations each (= 18 renders) and writes a strict JSON +
human-readable report covering:

  * per-scenario pass rate (rendered successfully, PDF produced, no exception)
  * fallback frequency
  * quality score distribution (avg / min)
  * approval status breakdown (PENDING / BLOCKED / etc.)
  * template stability — which templates fell back / blocked most often
  * exception patterns

This is NOT a CI gate. It's a pre-demo checklist:
  $ python scripts/smoke_generation.py
  $ python scripts/smoke_generation.py --runs 5  # heavier sweep

Exits 0 on completion regardless of pass rate — the report is the artifact.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any

from sqlalchemy import select

# Make `app.*` importable when running this script directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.db import SessionLocal  # noqa: E402
from app.db.models import Company, User  # noqa: E402
from app.db.seed import init_and_seed  # noqa: E402
from app.services.documents.generation import GenerationPipeline  # noqa: E402


# ── Scenarios — six representative happy + edge cases ─────────────────────

SCENARIOS: list[dict[str, Any]] = [
    {
        "id": "invoice_happy",
        "label": "Invoice — happy path",
        "kind": "invoice",
        "prompt": "Выстави счёт TOO Sigma на 540 000 KZT за консалтинговые услуги",
        "overrides": {"client_name": "TOO Sigma", "total": 540_000,
                       "item_description": "Консалтинговые услуги"},
    },
    {
        "id": "act_happy",
        "label": "Act — happy path",
        "kind": "act",
        "prompt": "Создай акт для TOO KazSteel Industry на 1 240 000 KZT за майскую логистику",
        "overrides": {"client_name": "TOO KazSteel Industry", "total": 1_240_000,
                       "item_description": "Майская логистика"},
    },
    {
        "id": "nakladnaya_happy",
        "label": "Накладная — happy path",
        "kind": "nakladnaya",
        "prompt": "Накладная для ИП Аманжолов А.Е. 320 000 KZT за поставку оборудования",
        "overrides": {"client_name": "ИП Аманжолов А.Е.", "total": 320_000,
                       "item_description": "Поставка оборудования"},
    },
    {
        "id": "invoice_long_strings",
        "label": "Invoice — long company name + long item description",
        "kind": "invoice",
        "prompt": "Счёт",
        "overrides": {
            "client_name": "TOO «Каспийская Логистическая Корпорация Транспортных Решений» KZ",
            "total": 7_850_000,
            "item_description": ("Комплекс работ по транспортной логистике "
                                  "Атырау–Алматы с таможенным сопровождением, "
                                  "перегрузкой и складским хранением 14 суток"),
            "qty": 1,
        },
    },
    {
        "id": "act_empty_prompt",
        "label": "Act — empty prompt (must trigger fallback gracefully)",
        "kind": "act",
        "prompt": "",
        "overrides": {},
    },
    {
        "id": "invoice_high_total_no_items",
        "label": "Invoice — extreme total, no client (must trigger quality block)",
        "kind": "invoice",
        "prompt": "",
        "overrides": {"total": 999_999_999.0},
    },
    # ── Multi-item stress scenarios (Priority 5-lite) ─────────────────────
    {
        "id": "act_three_items",
        "label": "Act — 3 line items from multi-line prompt",
        "kind": "act",
        "prompt": (
            "Создай акт для TOO Sigma:\n"
            "разработка сайта — 350000\n"
            "дизайн UI/UX — 120000\n"
            "хостинг и SSL — 30000"
        ),
        "overrides": {"client_name": "TOO Sigma"},
    },
    {
        "id": "invoice_ten_items_with_qty",
        "label": "Invoice — 10 items with quantities and long names",
        "kind": "invoice",
        "prompt": (
            "Счёт для TOO KazSteel Industry:\n"
            "- 12 шт металлопрокат катаный листовой — 720000\n"
            "- 4 шт уголок стальной горячекатаный 50x50 — 18000\n"
            "- 8 шт труба профильная электросварная 40x40x2 — 64000\n"
            "- 25 шт швеллер П-образный 14 — 187500\n"
            "- доставка Атырау-Алматы с таможенным сопровождением — 145000\n"
            "- погрузка и разгрузка вилочным погрузчиком — 28000\n"
            "- упаковка термоусадочной плёнкой — 12000\n"
            "- складское хранение 7 суток — 35000\n"
            "- страхование груза по всем рискам — 18500\n"
            "- комиссия за оформление документов — 7500"
        ),
        "overrides": {"client_name": "TOO KazSteel Industry"},
    },
    {
        "id": "nakladnaya_mixed_punctuation",
        "label": "Накладная — mixed RU/KZ punctuation, em-dashes, № signs",
        "kind": "nakladnaya",
        "prompt": (
            "Накладная для ИП Аманжолов:\n"
            "Товар №1 запчасти — 250 000\n"
            "Товар №2 расходные материалы — 100 000\n"
            "доставка по г. Алматы — 15 000"
        ),
        "overrides": {"client_name": "ИП Аманжолов А.Е."},
    },
]


# ── Runner ─────────────────────────────────────────────────────────────────

async def run_one(pipe: GenerationPipeline, session, *, company_id, actor_id, scenario) -> dict:
    t0 = time.perf_counter()
    record: dict[str, Any] = {
        "scenario": scenario["id"], "label": scenario["label"], "kind": scenario["kind"],
    }
    try:
        result = await pipe.generate(
            session, company_id=company_id, actor_id=actor_id, actor_type="harness",
            kind=scenario["kind"], prompt=scenario.get("prompt"),
            overrides=scenario.get("overrides") or None,
        )
        record.update({
            "ok": True,
            "document_id":      result.document_id,
            "number":           result.document_number,
            "template_id":      result.template_id,
            "template_name":    result.template_name or None,
            "fallback_used":    result.fallback_used,
            "fallback_reason":  result.fallback_reason,
            "adaptation_applied": result.adaptation_applied,
            "adaptation_anchors": result.adaptation_anchors_injected,
            "quality_score":    (result.quality or {}).get("score"),
            "quality_status":   (result.quality or {}).get("status"),
            "pdf_ready":        bool(result.pdf_url),
            "approval_status":  result.approval_status,
            "render_ms":        result.render_duration_ms,
            "diagnostics_count": len(result.diagnostics or []),
            "error_codes": [
                d.get("code") for d in (result.diagnostics or [])
                if d.get("severity") == "error"
            ],
        })
    except Exception as exc:  # noqa: BLE001
        record.update({
            "ok": False,
            "exception_type": type(exc).__name__,
            "exception_msg":  str(exc)[:240],
        })
    record["wall_ms"] = int((time.perf_counter() - t0) * 1000)
    return record


async def run_harness(runs_per_scenario: int = 3) -> dict[str, Any]:
    await init_and_seed()
    async with SessionLocal() as session:
        company = (await session.scalars(select(Company).limit(1))).first()
        user = (await session.scalars(
            select(User).where(User.company_id == company.id).limit(1)
        )).first()
        pipe = GenerationPipeline()
        results: list[dict] = []
        started = time.time()
        for scenario in SCENARIOS:
            for i in range(runs_per_scenario):
                rec = await run_one(pipe, session, company_id=company.id,
                                     actor_id=user.id, scenario=scenario)
                rec["iteration"] = i + 1
                results.append(rec)
        await session.commit()
        return {
            "started_at": started, "finished_at": time.time(),
            "company_id": company.id,
            "runs_per_scenario": runs_per_scenario,
            "scenarios": [s["id"] for s in SCENARIOS],
            "results": results,
            "summary": summarise(results),
        }


# ── Reporting ──────────────────────────────────────────────────────────────

def summarise(results: list[dict]) -> dict[str, Any]:
    total = len(results)
    ok = [r for r in results if r.get("ok")]
    fail = [r for r in results if not r.get("ok")]

    # Group by scenario.
    by_scenario: dict[str, list[dict]] = {}
    for r in results:
        by_scenario.setdefault(r["scenario"], []).append(r)
    per_scenario = {}
    for sid, rs in by_scenario.items():
        passed = [r for r in rs if r.get("ok")]
        quality_scores = [r.get("quality_score") for r in passed if r.get("quality_score") is not None]
        per_scenario[sid] = {
            "label":             rs[0]["label"],
            "runs":              len(rs),
            "pass":              len(passed),
            "pass_rate":         round(len(passed) / len(rs), 3) if rs else 0,
            "fallback_rate":     round(sum(1 for r in passed if r.get("fallback_used")) / len(passed), 3) if passed else 0,
            "pdf_rate":          round(sum(1 for r in passed if r.get("pdf_ready")) / len(passed), 3) if passed else 0,
            "blocked_rate":      round(sum(1 for r in passed if r.get("approval_status") == "BLOCKED") / len(passed), 3) if passed else 0,
            "avg_quality":       round(statistics.mean(quality_scores), 1) if quality_scores else None,
            "min_quality":       min(quality_scores) if quality_scores else None,
            "avg_render_ms":     int(statistics.mean(r["render_ms"] for r in passed)) if passed else 0,
            "max_render_ms":     max((r["render_ms"] for r in passed), default=0),
            "exceptions": [
                {"type": r["exception_type"], "msg": r["exception_msg"]}
                for r in rs if not r.get("ok")
            ],
        }

    # Template stability.
    tpl: dict[str, dict[str, Any]] = {}
    for r in ok:
        tid = r.get("template_id") or "(fallback-no-template)"
        bucket = tpl.setdefault(tid, {
            "template_name": r.get("template_name"),
            "renders": 0, "fallbacks": 0, "blocks": 0,
            "quality_scores": [],
        })
        bucket["renders"] += 1
        if r.get("fallback_used"):       bucket["fallbacks"] += 1
        if r.get("approval_status") == "BLOCKED": bucket["blocks"] += 1
        if r.get("quality_score") is not None:
            bucket["quality_scores"].append(r["quality_score"])
    template_stability = []
    for tid, b in tpl.items():
        qs = b["quality_scores"]
        template_stability.append({
            "template_id":   tid,
            "template_name": b["template_name"],
            "renders":       b["renders"],
            "fallback_rate": round(b["fallbacks"] / b["renders"], 3),
            "block_rate":    round(b["blocks"] / b["renders"], 3),
            "avg_quality":   round(statistics.mean(qs), 1) if qs else None,
        })
    template_stability.sort(key=lambda x: (x["fallback_rate"], -(x["avg_quality"] or 0)))

    # Aggregate error codes from diagnostics.
    error_codes: dict[str, int] = {}
    for r in ok:
        for code in r.get("error_codes") or []:
            error_codes[code] = error_codes.get(code, 0) + 1
    error_codes_sorted = sorted(error_codes.items(), key=lambda x: -x[1])

    return {
        "total_runs":          total,
        "pass":                len(ok),
        "fail":                len(fail),
        "pass_rate":           round(len(ok) / total, 3) if total else 0,
        "fallback_rate":       round(sum(1 for r in ok if r.get("fallback_used")) / len(ok), 3) if ok else 0,
        "block_rate":          round(sum(1 for r in ok if r.get("approval_status") == "BLOCKED") / len(ok), 3) if ok else 0,
        "pdf_rate":            round(sum(1 for r in ok if r.get("pdf_ready")) / len(ok), 3) if ok else 0,
        "avg_render_ms":       int(statistics.mean(r["render_ms"] for r in ok)) if ok else 0,
        "per_scenario":        per_scenario,
        "template_stability":  template_stability,
        "common_error_codes":  [{"code": c, "count": n} for c, n in error_codes_sorted[:10]],
    }


def render_text_report(report: dict) -> str:
    s = report["summary"]
    lines = [
        "================  Buchuchet · Generation Smoke Harness  ================",
        f"Runs: {s['total_runs']} ({report['runs_per_scenario']}x x {len(report['scenarios'])} scenarios)",
        f"Pass:        {s['pass']}/{s['total_runs']}  ({s['pass_rate'] * 100:.1f}%)",
        f"Fallback:    {s['fallback_rate'] * 100:.1f}%   "
        f"Blocked:     {s['block_rate'] * 100:.1f}%   "
        f"PDF ready:   {s['pdf_rate'] * 100:.1f}%",
        f"Avg render:  {s['avg_render_ms']} ms",
        "",
        "── Per-scenario ──────────────────────────────────────────────",
    ]
    for sid, st in s["per_scenario"].items():
        q = f"avg_q={st['avg_quality']}/min={st['min_quality']}" if st["avg_quality"] is not None else "no quality data"
        lines.append(
            f"  {sid:32s}  pass {st['pass']}/{st['runs']}  "
            f"fb={st['fallback_rate']*100:>4.0f}%  "
            f"blocked={st['blocked_rate']*100:>4.0f}%  "
            f"pdf={st['pdf_rate']*100:>4.0f}%  "
            f"{q}  {st['avg_render_ms']}ms"
        )
        for exc in st.get("exceptions", []):
            lines.append(f"      -> EXCEPTION {exc['type']}: {exc['msg'][:120]}")
    lines.append("")
    lines.append("── Template stability (sorted: lowest fallback first) ─────")
    for t in s["template_stability"]:
        lines.append(
            f"  {(t['template_name'] or '(fallback)')[:42]:42s}  "
            f"runs={t['renders']:<3}  fb={t['fallback_rate']*100:>4.0f}%  "
            f"blk={t['block_rate']*100:>4.0f}%  avg_q={t['avg_quality']}"
        )
    if s["common_error_codes"]:
        lines.append("")
        lines.append("── Common diagnostic error codes ──────────────────────────")
        for e in s["common_error_codes"]:
            lines.append(f"  {e['code']:32s}  x{e['count']}")
    lines.append("")
    return "\n".join(lines)


# ── CLI ────────────────────────────────────────────────────────────────────

async def amain(args) -> int:
    report = await run_harness(runs_per_scenario=args.runs)
    out_path = Path(args.output)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    # Force stdout to UTF-8 so Russian template names / Cyrillic labels render
    # on Windows terminals (default cp1251) without UnicodeEncodeError.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    print(render_text_report(report))
    print(f"\nFull JSON report -> {out_path.resolve()}")
    return 0


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--runs", type=int, default=3, help="iterations per scenario (default: 3)")
    p.add_argument("--output", default="smoke_report.json", help="path to write JSON report")
    args = p.parse_args()
    sys.exit(asyncio.run(amain(args)))


if __name__ == "__main__":
    main()
