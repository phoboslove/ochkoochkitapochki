"""Promote 2 selected templates to VERIFIED with canonical mappings.

This is a one-shot operational script — pick the best ACT + NAKLADNAYA DOCX
candidates from the company's library, install a standard canonical mapping
set so the renderer + adapter pipeline can lookup values, and flip status
to VERIFIED so the matcher picks them up.

The mapping uses the canonical key itself as ``source_label``. The adapter
injects ``{{canonical}}`` placeholders at render-time near anchor labels in
the legacy KZ text, so the resolved values come from canonical context.

Run:
  $ python scripts/verify_templates.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.db import SessionLocal  # noqa: E402
from app.db.models import Company, Template  # noqa: E402


# Canonical fields that we install as "confirmed" mappings. The adapter
# injects `{{key}}` placeholders for each at render time; the renderer's
# context already supplies these as flat keys + nested aliases.
CANONICAL_MAPPING_SET = [
    "company_name", "company_bin", "company_address",
    "client_name", "client_bin", "client_address",
    "document_number", "document_date",
    "total", "subtotal", "vat", "currency",
    "director_name", "accountant_name", "notes",
]


# Candidate (kind, exact_template_name_prefix). DOCX only — render path is
# strongest there and adapter handles legacy Kazakh layouts.
PICKS = [
    ("act",        "Inv 4 akt inventarizatsii debitorskoy"),
    ("nakladnaya", "Da 4 nakladnaya na vnutrennee peremeshchenie dolgosrochnykh"),
]


def _build_mappings() -> dict[str, dict]:
    return {
        key: {
            "source_label": key,
            "source_kind":  "canonical",
            "confidence":   0.9,
            "confirmed":    True,
        }
        for key in CANONICAL_MAPPING_SET
    }


async def promote() -> None:
    async with SessionLocal() as session:
        company = (await session.scalars(select(Company).limit(1))).first()
        if not company:
            print("no company found — seed first"); return
        print(f"company = {company.id} ({company.name})")
        promoted: list[Template] = []
        for kind, name_prefix in PICKS:
            t = (await session.scalars(
                select(Template).where(
                    Template.company_id == company.id,
                    Template.kind == kind,
                    Template.format == "docx",
                    Template.name.startswith(name_prefix[:30]),
                ).limit(1),
            )).first()
            if not t:
                print(f"  [{kind}] candidate not found ({name_prefix!r}) — SKIP")
                continue
            mappings = _build_mappings()
            t.mappings = {**(t.mappings or {}), **mappings}
            t.status = "VERIFIED"
            t.confidence = max(t.confidence or 0, 0.85)
            t.validation_warnings = (t.validation_warnings or []) + [
                "Promoted to VERIFIED via verify_templates.py — canonical mapping set installed; "
                "adapter resolves Kazakh labels at render time.",
            ]
            promoted.append(t)
            print(f"  [{kind}] VERIFIED  {t.name}  (mappings={len(t.mappings)}, confidence={t.confidence})")
        await session.commit()
        print(f"\nDone. Promoted {len(promoted)} templates.")


if __name__ == "__main__":
    asyncio.run(promote())
