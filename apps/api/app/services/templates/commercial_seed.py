"""Auto-install the 3 commercial KZ templates for a tenant.

Same DOCX bytes the standalone ``scripts/install_commercial_templates.py``
ships — kept in one place so the CLI script and the new-user onboarding
hook can't drift apart. New tenants get verified Russian act / invoice /
nakladnaya templates the moment they register, so the very first call to
``/documents/generate`` doesn't fall back to the built-in HTML preview.
"""
from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Template
from app.services.storage import get_storage


# Lazy-import the builders from the script: keeps this file dependency-free
# until install_for_tenant() is actually called, and means the script remains
# the single source of truth for template content.
def _builders():
    import importlib.util
    script_path = Path(__file__).resolve().parents[3] / "scripts" / "install_commercial_templates.py"
    spec = importlib.util.spec_from_file_location("_commercial_templates_builders", script_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return [
        ("act",        "Акт выполненных работ (коммерческий)",   mod.build_act_of_works,        mod.CANONICAL_MAPPING_SET),
        ("invoice",    "Счёт на оплату (коммерческий)",           mod.build_commercial_invoice,  mod.CANONICAL_MAPPING_SET),
        ("nakladnaya", "Товарная накладная (коммерческая)",       mod.build_delivery_waybill,    mod.CANONICAL_MAPPING_SET),
    ]


def _mappings(canonical_keys: list[str]) -> dict[str, dict[str, Any]]:
    return {
        k: {"source_label": k, "source_kind": "canonical",
            "confidence": 0.95, "confirmed": True}
        for k in canonical_keys
    }


async def install_for_tenant(session: AsyncSession, *, company_id: str) -> int:
    """Install the 3 commercial templates for a brand-new company.

    Idempotent: skips any kind that already has a VERIFIED commercial
    template by name. Returns the number of templates inserted.
    """
    storage = get_storage()
    inserted = 0
    for kind, display_name, builder, canonical_set in _builders():
        # Skip if already present (e.g. re-running for the demo seed).
        existing = await session.scalar(
            select(Template).where(
                Template.company_id == company_id,
                Template.name == display_name,
            ),
        )
        if existing:
            continue

        blob = builder()
        file_hash = hashlib.sha256(blob).hexdigest()
        tpl_id = f"tpl_{uuid.uuid4().hex[:10]}"
        storage_key = f"{company_id}/templates/{tpl_id}/{display_name}.docx"
        storage.put(storage_key, blob, content_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ))
        session.add(Template(
            id=tpl_id, company_id=company_id,
            name=display_name, kind=kind, format="docx",
            body=storage_key, is_default=True,
            status="VERIFIED",
            original_filename=f"{display_name}.docx",
            file_hash=file_hash, language="ru", version=1,
            detected_fields={
                "placeholders": list(canonical_set),
                "tables": [{"rows": 1, "cols": 6, "is_items": True}],
                "semantic": {"kind": kind, "commercial": True},
                "built_by": "commercial_seed.install_for_tenant",
            },
            detected_tables=[{"rows": 1, "cols": 6, "is_items": True,
                                "header": ["№","Наименование","Ед.","Кол-во","Цена","Сумма"]}],
            mappings=_mappings(canonical_set),
            confidence=0.95,
            validation_score=95, validation_warnings=[],
            industry="general",
        ))
        inserted += 1
    await session.flush()
    return inserted
